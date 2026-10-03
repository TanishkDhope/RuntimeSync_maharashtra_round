"""Read-only dataset loading.

`misconceptions.jsonl` and `problems.jsonl` live in /data and are JSON Lines,
not the single JSON arrays the brief describes. Loading is strict: a problem
that references an unknown misconception raises at startup rather than failing
halfway through a quiz.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

TOPICS = ("variables", "conditionals", "loops", "functions", "lists", "strings")
SLIP_ID = "SLIP"


@dataclass(frozen=True)
class Misconception:
    misconception_id: str
    description: str
    topic: str | None
    confusable_group: str | None
    split: str


@dataclass(frozen=True)
class TestCase:
    call: str
    expected: str


@dataclass(frozen=True)
class Problem:
    problem_id: str
    item_type: str  # predict_output | write_code
    topic: str
    problem_text: str
    correct_output: str | None
    reference_solution: str | None
    test_cases: tuple[TestCase, ...]
    applicable_misconceptions: tuple[str, ...]
    predicted_outputs: dict[str, str]
    split: str


@dataclass
class Library:
    """Everything loaded from /data, indexed for lookup."""

    misconceptions: dict[str, Misconception] = field(default_factory=dict)
    problems: dict[str, Problem] = field(default_factory=dict)

    def misconception(self, misconception_id: str) -> Misconception:
        return self.misconceptions[misconception_id]

    def problem(self, problem_id: str) -> Problem:
        return self.problems[problem_id]

    def ranked_misconceptions(self) -> list[Misconception]:
        """The library the diagnoser ranks against: train split only (brief s5)."""
        return [m for m in self.misconceptions.values() if m.split == "train"]

    def problems_for_topic(self, topic: str | None) -> list[Problem]:
        """Problems for one topic, or all of them when topic is None/"mixed"."""
        if topic in (None, "", "mixed"):
            return list(self.problems.values())
        return [p for p in self.problems.values() if p.topic == topic]

    def topic_counts(self) -> list[tuple[str, int]]:
        counts: dict[str, int] = {}
        for problem in self.problems.values():
            counts[problem.topic] = counts.get(problem.topic, 0) + 1
        ordered = [t for t in TOPICS if t in counts]
        ordered += sorted(t for t in counts if t not in TOPICS)
        return [(topic, counts[topic]) for topic in ordered]


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Dataset file not found: {path}")
    rows: list[dict] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path.name} line {line_number}: {exc}") from exc
    return rows


def load_library(data_dir: Path) -> Library:
    library = Library()

    for row in _read_jsonl(data_dir / "misconceptions.jsonl"):
        misconception = Misconception(
            misconception_id=row["misconception_id"],
            description=row["description"],
            topic=row.get("topic"),
            confusable_group=row.get("confusable_group"),
            split=row.get("split", "train"),
        )
        library.misconceptions[misconception.misconception_id] = misconception

    for row in _read_jsonl(data_dir / "problems.jsonl"):
        test_cases = tuple(
            TestCase(call=tc["call"], expected=tc["expected"])
            for tc in (row.get("test_cases") or [])
        )
        problem = Problem(
            problem_id=row["problem_id"],
            item_type=row["item_type"],
            topic=row["topic"],
            problem_text=row["problem_text"],
            correct_output=row.get("correct_output"),
            reference_solution=row.get("reference_solution"),
            test_cases=test_cases,
            applicable_misconceptions=tuple(row.get("applicable_misconceptions") or []),
            predicted_outputs=dict(row.get("predicted_outputs") or {}),
            split=row.get("split", "train"),
        )
        _validate_problem(problem, library)
        library.problems[problem.problem_id] = problem

    if SLIP_ID not in library.misconceptions:
        raise ValueError(f"misconceptions.jsonl is missing the special {SLIP_ID} entry")
    return library


def _validate_problem(problem: Problem, library: Library) -> None:
    known = library.misconceptions
    unknown = [m for m in problem.applicable_misconceptions if m not in known]
    unknown += [m for m in problem.predicted_outputs if m not in known]
    if unknown:
        raise ValueError(
            f"{problem.problem_id} references unknown misconceptions: {sorted(set(unknown))}"
        )
    if problem.item_type == "predict_output" and problem.correct_output is None:
        raise ValueError(f"{problem.problem_id} is predict_output but has no correct_output")
    if problem.item_type == "write_code" and not problem.test_cases:
        raise ValueError(f"{problem.problem_id} is write_code but has no test_cases")
