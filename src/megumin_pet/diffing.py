"""Policy-driven atlas regression comparison and HTML evidence."""

from __future__ import annotations

import html
import json
import math
from pathlib import Path
from typing import Any

from .atlas import inspect_pet, mean_byte_delta
from .contract import (
    ACTIVE_CELL_KEYS,
    REPORT_SCHEMA,
    STATE_LAYOUT,
    TOOL_VERSION,
    finding,
)

DEFAULT_POLICY: dict[str, Any] = {
    "max_alpha_area_delta_ratio": 0.20,
    "max_centroid_shift_px": 14.0,
    "max_silhouette_mean_delta": 0.12,
    "max_rgba_mean_delta": 0.18,
    "max_motion_metric_delta_ratio": 0.40,
    "fail_on_contract_warning": False,
}
NUMERIC_POLICY_KEYS = frozenset(
    {
        "max_alpha_area_delta_ratio",
        "max_centroid_shift_px",
        "max_silhouette_mean_delta",
        "max_rgba_mean_delta",
        "max_motion_metric_delta_ratio",
    }
)


def load_policy(path: Path | None) -> dict[str, Any]:
    """Load a policy and reject unknown or unsafe values."""
    policy = dict(DEFAULT_POLICY)
    if path is None:
        return policy
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("policy must contain one JSON object")
    unknown = set(loaded) - set(DEFAULT_POLICY)
    if unknown:
        raise ValueError(f"unknown policy keys: {', '.join(sorted(unknown))}")
    policy.update(loaded)
    for key in NUMERIC_POLICY_KEYS:
        value = policy[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
            raise ValueError(f"{key} must be a non-negative number")
    if not isinstance(policy["fail_on_contract_warning"], bool):
        raise ValueError("fail_on_contract_warning must be a boolean")
    return policy


def load_snapshot(source: Path) -> dict[str, Any]:
    """Load a lock file or inspect an unpacked pet directory."""
    if source.is_dir():
        return inspect_pet(source)
    loaded = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict) or loaded.get("schema") != 1:
        raise ValueError("snapshot must be a PetDiff schema-1 JSON object")
    if not isinstance(loaded.get("cells"), dict):
        raise ValueError("snapshot does not contain cell metrics")
    return loaded


def _ratio_delta(left: float, right: float) -> float:
    return round(abs(right - left) / max(abs(left), 1.0), 6)


def _centroid_delta(left: object, right: object) -> float:
    if (
        not isinstance(left, list)
        or not isinstance(right, list)
        or len(left) != 2
        or len(right) != 2
    ):
        return math.inf
    x_delta = float(right[0]) - float(left[0])
    y_delta = float(right[1]) - float(left[1])
    return round(math.hypot(x_delta, y_delta), 4)


def _copy_contract_findings(
    snapshot: dict[str, Any], *, fail_on_warning: bool
) -> list[dict[str, Any]]:
    copied: list[dict[str, Any]] = []
    validation = snapshot.get("validation")
    if not isinstance(validation, dict):
        return [
            finding(
                "error",
                "current-validation-missing",
                "current snapshot has no validation",
            )
        ]
    entries = validation.get("findings", [])
    if not isinstance(entries, list):
        return [
            finding(
                "error",
                "current-findings-invalid",
                "current validation findings are invalid",
            )
        ]
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        severity = str(entry.get("severity", "error"))
        if severity == "warning" and fail_on_warning:
            severity = "error"
        copied_entry = dict(entry)
        copied_entry["severity"] = severity
        copied_entry["code"] = f"current-{entry.get('code', 'contract')}"
        copied.append(copied_entry)
    return copied


