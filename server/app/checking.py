"""Answer checking for predict_output. No model involved (brief s6 step 2)."""

from __future__ import annotations

from .data import Problem


def normalise_output(text: str | None) -> str:
    """Normalise program output for comparison.

    Line endings are unified, trailing whitespace is dropped from each line,
    and leading/trailing blank lines are removed. Internal blank lines and
    leading indentation are significant and kept.
    """
    if text is None:
        return ""
    unified = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in unified.split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def check_predict_output(problem: Problem, student_response: str) -> bool:
    return normalise_output(student_response) == normalise_output(problem.correct_output)
