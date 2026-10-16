from collections.abc import Iterable
from pathlib import Path
from typing import Any

from pikepdf import Array, Dictionary, Name, NameTree, OutlineItem, Pdf, String

from pdf_outline.manifest import (
    ManifestEntry,
    TocEntry,
    validate_manifest_for_set_toc,
)


def _write_outline_items(
    outline_root: Any,
    items: Iterable[tuple[str, int, int]],
) -> None:
    """Append OutlineItems into an outline root following level hierarchy.

    Args:
        outline_root: The root list-like object (``outline.root`` or an
            ``OutlineItem.children`` list) to append top-level items to.
        items: An iterable of ``(title, page_index, level)`` tuples where
            *page_index* is 0-based and *level* starts at 1.
    """
    stack: list[Any] = [outline_root]
    for title, page_index, level in items:
        new_item = OutlineItem(title, page_index)

        if level < len(stack):
            stack = stack[:level]

        parent = stack[-1]
        if hasattr(parent, "children"):
            parent.children.append(new_item)
        else:
            parent.append(new_item)

        stack.append(new_item)


def _resolve_page_number(
    pdf: Pdf,
    item: OutlineItem,
    page_map: dict[tuple[int, int], int],
) -> int | None:
    """Resolve an OutlineItem's destination to a 0-based page number."""
    dest = item.destination
    if dest is None and item.action and item.action.get("/S") == "/GoTo":
        dest = item.action.get("/D")

    if dest is None:
        return None

    if isinstance(dest, str | String | Name):
        key = str(dest).removeprefix("/") if isinstance(dest, Name) else str(dest)
        names = pdf.Root.get("/Names")
        if names is not None and "/Dests" in names:
            dest_tree = NameTree(names.Dests)
            if key in dest_tree:
                dest = dest_tree[key]
        if isinstance(dest, str | String | Name):
            legacy = pdf.Root.get("/Dests")
            dest = legacy.get(f"/{key}") if legacy is not None else None

    if isinstance(dest, Dictionary):
        dest = dest.get("/D")

    if isinstance(dest, Array) and len(dest) > 0:
        page_ref = dest[0]
        if isinstance(page_ref, int):
            return page_ref if 0 <= page_ref < len(pdf.pages) else None
        if hasattr(page_ref, "objgen"):
            return page_map.get(page_ref.objgen)

    return None


def extract_toc(pdf_path: str | Path) -> list[TocEntry]:
    """Extract a flat list of TOC entries from a PDF's outline."""
    entries: list[TocEntry] = []
    with Pdf.open(pdf_path) as pdf:
        page_map = {page.objgen: i for i, page in enumerate(pdf.pages)}
        total_pages = len(pdf.pages)

        def _walk(item: OutlineItem, level: int) -> list[TocEntry]:
            page_num = _resolve_page_number(pdf, item, page_map)
            page_num = (page_num + 1) if page_num is not None else None
            result: list[TocEntry] = [
                TocEntry(
                    level=level,
                    title=item.title or "",
                    start_page=page_num,
                )
            ]
            for child in item.children:
                result.extend(_walk(child, level + 1))
            return result

        with pdf.open_outline() as outline:
            for item in outline.root:
                entries.extend(_walk(item, 1))

    current_index = 1
    for i, entry in enumerate(entries):
        next_start = total_pages + 1
        for j in range(i + 1, len(entries)):
            if entries[j].level <= entry.level:
                next_start = entries[j].start_page
                break

        current_start = entry.start_page
        page_count = end_page = None
        if (
            current_start is not None
            and next_start is not None
            and next_start >= current_start
        ):
            page_count = next_start - current_start
            end_page = max(current_start, next_start - 1)

        update_dict: dict[str, Any] = {
            "page_count": page_count,
            "end_page": end_page,
        }
        if entry.level == 1:
            update_dict["index"] = current_index
            current_index += 1

        entries[i] = entry.model_copy(update=update_dict)

    return entries


def set_toc(
    pdf_path: str | Path,
    entries: Iterable[ManifestEntry],
    output_path: str | Path | None = None,
) -> None:
    """Set the TOC in a PDF to the given entries."""
    output_path = output_path or pdf_path
    entries_list = list(entries)
    with Pdf.open(pdf_path, allow_overwriting_input=True) as pdf:
        validate_manifest_for_set_toc(entries_list, len(pdf.pages))
        with pdf.open_outline() as outline:
            outline.root.clear()
            _write_outline_items(
                outline.root,
                ((e.title, e.start_page - 1, e.level) for e in entries_list),
            )

        pdf.save(output_path)
