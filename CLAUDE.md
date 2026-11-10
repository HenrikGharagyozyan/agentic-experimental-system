# CLAUDE.md — working rules for this repository

## Who you are working with

I am the developer and the owner of every decision in this project. I am learning the
architecture as we build it. Your job is to be a careful senior engineer **and a teacher**:
you propose, explain and implement; I review, decide and approve.

**Always talk to me in Russian.** Code, identifiers, comments, docstrings and commit
messages are in English.

The full project specification is in `docs/PROJECT_SPEC.md`. Read it at the start of
every session.

## The workflow you must follow (no exceptions)

For every task, however small:

1. **Plan first, code later.** Before touching any file, describe:
   - what you are going to do and why;
   - which files you will create or change;
   - which alternatives exist and why you recommend this one.
   Then **stop and wait for my approval**.
2. **Ask instead of guessing.** If something is ambiguous or is an architectural decision
   (library choice, data format, interface shape, folder layout, naming that will spread
   through the code), ask me with 2–3 options and your recommendation. Do not decide for me.
3. **Small steps.** One logical change at a time (one module, one interface, one schema
   group). Never generate large parts of the system in one go.
4. **Explain the code you wrote.** After each change give me a short explanation in
   Russian:
   - what each new file / class / function does;
   - the key design decisions and *why* they were made;
   - any new concept I may not know (e.g. Pydantic validator, Protocol, async, fixture,
     state machine) — explain it in 2–5 sentences with a tiny example.
5. **Tests.** Every component gets tests. Run them and show me the result.
6. **Stop at the end of each step** and wait for my review before continuing.
7. **Never commit or push.** I make all git commits and pushes myself. You may suggest a
   commit message.
8. Never install new dependencies, delete files, or change project configuration
   (`pyproject.toml`, `.claude/`, CI) without asking first.

If I say "объясни" or "почему", explain in more depth before continuing.

**Current mode: fast MVP.** We are building a minimal end-to-end skeleton tonight.
Steps may be a bit larger (one milestone step = one reviewable chunk), explanations stay
short and focused on decisions and new concepts — but approval before writing code and
the "no commits" rule still apply. Prefer the simplest working solution; mark anything
deferred with `# TODO(later):`.

## Architecture in one paragraph

Multi-agent system for autonomous scientific experiments. An **Orchestrator** (explicit
state machine, LangGraph) drives four LLM agents:

- **Scientist** — scientific formulation (what the problem means, formulas, success
  criteria).
- **Experiment** — decides which experiments to run and which devices are involved
  (step-level plan).
- **Runner** — device specialist: turns plan steps into concrete device commands using
  the device registry, checks device health, executes via the backend.
- **Analyst** — interprets results, decides: done / adjust plan (→ Experiment) /
  rethink model (→ Scientist) / stop with error.

Flow: Scientist → Experiment → Runner → Analyst → (route back or finish).

Non-LLM parts: **Device Registry** (YAML/JSON: devices, parameters, ranges, units),
**Safety Validator** (rejects any command outside the registry in code), **Scientific
Core** (all math), **Optimization Engine**, **Execution backends** (Simulation now,
Hardware via MCP later, one common interface), **Storage**, **LLM provider layer**.
Agents exchange **Pydantic models**, never free text.

## Hard rules

- **LLMs never do arithmetic.** All numbers (energy, metrics, errors) come from
  deterministic Python in `scientific_core/`.
- **Two optimization loops.** The *fast inner loop* (thousands of iterations, e.g. flipping
  spins and measuring) is plain Python inside the backend / optimization engine and must
  never call an LLM per iteration. The *slow outer loop* (agents) chooses strategy and
  parameters between runs.
- **Hardware independence.** No device-specific code until the hardware milestone. Do not
  invent physics or lab-setup details. If something about the physical setup is needed,
  mark it as an open question for me.
- **Backends are swappable.** Agents depend only on the backend interface, never on
  simulation or hardware internals.
- **Device safety is enforced in code, not trusted to the LLM.** The Runner proposes
  commands; the Safety Validator checks every command against the Device Registry
  (allowed operations, ranges, units) before it reaches any backend. Out-of-range = reject
  and report, never clamp silently. Human approval for real hardware comes later.
- **Iteration limit.** The orchestrator always has a max-iterations guard.
- Keep it simple: no extra agents, frameworks or abstractions that the current milestone
  does not need. No FastAPI / PostgreSQL / vector DB until the roadmap reaches them.

## Known context (unconfirmed — do not hard-code)

The likely target is a spatial photonic Ising machine: laser → SLM (spins as 0/π phase
macro-pixels) → liquid crystal cell (voltage-tunable scattering medium, i.e. the
transmission matrix T) → camera. Ising energy ≈ −(intensity at chosen camera points),
with J_ij = Re Σ_m t_im t*_jm. Treat this as a hypothesis useful for the simulation
backend later, not as a confirmed requirement.

## Tooling conventions

- Python 3.12+, `uv` for environment and dependencies, `src/` layout.
- `pytest` for tests, `ruff` for lint + format, type hints everywhere.
- Commands: `uv run pytest`, `uv run ruff check .`, `uv run ruff format .`
- Secrets only in `.env` (never committed); `.env.example` documents the variables.
