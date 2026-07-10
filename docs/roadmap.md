# Roadmap

## Implemented initial workflow

- Recursive EPUB/PDF discovery and canonical directory/file planning.
- Title, author, edition, filename, and locally validated ISBN evidence.
- Per-field and overall confidence with explicit reasons.
- Conservative dry-run plus `--yolo` organization of all actionable books.
- Optional OpenAI/Claude enrichment in YOLO mode; AI values remain attention items.
- Target collision preflight and rollback for unexpected apply failures.

## Deliberate constraints

- A title and at least one author are required for a canonical move; the tool never invents a placeholder author.
- Subtitles are excluded from canonical names.
- First edition is omitted; only recognized non-first/special editions are rendered.
- PDF text is sampled only to identify valid ISBNs; it is not yet a general title-page parser.

## Next improvements

1. Add content hashes for duplicate detection and an undo journal for completed moves.
2. Improve PDF title-page extraction and cross-format fuzzy matching when ISBN is absent.
3. Preserve contributor roles as metadata and improve international person-name normalization.
4. Add catalog/source connectors that an agent can cite as corroborating evidence.
5. Add MOBI/AZW3 support, then optional Notion and Kindle-delivery integrations.
