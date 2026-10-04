"""Does the learner model's verdict predict anything?

The diagnoser has an evaluation. The learner model - the thing that decides
active / improving / resolved across attempts - has never had one, so
"resolved" has been a label the system assigns to itself and then reports as
a result. This measures it.

Two modes, because they answer different questions:

  replay    Walk a real database's attempts in order. Before each one, work
            out the status the model held for the beliefs that problem tests,
            then look at what the learner actually did. A model with signal
            gets a higher correct-rate behind "resolved" than behind "active".
            No ground truth here - only whether the verdict predicts.

  simulate  Synthetic learners whose beliefs we *know*, because we chose them.
            problems.jsonl carries predicted_outputs keyed by misconception,
            so a learner holding ASSIGN_LINKS_VARIABLES can be made to answer
            exactly the way that belief makes people answer. When the belief
            is removed, we know the instant it happened, so "did the model
            notice, and how late" becomes measurable.

The simulation drives the real app.flow.update_learner_model, so what it
scores is the shipped rulebook rather than a restatement of it. The diagnoser
is stubbed at a configurable accuracy on purpose: the learner model is being
measured *given* a diagnoser, and mixing the two failure sources is how you
end up unable to fix either.

Run from the server directory:

    .venv/Scripts/python.exe scripts/eval_learner_model.py simulate
    .venv/Scripts/python.exe scripts/eval_learner_model.py replay --db relearn.db
"""

from __future__ import annotations

import argparse
import random
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVER_DIR))

from sqlmodel import Session, SQLModel, create_engine, select  # noqa: E402

from app import learner_model  # noqa: E402
from app.data import Library, Problem, load_library  # noqa: E402
from app.diagnosis.base import Candidate  # noqa: E402
from app.flow import update_learner_model  # noqa: E402
from app.models import Attempt, Learner, LearnerMisconception  # noqa: E402
from app.stages import RETEST_COUNT, pick_retest_from_bank  # noqa: E402

UNKNOWN_THRESHOLD = 0.5
SLIP_ID = "SLIP"


# --- the rules as they were, kept so the comparison stays reproducible ------
#
# The evidence table replaced these. They are copied here rather than left in
# the app so that `--rules legacy` still runs after the originals are gone:
# a before/after you cannot re-run is a claim, not a measurement.

def legacy_update(db, learner_id, problem, is_correct, ranked, unknown_threshold):
    """flow.update_learner_model as it stood before the evidence table."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    if not is_correct:
        scores = [c.score for c in ranked]
        top = ranked[0] if (scores and scores[0] >= unknown_threshold) else None
        if top and top.misconception_id != SLIP_ID:
            record = _cached(db, learner_id, top.misconception_id)
            if record is None:
                db.add(LearnerMisconception(
                    learner_id=learner_id, misconception_id=top.misconception_id,
                    status="active", times_seen=1, consecutive_correct=0,
                    first_seen=now, last_seen=now,
                ))
            else:
                record.times_seen += 1
                record.consecutive_correct = 0
                record.last_seen = now
                if record.status == "resolved" or record.returned:
                    record.returned = True
                record.status = "active"
                record.resolved_at = None
                db.add(record)
            db.commit()
    else:
        # The bug: two correct answers on problems that happen to test this
        # exact belief, drawn at random from the whole bank.
        for m_id in problem.applicable_misconceptions:
            record = _cached(db, learner_id, m_id)
            if record is not None and record.status in ("active", "improving"):
                record.consecutive_correct += 1
                if record.consecutive_correct >= 2:
                    record.status = "resolved"
                    record.resolved_at = now
                else:
                    record.status = "improving"
                db.add(record)
        db.commit()


def legacy_verdict(db, learner_id, confirmed_id, correct, total, still_in_reasoning):
    """The status write that used to live in stages.build_result_step."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    if total == 0:
        verdict = "improving"
    elif correct == total and not still_in_reasoning:
        verdict = "resolved"
    elif correct > 0 or not still_in_reasoning:
        verdict = "improving"
    else:
        verdict = "active"

    record = _cached(db, learner_id, confirmed_id)
    if record is None:
        db.add(LearnerMisconception(
            learner_id=learner_id, misconception_id=confirmed_id, status=verdict,
            times_seen=1, consecutive_correct=correct, first_seen=now, last_seen=now,
        ))
    else:
        record.last_seen = now
        if verdict == "resolved":
            record.status, record.resolved_at = "resolved", now
            record.consecutive_correct = correct
        elif verdict == "improving":
            record.status = "improving"
            record.consecutive_correct = correct
        else:
            if record.status == "resolved":
                record.returned = True
            record.status = "active"
            record.consecutive_correct = 0
        db.add(record)
    db.commit()


