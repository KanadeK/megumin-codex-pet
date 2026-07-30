"""Atlas inspection, metrics, and strict contract validation."""

from __future__ import annotations

import hashlib
import json
from itertools import pairwise
from pathlib import Path
from typing import Any

from PIL import Image

from .contract import (
    ACTIVE_CELL_KEYS,
    ATLAS_HEIGHT,
    ATLAS_WIDTH,
    CELL_HEIGHT,
    CELL_WIDTH,
    COLUMNS,
    LOOK_ANGLES,
    OPTIONAL_CELL_KEYS,
    RESERVED_CELL_KEYS,
    ROWS,
    SNAPSHOT_SCHEMA,
    STATE_LAYOUT,
    TOOL_VERSION,
    cell_key,
    cell_label,
    finding,
    resolve_inside,
    safe_sprite_path,
    validate_manifest,
)


class PetInspectionError(RuntimeError):
    """Raised when a pet cannot be inspected."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _byte_fingerprint(image: Image.Image, mode: str) -> str:
    resized = image.convert(mode).resize((16, 16), Image.Resampling.BOX)
    return bytes(resized.tobytes()).hex()


def _cell_metrics(cell: Image.Image, row: int, column: int) -> dict[str, Any]:
    rgba = cell.convert("RGBA")
    alpha = rgba.getchannel("A")
    alpha_values = bytes(alpha.tobytes())
    alpha_sum = sum(alpha_values)
    visible_pixels = sum(1 for value in alpha_values if value)
    opaque_pixels = sum(1 for value in alpha_values if value == 255)
    bbox = alpha.getbbox()

    weighted_x = 0
    weighted_y = 0
    if alpha_sum:
        for index, value in enumerate(alpha_values):
            if value:
                weighted_x += (index % CELL_WIDTH) * value
                weighted_y += (index // CELL_WIDTH) * value
        centroid: list[float] | None = [
            round(weighted_x / alpha_sum, 4),
            round(weighted_y / alpha_sum, 4),
        ]
    else:
        centroid = None

    edge_alpha = (
        sum(alpha_values[:CELL_WIDTH])
        + sum(alpha_values[-CELL_WIDTH:])
        + sum(alpha_values[offset] for offset in range(0, len(alpha_values), CELL_WIDTH))
        + sum(
            alpha_values[offset]
            for offset in range(CELL_WIDTH - 1, len(alpha_values), CELL_WIDTH)
        )
    )
    key = cell_key(row, column)
    return {
        "key": key,
        "label": cell_label(row, column),
        "row": row,
        "column": column,
        "required": key in ACTIVE_CELL_KEYS,
        "optional": key in OPTIONAL_CELL_KEYS,
        "visible_pixels": visible_pixels,
        "opaque_pixels": opaque_pixels,
        "alpha_area": round(alpha_sum / 255.0, 4),
        "bbox": list(bbox) if bbox else None,
        "centroid": centroid,
        "edge_alpha": edge_alpha,
        "silhouette_16": _byte_fingerprint(alpha, "L"),
        "rgba_16": _byte_fingerprint(rgba, "RGBA"),
    }


def _mean_byte_delta(left_hex: str, right_hex: str) -> float:
    left = bytes.fromhex(left_hex)
    right = bytes.fromhex(right_hex)
    if len(left) != len(right) or not left:
        return 1.0
    return round(sum(abs(a - b) for a, b in zip(left, right, strict=True)) / (255 * len(left)), 6)


def _motion_metrics(cells: list[dict[str, Any]], *, loop: bool) -> dict[str, Any]:
    pairs = list(pairwise(cells))
    if loop and len(cells) > 1:
        pairs.append((cells[-1], cells[0]))
    centroid_steps: list[float] = []
    silhouette_steps: list[float] = []
    area_steps: list[float] = []
    for left, right in pairs:
        left_centroid = left["centroid"]
        right_centroid = right["centroid"]
        if left_centroid is not None and right_centroid is not None:
            x_delta = float(right_centroid[0]) - float(left_centroid[0])
            y_delta = float(right_centroid[1]) - float(left_centroid[1])
            centroid_steps.append(round((x_delta * x_delta + y_delta * y_delta) ** 0.5, 4))
        silhouette_steps.append(
            _mean_byte_delta(str(left["silhouette_16"]), str(right["silhouette_16"]))
        )
        left_area = float(left["alpha_area"])
        right_area = float(right["alpha_area"])
        area_steps.append(round(abs(right_area - left_area) / max(left_area, 1.0), 6))
    return {
        "frames": len(cells),
        "centroid_step_mean": round(sum(centroid_steps) / max(len(centroid_steps), 1), 4),
        "centroid_step_max": round(max(centroid_steps, default=0.0), 4),
        "silhouette_step_mean": round(sum(silhouette_steps) / max(len(silhouette_steps), 1), 6),
        "silhouette_step_max": round(max(silhouette_steps, default=0.0), 6),
        "alpha_area_step_mean": round(sum(area_steps) / max(len(area_steps), 1), 6),
        "alpha_area_step_max": round(max(area_steps, default=0.0), 6),
    }


def _validation_for_cells(cells: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for key in sorted(cells):
        metrics = cells[key]
        required = bool(metrics["required"])
        optional = bool(metrics["optional"])
        visible_pixels = int(metrics["visible_pixels"])
        if required and visible_pixels == 0:
            findings.append(
                finding(
                    "error",
                    "required-cell-empty",
                    f"{metrics['label']} is required but fully transparent",
                    cell=key,
                )
            )
        if not required and not optional and visible_pixels != 0:
            findings.append(
                finding(
                    "error",
                    "unused-cell-visible",
                    f"{metrics['label']} is reserved and must be fully transparent",
                    cell=key,
                    detail={"visible_pixels": metrics["visible_pixels"]},
                )
            )
        if (required or optional) and visible_pixels != 0 and int(metrics["edge_alpha"]) != 0:
            findings.append(
                finding(
                    "error",
                    "cell-edge-contact",
                    f"{metrics['label']} touches its cell boundary and may be clipped",
                    cell=key,
                    detail={"edge_alpha": metrics["edge_alpha"]},
                )
            )

    look_fingerprints = {
        str(cells[cell_key(row, column)]["rgba_16"])
        for row in (9, 10)
        for column in range(COLUMNS)
        if cell_key(row, column) in cells
    }
    if len(look_fingerprints) < 8:
        findings.append(
            finding(
                "warning",
                "look-low-diversity",
                "The 16 look cells contain fewer than eight distinct low-resolution poses",
                detail={"unique_poses": len(look_fingerprints)},
            )
        )
    return findings


def inspect_pet(pet_dir: Path) -> dict[str, Any]:
    """Inspect one unpacked pet and return a deterministic snapshot."""
    root = pet_dir.resolve()
    findings: list[dict[str, Any]] = []
    manifest_path = root / "pet.json"
    manifest: dict[str, Any] = {}
    if not manifest_path.is_file():
        findings.append(finding("error", "manifest-missing", "pet.json was not found"))
    else:
        try:
            loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            findings.append(
                finding("error", "manifest-unreadable", f"pet.json could not be read: {exc}")
            )
        else:
            if isinstance(loaded, dict):
                manifest = loaded
            findings.extend(validate_manifest(loaded))

    snapshot: dict[str, Any] = {
        "schema": SNAPSHOT_SCHEMA,
        "tool": {"name": "petdiff", "version": TOOL_VERSION},
        "contract": {
            "spriteVersionNumber": 2,
            "atlas": [ATLAS_WIDTH, ATLAS_HEIGHT],
            "grid": [COLUMNS, ROWS],
            "cell": [CELL_WIDTH, CELL_HEIGHT],
            "required_cells": len(ACTIVE_CELL_KEYS),
            "optional_cells": len(OPTIONAL_CELL_KEYS),
            "reserved_cells": len(RESERVED_CELL_KEYS),
        },
        "manifest": manifest,
        "atlas": None,
        "cells": {},
        "motion": {},
        "validation": {"ok": False, "error_count": 0, "warning_count": 0, "findings": []},
    }

    sprite_path, path_error = safe_sprite_path(manifest.get("spritesheetPath"))
    if path_error is None and sprite_path is not None:
        try:
            atlas_path = resolve_inside(root, sprite_path)
        except ValueError as exc:
            findings.append(finding("error", "atlas-path-escape", str(exc)))
        else:
            if not atlas_path.is_file():
                findings.append(
                    finding("error", "atlas-missing", f"spritesheet was not found: {sprite_path}")
                )
            else:
                try:
                    with Image.open(atlas_path) as opened:
                        source_format = opened.format or "unknown"
                        source_mode = opened.mode
                        source_size = list(opened.size)
                        rgba = opened.convert("RGBA")
                        rgba.load()
                except (OSError, ValueError) as exc:
                    findings.append(
                        finding(
                            "error",
                            "atlas-unreadable",
                            f"spritesheet could not be read: {exc}",
                        )
                    )
                else:
                    snapshot["atlas"] = {
                        "path": sprite_path.as_posix(),
                        "format": source_format,
                        "source_mode": source_mode,
                        "size": source_size,
                        "bytes": atlas_path.stat().st_size,
                        "sha256": _sha256(atlas_path),
                    }
                    if rgba.size != (ATLAS_WIDTH, ATLAS_HEIGHT):
                        findings.append(
                            finding(
                                "error",
                                "atlas-dimensions",
                                f"atlas must be {ATLAS_WIDTH}x{ATLAS_HEIGHT}",
                                detail={"actual": source_size},
                            )
                        )
                    else:
                        cells: dict[str, dict[str, Any]] = {}
                        for row in range(ROWS):
                            for column in range(COLUMNS):
                                box = (
                                    column * CELL_WIDTH,
                                    row * CELL_HEIGHT,
                                    (column + 1) * CELL_WIDTH,
                                    (row + 1) * CELL_HEIGHT,
                                )
                                metrics = _cell_metrics(rgba.crop(box), row, column)
                                cells[str(metrics["key"])] = metrics
                        snapshot["cells"] = cells
                        findings.extend(_validation_for_cells(cells))

                        motion: dict[str, Any] = {}
                        for state in STATE_LAYOUT:
                            row = int(state["row"])
                            state_cells = [
                                cells[cell_key(row, column)]
                                for column in range(int(state["frames"]))
                            ]
                            motion[str(state["name"])] = _motion_metrics(state_cells, loop=True)
                        look_cells = [
                            cells[cell_key(row, column)]
                            for row in (9, 10)
                            for column in range(COLUMNS)
                        ]
                        motion["look-clockwise"] = {
                            **_motion_metrics(look_cells, loop=True),
                            "angles": list(LOOK_ANGLES),
                        }
                        snapshot["motion"] = motion

    findings.sort(
        key=lambda item: (
            str(item["severity"]),
            str(item["code"]),
            str(item.get("cell", "")),
        )
    )
    error_count = sum(item["severity"] == "error" for item in findings)
    warning_count = sum(item["severity"] == "warning" for item in findings)
    snapshot["validation"] = {
        "ok": error_count == 0,
        "error_count": error_count,
        "warning_count": warning_count,
        "findings": findings,
    }
    return snapshot


def mean_byte_delta(left_hex: str, right_hex: str) -> float:
    """Public wrapper used by PetDiff."""
    return _mean_byte_delta(left_hex, right_hex)
