from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from pikepdf import Pdf

from pdf_outline.binder import (
    bind_pdfs,
    build_entries_from_paths,
    parse_entry,
)
from pdf_outline.manifest import load_manifest
from pdf_outline.outline import extract_toc
from pdf_outline.outline import set_toc as set_toc_outline
from pdf_outline.titles import slugify_title

app = typer.Typer(
    help="Merge PDFs in CLI order and generate outline titles from filenames.",
)


@app.command()
def bind(
    output: Annotated[
        Path,
        typer.Option("--output", help="Path for the merged PDF."),
    ],
    manifest: Annotated[
        Path | None,
        typer.Option(
            "--manifest",
            help="Path to a JSON manifest with title/path entries.",
        ),
    ] = None,
    entry: Annotated[
        list[str] | None,
        typer.Option("--entry", help="Explicit entry in Title::path format."),
    ] = None,
    inputs: Annotated[
        list[Path] | None,
        typer.Argument(help="Input PDF paths in merge order."),
    ] = None,
) -> None:
    """Merge PDFs in CLI order."""
    try:
        if manifest is not None:
            if entry or inputs:
                raise ValueError("exactly one input mode must be used")
            entries = load_manifest(manifest)
        elif entry:
            if inputs:
                raise ValueError("exactly one input mode must be used")
            entries = [parse_entry(item) for item in entry]
        else:
            if not inputs:
                raise ValueError("exactly one input mode must be used")
            entries = build_entries_from_paths(inputs)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    bind_pdfs(entries, output)


@app.command()
def toc(
    input_pdf: Annotated[Path, typer.Argument(help="Path to the input PDF.")],
    as_json: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
) -> None:
    """Extract and print the table of contents from a PDF."""
    entries = extract_toc(input_pdf)
    if as_json:
        data = [entry.model_dump() for entry in entries]
        typer.echo(json.dumps(data, indent=2))
    else:
        for entry in entries:
            indent = "  " * (entry.level - 1)
            idx_str = f"[Idx: {entry.index:02d}] " if entry.index is not None else ""
            count_str = (
                f"[end: {entry.end_page}] ({entry.page_count} pages)"
                if entry.page_count is not None
                else ""
            )
            typer.echo(
                f"{idx_str}{indent}{entry.level}  {entry.title:<40} "
                f"p.{entry.start_page} {count_str}"
            )


@app.command(name="set-toc")
def set_toc_cmd(
    input_pdf: Annotated[Path, typer.Argument(help="Path to the input PDF.")],
    manifest: Annotated[
        Path,
        typer.Option("--manifest", help="JSON manifest file with TOC entries."),
    ],
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Output path. Defaults to overwriting input."),
    ] = None,
) -> None:
    """Write a new table of contents into a PDF."""
    try:
        entries = load_manifest(manifest)
    except Exception as exc:
        raise typer.BadParameter(f"Failed to load manifest: {exc}") from exc

    set_toc_outline(input_pdf, entries, output)


@app.command()
def split(
    input_pdf: Annotated[Path, typer.Argument(help="Path to the input PDF.")],
    output_dir: Annotated[
        Path,
        typer.Option("--outdir", "-o", help="Directory to save the split chapters."),
    ] = Path("chapters"),
    number: Annotated[
        bool,
        typer.Option(help="Whether to include the chapter index in the filename."),
    ] = True,
) -> None:
    """Split a PDF into separate files based on its level-1 TOC entries."""
    entries = [
        e for e in extract_toc(input_pdf) if e.level == 1 and (e.page_count or 0) > 0
    ]
    if not entries:
        typer.echo("No level-1 TOC entries found to split.")
        raise typer.Exit()

    output_dir.mkdir(parents=True, exist_ok=True)

    with Pdf.open(input_pdf) as pdf:
        for entry in entries:
            # Pydantic model ensures index is not None for level 1
            idx = entry.index if entry.index is not None else 0
            prefix = f"{idx:02d}_" if number else ""
            safe_title = slugify_title(entry.title)
            filename = f"{prefix}{safe_title}.pdf"
            output_path = output_dir / filename

            # Slicing: start_page is 1-based, end_page is inclusive
            start = entry.start_page - 1
            end = entry.end_page if entry.end_page is not None else start + 1

            new_pdf = Pdf.new()
            new_pdf.pages.extend(pdf.pages[start:end])
            new_pdf.save(output_path)
            typer.echo(f"Created: {output_path}")


def main(argv: list[str] | None = None) -> int:
    app(argv if argv is not None else None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
