"""LLM layer: structured output with fallback and retries, FakeLLM, logging, budget."""

import json
from typing import Any

import pytest
from pydantic import BaseModel

from experimental_system.config import ConfigError, Settings
from experimental_system.llm import (
    CallBudget,
    ChatMessage,
    FakeLLM,
    LLMBudgetExceededError,
    LLMClient,
    LoggedLLM,
    StructuredOutputError,
)
from experimental_system.llm.factory import build_clients
from experimental_system.llm.openrouter import (
    Completion,
    OpenRouterClient,
    SchemaUnsupportedError,
)
from experimental_system.llm.structured import extract_json, parse_reply
from experimental_system.schemas import AnalysisReport, Decision


class Answer(BaseModel):
    value: int
    label: str


class ScriptedTransport:
    """Returns scripted texts; can reject response_format like a model without support."""

    def __init__(self, texts: list[str], *, reject_schema: bool = False) -> None:
        self.texts = texts
        self.reject_schema = reject_schema
        self.requests: list[dict[str, Any]] = []

    def complete(
        self, *, model: str, messages: list[dict[str, str]], response_format: dict[str, Any] | None
    ) -> Completion:
        self.requests.append(
            {"model": model, "messages": list(messages), "response_format": response_format}
        )
        if response_format is not None and self.reject_schema:
            raise SchemaUnsupportedError("response_format not supported")
        return Completion(self.texts.pop(0), prompt_tokens=10, completion_tokens=5)


MSG = [ChatMessage(role="user", content="give me an answer")]


def test_extract_json_from_fences_and_prose() -> None:
    assert extract_json('Sure!\n```json\n{"a": {"b": "}"}}\n```') == '{"a": {"b": "}"}}'
    assert extract_json('Result: {"value": 1} done') == '{"value": 1}'


def test_parse_reply_error_message_is_llm_friendly() -> None:
    with pytest.raises(ValueError, match="value"):
        parse_reply('{"label": "x"}', Answer)


def test_json_schema_mode_success() -> None:
    transport = ScriptedTransport(['{"value": 3, "label": "ok"}'])
    client = OpenRouterClient("some/model", transport)
    assert client.generate(MSG, Answer) == Answer(value=3, label="ok")
    request = transport.requests[0]
    assert request["response_format"]["type"] == "json_schema"
    assert request["messages"][0]["role"] == "system"  # schema instruction prepended
    assert client.last_call is not None and client.last_call.attempts == 1


def test_retry_with_validation_error_text() -> None:
    transport = ScriptedTransport(['{"value": "x"}', '{"value": 4, "label": "fixed"}'])
    client = OpenRouterClient("m", transport, mode="text")
    assert client.generate(MSG, Answer).value == 4
    retry_messages = transport.requests[1]["messages"]
    assert retry_messages[-1]["role"] == "user"
    assert "invalid" in retry_messages[-1]["content"]
    assert transport.requests[1]["response_format"] is None
    assert client.last_call is not None
    assert client.last_call.attempts == 2 and client.last_call.prompt_tokens == 20


def test_gives_up_after_max_attempts() -> None:
    transport = ScriptedTransport(["nope", "still no", "{}"])
    client = OpenRouterClient("m", transport, max_attempts=3)
    with pytest.raises(StructuredOutputError, match="3 attempts"):
        client.generate(MSG, Answer)


def test_auto_mode_falls_back_to_text_and_remembers() -> None:
    transport = ScriptedTransport(
        ['{"value": 1, "label": "a"}', '{"value": 2, "label": "b"}'], reject_schema=True
    )
    client = OpenRouterClient("m", transport, mode="auto")
    assert client.generate(MSG, Answer).value == 1
    assert client.generate(MSG, Answer).value == 2
    formats = [r["response_format"] is not None for r in transport.requests]
    assert formats == [True, False, False]  # schema tried once, then text only


