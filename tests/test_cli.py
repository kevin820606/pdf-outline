import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from typer.testing import CliRunner

from pdf_outline import cli
from pdf_outline.manifest import ManifestEntry

RUNNER = CliRunner()


class CliTests(unittest.TestCase):
    def test_invokes_typer_single_command_with_ordered_inputs(self):
        with patch.object(cli, "bind_pdfs") as bind_pdfs:
            result = RUNNER.invoke(
                cli.app,
                [
                    "bind",
                    "--output",
                    "merged.pdf",
                    "book_(B).pdf",
                    "book_(A).pdf",
                ],
            )

        self.assertEqual(result.exit_code, 0, result.stdout)
        bind_pdfs.assert_called_once_with(
            [
                ManifestEntry("B", Path("book_(B).pdf")),
                ManifestEntry("A", Path("book_(A).pdf")),
            ],
            Path("merged.pdf"),
        )

    def test_invokes_typer_with_explicit_entries(self):
        with patch.object(cli, "bind_pdfs") as bind_pdfs:
            result = RUNNER.invoke(
                cli.app,
                [
                    "bind",
                    "--output",
                    "merged.pdf",
                    "--entry",
                    "Cover::cover.pdf",
                    "--entry",
                    "Book IV::book4.pdf",
                ],
            )

        self.assertEqual(result.exit_code, 0, result.stdout)
        bind_pdfs.assert_called_once_with(
            [
                ManifestEntry("Cover", Path("cover.pdf")),
                ManifestEntry("Book IV", Path("book4.pdf")),
            ],
            Path("merged.pdf"),
        )

    def test_invokes_typer_with_manifest(self):
        with TemporaryDirectory() as tmpdir:
            manifest = Path(tmpdir) / "chapters.json"
            manifest.write_text(
                json.dumps(
                    [
                        {"title": "Cover", "path": "cover.pdf"},
                        {"title": "Book IV", "path": "book4.pdf"},
                    ],
                ),
                encoding="utf-8",
            )
            with patch.object(cli, "bind_pdfs") as bind_pdfs:
                result = RUNNER.invoke(
                    cli.app,
                    [
                        "bind",
                        "--output",
                        "merged.pdf",
                        "--manifest",
                        str(manifest),
                    ],
                )

        self.assertEqual(result.exit_code, 0, result.stdout)
        bind_pdfs.assert_called_once_with(
            [
                ManifestEntry("Cover", Path("cover.pdf")),
                ManifestEntry("Book IV", Path("book4.pdf")),
            ],
            Path("merged.pdf"),
        )

    def test_requires_output_argument(self):
        result = RUNNER.invoke(cli.app, ["bind", "a.pdf"])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIsNotNone(result.exception)

    def test_requires_at_least_one_input(self):
        result = RUNNER.invoke(cli.app, ["bind", "--output", "merged.pdf"])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIsNotNone(result.exception)

    def test_rejects_mixed_input_modes(self):
        result = RUNNER.invoke(
            cli.app,
            [
                "bind",
                "--output",
                "merged.pdf",
                "--entry",
                "Cover::cover.pdf",
                "a.pdf",
            ],
        )

        self.assertNotEqual(result.exit_code, 0)
        self.assertIsNotNone(result.exception)

    def test_rejects_malformed_entry(self):
        result = RUNNER.invoke(
            cli.app,
            [
                "bind",
                "--output",
                "merged.pdf",
                "--entry",
                "CoverOnly",
            ],
        )

        self.assertNotEqual(result.exit_code, 0)
        self.assertIsNotNone(result.exception)

    def test_main_passes_ordered_inputs_to_app(self):
        with patch.object(cli, "app") as app:
            result = cli.main(["bind", "--output", "merged.pdf", "b.pdf", "a.pdf"])

        self.assertEqual(result, 0)
        app.assert_called_once_with(
            ["bind", "--output", "merged.pdf", "b.pdf", "a.pdf"]
        )


if __name__ == "__main__":
    unittest.main()