def _cached(db, learner_id, misconception_id):
    return db.exec(
        select(LearnerMisconception).where(
            LearnerMisconception.learner_id == learner_id,
            LearnerMisconception.misconception_id == misconception_id,
        )
    ).first()


# --- what we are scoring ----------------------------------------------------

@dataclass
class Observation:
    """One attempt, with what the model believed just before it landed.

    `status` is the model's standing on the belief this problem tests at the
    moment the question was asked - before the answer could influence it.
    `holds` is the truth, and is None in replay mode where there isn't one.
    """

    misconception_id: str
    status: str
    is_correct: bool
    holds: bool | None = None
    phase: str = "initial"


@dataclass
class Scoreboard:
    observations: list[Observation] = field(default_factory=list)
    # Beliefs the simulation genuinely removed, and how many attempts passed
    # before the model said "resolved". None means it never did.
    detection_lag: list[int | None] = field(default_factory=list)

    def add(self, **kwargs) -> None:
        self.observations.append(Observation(**kwargs))


# --- the simulated learner --------------------------------------------------

@dataclass
class SyntheticLearner:
    """Someone whose head we can see into.

    `beliefs` is what they actually hold right now. It shrinks when a belief is
    learned away, which is the event the learner model is supposed to detect.
    """

    name: str
    beliefs: set[str]
    slip_rate: float
    # Chance of answering correctly while still holding the belief: a lucky
    # guess, or a problem where the wrong rule happens to give the right
    # output. This is the case "two correct answers = resolved" cannot see.
    guess_rate: float = 0.0
    # misconception_id -> attempts seen since it was truly removed
    removed_at_attempt: dict[str, int] = field(default_factory=dict)
    # misconception_id -> how many times it has been diagnosed and taught against
    interventions: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def answer(self, problem: Problem, rng: random.Random) -> tuple[bool, str | None]:
        """How this learner answers, and which belief drove it.

        A belief only shows when the problem actually tests it. Everything else
        is answered correctly, apart from the slip rate - people mistype.
        """
        active = [m for m in problem.applicable_misconceptions if m in self.beliefs]
        if active:
            if rng.random() < self.guess_rate:
                return True, None  # right answer, belief intact
            # Whichever belief fires first is the one that produces the answer.
            return False, active[0]
        if rng.random() < self.slip_rate:
            return False, None  # a slip: wrong, but no belief behind it
        return True, None


def fake_diagnosis(
    library: Library,
    problem: Problem,
    cause: str | None,
    accuracy: float,
    rng: random.Random,
) -> list[Candidate]:
    """A diagnoser of known quality, so the learner model can be scored alone.

    With probability `accuracy` it names the belief that actually produced the
    answer. Otherwise it names a confusable sibling - the dataset groups those
    in confusable_group, which is exactly the mistake a real ranker makes - or
    falls back to SLIP when there is nothing to confuse it with.
    """
    if cause is None:
        # A slip. A good diagnoser recognises there is no belief here.
        return [Candidate(SLIP_ID, 0.7)] if rng.random() < accuracy else _noise(problem, rng)

    if rng.random() < accuracy:
        return [Candidate(cause, 0.85), Candidate(SLIP_ID, 0.3)]

    group = library.misconception(cause).confusable_group
    siblings = [
        m.misconception_id
        for m in library.misconceptions.values()
        if m.confusable_group and m.confusable_group == group and m.misconception_id != cause
    ]
    wrong = rng.choice(siblings) if siblings else SLIP_ID
    return [Candidate(wrong, 0.7), Candidate(cause, 0.6)]


