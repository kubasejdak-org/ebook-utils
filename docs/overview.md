# Architecture

The core is a deterministic local pipeline, independent of the CLI and optional AI SDKs:

```text
EPUB/PDF + filename → extraction evidence → grouping → field confidence → plan → dry-run or YOLO apply
```

`extractor.py` obtains embedded data and filename fallback. `pipeline.py` groups variants, selects canonical metadata,
calculates field-level confidence, creates safe moves, preflights collisions, and rolls back an unexpected partial
apply. `cli.py` exposes that logic with Typer.

Confidence is evidence-aware rather than a property of the file type alone. A valid ISBN is checksum-validated locally.
An EPUB metadata value is useful but normally medium until corroborated; a filename alone is never high. Conflicts among
usable sources are low confidence and stay visible in the attention list.

The user-facing flow avoids review artifacts. `organize` is a dry-run by default and `--yolo` executes all actionable
proposals. An external AI agent can consume `--json`; optional OpenAI/Claude adapters are available for autonomous
enrichment, but their suggestions are never silently promoted to high confidence.
