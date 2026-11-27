"""Static knowledge: knowledge cards -> one "Knowledge pack" in the Scientist's prompt.

There is no retrieval: the whole (small) curated pack is given to the Scientist, so no
formula can be lost by a bad search. Cards live in ``data/knowledge/cards/*.md``:

    ---
    id: ggs_transmission_matrix          # snake_case, unique
    title: ...
    source: "Huang et al., Photonics Research 9(1), 34 (2021), Eqs. 1-4"
    tags: [ggs, phase retrieval]
    ---
    Markdown body ...

The pack text is deterministic (cards sorted by id), so the same cards always give the
same prompt (and the same sha256).
"""

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

import yaml
from pydantic import ValidationError

from experimental_system.schemas.knowledge import KnowledgeCard

_FRONT_MATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n(.*)\Z", re.DOTALL)
_REQUIRED = ("id", "title", "source")
_ALLOWED = {"id", "title", "source", "tags"}
DEFAULT_MAX_CHARS = 60_000


class KnowledgePackError(ValueError):
    """Invalid card or a knowledge pack that does not fit the configured limit."""


@runtime_checkable
class KnowledgeSource(Protocol):
    """Where knowledge cards come from (a directory now; anything else later)."""

    def cards(self) -> list[KnowledgeCard]: ...


def parse_card(text: str, file: str = "") -> KnowledgeCard:
    where = file or "<card>"
    match = _FRONT_MATTER.match(text)
    if match is None:
        raise KnowledgePackError(f"{where}: missing YAML front matter between '---' lines")
    try:
        meta = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError as exc:
        raise KnowledgePackError(f"{where}: invalid YAML front matter: {exc}") from exc
    if not isinstance(meta, dict):
        raise KnowledgePackError(f"{where}: front matter must be a mapping")
    missing = [k for k in _REQUIRED if not meta.get(k)]
    if missing:
        raise KnowledgePackError(f"{where}: front matter is missing {missing}")
    unknown = sorted(set(meta) - _ALLOWED)
    if unknown:
        raise KnowledgePackError(f"{where}: unknown front matter keys {unknown}")
    try:
        return KnowledgeCard(
            card_id=meta["id"],
            title=str(meta["title"]),
            source=str(meta["source"]),
            tags=[str(t) for t in meta.get("tags") or []],
            body=match.group(2).strip(),
            file=file,
        )
    except ValidationError as exc:
        problems = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
        raise KnowledgePackError(f"{where}: {problems}") from exc


class CardDirectorySource:
    """Implements ``KnowledgeSource``: every ``*.md`` file in a directory is one card."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def cards(self) -> list[KnowledgeCard]:
        if not self.directory.is_dir():
            raise KnowledgePackError(f"knowledge cards directory not found: {self.directory}")
        cards = [
            parse_card(path.read_text(encoding="utf-8"), path.name)
            for path in sorted(self.directory.glob("*.md"))
        ]
        if not cards:
            raise KnowledgePackError(f"no knowledge cards (*.md) in {self.directory}")
        return cards


@dataclass(frozen=True)
class KnowledgePack:
    cards: tuple[KnowledgeCard, ...]
    text: str  # exactly what is appended to the Scientist's system prompt

    @property
    def card_ids(self) -> frozenset[str]:
        return frozenset(c.card_id for c in self.cards)

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()


def render_card(card: KnowledgeCard) -> str:
    lines = [f"## Card `{card.card_id}` — {card.title}", "", f"Source: {card.source}"]
    if card.tags:
        lines.append(f"Tags: {', '.join(card.tags)}")
    lines += ["", card.body]
    return "\n".join(lines)


def build_knowledge_pack(
    cards: Sequence[KnowledgeCard], *, max_chars: int = DEFAULT_MAX_CHARS
) -> KnowledgePack:
    """Validate (unique ids) and render the pack; fail if it exceeds ``max_chars``."""
    seen: dict[str, str] = {}
    for card in cards:
        if card.card_id in seen:
            raise KnowledgePackError(
                f"duplicate card id {card.card_id!r} in {seen[card.card_id]!r} and {card.file!r}"
            )
        seen[card.card_id] = card.file
    ordered = tuple(sorted(cards, key=lambda c: c.card_id))
    header = (
        "# Knowledge pack\n\n"
        f"The {len(ordered)} knowledge cards below are your ONLY scientific references "
        "(human-curated summaries of the papers, with equation/section references). Cite "
        "the cards you rely on by their `card_id` in `citations`; never cite anything else. "
        "Lines marked 'Discrepancy' or 'Note' explain where our convention differs from "
        "the printed paper."
    )
    text = "\n\n---\n\n".join([header, *(render_card(c) for c in ordered)]) + "\n"
    if len(text) > max_chars:
        raise KnowledgePackError(
            f"knowledge pack is {len(text)} characters, limit is {max_chars} "
            f"(EXPSYS_KNOWLEDGE_PACK_MAX_CHARS); shorten or remove cards"
        )
    return KnowledgePack(cards=ordered, text=text)


def load_knowledge_pack(source: KnowledgeSource, *, max_chars: int) -> KnowledgePack:
    return build_knowledge_pack(source.cards(), max_chars=max_chars)
