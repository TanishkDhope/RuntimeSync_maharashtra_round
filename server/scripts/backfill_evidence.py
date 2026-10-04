"""Rebuild misconception_evidence from the attempts already on record.

The learner model used to keep only a status per belief, with nothing behind
it. Now the status is derived from evidence, so a database made before the
change has learner_misconceptions rows and no evidence to justify them - every
belief would read "active" with a times_seen of zero.

Every fact needed is already in `attempts`: the problem, the phase, whether it
was right, and what the diagnoser said. Replaying them in order reconstructs
the evidence, and recompute then rewrites the cached standings from it.

Idempotent: it clears the evidence table first, so running it twice gives the
same answer as running it once. Dry by default.

    .venv/Scripts/python.exe scripts/backfill_evidence.py --db relearn.db
    .venv/Scripts/python.exe scripts/backfill_evidence.py --db relearn.db --write
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVER_DIR))

from sqlalchemy import delete  # noqa: E402
from sqlmodel import Session, SQLModel, create_engine, select  # noqa: E402

from app import learner_model  # noqa: E402
from app.data import SLIP_ID, load_library  # noqa: E402
from app.models import Attempt, LearnerMisconception, MisconceptionEvidence  # noqa: E402


def targeted_belief(attempt: Attempt) -> str | None:
    """Which belief a retest was aimed at, as recorded at the time.

    stages.submit_retest_answer writes the confirmed misconception into the
    attempt's diagnosis, so a reassess row carries its own target even when
    the answer was correct and there was nothing to diagnose.
    """
    if attempt.phase != "reassess":
        return None
    for entry in attempt.diagnosis or []:
        m_id = entry.get("misconception_id")
        if m_id and m_id != SLIP_ID:
            return m_id
    return None


def diagnosed_belief(attempt: Attempt, unknown_threshold: float) -> str | None:
    """The belief a wrong answer was blamed on, if the diagnoser was sure enough."""
    ranked = attempt.diagnosis or []
    if not ranked:
        return None
    top = ranked[0]
    if float(top.get("score") or 0.0) < unknown_threshold:
        return None
    m_id = top.get("misconception_id")
    return None if m_id == SLIP_ID else m_id


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=SERVER_DIR / "relearn.db")
    parser.add_argument("--unknown-threshold", type=float, default=0.5)
    parser.add_argument("--write", action="store_true", help="actually commit; otherwise report only")
    args = parser.parse_args()

    if not args.db.exists():
        sys.exit(f"no database at {args.db}")

    library = load_library(SERVER_DIR.parent / "data")
    engine = create_engine(f"sqlite:///{args.db}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)

    tally: Counter[str] = Counter()

    with Session(engine) as db:
        attempts = list(
            db.exec(select(Attempt).order_by(Attempt.created_at.asc(), Attempt.id.asc())).all()
        )
        print(f"{len(attempts)} attempts on record")

        db.exec(delete(MisconceptionEvidence))
        db.commit()

        for attempt in attempts:
            try:
                problem = library.problem(attempt.problem_id)
            except KeyError:
                # The problem has left the dataset; there is nothing to say
                # about which beliefs it tested.
                tally["skipped: problem gone"] += 1
                continue

            if attempt.phase == "probe":
                # A probe disambiguates *which* belief is at work, not whether
                # it has gone. Treating it as evidence either way would be
                # reading something into it that it was not asked.
                tally["skipped: probe"] += 1
                continue

            target = targeted_belief(attempt)
            touched = learner_model.observe_answer(
                db,
                learner_id=attempt.learner_id,
                problem=problem,
                is_correct=attempt.is_correct,
                diagnosed_id=target if attempt.is_correct else diagnosed_belief(attempt, args.unknown_threshold),
                phase=attempt.phase,
                attempt_id=attempt.id,
                session_id=attempt.session_id,
                at=attempt.created_at,
            )
            tally["evidence rows" if touched else "no evidence"] += len(touched) or 1

        # Standings left over from before, with nothing behind them. The live
        # database has one: a belief marked resolved for a learner with no
        # attempts at all. Under the old rules a status could be written
        # without any record of why; those are exactly the rows to drop.
        db.flush()
        ghosts = [
            standing
            for standing in db.exec(select(LearnerMisconception)).all()
            if not learner_model.evidence_for(db, standing.learner_id, standing.misconception_id)
        ]
        for standing in ghosts:
            db.delete(standing)
        db.flush()

        rows = db.exec(select(MisconceptionEvidence)).all()
        standings = db.exec(select(LearnerMisconception)).all()

        print()
        for key, count in sorted(tally.items()):
            print(f"  {key:<24} {count}")
        print()
        print(f"  {'evidence rows built':<24} {len(rows)}")
        print(f"  {'ghost standings dropped':<24} {len(ghosts)}")
        by_status = Counter(s.status for s in standings)
        print(f"  {'standings':<24} {len(standings)}  {dict(by_status)}")

        if args.write:
            db.commit()
            print("\nwritten.")
        else:
            db.rollback()
            print("\nnothing written - pass --write to commit.")


if __name__ == "__main__":
    main()
