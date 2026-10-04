"""The belief graph: a learner's misconceptions and what sits next to them."""

from __future__ import annotations

from app.db import build_engine, create_tables
from app.graph import CO_OCCURRENCE_MIN, build_belief_graph
from app.models import Learner, LearnerMisconception
from sqlmodel import Session


def _learner_with(db, name, beliefs):
    learner = Learner(name=name)
    db.add(learner)
    db.commit()
    db.refresh(learner)
    for misconception_id, status in beliefs.items():
        db.add(
            LearnerMisconception(
                learner_id=learner.id, misconception_id=misconception_id,
                status=status, times_seen=2,
            )
        )
    db.commit()
    return learner


def test_a_learner_with_nothing_diagnosed_gets_an_empty_graph(settings, library):
    """Not an error: there is simply no neighbourhood to draw yet."""
    engine = build_engine(settings)
    create_tables(engine)
    with Session(engine) as db:
        learner = _learner_with(db, "Nobody", {})
        graph = build_belief_graph(db, library, learner.id)
        assert graph.nodes == []
        assert graph.edges == []
        assert graph.hidden_beliefs > 0


def test_the_graph_is_the_learners_own_neighbourhood(settings, library):
    """Their beliefs, plus one hop - not all sixty-odd in the library."""
    engine = build_engine(settings)
    create_tables(engine)
    with Session(engine) as db:
        learner = _learner_with(db, "Grapher", {"RANGE_FROM_1": "active"})
        graph = build_belief_graph(db, library, learner.id)

        beliefs = [n for n in graph.nodes if n.kind == "belief"]
        held = [n for n in beliefs if n.held]
        assert [n.id for n in held] == ["RANGE_FROM_1"]
        assert held[0].status == "active"

        # The confusable siblings come along, marked as not shown.
        ids = {n.id for n in beliefs}
        assert "RANGE_INCLUDES_END" in ids
        assert all(not n.held for n in beliefs if n.id != "RANGE_FROM_1")
        assert len(ids) < len(library.misconceptions)
        assert graph.hidden_beliefs > 0


def test_confusable_beliefs_are_joined_and_outrank_co_occurrence(settings, library):
    """The pair a diagnoser has to split is the stronger claim, drawn once."""
    engine = build_engine(settings)
    create_tables(engine)
    with Session(engine) as db:
        learner = _learner_with(db, "Pairs", {"RANGE_FROM_1": "active"})
        graph = build_belief_graph(db, library, learner.id)

        pairs = {
            tuple(sorted((e.source, e.target)))
            for e in graph.edges
            if e.kind == "confusable"
        }
        assert ("RANGE_FROM_1", "RANGE_INCLUDES_END") in pairs

        # No pair is drawn twice under two different kinds.
        drawn = [tuple(sorted((e.source, e.target))) for e in graph.edges if e.kind != "in_topic"]
        assert len(drawn) == len(set(drawn))


def test_a_single_shared_problem_is_not_an_edge(settings, library):
    """The bank is small; one overlap is noise, not a relationship."""
    engine = build_engine(settings)
    create_tables(engine)
    with Session(engine) as db:
        learner = _learner_with(db, "Thresholds", {"RANGE_FROM_1": "active"})
        graph = build_belief_graph(db, library, learner.id)
        assert all(e.weight >= CO_OCCURRENCE_MIN for e in graph.edges if e.kind == "co_occurs")


def test_every_belief_hangs_off_its_topic(settings, library):
    """The hubs are what make the picture readable rather than a hairball."""
    engine = build_engine(settings)
    create_tables(engine)
    with Session(engine) as db:
        learner = _learner_with(
            db, "Topical", {"RANGE_FROM_1": "active", "ASSIGN_LINKS_VARIABLES": "resolved"}
        )
        graph = build_belief_graph(db, library, learner.id)

        topic_ids = {n.id for n in graph.nodes if n.kind == "topic"}
        assert topic_ids  # loops and variables at least
        for node in graph.nodes:
            if node.kind == "belief" and node.topic:
                assert any(
                    e.kind == "in_topic" and e.target == node.id and e.source == f"topic:{node.topic}"
                    for e in graph.edges
                )
        # Edges only ever reference nodes that were actually sent.
        known = {n.id for n in graph.nodes}
        for edge in graph.edges:
            assert edge.source in known and edge.target in known


def test_the_graph_endpoint_serves_it(client):
    learner_id = client.post("/learners", json={"name": "GraphEndpoint"}).json()["id"]

    res = client.get(f"/learners/{learner_id}/graph")
    assert res.status_code == 200
    body = res.json()
    assert body["nodes"] == [] and body["edges"] == []
    assert body["hidden_beliefs"] > 0

    assert client.get("/learners/999999/graph").status_code == 404
