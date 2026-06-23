# ebook-utils

A CLI tool for organizing downloaded ebooks (EPUB, PDF) into a clean, structured library. It extracts metadata from
embedded file headers and filenames, groups different formats of the same book together, assigns confidence scores, and
renames or moves files into a canonical directory structure — automatically for high-confidence matches, with a manual
review gate for uncertain ones. An optional AI step (OpenAI or Claude) can suggest metadata for the uncertain cases.

Typical use case: a raw Humble Bundle download folder full of files like `python-crash-course_ebookpoint.epub` that you
want to turn into `Python Crash Course - Eric Matthes - 2nd edition`.

---

## Install

```bash
# Core (no AI)
uv sync

# With AI support
uv sync --extra ai-openai    # OpenAI only
uv sync --extra ai-claude    # Claude only
uv sync --extra ai           # Both providers
```

## Quick start

```bash
# Preview what would happen — no files touched
ebook-utils plan /path/to/downloads

# Apply: move high-confidence files into organized folders
ebook-utils apply /path/to/downloads --output-dir /path/to/library

# Use --copy to keep originals while testing
ebook-utils apply /path/to/downloads --output-dir /path/to/library --copy

# Get AI suggestions for anything the tool wasn't sure about
export ANTHROPIC_API_KEY=...
ebook-utils resolve-low-confidence /path/to/downloads --ai-provider claude
```

---

## Commands

| Command                        | What it does                                                      |
| ------------------------------ | ----------------------------------------------------------------- |
| `info <file>`                  | Show extracted metadata and confidence for a single file          |
| `scan <dir>`                   | List all discovered bundles with confidence scores                |
| `plan <dir>`                   | Preview the full rename/move plan without touching files          |
| `apply <dir>`                  | Execute the plan (move or `--copy`); skips low-confidence bundles |
| `resolve-low-confidence <dir>` | Query AI for metadata suggestions on uncertain bundles            |
| `prepare-kindle <dir>`         | Generate a CSV manifest for Send-to-Kindle                        |
| `sync-notion`                  | _(not yet implemented)_ Sync metadata to a Notion database        |

All commands accept `--json` for machine-readable output.

---

## Canonical naming format

```
Title - Author1, Author2 - Optional edition
```

Files are placed inside a folder with this name, e.g.:

```
Python Crash Course - Eric Matthes - 2nd edition/
  Python Crash Course - Eric Matthes - 2nd edition.epub
  Python Crash Course - Eric Matthes - 2nd edition.pdf
```

---

## Environment variables

| Variable                   | Purpose                                                   |
| -------------------------- | --------------------------------------------------------- |
| `OPENAI_API_KEY`           | Required for `--ai-provider openai`                       |
| `ANTHROPIC_API_KEY`        | Required for `--ai-provider claude`                       |
| `EBOOK_UTILS_OPENAI_MODEL` | Override default OpenAI model (`gpt-4.1-mini`)            |
| `EBOOK_UTILS_CLAUDE_MODEL` | Override default Claude model (`claude-3-5-haiku-latest`) |

---

## Documentation

- [`docs/overview.md`](docs/overview.md) — Architecture and key design decisions
- [`docs/usage.md`](docs/usage.md) — Full CLI reference with examples
- [`docs/requirements.md`](docs/requirements.md) — Functional requirements and implementation status
- [`docs/roadmap.md`](docs/roadmap.md) — Known limitations and future work
