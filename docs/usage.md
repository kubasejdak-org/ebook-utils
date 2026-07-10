# Usage

## Direct workflow

```bash
# Default: print only high-confidence proposals; no files are changed.
uv run ebook-utils organize path/to/downloads --output-dir path/to/library

# Inspect all actionable proposals, including books that need later attention.
uv run ebook-utils organize path/to/downloads --output-dir path/to/library --yolo --dry-run

# Apply every actionable proposal.
uv run ebook-utils organize path/to/downloads --output-dir path/to/library --yolo

# Copy while validating the result.
uv run ebook-utils organize path/to/downloads --output-dir path/to/library --yolo --copy
```

`--yolo` is explicit. It applies medium/low-confidence books only when a title and author exist; incomplete bundles are
left untouched. The terminal output identifies attention items, while `--json` returns the same detail for an AI agent.

## AI-assisted YOLO

The normal integration is an external agent calling the CLI and reading JSON—there are no user-managed review files:

```bash
uv run ebook-utils organize path/to/downloads --output-dir path/to/library --yolo --dry-run --json
```

For one-command provider assistance, install an optional adapter and supply its normal environment variable:

```bash
uv sync --extra ai-openai
export OPENAI_API_KEY=...
uv run ebook-utils organize path/to/downloads --output-dir path/to/library --yolo --ai-provider openai
```

Use `--ai-provider claude` after `uv sync --extra ai-claude` and setting `ANTHROPIC_API_KEY`. AI-supplied values are
included in the final attention list and capped at medium confidence.

## Inspection

```bash
uv run ebook-utils info path/to/book.epub
uv run ebook-utils scan path/to/downloads
uv run ebook-utils scan path/to/downloads --json
uv run ebook-utils plan path/to/downloads --output-dir path/to/library --yolo
```

`scan` and `plan` expose evidence, selected metadata, field confidence, reasons, proposed moves, skipped books, and
collisions.

## Canonical name

```text
Title - Author 1, Author 2, Author 3 - Optional edition
```

Subtitles are deliberately omitted. First edition is omitted. Numeric editions are normalized to `2nd edition`,
`3rd edition`, and so on; recognized special editions include `Anniversary edition`, `Revised edition`, and
`Special edition`.
