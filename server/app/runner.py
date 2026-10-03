"""Grades write_code answers by running them in a separate Python process.

The student's code is never passed to exec() or eval() inside the server
process (brief s6 step 2). It is screened, then written to a temp directory
together with a generated harness and run as an isolated subprocess.

Four layers keep a hostile answer away from the server:

1. `screen_student_code` rejects the code outright if its syntax tree reaches
   for the filesystem, the network, other processes or the import machinery.
   An introductory Python answer never needs any of it.
2. The subprocess gets a minimal environment (`_subprocess_env`), not the
   server's, so secrets passed in as env vars are not visible to it.
3. `-I -S -B` isolate it from the server's sys.path, site-packages and
   PYTHONPATH, and the working directory is a temp directory that is deleted
   afterwards.
4. Results come back through a file in that temp directory, so a program that
   prints anything at all - including something shaped like our own marker -
   cannot corrupt the parse.

Still missing, and deliberately out of scope: a memory cap and a network
block. Both need platform specific work that is awkward on Windows. Layer 1
stands in for them, which is why SERVE_WRITE_CODE defaults to false.
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from .data import Problem

RESULTS_FILENAME = "__relearn_results.json"

# Longest `got`/`error` string sent back to the browser. A program that
# returns a megabyte of text should not become a megabyte of JSON response.
MAX_VALUE_CHARS = 400

# Names an introductory Python answer has no reason to touch.
_BANNED_NAMES = frozenset(
    {
        "open",
        "eval",
        "exec",
        "compile",
        "__import__",
        "input",
        "breakpoint",
        "globals",
        "locals",
        "vars",
        "memoryview",
    }
)
_BANNED_MODULES = frozenset(
    {
        "builtins",
        "code",
        "codeop",
        "ctypes",
        "gc",
        "glob",
        "http",
        "importlib",
        "inspect",
        "io",
        "marshal",
        "multiprocessing",
        "os",
        "pathlib",
        "pickle",
        "requests",
        "resource",
        "shutil",
        "signal",
        "socket",
        "subprocess",
        "sys",
        "tempfile",
        "threading",
        "urllib",
        "webbrowser",
    }
)
# Attribute hops that walk out of the sandbox from any ordinary object.
_BANNED_ATTRS = frozenset(
    {
        "__bases__",
        "__builtins__",
        "__class__",
        "__code__",
        "__dict__",
        "__getattribute__",
        "__globals__",
        "__loader__",
        "__mro__",
        "__reduce__",
        "__reduce_ex__",
        "__spec__",
        "__subclasses__",
    }
)

_HARNESS = """
import json, sys, traceback

sys.setrecursionlimit(2000)
RESULTS = []
for call, expected in CASES:
    try:
        value = eval(call, GLOBALS)
        got = repr(value)
        RESULTS.append({"call": call, "expected": expected, "got": got,
                        "passed": got == expected, "error": None})
    except Exception:
        RESULTS.append({"call": call, "expected": expected, "got": None,
                        "passed": False,
                        "error": traceback.format_exception_only(*sys.exc_info()[:2])[-1].strip()})

with open(RESULTS_PATH, "w", encoding="utf-8") as _handle:
    json.dump(RESULTS, _handle)
