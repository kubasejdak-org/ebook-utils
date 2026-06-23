from pathlib import Path
from typing import Annotated

import typer

from .ai import AiResolverError, get_resolver
from .extractor import extract_result, get_extractor
from .models import Confidence
from .naming import ordinal_suffix
from .pipeline import apply_plan, build_plan, dumps_json, prepare_kindle_manifest, to_jsonable

app = typer.Typer(name="ebook-utils", no_args_is_help=True)


@app.callback()
def callback() -> None:
    """Utility tools for working with ebook files."""


@app.command()
def info(
    ebook_file: Annotated[Path, typer.Argument(...)],
    json_output: Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON.")] = False,
) -> None:
    """Display metadata evidence for one ebook file."""
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
    typer.echo(f"Title:    {metadata.title}")
    if metadata.subtitle:
        typer.echo(f"Subtitle: {metadata.subtitle}")
    authors_str = ", ".join(metadata.authors) if metadata.authors else "(none found)"
    typer.echo(f"Authors:  {authors_str}")
    if metadata.edition_text:
        typer.echo(f"Edition:  {metadata.edition_text}")
    elif metadata.edition is not None and metadata.edition > 1:
        n = metadata.edition
        typer.echo(f"Edition:  {n}{ordinal_suffix(n)} edition")
    if result.warnings:
        typer.echo("Warnings:")
        for warning in result.warnings:
            typer.echo(f"  - {warning}")


@app.command()
def scan(
    root: Annotated[Path, typer.Argument(...)],
    json_output: Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON.")] = False,
) -> None:
    """Scan raw ebook files and show grouped bundle candidates."""
    plan = build_plan(root)
    if json_output:
        typer.echo(dumps_json(plan.bundles))
        return
    _print_bundles(plan.bundles)


@app.command()
def plan(
    root: Annotated[Path, typer.Argument(...)],
    output_dir: Annotated[
        Path | None, typer.Option("--output-dir", help="Directory where grouped files should be placed.")
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON.")] = False,
) -> None:
    """Build a rename/grouping plan without changing files."""
    pipeline_plan = build_plan(root, output_dir=output_dir)
    if json_output:
        typer.echo(dumps_json(pipeline_plan))
        return
    _print_plan(pipeline_plan)


@app.command("apply")
def apply_command(
    root: Annotated[Path, typer.Argument(...)],
    output_dir: Annotated[
        Path | None, typer.Option("--output-dir", help="Directory where grouped files should be placed.")
    ] = None,
    copy: Annotated[bool, typer.Option("--copy", help="Copy files instead of moving them.")] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON.")] = False,
) -> None:
    """Apply high-confidence rename/grouping moves and leave review cases untouched."""
    pipeline_plan = build_plan(root, output_dir=output_dir)
    try:
        applied = apply_plan(pipeline_plan, copy=copy)
    except FileExistsError as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1)
    if json_output:
        typer.echo(dumps_json({"applied": applied, "review_bundles": pipeline_plan.review_bundles}))
        return
    for move in applied:
        verb = "Copied" if copy else "Moved"
        typer.echo(f"{verb}: {move.source} -> {move.target}")
    if pipeline_plan.review_bundles:
        typer.echo(f"Review required for {len(pipeline_plan.review_bundles)} bundle(s).")


@app.command("resolve-low-confidence")
def resolve_low_confidence(
    root: Annotated[Path, typer.Argument(...)],
    provider: Annotated[str, typer.Option("--ai-provider", help="AI provider: openai or claude.")] = "openai",
    model: Annotated[str | None, typer.Option("--model", help="Provider model override.")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON.")] = False,
) -> None:
    """Ask an AI provider for advisory suggestions for low-confidence bundles."""
    pipeline_plan = build_plan(root)
    try:
        resolver = get_resolver(provider, model=model)
        suggestions = [
            {"bundle": to_jsonable(bundle), "suggestion": to_jsonable(resolver.resolve(bundle))}
            for bundle in pipeline_plan.review_bundles
        ]
    except AiResolverError as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1)

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
        typer.echo("")


@app.command("prepare-kindle")
def prepare_kindle(
    root: Annotated[Path, typer.Argument(...)],
    manifest: Annotated[Path, typer.Option("--manifest", help="CSV manifest path.")] = Path("kindle-manifest.csv"),
    output_dir: Annotated[
        Path | None, typer.Option("--output-dir", help="Directory where grouped files should be placed.")
    ] = None,
) -> None:
    """Create a Send-to-Kindle preparation manifest for high-confidence bundles."""
    pipeline_plan = build_plan(root, output_dir=output_dir)
    output_path = prepare_kindle_manifest(pipeline_plan, manifest)
    typer.echo(f"Wrote Kindle manifest: {output_path}")
    if pipeline_plan.review_bundles:
        typer.echo(f"Skipped {len(pipeline_plan.review_bundles)} review bundle(s).")


@app.command("sync-notion")
def sync_notion() -> None:
    """Placeholder for Notion sync once database schema/config is supplied."""
    typer.echo(
        "Notion sync is not implemented yet. The pipeline now emits structured plans; the next step is adding configured database schema mapping.",
        err=True,
    )
    raise typer.Exit(2)


def _print_bundles(bundles: list) -> None:
    for bundle in bundles:
        metadata = bundle.metadata
        typer.echo(f"{metadata.confidence.value.upper()}: {metadata.title}")
        typer.echo(f"  Authors: {', '.join(metadata.authors) if metadata.authors else '(missing)'}")
        if metadata.edition_text:
            typer.echo(f"  Edition: {metadata.edition_text}")
        for file_path in bundle.files:
            typer.echo(f"  File: {file_path}")
        for warning in metadata.warnings:
            typer.echo(f"  Warning: {warning}")


def _print_plan(pipeline_plan) -> None:
    typer.echo(f"Bundles: {len(pipeline_plan.bundles)}")
    typer.echo(f"High-confidence moves: {len(pipeline_plan.moves)}")
    typer.echo(f"Review bundles: {len(pipeline_plan.review_bundles)}")
    for move in pipeline_plan.moves:
        typer.echo(f"MOVE: {move.source} -> {move.target}")
    if pipeline_plan.review_bundles:
        typer.echo("Review required:")
        for bundle in pipeline_plan.review_bundles:
            typer.echo(f"  - {bundle.metadata.title} [{bundle.metadata.confidence.value}]")


if __name__ == "__main__":
    app()
