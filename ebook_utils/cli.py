from pathlib import Path
from typing import Annotated

import typer

from .ai import AiResolverError, get_resolver
from .extractor import extract_result, get_extractor
from .naming import ordinal_suffix
from .pipeline import (
    apply_plan,
    build_plan,
    dumps_json,
    resolve_bundles_with_ai,
    to_jsonable,
)

app = typer.Typer(name="ebook-utils", no_args_is_help=True)


@app.callback()
def callback() -> None:
    """Organize EPUB and PDF downloads into a consistent local library."""


@app.command()
def info(
    ebook_file: Annotated[Path, typer.Argument(...)],
    json_output: Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON.")] = False,
) -> None:
    """Display raw metadata evidence for one ebook file."""
    if not ebook_file.exists():
        typer.echo(f"Error: file not found: {ebook_file}", err=True)
        raise typer.Exit(1)
    try:
        get_extractor(ebook_file)
    except ValueError as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1)

    result = extract_result(ebook_file)
    if json_output:
        typer.echo(dumps_json(result))
        return

    metadata = result.metadata
    typer.echo(f"Title:    {metadata.title or '(none found)'}")
    if metadata.subtitle:
        typer.echo(f"Subtitle: {metadata.subtitle} (not used in canonical names)")
    typer.echo(f"Authors:  {', '.join(metadata.authors) if metadata.authors else '(none found)'}")
    if metadata.edition_text:
        typer.echo(f"Edition:  {metadata.edition_text}")
    elif metadata.edition is not None and metadata.edition > 1:
        typer.echo(f"Edition:  {metadata.edition}{ordinal_suffix(metadata.edition)} edition")
    typer.echo(f"ISBN:     {', '.join(metadata.isbns) if metadata.isbns else '(none found)'}")
    for warning in result.warnings:
        typer.echo(f"Warning: {warning}")


@app.command()
def scan(
    root: Annotated[Path, typer.Argument(...)],
    json_output: Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON.")] = False,
) -> None:
    """Inspect books and show the confidence of every naming field."""
    try:
        pipeline_plan = build_plan(root)
    except FileNotFoundError as error:
        _fail(error)
    if json_output:
        typer.echo(dumps_json(pipeline_plan.bundles))
        return
    _print_bundles(pipeline_plan.bundles)