def test_strict_json_schema_mode_does_not_fall_back() -> None:
    transport = ScriptedTransport([], reject_schema=True)
    client = OpenRouterClient("m", transport, mode="json_schema")
    with pytest.raises(SchemaUnsupportedError):
        client.generate(MSG, Answer)


def test_fake_llm_scripted_and_validated() -> None:
    fake = FakeLLM("analyst", [{"decision": "DONE", "rationale": "ok"}, {"decision": "MAYBE"}])
    assert isinstance(fake, LLMClient)
    assert fake.generate(MSG, AnalysisReport).decision is Decision.DONE
    with pytest.raises(StructuredOutputError, match="not a valid"):
        fake.generate(MSG, AnalysisReport)
    with pytest.raises(StructuredOutputError, match="exhausted"):
        fake.generate(MSG, AnalysisReport)
    assert len(fake.calls) == 3


def test_logged_llm_writes_entries_and_enforces_budget() -> None:
    entries: list[dict[str, Any]] = []
    budget = CallBudget(limit=2)
    inner = OpenRouterClient("m", ScriptedTransport(['{"value": 1, "label": "a"}'] * 2))
    llm = LoggedLLM(inner, agent="runner", model="m", sink=entries.append, budget=budget)
    llm.generate(MSG, Answer)
    llm.generate(MSG, Answer)
    with pytest.raises(LLMBudgetExceededError, match="2/2"):
        llm.generate(MSG, Answer)
    assert [e["ok"] for e in entries] == [True, True]
    assert entries[0]["agent"] == "runner" and entries[0]["prompt_tokens"] == 10
    json.dumps(entries)  # serialisable for llm_calls.jsonl


def test_logged_llm_logs_failures() -> None:
    entries: list[dict[str, Any]] = []
    llm = LoggedLLM(
        FakeLLM("scientist", []),
        agent="scientist",
        model="fake",
        sink=entries.append,
        budget=CallBudget(limit=5),
    )
    with pytest.raises(StructuredOutputError):
        llm.generate(MSG, Answer)
    assert entries[0]["ok"] is False and "exhausted" in entries[0]["error"]


def test_model_per_agent_with_default() -> None:
    settings = Settings(_env_file=None, default_model="vendor/default", runner_model="vendor/r")
    assert settings.model_for("runner") == "vendor/r"
    assert settings.model_for("analyst") == "vendor/default"
    with pytest.raises(ConfigError, match="DEFAULT_MODEL"):
        Settings(_env_file=None).model_for("scientist")


def test_factory_fake_and_missing_key() -> None:
    settings = Settings(_env_file=None)
    clients = build_clients(
        "fake",
        settings,
        sink=lambda e: None,
        budget=CallBudget(10),
        fake_responses={"analyst": [{"decision": "ABORT", "rationale": "x"}]},
    )
    assert set(clients) == {"scientist", "experiment", "runner", "analyst"}
    assert clients["analyst"].generate(MSG, AnalysisReport).decision is Decision.ABORT
    with pytest.raises(ConfigError, match="OPENROUTER_API_KEY"):
        build_clients("openrouter", settings, sink=lambda e: None, budget=CallBudget(1))


@pytest.mark.live
def test_openrouter_live() -> None:
    settings = Settings()
    if not (settings.run_live and settings.openrouter_api_key and settings.default_model):
        pytest.skip("needs EXPSYS_RUN_LIVE=1, OPENROUTER_API_KEY and DEFAULT_MODEL")
    clients = build_clients("openrouter", settings, sink=lambda e: None, budget=CallBudget(2))
    answer = clients["analyst"].generate(
        [ChatMessage(role="user", content="Return value 7 and label 'seven'.")], Answer
    )
    assert answer.value == 7


def test_empty_env_values_mean_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """`KEY=` lines copied from .env.example must not become empty secrets/models."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    monkeypatch.setenv("DEFAULT_MODEL", " ")
    settings = Settings(_env_file=None)
    assert settings.openrouter_api_key is None and settings.default_model is None