def _noise(problem: Problem, rng: random.Random) -> list[Candidate]:
    pool = list(problem.applicable_misconceptions) or [SLIP_ID]
    return [Candidate(rng.choice(pool), 0.6)]


# --- simulate ---------------------------------------------------------------

def simulate(
    library: Library,
    learners: int,
    sessions: int,
    session_length: int,
    diagnoser_accuracy: float,
    learn_rate: float,
    slip_rate: float,
    guess_rate: float,
    seed: int,
    rules: str,
) -> Scoreboard:
    """Run synthetic learners through the whole loop the app runs.

    Ask -> diagnose -> teach -> retest -> verdict, the same shape as
    flow/stages, so the retest evidence that the real system gathers is
    gathered here too. Every time a belief is diagnosed the system teaches
    against it, and with probability `learn_rate` it is genuinely removed -
    that is the moment the model is supposed to catch.
    """
    rng = random.Random(seed)
    board = Scoreboard()

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)

    teachable = [
        m.misconception_id
        for m in library.misconceptions.values()
        if m.misconception_id != SLIP_ID
        and any(m.misconception_id in p.applicable_misconceptions for p in library.problems.values())
    ]
    problems = list(library.problems.values())

    with Session(engine) as db:
        for index in range(learners):
            person = SyntheticLearner(
                name=f"sim-{index:03d}",
                beliefs=set(rng.sample(teachable, rng.choice([2, 3]))),
                slip_rate=slip_rate,
                guess_rate=guess_rate,
            )
            row = Learner(name=person.name)
            db.add(row)
            db.commit()
            db.refresh(row)

            truly_removed: dict[str, int] = {}
            attempt_no = 0

            def note(problem, is_correct, phase="initial"):
                """Record what the model believed before this question landed."""
                tested = [m for m in problem.applicable_misconceptions if m != SLIP_ID]
                before = _standings(db, row.id, tested)
                for m_id in tested:
                    board.add(
                        misconception_id=m_id,
                        status=before.get(m_id, "unseen"),
                        is_correct=is_correct,
                        holds=m_id in person.beliefs,
                        phase=phase,
                    )

            def apply(problem, is_correct, ranked, phase="initial", targeted_id=None):
                if rules == "legacy":
                    if phase == "initial":
                        legacy_update(db, row.id, problem, is_correct, ranked, UNKNOWN_THRESHOLD)
                    # Legacy never fed retest answers to the learner model.
                    return
                update_learner_model(
                    db,
                    learner_id=row.id,
                    problem=problem,
                    is_correct=is_correct,
                    ranked=ranked,
                    unknown_threshold=UNKNOWN_THRESHOLD,
                    phase=phase,
                    targeted_id=targeted_id,
                )

            def check_detection():
                """Has the model noticed a belief that is genuinely gone?"""
                for m_id, removed_at in list(truly_removed.items()):
                    if _standings(db, row.id, [m_id]).get(m_id) == "resolved":
                        board.detection_lag.append(attempt_no - removed_at)
                        del truly_removed[m_id]

            for _ in range(sessions):
                queue = rng.sample(problems, session_length)
                for problem in queue:
                    attempt_no += 1
                    is_correct, cause = person.answer(problem, rng)
                    note(problem, is_correct)
                    ranked = fake_diagnosis(library, problem, cause, diagnoser_accuracy, rng)
                    apply(problem, is_correct, ranked)
                    check_detection()

                    confirmed = ranked[0].misconception_id if ranked else None
                    if is_correct or not confirmed or confirmed == SLIP_ID:
                        continue
                    if ranked[0].score < UNKNOWN_THRESHOLD:
                        continue

                    # The explain step: the system teaches against the belief
                    # it diagnosed, and sometimes that actually works.
                    person.interventions[confirmed] += 1
                    if confirmed in person.beliefs and rng.random() < learn_rate:
                        person.beliefs.discard(confirmed)
                        truly_removed[confirmed] = attempt_no

                    # The retest: problems chosen because they test this belief.
                    rt_ids = pick_retest_from_bank(
                        library, confirmed, {p.problem_id for p in queue}, RETEST_COUNT
                    )
                    rt_correct = 0
                    still_in_reasoning = False
                    for rt_id in rt_ids:
                        rt_problem = library.problem(rt_id)
                        attempt_no += 1
                        rt_is_correct, rt_cause = person.answer(rt_problem, rng)
                        note(rt_problem, rt_is_correct, phase="reassess")
                        apply(
                            rt_problem,
                            rt_is_correct,
                            [Candidate(confirmed, 0.8)],
                            phase="reassess",
                            targeted_id=confirmed,
                        )
                        rt_correct += int(rt_is_correct)
                        if not rt_is_correct and rt_cause == confirmed:
                            still_in_reasoning = True

                    if rules == "legacy":
                        legacy_verdict(
                            db, row.id, confirmed, rt_correct, len(rt_ids), still_in_reasoning
                        )
                    else:
                        learner_model.recompute(db, row.id, confirmed)
                    check_detection()

            board.detection_lag.extend(None for _ in truly_removed)

    return board


