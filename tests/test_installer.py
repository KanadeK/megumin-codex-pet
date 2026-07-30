from __future__ import annotations

from pathlib import Path

import pytest

from megumin_pet.installer import InstallError, doctor, install, uninstall
from megumin_pet.packaging import build_package
from tests.helpers import make_pet


def test_install_doctor_replace_backup_and_recoverable_uninstall(tmp_path: Path) -> None:
    codex_home = tmp_path / "codex"
    first_pet = make_pet(tmp_path / "first")
    first = install(first_pet, codex_home)
    assert first["ok"]
    assert first["backup"] is None
    assert doctor("fixture-pet", codex_home)["ok"]

    second_pet = make_pet(tmp_path / "second", changes={(0, 0): "recolor"})
    second = install(second_pet, codex_home)
    assert second["ok"]
    assert second["backup"] is not None
    assert Path(second["backup"]).is_dir()
    assert second["atlas_sha256"] != first["atlas_sha256"]

    removed = uninstall("fixture-pet", codex_home)
    assert removed["ok"]
    assert not (codex_home / "pets" / "fixture-pet").exists()
    assert Path(removed["recoverable_at"]).is_dir()


def test_install_from_verified_package(tmp_path: Path) -> None:
    pet = make_pet(tmp_path / "pet")
    package = tmp_path / "fixture.codex-pet"
    build_package(pet, package)
    result = install(package, tmp_path / "codex")
    assert result["pet_id"] == "fixture-pet"
    assert (tmp_path / "codex" / "pets" / "fixture-pet" / "spritesheet.webp").is_file()


def test_doctor_detects_lock_drift(tmp_path: Path) -> None:
    first = make_pet(tmp_path / "first")
    codex_home = tmp_path / "codex"
    install(first, codex_home)
    lock = tmp_path / "lock.json"
    lock.write_text(
        '{"atlas":{"sha256":"definitely-not-the-installed-hash"}}',
        encoding="utf-8",
    )
    report = doctor("fixture-pet", codex_home, lock)
    assert not report["ok"]
    assert report["findings"][-1]["code"] == "installed-lock-drift"


def test_invalid_ids_missing_pet_and_install_lock_are_safe(tmp_path: Path) -> None:
    with pytest.raises(InstallError, match="kebab"):
        doctor("../escape", tmp_path)
    with pytest.raises(InstallError, match="not found"):
        uninstall("fixture-pet", tmp_path)

    pet = make_pet(tmp_path / "pet")
    pets_root = tmp_path / "codex" / "pets"
    pets_root.mkdir(parents=True)
    (pets_root / ".petdiff-install.lock").write_text("busy", encoding="utf-8")
    with pytest.raises(InstallError, match="another"):
        install(pet, tmp_path / "codex")


def test_invalid_source_is_refused(tmp_path: Path) -> None:
    pet = make_pet(tmp_path / "bad", changes={(0, 0): "blank"})
    with pytest.raises(InstallError, match="validation"):
        install(pet, tmp_path / "codex")
