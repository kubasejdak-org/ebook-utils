# ebook-utils

`ebook-utils` turns a loose EPUB/PDF download folder into a consistent ebook library:

```text
Title - First Author, Second Author, Third Author [- Nth edition]/
  Title - First Author, Second Author, Third Author [- Nth edition].epub
  Title - First Author, Second Author, Third Author [- Nth edition].pdf
```

It is built for raw Humble Bundle-style downloads, where filenames and embedded metadata are uneven. It does not include
subtitles in the canonical title. First editions are omitted; defined special editions such as `Anniversary edition` are
retained.

## Use it

```bash
uv sync

# Always safe: default is a dry run of high-confidence moves.
ebook-utils organize /downloads --output-dir /library

# Preview every actionable proposal, including uncertain books.
ebook-utils organize /downloads --output-dir /library --yolo --dry-run

# Organize every actionable book now. Uncertain books remain in the attention list.
ebook-utils organize /downloads --output-dir /library --yolo

# Test without removing the originals.
ebook-utils organize /downloads --output-dir /library --yolo --copy
```

A book is actionable only when the tool has both a title and at least one author. `--yolo` never invents
`Unknown Author`; it leaves incomplete books in place and reports them.

## Confidence and attention

Every scan, plan, and `organize --json` result includes confidence for `title`, `authors`, `edition`, and `isbn`, plus
the evidence and reasons behind it.

- `high`: corroborated by independent usable evidence, such as matching EPUB/PDF metadata or reliable metadata plus a
  canonical filename.
- `medium`: plausible but supported by only one usable source. This includes a valid ISBN discovered in one file and a
  standalone EPUB metadata record.
- `low`: missing, filename-only, or conflicting evidence.

The overall confidence is based on title and author confidence. Edition and ISBN are reported independently because
their absence should not prevent a book with a known title and author from being organized.

`organize --yolo` moves actionable medium/low-confidence books too, but prints them under **Attention after
organization** so the manual review happens in the already structured library. Existing targets and duplicate planned
targets are preflighted before any move; a collision stops the whole apply pass.

## AI use

The primary interface is agent-friendly rather than tied to one AI SDK:

```bash
ebook-utils organize /downloads --output-dir /library --yolo --dry-run --json
```

Codex, Claude, or another agent can inspect this structured output and choose whether to run the same command with
`--yolo`. No review files are required.

For a self-contained autonomous run, the existing optional provider adapters can enrich uncertain bundles before YOLO
mode:

```bash
uv sync --extra ai-openai
ebook-utils organize /downloads --output-dir /library --yolo --ai-provider openai
```

OpenAI and Claude suggestions are intentionally capped at medium confidence and remain in the final attention list. They
never silently become high-confidence evidence.

## Commands

| Command                      | Purpose                                                                           |
| ---------------------------- | --------------------------------------------------------------------------------- |
| `info FILE`                  | Show raw metadata/evidence for one EPUB or PDF.                                   |
| `scan DIR`                   | List bundles with field-level confidence.                                         |
| `plan DIR`                   | Dry-run high-confidence moves; add `--yolo` to preview all actionable candidates. |
| `organize DIR`               | Direct workflow: dry-run by default; `--yolo` applies.                            |
| `apply DIR`                  | Backward-compatible apply command; use `--yolo` for uncertain actionable books.   |
| `resolve-low-confidence DIR` | Print optional OpenAI/Claude suggestions without mutation.                        |
| `prepare-kindle DIR`         | Create a high-confidence CSV manifest.                                            |

All implemented inspection/planning commands accept `--json` for agents and scripts.

## Supported metadata

- EPUB: OPF/DC title, author-role filtering, edition metadata, and valid ISBNs.
- PDF: document/XMP metadata, first five pages for valid ISBNs, and conservative filename fallback.
- Filename fallback: useful, but never high-confidence on its own.

The tool supports EPUB and PDF. MOBI, Notion sync, and Kindle upload are intentionally outside the initial organization
workflow.
