import json
import shutil
from collections import defaultdict
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
from .naming import canonical_name, normalize_key

SUPPORTED_EXTENSIONS = {".epub", ".pdf"}
CONFIDENCE_RANK = {Confidence.LOW: 1, Confidence.MEDIUM: 2, Confidence.HIGH: 3}
SOURCE_RANK = {"epub": 4, "filename": 3, "pdf": 1}


def iter_ebook_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root] if root.suffix.lower() in SUPPORTED_EXTENSIONS else []
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
        and path.suffix.lower() in SUPPORTED_EXTENSIONS
        and not any(part.startswith(".") for part in path.parts)
    )


def _evidence_score(evidence: MetadataEvidence) -> tuple[int, int, int]:
    value_len = len(evidence.value) if isinstance(evidence.value, list) else len(str(evidence.value))
    return (CONFIDENCE_RANK[evidence.confidence], SOURCE_RANK.get(evidence.source, 0), value_len)


def _best_evidence(extractions: Iterable[ExtractionResult], field: MetadataField) -> MetadataEvidence | None:
    candidates = [evidence for extraction in extractions for evidence in extraction.evidence if evidence.field == field]
    if not candidates:
        return None
    return max(candidates, key=_evidence_score)


def _group_key(extraction: ExtractionResult) -> str:
    title_evidence = _best_evidence([extraction], MetadataField.TITLE)
    if title_evidence and str(title_evidence.value).strip():
        return normalize_key(str(title_evidence.value))
    return normalize_key(extraction.path.stem)


def _merge_metadata(extractions: list[ExtractionResult]) -> CanonicalMetadata:
    warnings = [warning for extraction in extractions for warning in extraction.warnings]
    title_evidence = _best_evidence(extractions, MetadataField.TITLE)
    authors_evidence = _best_evidence(extractions, MetadataField.AUTHORS)
    edition_evidence = _best_evidence(extractions, MetadataField.EDITION)

    title = str(title_evidence.value).strip() if title_evidence else ""
    authors = list(authors_evidence.value) if authors_evidence and isinstance(authors_evidence.value, list) else []
    edition_text = str(edition_evidence.value).strip() if edition_evidence else None

    if not title:
        title = extractions[0].path.stem
        warnings.append("No title evidence found; using filename stem.")
    if not authors:
        warnings.append("No author evidence found.")

    selected = [e for e in [title_evidence, authors_evidence] if e is not None]
    if title and authors and selected and all(e.confidence == Confidence.HIGH for e in selected):
        confidence = Confidence.HIGH
    elif title and authors:
        confidence = Confidence.MEDIUM
    else:
        confidence = Confidence.LOW

    return CanonicalMetadata(
        title=title, authors=authors, edition_text=edition_text, confidence=confidence, warnings=warnings
    )


def discover_bundles(root: Path) -> list[EbookBundle]:
    grouped: dict[str, list[ExtractionResult]] = defaultdict(list)
    for file_path in iter_ebook_files(root):
        extraction = extract_result(file_path)
        grouped[_group_key(extraction)].append(extraction)

    bundles: list[EbookBundle] = []
    for key, extractions in sorted(grouped.items()):
        files = sorted(extraction.path for extraction in extractions)
        bundles.append(
            EbookBundle(key=key, files=files, extractions=extractions, metadata=_merge_metadata(extractions))
        )
    return bundles


def build_plan(root: Path, output_dir: Path | None = None) -> PipelinePlan:
    root = root.resolve()
    output_dir = (output_dir or root).resolve()
    bundles = discover_bundles(root)
    moves: list[PlannedFileMove] = []
    review_bundles: list[EbookBundle] = []

    for bundle in bundles:
        if bundle.metadata.confidence != Confidence.HIGH:
            review_bundles.append(bundle)
            continue
        folder_name = canonical_name(bundle.metadata.title, bundle.metadata.authors, bundle.metadata.edition_text)
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
            moves.append(PlannedFileMove(source=source, target=bundle_dir / target_name))

    return PipelinePlan(root=root, bundles=bundles, moves=moves, review_bundles=review_bundles)


def apply_plan(plan: PipelinePlan, *, copy: bool = False) -> list[PlannedFileMove]:
    applied: list[PlannedFileMove] = []
    for move in plan.moves:
        if move.source.resolve() == move.target.resolve():
            continue
        move.target.parent.mkdir(parents=True, exist_ok=True)
        if move.target.exists():
            raise FileExistsError(f"Target already exists: {move.target}")
        if copy:
            shutil.copy2(move.source, move.target)
        else:
            shutil.move(str(move.source), str(move.target))
        applied.append(move)
    return applied


def prepare_kindle_manifest(plan: PipelinePlan, output_path: Path) -> Path:
    rows = ["source,target,title,authors,edition"]
    bundle_by_file = {file_path: bundle for bundle in plan.bundles for file_path in bundle.files}
    for move in plan.moves:
        bundle = bundle_by_file[move.source]
        rows.append(
            ",".join(
                [
                    _csv(move.source),
                    _csv(move.target),
                    _csv(bundle.metadata.title),
                    _csv("; ".join(bundle.metadata.authors)),
                    _csv(bundle.metadata.edition_text or ""),
                ]
            )
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(rows) + "\n")
    return output_path


def _csv(value: object) -> str:
    text = str(value).replace('"', '""')
    return f'"{text}"'


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
        return {key: to_jsonable(item) for key, item in value.items()}
    return value


def dumps_json(value: Any) -> str:
    return json.dumps(to_jsonable(value), ensure_ascii=False, indent=2, sort_keys=True)
