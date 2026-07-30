from __future__ import annotations

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
YAML_FILES = (
    ROOT / "action.yml",
    ROOT / ".github" / "ISSUE_TEMPLATE" / "bug.yml",
    ROOT / ".github" / "ISSUE_TEMPLATE" / "config.yml",
    ROOT / ".github" / "workflows" / "ci.yml",
    ROOT / ".github" / "workflows" / "pet-review.yml",
    ROOT / ".github" / "workflows" / "release.yml",
)


@pytest.mark.parametrize("path", YAML_FILES, ids=lambda path: path.name)
def test_github_yaml_is_parseable(path: Path) -> None:
    parsed = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert isinstance(parsed, dict)
    assert parsed


def test_composite_action_has_required_contract() -> None:
    action = yaml.load(
        (ROOT / "action.yml").read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )
    assert action["runs"]["using"] == "composite"
    assert action["inputs"]["baseline"]["required"] == "true"
    assert action["inputs"]["current"]["required"] == "true"
    assert action["outputs"]["json-report"]["value"] == (
        "${{ steps.review.outputs['json-report'] }}"
    )
    step_ids = {step.get("id") for step in action["runs"]["steps"]}
    assert "review" in step_ids


def test_release_workflow_runs_strict_gate_before_publishing() -> None:
    workflow = yaml.load(
        (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )
    steps = workflow["jobs"]["release"]["steps"]
    commands = "\n".join(str(step.get("run", "")) for step in steps)
    assert "scripts/release_check.py --strict --json" in commands
    release_steps = [step for step in steps if step.get("uses") == "softprops/action-gh-release@v2"]
    assert len(release_steps) == 1
