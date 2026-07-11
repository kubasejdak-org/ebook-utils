# ebook-utils: How It Works

This is a codebase-level companion to `README.md` and `docs/`. Where those documents describe the intended user
experience, this report traces the actual implementation — the confidence algorithm, naming rules, pipeline mechanics,
and edge cases — so you know exactly what each command will do before you run it. Every claim below is backed by a
`file:line` reference into `ebook_utils/`.

## 1. What the tool does

`ebook-utils` takes a folder of loosely-named EPUB/PDF downloads (the canonical case: a Humble Bundle drop with
inconsistent filenames and unreliable embedded metadata) and reorganizes it into

```text
Title - Author1, Author2[, Author3] [- Nth edition]/
  Title - Author1, Author2[, Author3] [- Nth edition].epub
  Title - Author1, Author2[, Author3] [- Nth edition].pdf
```

It never guesses an author to make a book "complete," and it grades every decision with an explicit confidence level so
you can decide how much to automate versus review by hand.

## 2. Core concepts

### Bundle

A **bundle** is a group of files believed to be the same book (e.g. an EPUB and a PDF of the same title). Bundles are
formed by `discover_bundles` (`ebook_utils/pipeline.py:225`), which walks the directory tree via `iter_ebook_files`
(`pipeline.py:26`, skips dotfiles/dot-directories), extracts each file, and pairwise-merges files using `_can_group`
(`pipeline.py:201`):

- If **both** files have a valid, checksum-passing ISBN, group them when the ISBN sets intersect.
- Otherwise, group them when normalized titles match, **and** (if both have edition evidence) editions match, **and**
  (if both have authors) author sets intersect.

This is why an EPUB and PDF named identically (e.g. both `Example Book - Jane Doe.*`) merge into one bundle even with no
ISBN in either file.

### Confidence

Confidence is a three-level enum — `HIGH` / `MEDIUM` / `LOW` (`models.py:24`) — computed **per field** (title, authors,
edition, isbn) and then rolled up into one **overall bundle confidence**.

Per-field rule, `_field_assessment` (`pipeline.py:66`):

| Situation                                                                         | Result                                                                   |
| --------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| No evidence found for the field                                                   | `LOW`                                                                    |
| Two or more _reliable_ (non-LOW) sources disagree                                 | `LOW` — conflicts always win, no matter how good one source is           |
| Agreement across ≥2 distinct **source kinds** (epub+pdf) or ≥2 distinct **files** | `HIGH`                                                                   |
| A single EPUB source, high baseline confidence, uncorroborated                    | demoted to `MEDIUM` — one EPUB's metadata alone is never enough for HIGH |
| Anything else                                                                     | keeps the selected evidence's own confidence                             |

ISBN uses a dedicated variant, `_isbn_assessment` (`pipeline.py:96`): no valid ISBN → `LOW`; found in exactly one
file/source → `MEDIUM`; found in ≥2 files or source kinds → `HIGH`.

Overall bundle confidence, `_merge_metadata` (`pipeline.py:152`):

```text
missing title or authors        → LOW
title=HIGH  and authors=HIGH    → HIGH
title≠LOW  and authors≠LOW      → MEDIUM
otherwise                       → LOW
```

Edition and ISBN confidence are tracked and reported independently — their absence never blocks a book that has a solid
title and author from being organized (this is why `organize` without `--yolo` can still move a book that has no ISBN at
all).

**Evidence source ranking** — used to pick which evidence "wins" when several disagree,
`_evidence_score`/`SOURCE_RANK`/`CONFIDENCE_RANK` (`pipeline.py:22`, `pipeline.py:42`):

```text
epub (baseline HIGH) > pdf (baseline MEDIUM) > filename (MEDIUM if canonical "Title - Author" pattern, else LOW)
```

### Actionable

A bundle is **actionable** only if it has a non-empty title **and** at least one author (`pipeline.py:325`) — edition
and ISBN don't matter for this. Non-actionable bundles are always placed in `skipped_bundles` and are **never** moved,
even with `--yolo`. This is the guarantee behind "`--yolo` never invents `Unknown Author`."

### Canonical naming formula

`canonical_name(title, authors, edition_text)` (`naming.py:188`):

```python
parts = [sanitize_path_part(title)]
if authors:
    parts.append(sanitize_path_part(", ".join(authors[:3])))   # only first 3 authors
if edition_text:
    parts.append(sanitize_path_part(edition_text))
return " - ".join(parts)
```

