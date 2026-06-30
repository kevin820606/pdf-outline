import json
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class ManifestEntry(BaseModel):
    """
    Unified entry for both PDF binding and TOC setting.
    """

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    def __init__(
        self, title: str | None = None, path: Path | str | None = None, **kwargs
    ):
        if title is not None:
            kwargs["title"] = title
        if path is not None:
            kwargs["path"] = Path(path)
        elif "path" in kwargs and isinstance(kwargs["path"], str):
            kwargs["path"] = Path(kwargs["path"])
        super().__init__(**kwargs)

    title: str = Field(..., min_length=1)
    level: int = 1
    path: Path | None = None
    start_page: int | None = None
    index: int | None = None
    end_page: int | None = None
    page_count: int | None = None


def load_manifest(path: str | Path) -> list[ManifestEntry]:
    """Load and validate a JSON manifest using Pydantic."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError("manifest must be a JSON array")
        return [ManifestEntry.model_validate(item) for item in data]
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse manifest JSON: {exc}") from exc


def validate_manifest_levels(entries: Sequence[ManifestEntry]) -> None:
    """Validate that manifest levels can form a hierarchy."""
    stack: list[ManifestEntry] = []

    for entry in entries:
        if entry.level < 1:
            raise ValueError(f"Entry '{entry.title}' has invalid level {entry.level}.")

        if entry.level > len(stack) + 1:
            raise ValueError(
                f"Entry '{entry.title}' at level {entry.level} has no level "
                f"{entry.level - 1} parent."
            )

        if entry.level <= len(stack):
            stack = stack[: entry.level - 1]

        stack.append(entry)


def validate_manifest_for_bind(entries: Sequence[ManifestEntry]) -> None:
    """Validate manifest entries for PDF binding."""
    validate_manifest_levels(entries)
    stack: list[ManifestEntry] = []

    for entry in entries:
        if entry.level <= len(stack):
            stack = stack[: entry.level - 1]
        stack.append(entry)

        if entry.path is None and entry.level > 1:
            parent = stack[entry.level - 2]
            if parent.path is None:
                raise ValueError(
                    f"Empty entry '{entry.title}' at level {entry.level} "
                    f"cannot be a child of another empty entry '{parent.title}'."
                )
