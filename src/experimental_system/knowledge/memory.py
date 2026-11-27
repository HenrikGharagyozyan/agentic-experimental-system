"""InMemoryKnowledgeBase: BM25 lexical search (tests, offline demos)."""

import json
import math
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path

from experimental_system.schemas.knowledge import KnowledgeFragment

_TOKEN = re.compile(r"[a-z0-9]+")
_STOP = frozenset(
    "a an and are as at be by for from in is it of on or that the this to with we our be "
    "can which using use used".split()
)


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOP and len(t) > 1]


class InMemoryKnowledgeBase:
    """Implements ``KnowledgeBase`` with Okapi BM25 over fragment text + metadata."""

    def __init__(self, fragments: Sequence[KnowledgeFragment], k1: float = 1.5, b: float = 0.75):
        self._fragments = list(fragments)
        self._k1, self._b = k1, b
        self._docs = [Counter(tokenize(self._indexed_text(f))) for f in self._fragments]
        self._lengths = [sum(d.values()) for d in self._docs]
        self._avg = (sum(self._lengths) / len(self._lengths)) if self._lengths else 0.0
        df: Counter[str] = Counter()
        for doc in self._docs:
            df.update(doc.keys())
        n = len(self._docs)
        self._idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}

    @staticmethod
    def _indexed_text(f: KnowledgeFragment) -> str:
        extra = " ".join(str(v) for k, v in f.metadata.items() if k in ("title", "section", "tags"))
        return f"{f.text} {extra}"

    def __len__(self) -> int:
        return len(self._fragments)

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        filters: Mapping[str, str | int | float | bool] | None = None,
    ) -> list[KnowledgeFragment]:
        terms = tokenize(query)
        scored: list[tuple[float, int]] = []
        for i, (frag, doc) in enumerate(zip(self._fragments, self._docs, strict=True)):
            if filters and any(frag.metadata.get(k) != v for k, v in filters.items()):
                continue
            score = 0.0
            norm = self._k1 * (1 - self._b + self._b * self._lengths[i] / (self._avg or 1.0))
            for term in terms:
                tf = doc.get(term, 0)
                if tf:
                    score += self._idf[term] * tf * (self._k1 + 1) / (tf + norm)
            if score > 0:
                scored.append((score, i))
        scored.sort(key=lambda x: (-x[0], x[1]))
        return [
            self._fragments[i].model_copy(update={"score": round(s, 4)}) for s, i in scored[:top_k]
        ]

    # --- persistence of the local index -------------------------------------------------------

    def save_jsonl(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for frag in self._fragments:
                f.write(frag.model_dump_json() + "\n")

    @classmethod
    def load_jsonl(cls, path: Path) -> "InMemoryKnowledgeBase":
        lines = path.read_text(encoding="utf-8").splitlines()
        return cls([KnowledgeFragment.model_validate(json.loads(line)) for line in lines if line])
