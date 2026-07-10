from abc import ABC, abstractmethod
from pathlib import Path

import pypdf
from ebooklib import epub

from .models import Confidence, EbookMetadata, ExtractionResult, MetadataEvidence, MetadataField
from .naming import (
    edition_from_path,
    extract_edition_number,
    extract_isbns,
    format_edition,
    parse_filename_metadata,
    is_non_author_contributor,
    normalize_author_name,
    split_author_string,
)

_DC_NS = "http://purl.org/dc/elements/1.1/"
_OPF_NS = "http://www.idpf.org/2007/opf"

_NOISY_PDF_TITLES = {
    "information box icon",
    "new packt logo",
    "packt_logo_ill 01_orange",
    "quote",
}


def _clean_values(values: list[str]) -> list[str]:
    return [value.strip() for value in values if value and value.strip()]


def _looks_like_asset_title(value: str) -> bool:
    value_l = value.casefold().strip()
    return (
        value_l in _NOISY_PDF_TITLES
        or value_l.endswith((".eps", ".ai", ".svg", ".psd"))
        or "logo" in value_l
        or " icon" in value_l
    )


class EbookExtractor(ABC):
    @abstractmethod
    def extract(self, path: Path) -> EbookMetadata: ...

    def extract_result(self, path: Path) -> ExtractionResult:
        metadata = self.extract(path)
        evidence: list[MetadataEvidence] = []
        warnings: list[str] = []
        source = path.suffix.lower().lstrip(".") or "unknown"
        embedded_confidence = Confidence.HIGH if source == "epub" else Confidence.MEDIUM

        if metadata.title:
            evidence.append(MetadataEvidence(MetadataField.TITLE, metadata.title, source, path, embedded_confidence))
        if metadata.authors:
            evidence.append(MetadataEvidence(MetadataField.AUTHORS, metadata.authors, source, path, embedded_confidence))
        if metadata.edition_text:
            evidence.append(
                MetadataEvidence(MetadataField.EDITION, metadata.edition_text, source, path, embedded_confidence)
            )
        elif metadata.edition:
            evidence.append(MetadataEvidence(MetadataField.EDITION, metadata.edition, source, path, embedded_confidence))

        if metadata.isbns:
            evidence.append(MetadataEvidence(MetadataField.ISBN, metadata.isbns, source, path, embedded_confidence))
        filename_title, filename_authors, filename_edition, filename_confidence = parse_filename_metadata(path)
        if filename_title:
            evidence.append(
                MetadataEvidence(MetadataField.TITLE, filename_title, "filename", path, filename_confidence)
            )
        if filename_authors:
            evidence.append(
                MetadataEvidence(MetadataField.AUTHORS, filename_authors, "filename", path, filename_confidence)
            )
        if filename_edition:
            evidence.append(
                MetadataEvidence(MetadataField.EDITION, filename_edition, "filename", path, Confidence.MEDIUM)
            )

        if not metadata.title:
            warnings.append("No embedded title found; filename will be used as fallback.")
        if not metadata.authors:
            warnings.append("No embedded authors found; filename or AI review may be needed.")

        return ExtractionResult(path=path, format=source, metadata=metadata, evidence=evidence, warnings=warnings)


class EpubExtractor(EbookExtractor):
    def extract(self, path: Path) -> EbookMetadata:
        book = epub.read_epub(str(path))

        dc = book.metadata.get(_DC_NS, {})
        opf_metas: list[tuple[str, dict]] = book.metadata.get(_OPF_NS, {}).get("meta", [])

        id_to_title_type: dict[str, str] = {}
        id_to_role: dict[str, str] = {}
        for value, attrs in opf_metas:
            if attrs.get("property") == "title-type" and attrs.get("refines", "").startswith("#"):
                id_to_title_type[attrs["refines"][1:]] = (value or "").strip()
            if (
                attrs.get("property") == "role"
                and attrs.get("refines", "").startswith("#")
                and attrs.get("scheme") == "marc:relators"
            ):
                id_to_role[attrs["refines"][1:]] = (value or "").strip()

        title, subtitle = self._parse_titles(dc, id_to_title_type)
        authors = self._parse_authors(dc, id_to_role)
        edition_number, edition_text = self._parse_edition(dc, opf_metas, id_to_title_type, path)
        isbns = extract_isbns(" ".join(value or "" for value, _ in dc.get("identifier", [])))

        return EbookMetadata(
            title=title,
            subtitle=subtitle,
            authors=authors,
            edition=edition_number,
            edition_text=edition_text,
            isbns=isbns,
        )

    def _parse_titles(
        self, dc: dict[str, list[tuple[str, dict]]], id_to_title_type: dict[str, str]
    ) -> tuple[str, str | None]:
        title_entries: list[tuple[str, dict]] = dc.get("title", [])
        if id_to_title_type:
            main_title: str | None = None
            subtitle: str | None = None
            for value, attrs in title_entries:
                title_type = id_to_title_type.get(attrs.get("id", ""), "")
                if title_type == "main":
                    main_title = (value or "").strip()
                elif title_type == "subtitle":
                    subtitle = (value or "").strip()
            if main_title is not None:
                return main_title, subtitle
        if title_entries:
            return (title_entries[0][0] or "").strip(), None
        return "", None

    def _parse_authors(self, dc: dict[str, list[tuple[str, dict]]], id_to_role: dict[str, str]) -> list[str]:
        creator_entries: list[tuple[str, dict]] = dc.get("creator", [])
        if not creator_entries:
            return []
        if id_to_role:
            values = [value or "" for value, attrs in creator_entries if id_to_role.get(attrs.get("id", "")) == "aut"]
        elif any(attrs.get("role") for _, attrs in creator_entries):
            values = [value or "" for value, attrs in creator_entries if attrs.get("role", "") == "aut"]
        else:
            values = [value or "" for value, _ in creator_entries]

        authors: list[str] = []
        for value in _clean_values(values):
            for author in split_author_string(value):
                if author and not is_non_author_contributor(author):
                    authors.append(normalize_author_name(author))
        return authors

    def _parse_edition(
        self,
        dc: dict[str, list[tuple[str, dict]]],
        opf_metas: list[tuple[str, dict]],
        id_to_title_type: dict[str, str],
        path: Path,
    ) -> tuple[int | None, str | None]:
        candidates: list[str] = []
        if id_to_title_type:
            candidates.extend(
                (value or "").strip()
                for value, attrs in dc.get("title", [])
                if id_to_title_type.get(attrs.get("id", "")) == "edition"
            )
        candidates.extend(
            (value or "").strip() for value, attrs in opf_metas if attrs.get("property") == "schema:bookEdition"
        )
        candidates.extend(attrs.get("content", "").strip() for _, attrs in opf_metas if attrs.get("name") == "edition")
        for candidate in candidates:
            if candidate:
                return extract_edition_number(candidate), candidate
        return edition_from_path(path)


