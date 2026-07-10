from pathlib import Path

from ebook_utils.models import Confidence
from ebook_utils.naming import (
    canonical_name,
    extract_edition_number,
    extract_edition_text,
    format_edition,
    parse_filename_metadata,
    split_author_string,
)


def test_extract_edition_text_number_and_special_edition() -> None:
    assert extract_edition_text("C++ High Performance Second Edition") == "Second Edition"
    assert extract_edition_number("Second Edition") == 2
    assert extract_edition_number("3rd edition") == 3
    assert extract_edition_text("Book Anniversary Edition") == "Anniversary Edition"


def test_first_edition_is_omitted_and_special_edition_is_kept() -> None:
    assert format_edition(1, "First edition") is None
    assert format_edition(None, "1st edition") is None
    assert format_edition(None, "Anniversary edition") == "Anniversary edition"
    assert canonical_name("Title", ["Jane Doe"], format_edition(1, "First edition")) == "Title - Jane Doe"


def test_parse_canonical_filename_is_medium_confidence() -> None:
    title, authors, edition, confidence = parse_filename_metadata(
        Path("Clean Code - Robert C. Martin - 2nd edition.epub")
    )
    assert title == "Clean Code"
    assert authors == ["Robert C. Martin"]
    assert edition == "2nd edition"
    assert confidence == Confidence.MEDIUM


def test_author_name_is_normalized_when_last_first_is_unambiguous() -> None:
    assert split_author_string("Martin, Robert C.") == ["Robert C. Martin"]


def test_canonical_name_limits_authors_to_three() -> None:
    assert canonical_name("Title", ["A", "B", "C", "D"], "2nd edition") == "Title - A, B, C - 2nd edition"
