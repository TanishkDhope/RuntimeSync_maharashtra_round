"""No-ML diagnoser (brief s5).

For predict_output it matches the student's output against the problem's
predicted_outputs map. For write_code it has nothing to go on, so it returns
the applicable misconceptions at a flat low score.

Scores are deliberately coarse (0.9 / 0.3 / 0.2 / 0.15) so nobody mistakes
them for the trained model's confidence. Ties are left as ties: when two
misconceptions predict the same wrong output the stub cannot separate them,
and inventing a winner would be a lie on screen.
"""

from __future__ import annotations

from ..checking import normalise_output
from ..data import SLIP_ID, Library, Problem
from .base import Candidate

MATCH_SCORE = 0.9
SLIP_SCORE = 0.3
WRITE_CODE_SCORE = 0.2
UNMATCHED_SCORE = 0.15


class StubDiagnoser:
    name = "stub"

    def __init__(self, library: Library) -> None:
        self._library = library

    def rank(
        self,
        problem: Problem,
        student_response: str,
        student_explanation: str,
    ) -> list[Candidate]:
        if problem.item_type == "write_code":
            scored = {m: WRITE_CODE_SCORE for m in problem.applicable_misconceptions}
        else:
            scored = self._rank_predict_output(problem, student_response)

        candidates = [Candidate(misconception_id=m, score=s) for m, s in scored.items()]
        # Stable: equal scores keep the order they appear in the problem.
        candidates.sort(key=lambda c: -c.score)
        return candidates

    def _rank_predict_output(self, problem: Problem, student_response: str) -> dict[str, float]:
        answer = normalise_output(student_response)
        scored: dict[str, float] = {}
        matched = False
        for misconception_id in problem.applicable_misconceptions:
            predicted = problem.predicted_outputs.get(misconception_id)
            if predicted is not None and normalise_output(predicted) == answer:
                scored[misconception_id] = MATCH_SCORE
                matched = True
            else:
                scored[misconception_id] = UNMATCHED_SCORE

        if not matched and SLIP_ID in self._library.misconceptions:
            # No known belief produces this answer, so a careless slip is as
            # good a guess as the stub can make.
            scored[SLIP_ID] = SLIP_SCORE
        return scored
