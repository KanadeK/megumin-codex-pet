from __future__ import annotations

from pathlib import Path, PurePosixPath

import pytest

from megumin_pet.contract import (
    ACTIVE_CELLS,
    ATLAS_HEIGHT,
    ATLAS_WIDTH,
    cell_key,
    cell_label,
    resolve_inside,
    safe_sprite_path,
    validate_manifest,
)


def valid_manifest() -> dict[str, object]:
    return {
        "id": "megumin",
        "displayName": "Megumin",
        "description": "A test manifest.",
        "spriteVersionNumber": 2,
        "spritesheetPath": "spritesheet.webp",
    }


def test_contract_dimensions_and_active_cell_count() -> None:
    assert (ATLAS_WIDTH, ATLAS_HEIGHT) == (1536, 2288)
    assert len(ACTIVE_CELLS) == 73
    assert len(set(ACTIVE_CELLS)) == 73
    assert cell_key(10, 7) == "r10c07"
    assert cell_label(0, 0) == "idle:0"
    assert cell_label(10, 7) == "look:337.5"


@pytest.mark.parametrize(
    ("path", "valid"),
    [
        ("spritesheet.webp", True),
        ("assets/spritesheet.png", True),
        ("../escape.webp", False),
        ("/absolute.webp", False),
        ("assets\\sprite.webp", False),
        ("assets//sprite.webp", False),
        ("C:/sprite.webp", False),
        ("sprite\n.webp", False),
        ("sprite.gif", False),
        ("", False),
        (None, False),
    ],
)
def test_safe_sprite_path(path: object, valid: bool) -> None:
    parsed, error = safe_sprite_path(path)
    assert (parsed is not None) is valid
    assert (error is None) is valid


def test_manifest_validation_reports_each_required_field() -> None:
    assert validate_manifest(valid_manifest()) == []
    broken = {
        "id": "Not Safe!",
        "displayName": "",
        "description": "",
        "spriteVersionNumber": 1,
        "spritesheetPath": "../sprite.gif",
    }
    codes = {item["code"] for item in validate_manifest(broken)}
    assert codes == {
        "manifest-id",
        "manifest-display-name",
        "manifest-description",
        "manifest-sprite-version",
        "manifest-sprite-path",
    }
    assert validate_manifest([])[0]["code"] == "manifest-not-object"


def test_resolve_inside_enforces_containment(tmp_path: Path) -> None:
    expected = tmp_path / "assets" / "pet.webp"
    assert resolve_inside(tmp_path, PurePosixPath("assets/pet.webp")) == expected.resolve()
    with pytest.raises(ValueError, match="escapes"):
        resolve_inside(tmp_path, PurePosixPath("../escape.webp"))
