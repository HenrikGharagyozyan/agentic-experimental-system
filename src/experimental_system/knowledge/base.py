"""Knowledge Base interface: scientific retrieval for the Scientist agent only."""

from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from experimental_system.schemas.knowledge import KnowledgeFragment


@runtime_checkable
class KnowledgeBase(Protocol):
    """Search over scientific knowledge (papers, formulas, theory).

    Never a source of device parameters: those come only from the Device Registry.
    Planned implementations: InMemory (tests) and Pinecone (integrated embedding).
    """

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        filters: Mapping[str, str | int | float | bool] | None = None,
    ) -> list[KnowledgeFragment]:
        """Return up to ``top_k`` fragments, most relevant first."""
        ...
