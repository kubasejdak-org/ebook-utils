# Ebook Utils Conversation And Implementation Summary

## Goal

`ebook-utils` is intended to manage raw ebook downloads, especially packs from Humble Bundle or similar vendors. The
target workflow is:

1. Scan loose ebook files such as EPUB and PDF.
2. Extract title, authors, and edition from embedded metadata and filenames.
3. Group different formats of the same book into one directory.
4. Rename files into the canonical format: `Title - Authors - Optional edition`.
5. Use AI only for low-confidence cases.
6. Later enrich metadata from Amazon and update Notion.
7. Later prepare or automate Kindle upload workflows.

The original concern was that manual review of every book is too slow. The implemented direction is therefore tool-first
automation with conservative review gates.

## Main Decisions

- Raw downloaded files are the input, not manually verified `To Notion` folders.
- High-confidence books may be renamed and grouped automatically.
- Low-confidence cases stop before file mutation and are reported for review.
- EPUB metadata is treated as stronger evidence than PDF metadata.
- PDF metadata is treated carefully because PDFs can contain embedded asset metadata that looks like book metadata.
- Filename parsing is important because vendor downloads often contain useful title/author hints.
- AI postprocessing is advisory by default. It can suggest corrected metadata for low-confidence bundles, but it does
  not directly authorize mutation.
- OpenAI and Claude support should be pluggable through one provider interface.
- The code should remain ready for a future terminal UI, so pipeline logic lives in service modules rather than Typer
  command handlers.

## What Was Implemented

- Structured metadata and evidence models with confidence and source tracking.
- EPUB and PDF extraction returning `ExtractionResult` objects.
- Filename fallback extraction when embedded metadata is missing or parsing fails.
- Canonical naming helpers for title, authors, and edition.
- Bundle discovery for supported ebook files.
- Rename/grouping plan generation.
- High-confidence file move/copy application.
- Kindle preparation manifest generation.
- Optional AI resolver interface with OpenAI and Claude adapters.
- CLI commands for scan, plan, apply, AI review, and Kindle manifest generation.
- JSON output for agent and future UI integration.
- Focused tests for naming, planning, and AI response parsing.

## Current Verification

The following checks passed after implementation:

```bash
uv run --extra test python -m pytest
uv run python -m compileall ebook_utils
uv run ebook-utils plan .
```

The local sample run found four bundles: two EPUBs were high confidence and two sample PDFs were left as low-confidence
review cases.