def _standings(db: Session, learner_id: int, ids: list[str]) -> dict[str, str]:
    if not ids:
        return {}
    rows = db.exec(
        select(LearnerMisconception).where(
            LearnerMisconception.learner_id == learner_id,
            LearnerMisconception.misconception_id.in_(ids),
        )
    ).all()
    return {r.misconception_id: r.status for r in rows}


# --- replay -----------------------------------------------------------------

def replay(library: Library, db_path: Path) -> Scoreboard:
    """Score the model against a real database.

    No ground truth exists here, so this answers the weaker question: did the
    verdict predict the next answer? It is the number you can quote about real
    users, which is why it is worth having alongside the simulation.
    """
    board = Scoreboard()
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})

    with Session(engine) as db:
        attempts = list(db.exec(select(Attempt).order_by(Attempt.created_at.asc(), Attempt.id.asc())).all())
        if not attempts:
            return board

        # Replaying means rebuilding the standing as it was, so a fresh model
        # is driven through the same attempts in the same order.
        scratch = create_engine("sqlite://", connect_args={"check_same_thread": False})
        SQLModel.metadata.create_all(scratch)

        with Session(scratch) as mirror:
            seen: set[int] = set()
            for attempt in attempts:
                try:
                    problem = library.problem(attempt.problem_id)
                except KeyError:
                    continue  # a problem that left the dataset; nothing to say about it
                if attempt.learner_id not in seen:
                    mirror.add(Learner(id=attempt.learner_id, name=f"replay-{attempt.learner_id}"))
                    mirror.commit()
                    seen.add(attempt.learner_id)

                tested = [m for m in problem.applicable_misconceptions if m != SLIP_ID]
                before = _standings(mirror, attempt.learner_id, tested)
                for m_id in tested:
                    board.add(
                        misconception_id=m_id,
                        status=before.get(m_id, "unseen"),
                        is_correct=attempt.is_correct,
                    )

                ranked = [
                    Candidate(d["misconception_id"], float(d["score"]))
                    for d in (attempt.diagnosis or [])
                ]
                update_learner_model(
                    mirror,
                    learner_id=attempt.learner_id,
                    problem=problem,
                    is_correct=attempt.is_correct,
                    ranked=ranked,
                    unknown_threshold=UNKNOWN_THRESHOLD,
                    phase=attempt.phase,
                )

    return board


# --- reporting --------------------------------------------------------------

ORDER = ("unseen", "active", "improving", "resolved")


