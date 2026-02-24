import re
from abc import ABC, abstractmethod
from pathlib import Path

import pypdf
from ebooklib import epub

from .models import EbookMetadata

_DC_NS = "http://purl.org/dc/elements/1.1/"
_OPF_NS = "http://www.idpf.org/2007/opf"

_WORD_TO_NUM = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
    "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10,
}


def _extract_edition_number(text: str) -> int | None:
    text_l = text.lower().strip()
    for word, n in _WORD_TO_NUM.items():
        if word in text_l:
            return n
    m = re.search(r'\b(\d+)(?:st|nd|rd|th)?\b', text_l)
    if m:
        return int(m.group(1))
    return None


def _edition_from_path(path: Path) -> int | None:
    """Return edition number parsed from the file path, or None."""
    path_text = " ".join(path.parts).lower()
    m = re.search(
        r'\b(?:(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth)|(\d+)(?:st|nd|rd|th)?)\s+edition\b',
        path_text,
    )
    if m:
        return _WORD_TO_NUM.get(m.group(1)) if m.group(1) else int(m.group(2))
    m = re.search(r'\bedition\s+(\d+)\b', path_text)
    if m:
        return int(m.group(1))
    return None


def _split_author_string(raw: str) -> list[str]:
    """Split a raw author string on ';', ' and '/' & ', or ','."""
    if ";" in raw:
        parts = raw.split(";")
    elif re.search(r'\s+(?:and|&)\s+', raw, re.IGNORECASE):
        parts = re.split(r'\s+(?:and|&)\s+', raw, flags=re.IGNORECASE)
    elif "," in raw:
        parts = raw.split(",")
    else:
        return [raw.strip()]
    return [p.strip() for p in parts if p.strip()]


class EbookExtractor(ABC):
    @abstractmethod
    def extract(self, path: Path) -> EbookMetadata: ...


class EpubExtractor(EbookExtractor):
    def extract(self, path: Path) -> EbookMetadata:
        book = epub.read_epub(str(path))

        dc = book.metadata.get(_DC_NS, {})
        opf_metas: list[tuple[str, dict]] = book.metadata.get(_OPF_NS, {}).get("meta", [])

        # Build id -> title-type map from EPUB 3 refinements
        id_to_title_type: dict[str, str] = {}
        for value, attrs in opf_metas:
            if (
                attrs.get("property") == "title-type"
                and attrs.get("refines", "").startswith("#")
            ):
                id_to_title_type[attrs["refines"][1:]] = (value or "").strip()

        # Build id -> role map from EPUB 3 refinements
        id_to_role: dict[str, str] = {}
        for value, attrs in opf_metas:
            if (
                attrs.get("property") == "role"
                and attrs.get("refines", "").startswith("#")
                and attrs.get("scheme") == "marc:relators"
            ):
                id_to_role[attrs["refines"][1:]] = (value or "").strip()

        title, subtitle = self._parse_titles(dc, id_to_title_type)
        authors = self._parse_authors(dc, id_to_role)
        edition = self._parse_edition(dc, opf_metas, id_to_title_type, path)

        return EbookMetadata(
            title=title,
            subtitle=subtitle,
            authors=authors,
            edition=edition,
        )

    def _parse_titles(
        self,
        dc: dict[str, list[tuple[str, dict]]],
        id_to_title_type: dict[str, str],
    ) -> tuple[str, str | None]:
        title_entries: list[tuple[str, dict]] = dc.get("title", [])

        # EPUB 3: use refinement title-types
        if id_to_title_type:
            main_title: str | None = None
            subtitle: str | None = None
            for value, attrs in title_entries:
                el_id = attrs.get("id", "")
                title_type = id_to_title_type.get(el_id, "")
                if title_type == "main":
                    main_title = (value or "").strip()
                elif title_type == "subtitle":
                    subtitle = (value or "").strip()
            if main_title is not None:
                return main_title, subtitle

        # EPUB 2 fallback: first dc:title
        if title_entries:
            return (title_entries[0][0] or "").strip(), None

        return "", None

    def _parse_authors(
        self,
        dc: dict[str, list[tuple[str, dict]]],
        id_to_role: dict[str, str],
    ) -> list[str]:
        creator_entries: list[tuple[str, dict]] = dc.get("creator", [])
        if not creator_entries:
            return []

        # EPUB 3: filter by role "aut" using refinements
        if id_to_role:
            return [
                (value or "").strip()
                for value, attrs in creator_entries
                if id_to_role.get(attrs.get("id", ""), "") == "aut"
            ]

        # EPUB 2: use opf:role attribute
        has_role_attrs = any(attrs.get("role") for _, attrs in creator_entries)
        if has_role_attrs:
            return [
                (value or "").strip()
                for value, attrs in creator_entries
                if attrs.get("role", "") == "aut"
            ]

        # No role info at all: return all creators
        return [(value or "").strip() for value, _ in creator_entries]

    def _parse_edition(
        self,
        dc: dict[str, list[tuple[str, dict]]],
        opf_metas: list[tuple[str, dict]],
        id_to_title_type: dict[str, str],
        path: Path,
    ) -> int | None:
        # 1. dc:title with title-type="edition"
        if id_to_title_type:
            for value, attrs in dc.get("title", []):
                el_id = attrs.get("id", "")
                if id_to_title_type.get(el_id) == "edition":
                    return _extract_edition_number((value or "").strip())

        # 2. <meta property="schema:bookEdition">
        for value, attrs in opf_metas:
            if attrs.get("property") == "schema:bookEdition":
                return _extract_edition_number((value or "").strip())

        # 3. <meta name="edition" content="...">
        for value, attrs in opf_metas:
            if attrs.get("name") == "edition":
                content = attrs.get("content", "").strip()
                if content:
                    return _extract_edition_number(content)

        # 4. Filename fallback
        return _edition_from_path(path)


class PdfExtractor(EbookExtractor):
    def extract(self, path: Path) -> EbookMetadata:
        reader = pypdf.PdfReader(str(path))
        xmp = reader.xmp_metadata   # XmpInformation | None
        did = reader.metadata       # DocumentInformation | None

        return EbookMetadata(
            title=self._parse_title(xmp, did),
            subtitle=None,
            authors=self._parse_authors(xmp, did),
            edition=_edition_from_path(path),
        )

    def _parse_title(
        self,
        xmp: pypdf.xmp.XmpInformation | None,
        did: pypdf.DocumentInformation | None,
    ) -> str:
        if xmp is not None:
            dc_title = xmp.dc_title  # dict[str, str] | None
            if dc_title:
                if "x-default" in dc_title:
                    return dc_title["x-default"].strip()
                first = next(iter(dc_title.values()), None)
                if first:
                    return first.strip()
        if did is not None and did.title:
            return did.title.strip()
        return ""

    def _parse_authors(
        self,
        xmp: pypdf.xmp.XmpInformation | None,
        did: pypdf.DocumentInformation | None,
    ) -> list[str]:
        if xmp is not None:
            dc_creator = xmp.dc_creator  # list[str] | None
            if dc_creator:
                return [a.strip() for a in dc_creator if a.strip()]
        if did is not None and did.author:
            raw = did.author.strip()
            if raw:
                return _split_author_string(raw)
        return []


def get_extractor(path: Path) -> EbookExtractor:
    suffix = path.suffix.lower()
    if suffix == ".epub":
        return EpubExtractor()
    if suffix == ".pdf":
        return PdfExtractor()
    raise ValueError(
        f"Unsupported format '{path.suffix}'. Supported formats: .epub, .pdf."
    )
