from collections.abc import Iterable
from pathlib import Path
from typing import Any

from pikepdf import Array, Name, OutlineItem, Pdf

from pdf_outline.manifest import ManifestEntry, validate_manifest_levels


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

    # Handle named destinations
    if isinstance(dest, str | Name):
        # Try to resolve named destination in root.Names.Dests
        if "/Names" in pdf.root and "/Dests" in pdf.root.Names:
            from pikepdf import NameTree

            try:
                dest_tree = NameTree(pdf.root.Names.Dests)
                if dest in dest_tree:
                    dest = dest_tree[dest]
            except Exception:
                pass

        # Also check /Dests directly in root
        if (
            isinstance(dest, str | Name)
            and "/Dests" in pdf.root
            and dest in pdf.root.Dests
        ):
            dest = pdf.root.Dests[dest]

        # If it's still a name/string, we failed to resolve
        if isinstance(dest, str | Name):
            return None

    # If it's a dictionary (like from a name tree), it usually has a /D array
    if isinstance(dest, dict) and "/D" in dest:
        dest = dest["/D"]

    if isinstance(dest, Array) and len(dest) > 0:
        page_ref = dest[0]
        if hasattr(page_ref, "objgen"):
            return page_map.get(page_ref.objgen)
        # If it's an integer, it might be a page index directly
        if isinstance(page_ref, int):
            return page_ref

    return None


def extract_toc(pdf_path: str | Path) -> list[ManifestEntry]:
    """Extract a flat list of TOC entries from a PDF's outline."""
    entries: list[ManifestEntry] = []
    with Pdf.open(pdf_path) as pdf:
        page_map = {page.objgen: i for i, page in enumerate(pdf.pages)}
        total_pages = len(pdf.pages)

        def _walk(item: OutlineItem, level: int) -> None:
            page_num = _resolve_page_number(pdf, item, page_map)
            page_num = (page_num + 1) if page_num is not None else 1

            entries.append(
                ManifestEntry(
                    level=level,
                    title=item.title or "",
                    start_page=page_num,
                ),
            )
            for child in item.children:
                _walk(child, level + 1)

        with pdf.open_outline() as outline:
            for item in outline.root:
                _walk(item, 1)

    current_index = 1
    for i, entry in enumerate(entries):
        next_start = total_pages + 1
        for j in range(i + 1, len(entries)):
            if entries[j].level <= entry.level:
                next_start = entries[j].start_page or 1
                break

        current_start = entry.start_page or 1
        page_count = max(0, next_start - current_start)
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
    validate_manifest_levels(entries_list)

    with Pdf.open(pdf_path, allow_overwriting_input=True) as pdf:
        with pdf.open_outline() as outline:
            # Clear existing outline
            outline.root.clear()

            # Stack stores the items we can append to.
            # stack[0] is outline.root (level 0)
            stack: list[Any] = [outline.root]

            for entry in entries_list:
                if entry.start_page is None:
                    raise ValueError(
                        f"start_page is required for entry '{entry.title}'"
                    )
                page_index = max(0, entry.start_page - 1)
                new_item = OutlineItem(entry.title, page_index)

                # Truncate stack if level is <= current nesting depth
                if entry.level < len(stack):
                    stack = stack[: entry.level]

                parent = stack[-1]

                if hasattr(parent, "children"):
                    parent.children.append(new_item)
                else:
                    parent.append(new_item)

                stack.append(new_item)

        pdf.save(output_path)
