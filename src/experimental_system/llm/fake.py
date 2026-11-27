"""FakeLLM: scripted responses per agent, so the whole loop runs offline."""

from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, ValidationError

from experimental_system.llm.base import ChatMessage, StructuredOutputError


class FakeLLM:
    """``LLMClient`` that returns the next scripted response for its agent.

    Responses are plain dicts (e.g. from a scenario YAML) and go through the same Pydantic
    validation as real LLM output, so a broken scenario fails loudly.
    """

    def __init__(self, agent: str, responses: Sequence[Mapping[str, Any]]) -> None:
        self.agent = agent
        self.model = f"fake/{agent}"
        self._responses = list(responses)
        self.calls: list[list[ChatMessage]] = []  # what the agent sent, for tests

    @property
    def remaining(self) -> int:
        return len(self._responses)

    def generate[T: BaseModel](self, messages: Sequence[ChatMessage], response_model: type[T]) -> T:
        self.calls.append(list(messages))
        if not self._responses:
            raise StructuredOutputError(f"FakeLLM scenario for agent {self.agent!r} is exhausted")
        raw = self._responses.pop(0)
        try:
            return response_model.model_validate(raw)
        except ValidationError as exc:
            raise StructuredOutputError(
                f"scripted {self.agent} response is not a valid {response_model.__name__}: {exc}"
            ) from exc
