"""Final report (Markdown, in Russian), rendered deterministically from the state."""

from experimental_system.schemas.state import ExperimentState, ExperimentStatus, IterationRecord

_STATUS_RU = {
    ExperimentStatus.RUNNING: "выполняется",
    ExperimentStatus.DONE: "успех (DONE): все критерии выполнены",
    ExperimentStatus.ABORTED: "остановлен (ABORTED)",
    ExperimentStatus.ITERATION_LIMIT: "достигнут лимит итераций (ITERATION_LIMIT)",
    ExperimentStatus.FAILED: "техническая ошибка (FAILED)",
}


def _fmt(value: float | None) -> str:
    if value is None:
        return "—"
    if value == int(value) and abs(value) < 1e9:
        return str(int(value))
    return f"{value:.4g}"


def _iteration(record: IterationRecord) -> list[str]:
    lines = [f"### Итерация {record.iteration}", ""]
    if record.plan is not None:
        lines += [f"**План.** {record.plan.rationale}", ""]
        for step in record.plan.steps:
            params = ", ".join(f"{k}={v}" for k, v in step.parameters.items())
            lines.append(
                f"- `{step.step_id}` **{step.action}** — {step.description} "
                f"(устройства: {', '.join(step.devices) or '—'}{'; ' + params if params else ''})"
            )
        lines.append("")
    if record.runner_corrections:
        lines += [
            f"Safety Validator отклонял команды Runner'а; исправлений: "
            f"{record.runner_corrections}.",
            "",
        ]
    if record.validations:
        lines.append(f"Команд принято валидатором: {sum(v.accepted for v in record.validations)}.")
    if record.execution is not None:
        lines.append(
            f"Исполнение: **{record.execution.status.value}** ({record.execution.backend})."
        )
        for err in record.execution.errors:
            lines.append(f"- ошибка: {err.message}")
    lines.append("")
    if record.metrics is not None and record.metrics.values:
        lines += ["| Метрика | Значение |", "|---|---|"]
        lines += [f"| `{k}` | {_fmt(v)} |" for k, v in record.metrics.values.items()]
        lines.append("")
    if record.metrics is not None and record.metrics.criteria:
        lines += ["| Критерий | Наблюдение | Выполнен |", "|---|---|---|"]
        for c in record.metrics.criteria:
            crit = f"`{c.criterion.metric}` {c.criterion.op} {_fmt(c.criterion.target)}"
            lines.append(f"| {crit} | {_fmt(c.observed)} | {'да' if c.passed else 'нет'} |")
        lines.append("")
    if record.analysis is not None:
        a = record.analysis
        lines += [f"**Решение Analyst: {a.decision.value}.** {a.rationale}", ""]
        for item in a.anomalies:
            lines.append(f"- аномалия: {item}")
        for item in a.recommendations:
            lines.append(f"- рекомендация: {item}")
        lines.append("")
    return lines


def render_report(state: ExperimentState) -> str:
    lines = [
        f"# Отчёт об эксперименте `{state.experiment_id}`",
        "",
        f"- **Итог:** {_STATUS_RU[state.status]}",
        f"- **Итераций:** {len(state.history)} (лимит {state.max_iterations})",
        f"- **Вызовов LLM:** {state.llm_calls}",
        f"- **Задача создана:** {state.task.created_at.isoformat(timespec='seconds')}",
        "",
        "## Задача",
        "",
        state.task.description,
        "",
    ]
    spec = state.specification or (state.history[-1].specification if state.history else None)
    if spec is not None:
        lines += [
            "## Научная постановка (Scientist)",
            "",
            f"- **Цель:** {spec.objective}",
            f"- **Тип задачи:** `{spec.task_type}`",
            f"- **Модель:** {spec.math_model.description}",
        ]
        lines += [f"  - `{eq}`" for eq in spec.math_model.equations]
        lines.append("- **Критерии успеха:**")
        lines += [
            f"  - `{c.metric}` {c.op} {_fmt(c.target)}"
            + (f" — {c.description}" if c.description else "")
            for c in spec.success_criteria
        ]
        if spec.assumptions:
            lines.append("- **Допущения:** " + "; ".join(spec.assumptions))
        if spec.open_questions:
            lines.append("- **Открытые вопросы:** " + "; ".join(spec.open_questions))
        lines.append("")
    lines += ["## Что делалось по итерациям", ""]
    for record in state.history:
        lines += _iteration(record)
    if state.history and any(r.metrics for r in state.history):
        names = sorted({k for r in state.history if r.metrics for k in r.metrics.values})
        lines += [
            "## Метрики по итерациям",
            "",
            "| Метрика | " + " | ".join(f"it {r.iteration}" for r in state.history) + " |",
            "|---|" + "---|" * len(state.history),
        ]
        for name in names:
            row = [_fmt(r.metrics.values.get(name)) if r.metrics else "—" for r in state.history]
            lines.append(f"| `{name}` | " + " | ".join(row) + " |")
        lines.append("")
    lines += ["## Итог", "", _STATUS_RU[state.status] + "."]
    for err in state.errors:
        lines.append(f"- {err}")
    for note in state.notes:
        lines.append(f"- примечание: {note}")
    lines.append("")
    cited = {c.card_id: c.note for r in state.history for c in r.specification.citations}
    if spec is not None:
        cited.update({c.card_id: c.note for c in spec.citations})
    if cited:
        by_id = {card.card_id: card for card in state.knowledge_cards}
        lines += ["## Источники (карточки knowledge pack, процитированные Scientist)", ""]
        for card_id, cite_note in cited.items():
            card = by_id.get(card_id)
            where = f" — {card.title}. {card.source}" if card is not None else ""
            lines.append(f"- `{card_id}`{where}" + (f" ({cite_note})" if cite_note else ""))
        lines.append("")
    if state.knowledge_pack_sha256:
        lines += [
            f"Knowledge pack: {len(state.knowledge_cards)} карточек, sha256 "
            f"`{state.knowledge_pack_sha256[:16]}…` (полный текст — `knowledge_pack.md`).",
            "",
        ]
    return "\n".join(lines)
