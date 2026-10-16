import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from pikepdf import OutlineItem, Pdf, String
from typer.testing import CliRunner

from pdf_outline.cli import app
from pdf_outline.splitter import split_pdf

runner = CliRunner()


class TestSplit(unittest.TestCase):
    def test_split_creates_numbered_files(self):
        with TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            pdf_path = tmpdir_path / "book.pdf"

            # Create a 3-page PDF with 2 chapters
            pdf = Pdf.new()
            for _ in range(3):
                pdf.add_blank_page()

            with pdf.open_outline() as outline:
                outline.root.append(OutlineItem("Chap 1", 0))
                outline.root.append(OutlineItem("Chap 2", 1))
            pdf.save(pdf_path)

            outdir = tmpdir_path / "out"
            result = runner.invoke(
                app, ["split", str(pdf_path), "--outdir", str(outdir)]
            )

            self.assertEqual(result.exit_code, 0)
            self.assertTrue((outdir / "01_Chap-1.pdf").exists())
            self.assertTrue((outdir / "02_Chap-2.pdf").exists())

            # Verify page counts
            with Pdf.open(outdir / "01_Chap-1.pdf") as p1:
                self.assertEqual(len(p1.pages), 1)
            with Pdf.open(outdir / "02_Chap-2.pdf") as p2:
                self.assertEqual(len(p2.pages), 2)

    def test_split_no_number(self):
        with TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            pdf_path = tmpdir_path / "book.pdf"

            pdf = Pdf.new()
            pdf.add_blank_page()
            with pdf.open_outline() as outline:
                outline.root.append(OutlineItem("Introduction", 0))
            pdf.save(pdf_path)

            outdir = tmpdir_path / "out"
            result = runner.invoke(
                app, ["split", str(pdf_path), "--outdir", str(outdir), "--no-number"]
            )

            self.assertEqual(result.exit_code, 0)
            self.assertTrue((outdir / "Introduction.pdf").exists())
            self.assertFalse((outdir / "01_Introduction.pdf").exists())

    def test_split_sanitizes_filenames(self):
        with TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            pdf_path = tmpdir_path / "book.pdf"

            pdf = Pdf.new()
            pdf.add_blank_page()
            with pdf.open_outline() as outline:
                outline.root.append(
                    OutlineItem("A Theory: Multinational Firms & World Order!", 0)
                )
            pdf.save(pdf_path)

            outdir = tmpdir_path / "out"
            result = runner.invoke(
                app, ["split", str(pdf_path), "--outdir", str(outdir), "--no-number"]
            )

            self.assertEqual(result.exit_code, 0)
            # Sanitized: remove ! &; replace : and . and space with -
            self.assertTrue(
                (outdir / "A-Theory-Multinational-Firms-World-Order.pdf").exists()
            )


if __name__ == "__main__":
    unittest.main()


@pytest.mark.parametrize("titles", [("A:B", "AB"), ("Intro", "INTRO")])
def test_split_rejects_filename_collisions_before_writing(tmp_pdf, tmp_path, titles):
    source = tmp_pdf(pages=4, toc=[(titles[0], 0), (titles[1], 2)])
    output = tmp_path / "chapters"
    with pytest.raises(ValueError, match="Duplicate output filename"):
        split_pdf(source, output, number=False)
    assert not output.exists()
    assert len(split_pdf(source, output)) == 2


def test_split_checks_all_outputs_before_writing(tmp_pdf, tmp_path):
    source = tmp_pdf(pages=4, toc=[("First", 0), ("Second", 2)])
    output = tmp_path / "chapters"
    output.mkdir()
    existing = output / "02_Second.pdf"
    existing.write_bytes(b"preserve me")
    result = runner.invoke(app, ["split", str(source), "--outdir", str(output)])
    assert result.exit_code != 0
    assert "already exists" in result.output
    assert existing.read_bytes() == b"preserve me"
    assert not (output / "01_First.pdf").exists()


@pytest.mark.parametrize("starts", [(2, 0), (0, 0)])
def test_split_rejects_unordered_or_duplicate_pages(tmp_pdf, tmp_path, starts):
    source = tmp_pdf(pages=4, toc=[("First", starts[0]), ("Second", starts[1])])
    output = tmp_path / "chapters"
    with pytest.raises(ValueError, match="strictly increasing"):
        split_pdf(source, output)
    assert not output.exists()


def test_split_rejects_unresolved_destination(tmp_pdf, tmp_path):
    source = tmp_pdf(pages=4, toc=[("First", 0), ("Unknown", 2)])
    unresolved = tmp_path / "unresolved.pdf"
    with Pdf.open(source) as pdf:
        pdf.Root.Outlines.First.Next.Dest = String("missing")
        pdf.save(unresolved)
    output = tmp_path / "chapters"
    with pytest.raises(ValueError, match="strictly increasing"):
        split_pdf(unresolved, output)
    assert not output.exists()


def test_split_without_bookmarks_creates_nothing(tmp_pdf, tmp_path):
    source = tmp_pdf(pages=2)
    output = tmp_path / "chapters"
    assert split_pdf(source, output) == []
    result = runner.invoke(app, ["split", str(source), "--outdir", str(output)])
    assert result.exit_code == 0
    assert "No level-1" in result.output
    assert not output.exists()


def test_split_removes_incomplete_file_on_save_failure(tmp_pdf, tmp_path, monkeypatch):
    source = tmp_pdf(pages=2, toc=[("Chapter", 0)])
    output = tmp_path / "chapters"

    def fail_save(self, stream, **kwargs):
        stream.write(b"partial PDF")
        raise OSError("disk full")

    monkeypatch.setattr(Pdf, "save", fail_save)
    with pytest.raises(OSError, match="disk full"):
        split_pdf(source, output)
    assert list(output.iterdir()) == []


def test_split_refuses_broken_symlink(tmp_pdf, tmp_path):
    source = tmp_pdf(pages=2, toc=[("Chapter", 0)])
    output = tmp_path / "chapters"
    output.mkdir()
    link = output / "01_Chapter.pdf"
    missing = tmp_path / "missing.pdf"
    link.symlink_to(missing)
    with pytest.raises(FileExistsError):
        split_pdf(source, output)
    assert link.is_symlink()
    assert not missing.exists()


def test_split_preserves_file_created_after_preflight(tmp_pdf, tmp_path, monkeypatch):
    source = tmp_pdf(pages=2, toc=[("Chapter", 0)])
    output = tmp_path / "chapters"
    original_open = Path.open

    def competing_open(path, mode="r", *args, **kwargs):
        if mode == "xb":
            with original_open(path, "wb") as stream:
                stream.write(b"another process")
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", competing_open)
    with pytest.raises(FileExistsError):
        split_pdf(source, output)
    assert (output / "01_Chapter.pdf").read_bytes() == b"another process"