"""


@dataclass
class TestResult:
    call: str
    expected: str
    got: str | None
    passed: bool
    error: str | None


def screen_student_code(student_code: str) -> str | None:
    """Return why this code must not be run, or None when it is safe to run.

    Rejection happens by syntax tree, before anything executes. A SyntaxError
    is not a rejection: the subprocess reports it as an ordinary wrong answer,
    which is what a student with a typo should see.
    """
    try:
        tree = ast.parse(student_code)
    except SyntaxError:
        return None

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in _BANNED_MODULES:
                    return f"importing {root!r} is not allowed here"
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root in _BANNED_MODULES:
                return f"importing from {root!r} is not allowed here"
        elif isinstance(node, ast.Name) and node.id in _BANNED_NAMES:
            return f"{node.id}() is not allowed here"
        elif isinstance(node, ast.Attribute) and node.attr in _BANNED_ATTRS:
            return f"the attribute {node.attr!r} is not allowed here"
    return None


def _subprocess_env(workdir: str) -> dict[str, str]:
    """A minimal environment, so the server's own env vars are not inherited.

    Windows refuses to start a process without SystemRoot, and Python reaches
    for ComSpec in a few stdlib calls, so those are kept. Nothing else is.
    """
    env = {
        "PYTHONIOENCODING": "utf-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
        "TEMP": workdir,
        "TMP": workdir,
        "TMPDIR": workdir,
    }
    if sys.platform == "win32":
        for key in ("SystemRoot", "ComSpec", "PATHEXT", "NUMBER_OF_PROCESSORS"):
            value = os.environ.get(key)
            if value:
                env[key] = value
    else:
        env["PATH"] = "/usr/bin:/bin"
    return env


def _script(student_code: str, problem: Problem, results_path: Path) -> str:
    cases = [[tc.call, tc.expected] for tc in problem.test_cases]
    return (
        "import io, sys\n"
        "_captured = io.StringIO()\n"
        "_real_stdout = sys.stdout\n"
        "sys.stdout = _captured\n"
        "GLOBALS = {}\n"
        "try:\n"
        f"    exec(compile({student_code!r}, '<student>', 'exec'), GLOBALS)\n"
        "finally:\n"
        "    sys.stdout = _real_stdout\n"
        f"CASES = {cases!r}\n"
        f"RESULTS_PATH = {str(results_path)!r}\n" + _HARNESS
    )


def _clip(value: str | None) -> str | None:
    """Cap one returned value, so a huge result cannot flood the response."""
    if value is None or len(value) <= MAX_VALUE_CHARS:
        return value
    dropped = len(value) - MAX_VALUE_CHARS
    return value[:MAX_VALUE_CHARS] + f"... [{dropped} more characters]"


def run_write_code(
    problem: Problem, student_code: str, timeout_seconds: float
) -> tuple[bool, list[dict]]:
    """Return (is_correct, test_results). Correct only when every test passes."""
    if not problem.test_cases:
        raise ValueError(f"{problem.problem_id} has no test cases to run")

    rejection = screen_student_code(student_code)
    if rejection is not None:
        return False, _all_failed(problem, rejection)

    with tempfile.TemporaryDirectory(prefix="relearn-run-") as workdir:
        script_path = Path(workdir) / "attempt.py"
        results_path = Path(workdir) / RESULTS_FILENAME
        script_path.write_text(
            _script(student_code, problem, results_path), encoding="utf-8"
        )
        try:
            completed = subprocess.run(
                [sys.executable, "-I", "-S", "-B", str(script_path)],
                cwd=workdir,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                stdin=subprocess.DEVNULL,
                env=_subprocess_env(workdir),
            )
        except subprocess.TimeoutExpired:
            return False, _all_failed(problem, f"timed out after {timeout_seconds:g}s")

        # The harness writes the file last, so its absence means the student's
        # own code raised before the test cases ran.
        if not results_path.exists():
            return False, _all_failed(problem, _failure_reason(completed))

        try:
            rows = json.loads(results_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False, _all_failed(problem, "the test results could not be read back")

    try:
        results = [
            asdict(
                TestResult(
                    call=str(row["call"]),
                    expected=str(row["expected"]),
                    got=_clip(row["got"]),
                    passed=bool(row["passed"]),
                    error=_clip(row["error"]),
                )
            )
            for row in rows
        ]
    except (KeyError, TypeError):
        return False, _all_failed(problem, "the test results were malformed")

    return all(row["passed"] for row in results), results


def run_probe_program(program: str, timeout_seconds: float) -> str | None:
    """Run a generated/output-bank program in the same isolated subprocess.

    Unlike write-code grading, a probe needs stdout itself. It still goes
    through the AST screen, minimal environment, isolated interpreter and
    timeout; it is never executed in the API process.
    """
    if screen_student_code(program) is not None:
        return None
    with tempfile.TemporaryDirectory(prefix="relearn-probe-") as workdir:
        script_path = Path(workdir) / "probe.py"
        script_path.write_text(program, encoding="utf-8")
        try:
            completed = subprocess.run(
                [sys.executable, "-I", "-S", "-B", str(script_path)],
                cwd=workdir,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                stdin=subprocess.DEVNULL,
                env=_subprocess_env(workdir),
            )
        except subprocess.TimeoutExpired:
            return None
    if completed.returncode != 0 or len(completed.stdout) > MAX_VALUE_CHARS:
        return None
    return completed.stdout.rstrip("\r\n")


def _failure_reason(completed: subprocess.CompletedProcess) -> str:
    detail = (completed.stderr or "").strip().splitlines()
    if not detail:
        return "the program produced no result"
    return _clip(detail[-1]) or "the program produced no result"


def _all_failed(problem: Problem, error: str) -> list[dict]:
    return [
        asdict(TestResult(call=tc.call, expected=tc.expected, got=None, passed=False, error=error))
        for tc in problem.test_cases
    ]
