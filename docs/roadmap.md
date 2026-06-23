# Assumptions, Known Problems, And Roadmap

## Assumptions

- The first supported formats are EPUB and PDF.
- MOBI support will be added later behind the same extractor interface.
- EPUB OPF/DC metadata is generally more reliable than PDF metadata.
- PDF metadata can be contaminated by embedded assets, especially from design tools and publisher graphics.
- High-confidence means title and authors are present and selected from strong evidence.
- Low-confidence cases should not be renamed or grouped without review.
- AI is used only as a postprocessor for uncertain cases unless policy changes later.
- Future terminal UI should consume the same service layer and JSON/result models as the CLI.

## Known Problems

- Bundle grouping is currently title-key based and basic. It will miss cases where EPUB and PDF have different title
  strings or filenames only contain slugs.
- Filename parsing is intentionally conservative. Humble Bundle filenames with title and author in one long slug may
  still need AI review.
- PDF extraction avoids obvious asset metadata, but it is not a complete document-level XMP parser.
- `apply` can move high-confidence files, but there is no undo command yet. Use `plan` first and consider `--copy` while
  validating behavior.
- Collision handling prevents overwrites, but it does not yet produce a rich collision-resolution report.
- AI suggestions are not fed back into the planning pipeline automatically.
- Amazon lookup is not implemented.
- Notion schema mapping and writes are not implemented.
- Kindle support currently means manifest/preparation only, not upload automation.
- There is no Textual UI yet. The code is structured to make one easier later.
- `uv.lock` changed because test dependencies were installed through `uv run --extra test`.

## Future Work

### Metadata And Grouping

- Improve grouping with fuzzy title matching and author-aware matching.
- Add multi-format grouping when one file has strong EPUB metadata and another has only filename evidence.
- Add MOBI extraction support.
- Add richer author normalization, including editor prefixes such as `red.` and publisher-specific conventions.
- Add a review report file for low-confidence cases.

### AI Integration

- Add a command that writes AI suggestions to a review artifact.
- Add an approval flow that can promote validated AI suggestions into a new plan.
- Add stricter structured-output schemas for OpenAI and Claude responses.
- Add provider config defaults for provider, model, and review policy.

### Amazon And Notion

- Implement Amazon search and product-page extraction for page count, release year, URL, and ISBN where available.
- Add deterministic confidence rules for accepting Amazon matches.
- Add Notion config with database/data-source URL and property mapping.
- Fetch Notion schema before writes and fail clearly when required properties are missing.
- Match existing Notion book entries before creating new ones.
- Mark owned books and initialize reading/progress tracking fields.

### Kindle Workflow

- Expand `prepare-kindle` from CSV manifest to staged output folders.
- Decide whether Kindle upload remains manual, email-based, connected-device based, or browser-automated.
- Add collection mapping if local folders should mirror Kindle collections.

### Terminal UI

- Keep pipeline services independent from Typer.
- Add progress/event models for long scans.
- Build a Textual UI around bundle list, confidence filters, evidence view, AI suggestions, and apply/skip actions.

## Recommended Next Implementation Step

The next practical step is to improve the review loop:

1. Write low-confidence cases to a durable JSON review file.
2. Allow AI suggestions to be stored next to deterministic evidence.
3. Add a command that accepts approved suggestions and rebuilds the move plan.

This will make the tool useful on real Humble Bundle dumps before adding Amazon and Notion integrations.
