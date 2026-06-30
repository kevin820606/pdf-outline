import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from pikepdf import OutlineItem, Pdf

from pdf_outline.manifest import ManifestEntry
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
                ManifestEntry(
                    level=1,
                    title="Chap 1",
                    start_page=1,
                    end_page=2,
                    page_count=2,
                    index=1,
                ),
                ManifestEntry(
                    level=2,
                    title="Sec 1.1",
                    start_page=2,
                    end_page=2,
                    page_count=1,
                    index=None,
                ),
                ManifestEntry(
                    level=2,
                    title="Sec 1.2",
                    start_page=3,
                    end_page=3,
                    page_count=0,
                    index=None,
                ),
                ManifestEntry(
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

            entries = [ManifestEntry(level=1, title="New", start_page=1, index=1)]
            set_toc(pdf_path, entries)

            extracted = extract_toc(pdf_path)
            self.assertEqual(len(extracted), 1)
            self.assertEqual(extracted[0].title, "New")
            self.assertEqual(extracted[0].index, 1)


if __name__ == "__main__":
    unittest.main()
