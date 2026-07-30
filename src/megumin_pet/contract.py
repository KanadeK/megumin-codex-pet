"""The executable Codex v2 pet contract."""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import Any

TOOL_VERSION = "0.1.0"
SNAPSHOT_SCHEMA = 1
REPORT_SCHEMA = 1
PACKAGE_SCHEMA = 1

CELL_WIDTH = 192
CELL_HEIGHT = 208
COLUMNS = 8
ROWS = 11
ATLAS_WIDTH = CELL_WIDTH * COLUMNS
ATLAS_HEIGHT = CELL_HEIGHT * ROWS

STATE_LAYOUT: tuple[dict[str, Any], ...] = (
    {"name": "idle", "row": 0, "frames": 6, "durations_ms": [280, 110, 110, 140, 140, 320]},
    {
        "name": "running-right",
        "row": 1,
        "frames": 8,
        "durations_ms": [120, 120, 120, 120, 120, 120, 120, 220],
    },
    {
        "name": "running-left",
        "row": 2,
        "frames": 8,
        "durations_ms": [120, 120, 120, 120, 120, 120, 120, 220],
    },
    {"name": "waving", "row": 3, "frames": 4, "durations_ms": [140, 140, 140, 280]},
    {"name": "jumping", "row": 4, "frames": 5, "durations_ms": [140, 140, 140, 140, 280]},
    {
        "name": "failed",
        "row": 5,
        "frames": 8,
        "durations_ms": [140, 140, 140, 140, 140, 140, 140, 240],
    },
    {"name": "waiting", "row": 6, "frames": 6, "durations_ms": [150, 150, 150, 150, 150, 260]},
    {"name": "running", "row": 7, "frames": 6, "durations_ms": [120, 120, 120, 120, 120, 220]},
    {"name": "review", "row": 8, "frames": 6, "durations_ms": [150, 150, 150, 150, 150, 280]},
)
LOOK_ANGLES: tuple[str, ...] = (
    "000",
    "022.5",
    "045",
    "067.5",
    "090",
    "112.5",
    "135",
    "157.5",
    "180",
    "202.5",
    "225",
    "247.5",
    "270",
    "292.5",
    "315",
    "337.5",
)

PET_ID_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")


def cell_key(row: int, column: int) -> str:
    """Return a stable atlas-cell key."""
    return f"r{row:02d}c{column:02d}"


def cell_label(row: int, column: int) -> str:
    """Return the semantic label for an atlas cell."""
    if (row, column) == (0, 6):
        return "neutral"
    if row <= 8:
        state = STATE_LAYOUT[row]
        return f"{state['name']}:{column}"
    angle_index = (row - 9) * COLUMNS + column
    return f"look:{LOOK_ANGLES[angle_index]}"


def active_cells() -> tuple[tuple[int, int], ...]:
    """Return all 73 required cells in deterministic row-major order."""
    cells: list[tuple[int, int]] = []
    for state in STATE_LAYOUT:
        cells.extend((int(state["row"]), column) for column in range(int(state["frames"])))
    cells.extend((row, column) for row in (9, 10) for column in range(COLUMNS))
    return tuple(cells)


ACTIVE_CELLS = active_cells()
ACTIVE_CELL_KEYS = frozenset(cell_key(row, column) for row, column in ACTIVE_CELLS)

# Codex's v2 hatch pipeline may populate row 0, column 6 with a neutral/default
# pose used by pointer dead-zone handling. It is valid when present and valid
# when transparent, so it is not one of the 73 required regression cells.
OPTIONAL_CELLS: tuple[tuple[int, int], ...] = ((0, 6),)
OPTIONAL_CELL_KEYS = frozenset(cell_key(row, column) for row, column in OPTIONAL_CELLS)
RESERVED_CELL_KEYS = frozenset(
    cell_key(row, column)
    for row in range(ROWS)
    for column in range(COLUMNS)
    if cell_key(row, column) not in ACTIVE_CELL_KEYS | OPTIONAL_CELL_KEYS
)


def finding(
    severity: str,
    code: str,
    message: str,
    *,
    cell: str | None = None,
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one stable machine-readable finding."""
    result: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if cell is not None:
        result["cell"] = cell
    if detail:
        result["detail"] = detail
    return result


def safe_sprite_path(raw: object) -> tuple[PurePosixPath | None, str | None]:
    """Validate a manifest sprite path without touching the filesystem."""
    if not isinstance(raw, str) or not raw.strip():
        return None, "spritesheetPath must be a non-empty string"
    if "\\" in raw or ":" in raw or any(ord(character) < 32 for character in raw):
        return None, "spritesheetPath contains a forbidden character"
    path = PurePosixPath(raw)
    if (
        path.is_absolute()
        or ".." in path.parts
        or "." in path.parts
        or path.as_posix() != raw
    ):
        return None, "spritesheetPath must be a normalized relative path"
    if path.name in {"", ".", ".."}:
        return None, "spritesheetPath must name a file"
    if path.suffix.lower() not in {".png", ".webp"}:
        return None, "spritesheetPath must point to a PNG or WebP file"
    return path, None


def validate_manifest(document: object) -> list[dict[str, Any]]:
    """Validate the public pet manifest shape."""
    findings: list[dict[str, Any]] = []
    if not isinstance(document, dict):
        return [finding("error", "manifest-not-object", "pet.json must contain one JSON object")]

    pet_id = document.get("id")
    if not isinstance(pet_id, str) or PET_ID_PATTERN.fullmatch(pet_id) is None:
        findings.append(
            finding(
                "error",
                "manifest-id",
                "id must be a lowercase kebab-case identifier of at most 64 characters",
            )
        )
    display_name = document.get("displayName")
    if not isinstance(display_name, str) or not display_name.strip() or len(display_name) > 80:
        findings.append(
            finding(
                "error",
                "manifest-display-name",
                "displayName must be a non-empty string of at most 80 characters",
            )
        )
    description = document.get("description")
    if not isinstance(description, str) or not description.strip() or len(description) > 240:
        findings.append(
            finding(
                "error",
                "manifest-description",
                "description must be a non-empty string of at most 240 characters",
            )
        )
    if document.get("spriteVersionNumber") != 2:
        findings.append(
            finding(
                "error",
                "manifest-sprite-version",
                "spriteVersionNumber must be exactly 2 for an 8x11 Codex pet",
            )
        )
    _, path_error = safe_sprite_path(document.get("spritesheetPath"))
    if path_error:
        findings.append(finding("error", "manifest-sprite-path", path_error))
    return findings


def resolve_inside(root: Path, relative: PurePosixPath) -> Path:
    """Resolve a validated POSIX path and enforce containment."""
    root_resolved = root.resolve()
    candidate = root.joinpath(*relative.parts).resolve()
    if candidate != root_resolved and root_resolved not in candidate.parents:
        raise ValueError("resolved path escapes pet directory")
    return candidate
