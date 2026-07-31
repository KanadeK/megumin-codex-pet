"""Deterministic transparent GIF previews and chroma-fringe auditing."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageColor, ImageDraw, ImageFilter, ImageSequence

from .atlas import inspect_pet
from .contract import (
    ATLAS_HEIGHT,
    ATLAS_WIDTH,
    CELL_HEIGHT,
    CELL_WIDTH,
    STATE_LAYOUT,
    TOOL_VERSION,
    resolve_inside,
    safe_sprite_path,
)

DEFAULT_ALPHA_THRESHOLD = 128
DEFAULT_CHROMA_KEY = (0, 255, 0)
DEFAULT_CHROMA_DISTANCE = 96
PREVIEW_SCHEMA = 1


class PreviewError(RuntimeError):
    """Raised when transparent previews cannot be rendered or inspected."""


def _report_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def parse_rgb(value: str) -> tuple[int, int, int]:
    """Parse a CSS-style RGB color for command-line options."""
    try:
        parsed = ImageColor.getrgb(value)
    except ValueError as exc:
        raise ValueError(f"invalid RGB color: {value}") from exc
    if len(parsed) != 3:
        raise ValueError(f"RGB color must not include alpha: {value}")
    return int(parsed[0]), int(parsed[1]), int(parsed[2])


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_atlas(pet_dir: Path) -> tuple[Path, Image.Image]:
    snapshot = inspect_pet(pet_dir)
    if not snapshot["validation"]["ok"]:
        raise PreviewError("pet failed validation; preview rendering refused")
    manifest = snapshot["manifest"]
    relative, path_error = safe_sprite_path(manifest.get("spritesheetPath"))
    if relative is None or path_error is not None:
        raise PreviewError(path_error or "spritesheetPath is invalid")
    atlas_path = resolve_inside(pet_dir.resolve(), relative)
    with Image.open(atlas_path) as opened:
        atlas = opened.convert("RGBA")
        atlas.load()
    if atlas.size != (ATLAS_WIDTH, ATLAS_HEIGHT):
        raise PreviewError(f"atlas must be {ATLAS_WIDTH}x{ATLAS_HEIGHT}")
    return atlas_path, atlas


def _gif_frame(frame: Image.Image, alpha_threshold: int) -> Image.Image:
    rgba = frame.convert("RGBA")
    alpha = rgba.getchannel("A")
    visible = alpha.point(lambda value: 255 if value >= alpha_threshold else 0, mode="L")
    rgb = Image.new("RGB", rgba.size, (0, 0, 0))
    rgb.paste(rgba.convert("RGB"), mask=visible)
    indexed = rgb.quantize(
        colors=255,
        method=Image.Quantize.MEDIANCUT,
        dither=Image.Dither.NONE,
    )
    transparent = visible.point(lambda value: 0 if value else 255, mode="L")
    indexed.paste(255, mask=transparent)
    palette = indexed.getpalette() or []
    palette.extend([0] * (768 - len(palette)))
    palette[765:768] = [0, 0, 0]
    indexed.putpalette(palette[:768])
    indexed.info["transparency"] = 255
    indexed.info["disposal"] = 2
    return indexed


def _save_gif(
    path: Path,
    frames: list[Image.Image],
    durations_ms: list[int],
    alpha_threshold: int,
) -> None:
    if not frames or len(frames) != len(durations_ms):
        raise PreviewError("preview frames and durations must be non-empty and aligned")
    indexed = [_gif_frame(frame, alpha_threshold) for frame in frames]
    path.parent.mkdir(parents=True, exist_ok=True)
    indexed[0].save(
        path,
        format="GIF",
        save_all=True,
        append_images=indexed[1:],
        duration=durations_ms,
        loop=0,
        disposal=2,
        transparency=255,
        optimize=False,
        include_color_table=True,
    )


def _boundary_chroma_count(
    frame: Image.Image,
    chroma_key: tuple[int, int, int],
    chroma_distance: int,
) -> int:
    rgba = frame.convert("RGBA")
    alpha = rgba.getchannel("A")
    visible = alpha.point(lambda value: 255 if value else 0, mode="L")
    transparent = alpha.point(lambda value: 255 if not value else 0, mode="L")
    near_transparency = transparent.filter(ImageFilter.MaxFilter(3))
    boundary = bytes(
        left & right
        for left, right in zip(
            bytes(visible.tobytes()),
            bytes(near_transparency.tobytes()),
            strict=True,
        )
    )
    maximum_delta = chroma_distance * chroma_distance
    count = 0
    pixels = bytes(rgba.tobytes())
    for index, marker in enumerate(boundary):
        if not marker:
            continue
        offset = index * 4
        red, green, blue = pixels[offset : offset + 3]
        distance = (
            (red - chroma_key[0]) ** 2
            + (green - chroma_key[1]) ** 2
            + (blue - chroma_key[2]) ** 2
        )
        if distance <= maximum_delta:
            count += 1
    return count


def audit_gif(
    path: Path,
    *,
    chroma_key: tuple[int, int, int] = DEFAULT_CHROMA_KEY,
    chroma_distance: int = DEFAULT_CHROMA_DISTANCE,
) -> dict[str, Any]:
    """Audit one transparent GIF for visible chroma-colored boundary pixels."""
    if chroma_distance < 0 or chroma_distance > 441:
        raise ValueError("chroma distance must be between 0 and 441")
    if not path.is_file():
        raise PreviewError(f"preview was not found: {path}")
    try:
        with Image.open(path) as opened:
            if opened.format != "GIF":
                raise PreviewError(f"preview is not a GIF: {path}")
            size = list(opened.size)
            frames = [frame.convert("RGBA") for frame in ImageSequence.Iterator(opened)]
            durations = [
                int(frame.info.get("duration", opened.info.get("duration", 0)))
                for frame in ImageSequence.Iterator(opened)
            ]
    except OSError as exc:
        raise PreviewError(f"preview could not be read: {path}: {exc}") from exc
    per_frame = [
        _boundary_chroma_count(frame, chroma_key, chroma_distance) for frame in frames
    ]
    return {
        "path": _report_path(path),
        "sha256": _sha256(path),
        "size": size,
        "frames": len(frames),
        "durations_ms": durations,
        "chroma_boundary_pixels": sum(per_frame),
        "chroma_boundary_pixels_by_frame": per_frame,
    }


def audit_previews(
    previews_dir: Path,
    *,
    chroma_key: tuple[int, int, int] = DEFAULT_CHROMA_KEY,
    chroma_distance: int = DEFAULT_CHROMA_DISTANCE,
) -> dict[str, Any]:
    """Audit all nine standard-row previews against the executable contract."""
    reports: dict[str, dict[str, Any]] = {}
    findings: list[dict[str, Any]] = []
    for state in STATE_LAYOUT:
        name = str(state["name"])
        path = previews_dir / f"{name}.gif"
        if not path.is_file():
            findings.append(
                {
                    "severity": "error",
                    "code": "preview-missing",
                    "state": name,
                    "message": f"missing preview: {path.as_posix()}",
                }
            )
            continue
        report = audit_gif(
            path,
            chroma_key=chroma_key,
            chroma_distance=chroma_distance,
        )
        reports[name] = report
        expected_frames = int(state["frames"])
        expected_durations = [int(value) for value in state["durations_ms"]]
        if report["size"] != [CELL_WIDTH, CELL_HEIGHT]:
            findings.append(
                {
                    "severity": "error",
                    "code": "preview-dimensions",
                    "state": name,
                    "message": f"{name} must be {CELL_WIDTH}x{CELL_HEIGHT}",
                    "detail": {"actual": report["size"]},
                }
            )
        if report["frames"] != expected_frames:
            findings.append(
                {
                    "severity": "error",
                    "code": "preview-frame-count",
                    "state": name,
                    "message": f"{name} must contain {expected_frames} frames",
                    "detail": {"actual": report["frames"]},
                }
            )
        if report["durations_ms"] != expected_durations:
            findings.append(
                {
                    "severity": "error",
                    "code": "preview-duration",
                    "state": name,
                    "message": f"{name} frame durations do not match the contract",
                    "detail": {
                        "actual": report["durations_ms"],
                        "expected": expected_durations,
                    },
                }
            )
        if report["chroma_boundary_pixels"]:
            findings.append(
                {
                    "severity": "error",
                    "code": "preview-chroma-fringe",
                    "state": name,
                    "message": f"{name} contains visible chroma-colored boundary pixels",
                    "detail": {
                        "pixels": report["chroma_boundary_pixels"],
                        "chroma_key": list(chroma_key),
                        "distance": chroma_distance,
                    },
                }
            )
    findings.sort(key=lambda finding: (str(finding["code"]), str(finding["state"])))
    return {
        "schema": PREVIEW_SCHEMA,
        "tool": {"name": "petdiff", "version": TOOL_VERSION},
        "directory": _report_path(previews_dir),
        "chroma_key": list(chroma_key),
        "chroma_distance": chroma_distance,
        "ok": not findings,
        "error_count": len(findings),
        "findings": findings,
        "previews": reports,
    }


def _representative_frame(path: Path) -> Image.Image:
    with Image.open(path) as opened:
        frames = [frame.convert("RGBA") for frame in ImageSequence.Iterator(opened)]
    if not frames:
        raise PreviewError(f"preview contains no frames: {path}")
    return frames[len(frames) // 2]


def render_background_check(previews_dir: Path, output: Path) -> dict[str, Any]:
    """Render actual GIF frames on light and dark backgrounds for visual QA."""
    columns = 3
    tile_width = CELL_WIDTH * 2 + 20
    tile_height = CELL_HEIGHT + 34
    rows = (len(STATE_LAYOUT) + columns - 1) // columns
    sheet = Image.new("RGB", (tile_width * columns, tile_height * rows), (216, 211, 202))
    draw = ImageDraw.Draw(sheet)
    light = (246, 241, 230, 255)
    dark = (29, 24, 34, 255)
    for index, state in enumerate(STATE_LAYOUT):
        name = str(state["name"])
        frame = _representative_frame(previews_dir / f"{name}.gif")
        x = (index % columns) * tile_width
        y = (index // columns) * tile_height
        draw.rectangle((x, y, x + tile_width - 1, y + tile_height - 1), fill=(216, 211, 202))
        draw.text((x + 7, y + 6), f"{name}  |  light / dark", fill=(40, 34, 38))
        light_panel = Image.new("RGBA", frame.size, light)
        dark_panel = Image.new("RGBA", frame.size, dark)
        light_panel.alpha_composite(frame)
        dark_panel.alpha_composite(frame)
        sheet.paste(light_panel.convert("RGB"), (x + 6, y + 28))
        sheet.paste(dark_panel.convert("RGB"), (x + CELL_WIDTH + 14, y + 28))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, format="PNG", optimize=True)
    return {
        "path": _report_path(output),
        "sha256": _sha256(output),
        "size": list(sheet.size),
    }


def render_previews(
    pet_dir: Path,
    output_dir: Path,
    *,
    qa_sheet: Path | None = None,
    alpha_threshold: int = DEFAULT_ALPHA_THRESHOLD,
    chroma_key: tuple[int, int, int] = DEFAULT_CHROMA_KEY,
    chroma_distance: int = DEFAULT_CHROMA_DISTANCE,
) -> dict[str, Any]:
    """Render all standard rows from the final pet atlas and audit the GIFs."""
    if alpha_threshold < 0 or alpha_threshold > 255:
        raise ValueError("alpha threshold must be between 0 and 255")
    atlas_path, atlas = _load_atlas(pet_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for state in STATE_LAYOUT:
        row = int(state["row"])
        frames = [
            atlas.crop(
                (
                    column * CELL_WIDTH,
                    row * CELL_HEIGHT,
                    (column + 1) * CELL_WIDTH,
                    (row + 1) * CELL_HEIGHT,
                )
            )
            for column in range(int(state["frames"]))
        ]
        _save_gif(
            output_dir / f"{state['name']}.gif",
            frames,
            [int(value) for value in state["durations_ms"]],
            alpha_threshold,
        )
    report = audit_previews(
        output_dir,
        chroma_key=chroma_key,
        chroma_distance=chroma_distance,
    )
    report["source"] = {
        "pet": _report_path(pet_dir),
        "atlas": _report_path(atlas_path),
        "atlas_sha256": _sha256(atlas_path),
        "alpha_threshold": alpha_threshold,
    }
    if qa_sheet is not None:
        report["background_check"] = render_background_check(output_dir, qa_sheet)
    return report


def write_preview_report(report: dict[str, Any], path: Path) -> None:
    """Write a stable UTF-8 JSON preview report."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
