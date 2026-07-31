from __future__ import annotations

import json
from pathlib import Path

from megumin_pet.cli import main
from tests.helpers import make_pet


def _read_stdout(capsys: object) -> dict[str, object]:
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    return json.loads(captured.out)


def test_validate_snapshot_compare_and_check_lock(tmp_path: Path, capsys: object) -> None:
    pet = make_pet(tmp_path / "pet")
    assert main(["validate", str(pet)]) == 0
    assert _read_stdout(capsys)["validation"]["ok"] is True

    lock = tmp_path / "pet.lock.json"
    assert main(["snapshot", str(pet), "--out", str(lock)]) == 0
    assert _read_stdout(capsys)["ok"] is True

    report_json = tmp_path / "report.json"
    report_html = tmp_path / "report.html"
    assert (
        main(
            [
                "check-lock",
                str(pet),
                str(lock),
                "--json-out",
                str(report_json),
                "--html-out",
                str(report_html),
            ]
        )
        == 0
    )
    assert _read_stdout(capsys)["ok"] is True
    assert report_json.is_file()
    assert report_html.is_file()

    assert main(["compare", str(lock), str(pet)]) == 0
    assert _read_stdout(capsys)["ok"] is True


def test_package_verify_install_doctor_and_uninstall_cli(tmp_path: Path, capsys: object) -> None:
    pet = make_pet(tmp_path / "pet")
    archive = tmp_path / "pet.codex-pet"
    codex_home = tmp_path / "codex"
    assert main(["package", str(pet), "--out", str(archive)]) == 0
    assert _read_stdout(capsys)["ok"] is True
    assert main(["verify-package", str(archive)]) == 0
    assert _read_stdout(capsys)["ok"] is True
    assert main(["install", str(archive), "--codex-home", str(codex_home)]) == 0
    assert _read_stdout(capsys)["pet_id"] == "fixture-pet"
    assert main(["doctor", "fixture-pet", "--codex-home", str(codex_home)]) == 0
    assert _read_stdout(capsys)["ok"] is True
    assert main(["uninstall", "fixture-pet", "--codex-home", str(codex_home)]) == 0
    assert _read_stdout(capsys)["ok"] is True


def test_render_and_audit_previews_cli(tmp_path: Path, capsys: object) -> None:
    pet = make_pet(tmp_path / "pet")
    previews = tmp_path / "previews"
    sheet = tmp_path / "background-check.png"
    report = tmp_path / "preview-audit.json"
    assert (
        main(
            [
                "render-previews",
                str(pet),
                "--out-dir",
                str(previews),
                "--qa-sheet",
                str(sheet),
                "--json-out",
                str(report),
            ]
        )
        == 0
    )
    assert _read_stdout(capsys)["ok"] is True
    assert report.is_file()
    assert sheet.is_file()

    assert main(["audit-previews", str(previews), "--chroma-key", "#00ff00"]) == 0
    assert _read_stdout(capsys)["ok"] is True


def test_cli_returns_structured_failure(tmp_path: Path, capsys: object) -> None:
    assert main(["verify-package", str(tmp_path / "missing")]) == 2
    result = _read_stdout(capsys)
    assert result["ok"] is False
    assert result["error"] == "PackageError"

    invalid = make_pet(tmp_path / "invalid", changes={(0, 0): "blank"})
    assert main(["snapshot", str(invalid), "--out", str(tmp_path / "lock.json")]) == 2
    assert _read_stdout(capsys)["error"] == "PetInspectionError"

    corrupt = tmp_path / "corrupt.codex-pet"
    corrupt.write_bytes(b"not a zip")
    assert main(["verify-package", str(corrupt)]) == 2
    assert _read_stdout(capsys)["error"] == "PackageError"
