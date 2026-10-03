"""The write_code grader, which actually executes student code."""

from __future__ import annotations

import time
from pathlib import Path

from app.runner import MAX_VALUE_CHARS, run_write_code, screen_student_code

TIMEOUT = 3.0


def test_reference_solution_passes_every_test(library):
    problem = library.problem("WC_01")
    is_correct, results = run_write_code(problem, problem.reference_solution, TIMEOUT)
    assert is_correct is True
    assert all(row["passed"] for row in results)
    assert len(results) == len(problem.test_cases)


def test_every_reference_solution_in_the_dataset_passes(library):
    """Guards the dataset: a write_code problem whose own solution fails is broken."""
    for problem in library.problems.values():
        if problem.item_type != "write_code":
            continue
        is_correct, results = run_write_code(problem, problem.reference_solution, TIMEOUT)
        failures = [row for row in results if not row["passed"]]
        assert is_correct, f"{problem.problem_id}: {failures}"


def test_wrong_solution_fails_with_per_test_detail(library):
    problem = library.problem("WC_01")
    is_correct, results = run_write_code(problem, "def sum_to(n):\n    return 0", TIMEOUT)
    assert is_correct is False
    assert results[0]["got"] == "0"
    assert results[0]["expected"] == "6"
    assert results[0]["error"] is None


def test_off_by_one_solution_fails(library):
    """range(1, n) instead of range(1, n + 1) - the RANGE_* family of beliefs."""
    problem = library.problem("WC_01")
    code = "def sum_to(n):\n    total = 0\n    for i in range(1, n):\n        total += i\n    return total"
    is_correct, results = run_write_code(problem, code, TIMEOUT)
    assert is_correct is False
    assert results[0]["got"] == "3"  # 1 + 2, missing the 3


def test_infinite_loop_is_killed_by_the_timeout(library):
    problem = library.problem("WC_01")
    started = time.monotonic()
    is_correct, results = run_write_code(problem, "def sum_to(n):\n    while True:\n        pass", 2.0)
    elapsed = time.monotonic() - started

    assert is_correct is False
    assert elapsed < 15.0, "the timeout did not stop the subprocess"
    assert all("timed out" in row["error"] for row in results)


def test_syntax_error_is_reported_not_raised(library):
    problem = library.problem("WC_01")
    is_correct, results = run_write_code(problem, "def sum_to(n)\n    return 1", TIMEOUT)
    assert is_correct is False
    assert "SyntaxError" in results[0]["error"]


def test_missing_function_is_reported(library):
    problem = library.problem("WC_01")
    is_correct, results = run_write_code(problem, "x = 1", TIMEOUT)
    assert is_correct is False
    assert "NameError" in results[0]["error"]


def test_exception_inside_the_function_is_reported(library):
    problem = library.problem("WC_01")
    is_correct, results = run_write_code(problem, "def sum_to(n):\n    return 1 / 0", TIMEOUT)
    assert is_correct is False
    assert "ZeroDivisionError" in results[0]["error"]


def test_string_results_compare_by_repr(library):
    """test_cases carry reprs ("'bcd'"), so str() comparison would be wrong."""
    problem = library.problem("WC_04")
    assert problem.test_cases[0].expected.startswith("'")
    is_correct, _ = run_write_code(problem, problem.reference_solution, TIMEOUT)
    assert is_correct is True


def test_boolean_results_compare_by_repr(library):
    problem = library.problem("WC_06")
    assert problem.test_cases[0].expected in {"True", "False"}
    is_correct, _ = run_write_code(problem, problem.reference_solution, TIMEOUT)
    assert is_correct is True


def test_printing_instead_of_returning_fails(library):
    """The PRINT_IS_RETURN belief: printing is not returning."""
    problem = library.problem("WC_01")
    code = "def sum_to(n):\n    print(sum(range(1, n + 1)))"
    is_correct, results = run_write_code(problem, code, TIMEOUT)
    assert is_correct is False
    assert results[0]["got"] == "None"


