from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from megumin_pet.packaging import PackageError, build_package, verify_package
from tests.helpers import make_pet


def test_package_is_byte_reproducible_and_verifiable(tmp_path: Path) -> None:
    pet = make_pet(tmp_path / "pet")
    first = tmp_path / "first.codex-pet"
    second = tmp_path / "second.codex-pet"
    first_result = build_package(pet, first)
    second_result = build_package(pet, second)
    assert first.read_bytes() == second.read_bytes()
    assert first_result["sha256"] == second_result["sha256"]
    verified = verify_package(first)
    assert verified["ok"]
    assert verified["pet_id"] == "fixture-pet"
    assert verified["entries"] == ["package.json", "pet.json", "spritesheet.webp"]


def test_packaging_refuses_invalid_pet(tmp_path: Path) -> None:
    pet = make_pet(tmp_path / "pet", changes={(0, 0): "blank"})
    with pytest.raises(PackageError, match="validation"):
        build_package(pet, tmp_path / "bad.codex-pet")


def test_verifier_rejects_traversal_duplicate_and_checksum_mismatch(tmp_path: Path) -> None:
    traversal = tmp_path / "traversal.codex-pet"
    with zipfile.ZipFile(traversal, "w") as archive:
        archive.writestr("../escape", b"bad")
    with pytest.raises(PackageError, match="unsafe"):
        verify_package(traversal)

    pet = make_pet(tmp_path / "pet")
    package = tmp_path / "pet.codex-pet"
    build_package(pet, package)
    tampered = tmp_path / "tampered.codex-pet"
    with zipfile.ZipFile(package) as source, zipfile.ZipFile(tampered, "w") as destination:
        for info in source.infolist():
            data = source.read(info)
            if info.filename == "pet.json":
                data += b" "
            destination.writestr(info.filename, data)
    with pytest.raises(PackageError, match="checksum mismatch"):
        verify_package(tampered)

    duplicate = tmp_path / "duplicate.codex-pet"
    metadata = {"schema": 1, "pet_id": "fixture-pet", "files": {"pet.json": "x"}}
    with (
        pytest.warns(UserWarning, match="Duplicate"),
        zipfile.ZipFile(duplicate, "w") as archive,
    ):
        archive.writestr("pet.json", b"one")
        archive.writestr("pet.json", b"two")
        archive.writestr("package.json", json.dumps(metadata))
    with pytest.raises(PackageError, match="duplicate"):
        verify_package(duplicate)


def test_verifier_rejects_missing_metadata_and_content_mismatch(tmp_path: Path) -> None:
    missing = tmp_path / "missing.codex-pet"
    with zipfile.ZipFile(missing, "w") as archive:
        archive.writestr("pet.json", "{}")
    with pytest.raises(PackageError, match=r"package\.json"):
        verify_package(missing)

    mismatched = tmp_path / "mismatched.codex-pet"
    metadata = {"schema": 1, "pet_id": "x", "files": {"pet.json": "abc"}}
    with zipfile.ZipFile(mismatched, "w") as archive:
        archive.writestr("pet.json", "{}")
        archive.writestr("extra.txt", "extra")
        archive.writestr("package.json", json.dumps(metadata))
    with pytest.raises(PackageError, match="contents"):
        verify_package(mismatched)


def test_missing_package_is_reported(tmp_path: Path) -> None:
    with pytest.raises(PackageError, match="not found"):
        verify_package(tmp_path / "missing.codex-pet")


def test_corrupt_zip_and_unsupported_entries_are_rejected(tmp_path: Path) -> None:
    corrupt = tmp_path / "corrupt.codex-pet"
    corrupt.write_bytes(b"not a zip")
    with pytest.raises(PackageError, match="invalid zip"):
        verify_package(corrupt)

    directory = tmp_path / "directory.codex-pet"
    with zipfile.ZipFile(directory, "w") as archive:
        archive.writestr("assets/", b"")
    with pytest.raises(PackageError, match="forbidden character"):
        verify_package(directory)

    compressed = tmp_path / "bzip2.codex-pet"
    with zipfile.ZipFile(compressed, "w", compression=zipfile.ZIP_BZIP2) as archive:
        archive.writestr("pet.json", b"{}")
        archive.writestr("package.json", b"{}")
    with pytest.raises(PackageError, match="unsupported compression"):
        verify_package(compressed)
