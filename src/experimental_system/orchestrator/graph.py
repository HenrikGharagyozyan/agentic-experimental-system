"""Orchestrator: explicit state machine (LangGraph) driving the four agents.

    scientist -> experiment -> runner -> validate --(rejected, <= 2x)--> runner
                                            |
                                         execute (optional human approval)
                                            |
                                         metrics -> analyst -> route
    route: DONE -> finalize | ABORT -> finalize | REPLAN -> experiment | REMODEL -> scientist
           (iteration limit -> ITERATION_LIMIT; any error -> FAILED, history kept)

The whole ExperimentState travels in one LangGraph channel as an immutable Pydantic
object; every node is a plain function ``ExperimentState -> ExperimentState`` and the
state is persisted after each node.
"""

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from experimental_system.agents import (
    AnalystInput,
    ExperimentInput,
    ScientistInput,
    run_analyst,
    run_experiment,
    run_runner,
    run_scientist,
)
from experimental_system.agents.context import iteration_summaries
from experimental_system.backends.base import ExecutionBackend
from experimental_system.config import AgentName
from experimental_system.devices.registry import DeviceRegistry
from experimental_system.devices.validator import SafetyValidator, all_accepted
from experimental_system.knowledge.base import KnowledgeBase
from experimental_system.llm.base import LLMClient
from experimental_system.llm.tracking import CallBudget
from experimental_system.orchestrator.report import render_report
from experimental_system.schemas.analysis import Decision
from experimental_system.schemas.devices import DeviceCommand
from experimental_system.schemas.state import ExperimentState, ExperimentStatus, IterationRecord
from experimental_system.schemas.task import TaskRequest
from experimental_system.scientific_core.evaluation import compute_metrics
from experimental_system.storage.run_store import RunStore

log = logging.getLogger(__name__)

Approver = Callable[[Sequence[DeviceCommand]], bool]
MAX_RUNNER_CORRECTIONS = 2


class GraphState(TypedDict):
    exp: ExperimentState


@dataclass
class OrchestratorDeps:
    llms: dict[AgentName, LLMClient]
    kb: KnowledgeBase
    registry: DeviceRegistry
    backend: ExecutionBackend
    store: RunStore
    budget: CallBudget
    approver: Approver | None = None  # set => pause before every execute()


Node = Callable[[ExperimentState], ExperimentState]


