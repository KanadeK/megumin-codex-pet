from __future__ import annotations

import json
from pathlib import Path

import pytest

from megumin_pet.atlas import inspect_pet
from megumin_pet.diffing import (
    DEFAULT_POLICY,
    compare_snapshots,
    load_policy,
    load_snapshot,
    render_html,
)
from tests.helpers import make_pet


def test_identical_snapshots_pass_all_default_budgets(tmp_path: Path) -> None:
    snapshot = inspect_pet(make_pet(tmp_path / "pet"))
    report = compare_snapshots(snapshot, snapshot)
    assert report["ok"]
    assert report["summary"] == {
        "cells_checked": 73,
        "errors": 0,
        "warnings": 0,
        "manifest_changes": 0,
    }


def test_shifted_cell_fails_with_local_evidence(tmp_path: Path) -> None:
    baseline = inspect_pet(make_pet(tmp_path / "base"))
    current = inspect_pet(make_pet(tmp_path / "current", changes={(0, 0): "shift"}))
    report = compare_snapshots(baseline, current)
    assert not report["ok"]
    cell_finding = next(item for item in report["findings"] if item.get("cell") == "r00c00")
    assert cell_finding["code"] == "cell-budget-exceeded"
    assert cell_finding["detail"]["centroid_shift_px"]["actual"] > 14
    assert report["cells"]["r00c00"]["label"] == "idle:0"


def test_permissive_policy_can_approve_an_intentional_change(tmp_path: Path) -> None:
    baseline = inspect_pet(make_pet(tmp_path / "base"))
    current = inspect_pet(make_pet(tmp_path / "current", changes={(0, 0): "recolor"}))
    policy = {key: 10_000 for key in DEFAULT_POLICY if key.startswith("max_")}
    policy["fail_on_contract_warning"] = False
    assert compare_snapshots(baseline, current, policy)["ok"]


def test_manifest_identity_change_fails_but_copy_change_is_recorded(tmp_path: Path) -> None:
    baseline = inspect_pet(make_pet(tmp_path / "base", pet_id="fixture-pet"))
    current_pet = make_pet(tmp_path / "current", pet_id="other-pet")
    manifest_path = current_pet / "pet.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["description"] = "New copy."
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    current = inspect_pet(current_pet)
    report = compare_snapshots(baseline, current)
    assert any(item["code"] == "manifest-identity-change" for item in report["findings"])
    assert report["changes"][0]["field"] == "description"


def test_current_contract_errors_are_propagated_and_warnings_can_be_fatal(
    tmp_path: Path,
) -> None:
    baseline = inspect_pet(make_pet(tmp_path / "base"))
    current = inspect_pet(make_pet(tmp_path / "current", changes={(0, 7): "recolor"}))
    report = compare_snapshots(baseline, current)
    assert any(item["code"] == "current-unused-cell-visible" for item in report["findings"])

    current["validation"]["findings"].append(
        {"severity": "warning", "code": "manual-warning", "message": "Review me"}
    )
    policy = dict(DEFAULT_POLICY)
    policy["fail_on_contract_warning"] = True
    strict = compare_snapshots(baseline, current, policy)
    warning = next(item for item in strict["findings"] if item["code"] == "current-manual-warning")
    assert warning["severity"] == "error"


def test_policy_validation_and_snapshot_loading(tmp_path: Path) -> None:
    assert load_policy(None) == DEFAULT_POLICY
    good = tmp_path / "good.json"
    good.write_text('{"max_centroid_shift_px": 2}', encoding="utf-8")
    assert load_policy(good)["max_centroid_shift_px"] == 2

    for payload, message in [
        ("[]", "object"),
        ('{"unknown": 2}', "unknown"),
        ('{"max_centroid_shift_px": -1}', "non-negative"),
        ('{"fail_on_contract_warning": 1}', "boolean"),
    ]:
        path = tmp_path / f"bad-{len(payload)}-{payload[0]}.json"
        path.write_text(payload, encoding="utf-8")
        with pytest.raises(ValueError, match=message):
            load_policy(path)

    pet = make_pet(tmp_path / "pet")
    assert load_snapshot(pet)["validation"]["ok"]
    lock = tmp_path / "pet.lock.json"
    lock.write_text(json.dumps(inspect_pet(pet)), encoding="utf-8")
    assert load_snapshot(lock)["manifest"]["id"] == "fixture-pet"
    lock.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="schema-1"):
        load_snapshot(lock)


def test_html_report_is_self_contained_and_escaped(tmp_path: Path) -> None:
    snapshot = inspect_pet(make_pet(tmp_path / "pet"))
    report = compare_snapshots(snapshot, snapshot)
    report["findings"].append(
        {"severity": "warning", "code": "<unsafe>", "message": "<script>alert(1)</script>"}
    )
    rendered = render_html(report)
    assert "<!doctype html>" in rendered
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in rendered
    assert "<script>alert(1)</script>" not in rendered
    assert "r10c07" in rendered


def test_missing_cell_metrics_are_reported(tmp_path: Path) -> None:
    snapshot = inspect_pet(make_pet(tmp_path / "pet"))
    missing = json.loads(json.dumps(snapshot))
    del missing["cells"]["r00c00"]
    report = compare_snapshots(snapshot, missing)
    assert any(item["code"] == "cell-missing" for item in report["findings"])
