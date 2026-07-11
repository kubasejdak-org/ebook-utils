import json
import shutil
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Iterable

from .extractor import extract_result
from .models import (
    CanonicalMetadata,
    Confidence,
    EbookBundle,
    ExtractionResult,
    MetadataEvidence,
    MetadataField,
    PipelinePlan,
    PlannedFileMove,
)
from .naming import canonical_name, extract_edition_number, format_edition, normalize_key

SUPPORTED_EXTENSIONS = {".epub", ".pdf"}
CONFIDENCE_RANK = {Confidence.LOW: 1, Confidence.MEDIUM: 2, Confidence.HIGH: 3}
SOURCE_RANK = {"epub": 3, "pdf": 2, "filename": 1}


def iter_ebook_files(root: Path, *, exclude: Path | None = None) -> list[Path]:
    if not root.exists():
        raise FileNotFoundError(f"Input path does not exist: {root}")
    if root.is_file():
        return [root] if root.suffix.lower() in SUPPORTED_EXTENSIONS else []
    excluded_root = exclude.resolve() if exclude and exclude.exists() else None
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
        and path.suffix.lower() in SUPPORTED_EXTENSIONS
        and not any(part.startswith(".") for part in path.parts)
        and not (excluded_root and path.is_relative_to(excluded_root))
    )


def _evidence_score(evidence: MetadataEvidence) -> tuple[int, int, int]:
    value_len = len(evidence.value) if isinstance(evidence.value, list) else len(str(evidence.value))
    return (SOURCE_RANK.get(evidence.source, 0), CONFIDENCE_RANK[evidence.confidence], value_len)


def _best_evidence(extractions: Iterable[ExtractionResult], field: MetadataField) -> MetadataEvidence | None:
    candidates = [evidence for extraction in extractions for evidence in extraction.evidence if evidence.field == field]
    return max(candidates, key=_evidence_score) if candidates else None


def _evidence_key(evidence: MetadataEvidence) -> str:
    if evidence.field == MetadataField.AUTHORS and isinstance(evidence.value, list):
        return "|".join(sorted(normalize_key(author) for author in evidence.value if author.strip()))
    if evidence.field == MetadataField.ISBN and isinstance(evidence.value, list):
        return "|".join(sorted(str(value) for value in evidence.value))
    if evidence.field == MetadataField.EDITION:
        raw = str(evidence.value)
        edition = format_edition(
            int(evidence.value) if isinstance(evidence.value, int) else extract_edition_number(raw), raw
        )
        return normalize_key(edition or "")
    return normalize_key(str(evidence.value))


def _field_assessment(
    extractions: Iterable[ExtractionResult], field: MetadataField, selected: MetadataEvidence | None
) -> tuple[Confidence, list[str]]:
    if selected is None or not _evidence_key(selected):
        return Confidence.LOW, [f"No {field.value} evidence found."]

    usable = [
        evidence
        for extraction in extractions
        for evidence in extraction.evidence
        if evidence.field == field and evidence.confidence != Confidence.LOW and _evidence_key(evidence)
    ]
    selected_key = _evidence_key(selected)
    conflicting = sorted({_evidence_key(evidence) for evidence in usable if _evidence_key(evidence) != selected_key})
    if conflicting:
        return Confidence.LOW, [
            f"Conflicting {field.value} evidence from reliable sources: "
            f"selected '{selected_key}', also found {', '.join(conflicting)}."
        ]

    supporting = [evidence for evidence in usable if _evidence_key(evidence) == selected_key]
    source_kinds = {evidence.source for evidence in supporting}
    source_files = {evidence.source_path for evidence in supporting if evidence.source_path}
    if len(source_kinds) >= 2 or (selected.source != "filename" and len(source_files) >= 2):
        return Confidence.HIGH, [f"Confirmed by {len(source_kinds)} source type(s) across {len(source_files)} file(s)."]
    if selected.confidence == Confidence.HIGH:
        return Confidence.MEDIUM, [f"Only one reliable {selected.source} source supports this field."]
    return selected.confidence, [f"Based only on {selected.source} evidence."]


