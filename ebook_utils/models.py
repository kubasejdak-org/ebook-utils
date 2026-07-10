from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


@dataclass
class EbookMetadata:
    title: str
    subtitle: str | None
    authors: list[str]
    edition: int | None = None
    edition_text: str | None = None
    isbns: list[str] = field(default_factory=list)


class MetadataField(str, Enum):
    TITLE = "title"
    AUTHORS = "authors"
    EDITION = "edition"
    ISBN = "isbn"


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True)
class MetadataEvidence:
    field: MetadataField
    value: str | list[str] | int
    source: str
    source_path: Path | None
    confidence: Confidence
    warnings: list[str] = field(default_factory=list)


@dataclass
class ExtractionResult:
    path: Path
    format: str
    metadata: EbookMetadata
    evidence: list[MetadataEvidence] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CanonicalMetadata:
    title: str
    authors: list[str]
    edition_text: str | None
    isbns: list[str]
    confidence: Confidence
    field_confidence: dict[MetadataField, Confidence] = field(default_factory=dict)
    field_reasons: dict[MetadataField, list[str]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


@dataclass
class EbookBundle:
    key: str
    files: list[Path]
    extractions: list[ExtractionResult]
    metadata: CanonicalMetadata


@dataclass(frozen=True)
class PlannedFileMove:
    source: Path
    target: Path


@dataclass
class PipelinePlan:
    root: Path
    bundles: list[EbookBundle]
    moves: list[PlannedFileMove]
    review_bundles: list[EbookBundle]
    skipped_bundles: list[EbookBundle] = field(default_factory=list)
    collisions: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AiSuggestion:
    title: str | None
    authors: list[str]
    edition_text: str | None
    confidence: Confidence
    reasoning: str
    raw: dict[str, Any] = field(default_factory=dict)