def test_student_file_writes_are_rejected_and_never_reach_the_repo(library):
    """open() is screened out, so the write never happens anywhere."""
    problem = library.problem("WC_01")
    marker = "relearn_should_not_exist.txt"
    code = (
        f"open({marker!r}, 'w').write('x')\n"
        "def sum_to(n):\n    return sum(range(1, n + 1))"
    )
    is_correct, results = run_write_code(problem, code, TIMEOUT)
    assert is_correct is False
    assert "open() is not allowed" in results[0]["error"]
    assert not (Path.cwd() / marker).exists()


def test_student_code_cannot_see_the_server_modules(library):
    """-I keeps the server's directory off sys.path in the subprocess."""
    problem = library.problem("WC_01")
    code = (
        "import app.config\n"
        "def sum_to(n):\n    return sum(range(1, n + 1))"
    )
    is_correct, results = run_write_code(problem, code, TIMEOUT)
    assert is_correct is False
    assert "ModuleNotFoundError" in results[0]["error"]


# --- hostile answers (review 1.2, 1.3) --------------------------------------

def test_reading_the_server_env_file_is_rejected(library):
    """The attack from the review: open the server's own .env and return it."""
    problem = library.problem("WC_01")
    env_path = Path(__file__).resolve().parent.parent / ".env"
    code = f"def sum_to(n):\n    return open({str(env_path)!r}).read()"
    is_correct, results = run_write_code(problem, code, TIMEOUT)

    assert is_correct is False
    assert "open() is not allowed" in results[0]["error"]
    # Nothing from the file comes back, whatever the file holds.
    assert results[0]["got"] is None


def test_importing_os_is_rejected(library):
    problem = library.problem("WC_01")
    code = "import os\ndef sum_to(n):\n    return os.environ.get('PATH')"
    is_correct, results = run_write_code(problem, code, TIMEOUT)
    assert is_correct is False
    assert "importing 'os' is not allowed" in results[0]["error"]


def test_dunder_class_walk_is_rejected(library):
    """The usual escape: reach the subprocess builtins through any object."""
    problem = library.problem("WC_01")
    code = "def sum_to(n):\n    return ().__class__.__bases__"
    is_correct, results = run_write_code(problem, code, TIMEOUT)
    assert is_correct is False
    assert "not allowed" in results[0]["error"]


def test_printing_the_old_results_marker_does_not_break_grading(library):
    """Results travel through a file now, so stdout cannot corrupt the parse."""
    problem = library.problem("WC_01")
    code = (
        'print("__RELEARN_RESULTS__" + "{bogus json")\n'
        "def sum_to(n):\n    return sum(range(1, n + 1))"
    )
    is_correct, results = run_write_code(problem, code, TIMEOUT)
    assert is_correct is True
    assert all(row["passed"] for row in results)


def test_a_huge_return_value_is_clipped(library):
    problem = library.problem("WC_01")
    code = f"def sum_to(n):\n    return 'x' * {MAX_VALUE_CHARS * 20}"
    is_correct, results = run_write_code(problem, code, TIMEOUT)
    assert is_correct is False
    assert len(results[0]["got"]) < MAX_VALUE_CHARS + 60
    assert "more characters" in results[0]["got"]


def test_the_subprocess_does_not_inherit_the_server_environment(monkeypatch, library):
    """A secret in the server's env must not be readable from student code."""
    monkeypatch.setenv("RELEARN_TEST_SECRET", "hunter2")
    problem = library.problem("WC_01")
    # A late import dodges the screen's module check, so this also proves the
    # environment itself is empty rather than relying on the screen alone.
    code = (
        "def sum_to(n):\n"
        "    import os\n"
        "    return os.environ.get('RELEARN_TEST_SECRET')"
    )
    is_correct, results = run_write_code(problem, code, TIMEOUT)
    assert is_correct is False
    assert "hunter2" not in str(results[0])


def test_screening_passes_ordinary_answers(library):
    """The screen must not reject the kind of code a student really writes."""
    for problem in library.problems.values():
        if problem.item_type != "write_code":
            continue
        assert screen_student_code(problem.reference_solution) is None, problem.problem_id


def test_a_syntax_error_is_not_treated_as_a_rejection():
    assert screen_student_code("def f(\n") is None
