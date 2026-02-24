from pathlib import Path
from typing import Annotated

import typer

from .extractor import get_extractor

app = typer.Typer(name="ebook-utils", no_args_is_help=True)


def _ordinal_suffix(n: int) -> str:
    if 11 <= (n % 100) <= 13:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


@app.callback()
def callback() -> None:
    """Utility tools for working with ebook files."""


@app.command()
def info(ebook_file: Annotated[Path, typer.Argument(...)]) -> None:
    """Display metadata for an ebook file."""
    if not ebook_file.exists():
        typer.echo(f"Error: file not found: {ebook_file}", err=True)
        raise typer.Exit(1)

    try:
        extractor = get_extractor(ebook_file)
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)

    metadata = extractor.extract(ebook_file)

    typer.echo(f"Title:    {metadata.title}")
    if metadata.subtitle:
        typer.echo(f"Subtitle: {metadata.subtitle}")
    authors_str = ", ".join(metadata.authors) if metadata.authors else "(none found)"
    typer.echo(f"Authors:  {authors_str}")
    if metadata.edition is not None and metadata.edition > 1:
        n = metadata.edition
        typer.echo(f"Edition:  {n}{_ordinal_suffix(n)} edition")
