"""Answer checking for predict_output."""

from __future__ import annotations

import pytest

from app.checking import check_predict_output, normalise_output


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("9 4", "9 4"),
        ("9 4\n", "9 4"),
        ("9 4\r\n", "9 4"),
        ("0\r\n1\r\n2", "0\n1\n2"),
        ("0\r1\r2", "0\n1\n2"),
        ("9 4   ", "9 4"),
        ("\n\n9 4\n\n\n", "9 4"),
        ("  indented", "  indented"),  # leading indentation is significant
        ("a\n\nb", "a\n\nb"),  # an internal blank line is significant
        (None, ""),
        ("", ""),
    ],
)
def test_normalise_output(raw, expected):
    assert normalise_output(raw) == expected


def test_correct_answer_accepted(library):
    problem = library.problem("PO_VAR_01")  # correct_output == "9 4"
    assert check_predict_output(problem, "9 4") is True


def test_trailing_newline_and_crlf_still_correct(library):
    problem = library.problem("PO_VAR_01")
    assert check_predict_output(problem, "9 4\r\n") is True
    assert check_predict_output(problem, "9 4  \n\n") is True


def test_leading_whitespace_is_significant(library):
    """Indentation can be part of real program output, so it is not stripped."""
    problem = library.problem("PO_VAR_01")
    assert check_predict_output(problem, "  9 4") is False


def test_wrong_answer_rejected(library):
    problem = library.problem("PO_VAR_01")
    assert check_predict_output(problem, "9 9") is False


def test_missing_internal_whitespace_is_not_correct(library):
    """"94" is a different answer from "9 4" - spacing inside a line matters."""
    problem = library.problem("PO_VAR_01")
    assert check_predict_output(problem, "94") is False


def test_every_predict_output_problem_accepts_its_own_correct_output(library):
    """Guards the dataset: no problem may be unanswerable."""
    for problem in library.problems.values():
        if problem.item_type == "predict_output":
            assert check_predict_output(problem, problem.correct_output), problem.problem_id
