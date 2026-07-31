"""Command-line interface for PetDiff and pet lifecycle tooling."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .atlas import PetInspectionError, inspect_pet
from .diffing import compare_snapshots, load_policy, load_snapshot, render_html
from .installer import InstallError, doctor, install, uninstall
from .packaging import PackageError, build_package, verify_package
from .previews import (
    PreviewError,
    audit_previews,
    parse_rgb,
    render_previews,
    write_preview_report,
)


def _write_json(document: dict[str, Any], path: Path | None = None) -> str:
    payload = json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload, encoding="utf-8", newline="\n")
    return payload


def _path(value: str) -> Path:
    return Path(value)


def build_parser() -> argparse.ArgumentParser:
    """Create the complete CLI parser."""
    parser = argparse.ArgumentParser(
        prog="petdiff",
        description="Validate, compare, package, and recoverably install Codex v2 pets.",
    )
    parser.add_argument("--version", action="version", version="petdiff 0.1.1")
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate", help="validate an unpacked v2 pet")
    validate.add_argument("pet", type=_path)
    validate.add_argument("--json-out", type=_path)

    snapshot = commands.add_parser("snapshot", help="write a deterministic atlas lock")
    snapshot.add_argument("pet", type=_path)
    snapshot.add_argument("--out", required=True, type=_path)
    snapshot.add_argument("--allow-invalid", action="store_true")

    compare = commands.add_parser("compare", help="compare two pets or snapshots")
    compare.add_argument("baseline", type=_path)
    compare.add_argument("current", type=_path)
    compare.add_argument("--policy", type=_path)
    compare.add_argument("--json-out", type=_path)
    compare.add_argument("--html-out", type=_path)

    check = commands.add_parser("check-lock", help="compare a pet against a committed lock")
    check.add_argument("pet", type=_path)
    check.add_argument("lock", type=_path)
    check.add_argument("--policy", type=_path)
    check.add_argument("--json-out", type=_path)
    check.add_argument("--html-out", type=_path)

    package = commands.add_parser("package", help="build a deterministic .codex-pet archive")
    package.add_argument("pet", type=_path)
    package.add_argument("--out", required=True, type=_path)

    verify = commands.add_parser("verify-package", help="verify package paths and checksums")
    verify.add_argument("archive", type=_path)

    render = commands.add_parser(
        "render-previews",
        help="render transparent GIF previews from the final pet atlas",
    )
    render.add_argument("pet", type=_path)
    render.add_argument("--out-dir", required=True, type=_path)
    render.add_argument("--qa-sheet", type=_path)
    render.add_argument("--alpha-threshold", type=int, default=128)
    render.add_argument("--chroma-key", type=parse_rgb, default=(0, 255, 0))
    render.add_argument("--chroma-distance", type=int, default=96)
    render.add_argument("--json-out", type=_path)

    audit = commands.add_parser(
        "audit-previews",
        help="audit all standard GIF previews for contract and chroma-fringe failures",
    )
    audit.add_argument("previews", type=_path)
    audit.add_argument("--chroma-key", type=parse_rgb, default=(0, 255, 0))
    audit.add_argument("--chroma-distance", type=int, default=96)
    audit.add_argument("--json-out", type=_path)

    install_parser = commands.add_parser("install", help="transactionally install a pet")
    install_parser.add_argument("source", type=_path)
    install_parser.add_argument("--codex-home", type=_path)

    doctor_parser = commands.add_parser("doctor", help="inspect an installed pet")
    doctor_parser.add_argument("pet_id")
    doctor_parser.add_argument("--codex-home", type=_path)
    doctor_parser.add_argument("--lock", type=_path)

    uninstall_parser = commands.add_parser(
        "uninstall", help="move an installed pet to recoverable trash"
    )
    uninstall_parser.add_argument("pet_id")
    uninstall_parser.add_argument("--codex-home", type=_path)
    return parser


def _run_compare(args: argparse.Namespace, baseline: Path, current: Path) -> dict[str, Any]:
    policy = load_policy(args.policy)
    report = compare_snapshots(load_snapshot(baseline), load_snapshot(current), policy)
    if args.json_out is not None:
        _write_json(report, args.json_out)
    if args.html_out is not None:
        args.html_out.parent.mkdir(parents=True, exist_ok=True)
        args.html_out.write_text(render_html(report), encoding="utf-8", newline="\n")
    return report


def run(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    """Execute one parsed command and return its document and exit code."""
    if args.command == "validate":
        document = inspect_pet(args.pet)
        if args.json_out is not None:
            _write_json(document, args.json_out)
        return document, 0 if document["validation"]["ok"] else 1
    if args.command == "snapshot":
        document = inspect_pet(args.pet)
        if not args.allow_invalid and not document["validation"]["ok"]:
            raise PetInspectionError("pet failed validation; snapshot refused")
        _write_json(document, args.out)
        return {
            "ok": bool(document["validation"]["ok"]),
            "snapshot": str(args.out.resolve()),
            "atlas_sha256": (document.get("atlas") or {}).get("sha256"),
        }, 0 if document["validation"]["ok"] else 1
    if args.command == "compare":
        report = _run_compare(args, args.baseline, args.current)
        return report, 0 if report["ok"] else 1
    if args.command == "check-lock":
        report = _run_compare(args, args.lock, args.pet)
        return report, 0 if report["ok"] else 1
    if args.command == "package":
        return build_package(args.pet, args.out), 0
    if args.command == "verify-package":
        return verify_package(args.archive), 0
    if args.command == "render-previews":
        result = render_previews(
            args.pet,
            args.out_dir,
            qa_sheet=args.qa_sheet,
            alpha_threshold=args.alpha_threshold,
            chroma_key=args.chroma_key,
            chroma_distance=args.chroma_distance,
        )
        if args.json_out is not None:
            write_preview_report(result, args.json_out)
        return result, 0 if result["ok"] else 1
    if args.command == "audit-previews":
        result = audit_previews(
            args.previews,
            chroma_key=args.chroma_key,
            chroma_distance=args.chroma_distance,
        )
        if args.json_out is not None:
            write_preview_report(result, args.json_out)
        return result, 0 if result["ok"] else 1
    if args.command == "install":
        return install(args.source, args.codex_home), 0
    if args.command == "doctor":
        result = doctor(args.pet_id, args.codex_home, args.lock)
        return result, 0 if result["ok"] else 1
    if args.command == "uninstall":
        return uninstall(args.pet_id, args.codex_home), 0
    raise AssertionError(f"unhandled command: {args.command}")


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        document, exit_code = run(args)
    except (
        InstallError,
        PackageError,
        PetInspectionError,
        PreviewError,
        OSError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        document = {"ok": False, "error": type(exc).__name__, "message": str(exc)}
        exit_code = 2
    sys.stdout.write(_write_json(document))
    return exit_code
