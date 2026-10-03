"""The write_code grader, which actually executes student code."""

from __future__ import annotations

import time
from pathlib import Path

from app.runner import run_write_code

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


def test_student_file_writes_do_not_touch_the_repo(library, tmp_path):
    """The subprocess runs in a temp cwd, so a relative write lands there."""
    problem = library.problem("WC_01")
    marker = "relearn_should_not_exist.txt"
    code = (
        f"open({marker!r}, 'w').write('x')\n"
        "def sum_to(n):\n    return sum(range(1, n + 1))"
    )
    is_correct, _ = run_write_code(problem, code, TIMEOUT)
    assert is_correct is True
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
