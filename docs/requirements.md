# ebook-utils – Requirements

## Overview

`ebook-utils` helps organize downloaded ebook collections (primarily from Humble Bundle) into a tidy, consistent
library. Users receive folders of EPUB and PDF files with machine-generated, non-human-readable names; the tool extracts
metadata from embedded file contents and filenames, groups format variants of the same book together, and renames and
moves files into a canonical directory structure.

High-confidence matches are processed automatically. Low-confidence cases are held for review, optionally with
AI-assisted metadata suggestions. The tool is designed to be used both interactively by the owner and by external AI
agents — all commands produce machine-readable structured output.

Future milestones include syncing library metadata to a Notion database and preparing files for Kindle delivery.

## Functional Requirements

### 1. File Discovery and Format Support

- [ ] **1.1**: The tool must discover all ebook files in a given directory tree recursively, including files in
      subdirectories.
    - **Status**: Implemented

- [ ] **1.2**: The tool must support EPUB and PDF formats with equivalent extraction, grouping, and rename behavior.
    - **Status**: Implemented

- [ ] **1.3**: The tool must support MOBI format with equivalent extraction, grouping, and rename behavior to EPUB and
      PDF.
    - **Status**: Not yet implemented

### 2. Metadata Extraction

- [ ] **2.1**: The tool must extract book title, author names, and edition from the embedded metadata of EPUB files.
    - **Status**: Implemented

- [ ] **2.2**: The tool must extract book title, author names, and edition from the embedded metadata of PDF files.
    - PDF files may contain embedded asset or design-tool titles that do not represent the book; the tool must filter
      these out and prefer document-level metadata.
    - **Status**: Implemented

- [ ] **2.3**: When embedded metadata is unavailable or extraction fails, the tool must fall back to parsing the
      filename to derive title, author names, and edition.
    - **Status**: Implemented

- [ ] **2.4**: The tool must assign a confidence level (high, medium, or low) to each extracted bundle, reflecting how
      reliably the metadata was determined.
    - Confidence is determined by the source of evidence (embedded file metadata is more reliable than filename) and by
      completeness (both title and authors must be present for high confidence).
    - **Status**: Implemented

### 3. Grouping and Deduplication

- [ ] **3.1**: The tool must group different format variants of the same book (e.g., EPUB and PDF editions) into a
      single bundle for unified processing.
    - Grouping is based on normalized title matching across all discovered files.
    - **Status**: Implemented

- [ ] **3.2**: When the same file appears in multiple input locations, the tool must recognize it as a single item
      rather than creating duplicate bundles.
    - **Status**: Not yet implemented

- [ ] **3.3**: When two bundles would result in the same target name, the tool must report the collision clearly and
      offer a resolution strategy, rather than stopping with an unhandled error.
    - **Status**: Partial — currently stops with an error; no resolution strategy is offered

### 4. Planning and Applying Changes

- [ ] **4.1**: The tool must generate a rename-and-move plan that produces a canonical output name in the format
      `Title - Author1, Author2 - Edition`, without modifying any files.
    - Up to three author names are included in the output name; additional authors are omitted.
    - **Status**: Implemented

- [ ] **4.2**: The user must be able to preview the full plan — including all planned moves and all bundles held for
      review — before any files are modified.
    - **Status**: Implemented

- [ ] **4.3**: The tool must apply the plan by moving files to their target location in a structured output directory. A
      lossless copy mode must also be available to leave the originals intact.
    - **Status**: Implemented

- [ ] **4.4**: The tool must only automatically apply changes to high-confidence bundles. Medium- and low-confidence
      bundles must be held for manual review.
    - **Status**: Implemented

### 5. AI-Assisted Review

- [ ] **5.1**: For bundles held for review, the tool must be able to query an AI assistant to suggest corrected title,
      author, and edition metadata.
    - At least two AI provider options must be supported.
    - AI suggestions are advisory; they must not automatically authorize any file mutations.
    - **Status**: Implemented (advisory only)

- [ ] **5.2**: The user must be able to inspect AI suggestions, selectively approve them, and then direct the tool to
      incorporate approved metadata into a new plan and apply it.
    - **Status**: Not yet implemented

### 6. Output and Integrations

- [ ] **6.1**: All commands must emit their results in a machine-readable structured format to support scripting and AI
      agent integration.
    - **Status**: Implemented

- [ ] **6.2**: The tool must generate a manifest file listing each planned file's current path, target path, title,
      authors, and edition, for use with external Kindle preparation tools.
    - **Status**: Implemented

- [ ] **6.3**: The tool must be able to sync the resulting library metadata (title, authors, edition, and file location)
      to a configured external knowledge base for reading-list and collection tracking.
    - **Status**: Not yet implemented

## Non-Functional Requirements

### 1. Safety and Control

- [ ] **1.1**: The tool must never modify, move, or delete any file without an explicit user or agent action. Planning
      and preview steps must be strictly read-only.
    - **Status**: Implemented

- [ ] **1.2**: AI suggestions must never be applied to files automatically. Applying AI-suggested metadata must require
      a separate, deliberate approval step.
    - **Status**: Implemented (AI step is advisory only; apply step requires separate invocation)

### 2. Integration and Extensibility

- [ ] **2.1**: The core scanning, extraction, grouping, and planning logic must be accessible as a programmable
      interface, independently of the command-line layer, to support future terminal UI and agent integrations.
    - **Status**: Implemented

## Technical Constraints and Requirements

### 1. Dependencies and Portability

- [ ] **1.1**: AI provider integrations must be optional at install time. The base installation must have no AI SDK
      dependencies; AI support must be available as an opt-in extra.
    - **Status**: Implemented

- [ ] **1.2**: The tool must run on a standard Python environment without requiring a container or a specific operating
      system.
    - **Status**: Implemented

---

## Supplementary: Gap Analysis

The following items are not yet implemented and represent the gap between current capabilities and the full desired
workflow.

### Critical path — AI review loop (FR 5.2)

The most important missing piece is the ability to approve AI suggestions and feed them back into an apply pass. The
desired flow is:

1. Run a plan pass → receive high-confidence moves and a review list
2. Run an AI review pass → receive metadata suggestions per uncertain bundle
3. Inspect suggestions → approve some, reject others
4. Run a second apply pass that incorporates the approved metadata

Suggested approach: write low-confidence bundles and AI suggestions to a durable review file, then add an `apply-review`
command that reads approved entries and executes those moves.

### Format coverage — MOBI (FR 1.3)

The extractor architecture is designed to support additional formats via subclassing. MOBI support requires adding a new
extractor and registering the format extension. Priority depends on whether MOBI files appear in the owner's bundle
downloads.

### File hygiene — duplicates (FR 3.2) and collisions (FR 3.3)

- **Duplicates**: The same book downloaded twice into different subdirectories produces two separate bundles with the
  same canonical name. A post-grouping deduplication pass keyed on canonical name would catch this.
- **Collisions**: When a target path already exists, the tool currently stops with an error. A collision report listing
  all conflicts with resolution options (skip, overwrite, or rename) would make the tool safe to run non-interactively.

### Notion integration (FR 6.3)

This is an explicitly later milestone. The structured output from plan and apply passes already provides the data
needed. What remains is a configured Notion client, a database property mapping, and the sync command implementation.
See `docs/roadmap.md` for the full scope.
