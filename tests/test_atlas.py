from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from megumin_pet.atlas import inspect_pet, mean_byte_delta
from megumin_pet.contract import ACTIVE_CELL_KEYS
from tests.helpers import make_pet


def test_valid_pet_produces_complete_deterministic_snapshot(tmp_path: Path) -> None:
    pet = make_pet(tmp_path / "pet")
    first = inspect_pet(pet)
    second = inspect_pet(pet)
    assert first == second
    assert first["validation"]["ok"]
    assert first["validation"]["error_count"] == 0
    assert len(first["cells"]) == 88
    assert sum(cell["required"] for cell in first["cells"].values()) == len(ACTIVE_CELL_KEYS)
    assert sum(cell["optional"] for cell in first["cells"].values()) == 1
    assert first["contract"]["optional_cells"] == 1
    assert first["contract"]["reserved_cells"] == 14
    assert first["atlas"]["size"] == [1536, 2288]
    assert first["motion"]["look-clockwise"]["frames"] == 16


def test_visible_optional_neutral_cell_is_valid_and_edge_checked(tmp_path: Path) -> None:
    visible = inspect_pet(make_pet(tmp_path / "visible", changes={(0, 6): "recolor"}))
    assert visible["validation"]["ok"]
    assert visible["cells"]["r00c06"]["label"] == "neutral"
    assert visible["cells"]["r00c06"]["optional"]
    assert not visible["cells"]["r00c06"]["required"]

    clipped = inspect_pet(make_pet(tmp_path / "clipped", changes={(0, 6): "edge"}))
    finding = next(
        item
        for item in clipped["validation"]["findings"]
        if item["code"] == "cell-edge-contact"
    )
    assert finding["cell"] == "r00c06"


def test_blank_required_and_visible_unused_cells_fail(tmp_path: Path) -> None:
    pet = make_pet(
        tmp_path / "pet",
        changes={(0, 0): "blank", (0, 7): "recolor"},
    )
    report = inspect_pet(pet)
    codes = {item["code"] for item in report["validation"]["findings"]}
    assert not report["validation"]["ok"]
    assert "required-cell-empty" in codes
    assert "unused-cell-visible" in codes


def test_edge_contact_is_a_hard_failure(tmp_path: Path) -> None:
    report = inspect_pet(make_pet(tmp_path / "pet", changes={(1, 0): "edge"}))
    finding = next(
        item for item in report["validation"]["findings"] if item["code"] == "cell-edge-contact"
    )
    assert finding["cell"] == "r01c00"
    assert finding["detail"]["edge_alpha"] > 0


def test_missing_bad_manifest_and_bad_dimensions_are_reported(tmp_path: Path) -> None:
    missing = inspect_pet(tmp_path / "missing")
    assert missing["validation"]["findings"][0]["code"] == "manifest-missing"

    malformed = tmp_path / "malformed"
    malformed.mkdir()
    (malformed / "pet.json").write_text("{no", encoding="utf-8")
    assert inspect_pet(malformed)["validation"]["findings"][0]["code"] == "manifest-unreadable"

    pet = make_pet(tmp_path / "wrong-size")
    Image.new("RGBA", (10, 10), (0, 0, 0, 0)).save(pet / "spritesheet.webp", "WEBP")
    report = inspect_pet(pet)
    assert any(item["code"] == "atlas-dimensions" for item in report["validation"]["findings"])


def test_missing_and_unreadable_atlas_are_reported(tmp_path: Path) -> None:
    missing = make_pet(tmp_path / "missing-atlas")
    (missing / "spritesheet.webp").unlink()
    assert any(
        item["code"] == "atlas-missing"
        for item in inspect_pet(missing)["validation"]["findings"]
    )

    unreadable = make_pet(tmp_path / "unreadable")
    (unreadable / "spritesheet.webp").write_bytes(b"not an image")
    assert any(
        item["code"] == "atlas-unreadable"
        for item in inspect_pet(unreadable)["validation"]["findings"]
    )


def test_manifest_list_does_not_crash_inspection(tmp_path: Path) -> None:
    root = tmp_path / "list"
    root.mkdir()
    (root / "pet.json").write_text(json.dumps([]), encoding="utf-8")
    report = inspect_pet(root)
    assert report["manifest"] == {}
    assert report["validation"]["findings"][0]["code"] == "manifest-not-object"


def test_byte_delta_handles_equal_and_different_inputs() -> None:
    assert mean_byte_delta("00ff", "00ff") == 0
    assert mean_byte_delta("0000", "ffff") == 1
    assert mean_byte_delta("", "") == 1
    assert mean_byte_delta("00", "0000") == 1
