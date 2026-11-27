"""Ingestion: PDF papers and knowledge cards -> KnowledgeFragments.

PDF -> page text (pymupdf) -> sections (heading heuristics) -> overlapping chunks of
~500-800 tokens -> fragments with metadata (paper, section, page). Fragment ids are
deterministic (``<paper_slug>:p<page>:c<chunk>``, ``card:<id>``), so re-ingesting updates
the same records and citations stay stable.
"""

import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

import pymupdf
import yaml

from experimental_system.schemas.knowledge import KnowledgeFragment

WORDS_PER_TOKEN = 0.75  # rough English average: 1 token ~ 0.75 words
CHUNK_TOKENS = 650
OVERLAP_TOKENS = 100

_SECTION_WORDS = (
    "abstract|introduction|methods?|results|discussions?|conclusions?|acknowledge?ments|"
    "references|funding|appendix|preliminaries|numerical methods|experimental setup"
)
# Numbered headings ("2.1. G-S Algorithm", "II. RESULTS") or well-known section names.
_HEADING = re.compile(
    r"^(?:(?:\d{1,2}(?:\.\d{1,2})*\.?|[IVX]{1,4}\.)\s+[A-Z][A-Za-z0-9 ,:;()\-–'’]{2,80}"
    rf"|(?i:(?:{_SECTION_WORDS})\.?))$"
)
_SKIPPED_SECTIONS = re.compile(r"(?i)\b(references|acknowledge?ments|funding|disclosures)\b")
_JUNK_TITLES = {"", "article", "untitled", "paper", "manuscript"}
_SLUG = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class PageText:
    page: int  # 1-based
    text: str


def slugify(text: str, max_length: int = 40) -> str:
    return _SLUG.sub("_", text.lower()).strip("_")[:max_length].strip("_") or "doc"


def read_pdf(path: Path) -> tuple[str, list[PageText]]:
    """(title, pages). Title from PDF metadata, else the file name."""
    with pymupdf.open(path) as doc:  # type: ignore[no-untyped-call]
        meta_title = (doc.metadata or {}).get("title") or ""
        pages = [PageText(i + 1, page.get_text("text")) for i, page in enumerate(doc)]
    title = meta_title.strip()
    if title.lower() in _JUNK_TITLES or len(title) < 15:
        title = path.stem.replace("_", " ")
    return title, pages


def _sections(pages: Iterable[PageText]) -> Iterator[tuple[str, int, str]]:
    """Yield (section, start_page, text) blocks, split at detected headings."""
    section, start = "Front matter", 1
    lines: list[str] = []
    for page in pages:
        for raw in page.text.splitlines():
            line = raw.strip()
            if not line:
                continue
            if _HEADING.match(line) and len(line.split()) <= 10:
                if lines:
                    yield section, start, " ".join(lines)
                section, start, lines = line, page.page, []
                continue
            if not lines:
                start = page.page
            lines.append(line)
    if lines:
        yield section, start, " ".join(lines)


def chunk_words(
    text: str, chunk_tokens: int = CHUNK_TOKENS, overlap_tokens: int = OVERLAP_TOKENS
) -> list[str]:
    """Split into overlapping windows of ~chunk_tokens tokens (word-based estimate)."""
    words = text.split()
    size = max(1, int(chunk_tokens * WORDS_PER_TOKEN))
    overlap = min(size - 1, int(overlap_tokens * WORDS_PER_TOKEN))
    if len(words) <= size:
        return [" ".join(words)] if words else []
    chunks, start = [], 0
    while start < len(words):
        chunks.append(" ".join(words[start : start + size]))
        if start + size >= len(words):
            break
        start += size - overlap
    return chunks


def pdf_fragments(path: Path) -> list[KnowledgeFragment]:
    title, pages = read_pdf(path)
    slug = slugify(path.stem)
    fragments: list[KnowledgeFragment] = []
    counters: dict[int, int] = {}
    blocks = [b for b in _sections(pages) if not _SKIPPED_SECTIONS.search(b[0])]
    # Merge very short sections into the following one so that chunks are not tiny; the
    # merged block keeps the name/page of its longest part.
    merged: list[tuple[str, int, str]] = []
    group: list[tuple[str, int, str]] = []
    for block in blocks:
        group.append(block)
        if sum(len(b[2].split()) for b in group) >= 80:
            main = max(group, key=lambda b: len(b[2].split()))
            merged.append((main[0], group[0][1], " ".join(b[2] for b in group)))
            group = []
    if group:
        main = max(group, key=lambda b: len(b[2].split()))
        merged.append((main[0], group[0][1], " ".join(b[2] for b in group)))
    for section, page, text in merged:
        for chunk in chunk_words(text):
            index = counters.get(page, 0)
            counters[page] = index + 1
            fragments.append(
                KnowledgeFragment(
                    fragment_id=f"{slug}:p{page}:c{index}",
                    text=chunk,
                    source=title,
                    metadata={
                        "kind": "paper",
                        "paper": title,
                        "file": path.name,
                        "section": section[:120],
                        "page": page,
                    },
                )
            )
    return fragments


def card_fragment(path: Path) -> KnowledgeFragment:
    """A knowledge card: markdown with YAML front matter (id, title, source, tags)."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError(f"{path}: missing YAML front matter")
    _, front, body = text.split("---", 2)
    meta = yaml.safe_load(front) or {}
    for key in ("id", "title", "source"):
        if not meta.get(key):
            raise ValueError(f"{path}: front matter needs {key!r}")
    tags = [str(t) for t in meta.get("tags", [])]
    return KnowledgeFragment(
        fragment_id=f"card:{meta['id']}",
        text=f"{meta['title']}\n\n{body.strip()}",
        source=str(meta["source"]),
        metadata={"kind": "card", "title": str(meta["title"]), "tags": tags, "file": path.name},
    )


def ingest(papers_dir: Path | None, cards_dir: Path | None) -> list[KnowledgeFragment]:
    """All fragments from ``papers_dir/*.pdf`` and ``cards_dir/*.md`` (sorted, stable)."""
    fragments: list[KnowledgeFragment] = []
    if cards_dir is not None and cards_dir.is_dir():
        fragments += [card_fragment(p) for p in sorted(cards_dir.glob("*.md"))]
    if papers_dir is not None and papers_dir.is_dir():
        for pdf in sorted(papers_dir.glob("*.pdf")):
            fragments += pdf_fragments(pdf)
    ids = [f.fragment_id for f in fragments]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate fragment ids during ingestion")
    return fragments
