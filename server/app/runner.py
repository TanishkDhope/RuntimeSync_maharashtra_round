"""Grades write_code answers by running them in a separate Python process.

The student's code is never passed to exec() or eval() inside the server
process (brief s6 step 2). It is written to a temp directory together with a
generated harness and run as an isolated subprocess with a timeout.

Not yet hardened: no memory cap and no network block. Both need platform
specific work (and are awkward on Windows), so they are a later milestone.
The subprocess does run with a temp working directory, so stray file writes
land there and the directory is deleted afterwards.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from .data import Problem

_HARNESS = '''
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

sys.stdout.write("__RELEARN_RESULTS__" + json.dumps(RESULTS))
'''


@dataclass
class TestResult:
    call: str
    expected: str
    got: str | None
    passed: bool
    error: str | None


def _script(student_code: str, problem: Problem) -> str:
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
        + _HARNESS
    )


def run_write_code(
    problem: Problem, student_code: str, timeout_seconds: float
) -> tuple[bool, list[dict]]:
    """Return (is_correct, test_results). Correct only when every test passes."""
    if not problem.test_cases:
        raise ValueError(f"{problem.problem_id} has no test cases to run")

    with tempfile.TemporaryDirectory(prefix="relearn-run-") as workdir:
        script_path = Path(workdir) / "attempt.py"
        script_path.write_text(_script(student_code, problem), encoding="utf-8")
        try:
            completed = subprocess.run(
                [sys.executable, "-I", "-S", "-B", str(script_path)],
                cwd=workdir,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                stdin=subprocess.DEVNULL,
            )
        except subprocess.TimeoutExpired:
            return False, _all_failed(problem, f"timed out after {timeout_seconds:g}s")

    marker = "__RELEARN_RESULTS__"
    if marker not in completed.stdout:
        detail = (completed.stderr or completed.stdout or "").strip().splitlines()
        reason = detail[-1] if detail else "the program produced no result"
        return False, _all_failed(problem, reason)

    payload = completed.stdout.split(marker, 1)[1]
    results = [asdict(TestResult(**row)) for row in json.loads(payload)]
    return all(row["passed"] for row in results), results


def _all_failed(problem: Problem, error: str) -> list[dict]:
    return [
        asdict(TestResult(call=tc.call, expected=tc.expected, got=None, passed=False, error=error))
        for tc in problem.test_cases
    ]
