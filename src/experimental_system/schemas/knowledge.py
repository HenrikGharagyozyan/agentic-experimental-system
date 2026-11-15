"""Knowledge Base retrieval results."""

from pydantic import Field

from experimental_system.schemas.common import Contract, NonEmptyStr

MetadataValue = str | int | float | bool | list[str]


class KnowledgeFragment(Contract):
    """One retrieved piece of scientific knowledge (paper excerpt, formula, theory note)."""

    fragment_id: NonEmptyStr
    text: NonEmptyStr
    source: NonEmptyStr  # title / DOI / URL
    score: float | None = None  # retrieval relevance, if the backend provides one
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)
