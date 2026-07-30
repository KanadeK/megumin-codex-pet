"""Transactional Codex pet installation with recoverable replacement/removal."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import uuid
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import Any

from .atlas import inspect_pet
from .contract import PET_ID_PATTERN, resolve_inside, safe_sprite_path
from .packaging import PackageError, verify_package


class InstallError(RuntimeError):
    """Raised when install safety or validation fails."""


def codex_root(explicit: Path | None = None) -> Path:
    """Resolve CODEX_HOME without broad destructive assumptions."""
    if explicit is not None:
        return explicit.resolve()
    configured = os.environ.get("CODEX_HOME")
    if configured:
        return Path(configured).resolve()
    return (Path.home() / ".codex").resolve()


def _assert_pet_id(pet_id: str) -> None:
    if PET_ID_PATTERN.fullmatch(pet_id) is None:
        raise InstallError("pet id must be lowercase kebab-case")


@contextmanager
def _install_lock(pets_root: Path) -> Iterator[None]:
    lock_path = pets_root / ".petdiff-install.lock"
    try:
        descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise InstallError(f"another pet install holds {lock_path}") from exc
    try:
        os.write(descriptor, str(os.getpid()).encode())
        os.close(descriptor)
        yield
    finally:
        with suppress(FileNotFoundError):
            lock_path.unlink()


def _copy_validated_pet(source: Path, destination: Path) -> dict[str, Any]:
    snapshot = inspect_pet(source)
    if not bool(snapshot["validation"]["ok"]):
        raise InstallError("source pet failed strict validation")
    manifest = snapshot["manifest"]
    sprite_path, error = safe_sprite_path(manifest.get("spritesheetPath"))
    if error or sprite_path is None:
        raise InstallError(error or "invalid spritesheet path")
    destination.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(source / "pet.json", destination / "pet.json")
    sprite_destination = destination.joinpath(*sprite_path.parts)
    sprite_destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(resolve_inside(source, sprite_path), sprite_destination)
    copied = inspect_pet(destination)
    if not bool(copied["validation"]["ok"]):
        raise InstallError("staged copy failed validation")
    return copied


@contextmanager
def _unpacked_source(source: Path) -> Iterator[Path]:
    if source.is_dir():
        yield source.resolve()
        return
    try:
        verify_package(source)
    except PackageError as exc:
        raise InstallError(str(exc)) from exc
    with tempfile.TemporaryDirectory(prefix="petdiff-unpack-") as temp:
        root = Path(temp)
        with zipfile.ZipFile(source, "r") as archive:
            for info in archive.infolist():
                if info.filename == "package.json":
                    continue
                target = root.joinpath(*info.filename.split("/"))
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(info))
        yield root


def install(source: Path, explicit_codex_home: Path | None = None) -> dict[str, Any]:
    """Validate, stage, atomically replace, and retain a recovery backup."""
    root = codex_root(explicit_codex_home)
    pets_root = root / "pets"
    pets_root.mkdir(parents=True, exist_ok=True)
    with _unpacked_source(source) as unpacked:
        snapshot = inspect_pet(unpacked)
        if not bool(snapshot["validation"]["ok"]):
            raise InstallError("source pet failed strict validation")
        pet_id = str(snapshot["manifest"]["id"])
        _assert_pet_id(pet_id)
        target = pets_root / pet_id
        token = uuid.uuid4().hex
        staging = pets_root / f".{pet_id}.staging-{token}"
        backup: Path | None = None
        with _install_lock(pets_root):
            try:
                staged_snapshot = _copy_validated_pet(unpacked, staging)
                if target.exists():
                    backup = pets_root / ".backups" / pet_id / token
                    backup.parent.mkdir(parents=True, exist_ok=True)
                    target.replace(backup)
                staging.replace(target)
            except Exception:
                if staging.exists():
                    shutil.rmtree(staging)
                if backup is not None and backup.exists() and not target.exists():
                    backup.replace(target)
                raise
    return {
        "ok": True,
        "pet_id": pet_id,
        "installed": str(target),
        "backup": str(backup) if backup else None,
        "atlas_sha256": staged_snapshot["atlas"]["sha256"],
    }


def doctor(
    pet_id: str,
    explicit_codex_home: Path | None = None,
    expected_snapshot: Path | None = None,
) -> dict[str, Any]:
    """Inspect an installed pet and optionally check it against a lock."""
    _assert_pet_id(pet_id)
    target = codex_root(explicit_codex_home) / "pets" / pet_id
    snapshot = inspect_pet(target)
    findings = list(snapshot["validation"]["findings"])
    if expected_snapshot is not None:
        expected = json.loads(expected_snapshot.read_text(encoding="utf-8"))
        expected_hash = (expected.get("atlas") or {}).get("sha256")
        actual_hash = (snapshot.get("atlas") or {}).get("sha256")
        if expected_hash != actual_hash:
            findings.append(
                {
                    "severity": "error",
                    "code": "installed-lock-drift",
                    "message": "installed atlas does not match the supplied lock",
                    "detail": {"expected": expected_hash, "actual": actual_hash},
                }
            )
    errors = sum(item.get("severity") == "error" for item in findings)
    return {
        "ok": errors == 0,
        "pet_id": pet_id,
        "installed": str(target),
        "atlas_sha256": (snapshot.get("atlas") or {}).get("sha256"),
        "findings": findings,
    }


def uninstall(pet_id: str, explicit_codex_home: Path | None = None) -> dict[str, Any]:
    """Move an installed pet into a recoverable trash directory."""
    _assert_pet_id(pet_id)
    root = codex_root(explicit_codex_home)
    pets_root = root / "pets"
    target = pets_root / pet_id
    if not target.is_dir():
        raise InstallError(f"installed pet not found: {target}")
    token = uuid.uuid4().hex
    trash = pets_root / ".trash" / pet_id / token
    trash.parent.mkdir(parents=True, exist_ok=True)
    with _install_lock(pets_root):
        target.replace(trash)
    return {"ok": True, "pet_id": pet_id, "removed": str(target), "recoverable_at": str(trash)}
