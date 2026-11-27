"""Build one LLM client per agent from settings (OpenRouter) or a scenario (FakeLLM)."""

from collections.abc import Callable, Mapping, Sequence
from typing import Any, Literal

from experimental_system.config import AGENT_NAMES, AgentName, ConfigError, Settings
from experimental_system.llm.base import LLMClient
from experimental_system.llm.fake import FakeLLM
from experimental_system.llm.openrouter import OpenAIChatTransport, OpenRouterClient
from experimental_system.llm.tracking import CallBudget, LoggedLLM

LLMKind = Literal["fake", "openrouter"]


def build_clients(
    kind: LLMKind,
    settings: Settings,
    *,
    sink: Callable[[dict[str, Any]], None],
    budget: CallBudget,
    fake_responses: Mapping[str, Sequence[Mapping[str, Any]]] | None = None,
) -> dict[AgentName, LLMClient]:
    clients: dict[AgentName, LLMClient] = {}
    transport: OpenAIChatTransport | None = None
    if kind == "openrouter":
        if settings.openrouter_api_key is None:
            raise ConfigError("OPENROUTER_API_KEY is not set (see .env.example)")
        transport = OpenAIChatTransport(
            api_key=settings.openrouter_api_key.get_secret_value(),
            base_url=settings.openrouter_base_url,
            timeout_s=settings.llm_timeout_s,
            temperature=settings.llm_temperature,
        )
    for agent in AGENT_NAMES:
        inner: LLMClient
        if kind == "fake":
            inner = FakeLLM(agent, (fake_responses or {}).get(agent, []))
            model = f"fake/{agent}"
        else:
            assert transport is not None
            model = settings.model_for(agent)
            inner = OpenRouterClient(
                model,
                transport,
                mode=settings.llm_structured_mode,
                max_attempts=settings.llm_max_attempts,
            )
        clients[agent] = LoggedLLM(inner, agent=agent, model=model, sink=sink, budget=budget)
    return clients