def compare_snapshots(
    baseline: dict[str, Any],
    current: dict[str, Any],
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compare two deterministic snapshots under explicit budgets."""
    effective = dict(DEFAULT_POLICY if policy is None else policy)
    findings = _copy_contract_findings(
        current, fail_on_warning=bool(effective["fail_on_contract_warning"])
    )
    changes: list[dict[str, Any]] = []
    cell_results: dict[str, dict[str, Any]] = {}

    baseline_manifest = baseline.get("manifest", {})
    current_manifest = current.get("manifest", {})
    for field in ("id", "spriteVersionNumber", "spritesheetPath"):
        left = baseline_manifest.get(field) if isinstance(baseline_manifest, dict) else None
        right = current_manifest.get(field) if isinstance(current_manifest, dict) else None
        if left != right:
            findings.append(
                finding(
                    "error",
                    "manifest-identity-change",
                    f"manifest field {field} changed",
                    detail={"field": field, "baseline": left, "current": right},
                )
            )
    for field in ("displayName", "description"):
        left = baseline_manifest.get(field) if isinstance(baseline_manifest, dict) else None
        right = current_manifest.get(field) if isinstance(current_manifest, dict) else None
        if left != right:
            changes.append({"kind": "manifest", "field": field, "baseline": left, "current": right})

    baseline_cells = baseline.get("cells", {})
    current_cells = current.get("cells", {})
    if not isinstance(baseline_cells, dict) or not isinstance(current_cells, dict):
        findings.append(
            finding(
                "error",
                "cell-metrics-missing",
                "one snapshot has no cell metrics",
            )
        )
    else:
        for key in sorted(ACTIVE_CELL_KEYS):
            left = baseline_cells.get(key)
            right = current_cells.get(key)
            if not isinstance(left, dict) or not isinstance(right, dict):
                findings.append(
                    finding(
                        "error",
                        "cell-missing",
                        "a required cell is absent from one snapshot",
                        cell=key,
                    )
                )
                continue
            alpha_delta = _ratio_delta(float(left["alpha_area"]), float(right["alpha_area"]))
            centroid_delta = _centroid_delta(left.get("centroid"), right.get("centroid"))
            silhouette_delta = mean_byte_delta(
                str(left["silhouette_16"]), str(right["silhouette_16"])
            )
            rgba_delta = mean_byte_delta(str(left["rgba_16"]), str(right["rgba_16"]))
            metrics = {
                "label": right.get("label", key),
                "alpha_area_delta_ratio": alpha_delta,
                "centroid_shift_px": centroid_delta,
                "silhouette_mean_delta": silhouette_delta,
                "rgba_mean_delta": rgba_delta,
            }
            cell_results[key] = metrics
            budgets = (
                ("alpha_area_delta_ratio", "max_alpha_area_delta_ratio"),
                ("centroid_shift_px", "max_centroid_shift_px"),
                ("silhouette_mean_delta", "max_silhouette_mean_delta"),
                ("rgba_mean_delta", "max_rgba_mean_delta"),
            )
            exceeded: dict[str, Any] = {}
            for metric_key, policy_key in budgets:
                if float(metrics[metric_key]) > float(effective[policy_key]):
                    exceeded[metric_key] = {
                        "actual": metrics[metric_key],
                        "maximum": effective[policy_key],
                    }
            if exceeded:
                findings.append(
                    finding(
                        "error",
                        "cell-budget-exceeded",
                        f"{metrics['label']} exceeded one or more PetDiff budgets",
                        cell=key,
                        detail=exceeded,
                    )
                )

    baseline_motion = baseline.get("motion", {})
    current_motion = current.get("motion", {})
    motion_results: dict[str, Any] = {}
    state_names = [str(state["name"]) for state in STATE_LAYOUT] + ["look-clockwise"]
    for name in state_names:
        left = baseline_motion.get(name) if isinstance(baseline_motion, dict) else None
        right = current_motion.get(name) if isinstance(current_motion, dict) else None
        if not isinstance(left, dict) or not isinstance(right, dict):
            continue
        metric_deltas: dict[str, float] = {}
        for metric in (
            "centroid_step_mean",
            "centroid_step_max",
            "silhouette_step_mean",
            "silhouette_step_max",
            "alpha_area_step_mean",
            "alpha_area_step_max",
        ):
            metric_deltas[metric] = _ratio_delta(float(left[metric]), float(right[metric]))
        motion_results[name] = metric_deltas
        largest = max(metric_deltas.values(), default=0.0)
        if largest > float(effective["max_motion_metric_delta_ratio"]):
            findings.append(
                finding(
                    "error",
                    "motion-budget-exceeded",
                    f"{name} motion cadence changed beyond the policy budget",
                    detail={
                        "state": name,
                        "largest_delta_ratio": largest,
                        "maximum": effective["max_motion_metric_delta_ratio"],
                        "metrics": metric_deltas,
                    },
                )
            )

    findings.sort(
        key=lambda item: (
            str(item["severity"]),
            str(item["code"]),
            str(item.get("cell", "")),
        )
    )
    errors = sum(item.get("severity") == "error" for item in findings)
    warnings = sum(item.get("severity") == "warning" for item in findings)
    return {
        "schema": REPORT_SCHEMA,
        "tool": {"name": "petdiff", "version": TOOL_VERSION},
        "ok": errors == 0,
        "policy": effective,
        "summary": {
            "cells_checked": len(cell_results),
            "errors": errors,
            "warnings": warnings,
            "manifest_changes": len(changes),
        },
        "baseline": {
            "id": baseline_manifest.get("id") if isinstance(baseline_manifest, dict) else None,
            "atlas_sha256": (baseline.get("atlas") or {}).get("sha256"),
        },
        "current": {
            "id": current_manifest.get("id") if isinstance(current_manifest, dict) else None,
            "atlas_sha256": (current.get("atlas") or {}).get("sha256"),
        },
        "changes": changes,
        "cells": cell_results,
        "motion": motion_results,
        "findings": findings,
    }


def render_html(report: dict[str, Any]) -> str:
    """Render a self-contained, deterministic review artifact."""
    rows: list[str] = []
    for key, metrics in sorted(report.get("cells", {}).items()):
        finding_for_cell = [
            item for item in report.get("findings", []) if item.get("cell") == key
        ]
        status = (
            "fail"
            if any(item.get("severity") == "error" for item in finding_for_cell)
            else "pass"
        )
        rows.append(
            "<tr class='{status}'><td><code>{key}</code></td><td>{label}</td>"
            "<td>{alpha:.4f}</td><td>{centroid:.2f}</td><td>{silhouette:.4f}</td>"
            "<td>{rgba:.4f}</td><td>{status}</td></tr>".format(
                status=status,
                key=html.escape(str(key)),
                label=html.escape(str(metrics.get("label", ""))),
                alpha=float(metrics.get("alpha_area_delta_ratio", 0)),
                centroid=float(metrics.get("centroid_shift_px", 0)),
                silhouette=float(metrics.get("silhouette_mean_delta", 0)),
                rgba=float(metrics.get("rgba_mean_delta", 0)),
            )
        )
    findings = "".join(
        f"<li><strong>{html.escape(str(item.get('code')))}</strong>: "
        f"{html.escape(str(item.get('message')))}</li>"
        for item in report.get("findings", [])
    ) or "<li>No findings.</li>"
    status_text = "PASS" if report.get("ok") else "FAIL"
    embedded = html.escape(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PetDiff {status_text}</title>
<style>
:root {{
  color-scheme: light dark;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
}}
body {{ max-width: 1180px; margin: 2rem auto; padding: 0 1rem; }}
.badge {{ display:inline-block; padding:.25rem .6rem; border-radius:999px; font-weight:700; }}
.badge.pass, tr.pass td:last-child {{ color:#117a37; }}
.badge.fail, tr.fail td:last-child {{ color:#c62828; }}
table {{ width:100%; border-collapse:collapse; font-size:.86rem; }}
th,td {{ border-bottom:1px solid #8885; padding:.45rem; text-align:right; }}
th:nth-child(-n+2),td:nth-child(-n+2) {{ text-align:left; }}
tr.fail {{ background:#c6282812; }} code {{ white-space:nowrap; }}
details {{ margin-top:1rem; }} pre {{ overflow:auto; white-space:pre-wrap; }}
</style>
</head>
<body>
<h1>PetDiff <span class="badge {str(status_text).lower()}">{status_text}</span></h1>
<p>{report.get("summary", {}).get("cells_checked", 0)} active cells checked;
{report.get("summary", {}).get("errors", 0)} errors and
{report.get("summary", {}).get("warnings", 0)} warnings.</p>
<h2>Findings</h2><ul>{findings}</ul>
<h2>Per-cell regression metrics</h2>
<table><thead><tr><th>Cell</th><th>Pose</th><th>Area Δ</th><th>Centroid px</th>
<th>Silhouette Δ</th><th>RGBA Δ</th><th>Status</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>
<details><summary>Embedded machine report</summary><pre>{embedded}</pre></details>
</body></html>
"""
