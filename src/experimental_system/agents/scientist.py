"""Scientist agent: task + knowledge pack (in the system prompt) -> ScientificSpecification.

Does not see devices. Must cite knowledge cards by id; criteria use catalog metrics only.
"""

from dataclasses import dataclass, field
from typing import Any

from experimental_system.agents.common import ask_checked, load_prompt
from experimental_system.knowledge.cards import KnowledgePack
from experimental_system.llm.base import LLMClient
from experimental_system.schemas.analysis import AnalysisReport
from experimental_system.schemas.task import ScientificSpecification, TaskRequest
from experimental_system.scientific_core.catalog import METRICS


@dataclass(frozen=True)
class ScientistInput:
    task: TaskRequest
    previous_specification: ScientificSpecification | None = None
    analyst_feedback: AnalysisReport | None = None  # set on REMODEL
    history: list[dict[str, Any]] = field(default_factory=list)


def scientist_system_prompt(pack: KnowledgePack) -> str:
    """The Scientist's full system prompt: role instructions + the whole knowledge pack."""
    return f"{load_prompt('scientist').rstrip()}\n\n{pack.text}"


def run_scientist(
    llm: LLMClient, pack: KnowledgePack, inp: ScientistInput
) -> ScientificSpecification:
    payload: dict[str, Any] = {
        "task": inp.task,
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
    known = pack.card_ids

    def check(spec: ScientificSpecification) -> list[str]:
        problems = []
        for c in spec.citations:
            if c.card_id not in known:
                problems.append(
                    f"citation {c.card_id!r} is not a card of the knowledge pack; "
                    f"valid card ids: {sorted(known)}"
                )
        if not spec.citations:
            problems.append("cite at least one knowledge card you rely on (by card_id)")
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

    return ask_checked(
        llm,
        agent="scientist",
        system=scientist_system_prompt(pack),
        payload=payload,
        response_model=ScientificSpecification,
        check=check,
    )
