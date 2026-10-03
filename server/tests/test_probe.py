from app.data import Problem
from app.probes import find_bank_probe, match_probe_answer, needs_probe


def test_probe_gap_decision():
    assert needs_probe([0.90, 0.85], 0.1)
    assert not needs_probe([0.90, 0.79], 0.1)


def test_bank_probe_distinguishes_candidates_and_is_executed(library):
    draft = find_bank_probe(library, "loops", ["RANGE_FROM_1", "RANGE_INCLUDES_END"], set())
    assert draft and draft.source == "bank"
    assert draft.actual_output
    assert len(set(draft.predictions.values())) == 2


def test_bank_probe_rejects_identical_predictions(library):
    # These two beliefs share their output on PO_LOOP_01; it cannot be served
    # as a probe even though both are applicable there.
    problem = library.problem("PO_LOOP_01")
    assert problem.predicted_outputs["RANGE_FROM_1"] == problem.predicted_outputs["RANGE_INCLUDES_END"]


def test_probe_answer_matching():
    predictions = {"A": "0\n1", "B": "1\n2"}
    assert match_probe_answer(predictions, "0\n1\n") == ("confirmed", "A")
    assert match_probe_answer(predictions, "other") == ("uncertain", None)
    assert match_probe_answer({"A": "1", "B": "1"}, "1") == ("ambiguous", None)
