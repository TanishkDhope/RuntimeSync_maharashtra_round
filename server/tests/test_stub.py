"""The stub diagnoser."""

from __future__ import annotations

import random

from app.data import load_library
from app.diagnosis import build_diagnoser
from app.diagnosis.stub import MATCH_SCORE, SLIP_SCORE, StubDiagnoser
from app.flow import choose_problems


def test_build_diagnoser_returns_the_stub_by_default(settings, library):
    diagnoser = build_diagnoser(settings, library)
    assert diagnoser.name == "stub"


def test_matching_predicted_output_scores_high(library):
    stub = StubDiagnoser(library)
    problem = library.problem("PO_VAR_03")  # ASSIGN_COMPARES -> "7\n2"
    ranked = stub.rank(problem, "7\n2", "the = checked whether they were equal")
    assert ranked[0].misconception_id == "ASSIGN_COMPARES"
    assert ranked[0].score == MATCH_SCORE
    assert ranked[1].score < MATCH_SCORE


def test_a_held_out_belief_is_not_named_even_when_its_output_matches(library):
    """PO_VAR_02 is a test-split problem whose "5 10 5" belongs to a held-out
    belief (VAR_KEEPS_FIRST_VALUE). The ranked library is train-split only
    (brief s5), so the honest answer is a low-confidence guess, not a
    confident name for a belief the model was never trained on.
    """
    stub = StubDiagnoser(library)
    problem = library.problem("PO_VAR_02")
    ranked = stub.rank(problem, "5 10 5", "x never changed")

    assert "VAR_KEEPS_FIRST_VALUE" not in {c.misconception_id for c in ranked}
    assert ranked[0].score < MATCH_SCORE, "an unseen belief must not score as a match"


def test_confusable_pair_is_returned_as_a_tie(library):
    """PO_VAR_01 has two beliefs that both predict "9 9".

    The stub cannot separate them, and inventing a winner would be a lie on
    screen. Resolving this needs the probe path or the trained model.
    """
    stub = StubDiagnoser(library)
    problem = library.problem("PO_VAR_01")
    ranked = stub.rank(problem, "9 9", "b points at a")
    top = [c for c in ranked if c.score == MATCH_SCORE]
    assert len(top) == 2
    assert {c.misconception_id for c in top} == {
        "ASSIGN_LINKS_VARIABLES",
        "VAR_HOLDS_EXPRESSION",
    }


def test_unexplained_answer_surfaces_slip(library):
    stub = StubDiagnoser(library)
    problem = library.problem("PO_VAR_01")
    ranked = stub.rank(problem, "42", "typed it wrong")
    assert ranked[0].misconception_id == "SLIP"
    assert ranked[0].score == SLIP_SCORE


def test_slip_is_absent_when_a_belief_explains_the_answer(library):
    stub = StubDiagnoser(library)
    problem = library.problem("PO_VAR_01")
    ranked = stub.rank(problem, "9 9", "linked")
    assert "SLIP" not in {c.misconception_id for c in ranked}


def test_whitespace_differences_still_match(library):
    stub = StubDiagnoser(library)
    problem = library.problem("PO_VAR_01")
    ranked = stub.rank(problem, "9 9  \r\n", "linked")
    assert ranked[0].score == MATCH_SCORE


def test_write_code_returns_flat_scores(library):
    """With no output to match, the stub has nothing to rank on."""
    stub = StubDiagnoser(library)
    problem = library.problem("WC_01")
    ranked = stub.rank(problem, "def sum_to(n):\n    return 0", "guessed")
    assert len(ranked) == len(problem.applicable_misconceptions)
    assert len({c.score for c in ranked}) == 1


def test_results_are_sorted_high_to_low(library):
    stub = StubDiagnoser(library)
    for problem in library.problems.values():
        ranked = stub.rank(problem, "some wrong answer", "a reason")
        scores = [c.score for c in ranked]
        assert scores == sorted(scores, reverse=True), problem.problem_id


# --- dataset-level guards ---------------------------------------------------

def test_ranked_library_is_the_train_split_only(library):
    ranked = library.ranked_misconceptions()
    assert ranked, "the ranked library is empty"
    assert all(m.split == "train" for m in ranked)
    assert len(ranked) < len(library.misconceptions), "held_out split is missing"


