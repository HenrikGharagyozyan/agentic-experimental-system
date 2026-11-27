"""Scientist agent: task + Knowledge Base fragments -> ScientificSpecification.

Does not see devices. Must cite retrieved fragments; criteria use catalog metrics only.
"""

from dataclasses import dataclass, field
from typing import Any

from experimental_system.agents.common import ask_checked, load_prompt
from experimental_system.knowledge.base import KnowledgeBase
from experimental_system.llm.base import LLMClient
from experimental_system.schemas.analysis import AnalysisReport
from experimental_system.schemas.knowledge import KnowledgeFragment
from experimental_system.schemas.task import ScientificSpecification, TaskRequest
from experimental_system.scientific_core.catalog import METRICS


@dataclass(frozen=True)
class ScientistInput:
    task: TaskRequest
    previous_specification: ScientificSpecification | None = None
    analyst_feedback: AnalysisReport | None = None  # set on REMODEL
    history: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class ScientistOutput:
    specification: ScientificSpecification
    fragments: list[KnowledgeFragment]


def search_query(inp: ScientistInput) -> str:
    parts = [inp.task.description]
    if inp.task.task_type_hint:
        parts.append(inp.task.task_type_hint.replace("_", " "))
    if inp.analyst_feedback is not None:
        parts.append(inp.analyst_feedback.rationale)
    return " ".join(parts)


def retrieve(
    kb: KnowledgeBase, query: str, *, top_k: int = 6, cards_k: int = 4
) -> list[KnowledgeFragment]:
    """Curated knowledge cards first (key formulas), then the best matches overall."""
    cards = kb.search(query, top_k=cards_k, filters={"kind": "card"})
    rest = kb.search(query, top_k=top_k)
    seen = {f.fragment_id for f in cards}
    return cards + [f for f in rest if f.fragment_id not in seen]


def run_scientist(
    llm: LLMClient, kb: KnowledgeBase, inp: ScientistInput, *, top_k: int = 6
) -> ScientistOutput:
    fragments = retrieve(kb, search_query(inp), top_k=top_k)
    retrieved = {f.fragment_id for f in fragments}
    payload: dict[str, Any] = {
        "task": inp.task,
        "knowledge_fragments": [
            {
                "fragment_id": f.fragment_id,
                "source": f.source,
                "section": f.metadata.get("section") or f.metadata.get("title"),
                "text": f.text,
            }
            for f in fragments
        ],
        "available_metrics": {name: info.description for name, info in METRICS.items()},
    }
    if inp.previous_specification is not None:
        payload["previous_specification"] = inp.previous_specification
    if inp.analyst_feedback is not None:
        payload["analyst_feedback"] = {
            "decision": inp.analyst_feedback.decision.value,
            "rationale": inp.analyst_feedback.rationale,
            "recommendations": inp.analyst_feedback.recommendations,
        }
    if inp.history:
        payload["history"] = inp.history

    def check(spec: ScientificSpecification) -> list[str]:
        problems = []
        for c in spec.citations:
            if c.fragment_id not in retrieved:
                problems.append(
                    f"citation {c.fragment_id!r} was not among the retrieved knowledge_fragments"
                )
        if fragments and not spec.citations:
            problems.append("cite at least one retrieved fragment you rely on (by fragment_id)")
        for criterion in spec.success_criteria:
            if criterion.metric not in METRICS:
                problems.append(
                    f"success criterion uses unknown metric {criterion.metric!r}; "
                    f"use only: {sorted(METRICS)}"
                )
        if (
            inp.analyst_feedback is not None
            and inp.previous_specification is not None
            and spec == inp.previous_specification
        ):
            problems.append("REMODEL requires a changed specification; do not repeat it unchanged")
        return problems

    spec = ask_checked(
        llm,
        agent="scientist",
        system=load_prompt("scientist"),
        payload=payload,
        response_model=ScientificSpecification,
        check=check,
    )
    return ScientistOutput(specification=spec, fragments=fragments)