def _isbn_assessment(extractions: Iterable[ExtractionResult]) -> tuple[list[str], Confidence, list[str]]:
    evidence = [
        item
        for extraction in extractions
        for item in extraction.evidence
        if item.field == MetadataField.ISBN and isinstance(item.value, list)
    ]
    isbns = sorted({str(value) for item in evidence for value in item.value})
    if not isbns:
        return [], Confidence.LOW, ["No valid ISBN found."]
    source_files = {item.source_path for item in evidence if item.source_path}
    source_kinds = {item.source for item in evidence}
    if len(source_files) >= 2 or len(source_kinds) >= 2:
        return isbns, Confidence.HIGH, ["Valid ISBN is present in more than one source."]
    return isbns, Confidence.MEDIUM, ["Valid ISBN found in one file; it has not been corroborated."]


def _merge_metadata(extractions: list[ExtractionResult]) -> CanonicalMetadata:
    warnings = [warning for extraction in extractions for warning in extraction.warnings]
    title_evidence = _best_evidence(extractions, MetadataField.TITLE)
    authors_evidence = _best_evidence(extractions, MetadataField.AUTHORS)
    edition_evidence = _best_evidence(extractions, MetadataField.EDITION)

    title = str(title_evidence.value).strip() if title_evidence else ""
    authors = list(authors_evidence.value) if authors_evidence and isinstance(authors_evidence.value, list) else []
    raw_edition = str(edition_evidence.value).strip() if edition_evidence else None
    edition_text = format_edition(
        int(edition_evidence.value) if edition_evidence and isinstance(edition_evidence.value, int) else extract_edition_number(raw_edition or ""),
        raw_edition,
    )
    isbns, isbn_confidence, isbn_reasons = _isbn_assessment(extractions)

    field_confidence: dict[MetadataField, Confidence] = {}
    field_reasons: dict[MetadataField, list[str]] = {}
    for field, selected in (
        (MetadataField.TITLE, title_evidence),
        (MetadataField.AUTHORS, authors_evidence),
        (MetadataField.EDITION, edition_evidence),
    ):
        confidence, reasons = _field_assessment(extractions, field, selected)
        field_confidence[field] = confidence
        field_reasons[field] = reasons
    field_confidence[MetadataField.ISBN] = isbn_confidence
    field_reasons[MetadataField.ISBN] = isbn_reasons

    if not title:
        title = extractions[0].path.stem
        warnings.append("No title evidence found; using the filename stem for display only.")
    if not authors:
        warnings.append("No author evidence found; this bundle cannot receive a canonical name.")
    for field in (MetadataField.TITLE, MetadataField.AUTHORS):
        if field_confidence[field] == Confidence.LOW:
            warnings.extend(field_reasons[field])
    if edition_evidence and field_confidence[MetadataField.EDITION] == Confidence.LOW:
        warnings.extend(field_reasons[MetadataField.EDITION])

    title_confidence = field_confidence[MetadataField.TITLE]
    authors_confidence = field_confidence[MetadataField.AUTHORS]
    if not title or not authors:
        confidence = Confidence.LOW
    elif title_confidence == Confidence.HIGH and authors_confidence == Confidence.HIGH:
        confidence = Confidence.HIGH
    elif title_confidence != Confidence.LOW and authors_confidence != Confidence.LOW:
        confidence = Confidence.MEDIUM
    else:
        confidence = Confidence.LOW

    return CanonicalMetadata(
        title=title,
        authors=authors,
        edition_text=edition_text,
        isbns=isbns,
        confidence=confidence,
        field_confidence=field_confidence,
        field_reasons=field_reasons,
        warnings=warnings,
    )


def _extraction_isbns(extraction: ExtractionResult) -> set[str]:
    return {
        str(value)
        for evidence in extraction.evidence
        if evidence.field == MetadataField.ISBN and isinstance(evidence.value, list)
        for value in evidence.value
    }


def _extraction_title(extraction: ExtractionResult) -> str:
    evidence = _best_evidence([extraction], MetadataField.TITLE)
    return _evidence_key(evidence) if evidence else ""


def _extraction_authors(extraction: ExtractionResult) -> set[str]:
    evidence = _best_evidence([extraction], MetadataField.AUTHORS)
    if not evidence or not isinstance(evidence.value, list):
        return set()
    return {normalize_key(author) for author in evidence.value if author.strip()}


