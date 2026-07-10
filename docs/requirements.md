# Current Requirements

## Initial organization workflow

- Discover EPUB and PDF files recursively from a raw download directory.
- Extract title, author, edition, and ISBN evidence from embedded metadata and filenames.
- Group likely format variants by shared valid ISBN or compatible normalized title/author/edition data.
- Create a folder and same-basename files using `Title - Authors [- Edition]`.
- Use up to three `First Name Last Name` authors; omit subtitles and first edition; preserve recognized special
  editions.

## Confidence and automation

- Report `high`, `medium`, or `low` confidence for title, authors, edition, ISBN, and the final bundle.
- Explain selected evidence, conflicts, and missing fields in both text and JSON output.
- A filename alone must never become high confidence.
- Default organization is read-only. `--yolo` explicitly applies every actionable proposal, including uncertain books.
- Missing title/author data is never replaced with a fabricated canonical name; those bundles remain in the attention
  list.
- The attention list is produced after YOLO organization so manual review happens in the structured library.

## Safety

- A plan is built before mutation.
- Every source and target is preflighted before mutation; existing and duplicate targets stop the apply pass.
- An unexpected failed apply rolls completed moves back where possible.
- `--copy` supports lossless validation.
- When the output library is nested under the input directory, it is excluded from later scans.

## AI and agent integration

- The base tool is usable by external agents through stable JSON stdout; no user-managed review files are required.
- OpenAI and Claude integrations are optional extras for autonomous enrichment in `organize --yolo`.
- AI suggestions remain medium-or-lower confidence and are shown in the post-organization attention list.

## Deferred

MOBI/AZW3 extraction, content-hash duplicate detection, undo journals, rich catalog corroboration, Notion
synchronization, and Kindle delivery remain later work.