def test_loader_rejects_a_problem_with_an_unknown_misconception(tmp_path):
    (tmp_path / "misconceptions.jsonl").write_text(
        '{"misconception_id": "SLIP", "description": "a slip", "topic": null,'
        ' "confusable_group": null, "split": "train"}\n',
        encoding="utf-8",
    )
    (tmp_path / "problems.jsonl").write_text(
        '{"problem_id": "P1", "item_type": "predict_output", "topic": "loops",'
        ' "problem_text": "print(1)", "correct_output": "1",'
        ' "applicable_misconceptions": ["NOT_A_REAL_ID"], "split": "train"}\n',
        encoding="utf-8",
    )
    try:
        load_library(tmp_path)
    except ValueError as exc:
        assert "NOT_A_REAL_ID" in str(exc)
    else:
        raise AssertionError("the loader accepted an unknown misconception id")


# --- problem selection ------------------------------------------------------

def test_choose_problems_respects_the_topic(library):
    chosen = choose_problems(library, "loops", 5, set(), random.Random(0))
    assert len(chosen) == 5
    assert all(library.problem(pid).topic == "loops" for pid in chosen)
    assert len(set(chosen)) == 5, "a problem was served twice"


def test_choose_problems_prefers_unseen(library):
    """Unseen is preferred within each question type.

    Leave plenty unseen of both types, so a seen problem appearing would mean
    the preference is not being applied rather than that it ran out of options.
    """
    loops = library.problems_for_topic("loops")
    predict = [p.problem_id for p in loops if p.item_type == "predict_output"]
    write = [p.problem_id for p in loops if p.item_type == "write_code"]
    seen = set(predict[:10]) | {write[0]}

    chosen = choose_problems(library, "loops", 5, seen, random.Random(0))
    assert len(chosen) == 5
    assert not (set(chosen) & seen), "a seen problem was served while fresh ones remained"


def test_choose_problems_reuses_seen_problems_only_as_a_last_resort(library):
    """Running out of fresh problems must not shorten the run."""
    loops = library.problems_for_topic("loops")
    predict = [p.problem_id for p in loops if p.item_type == "predict_output"]
    seen = set(predict[:-1])  # one fresh predict_output problem left

    chosen = choose_problems(library, "loops", 5, seen, random.Random(0))
    assert len(chosen) == 5
    assert predict[-1] in chosen, "the one fresh problem should still be used"


def test_choose_problems_falls_back_to_seen_when_it_must(library):
    """Everything seen: still return a full quiz rather than an empty one."""
    everything = {p.problem_id for p in library.problems.values()}
    chosen = choose_problems(library, "variables", 5, everything, random.Random(0))
    assert len(chosen) == 5


def test_mixed_topic_spans_topics(library):
    chosen = choose_problems(library, "mixed", 20, set(), random.Random(1))
    topics = {library.problem(pid).topic for pid in chosen}
    assert len(topics) > 1


def test_a_run_includes_a_write_code_item_when_the_topic_has_one(library):
    """Both question types must show up: the last slot is reserved."""
    for topic in ("conditionals", "loops", "lists", "strings", "mixed"):
        chosen = choose_problems(library, topic, 5, set(), random.Random(7))
        types = [library.problem(pid).item_type for pid in chosen]
        assert types.count("write_code") == 1, f"{topic}: {types}"
        assert types[-1] == "write_code", f"{topic} should end on the code question"


def test_topics_without_write_code_problems_are_all_predict_output(library):
    """variables and functions have no write_code items in the dataset."""
    for topic in ("variables", "functions"):
        chosen = choose_problems(library, topic, 5, set(), random.Random(7))
        types = {library.problem(pid).item_type for pid in chosen}
        assert types == {"predict_output"}, f"{topic}: {types}"


def test_a_one_question_run_is_not_only_a_code_question(library):
    chosen = choose_problems(library, "lists", 1, set(), random.Random(7))
    assert len(chosen) == 1
    assert library.problem(chosen[0]).item_type == "predict_output"


def test_the_stub_never_ranks_a_held_out_misconception(library):
    """Only split=train beliefs are rankable (brief s5), on every problem.

    Test-split problems can list held-out misconceptions, and a session draws
    those once the train and validation pools run out.
    """
    diagnoser = StubDiagnoser(library=library)
    held_out = {
        m.misconception_id
        for m in library.misconceptions.values()
        if m.split != "train"
    }
    assert held_out, "the dataset should have held-out misconceptions to guard against"

    checked = 0
    for problem in library.problems.values():
        if not held_out.intersection(problem.applicable_misconceptions):
            continue
        checked += 1
        ranked = diagnoser.rank(problem, "definitely wrong", "a guess")
        assert not held_out.intersection(c.misconception_id for c in ranked), (
            problem.problem_id
        )
    assert checked, "no problem in the dataset lists a held-out misconception"
