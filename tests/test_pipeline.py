from pathlib import Path

import pytest

from ebook_utils.models import (
    AiSuggestion,
    Confidence,
    EbookMetadata,
    ExtractionResult,
    MetadataEvidence,
    MetadataField,
    PipelinePlan,
    PlannedFileMove,
)
from ebook_utils.naming import canonical_name
from ebook_utils.pipeline import _merge_metadata, apply_plan, build_plan, resolve_bundles_with_ai


def test_yolo_plan_groups_canonical_filename_variants_and_reports_field_confidence(tmp_path: Path) -> None:
    epub = tmp_path / "Example Book - Jane Doe.epub"
    pdf = tmp_path / "Example Book - Jane Doe.pdf"
    epub.write_text("not a real epub")
    pdf.write_text("not a real pdf")

    plan = build_plan(tmp_path, include_review=True)

    assert len(plan.bundles) == 1
    bundle = plan.bundles[0]
    assert bundle.metadata.confidence == Confidence.MEDIUM
    assert bundle.metadata.field_confidence["title"] == Confidence.MEDIUM
    assert bundle.metadata.field_confidence["authors"] == Confidence.MEDIUM
    assert len(plan.moves) == 2
    assert bundle in plan.review_bundles
    assert {move.target.suffix for move in plan.moves} == {".epub", ".pdf"}
    assert all(move.target.parent.name == "Example Book - Jane Doe" for move in plan.moves)


def test_conservative_plan_keeps_filename_only_bundle_for_attention(tmp_path: Path) -> None:
    (tmp_path / "Example Book - Jane Doe.epub").write_text("not a real epub")

    plan = build_plan(tmp_path)

    assert len(plan.moves) == 0
    assert len(plan.review_bundles) == 1
    assert plan.review_bundles[0].metadata.confidence == Confidence.MEDIUM


def test_yolo_never_fabricates_missing_author_name(tmp_path: Path) -> None:
    (tmp_path / "unknown-book.epub").write_text("not a real epub")

    plan = build_plan(tmp_path, include_review=True)

    assert len(plan.moves) == 0
    assert len(plan.skipped_bundles) == 1
    assert plan.skipped_bundles[0].metadata.confidence == Confidence.LOW


def test_apply_preflights_all_targets_before_any_move(tmp_path: Path) -> None:
    first = tmp_path / "first.epub"
    second = tmp_path / "second.pdf"
    first.write_text("first")
    second.write_text("second")
    existing_target = tmp_path / "library" / "existing.pdf"
    existing_target.parent.mkdir()
    existing_target.write_text("existing")
    plan = PipelinePlan(
        root=tmp_path,
        bundles=[],
        moves=[
            PlannedFileMove(first, tmp_path / "library" / "first.epub"),
            PlannedFileMove(second, existing_target),
        ],
        review_bundles=[],
    )

    with pytest.raises(FileExistsError):
        apply_plan(plan)

    assert first.exists()
    assert second.exists()
    assert not (tmp_path / "library" / "first.epub").exists()


def test_ai_suggestion_makes_an_incomplete_bundle_actionable_only_in_yolo_mode(tmp_path: Path) -> None:
    source = tmp_path / "opaque-download.epub"
    source.write_text("not a real epub")
    deterministic = build_plan(tmp_path)

    class Resolver:
        def resolve(self, bundle):
            return AiSuggestion(
                title="Recovered Book",
                authors=["Jane Doe"],
                edition_text="First edition",
                confidence=Confidence.HIGH,
                reasoning="Matched the valid ISBN in the source file.",
            )

    bundles = resolve_bundles_with_ai(deterministic.bundles, Resolver())
    yolo_plan = build_plan(tmp_path, include_review=True, bundles=bundles)

    assert len(yolo_plan.moves) == 1
    assert yolo_plan.moves[0].target.parent.name == "Recovered Book - Jane Doe"
    assert yolo_plan.review_bundles[0].metadata.confidence == Confidence.MEDIUM
    assert yolo_plan.review_bundles[0].metadata.field_confidence["authors"] == Confidence.MEDIUM


def test_subtitle_is_retained_in_raw_metadata_but_omitted_from_canonical_name(tmp_path: Path) -> None:
    extraction = ExtractionResult(
        path=tmp_path / "book.epub",
        format="epub",
        metadata=EbookMetadata(title="Main title", subtitle="A subtitle", authors=["Jane Doe"]),
        evidence=[
            MetadataEvidence(MetadataField.TITLE, "Main title", "epub", tmp_path / "book.epub", Confidence.HIGH),
            MetadataEvidence(MetadataField.AUTHORS, ["Jane Doe"], "epub", tmp_path / "book.epub", Confidence.HIGH),
        ],
    )

    metadata = _merge_metadata([extraction])

    assert extraction.metadata.subtitle == "A subtitle"
    assert canonical_name(metadata.title, metadata.authors, metadata.edition_text) == "Main title - Jane Doe"
