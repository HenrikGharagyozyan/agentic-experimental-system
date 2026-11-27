"""Knowledge Base: ingestion, cards, BM25 search, Pinecone record mapping (fake index)."""

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pymupdf
import pytest

from experimental_system.config import Settings
from experimental_system.knowledge import InMemoryKnowledgeBase, KnowledgeBase
from experimental_system.knowledge.ingest import chunk_words, ingest, pdf_fragments
from experimental_system.knowledge.pinecone_kb import PineconeKnowledgeBase, to_record
from experimental_system.schemas import KnowledgeFragment

REPO = Path(__file__).resolve().parents[1]
CARDS = REPO / "data" / "knowledge" / "cards"
PAPERS = REPO / "data" / "papers"


def _make_pdf(path: Path) -> None:
    doc = pymupdf.open()  # type: ignore[no-untyped-call]  # pymupdf is partially typed
    for page_text in (
        "Front text about lasers.\n1. Introduction\n" + "light " * 300,
        "2. Methods\n" + "speckle intensity camera " * 200 + "\nReferences\n[1] Someone 2020",
    ):
        page = doc.new_page()
        page.insert_textbox(
            pymupdf.Rect(36, 36, 560, 800),  # type: ignore[no-untyped-call]
            page_text,
            fontsize=4,
        )
    doc.set_metadata({"title": "A Synthetic Test Paper About Speckle"})
    doc.save(path)  # type: ignore[no-untyped-call]
    doc.close()  # type: ignore[no-untyped-call]


def test_chunking_overlap() -> None:
    words = " ".join(f"w{i}" for i in range(1200))
    chunks = chunk_words(words, chunk_tokens=400, overlap_tokens=40)
    assert len(chunks) >= 3
    first, second = chunks[0].split(), chunks[1].split()
    assert first[-30:] == second[:30]  # 40 tokens * 0.75 = 30 words of overlap
    assert chunk_words("") == []


def test_pdf_ingestion_sections_pages_and_ids(tmp_path: Path) -> None:
    pdf = tmp_path / "Synthetic_Paper.pdf"
    _make_pdf(pdf)
    fragments = pdf_fragments(pdf)
    assert fragments
    assert all(f.fragment_id.startswith("synthetic_paper:p") for f in fragments)
    assert fragments[0].source == "A Synthetic Test Paper About Speckle"
    sections = {f.metadata["section"] for f in fragments}
    assert "1. Introduction" in sections and "2. Methods" in sections
    assert {f.metadata["page"] for f in fragments} == {1, 2}
    assert not any("Someone 2020" in f.text for f in fragments)  # references skipped
    assert [f.fragment_id for f in fragments] == [f.fragment_id for f in pdf_fragments(pdf)]


def test_cards_are_valid_and_cite_papers() -> None:
    fragments = ingest(None, CARDS)
    assert len(fragments) >= 8
    for f in fragments:
        assert f.fragment_id.startswith("card:")
        assert f.metadata["kind"] == "card"
        assert any(name in f.source for name in ("Delloye", "Huang", "Zhao"))


def test_bm25_search_ranks_relevant_card_first() -> None:
    kb = InMemoryKnowledgeBase(ingest(None, CARDS))
    assert isinstance(kb, KnowledgeBase)
    top = kb.search("retrieve transmission matrix gamma GGS", top_k=3)
    assert top[0].fragment_id == "card:ggs_transmission_matrix"
    assert top[0].score is not None and top[0].score > 0
    assert kb.search("enhancement", top_k=1)[0].fragment_id == "card:focusing_enhancement"
    assert kb.search("zzzz qqqq") == []
    only_cards = kb.search("ising", filters={"kind": "card"})
    assert only_cards and all(f.metadata["kind"] == "card" for f in only_cards)


def test_index_round_trip(tmp_path: Path) -> None:
    kb = InMemoryKnowledgeBase(ingest(None, CARDS))
    path = tmp_path / "index" / "fragments.jsonl"
    kb.save_jsonl(path)
    again = InMemoryKnowledgeBase.load_jsonl(path)
    assert len(again) == len(kb)
    assert again.search("replica overlap")[0].fragment_id == "card:replica_overlap"


@pytest.mark.skipif(not any(PAPERS.glob("*.pdf")), reason="papers are local-only (gitignored)")
def test_real_papers_ingest() -> None:
    fragments = ingest(PAPERS, CARDS)
    papers = {f.metadata.get("file") for f in fragments if f.metadata.get("kind") == "paper"}
    assert len(papers) == 3
    kb = InMemoryKnowledgeBase(fragments)
    hits = kb.search("Gerchberg Saxton transmission matrix adaptive parameter", top_k=5)
    assert any("Generalizing" in h.source or h.fragment_id.startswith("card:") for h in hits)


class FakeIndex:
    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    def upsert_records(self, *, records: list[dict[str, Any]], namespace: str) -> None:
        self.records += records

    def search(
        self,
        *,
        namespace: str,
        top_k: int | None = None,
        inputs: Mapping[str, Any] | None = None,
        filter: Mapping[str, Any] | None = None,
        fields: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        self.last_filter = filter
        hits = [
            {"id_": r["_id"], "score_": 0.9, "fields": {k: v for k, v in r.items() if k != "_id"}}
            for r in self.records[: top_k or 5]
        ]
        return {"result": {"hits": hits}}


def test_pinecone_mapping_with_fake_index() -> None:
    fragment = KnowledgeFragment(
        fragment_id="card:x", text="hello", source="Paper", metadata={"kind": "card", "page": 2}
    )
    record = to_record(fragment)
    assert record == {
        "_id": "card:x",
        "chunk_text": "hello",
        "source": "Paper",
        "kind": "card",
        "page": 2,
    }
    index = FakeIndex()
    kb = PineconeKnowledgeBase(index, "papers")
    assert isinstance(kb, KnowledgeBase)
    assert kb.upsert([fragment] * 200) == 200
    [hit] = kb.search("hello", top_k=1, filters={"kind": "card"})
    assert hit.fragment_id == "card:x" and hit.text == "hello" and hit.score == 0.9
    assert hit.metadata == {"kind": "card", "page": 2}
    assert index.last_filter == {"kind": {"$eq": "card"}}


@pytest.mark.live
def test_pinecone_live() -> None:
    settings = Settings()
    if not (settings.run_live and settings.pinecone_api_key and settings.pinecone_index):
        pytest.skip("needs EXPSYS_RUN_LIVE=1, PINECONE_API_KEY and PINECONE_INDEX")
    kb = PineconeKnowledgeBase.from_settings(settings)
    assert isinstance(kb.search("transmission matrix", top_k=3), list)
