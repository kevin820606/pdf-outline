"""Shared pytest fixtures for the pdf_outline test suite."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from pikepdf import OutlineItem, Pdf


@pytest.fixture()
def tmp_pdf(tmp_path: Path) -> Callable[..., Path]:
    """Factory fixture: create a temporary PDF with blank pages and optional TOC.

    Usage::

        def test_something(tmp_pdf):
            path = tmp_pdf(pages=3, toc=[("Chapter 1", 0), ("Chapter 2", 1)])
            with Pdf.open(path) as pdf:
                ...

    Args:
        pages: Number of blank pages to add (default 1).
        toc: Optional list of ``(title, 0-based-page-index)`` tuples that
             become top-level outline items.
        name: Filename stem inside ``tmp_path`` (default ``"test"``).

    Returns:
        The :class:`~pathlib.Path` to the saved PDF.
    """

    def _factory(
        pages: int = 1,
        toc: list[tuple[str, int]] | None = None,
        name: str = "test",
    ) -> Path:
        pdf_path = tmp_path / f"{name}.pdf"
        pdf = Pdf.new()
        for _ in range(pages):
            pdf.add_blank_page()
        if toc:
            with pdf.open_outline() as outline:
                for title, page_index in toc:
                    outline.root.append(OutlineItem(title, page_index))
        pdf.save(pdf_path)
        return pdf_path

    return _factory