Notable rules:

- **Only the first 3 authors** are included; a 4th+ author is silently dropped from the name (confirmed by
  `tests/test_naming.py:42`).
- **Subtitle is never included** in the canonical name, even though it's captured separately on `EbookMetadata.subtitle`
  (`models.py:8`, confirmed by `tests/test_pipeline.py:108`).
- **1st/First edition is always omitted.** `format_edition` (`naming.py:165`) returns `None` for edition number `1`, so
  no dangling `" - "` appears in the name.
- **Numeric editions ≥2** are normalized to ordinal form: `"2nd edition"`, `"3rd edition"`, etc.
- **Named special editions** — `revised`, `updated`, `expanded`, `anniversary`, `special`, `deluxe`, `collector('s)` +
  `"edition"` — are kept verbatim and capitalized, e.g. `"Anniversary edition"`.
- `sanitize_path_part` (`naming.py:182`) strips filesystem-unsafe characters (`\/:*?"<>|`), collapses whitespace, strips
  trailing dots (Windows compatibility), and falls back to `"Untitled"` if the result would be empty.

## 3. Command reference

All commands are Typer subcommands of `ebook-utils` (`ebook_utils/cli.py:18`). A shared error helper, `_fail`
(`cli.py:287`), prints `Error: {message}` to stderr and exits **1** on any
`FileNotFoundError`/`FileExistsError`/`AiResolverError`/`ValueError` — this is the exit code for essentially every
failure. Every inspection/planning command supports `--json` for machine consumption.

### `info FILE`

Show raw metadata/evidence for **one** file (not a whole bundle).

```bash
ebook-utils info /downloads/some-book.epub
ebook-utils info /downloads/some-book.epub --json
```

- No mutation, ever.
- Errors (exit 1) if the file doesn't exist or the extension isn't supported.
- Human output: `Title:`, optional `Subtitle: ... (not used in canonical names)`, `Authors:`, optional `Edition:`,
  `ISBN:`, then one `Warning:` line per extraction warning.
- `--json`: full `ExtractionResult`, including every `MetadataEvidence` entry (field, value, source, source path,
  confidence) — useful for understanding _why_ a field got the confidence it did.

### `scan DIR`

List every bundle found under a directory, with field-level confidence. **Diagnostic only — never proposes moves.**

```bash
ebook-utils scan /downloads
ebook-utils scan /downloads --json
```

- Internally: `build_plan(root)` (`pipeline.py:306`), but the CLI only prints the bundles, not the plan's moves.
- Human output per bundle: `{CONFIDENCE}: {title}`, `Authors:`, `ISBN:`, a field confidence line
  (`title=…, authors=…, edition=…, isbn=…`), and `Attention:` lines for any warnings.
- Use this first on an unfamiliar folder to see how the tool currently reads it before deciding whether to trust
  `plan`/`organize` defaults or reach for `--yolo`/AI enrichment.

### `plan DIR [--output-dir DIR] [--yolo]`

Pure dry-run preview of file moves. **Never touches the filesystem.**

```bash
ebook-utils plan /downloads --output-dir /library
ebook-utils plan /downloads --output-dir /library --yolo --json
```

- Without `--yolo`: only `HIGH`-confidence bundles produce a proposed move.
- With `--yolo`: every **actionable** bundle (regardless of confidence) produces a proposed move — but this is still
  just a preview; `plan` itself never applies anything, `--yolo` here only changes what's shown.
- Output: header `"{Conservative|YOLO} dry-run: N proposed file move(s)"`, then one line per move
  (`MOVE [{confidence}]: {source} -> {target}`), then an attention section (see below).

### `organize DIR` — the primary workflow command

```bash
# Safe default: dry run of high-confidence moves only.
ebook-utils organize /downloads --output-dir /library

# Preview everything, including uncertain books, still without touching disk.
ebook-utils organize /downloads --output-dir /library --yolo --dry-run

# Actually organize every actionable book now.
ebook-utils organize /downloads --output-dir /library --yolo

# Same, but copy instead of move (originals stay in place).
ebook-utils organize /downloads --output-dir /library --yolo --copy

# Let an AI provider help resolve uncertain bundles before planning.
ebook-utils organize /downloads --output-dir /library --yolo --ai-provider openai
```

Decision logic (`cli.py:97`, `_organization_plan` at `cli.py:227`):