@app.command()
def plan(
    root: Annotated[Path, typer.Argument(...)],
    output_dir: Annotated[Path | None, typer.Option("--output-dir", help="Destination library directory.")] = None,
    yolo: Annotated[
        bool,
        typer.Option("--yolo", help="Also propose moves for actionable medium/low-confidence books."),
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON.")] = False,
) -> None:
    """Print a non-mutating organization plan (a dry run)."""
    try:
        pipeline_plan = build_plan(root, output_dir=output_dir, include_review=yolo)
    except FileNotFoundError as error:
        _fail(error)
    if json_output:
        typer.echo(dumps_json(pipeline_plan))
        return
    _print_plan(pipeline_plan, yolo=yolo)


@app.command()
def organize(
    root: Annotated[Path, typer.Argument(...)],
    output_dir: Annotated[Path | None, typer.Option("--output-dir", help="Destination library directory.")] = None,
    yolo: Annotated[
        bool,
        typer.Option("--yolo", help="Apply every actionable proposal, including uncertain books."),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview YOLO proposals without changing files."),
    ] = False,
    copy: Annotated[bool, typer.Option("--copy", help="Copy files instead of moving them in YOLO mode.")] = False,
    ai_provider: Annotated[
        str | None,
        typer.Option("--ai-provider", help="Optional built-in resolver: openai or claude."),
    ] = None,
    model: Annotated[str | None, typer.Option("--model", help="Optional AI model override.")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON.")] = False,
) -> None:
    """Dry-run by default; use --yolo to organize the actionable books now."""
    try:
        pipeline_plan = _organization_plan(root, output_dir, yolo=yolo, ai_provider=ai_provider, model=model)
    except (AiResolverError, FileNotFoundError) as error:
        _fail(error)

    if not yolo or dry_run:
        if json_output:
            typer.echo(dumps_json({"mode": "dry-run", "plan": pipeline_plan}))
        else:
            _print_plan(pipeline_plan, yolo=yolo)
        return

    try:
        applied = apply_plan(pipeline_plan, copy=copy)
    except FileExistsError as error:
        _fail(error)
    result = {"mode": "yolo", "applied": applied, "plan": pipeline_plan}
    if json_output:
        typer.echo(dumps_json(result))
        return
    verb = "Copied" if copy else "Moved"
    for move in applied:
        typer.echo(f"{verb}: {move.source} -> {move.target}")
    _print_attention(pipeline_plan)


@app.command("resolve-low-confidence")
def resolve_low_confidence(
    root: Annotated[Path, typer.Argument(...)],
    provider: Annotated[str, typer.Option("--ai-provider", help="AI provider: openai or claude.")] = "openai",
    model: Annotated[str | None, typer.Option("--model", help="Provider model override.")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON.")] = False,
) -> None:
    """Show optional provider suggestions without moving any files."""
    try:
        pipeline_plan = build_plan(root)
        resolver = get_resolver(provider, model=model)
        suggestions = [
            {"bundle": to_jsonable(bundle), "suggestion": to_jsonable(resolver.resolve(bundle))}
            for bundle in pipeline_plan.review_bundles
        ]
    except (AiResolverError, FileNotFoundError) as error:
        _fail(error)

    if json_output:
        typer.echo(dumps_json(suggestions))
        return
    for item in suggestions:
        suggestion = item["suggestion"]
        typer.echo(f"Title: {suggestion.get('title') or '(unknown)'}")
        typer.echo(f"Authors: {', '.join(suggestion.get('authors') or []) or '(unknown)'}")
        typer.echo(f"Edition: {suggestion.get('edition_text') or '(none)'}")
        typer.echo(f"Confidence: {suggestion.get('confidence')}")
        typer.echo(f"Reasoning: {suggestion.get('reasoning')}")
        typer.echo()


def _organization_plan(
    root: Path,
    output_dir: Path | None,
    *,
    yolo: bool,
    ai_provider: str | None,
    model: str | None,
):
    deterministic = build_plan(root, output_dir=output_dir)
    if not ai_provider:
        return build_plan(root, output_dir=output_dir, include_review=yolo, bundles=deterministic.bundles)
    resolver = get_resolver(ai_provider, model=model)
    bundles = resolve_bundles_with_ai(deterministic.bundles, resolver)
    return build_plan(root, output_dir=output_dir, include_review=yolo, bundles=bundles)


def _print_bundles(bundles: list) -> None:
    for bundle in bundles:
        metadata = bundle.metadata
        typer.echo(f"{metadata.confidence.value.upper()}: {metadata.title}")
        typer.echo(f"  Authors: {', '.join(metadata.authors) if metadata.authors else '(missing)'}")
        typer.echo(f"  ISBN: {', '.join(metadata.isbns) if metadata.isbns else '(none)'}")
        typer.echo("  Field confidence: " + _field_confidence_text(bundle))
        for warning in metadata.warnings:
            typer.echo(f"  Attention: {warning}")


def _print_plan(pipeline_plan, *, yolo: bool) -> None:
    mode = "YOLO dry-run" if yolo else "Conservative dry-run"
    typer.echo(f"{mode}: {len(pipeline_plan.moves)} proposed file move(s)")
    for move in pipeline_plan.moves:
        bundle = next(bundle for bundle in pipeline_plan.bundles if move.source in bundle.files)
        typer.echo(f"MOVE [{bundle.metadata.confidence.value}]: {move.source} -> {move.target}")
    _print_attention(pipeline_plan)


def _print_attention(pipeline_plan) -> None:
    if pipeline_plan.review_bundles:
        typer.echo(f"Attention after organization: {len(pipeline_plan.review_bundles)} book(s)")
        for bundle in pipeline_plan.review_bundles:
            typer.echo(
                f"  [{bundle.metadata.confidence.value}] {bundle.metadata.title} — "
                + _field_confidence_text(bundle)
            )
    if pipeline_plan.skipped_bundles:
        typer.echo(f"Not moved (missing required naming data): {len(pipeline_plan.skipped_bundles)} book(s)")
        for bundle in pipeline_plan.skipped_bundles:
            typer.echo(f"  {bundle.metadata.title}: {', '.join(bundle.metadata.warnings)}")
    for collision in pipeline_plan.collisions:
        typer.echo(f"Collision: {collision}", err=True)


def _field_confidence_text(bundle) -> str:
    fields = bundle.metadata.field_confidence
    return ", ".join(
        f"{field}={fields.get(field, 'low').value if hasattr(fields.get(field, 'low'), 'value') else fields.get(field, 'low')}"
        for field in ("title", "authors", "edition", "isbn")
    )


def _fail(error: Exception) -> None:
    typer.echo(f"Error: {error}", err=True)
    raise typer.Exit(1)


if __name__ == "__main__":
    app()
