"""Run the complete local release gate and emit machine-readable evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _child_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment["PYTHONIOENCODING"] = "utf-8"
    return environment


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run(name: str, command: Sequence[str]) -> dict[str, Any]:
    completed = subprocess.run(
        list(command),
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env=_child_environment(),
    )
    return {
        "name": name,
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "command": list(command),
        "stdout": completed.stdout[-6000:],
        "stderr": completed.stderr[-6000:],
    }


def _json_output(command: Sequence[str]) -> dict[str, Any]:
    completed = subprocess.run(
        list(command),
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env=_child_environment(),
    )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        payload = {"raw_stdout": completed.stdout}
    return {
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "payload": payload,
        "stderr": completed.stderr[-6000:],
    }


def gate(strict: bool) -> dict[str, Any]:
    """Execute source, pet, reproducibility, and lifecycle gates."""
    python = sys.executable
    checks = [
        _run("ruff", [python, "-m", "ruff", "check", "."]),
        _run("mypy", [python, "-m", "mypy", "src"]),
        _run(
            "pytest",
            [
                python,
                "-m",
                "pytest",
                "--cov=megumin_pet",
                "--cov-report=term-missing",
            ],
        ),
        _run("build", [python, "-m", "build", "--no-isolation"]),
    ]
    pet_validation = _json_output(
        [python, "-m", "megumin_pet", "validate", "pet", "--json-out", "build/validation.json"]
    )
    if strict and pet_validation["ok"]:
        validation = pet_validation["payload"].get("validation", {})
        if validation.get("warning_count", 0):
            pet_validation["ok"] = False
            pet_validation["strict_error"] = "strict mode rejects contract warnings"

    lock_check = _json_output(
        [
            python,
            "-m",
            "megumin_pet",
            "check-lock",
            "pet",
            "pet/pet.lock.json",
            "--policy",
            "examples/release-policy.json",
            "--json-out",
            "build/petdiff-release.json",
            "--html-out",
            "build/petdiff-release.html",
        ]
    )
    preview_audit = _json_output(
        [
            python,
            "-m",
            "megumin_pet",
            "audit-previews",
            "artwork/qa/previews",
            "--json-out",
            "build/preview-audit.json",
        ]
    )

    reproducibility: dict[str, Any] = {"ok": False}
    lifecycle: dict[str, Any] = {"ok": False}
    with tempfile.TemporaryDirectory(prefix="megumin-release-check-") as temporary:
        temporary_path = Path(temporary)
        first = temporary_path / "first.codex-pet"
        second = temporary_path / "second.codex-pet"
        first_result = _json_output(
            [python, "-m", "megumin_pet", "package", "pet", "--out", str(first)]
        )
        time.sleep(2.1)
        second_result = _json_output(
            [python, "-m", "megumin_pet", "package", "pet", "--out", str(second)]
        )
        if first_result["ok"] and second_result["ok"]:
            first_hash = _sha256(first)
            second_hash = _sha256(second)
            verify = _json_output(
                [python, "-m", "megumin_pet", "verify-package", str(first)]
            )
            reproducibility = {
                "ok": first.read_bytes() == second.read_bytes() and verify["ok"],
                "first_sha256": first_hash,
                "second_sha256": second_hash,
                "verify": verify,
                "separation_seconds": 2.1,
            }
            codex_home = temporary_path / "codex-home"
            installed = _json_output(
                [
                    python,
                    "-m",
                    "megumin_pet",
                    "install",
                    str(first),
                    "--codex-home",
                    str(codex_home),
                ]
            )
            diagnosed = _json_output(
                [
                    python,
                    "-m",
                    "megumin_pet",
                    "doctor",
                    "megumin",
                    "--codex-home",
                    str(codex_home),
                    "--lock",
                    "pet/pet.lock.json",
                ]
            )
            removed = _json_output(
                [
                    python,
                    "-m",
                    "megumin_pet",
                    "uninstall",
                    "megumin",
                    "--codex-home",
                    str(codex_home),
                ]
            )
            recoverable = False
            if removed["ok"]:
                recoverable_at = removed["payload"].get("recoverable_at")
                recoverable = isinstance(recoverable_at, str) and Path(recoverable_at).is_dir()
            lifecycle = {
                "ok": installed["ok"] and diagnosed["ok"] and removed["ok"] and recoverable,
                "install": installed,
                "doctor": diagnosed,
                "uninstall": removed,
                "recoverable_copy_exists": recoverable,
            }
        else:
            reproducibility = {
                "ok": False,
                "first": first_result,
                "second": second_result,
            }

    ok = (
        all(check["ok"] for check in checks)
        and pet_validation["ok"]
        and lock_check["ok"]
        and preview_audit["ok"]
        and reproducibility["ok"]
        and lifecycle["ok"]
    )
    return {
        "ok": ok,
        "strict": strict,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "checks": checks,
        "pet_validation": pet_validation,
        "lock_check": lock_check,
        "preview_audit": preview_audit,
        "reproducibility": reproducibility,
        "lifecycle": lifecycle,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args(argv)
    report = gate(args.strict)
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.json_out is not None:
        output_path = args.json_out if args.json_out.is_absolute() else ROOT / args.json_out
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered + "\n", encoding="utf-8")
    if args.as_json:
        print(rendered)
    else:
        print("PASS" if report["ok"] else "FAIL")
        for check in report["checks"]:
            print(f"{check['name']}: {'PASS' if check['ok'] else 'FAIL'}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