1. Always builds a deterministic `HIGH`-only baseline plan first via `build_plan`.
2. If `--ai-provider` is given, resolves a provider (`openai` or `claude`/`anthropic`) and enriches non-HIGH bundles
   with AI suggestions (see §5) — **before** re-planning.
3. Re-plans with `include_review=yolo` over the (possibly AI-augmented) bundles.
4. **Branch**: if `not --yolo` **or** `--dry-run` is set → print/JSON the plan and stop; nothing on disk changes.
   Otherwise → validate and apply the plan (`apply_plan`, see §7), then print what was applied plus an **attention**
   section.

Expected results:

- Default invocation: `mode: "dry-run"` in JSON, source files untouched, output directory not even created (confirmed by
  `tests/test_cli.py:9`).
- `--yolo` (no `--copy`): files are actually **moved** — the original no longer exists afterward
  (`tests/test_cli.py:35`).
- `--yolo --copy`: files are **copied** (`shutil.copy2`, preserves metadata) — the original still exists, and a
  duplicate appears at the target (`tests/test_cli.py:9`).
- Exit 1 on `AiResolverError` (bad provider / missing SDK / bad AI JSON) or on an apply-time collision
  (`FileExistsError`).

### `resolve-low-confidence DIR [--ai-provider openai] [--model MODEL]`

Print optional AI suggestions for whatever is currently in the plan's `review_bundles` (i.e. non-HIGH-confidence bundles
from a plain `build_plan`). **Read-only — never mutates, and does not feed into any subsequent plan.**

```bash
ebook-utils resolve-low-confidence /downloads
ebook-utils resolve-low-confidence /downloads --ai-provider claude --json
```

- Default provider is `openai` here (unlike `organize`, where `--ai-provider` defaults to off).
- Human output per bundle: `Title:`, `Authors:`, `Edition:` (or `(none)`), `Confidence:`, `Reasoning:`.
- `--json`: list of `{"bundle": ..., "suggestion": ...}` objects — the raw, uncapped `AiSuggestion`, not merged/capped
  the way `organize --ai-provider` merges it into a plan.

### The "attention" section

Used by `organize` (yolo-apply path) (`_print_attention`, `cli.py:263`):

- **`Attention after organization: N book(s)`** — every bundle whose overall confidence isn't `HIGH`, whether or not it
  was actually moved. This is where manual review happens, inside the already-restructured library.
- **`Not moved (missing required naming data): N book(s)`** — bundles that were skipped because they lack a title or an
  author, regardless of `--yolo`.
- **`Collision: {message}`** (stderr) — any target path claimed by more than one planned move.

## 4. Decision guide — which command for which situation

| You want to...                                                                  | Run                                                         |
| ------------------------------------------------------------------------------- | ----------------------------------------------------------- |
| Inspect one suspicious file's raw metadata                                      | `info FILE`                                                 |
| See what the tool understands about a whole folder before doing anything        | `scan DIR`                                                  |
| Preview exactly what would move, safely, no disk changes                        | `plan DIR --output-dir OUT`                                 |
| Preview _everything_, including uncertain books, no disk changes                | `plan DIR --output-dir OUT --yolo`                          |
| Do the real, safe, high-confidence-only organize run                            | `organize DIR --output-dir OUT`                             |
| Also sweep up medium/low-confidence actionable books now, review them after     | `organize DIR --output-dir OUT --yolo`                      |
| Test the full flow without touching the originals                               | `organize DIR --output-dir OUT --yolo --copy`               |
| Let an agent (Claude/Codex/etc.) decide programmatically what to do next        | `organize DIR --output-dir OUT --yolo --dry-run --json`     |
| Get AI opinions on the borderline books without committing to anything          | `resolve-low-confidence DIR`                                |
| Let AI suggestions feed directly into the plan (still capped at MEDIUM)         | `organize DIR --output-dir OUT --yolo --ai-provider openai` |

## 5. AI provider integration (`ebook_utils/ai.py`)

- `get_resolver(provider, model=None)` (`ai.py:96`) dispatches `"openai"` → `OpenAiResolver`, `"claude"`/`"anthropic"` →
  `ClaudeResolver`; anything else raises `AiResolverError`.
- Model defaults: `gpt-4.1-mini` (override via `EBOOK_UTILS_OPENAI_MODEL` or `--model`) and `claude-3-5-haiku-latest`
  (override via `EBOOK_UTILS_CLAUDE_MODEL` or `--model`).