def _extraction_edition(extraction: ExtractionResult) -> str:
    evidence = _best_evidence([extraction], MetadataField.EDITION)
    return _evidence_key(evidence) if evidence else ""


def _can_group(left: ExtractionResult, right: ExtractionResult) -> bool:
    left_isbns = _extraction_isbns(left)
    right_isbns = _extraction_isbns(right)
    if left_isbns and right_isbns:
        return bool(left_isbns & right_isbns)

    left_title, right_title = _extraction_title(left), _extraction_title(right)
    if not left_title or left_title != right_title:
        return False
    left_edition, right_edition = _extraction_edition(left), _extraction_edition(right)
    if left_edition and right_edition and left_edition != right_edition:
        return False
    left_authors, right_authors = _extraction_authors(left), _extraction_authors(right)
    return not (left_authors and right_authors and not (left_authors & right_authors))


def _bundle_key(extractions: list[ExtractionResult], metadata: CanonicalMetadata) -> str:
    if metadata.isbns:
        return f"isbn:{metadata.isbns[0]}"
    author_key = "|".join(sorted(normalize_key(author) for author in metadata.authors))
    edition_key = normalize_key(metadata.edition_text or "")
    return "::".join((normalize_key(metadata.title), author_key, edition_key))


def discover_bundles(root: Path, *, exclude: Path | None = None) -> list[EbookBundle]:
    groups: list[list[ExtractionResult]] = []
    for file_path in iter_ebook_files(root, exclude=exclude):
        extraction = extract_result(file_path)
        matches = [group for group in groups if any(_can_group(extraction, existing) for existing in group)]
        if not matches:
            groups.append([extraction])
            continue
        primary = matches[0]
        primary.append(extraction)
        for group in matches[1:]:
            primary.extend(group)
            groups.remove(group)

    bundles: list[EbookBundle] = []
    for extractions in groups:
        extractions.sort(key=lambda result: result.path)
        metadata = _merge_metadata(extractions)
        bundles.append(
            EbookBundle(
                key=_bundle_key(extractions, metadata),
                files=[extraction.path for extraction in extractions],
                extractions=extractions,
                metadata=metadata,
            )
        )
    return sorted(bundles, key=lambda bundle: bundle.key)


def resolve_bundles_with_ai(bundles: Iterable[EbookBundle], resolver: Any) -> list[EbookBundle]:
    """Apply advisory AI suggestions as medium-or-lower confidence metadata.

    The caller must still opt into ``include_review``/YOLO before these suggestions
    can create moves. This keeps an uncorroborated model response visible in the
    final attention list rather than silently promoting it to high confidence.
    """
    resolved: list[EbookBundle] = []
    source = type(resolver).__name__.removesuffix("Resolver") or "AI"
    for bundle in bundles:
        metadata = bundle.metadata
        if metadata.confidence == Confidence.HIGH:
            resolved.append(bundle)
            continue
        suggestion = resolver.resolve(bundle)
        title = suggestion.title or metadata.title
        authors = suggestion.authors or metadata.authors
        edition_text = format_edition(extract_edition_number(suggestion.edition_text or ""), suggestion.edition_text) if suggestion.edition_text else metadata.edition_text
        field_confidence = dict(metadata.field_confidence)
        field_reasons = {field: list(reasons) for field, reasons in metadata.field_reasons.items()}
        changed = False
        for field, value in ((MetadataField.TITLE, suggestion.title), (MetadataField.AUTHORS, suggestion.authors), (MetadataField.EDITION, suggestion.edition_text)):
            if not value:
                continue
            changed = True
            confidence = Confidence.MEDIUM if suggestion.confidence == Confidence.HIGH else suggestion.confidence
            field_confidence[field] = confidence
            field_reasons[field] = [f"Suggested by {source}: {suggestion.reasoning or 'no rationale supplied'}"]
        confidence = Confidence.MEDIUM if title and authors and changed else metadata.confidence
        warnings = list(metadata.warnings)
        if changed:
            warnings.append(f"{source} supplied uncorroborated metadata; review this book after organization.")
        resolved.append(
            EbookBundle(
                key=bundle.key,
                files=bundle.files,
                extractions=bundle.extractions,
                metadata=CanonicalMetadata(
                    title=title,
                    authors=authors,
                    edition_text=edition_text,
                    isbns=metadata.isbns,
                    confidence=confidence,
                    field_confidence=field_confidence,
                    field_reasons=field_reasons,
                    warnings=warnings,
                ),
            )
        )
    return resolved


