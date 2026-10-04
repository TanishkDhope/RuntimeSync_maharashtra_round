"""The belief graph: what a learner has shown, and what sits next to it.

The dataset already describes how misconceptions relate, in two ways that mean
different things:

  confusable   misconceptions.jsonl groups beliefs that produce similar wrong
               answers (confusable_group). These are the pairs the diagnoser
               has to tell apart, so an edge here is a warning: a belief next
               to one you hold may be the one you actually hold.

  co-occurs    two beliefs that several problems both test. Weaker, and only
               counted past CO_OCCURRENCE_MIN, because a single shared problem
               says nothing - the bank is small and overlaps are common.

What this is not: a prerequisite graph. Nothing in the dataset orders the
topics, so these edges describe association, not "fix this one first".
Claiming otherwise from co-occurrence counts would be inventing a curriculum.

The view is deliberately the learner's own neighbourhood rather than all 62
beliefs: the beliefs they have shown, plus one hop. The whole graph laid out
at once is a hairball nobody reads.
"""

from __future__ import annotations

from collections import defaultdict
from itertools import combinations

from sqlmodel import Session, select

from .data import SLIP_ID, Library
from .models import LearnerMisconception
from .schemas import BeliefGraphOut, GraphEdgeOut, GraphNodeOut

#: Problems two beliefs must share before the overlap counts as an edge.
CO_OCCURRENCE_MIN = 2


def _co_occurrence(library: Library) -> dict[tuple[str, str], int]:
    """How many problems test each pair of beliefs together."""
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for problem in library.problems.values():
        tested = sorted({m for m in problem.applicable_misconceptions if m != SLIP_ID})
        for pair in combinations(tested, 2):
            counts[pair] += 1
    return counts


def _siblings(library: Library) -> dict[str, set[str]]:
    """Beliefs that share a confusable_group, keyed by belief."""
    groups: dict[str, set[str]] = defaultdict(set)
    for m in library.misconceptions.values():
        if m.confusable_group:
            groups[m.confusable_group].add(m.misconception_id)
    out: dict[str, set[str]] = defaultdict(set)
    for members in groups.values():
        for m_id in members:
            out[m_id] |= members - {m_id}
    return out


def build_belief_graph(db: Session, library: Library, learner_id: int) -> BeliefGraphOut:
    """The learner's beliefs and their immediate neighbourhood."""
    standings = {
        row.misconception_id: row
        for row in db.exec(
            select(LearnerMisconception).where(LearnerMisconception.learner_id == learner_id)
        ).all()
    }
    known = {m_id for m_id in standings if m_id in library.misconceptions}
    total_beliefs = sum(1 for m in library.misconceptions.values() if m.misconception_id != SLIP_ID)

    if not known:
        return BeliefGraphOut(nodes=[], edges=[], hidden_beliefs=total_beliefs)

    siblings = _siblings(library)
    co_counts = _co_occurrence(library)

    # One hop out: confusable siblings, and beliefs sharing enough problems.
    neighbours: set[str] = set()
    for m_id in known:
        neighbours |= siblings.get(m_id, set())
    for (left, right), count in co_counts.items():
        if count < CO_OCCURRENCE_MIN:
            continue
        if left in known:
            neighbours.add(right)
        if right in known:
            neighbours.add(left)
    neighbours = {m_id for m_id in neighbours if m_id in library.misconceptions} - known

    shown = known | neighbours
    nodes: list[GraphNodeOut] = []

    topics = sorted({library.misconception(m_id).topic for m_id in shown if library.misconception(m_id).topic})
    for topic in topics:
        nodes.append(GraphNodeOut(id=f"topic:{topic}", kind="topic", label=topic, topic=topic))

    for m_id in sorted(shown):
        m = library.misconception(m_id)
        standing = standings.get(m_id)
        nodes.append(
            GraphNodeOut(
                id=m_id,
                kind="belief",
                label=m_id,
                description=m.description,
                topic=m.topic,
                status=standing.status if standing else None,
                times_seen=standing.times_seen if standing else 0,
                held=m_id in known,
            )
        )

    edges: list[GraphEdgeOut] = []
    for m_id in sorted(shown):
        topic = library.misconception(m_id).topic
        if topic:
            edges.append(GraphEdgeOut(source=f"topic:{topic}", target=m_id, kind="in_topic"))

    seen_pairs: set[tuple[str, str]] = set()
    for m_id in sorted(shown):
        for other in sorted(siblings.get(m_id, set())):
            if other not in shown:
                continue
            pair = tuple(sorted((m_id, other)))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            edges.append(GraphEdgeOut(source=pair[0], target=pair[1], kind="confusable"))

    for (left, right), count in sorted(co_counts.items()):
        if count < CO_OCCURRENCE_MIN or left not in shown or right not in shown:
            continue
        if (left, right) in seen_pairs:
            # Already drawn as a confusable pair, which is the stronger claim.
            continue
        edges.append(GraphEdgeOut(source=left, target=right, kind="co_occurs", weight=float(count)))

    return BeliefGraphOut(
        nodes=nodes,
        edges=edges,
        hidden_beliefs=max(0, total_beliefs - len(shown)),
    )
