"""Answer checking for predict_output. No model involved (brief s6 step 2)."""

from __future__ import annotations

from .data import Problem


def normalise_output(text: str | None) -> str:
    """Normalise program output for comparison.

    Line endings are unified and trailing whitespace is dropped from each
    line, then trailing blank lines are removed.

    Leading blank lines are kept. A program that starts with a bare print()
    really does output a blank first line, and dropping it here would accept
    an answer that left it out. The dataset was built with trailing-only
    stripping, so this matches how correct_output was recorded. Internal
    blank lines and leading indentation are significant too.
    """
    if text is None:
        return ""
    unified = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in unified.split("\n")]
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def check_predict_output(problem: Problem, student_response: str) -> bool:
    return normalise_output(student_response) == normalise_output(problem.correct_output)
