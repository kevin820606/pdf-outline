import json
import unittest
from contextlib import chdir
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from typer.testing import CliRunner

from pdf_outline import cli
from pdf_outline.manifest import (
    ManifestEntry,
    load_manifest,
    validate_manifest_for_bind,
    validate_manifest_levels,
)

RUNNER = CliRunner()


class CliTests(unittest.TestCase):
    def test_create_manifest_templates(self):
        with TemporaryDirectory() as tmpdir:
            for mode in ("bind", "set-toc"):
                with self.subTest(mode=mode):
                    output = Path(tmpdir) / f"{mode}.json"
                    result = RUNNER.invoke(
                        cli.app,
                        ["create-manifest", "--output", str(output), "--mode", mode],
                    )
                    self.assertEqual(result.exit_code, 0, result.output)
                    entries = load_manifest(output)
                    self.assertEqual([entry.level for entry in entries], [1, 2, 1])
                    validate_manifest_levels(entries)
                    if mode == "bind":
                        validate_manifest_for_bind(entries)
                        self.assertTrue(
                            all(entry.path is not None for entry in entries)
                        )
                        self.assertTrue(
                            all(entry.start_page is None for entry in entries)
                        )
                    else:
                        self.assertEqual(
                            [entry.start_page for entry in entries], [1, 2, 3]
                        )
                        self.assertTrue(all(entry.path is None for entry in entries))

    def test_create_manifest_defaults_and_refuses_overwrite(self):
        with TemporaryDirectory() as tmpdir, chdir(tmpdir):
            result = RUNNER.invoke(cli.app, ["create-manifest"])
            self.assertEqual(result.exit_code, 0, result.output)
            output = Path("manifest.json")
            original = output.read_bytes()
            self.assertTrue(all(entry.path for entry in load_manifest(output)))
            result = RUNNER.invoke(cli.app, ["create-manifest"])
            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("--output", result.output)
            self.assertEqual(output.read_bytes(), original)

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
                ManifestEntry(title="B", path=Path("book_(B).pdf")),
                ManifestEntry(title="A", path=Path("book_(A).pdf")),
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
                ManifestEntry(title="Cover", path=Path("cover.pdf")),
                ManifestEntry(title="Book IV", path=Path("book4.pdf")),
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
                ManifestEntry(title="Cover", path=Path("cover.pdf")),
                ManifestEntry(title="Book IV", path=Path("book4.pdf")),
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