- Both resolvers send the same prompt, `build_review_prompt` (`ai.py:19`): the full bundle evidence as JSON, asking for
  `{title, authors, edition_text, confidence, reasoning}`, explicitly instructed **"Do not invent authors."**
- Response parsing (`parse_ai_suggestion`, `ai.py:30`) is defensive: unrecognized confidence strings fall back to `LOW`;
  non-list `authors` becomes `[]`.
- Requires optional extras: `uv sync --extra ai-openai` or `--extra ai-claude`; missing SDK raises `AiResolverError`
  with an install hint.
- **Hard rule — AI confidence is capped at MEDIUM.** In `resolve_bundles_with_ai` (`pipeline.py:254`), even if the model
  claims `HIGH`, it's downgraded: `confidence = MEDIUM if suggestion.confidence == HIGH else suggestion.confidence`
  (`pipeline.py:279`). AI-touched bundles therefore always land in `review_bundles`, and moving them still requires
  `--yolo`. AI is only ever consulted for bundles **not already `HIGH`** — it can never override an already-confident
  bundle.

## 6. Extraction details per format

- **EPUB** (`EpubExtractor`, `extractor.py:90`): reads Dublin Core + OPF metadata via `ebooklib`. Embedded EPUB metadata
  gets a `HIGH` baseline confidence (`extractor.py:52`). Uses EPUB3 title-type/role refinements when present
  (distinguishing "main" title from "subtitle", and filtering creators to role `"aut"` only). Authors pass through
  `is_non_author_contributor` (`naming.py:89`), which drops editors/translators — including Polish-market terms (`red.`,
  `redaktor`, `tłum.`), reflecting Helion/ebookpoint-style sources seen in `tests/assets/`.
- **PDF** (`PdfExtractor`, `extractor.py:184`): embedded metadata gets only a `MEDIUM` baseline confidence, since PDF
  metadata is far less reliable. Title extraction filters out publisher-embedded "asset" titles (e.g.
  `packt_logo_ill_01_orange`, anything ending in `.eps/.ai/.svg/.psd`, or containing "logo"/"icon") via
  `_looks_like_asset_title` (`extractor.py:22`). ISBNs are scanned from document metadata **and** the extracted text of
  the first 5 pages. Edition is always derived from the file path (`edition_from_path`), since PDFs have no reliable
  embedded edition field.
- **Filename fallback** (`FilenameExtractor` via `parse_filename_metadata`, `naming.py:137`): used whenever a real
  extractor throws, or as a source of corroborating/competing evidence otherwise. Confidence is `MEDIUM` only if the
  filename matches the canonical `Title - Author[ - Edition]` pattern with both title and author present; otherwise
  `LOW`. Never exceeds `MEDIUM` on its own.

## 7. Safety mechanics

- **Preflight before mutation.** `validate_plan` (`pipeline.py:363`) checks every move's source still exists, flags
  cross-bundle target collisions, and flags any target that already exists on disk and isn't itself one of the planned
  sources.
- **All-or-nothing apply.** `apply_plan` (`pipeline.py:383`) runs `validate_plan` first; if anything fails, it raises
  `FileExistsError` with all errors joined and performs **zero** moves.
- **Transactional rollback.** If a move fails partway through a batch, every already-applied move is reversed in reverse
  order (unlink the copy, or move the original back) before the original exception is re-raised.
- **`--copy` vs move.** Default is a real `shutil.move` (relocates the file). `--copy` uses `shutil.copy2` (preserves
  metadata, leaves the source in place) — rollback logic differs accordingly.
- **In-bundle name collisions.** If two files in the same bundle would produce the same target name, the tool tries
  `"{name} ({ext})"` first, then `"{name} (2)"`, `"(3)"`, etc.

## 8. Known gaps / testing notes

- `tests/test_cli.py` currently has only **2 tests**, both covering `organize` (dry-run-by-default behavior,
  `--yolo --copy`, `--yolo` real move). There is currently no CLI-level test coverage for `info`, `scan`, `plan`, or
  `resolve-low-confidence` — worth keeping in mind if you're relying on those commands for something critical.
- MOBI, Notion sync, and Kindle delivery remain intentionally out of scope for the organization workflow (per
  `README.md`) — there's no MOBI extractor and no Notion/Kindle integration code.
- `tests/assets/` contains real-world sample fixtures (two PDFs, two Helion/ebookpoint-style Polish EPUBs) used by the
  test suite — useful reference points for understanding the filename/author-filtering edge cases described in §6.
