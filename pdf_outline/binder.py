from collections.abc import Iterable, Sequence
from contextlib import ExitStack
from pathlib import Path
from typing import Any

from pikepdf import OutlineItem, Pdf
from pydantic import BaseModel, ConfigDict

from pdf_outline import titles
from pdf_outline.manifest import ManifestEntry, validate_manifest_for_bind


class OutlinePlanEntry(BaseModel):
    """Internal model for the binding plan."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    title: str
    start_page: int
    level: int = 1


def build_entries_from_paths(input_paths: Sequence[str | Path]) -> list[ManifestEntry]:
    """Extract titles from parenthesized filenames for binding."""
    entries: list[ManifestEntry] = []
    for input_path in input_paths:
        path = Path(input_path)
        chapter_token = titles.extract_chapter_token(str(path))
        entries.append(
            ManifestEntry(title=titles.normalize_title(chapter_token), path=path),
        )
    return entries


def parse_entry(entry: str) -> ManifestEntry:
    """Parse a Title::path string into a ManifestEntry."""
    if "::" not in entry:
        raise ValueError("entry must use Title::path format")
    title, path = entry.split("::", 1)
    return ManifestEntry(title=title.strip(), path=Path(path.strip()))


def build_outline_plan(
    entries: Sequence[ManifestEntry],
    page_counts: Sequence[int],
) -> list[OutlinePlanEntry]:
    """Calculate the cumulative page offsets for the outline."""
    plan: list[OutlinePlanEntry] = []
    start_page = 0

    page_count_iter = iter(page_counts)

    for entry in entries:
        plan.append(
            OutlinePlanEntry(
                title=entry.title,
                start_page=start_page,
                level=entry.level,
            ),
        )
        if entry.path is not None:
            start_page += next(page_count_iter)

    return plan


def bind_pdfs(entries: Iterable[ManifestEntry], output_path: str | Path) -> None:
    """
    Efficiently merge multiple PDFs and generate a chapter outline.
    Uses ExitStack for safe resource management.
    """
    entries_list = list(entries)
    validate_manifest_for_bind(entries_list)

    with ExitStack() as stack:
        sources: list[Pdf] = []
        page_counts: list[int] = []

        for entry in entries_list:
            if entry.path is not None:
                source_pdf = stack.enter_context(Pdf.open(entry.path))
                sources.append(source_pdf)
                page_counts.append(len(source_pdf.pages))

        outline_plan = build_outline_plan(entries_list, page_counts)
        output_pdf = stack.enter_context(Pdf.new())

        source_iter = iter(sources)

        with output_pdf.open_outline() as outline:
            # Stack stores the items we can append to.
            # out_stack[0] is outline.root (level 0)
            out_stack: list[Any] = [outline.root]

            for entry, plan_entry in zip(entries_list, outline_plan, strict=True):
                if entry.path is not None:
                    source_pdf = next(source_iter)
                    output_pdf.pages.extend(source_pdf.pages)

                new_item = OutlineItem(plan_entry.title, plan_entry.start_page)

                if plan_entry.level < len(out_stack):
                    out_stack = out_stack[: plan_entry.level]

                parent = out_stack[-1]

                if hasattr(parent, "children"):
                    parent.children.append(new_item)
                else:
                    parent.append(new_item)

                out_stack.append(new_item)

        output_pdf.save(Path(output_path))
