from dataclasses import dataclass


@dataclass
class EbookMetadata:
    title: str
    subtitle: str | None
    authors: list[str]
    edition: int | None
