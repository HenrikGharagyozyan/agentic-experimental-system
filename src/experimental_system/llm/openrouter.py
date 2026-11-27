"""OpenRouter adapter (OpenAI-compatible Chat Completions API via the ``openai`` package).

Structured output strategy (provider-agnostic, works with models without native support):
1. ``json_schema`` mode: send ``response_format={"type": "json_schema", ...}``;
2. if the provider rejects it (HTTP 400), switch this client to ``text`` mode: ask for
   JSON in the prompt;
3. in both modes: validate with Pydantic; on failure retry with the validation error text
   (up to ``max_attempts``), then raise ``StructuredOutputError``.

TODO(later): tool-calling mode for models that support tools but not response_format.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

import openai
from pydantic import BaseModel

from experimental_system.config import StructuredMode
from experimental_system.llm.base import ChatMessage, LLMError, StructuredOutputError
from experimental_system.llm.structured import json_schema, parse_reply, schema_instruction


class SchemaUnsupportedError(LLMError):
    """The provider/model rejected the response_format parameter."""


@dataclass(frozen=True)
class Completion:
    text: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


@dataclass(frozen=True)
class CallInfo:
    """Details of the last ``generate`` call (read by the logging wrapper)."""

    attempts: int
    mode: str
    prompt_tokens: int | None
    completion_tokens: int | None


class ChatTransport(Protocol):
    """The one provider call we need. A fake transport is used in tests."""

    def complete(
        self, *, model: str, messages: list[dict[str, str]], response_format: dict[str, Any] | None
    ) -> Completion: ...


class OpenAIChatTransport:
    """Real transport: ``openai.OpenAI(base_url=...)`` -> chat.completions.create."""

    def __init__(
        self, *, api_key: str, base_url: str, timeout_s: float, temperature: float
    ) -> None:
        self._client = openai.OpenAI(api_key=api_key, base_url=base_url, timeout=timeout_s)
        self._temperature = temperature

    def complete(
        self, *, model: str, messages: list[dict[str, str]], response_format: dict[str, Any] | None
    ) -> Completion:
        kwargs: dict[str, Any] = {"temperature": self._temperature}
        if response_format is not None:
            kwargs["response_format"] = response_format
        try:
            response = self._client.chat.completions.create(
                model=model,
                messages=messages,  # type: ignore[arg-type]
                **kwargs,
            )
        except openai.BadRequestError as exc:
            if response_format is not None:
                raise SchemaUnsupportedError(str(exc)) from exc
            raise LLMError(f"provider rejected the request: {exc}") from exc
        except openai.OpenAIError as exc:
            raise LLMError(f"LLM provider error: {exc}") from exc
        if not response.choices:
            raise LLMError("provider returned no choices")
        text = response.choices[0].message.content or ""
        usage = response.usage
        return Completion(
            text=text,
            prompt_tokens=usage.prompt_tokens if usage else None,
            completion_tokens=usage.completion_tokens if usage else None,
        )


class OpenRouterClient:
    """``LLMClient`` bound to one model."""

    def __init__(
        self,
        model: str,
        transport: ChatTransport,
        *,
        mode: StructuredMode = "auto",
        max_attempts: int = 3,
    ) -> None:
        self.model = model
        self._transport = transport
        self._mode = mode
        self._schema_supported = mode != "text"
        self._max_attempts = max_attempts
        self.last_call: CallInfo | None = None

    def generate[T: BaseModel](self, messages: Sequence[ChatMessage], response_model: type[T]) -> T:
        history = [{"role": m.role, "content": m.content} for m in messages]
        history.insert(0, {"role": "system", "content": schema_instruction(response_model)})
        prompt_tokens = completion_tokens = 0
        last_error = "no attempt made"
        for attempt in range(1, self._max_attempts + 1):
            completion, mode = self._complete(history, response_model)
            prompt_tokens += completion.prompt_tokens or 0
            completion_tokens += completion.completion_tokens or 0
            try:
                result = parse_reply(completion.text, response_model)
            except ValueError as exc:
                last_error = str(exc)
                history.append({"role": "assistant", "content": completion.text})
                history.append(
                    {
                        "role": "user",
                        "content": (
                            f"Your previous answer was invalid: {last_error}\n"
                            "Return the corrected JSON object only."
                        ),
                    }
                )
                continue
            self.last_call = CallInfo(attempt, mode, prompt_tokens, completion_tokens)
            return result
        self.last_call = CallInfo(self._max_attempts, mode, prompt_tokens, completion_tokens)
        raise StructuredOutputError(
            f"{self.model} gave no valid {response_model.__name__} after "
            f"{self._max_attempts} attempts; last error: {last_error}"
        )

    def _complete(
        self, history: list[dict[str, str]], response_model: type[BaseModel]
    ) -> tuple[Completion, str]:
        if self._schema_supported:
            response_format = {
                "type": "json_schema",
                "json_schema": {
                    "name": response_model.__name__,
                    "schema": json_schema(response_model),
                    "strict": False,
                },
            }
            try:
                return (
                    self._transport.complete(
                        model=self.model, messages=history, response_format=response_format
                    ),
                    "json_schema",
                )
            except SchemaUnsupportedError:
                if self._mode == "json_schema":
                    raise
                self._schema_supported = False  # remember for the rest of the run
        return (
            self._transport.complete(model=self.model, messages=history, response_format=None),
            "text",
        )
