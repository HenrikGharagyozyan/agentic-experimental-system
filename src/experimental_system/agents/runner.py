"""Runner agent: plan + full device descriptions + statuses -> CommandBatch.

The Runner only proposes; the Safety Validator (code) decides. On rejection the
orchestrator calls the Runner again with the violations.
"""

from collections.abc import Sequence
from typing import Any

from experimental_system.agents.common import ask_checked, load_prompt
from experimental_system.devices.registry import DeviceRegistry
from experimental_system.llm.base import LLMClient
from experimental_system.schemas.devices import CommandBatch, ValidationResult
from experimental_system.schemas.execution import DeviceStatus
from experimental_system.schemas.plan import ExperimentPlan


def run_runner(
    llm: LLMClient,
    registry: DeviceRegistry,
    plan: ExperimentPlan,
    statuses: Sequence[DeviceStatus],
    *,
    rejected: Sequence[ValidationResult] = (),
) -> CommandBatch:
    payload: dict[str, Any] = {
        "plan": plan,
        "device_registry": [d.model_dump(mode="json") for d in registry.list_devices()],
        "device_statuses": list(statuses),
    }
    if rejected:
        payload["previous_commands_rejected_by_safety_validator"] = [
            {
                "command": r.command,
                "violations": [v.message for v in r.violations],
            }
            for r in rejected
            if not r.accepted
        ]
    step_ids = {s.step_id for s in plan.steps}
    offline = {s.device_id for s in statuses if s.state in ("offline", "error")}

    def check(batch: CommandBatch) -> list[str]:
        problems = []
        for c in batch.commands:
            if c.step_id not in step_ids:
                problems.append(f"command step_id {c.step_id!r} is not a step of the plan")
            if c.device_id in offline:
                problems.append(f"device {c.device_id!r} is not available (status offline/error)")
        return problems

    return ask_checked(
        llm,
        agent="runner",
        system=load_prompt("runner"),
        payload=payload,
        response_model=CommandBatch,
        check=check,
        max_attempts=2,
    )
