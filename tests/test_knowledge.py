"""Knowledge pack: card parsing/validation, deterministic rendering, size limit, repo cards."""

from pathlib import Path

import pytest

from experimental_system.knowledge import (
    CardDirectorySource,
    KnowledgePackError,
    KnowledgeSource,
    build_knowledge_pack,
    load_knowledge_pack,
    parse_card,
)

REPO = Path(__file__).resolve().parents[1]
CARDS = REPO / "data" / "knowledge" / "cards"

GOOD = """---
id: toy_card
title: Toy card
source: "Someone et al. 2020, Eq. 3"
tags: [toy]
---
Body with a formula E = T x.
"""


def _write(directory: Path, name: str, text: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(text, encoding="utf-8")


def test_parse_card() -> None:
    card = parse_card(GOOD, "toy.md")
    assert card.card_id == "toy_card" and card.tags == ["toy"] and card.file == "toy.md"
    assert card.body == "Body with a formula E = T x."


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("no front matter", "missing YAML front matter"),
        (GOOD.replace('source: "Someone et al. 2020, Eq. 3"\n', ""), "missing ['source']"),
        (GOOD.replace("id: toy_card", "id: Toy Card"), "card_id"),
        (GOOD.replace("tags: [toy]", "tags: [toy]\nauthor: me"), "unknown front matter keys"),
        (GOOD.replace("Body with a formula E = T x.\n", ""), "body"),
        (GOOD.replace("tags: [toy]", "tags: [toy"), "invalid YAML"),
    ],
)
def test_invalid_cards_fail_clearly(text: str, message: str) -> None:
    with pytest.raises(KnowledgePackError, match=message.replace("[", r"\[").replace("]", r"\]")):
        parse_card(text, "bad.md")


def test_duplicate_ids_rejected(tmp_path: Path) -> None:
    _write(tmp_path, "a.md", GOOD)
    _write(tmp_path, "b.md", GOOD)
    with pytest.raises(
        KnowledgePackError, match="duplicate card id 'toy_card' in 'a.md' and 'b.md'"
    ):
        load_knowledge_pack(CardDirectorySource(tmp_path), max_chars=10_000)


def test_missing_or_empty_directory(tmp_path: Path) -> None:
    with pytest.raises(KnowledgePackError, match="not found"):
        CardDirectorySource(tmp_path / "nope").cards()
    with pytest.raises(KnowledgePackError, match="no knowledge cards"):
        CardDirectorySource(tmp_path).cards()


def test_size_limit(tmp_path: Path) -> None:
    _write(tmp_path, "a.md", GOOD)
    pack = load_knowledge_pack(CardDirectorySource(tmp_path), max_chars=10_000)
    with pytest.raises(KnowledgePackError, match=rf"{len(pack.text)} characters, limit is 100"):
        load_knowledge_pack(CardDirectorySource(tmp_path), max_chars=100)


def test_pack_is_deterministic_and_sorted(tmp_path: Path) -> None:
    _write(tmp_path, "z.md", GOOD.replace("toy_card", "alpha_card"))
    _write(tmp_path, "a.md", GOOD)
    source = CardDirectorySource(tmp_path)
    assert isinstance(source, KnowledgeSource)
    first = load_knowledge_pack(source, max_chars=10_000)
    second = build_knowledge_pack(list(reversed(source.cards())))
    assert first.text == second.text and first.sha256 == second.sha256
    assert first.text.index("Card `alpha_card`") < first.text.index("Card `toy_card`")
    assert first.text.startswith("# Knowledge pack")
    assert "Source: Someone et al. 2020, Eq. 3" in first.text
    assert first.card_ids == {"alpha_card", "toy_card"}


def test_repository_cards_form_a_valid_pack() -> None:
    pack = load_knowledge_pack(CardDirectorySource(CARDS), max_chars=60_000)
    ids = pack.card_ids
    assert {
        "ising_energy_from_intensity",
        "coupling_matrix_from_tm",
        "ggs_transmission_matrix",
        "focusing_enhancement",
        "gerchberg_saxton",
    } <= ids
    for card in pack.cards:
        assert any(name in card.source for name in ("Delloye", "Huang", "Zhao")), card.card_id
