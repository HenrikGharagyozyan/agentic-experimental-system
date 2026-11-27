"""Builders of known-valid contract objects for tests.

Negative tests start from one of these, break a single field via ``model_dump()``
and assert that ``model_validate`` rejects the result.
Devices here are neutral, fictional test devices — not real lab equipment.
"""

from datetime import UTC, datetime, timedelta

from experimental_system.schemas import (
    AnalysisReport,
    Citation,
    CommandParam,
    CriterionResult,
    Decision,
    DeviceCommand,
    DeviceSpec,
    DeviceStatus,
    ExecutionResult,
    ExecutionStatus,
    ExperimentPlan,
    ExperimentState,
    IterationRecord,
    MathModel,
    Measurement,
    Metrics,
    OperationSpec,
    ParameterSpec,
    PlanStep,
    ScientificSpecification,
    SuccessCriterion,
    TaskRequest,
    ValidationResult,
)

T0 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def make_task() -> TaskRequest:
    return TaskRequest(description="Minimise a toy objective", task_type_hint="toy_problem")


def make_criterion() -> SuccessCriterion:
    return SuccessCriterion(metric="objective", op="<=", target=1.0)


def make_spec() -> ScientificSpecification:
    return ScientificSpecification(
        objective="Find a configuration with low objective value",
        task_type="toy_problem",
        math_model=MathModel(description="Toy model", equations=["f(x) = x^2"]),
        parameters={"n_variables": 4, "use_bias": False},
        success_criteria=[make_criterion()],
        assumptions=["Noise is negligible"],
        open_questions=["Is the objective convex?"],
        citations=[Citation(card_id="toy_card", note="Definition of f")],
    )


def make_plan() -> ExperimentPlan:
    return ExperimentPlan(
        rationale="Calibrate, then measure",
        steps=[
            PlanStep(
                step_id="s1",
                action="calibrate",
                description="Calibrate the test source",
                devices=["test_source"],
            ),
            PlanStep(
                step_id="s2",
                action="capture",
                description="Capture with the test detector",
                devices=["test_detector"],
                depends_on=["s1"],
            ),
        ],
    )


def make_device() -> DeviceSpec:
    return DeviceSpec(
        device_id="test_source",
        kind="source",
        operations=[
            OperationSpec(
                name="set_level",
                parameters=[
                    ParameterSpec(name="level", kind="float", unit="mV", minimum=0, maximum=500),
                    ParameterSpec(name="mode", kind="choice", choices=["cw", "pulsed"]),
                ],
            )
        ],
    )


def make_command() -> DeviceCommand:
    return DeviceCommand(
        step_id="s1",
        device_id="test_source",
        operation="set_level",
        parameters={
            "level": CommandParam(value=100.0, unit="mV"),
            "mode": CommandParam(value="cw"),
        },
    )


def make_execution() -> ExecutionResult:
    return ExecutionResult(
        backend="simulation",
        status=ExecutionStatus.SUCCESS,
        measurements=[Measurement(name="objective", value=0.5, step_id="s2")],
        device_statuses=[DeviceStatus(device_id="test_source", state="ok")],
        started_at=T0,
        finished_at=T0 + timedelta(seconds=2),
    )


def make_metrics() -> Metrics:
    return Metrics(
        values={"objective": 0.5},
        criteria=[CriterionResult(criterion=make_criterion(), observed=0.5, passed=True)],
    )


def make_report() -> AnalysisReport:
    return AnalysisReport(
        decision=Decision.DONE,
        rationale="Objective is below target",
        referenced_metrics=["objective"],
    )


def make_state() -> ExperimentState:
    """A fully populated state with one history record."""
    spec = make_spec()
    plan = make_plan()
    validations = [ValidationResult(command=make_command())]
    return ExperimentState(
        task=make_task(),
        iteration=1,
        max_iterations=5,
        specification=spec,
        plan=plan,
        commands=[make_command()],
        validations=validations,
        execution=make_execution(),
        metrics=make_metrics(),
        analysis=make_report(),
        history=[
            IterationRecord(
                iteration=0,
                specification=spec,
                plan=plan,
                validations=validations,
                execution=make_execution(),
                metrics=make_metrics(),
                analysis=make_report(),
            )
        ],
    )
