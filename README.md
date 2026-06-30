# pdf-outline

`pdf-outline` provides tools for managing PDF tables of contents (outlines), merging chapter PDFs, and splitting books into chapter-based files.

## Features

- **`bind`**: Merges multiple PDFs into a single file in CLI order, creating top-level bookmarks for each input.
  - Supports explicit titles via JSON manifest or `--entry`.
  - Automatically normalizes titles from filenames (preserves Roman numerals/acronyms).
- **`toc`**: Extracts a PDF's table of contents as a readable tree or structured JSON.
  - Assigns a sequential **index** to top-level entries to represent inferred chapter order.
- **`split`**: Divides a PDF into separate files based on its level-1 TOC entries.
  - Automatically names files using the chapter index and a sanitized title.
- **`set-toc`**: Writes a new hierarchical outline into an existing PDF from a JSON manifest.

## Installation

This project uses `uv`.

```bash
uv sync
```

## Usage

### 1. Bind PDFs

Merge multiple PDF files into one.

```bash
uv run pdf-outline bind --output merged.pdf \
  "/path/to/Book_(Cover).pdf" \
  "/path/to/Book_(1._Introduction).pdf" \
  "/path/to/Book_(Chapter_1).pdf"
```

### 2. Extract TOC

Print the TOC of an existing PDF. Top-level entries are assigned a sequential `Idx` for easy identification as chapters.

```bash
uv run pdf-outline toc input.pdf
```
Output:
```
[Idx: 01] 1  Cover                                    p.1 [end: 1] (1 pages)
[Idx: 02] 1  Preface                                  p.2 [end: 5] (4 pages)
[Idx: 03] 1  1. Introduction                          p.6 [end: 15] (10 pages)
```

Extract to JSON:
```bash
uv run pdf-outline toc input.pdf --json > outline.json
```

### 3. Split by Chapters

Split a single book PDF into separate files named by their top-level TOC entries.

```bash
# Saves files like 01_Cover.pdf, 02_Preface.pdf to the 'chapters' folder
uv run pdf-outline split book.pdf --outdir chapters

# Omit the 01_ prefix
uv run pdf-outline split book.pdf --no-number
```

### 4. Set TOC

Overwrite or add a table of contents using a JSON manifest. `start_page` is 1-based.

```bash
uv run pdf-outline set-toc input.pdf --manifest outline.json --output updated.pdf
```

## Filename Rules (for `bind`)

The tool extracts the first parenthesized token from the filename stem to use as the bookmark title.

Examples:
- `Book_(Cover).pdf` -> `Cover`
- `Book_(1._Introduction).pdf` -> `1. Introduction`
- `Book_(The_UN_and_NATO).pdf` -> `The UN And NATO`

## Manifest Formats

**For `set-toc`:**
Hierarchy is defined by the `level` property.
```json
[
  {"level": 1, "title": "Cover", "start_page": 1, "index": 1},
  {"level": 2, "title": "Preface", "start_page": 2, "index": null},
  {"level": 1, "title": "Introduction", "start_page": 6, "index": 2}
]
```

## Development

Run the full test suite:

```bash
uv run pytest
```

## License

MIT. See [LICENSE](LICENSE).
