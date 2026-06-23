from pathlib import Path

from ebook_utils.models import Confidence
from ebook_utils.naming import canonical_name, extract_edition_number, extract_edition_text, parse_filename_metadata


def test_extract_edition_text_and_number() -> None:
    assert extract_edition_text("C++ High Performance Second Edition") == "Second Edition"
    assert extract_edition_number("Second Edition") == 2
    assert extract_edition_number("3rd edition") == 3


def test_parse_canonical_filename() -> None:
    title, authors, edition, confidence = parse_filename_metadata(
        Path("Clean Code - Robert C. Martin - 2nd edition.epub")
    )
    assert title == "Clean Code"
    assert authors == ["Robert C. Martin"]
    assert edition == "2nd edition"
    assert confidence == Confidence.HIGH


def test_canonical_name_limits_authors_to_three() -> None:
    assert canonical_name("Title", ["A", "B", "C", "D"], "2nd edition") == "Title - A, B, C - 2nd edition"
