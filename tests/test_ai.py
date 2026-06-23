from ebook_utils.ai import parse_ai_suggestion
from ebook_utils.models import Confidence


def test_parse_ai_suggestion_validates_confidence() -> None:
    suggestion = parse_ai_suggestion(
        {
            "title": "Book",
            "authors": ["Jane Doe"],
            "edition_text": None,
            "confidence": "unexpected",
            "reasoning": "No valid confidence was supplied.",
        }
    )

    assert suggestion.title == "Book"
    assert suggestion.authors == ["Jane Doe"]
    assert suggestion.confidence == Confidence.LOW
