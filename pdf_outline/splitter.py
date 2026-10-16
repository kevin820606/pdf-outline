from pathlib import Path

from pikepdf import Pdf

from pdf_outline.outline import extract_toc
from pdf_outline.titles import slugify_title


def split_pdf(
    input_pdf: str | Path,
    output_dir: str | Path = "chapters",
    number: bool = True,
) -> list[Path]:
    """Split at level-1 bookmarks, rejecting unsafe ranges and output names."""
    entries = [entry for entry in extract_toc(input_pdf) if entry.level == 1]
    if not entries:
        return []

    output_dir = Path(output_dir)
    outputs: list[Path] = []
    names: set[str] = set()
    previous_start = 0
    for entry in entries:
        if (
            entry.start_page is None
            or entry.start_page <= previous_start
            or entry.end_page is None
            or entry.page_count is None
            or entry.page_count <= 0
        ):
            raise ValueError(
                f"Cannot split at '{entry.title}': level-1 destinations must "
                "resolve to strictly increasing pages."
            )
        previous_start = entry.start_page
        prefix = f"{entry.index:02d}_" if number else ""
        filename = f"{prefix}{slugify_title(entry.title)}.pdf"
        output_path = output_dir / filename
        if filename.casefold() in names:
            raise ValueError(f"Duplicate output filename: {filename}; keep numbering.")
        if output_path.exists() or output_path.is_symlink():
            raise FileExistsError(f"Output already exists: {output_path}")
        names.add(filename.casefold())
        outputs.append(output_path)

    output_dir.mkdir(parents=True, exist_ok=True)
    with Pdf.open(input_pdf) as pdf:
        for entry, output_path in zip(entries, outputs, strict=True):
            with Pdf.new() as chapter:
                chapter.pages.extend(pdf.pages[entry.start_page - 1 : entry.end_page])
                with output_path.open("xb") as stream:
                    try:
                        chapter.save(stream)
                    except Exception:
                        output_path.unlink()
                        raise
    return outputs
