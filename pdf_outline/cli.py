from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from pdf_outline.binder import (
    bind_pdfs,
    build_entries_from_paths,
    parse_entry,
)
from pdf_outline.manifest import ManifestEntry, load_manifest
from pdf_outline.outline import extract_toc
from pdf_outline.outline import set_toc as set_toc_outline
from pdf_outline.splitter import split_pdf

app = typer.Typer(
    help="Merge PDFs in CLI order and generate outline titles from filenames.",
)


class ManifestMode(StrEnum):
    bind = "bind"
    set_toc = "set-toc"


@app.command()
def create_manifest(
    output: Annotated[
        Path, typer.Option("--output", help="Path for the JSON manifest template.")
    ] = Path("manifest.json"),
    mode: Annotated[
        ManifestMode, typer.Option("--mode", help="Command that will use the manifest.")
    ] = ManifestMode.bind,
) -> None:
    """Create an editable manifest template without overwriting existing files."""
    entries = [
        ManifestEntry(
            title=title,
            level=level,
            path=Path(path) if mode == ManifestMode.bind else None,
            start_page=page if mode == ManifestMode.set_toc else None,
        )
        for title, level, path, page in [
            ("Introduction", 1, "01_intro.pdf", 1),
            ("Background", 2, "02_background.pdf", 2),
            ("Chapter 1", 1, "03_chapter1.pdf", 3),
        ]
    ]
    data = [entry.model_dump(mode="json", exclude_none=True) for entry in entries]
    try:
        with output.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(data, indent=2) + "\n")
    except OSError as exc:
        raise typer.BadParameter(str(exc), param_hint="--output") from exc
    typer.echo(f"Created: {output}")


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
    acronym: Annotated[
        list[str] | None,
        typer.Option(
            "--acronym",
            help=(
                "Extra acronym to preserve in upper-case during title normalisation "
                "(repeatable, e.g. --acronym GDP --acronym IMF). "
                "Only applies when titles are derived from filenames."
            ),
        ),
    ] = None,
) -> None:
    """Merge PDFs in CLI order."""
    extra_acronyms: list[str] = acronym or []
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
            entries = build_entries_from_paths(inputs, extra_acronyms)
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
            page = entry.start_page if entry.start_page is not None else "?"
            typer.echo(
                f"{idx_str}{indent}{entry.level}  {entry.title:<40} "
                f"p.{page} {count_str}"
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
        set_toc_outline(input_pdf, entries, output)
    except (ValueError, OSError) as exc:
        raise typer.BadParameter(str(exc)) from exc


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
    try:
        outputs = split_pdf(input_pdf, output_dir, number)
    except (ValueError, OSError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    if not outputs:
        typer.echo("No level-1 TOC entries found to split.")
    for output_path in outputs:
        typer.echo(f"Created: {output_path}")


def main(argv: list[str] | None = None) -> int:
    app(argv if argv is not None else None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
