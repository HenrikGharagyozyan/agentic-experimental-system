"""PineconeKnowledgeBase: integrated-embedding index (Pinecone embeds the text server-side).

Index name, embedding model, cloud and region come only from settings. Records:
``{"_id": fragment_id, "chunk_text": text, "source": ..., <flat metadata>}``; the index is
created with ``field_map={"text": "chunk_text"}``.
"""

from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from experimental_system.config import ConfigError, Settings
from experimental_system.schemas.knowledge import KnowledgeFragment

TEXT_FIELD = "chunk_text"
UPSERT_BATCH = 96  # Pinecone limit for records with integrated embedding


class PineconeIndexLike(Protocol):
    """The two Index methods we use (a fake implements them in tests)."""

    def upsert_records(self, *, records: list[dict[str, Any]], namespace: str) -> Any: ...

    def search(
        self,
        *,
        namespace: str,
        top_k: int | None = None,
        inputs: Mapping[str, Any] | None = None,
        filter: Mapping[str, Any] | None = None,
        fields: Sequence[str] | None = None,
    ) -> Any: ...


def to_record(fragment: KnowledgeFragment) -> dict[str, Any]:
    record: dict[str, Any] = {"_id": fragment.fragment_id, TEXT_FIELD: fragment.text}
    record["source"] = fragment.source
    for key, value in fragment.metadata.items():
        if key not in record:
            record[key] = value
    return record


def from_hit(hit: Any) -> KnowledgeFragment:
    fields = dict(_get(hit, "fields") or {})
    text = str(fields.pop(TEXT_FIELD, "")) or "(empty)"
    source = str(fields.pop("source", "")) or "unknown"
    metadata = {k: v for k, v in fields.items() if isinstance(v, str | int | float | bool | list)}
    return KnowledgeFragment(
        fragment_id=str(_get(hit, "id_") or _get(hit, "_id") or _get(hit, "id")),
        text=text,
        source=source,
        score=float(_get(hit, "score_") or _get(hit, "_score") or 0.0),
        metadata=metadata,
    )


def _get(obj: Any, name: str) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(name)
    return getattr(obj, name, None)


class PineconeKnowledgeBase:
    """Implements ``KnowledgeBase`` on top of a Pinecone index."""

    def __init__(self, index: PineconeIndexLike, namespace: str) -> None:
        self._index = index
        self._namespace = namespace

    @classmethod
    def from_settings(cls, settings: Settings, *, create: bool = False) -> "PineconeKnowledgeBase":
        """Connect (and, if ``create``, create a missing integrated index)."""
        if settings.pinecone_api_key is None or not settings.pinecone_index:
            raise ConfigError("PINECONE_API_KEY and PINECONE_INDEX must be set (see .env.example)")
        from pinecone import Pinecone  # imported lazily: only needed for this backend

        pc = Pinecone(api_key=settings.pinecone_api_key.get_secret_value())
        name = settings.pinecone_index
        if not pc.has_index(name):
            if not create:
                raise ConfigError(f"Pinecone index {name!r} does not exist; run `expsys ingest`")
            if not settings.pinecone_embed_model:
                raise ConfigError("PINECONE_EMBED_MODEL must be set to create the index")
            pc.create_index_for_model(
                name=name,
                cloud=settings.pinecone_cloud,
                region=settings.pinecone_region,
                embed={"model": settings.pinecone_embed_model, "field_map": {"text": TEXT_FIELD}},
            )
        index: PineconeIndexLike = pc.Index(name)
        return cls(index, settings.pinecone_namespace)

    def upsert(self, fragments: Sequence[KnowledgeFragment]) -> int:
        records = [to_record(f) for f in fragments]
        for start in range(0, len(records), UPSERT_BATCH):
            self._index.upsert_records(
                records=records[start : start + UPSERT_BATCH], namespace=self._namespace
            )
        return len(records)

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        filters: Mapping[str, str | int | float | bool] | None = None,
    ) -> list[KnowledgeFragment]:
        pinecone_filter = {k: {"$eq": v} for k, v in filters.items()} if filters else None
        response = self._index.search(
            namespace=self._namespace,
            top_k=top_k,
            inputs={"text": query},
            filter=pinecone_filter,
        )
        result = _get(response, "result")
        hits = _get(result, "hits") or []
        return [from_hit(h) for h in hits]
