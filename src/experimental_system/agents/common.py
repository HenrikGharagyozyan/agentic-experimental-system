"""Shared agent machinery: prompts, JSON context, "ask -> check in code -> retry"."""

import json
from collections.abc import Callable, Sequence
from importlib import resources
from typing import Any

from pydantic import BaseModel

from experimental_system.llm.base import ChatMessage, LLMClient


class AgentError(RuntimeError):
    """An agent could not produce output that passes the code checks."""


def load_prompt(name: str) -> str:
    """System prompt from ``experimental_system/prompts/<name>.md``."""
    return resources.files("experimental_system.prompts").joinpath(f"{name}.md").read_text("utf-8")


def to_jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {k: to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [to_jsonable(v) for v in value]
    return value


def context_message(payload: dict[str, Any]) -> str:
    """User message: the agent's whole context as one JSON document."""
    return json.dumps(to_jsonable(payload), ensure_ascii=False, indent=2)


def ask_checked[T: BaseModel](
    llm: LLMClient,
    *,
    agent: str,
    system: str,
    payload: dict[str, Any],
    response_model: type[T],
    check: Callable[[T], Sequence[str]],
    max_attempts: int = 3,
) -> T:
    """Ask the LLM, run deterministic checks, feed problems back, retry.

    The LLM never gets the last word: output that fails ``check`` is never returned.
    """
    messages = [
        ChatMessage(role="system", content=system),
        ChatMessage(role="user", content=context_message(payload)),
    ]
    problems: Sequence[str] = []
    for _ in range(max_attempts):
        result = llm.generate(messages, response_model)
        problems = check(result)
        if not problems:
            return result
        messages += [
            ChatMessage(role="assistant", content=result.model_dump_json()),
            ChatMessage(
                role="user",
                content=(
                    "Your answer was REJECTED by deterministic code checks:\n- "
                    + "\n- ".join(problems)
                    + "\nReturn a corrected, complete JSON object."
                ),
            ),
        ]
    raise AgentError(
        f"{agent}: output failed code checks after {max_attempts} attempts: {problems}"
    )