class PdfExtractor(EbookExtractor):
    def extract(self, path: Path) -> EbookMetadata:
        reader = pypdf.PdfReader(str(path))
        xmp = reader.xmp_metadata
        did = reader.metadata
        edition_number, edition_text = edition_from_path(path)
        return EbookMetadata(
            title=self._parse_title(xmp, did),
            subtitle=None,
            authors=self._parse_authors(xmp, did),
            edition=edition_number,
            edition_text=format_edition(edition_number, edition_text),
            isbns=self._parse_isbns(reader, did),
        )

    def _parse_title(self, xmp: pypdf.xmp.XmpInformation | None, did: pypdf.DocumentInformation | None) -> str:
        if did is not None and did.title and not _looks_like_asset_title(did.title):
            return did.title.strip()
        if xmp is not None:
            dc_title = xmp.dc_title
            if dc_title:
                values = [dc_title.get("x-default", ""), *dc_title.values()]
                for value in values:
                    if value and not _looks_like_asset_title(value):
                        return value.strip()
        return ""

    def _parse_authors(self, xmp: pypdf.xmp.XmpInformation | None, did: pypdf.DocumentInformation | None) -> list[str]:
        values: list[str] = []
        if did is not None and did.author and not _looks_like_asset_title(did.author):
            values.append(did.author)
        elif xmp is not None and xmp.dc_creator:
            values.extend(author for author in xmp.dc_creator if author and not _looks_like_asset_title(author))
        authors: list[str] = []
        for value in values:
            for author in split_author_string(value):
                if author and not is_non_author_contributor(author):
                    authors.append(normalize_author_name(author))
        return authors

    def _parse_isbns(self, reader: pypdf.PdfReader, did: pypdf.DocumentInformation | None) -> list[str]:
        values: list[str] = []
        if did is not None:
            values.extend(str(value) for value in did.values() if value)
        for page in reader.pages[:5]:
            try:
                values.append(page.extract_text() or "")
            except Exception:
                continue
        return extract_isbns("\n".join(values))


class FilenameExtractor(EbookExtractor):
    def extract_result(self, path: Path) -> ExtractionResult:
        metadata = self.extract(path)
        title, authors, edition_text, confidence = parse_filename_metadata(path)
        evidence: list[MetadataEvidence] = []
        if title:
            evidence.append(MetadataEvidence(MetadataField.TITLE, title, "filename", path, confidence))
        if authors:
            evidence.append(MetadataEvidence(MetadataField.AUTHORS, authors, "filename", path, confidence))
        if edition_text:
            evidence.append(MetadataEvidence(MetadataField.EDITION, edition_text, "filename", path, confidence))
        return ExtractionResult(
            path=path,
            format=path.suffix.lower().lstrip(".") or "unknown",
            metadata=metadata,
            evidence=evidence,
            warnings=["Only filename evidence is available."],
        )

    def extract(self, path: Path) -> EbookMetadata:
        title, authors, edition_text, _ = parse_filename_metadata(path)
        return EbookMetadata(
            title=title,
            subtitle=None,
            authors=authors,
            edition=extract_edition_number(edition_text) if edition_text else None,
            edition_text=edition_text,
        )


def get_extractor(path: Path) -> EbookExtractor:
    suffix = path.suffix.lower()
    if suffix == ".epub":
        return EpubExtractor()
    if suffix == ".pdf":
        return PdfExtractor()
    raise ValueError(f"Unsupported format '{path.suffix}'. Supported formats: .epub, .pdf.")


def extract_result(path: Path) -> ExtractionResult:
    try:
        return get_extractor(path).extract_result(path)
    except Exception as error:
        result = FilenameExtractor().extract_result(path)
        result.warnings.append(f"Embedded metadata extraction failed: {error}")
        return result
