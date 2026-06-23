from pathlib import Path

from ebook_utils.models import Confidence
from ebook_utils.pipeline import build_plan


def test_build_plan_groups_high_confidence_canonical_names(tmp_path: Path) -> None:
    epub = tmp_path / "Example Book - Jane Doe.epub"
    pdf = tmp_path / "Example Book - Jane Doe.pdf"
    epub.write_text("not a real epub")
    pdf.write_text("not a real pdf")

    plan = build_plan(tmp_path)

    assert len(plan.bundles) == 1
    assert plan.bundles[0].metadata.confidence == Confidence.HIGH
    assert len(plan.moves) == 2
    assert {move.target.suffix for move in plan.moves} == {".epub", ".pdf"}
    assert all(move.target.parent.name == "Example Book - Jane Doe" for move in plan.moves)


def test_build_plan_keeps_missing_authors_for_review(tmp_path: Path) -> None:
    (tmp_path / "unknown-book.epub").write_text("not a real epub")

    plan = build_plan(tmp_path)

    assert len(plan.moves) == 0
    assert len(plan.review_bundles) == 1
    assert plan.review_bundles[0].metadata.confidence == Confidence.LOW
