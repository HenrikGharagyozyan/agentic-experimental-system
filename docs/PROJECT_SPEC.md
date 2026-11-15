# Project: Agentic Experimental System

## 1. Project Objective

Develop a modular multi-agent system for autonomous scientific experimentation, analysis, and optimization.

The system should accept a scientific task, understand its mathematical formulation, plan an experiment, execute it in a selected environment, analyze the results, and iteratively optimize the experiment until the specified success criteria are met.

The eventual target is integration with a physical laboratory setup. However, the exact hardware configuration and experimental model are currently unknown.

**Critical requirement:** The initial architecture must be completely independent of specific laboratory devices.

Do not assume that any particular device, optical configuration, transformation matrix, or physical mechanism is already confirmed.

## 2. Core Architecture

The system consists of four LLM agents (Scientist, Experiment, Runner, Analyst) and one orchestrator:

### Orchestrator

Responsible for:

- Workflow management.
- Agent coordination and routing.
- Experiment state management.
- Iteration control.
- Error handling.
- Human approval.
- Final result aggregation.

Implement as a controlled state machine, preferably using LangGraph.

### Scientist Agent

Responsible for:

- Understanding scientific problems.
- Mathematical and physical reasoning.
- Formulating scientific specifications.
- Identifying assumptions and missing information.
- Retrieving scientific literature and documentation through a future Knowledge Base / RAG interface.
- Explaining scientific decisions.

Must not perform deterministic numerical computations using LLM-generated arithmetic.

### Experiment Agent

Responsible for:

- Converting scientific specifications into experiment plans.
- Planning execution steps.
- Selecting and using an execution backend.
- Executing experiments.
- Returning structured experiment results.

The Experiment Agent decides WHAT to run and WHICH devices are involved, at the level of
experiment steps ("calibrate", "set coupling medium", "run optimization", "capture").
It does not issue low-level device commands itself — it hands the plan to the Runner.

### Runner Agent

Responsible for:

- Knowing every available device: capabilities, parameters, allowed ranges, units,
  settle times, dependencies between devices (from a device registry, not from memory).
- Translating experiment steps into concrete, safe device commands.
- Checking device availability/health before execution.
- Executing commands through the execution backend and returning raw measurements.
- Reporting problems back (unknown parameter, out-of-range value, device error) instead of
  improvising.

Safety rule: the Runner LLM proposes commands, but a deterministic Safety Validator
(plain Python, using the device registry) checks every command before it reaches a
backend. An out-of-range value is rejected in code even if the LLM asks for it.

The execution backend supports two modes:

1. Simulation Backend.
2. Hardware Backend.

Both must implement a common backend interface. The Runner does not know which one is
active.

The Hardware Backend and MCP integration will be implemented later, after the laboratory equipment and existing MCP interfaces are understood.

### Analyst Agent

Responsible for:

- Analyzing experiment results.
- Interpreting measurements.
- Evaluating success criteria.
- Identifying invalid measurements and anomalies.
- Recommending whether another iteration is needed.
- Returning structured analysis.

Numerical calculations must be delegated to deterministic Python modules.

## 3. Non-Agent Components

### Optimization Engine

A deterministic Python module, not an LLM agent.

Its future responsibilities include:

- Selecting improved experiment parameters.
- Supporting optimization algorithms.
- Returning candidate configurations.
- Respecting parameter constraints.

Keep two optimization concepts separate:

- Scientific problem optimization, such as Ising energy minimization.
- Experimental or hardware parameter optimization.

Do not assume their exact relationship before the physical model is established.

### Scientific Core

Contains:

- Mathematical models.
- Numerical calculations.
- Metrics.
- Data processing.
- Validation.
- Scientific algorithms.

### Knowledge Base

A future retrieval interface for scientific papers, documentation, mathematical references, and laboratory knowledge.

Do not build a complex RAG system in the first milestone. Define a clean interface first.

### Storage

Persists:

- Experiment metadata.
- Experiment state.
- Iteration history.
- Input parameters.
- Measurements.
- Metrics.
- Logs.
- Final reports.

### LLM Provider Layer

Provides a unified interface for LLM providers. Agents must not be tightly coupled to one provider.

## 4. Technology Stack

Preferred initial stack:

- Python 3.12+
- LangGraph
- Pydantic v2
- NumPy
- SciPy
- pytest
- FastAPI (introduced when needed)
- SQLite initially
- PostgreSQL as a future option
- MCP for future hardware integration

Use asynchronous execution where it is beneficial, but avoid unnecessary complexity.

## 5. Architectural Principles

1. Hardware independence.
2. Simulation-first development.
3. Modular architecture.
4. Clear responsibility boundaries.
5. Structured communication between agents.
6. Pydantic schemas for inter-component contracts.
7. Deterministic numerical computation.
8. Reproducible experiments.
9. Explicit state management.
10. Validation of all experiment plans and execution parameters.
11. Controlled hardware access and human approval for sensitive operations.
12. Testability of every major component.

## 6. Development Roadmap

Implement incrementally:

1. Project foundation and configuration.
2. Common schemas and interfaces.
3. Scientific Core.
4. Simulation Backend.
5. Individual agents.
6. Orchestrator and state machine.
7. Optimization Engine.
8. Storage and persistence.
9. API and observability.
10. Hardware Backend and MCP integration.

The initial MVP must execute a complete experiment cycle in simulation:

Scientific task → Scientific specification → Experiment plan → Simulation → Numerical analysis → Optimization → Next iteration → Final report.

## 7. Important Development Rules

Do not generate the entire application in one response.

Work in small, verifiable milestones.

For every component:

1. Explain its purpose and responsibility.
2. Explain its interfaces and data contracts.
3. Propose the implementation.
4. Write the code only after the design is clear.
5. Explain important implementation decisions.
6. Add tests.
7. Run tests and fix errors.
8. Verify that the implementation respects the overall architecture.

Do not introduce speculative hardware abstractions or device-specific implementations.

Do not invent experimental physics or assumptions about the laboratory setup.

Do not add unnecessary agents or frameworks.

The developer must understand the architecture and code rather than blindly accepting generated implementations.

## 8. First Task

Start with **Milestone 1: Project Foundation**.

Do not implement the agents yet.

First:

- Propose the initial repository structure.
- Explain the responsibilities of the main directories.
- Set up Python project configuration.
- Configure dependencies and development tooling.
- Configure pytest.
- Add basic settings management.
- Establish initial coding conventions.

Then propose the first set of common Pydantic schemas and interfaces, but do not implement the entire system.

Wait for review and agreement before proceeding to the next milestone.
