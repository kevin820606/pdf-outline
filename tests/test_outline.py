import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from pikepdf import Array, Dictionary, Name, NameTree, OutlineItem, Pdf, String

from pdf_outline.manifest import ManifestEntry, TocEntry
from pdf_outline.outline import extract_toc, set_toc


class TestOutline(unittest.TestCase):
    def test_extract_toc_flat(self):
        with TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / "test.pdf"
            pdf = Pdf.new()
            pdf.add_blank_page()
            pdf.add_blank_page()

            with pdf.open_outline() as outline:
                outline.root.append(OutlineItem("Page 1", 0))
                outline.root.append(OutlineItem("Page 2", 1))
            pdf.save(pdf_path)

            entries = extract_toc(pdf_path)
            self.assertEqual(len(entries), 2)
            self.assertEqual(entries[0].title, "Page 1")
            self.assertEqual(entries[0].level, 1)
            self.assertEqual(entries[0].start_page, 1)
            self.assertEqual(entries[0].index, 1)

            self.assertEqual(entries[1].title, "Page 2")
            self.assertEqual(entries[1].level, 1)
            self.assertEqual(entries[1].start_page, 2)
            self.assertEqual(entries[1].index, 2)

    def test_extract_toc_nested(self):
        with TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / "test.pdf"
            pdf = Pdf.new()
            pdf.add_blank_page()
            pdf.add_blank_page()

            with pdf.open_outline() as outline:
                p1 = OutlineItem("Chap 1", 0)
                p1.children.append(OutlineItem("Sec 1.1", 1))
                outline.root.append(p1)
            pdf.save(pdf_path)

            entries = extract_toc(pdf_path)
            self.assertEqual(len(entries), 2)
            self.assertEqual(entries[0].title, "Chap 1")
            self.assertEqual(entries[0].level, 1)
            self.assertEqual(entries[0].start_page, 1)
            self.assertEqual(entries[0].index, 1)

            self.assertEqual(entries[1].title, "Sec 1.1")
            self.assertEqual(entries[1].level, 2)
            self.assertEqual(entries[1].start_page, 2)
            self.assertEqual(entries[1].index, None)

    def test_extract_toc_empty(self):
        with TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / "test.pdf"
            pdf = Pdf.new()
            pdf.add_blank_page()
            pdf.save(pdf_path)

            entries = extract_toc(pdf_path)
            self.assertEqual(entries, [])

    def test_set_toc_builds_hierarchy(self):
        with TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / "test.pdf"
            pdf = Pdf.new()
            pdf.add_blank_page()
            pdf.add_blank_page()
            pdf.add_blank_page()
            pdf.save(pdf_path)

            entries = [
                TocEntry(
                    level=1,
                    title="Chap 1",
                    start_page=1,
                    end_page=2,
                    page_count=2,
                    index=1,
                ),
                TocEntry(
                    level=2,
                    title="Sec 1.1",
                    start_page=2,
                    end_page=2,
                    page_count=1,
                    index=None,
                ),
                TocEntry(
                    level=2,
                    title="Sec 1.2",
                    start_page=3,
                    end_page=3,
                    page_count=0,
                    index=None,
                ),
                TocEntry(
                    level=1,
                    title="Chap 2",
                    start_page=3,
                    end_page=3,
                    page_count=1,
                    index=2,
                ),
            ]

            set_toc(pdf_path, entries)

            # Re-read to verify
            extracted = extract_toc(pdf_path)
            self.assertEqual(extracted, entries)

            # Also check actual hierarchy
            with (
                Pdf.open(pdf_path) as verify_pdf,
                verify_pdf.open_outline() as outline,
            ):
                self.assertEqual(len(outline.root), 2)
                self.assertEqual(outline.root[0].title, "Chap 1")
                self.assertEqual(len(outline.root[0].children), 2)
                self.assertEqual(outline.root[0].children[0].title, "Sec 1.1")
                self.assertEqual(outline.root[1].title, "Chap 2")

    def test_set_toc_overwrites_existing(self):
        with TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / "test.pdf"
            pdf = Pdf.new()
            pdf.add_blank_page()
            with pdf.open_outline() as outline:
                outline.root.append(OutlineItem("Old", 0))
            pdf.save(pdf_path)

            entries = [TocEntry(level=1, title="New", start_page=1, index=1)]
            set_toc(pdf_path, entries)

            extracted = extract_toc(pdf_path)
            self.assertEqual(len(extracted), 1)
            self.assertEqual(extracted[0].title, "New")
            self.assertEqual(extracted[0].index, 1)

    def test_set_toc_rejects_missing_parent_level(self):
        with TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / "test.pdf"
            pdf = Pdf.new()
            pdf.add_blank_page()
            pdf.save(pdf_path)

            entries = [ManifestEntry(level=2, title="Orphan", start_page=1)]

            with self.assertRaisesRegex(ValueError, "has no level 1 parent"):
                set_toc(pdf_path, entries)


