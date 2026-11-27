# Agentic Experimental System

Мультиагентная система для автономных научных экспериментов. Сейчас работает в режиме
**симуляции** оптической установки «лазер → SLM → рассеивающая среда → камера»:
Изинг-машина на оптике (Delloye et al. 2023), калибровка матрицы передачи по одним
интенсивностям (GGS, Huang et al. 2021) и фазовое восстановление GS (Zhao & Chi 2020).

```
TaskRequest → Scientist → Experiment → Runner → Safety Validator → Simulation Backend
  (быстрый цикл в Python) → Scientific Core (метрики) → Analyst → DONE / REPLAN / REMODEL / ABORT
```

LLM никогда не считают числа и не управляют устройствами напрямую: все числа — из
детерминированного `scientific_core`, все команды проходят Safety Validator по Device
Registry. Подробности — в [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), история решений —
в [docs/DEVLOG.md](docs/DEVLOG.md).

## Быстрый старт

Требования: Python 3.12+, [uv](https://docs.astral.sh/uv/). Все команды — из корня репозитория.

```bash
uv sync                      # окружение и зависимости
uv run pytest                # тесты (live-тесты пропускаются)
uv run expsys scenarios      # список демо-сценариев
```

### Офлайн-демо (FakeLLM, без ключей и сети)

```bash
uv run expsys run --scenario ising_ground_state       # слабый план → REPLAN → успех
uv run expsys run --scenario tm_calibration_focusing  # GGS 2-1 (γ=4) + фокусировка
uv run expsys run --scenario two_foci_coupling        # тонкая среда, overlap реплик
uv run expsys run --scenario runner_out_of_range      # валидатор отклоняет 500 мВт
uv run expsys show <experiment_id>                    # сводка прогона
```

Результаты: `runs/<experiment_id>/` — `state.json`, `iterations/`, `arrays/*.npy`,
`llm_calls.jsonl`, `final_report.md` (отчёт на русском).

### Научные знания (knowledge pack)

Scientist получает все карточки `data/knowledge/cards/*.md` целиком в системном промпте
(поиска нет). Точный текст пакета каждого прогона сохраняется в
`runs/<id>/knowledge_pack.md`. PDF статей лежат только локально (`data/papers/*.pdf` в
`.gitignore`) — это первоисточники для людей, система их не читает.

### С настоящей LLM (OpenRouter)

```bash
cp .env.example .env   # заполнить OPENROUTER_API_KEY и DEFAULT_MODEL (или модели по агентам)
uv run expsys run "Find the optical Ising ground state for N = 16 spins" --llm openrouter
uv run expsys run --scenario two_foci_coupling --llm openrouter   # мир сценария, реальные агенты
uv run expsys run --scenario tm_calibration_focusing --llm openrouter --approve
```

`--scenario` с OpenRouter задаёт только «мир» симуляции (тип среды, seeds) и текст задачи;
ответы агентов генерирует модель. `--approve` — подтверждение перед каждым `execute()`.
Ограничители: `--max-iterations`, `EXPSYS_MAX_LLM_CALLS` (бюджет вызовов LLM на прогон).

## Разработка

```bash
uv run pytest                    # ~20 с
uv run ruff check . && uv run ruff format --check .
uv run mypy                      # strict
EXPSYS_RUN_LIVE=1 uv run pytest -m live   # реальный OpenRouter (нужен ключ, платно)
```

## Структура

```
configs/devices/simulation.yaml   Device Registry (симуляция; вымышленные значения)
configs/scenarios/*.yaml          демо-сценарии: задача + мир симуляции + ответы FakeLLM
data/knowledge/cards/*.md         карточки знаний (knowledge pack) со ссылками на статьи
src/experimental_system/
  schemas/         Pydantic-контракты (extra="forbid")
  devices/         YAML-реестр + Safety Validator
  scientific_core/ оптика, модели T, Изинг, GGS/GS, метрики, вычисление Metrics
  optimization/    быстрый внутренний цикл (batch-flip, simulated annealing)
  backends/        интерфейс backend + SimulationBackend
  knowledge/       карточки → knowledge pack (проверка, лимит размера)
  llm/             LLMClient, OpenRouter, FakeLLM, логирование и бюджет
  agents/ prompts/ Scientist, Experiment, Runner, Analyst + системные промпты
  orchestrator/    граф LangGraph, отчёт
  storage/         runs/<id>/…
  app.py cli.py    сборка компонентов и CLI `expsys`
```