class Orchestrator:
    def __init__(self, deps: OrchestratorDeps) -> None:
        self.deps = deps
        self.validator = SafetyValidator(deps.registry)
        self.graph = self._build()

    # --- public API ------------------------------------------------------------------------

    def run(self, task: TaskRequest, *, max_iterations: int, experiment_id: str) -> ExperimentState:
        state = ExperimentState(
            experiment_id=experiment_id, task=task, max_iterations=max_iterations
        )
        self.deps.store.save_state(state)
        per_iteration = 8 + 2 * MAX_RUNNER_CORRECTIONS
        result = self.graph.invoke(
            {"exp": state}, config={"recursion_limit": per_iteration * max_iterations + 10}
        )
        final: ExperimentState = result["exp"]
        return final

    # --- graph -----------------------------------------------------------------------------

    def _build(self) -> Any:
        g = StateGraph(GraphState)
        nodes: dict[str, Node] = {
            "scientist": self._scientist,
            "experiment": self._experiment,
            "runner": self._runner,
            "validate": self._validate,
            "execute": self._execute,
            "metrics": self._metrics,
            "analyst": self._analyst,
            "route": self._route,
            "finalize": self._finalize,
        }
        for name, fn in nodes.items():
            # LangGraph's node protocols want a named `state` parameter; ours is positional.
            g.add_node(name, self._wrap(name, fn))  # type: ignore[call-overload]
        g.add_edge(START, "scientist")
        linear = [
            ("scientist", "experiment"),
            ("experiment", "runner"),
            ("runner", "validate"),
            ("execute", "metrics"),
            ("metrics", "analyst"),
            ("analyst", "route"),
        ]
        for src, dst in linear:
            g.add_conditional_edges(src, self._continue_to(dst), [dst, "finalize"])
        g.add_conditional_edges("validate", self._after_validate, ["runner", "execute", "finalize"])
        g.add_conditional_edges("route", self._after_route, ["scientist", "experiment", "finalize"])
        g.add_edge("finalize", END)
        return g.compile()

    def _wrap(self, name: str, fn: Node) -> Callable[[GraphState], GraphState]:
        def node(gs: GraphState) -> GraphState:
            state = gs["exp"]
            try:
                new = fn(state)
            except Exception as exc:  # LLM, agent, backend, storage... -> FAILED, keep history
                log.exception("node %s failed", name)
                new = self._fail(state, f"{name}: {type(exc).__name__}: {exc}")
            new = new.model_copy(update={"llm_calls": self.deps.budget.used})
            self.deps.store.save_state(new)
            return {"exp": new}

        return node

    @staticmethod
    def _continue_to(dst: str) -> Callable[[GraphState], str]:
        def edge(gs: GraphState) -> str:
            return dst if gs["exp"].status is ExperimentStatus.RUNNING else "finalize"

        return edge

    def _after_validate(self, gs: GraphState) -> str:
        state = gs["exp"]
        if state.status is not ExperimentStatus.RUNNING:
            return "finalize"
        return "execute" if all_accepted(state.validations) else "runner"

    @staticmethod
    def _after_route(gs: GraphState) -> str:
        state = gs["exp"]
        if state.status is not ExperimentStatus.RUNNING or state.analysis is None:
            return "finalize"
        return "scientist" if state.analysis.decision is Decision.REMODEL else "experiment"

    # --- nodes -----------------------------------------------------------------------------

    def _history(self, state: ExperimentState) -> list[dict[str, Any]]:
        return iteration_summaries(state.history)

    def _scientist(self, state: ExperimentState) -> ExperimentState:
        remodel = (
            state.analysis
            if state.analysis and state.analysis.decision is Decision.REMODEL
            else None
        )
        out = run_scientist(
            self.deps.llms["scientist"],
            self.deps.kb,
            ScientistInput(
                task=state.task,
                previous_specification=state.specification if remodel else None,
                analyst_feedback=remodel,
                history=self._history(state),
            ),
        )
        known = {f.fragment_id for f in state.fragments}
        fragments = state.fragments + [f for f in out.fragments if f.fragment_id not in known]
        return state.model_copy(
            update={"specification": out.specification, "fragments": fragments, **_cleared()}
        )

    def _experiment(self, state: ExperimentState) -> ExperimentState:
        assert state.specification is not None
        replan = (
            state.analysis
            if state.analysis and state.analysis.decision is Decision.REPLAN
            else None
        )
        plan = run_experiment(
            self.deps.llms["experiment"],
            self.deps.registry,
            ExperimentInput(
                specification=state.specification,
                previous_plan=state.plan if replan else None,
                analyst_feedback=replan,
                history=self._history(state),
            ),
        )
        return state.model_copy(update={**_cleared(), "plan": plan})

    def _runner(self, state: ExperimentState) -> ExperimentState:
        assert state.plan is not None
        rejected = state.validations if state.validations else ()
        corrections = state.runner_corrections + (1 if rejected else 0)
        batch = run_runner(
            self.deps.llms["runner"],
            self.deps.registry,
            state.plan,
            self.deps.backend.device_status(),
            rejected=rejected,
        )
        return state.model_copy(
            update={
                "commands": batch.commands,
                "validations": [],
                "runner_corrections": corrections,
            }
        )

    def _validate(self, state: ExperimentState) -> ExperimentState:
        validations = self.validator.validate_batch(state.commands)
        new = state.model_copy(update={"validations": validations})
        if all_accepted(validations):
            return new
        problems = [v.message for r in validations for v in r.violations]
        if state.runner_corrections >= MAX_RUNNER_CORRECTIONS:
            return self._fail(
                new,
                f"safety validator rejected the Runner's commands after "
                f"{MAX_RUNNER_CORRECTIONS} corrections: {problems}",
            )
        return new.model_copy(
            update={
                "notes": [
                    *new.notes,
                    f"iteration {state.iteration}: validator rejected: {problems}",
                ]
            }
        )

    def _execute(self, state: ExperimentState) -> ExperimentState:
        if self.deps.approver is not None and not self.deps.approver(state.commands):
            return self._record(
                state.model_copy(
                    update={
                        "status": ExperimentStatus.ABORTED,
                        "errors": [*state.errors, "execution not approved by the operator"],
                    }
                )
            )
        # Defense in depth: never execute anything the validator has not accepted.
        if not all_accepted(self.validator.validate_batch(state.commands)):
            raise RuntimeError("refusing to execute unvalidated commands")
        self.deps.store.prefix = f"it{state.iteration:02d}"
        execution = self.deps.backend.execute(state.commands)
        return state.model_copy(update={"execution": execution})

    def _metrics(self, state: ExperimentState) -> ExperimentState:
        assert state.execution is not None and state.specification is not None
        metrics = compute_metrics(
            state.execution, self.deps.store.load_array, state.specification.success_criteria
        )
        return state.model_copy(update={"metrics": metrics})

    def _analyst(self, state: ExperimentState) -> ExperimentState:
        assert state.specification and state.plan and state.execution and state.metrics
        out = run_analyst(
            self.deps.llms["analyst"],
            AnalystInput(
                specification=state.specification,
                plan=state.plan,
                execution=state.execution,
                metrics=state.metrics,
                history=self._history(state),
            ),
        )
        notes = state.notes + (
            [f"iteration {state.iteration}: {out.override_note}"] if out.override_note else []
        )
        return state.model_copy(update={"analysis": out.report, "notes": notes})

    def _route(self, state: ExperimentState) -> ExperimentState:
        assert state.analysis is not None
        state = self._record(state)
        decision = state.analysis.decision if state.analysis else Decision.ABORT
        if decision is Decision.DONE:
            return state.model_copy(update={"status": ExperimentStatus.DONE})
        if decision is Decision.ABORT:
            return state.model_copy(update={"status": ExperimentStatus.ABORTED})
        if state.iteration + 1 >= state.max_iterations:
            return state.model_copy(
                update={
                    "status": ExperimentStatus.ITERATION_LIMIT,
                    "errors": [
                        *state.errors,
                        f"max_iterations={state.max_iterations} reached without success",
                    ],
                }
            )
        return state.model_copy(update={"iteration": state.iteration + 1})

    def _finalize(self, state: ExperimentState) -> ExperimentState:
        self.deps.store.write_text("final_report.md", render_report(state))
        return state

    # --- helpers ---------------------------------------------------------------------------

    def _record(self, state: ExperimentState) -> ExperimentState:
        """Append the current iteration to history (once per iteration)."""
        if state.specification is None:
            return state
        if state.history and state.history[-1].iteration == state.iteration:
            return state
        record = IterationRecord(
            iteration=state.iteration,
            specification=state.specification,
            plan=state.plan,
            validations=state.validations,
            runner_corrections=state.runner_corrections,
            execution=state.execution,
            metrics=state.metrics,
            analysis=state.analysis,
        )
        self.deps.store.save_iteration(record)
        return state.model_copy(update={"history": [*state.history, record]})

    def _fail(self, state: ExperimentState, message: str) -> ExperimentState:
        failed = state.model_copy(
            update={"status": ExperimentStatus.FAILED, "errors": [*state.errors, message]}
        )
        return self._record(failed)


def _cleared() -> dict[str, Any]:
    """Fields of the current iteration that a new plan invalidates."""
    return {
        "plan": None,
        "commands": [],
        "validations": [],
        "runner_corrections": 0,
        "execution": None,
        "metrics": None,
        "analysis": None,  # read by scientist/experiment before clearing (REMODEL/REPLAN)
    }
