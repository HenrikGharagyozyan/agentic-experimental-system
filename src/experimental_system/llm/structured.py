"""Helpers for structured output: JSON schema for prompts, JSON extraction, validation."""

import json
import re
from typing import Any

from pydantic import BaseModel, ValidationError

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def json_schema(model: type[BaseModel]) -> dict[str, Any]:
    return model.model_json_schema()


def schema_instruction(model: type[BaseModel]) -> str:
    """System-prompt suffix used by the text fallback (and as a hint in schema mode)."""
    schema = json.dumps(json_schema(model), ensure_ascii=False)
    return (
        "Answer with ONE JSON object only (no prose, no markdown) that validates against "
        f"this JSON schema of `{model.__name__}`. Do not add fields that are not in the "
        f"schema.\nJSON schema: {schema}"
    )


def extract_json(text: str) -> str:
    """Best-effort: the JSON object inside a reply (code fences / surrounding prose)."""
    fenced = _FENCE.search(text)
    if fenced:
        text = fenced.group(1)
    start = text.find("{")
    if start < 0:
        return text.strip()
    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
        elif ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return text[start:].strip()


def parse_reply[T: BaseModel](text: str, model: type[T]) -> T:
    """Validate a reply; raises ``ValueError`` with a message suitable for the LLM."""
    candidate = extract_json(text)
    try:
        return model.model_validate_json(candidate)
    except ValidationError as exc:
        errors = "; ".join(
            f"{'.'.join(str(p) for p in e['loc']) or '<root>'}: {e['msg']}" for e in exc.errors()
        )
        raise ValueError(f"the JSON does not match {model.__name__}: {errors}") from exc