def build_plan(
    root: Path,
    output_dir: Path | None = None,
    *,
    include_review: bool = False,
    bundles: list[EbookBundle] | None = None,
) -> PipelinePlan:
    root = root.resolve()
    output_dir = (output_dir or root).resolve()
    output_is_nested_input = output_dir != root and output_dir.is_relative_to(root)
    bundles = bundles if bundles is not None else discover_bundles(root, exclude=output_dir if output_is_nested_input else None)
    moves: list[PlannedFileMove] = []
    review_bundles: list[EbookBundle] = []
    skipped_bundles: list[EbookBundle] = []
    collisions: list[str] = []
    target_owner: dict[Path, Path] = {}

    for bundle in bundles:
        metadata = bundle.metadata
        actionable = bool(metadata.title and metadata.authors)
        if metadata.confidence != Confidence.HIGH:
            review_bundles.append(bundle)
        if not actionable:
            skipped_bundles.append(bundle)
            continue
        if metadata.confidence != Confidence.HIGH and not include_review:
            continue

        folder_name = canonical_name(metadata.title, metadata.authors, metadata.edition_text)
        bundle_dir = output_dir / folder_name
        used_names: set[str] = set()
        for source in bundle.files:
            target_name = f"{folder_name}{source.suffix.lower()}"
            if target_name in used_names:
                target_name = f"{folder_name} ({source.suffix.lower().lstrip('.')}){source.suffix.lower()}"
            counter = 2
            while target_name in used_names:
                target_name = f"{folder_name} ({counter}){source.suffix.lower()}"
                counter += 1
            used_names.add(target_name)
            target = bundle_dir / target_name
            owner = target_owner.get(target)
            if owner is not None and owner != source:
                collisions.append(f"Multiple files would target {target}: {owner} and {source}")
            target_owner[target] = source
            moves.append(PlannedFileMove(source=source, target=target))

    return PipelinePlan(
        root=root,
        bundles=bundles,
        moves=moves,
        review_bundles=review_bundles,
        skipped_bundles=skipped_bundles,
        collisions=collisions,
    )


def validate_plan(plan: PipelinePlan) -> list[str]:
    errors = list(plan.collisions)
    target_owner: dict[Path, Path] = {}
    source_paths = {move.source.resolve() for move in plan.moves}
    for move in plan.moves:
        source = move.source.resolve()
        target = move.target.resolve()
        if not source.exists():
            errors.append(f"Source no longer exists: {source}")
        if source == target:
            continue
        owner = target_owner.get(target)
        if owner is not None and owner != source:
            errors.append(f"Multiple moves target {target}: {owner} and {source}")
        target_owner[target] = source
        if target.exists() and target not in source_paths:
            errors.append(f"Target already exists: {target}")
    return errors


def apply_plan(plan: PipelinePlan, *, copy: bool = False) -> list[PlannedFileMove]:
    errors = validate_plan(plan)
    if errors:
        raise FileExistsError("Plan cannot be applied:\n- " + "\n- ".join(errors))

    applied: list[PlannedFileMove] = []
    try:
        for move in plan.moves:
            if move.source.resolve() == move.target.resolve():
                continue
            move.target.parent.mkdir(parents=True, exist_ok=True)
            if copy:
                shutil.copy2(move.source, move.target)
            else:
                shutil.move(str(move.source), str(move.target))
            applied.append(move)
    except Exception:
        for move in reversed(applied):
            try:
                if copy:
                    move.target.unlink(missing_ok=True)
                else:
                    move.source.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(move.target), str(move.source))
            except Exception:
                pass
        raise
    return applied


def to_jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {key: to_jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {
            (key.value if isinstance(key, Enum) else str(key)): to_jsonable(item)
            for key, item in value.items()
        }
    return value


def dumps_json(value: Any) -> str:
    return json.dumps(to_jsonable(value), ensure_ascii=False, indent=2, sort_keys=True)
