from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from megumin_pet.previews import (
    PreviewError,
    audit_gif,
    audit_previews,
    parse_rgb,
    render_previews,
)
from tests.helpers import make_pet


def test_render_and_audit_previews(tmp_path: Path) -> None:
    pet = make_pet(tmp_path / "pet")
    previews = tmp_path / "previews"
    sheet = tmp_path / "background-check.png"

    report = render_previews(pet, previews, qa_sheet=sheet)

    assert report["ok"] is True
    assert report["error_count"] == 0
    assert report["source"]["alpha_threshold"] == 128
    assert report["background_check"]["size"] == [1212, 726]
    assert sheet.is_file()
    assert sorted(path.name for path in previews.glob("*.gif")) == [
        "failed.gif",
        "idle.gif",
        "jumping.gif",
        "review.gif",
        "running-left.gif",
        "running-right.gif",
        "running.gif",
        "waiting.gif",
        "waving.gif",
    ]
    assert report["previews"]["idle"]["frames"] == 6
    assert report["previews"]["idle"]["durations_ms"] == [280, 110, 110, 140, 140, 320]


def test_audit_gif_detects_green_boundary(tmp_path: Path) -> None:
    image = Image.new("RGBA", (24, 24), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rectangle((5, 5, 18, 18), fill=(0, 255, 0, 255))
    draw.rectangle((7, 7, 16, 16), fill=(160, 32, 28, 255))
    path = tmp_path / "fringe.gif"
    image.save(path, format="GIF", transparency=0, disposal=2)

    report = audit_gif(path)

    assert report["frames"] == 1
    assert report["chroma_boundary_pixels"] > 0


def test_audit_previews_reports_missing_files(tmp_path: Path) -> None:
    report = audit_previews(tmp_path)

    assert report["ok"] is False
    assert report["error_count"] == 9
    assert {finding["code"] for finding in report["findings"]} == {"preview-missing"}


def test_preview_input_validation(tmp_path: Path) -> None:
    assert parse_rgb("#00ff00") == (0, 255, 0)
    with pytest.raises(ValueError, match="invalid RGB color"):
        parse_rgb("not-a-color")
    with pytest.raises(ValueError, match="alpha threshold"):
        render_previews(make_pet(tmp_path / "pet"), tmp_path / "out", alpha_threshold=256)
    with pytest.raises(ValueError, match="chroma distance"):
        audit_gif(tmp_path / "missing.gif", chroma_distance=442)
    with pytest.raises(PreviewError, match="not found"):
        audit_gif(tmp_path / "missing.gif")
