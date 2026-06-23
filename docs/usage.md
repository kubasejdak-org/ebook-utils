# Current Usage

## Setup

Use `uv` from the repository root. The project dependencies are declared in `pyproject.toml`.

```bash
uv run ebook-utils --help
```

For tests:

```bash
uv run --extra test python -m pytest
```

For AI provider dependencies:

```bash
uv sync --extra ai-openai
uv sync --extra ai-claude
uv sync --extra ai
```

Set provider credentials using the normal SDK environment variables, for example `OPENAI_API_KEY` or
`ANTHROPIC_API_KEY`. Optional model overrides can be passed on the CLI.

## Inspect One File

```bash
uv run ebook-utils info path/to/book.epub
uv run ebook-utils info path/to/book.epub --json
```

This extracts embedded metadata and filename evidence. JSON output includes confidence, evidence source, warnings, and
parsed metadata.

## Scan A Raw Download Directory

```bash
uv run ebook-utils scan path/to/downloads
uv run ebook-utils scan path/to/downloads --json
```

This discovers `.epub` and `.pdf` files, extracts evidence, groups likely same-book files, and prints bundle confidence.

## Preview Rename And Grouping Actions

```bash
uv run ebook-utils plan path/to/downloads
uv run ebook-utils plan path/to/downloads --output-dir path/to/library
uv run ebook-utils plan path/to/downloads --json
```

`plan` does not mutate files. It shows which files would be moved into canonical book directories. Low-confidence
bundles are listed for review and are not included in planned moves.

## Apply High-Confidence Moves

```bash
uv run ebook-utils apply path/to/downloads --output-dir path/to/library
```

By default this moves files. To copy instead:

```bash
uv run ebook-utils apply path/to/downloads --output-dir path/to/library --copy
```

Only high-confidence bundles are moved or copied. Low-confidence bundles remain untouched. Existing target files cause
the command to fail instead of overwriting.

## Resolve Low-Confidence Bundles With AI Suggestions

```bash
uv run ebook-utils resolve-low-confidence path/to/downloads --ai-provider openai
uv run ebook-utils resolve-low-confidence path/to/downloads --ai-provider claude
uv run ebook-utils resolve-low-confidence path/to/downloads --ai-provider openai --model gpt-4.1-mini --json
```

AI output is advisory. It returns suggested title, authors, edition text, confidence, and reasoning. The current
pipeline does not automatically convert AI suggestions into file mutations.

## Prepare Kindle Manifest

```bash
uv run ebook-utils prepare-kindle path/to/downloads --manifest kindle-manifest.csv
```

This writes a CSV manifest for high-confidence planned files. It is intended for Send-to-Kindle preparation and review.
It does not upload files to Kindle.

## Notion Command

```bash
uv run ebook-utils sync-notion
```

This command currently exits with a placeholder message. Notion sync is not implemented yet.

## Canonical Naming

The current target format is:

```text
Title - Author 1, Author 2, Author 3 - Optional edition
```

Only up to three authors are included in canonical names. File and directory names are sanitized for common path-invalid
characters.