if __name__ == "__main__":
    unittest.main()


@pytest.mark.parametrize("storage", ["tree-array", "tree-dict", "legacy"])
@pytest.mark.parametrize("action", [False, True])
def test_extract_named_destinations(tmp_pdf, tmp_path, storage, action):
    source = tmp_pdf(pages=4, toc=[("Named chapter", 0)])
    target = tmp_path / "named.pdf"
    with Pdf.open(source) as pdf:
        destination = Array([pdf.pages[2].obj, Name.Fit])
        if storage == "legacy":
            pdf.Root.Dests = Dictionary(chapter=Dictionary(D=destination))
            reference = Name("/chapter")
        else:
            tree = NameTree.new(pdf)
            tree["chapter"] = (
                Dictionary(D=destination) if storage == "tree-dict" else destination
            )
            pdf.Root.Names = Dictionary(Dests=tree.obj)
            reference = String("chapter")
        bookmark = pdf.Root.Outlines.First
        if action:
            del bookmark.Dest
            bookmark.A = Dictionary(S=Name.GoTo, D=reference)
        else:
            bookmark.Dest = reference
        pdf.save(target)
    entry = extract_toc(target)[0]
    assert (entry.start_page, entry.end_page, entry.page_count) == (3, 4, 2)


def test_unresolved_destination_preserves_unknown_ranges(tmp_pdf, tmp_path):
    source = tmp_pdf(pages=4, toc=[("Known", 0), ("Unknown", 2)])
    target = tmp_path / "unresolved.pdf"
    with Pdf.open(source) as pdf:
        pdf.Root.Outlines.First.Next.Dest = String("missing")
        pdf.save(target)
    known, unknown = extract_toc(target)
    assert known.start_page == 1
    assert known.end_page is None and known.page_count is None
    assert unknown.start_page is None
    assert unknown.end_page is None and unknown.page_count is None
    assert [known.index, unknown.index] == [1, 2]


@pytest.mark.parametrize("page", [None, -2, 0, 4])
@pytest.mark.parametrize("in_place", [False, True])
def test_set_toc_rejects_invalid_pages_without_writing(
    tmp_pdf, tmp_path, page, in_place
):
    source = tmp_pdf(pages=3, toc=[("Old", 0)])
    output = source if in_place else tmp_path / "output.pdf"
    if not in_place:
        output.write_bytes(b"existing output")
    original_source, original_output = source.read_bytes(), output.read_bytes()
    with pytest.raises(ValueError, match="start_page"):
        set_toc(
            source,
            [
                ManifestEntry(title="Valid", start_page=1),
                ManifestEntry(title="Invalid", start_page=page),
            ],
            output,
        )
    assert source.read_bytes() == original_source
    assert output.read_bytes() == original_output


def test_set_toc_accepts_last_page(tmp_pdf, tmp_path):
    source = tmp_pdf(pages=3)
    output = tmp_path / "output.pdf"
    set_toc(source, [ManifestEntry(title="Last", start_page=3)], output)
    assert extract_toc(output)[0].start_page == 3


@pytest.mark.parametrize("page_index, expected", [(-1, None), (2, 3), (3, None)])
def test_integer_destination_bounds(tmp_pdf, tmp_path, page_index, expected):
    source = tmp_pdf(pages=3, toc=[("Chapter", 0)])
    target = tmp_path / "integer-destination.pdf"
    with Pdf.open(source) as pdf:
        pdf.Root.Outlines.First.Dest = Array([page_index, Name.Fit])
        pdf.save(target)
    assert extract_toc(target)[0].start_page == expected
