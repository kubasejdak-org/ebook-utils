import re
import unicodedata
from pathlib import Path

from .models import Confidence

_VENDOR_SUFFIXES = {
    "ebookpoint",
    "helion",
    "humble",
    "humblebundle",
    "packt",
}

_WORD_TO_NUM = {
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
    "sixth": 6,
    "seventh": 7,
    "eighth": 8,
    "ninth": 9,
    "tenth": 10,
}


def normalize_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).casefold()
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return " ".join(normalized.split())


def split_author_string(raw: str) -> list[str]:
    raw = raw.strip()
    if not raw:
        return []
    if ";" in raw:
        parts = raw.split(";")
    elif re.search(r"\s+(?:and|&)\s+", raw, re.IGNORECASE):
        parts = re.split(r"\s+(?:and|&)\s+", raw, flags=re.IGNORECASE)
    elif re.search(r",\s+(?:[A-ZŁŚŻŹĆŃÓĘ]|[A-Z][a-z])", raw):
        parts = raw.split(",")
    else:
        return [raw]
    return [part.strip() for part in parts if part.strip()]


def extract_edition_number(text: str) -> int | None:
    text_l = text.lower().strip()
    for word, number in _WORD_TO_NUM.items():
        if re.search(rf"\b{word}\b", text_l):
            return number
    match = re.search(r"\b(\d+)(?:st|nd|rd|th)?\b", text_l)
    return int(match.group(1)) if match else None


def extract_edition_text(text: str) -> str | None:
    match = re.search(
        r"\b((?:(?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth)|(?:\d+)(?:st|nd|rd|th)?)\s+edition|revised edition)\b",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        match = re.search(r"\bedition\s+(\d+)\b", text, flags=re.IGNORECASE)
        if not match:
            return None
        return f"{match.group(1)} edition"
    return match.group(1).strip()


def edition_from_path(path: Path) -> tuple[int | None, str | None]:
    text = " ".join(path.parts)
    edition_text = extract_edition_text(text)
    if not edition_text:
        return None, None
    return extract_edition_number(edition_text), edition_text


def parse_filename_metadata(path: Path) -> tuple[str, list[str], str | None, Confidence]:
    stem = path.stem.replace("_", " ").strip()
    edition_text = extract_edition_text(stem)
    without_edition = (
        re.sub(re.escape(edition_text), "", stem, flags=re.IGNORECASE).strip(" -_()") if edition_text else stem
    )

    if " - " in without_edition:
        parts = [part.strip() for part in without_edition.split(" - ") if part.strip()]
        title = parts[0] if parts else without_edition
        authors = split_author_string(parts[1]) if len(parts) > 1 else []
        confidence = Confidence.HIGH if title and authors else Confidence.MEDIUM
        return title, authors, edition_text, confidence

    slug_parts = [part for part in re.split(r"[-\s]+", without_edition) if part]
    while slug_parts and slug_parts[-1].casefold() in _VENDOR_SUFFIXES:
        slug_parts.pop()
    title = " ".join(slug_parts).strip() or stem
    title = title[:1].upper() + title[1:] if title else title
    return title, [], edition_text, Confidence.LOW


def ordinal_suffix(number: int) -> str:
    if 11 <= (number % 100) <= 13:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")


def format_edition(edition_number: int | None, edition_text: str | None) -> str | None:
    if edition_text:
        return edition_text
    if edition_number and edition_number > 1:
        return f"{edition_number}{ordinal_suffix(edition_number)} edition"
    return None


def sanitize_path_part(value: str) -> str:
    value = re.sub(r"[\\/:*?\"<>|]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value.rstrip(".") or "Untitled"


def canonical_name(title: str, authors: list[str], edition_text: str | None) -> str:
    parts = [sanitize_path_part(title)]
    if authors:
        parts.append(sanitize_path_part(", ".join(authors[:3])))
    if edition_text:
        parts.append(sanitize_path_part(edition_text))
    return " - ".join(parts)
