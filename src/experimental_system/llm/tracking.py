"""Logging + call budget wrapper around any LLMClient."""

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from experimental_system.llm.base import ChatMessage, LLMClient, LLMError
from experimental_system.schemas.common import utc_now


class LLMBudgetExceededError(LLMError):
    """The run used up its LLM-call budget."""


@dataclass
class CallBudget:
    """Shared counter of agent LLM calls in one run (one ``generate`` = one call)."""

    limit: int
    used: int = 0

    def consume(self, agent: str) -> None:
        if self.used >= self.limit:
            raise LLMBudgetExceededError(
                f"LLM call budget exhausted: {self.used}/{self.limit} calls used "
                f"(next call by {agent!r}); raise EXPSYS_MAX_LLM_CALLS or simplify the task"
            )
        self.used += 1


class LoggedLLM:
    """Checks the budget, calls the inner client, appends one log entry per call."""

    def __init__(
        self,
        inner: LLMClient,
        *,
        agent: str,
        model: str,
        sink: Callable[[dict[str, Any]], None],
        budget: CallBudget,
    ) -> None:
        self._inner = inner
        self._agent = agent
        self._model = model
        self._sink = sink
        self._budget = budget

    def generate[T: BaseModel](self, messages: Sequence[ChatMessage], response_model: type[T]) -> T:
        self._budget.consume(self._agent)
        started = time.monotonic()
        entry: dict[str, Any] = {
            "timestamp": utc_now().isoformat(),
            "agent": self._agent,
            "model": self._model,
            "response_model": response_model.__name__,
            "call_number": self._budget.used,
        }
        try:
            result = self._inner.generate(messages, response_model)
            entry["ok"] = True
            return result
        except Exception as exc:
            entry["ok"] = False
            entry["error"] = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            entry["duration_s"] = round(time.monotonic() - started, 3)
            info = getattr(self._inner, "last_call", None)
            if info is not None:
                entry["attempts"] = info.attempts
                entry["mode"] = info.mode
                entry["prompt_tokens"] = info.prompt_tokens
                entry["completion_tokens"] = info.completion_tokens
            self._sink(entry)