def report(board: Scoreboard, mode: str) -> None:
    if not board.observations:
        print("No observations. The database has no attempts on problems that")
        print("are still in the dataset, so there is nothing to score.")
        return

    buckets: dict[str, list[Observation]] = defaultdict(list)
    for ob in board.observations:
        buckets[ob.status].append(ob)

    print()
    print("Does the standing predict the answer?")
    print("  (status held before the question was asked, vs what happened)")
    print()
    print(f"  {'status':<12}{'n':>8}{'correct':>10}{'rate':>9}")
    print(f"  {'-' * 37}")
    rates: dict[str, float] = {}
    for status in ORDER:
        rows = buckets.get(status, [])
        if not rows:
            continue
        correct = sum(1 for r in rows if r.is_correct)
        rate = correct / len(rows) * 100
        rates[status] = rate
        print(f"  {status:<12}{len(rows):>8}{correct:>10}{rate:>8.1f}%")

    if "resolved" in rates and "active" in rates:
        gap = rates["resolved"] - rates["active"]
        print(f"  {'-' * 37}")
        print(f"  separation (resolved - active): {gap:+.1f} pts")
        if gap < 10:
            print("  -> near zero. The verdict is not carrying information.")

    if mode != "simulate":
        print()
        return

    truth = [ob for ob in board.observations if ob.holds is not None]
    wrong_resolved = [ob for ob in truth if ob.status == "resolved" and ob.holds]
    resolved = [ob for ob in truth if ob.status == "resolved"]
    still_active = [ob for ob in truth if ob.status == "active" and not ob.holds]
    active = [ob for ob in truth if ob.status == "active"]

    print()
    print("Against the truth (simulation only)")
    print()
    if resolved:
        pct = len(wrong_resolved) / len(resolved) * 100
        print(f"  said resolved while the belief was still held   {len(wrong_resolved):>5} / {len(resolved):<6} {pct:>5.1f}%")
    if active:
        pct = len(still_active) / len(active) * 100
        print(f"  said active after the belief was really gone    {len(still_active):>5} / {len(active):<6} {pct:>5.1f}%")

    lags = [lag for lag in board.detection_lag if lag is not None]
    missed = sum(1 for lag in board.detection_lag if lag is None)
    if board.detection_lag:
        total = len(board.detection_lag)
        print()
        print(f"  beliefs genuinely removed                       {total:>5}")
        if lags:
            lags.sort()
            print(f"  ...noticed, median attempts later               {lags[len(lags) // 2]:>5}")
        print(f"  ...never noticed                                {missed:>5}  ({missed / total * 100:.1f}%)")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)

    sim = sub.add_parser("simulate", help="synthetic learners with known beliefs")
    sim.add_argument("--learners", type=int, default=120)
    sim.add_argument("--sessions", type=int, default=4)
    sim.add_argument("--session-length", type=int, default=5)
    sim.add_argument("--diagnoser-accuracy", type=float, default=0.8)
    sim.add_argument("--learn-rate", type=float, default=0.45,
                     help="chance an intervention actually removes the belief")
    sim.add_argument("--slip-rate", type=float, default=0.07)
    sim.add_argument("--guess-rate", type=float, default=0.15,
                     help="chance of a correct answer while the belief is still held")
    sim.add_argument("--seed", type=int, default=7)
    sim.add_argument("--rules", choices=("evidence", "legacy"), default="evidence",
                     help="evidence = the shipped learner model; legacy = the in-place "
                          "status writes it replaced, kept so the comparison re-runs")

    rep = sub.add_parser("replay", help="score against a real database")
    rep.add_argument("--db", type=Path, default=SERVER_DIR / "relearn.db")

    args = parser.parse_args()
    library = load_library(SERVER_DIR.parent / "data")

    if args.mode == "simulate":
        board = simulate(
            library,
            learners=args.learners,
            sessions=args.sessions,
            session_length=args.session_length,
            diagnoser_accuracy=args.diagnoser_accuracy,
            learn_rate=args.learn_rate,
            slip_rate=args.slip_rate,
            guess_rate=args.guess_rate,
            seed=args.seed,
            rules=args.rules,
        )
        print(f"\n{args.learners} learners x {args.sessions} sessions x {args.session_length} "
              f"questions, diagnoser accuracy {args.diagnoser_accuracy:.0%}")
        print(f"rules: {args.rules}, guess rate {args.guess_rate:.0%}")
    else:
        if not args.db.exists():
            sys.exit(f"no database at {args.db}")
        board = replay(library, args.db)
        print(f"\nreplaying {args.db}")

    report(board, args.mode)


if __name__ == "__main__":
    main()
