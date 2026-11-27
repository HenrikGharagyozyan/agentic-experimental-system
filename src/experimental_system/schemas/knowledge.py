"""Scientific knowledge given to the Scientist: curated knowledge cards."""

from pydantic import Field

from experimental_system.schemas.common import Contract, Identifier, NonEmptyStr


class KnowledgeCard(Contract):
    """One human-curated card (formula, algorithm, theory note) with its literature source.

    Cards are the only scientific references of the Scientist; they never contain device
    parameters (those come only from the Device Registry).
    """

    card_id: Identifier
    title: NonEmptyStr
    source: NonEmptyStr  # paper + equation / section
    tags: list[str] = Field(default_factory=list)
    body: NonEmptyStr
    file: str = ""  # file name the card was loaded from (for error messages)
