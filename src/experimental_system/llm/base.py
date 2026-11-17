"""Provider-agnostic LLM interface: request -> validated Pydantic object."""

from collections.abc import Sequence
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict


class ChatMessage(BaseModel):
    """One message of a chat-style LLM request."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    role: Literal["system", "user", "assistant"]
    content: str


class LLMError(Exception):
    """Base error of the LLM provider layer (network, auth, provider errors)."""


class StructuredOutputError(LLMError):
    """The model did not produce a valid ``response_model`` even after retries."""


@runtime_checkable
class LLMClient(Protocol):
    """Any LLM backend (OpenRouter adapter, FakeLLM, ...).

    An instance is bound to one model; per-agent clients are created from settings.
    Implementations may use native structured output / tool calling, or the fallback:
    JSON in text -> Pydantic validation -> retry with the validation error text.
    """

    def generate[T: BaseModel](self, messages: Sequence[ChatMessage], response_model: type[T]) -> T:
        """Return a validated instance of ``response_model``.

        Raises:
            StructuredOutputError: if no valid object could be obtained.
            LLMError: on provider / transport failures.
        """
        ...
