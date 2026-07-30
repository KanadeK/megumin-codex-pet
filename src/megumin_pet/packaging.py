"""Deterministic package creation and archive safety checks."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from .atlas import inspect_pet
from .contract import PACKAGE_SCHEMA, TOOL_VERSION, resolve_inside, safe_sprite_path

FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)
MAX_ENTRY_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 96 * 1024 * 1024


class PackageError(RuntimeError):
    """Raised for an invalid source pet or unsafe package."""


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, FIXED_ZIP_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    info.flag_bits |= 0x800
    return info


def build_package(pet_dir: Path, output: Path) -> dict[str, Any]:
    """Build one byte-reproducible .codex-pet archive."""
    snapshot = inspect_pet(pet_dir)
    if not bool(snapshot["validation"]["ok"]):
        raise PackageError("pet failed validation; packaging refused")
    manifest = snapshot["manifest"]
    sprite_relative, error = safe_sprite_path(manifest.get("spritesheetPath"))
    if error or sprite_relative is None:
        raise PackageError(error or "invalid spritesheet path")

    root = pet_dir.resolve()
    files: dict[str, bytes] = {
        "pet.json": (root / "pet.json").read_bytes(),
        sprite_relative.as_posix(): resolve_inside(root, sprite_relative).read_bytes(),
    }
    checksums = {name: _digest(data) for name, data in sorted(files.items())}
    metadata = {
        "schema": PACKAGE_SCHEMA,
        "tool": {"name": "petdiff", "version": TOOL_VERSION},
        "pet_id": manifest["id"],
        "files": checksums,
    }
    files["package.json"] = (
        json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode()

    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", allowZip64=False) as archive:
        for name, data in sorted(files.items()):
            archive.writestr(_zip_info(name), data, compresslevel=9)
    package_bytes = output.read_bytes()
    return {
        "ok": True,
        "path": str(output.resolve()),
        "bytes": len(package_bytes),
        "sha256": _digest(package_bytes),
        "pet_id": manifest["id"],
        "entries": sorted(files),
    }


def _safe_archive_name(raw: str) -> PurePosixPath:
    if (
        "\\" in raw
        or ":" in raw
        or raw.endswith("/")
        or any(ord(character) < 32 for character in raw)
    ):
        raise PackageError(f"archive entry contains a forbidden character: {raw}")
    path = PurePosixPath(raw)
    if (
        path.is_absolute()
        or ".." in path.parts
        or "." in path.parts
        or not path.name
        or path.as_posix() != raw
    ):
        raise PackageError(f"unsafe archive entry: {raw}")
    return path


def verify_package(archive_path: Path) -> dict[str, Any]:
    """Verify paths, sizes, duplicates, metadata, and file digests."""
    if not archive_path.is_file():
        raise PackageError(f"package not found: {archive_path}")
    try:
        with zipfile.ZipFile(archive_path, "r") as archive:
            names: set[str] = set()
            total = 0
            for info in archive.infolist():
                _safe_archive_name(info.filename)
                if info.is_dir():
                    raise PackageError(f"directory archive entry is not allowed: {info.filename}")
                unix_kind = (info.external_attr >> 16) & 0o170000
                if unix_kind == 0o120000:
                    raise PackageError(
                        f"symbolic-link archive entry is not allowed: {info.filename}"
                    )
                if info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
                    raise PackageError(f"unsupported compression method: {info.filename}")
                if info.filename in names:
                    raise PackageError(f"duplicate archive entry: {info.filename}")
                names.add(info.filename)
                if info.flag_bits & 0x1:
                    raise PackageError(f"encrypted archive entry: {info.filename}")
                if info.file_size > MAX_ENTRY_BYTES:
                    raise PackageError(f"archive entry exceeds size limit: {info.filename}")
                total += info.file_size
                if total > MAX_TOTAL_BYTES:
                    raise PackageError("archive exceeds total size limit")
            if "pet.json" not in names or "package.json" not in names:
                raise PackageError("package must contain pet.json and package.json")
            try:
                metadata = json.loads(archive.read("package.json"))
            except (KeyError, json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise PackageError(f"invalid package.json: {exc}") from exc
            if not isinstance(metadata, dict) or metadata.get("schema") != PACKAGE_SCHEMA:
                raise PackageError("unsupported package schema")
            expected = metadata.get("files")
            if not isinstance(expected, dict) or "package.json" in expected:
                raise PackageError("package.json has no valid checksum map")
            if set(expected) | {"package.json"} != names:
                raise PackageError("package contents do not match package.json")
            for name, expected_digest in expected.items():
                if not isinstance(name, str) or not isinstance(expected_digest, str):
                    raise PackageError("invalid checksum map")
                if _digest(archive.read(name)) != expected_digest:
                    raise PackageError(f"checksum mismatch: {name}")
    except PackageError:
        raise
    except (OSError, RuntimeError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise PackageError(f"invalid zip package: {exc}") from exc
    raw = archive_path.read_bytes()
    return {
        "ok": True,
        "path": str(archive_path.resolve()),
        "bytes": len(raw),
        "sha256": _digest(raw),
        "pet_id": metadata.get("pet_id"),
        "entries": sorted(names),
    }
