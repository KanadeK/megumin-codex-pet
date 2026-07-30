# Acceptance matrix

Passing unit tests alone is not a release. Every row below must have evidence.

| Gate | Command or evidence | Pass condition |
| --- | --- | --- |
| Source quality | `ruff check .` | exit 0 |
| Types | `mypy src` | exit 0 |
| Tests | `pytest --cov=megumin_pet --cov-report=term-missing` | exit 0 and coverage threshold met |
| Wheel/sdist | `python -m build` | both artifacts created |
| Manifest/atlas | `petdiff validate pet` | `validation.ok` is `true`; no strict warnings |
| Locked regression | `petdiff check-lock pet pet/pet.lock.json --policy examples/release-policy.json` | report `ok` is `true` |
| Codex hatch contract | bundled `validate_atlas.py --require-v2` | exact 1536×2288, 73 used, 15 transparent reserved |
| Visual quality | hatch run QA artifacts and three isolated blind reviews | identity, animation, and direction reviews all pass |
| Package safety | `petdiff verify-package dist/megumin.codex-pet` | checksums, paths, sizes, contents pass |
| Reproducibility | two builds separated by at least two seconds | byte-identical SHA-256 |
| Install smoke | install → doctor → recoverable uninstall in a temporary CODEX_HOME | all exit 0; trash copy exists |
| Git identity | author/committer log and `git shortlog -sne HEAD` | only intended identity; no co-author trailer |
| Remote | public repository/default branch | exact release commit is visible |
| CI | GitHub Actions checks on release commit | all required checks green |
| Release | tag and GitHub Release | tag targets release commit; assets and checksums downloadable |
| Remote hash audit | download release assets into a new temporary directory | downloaded SHA-256 matches published checksum |
| Contributors | GitHub contributors page/API | only intended contributor at first release |

## One-command local gate

```bash
python scripts/release_check.py --strict --json
```

The command runs source gates, builds artifacts, validates the pet, checks the
lock, creates two time-separated packages, compares their bytes, verifies the
archive, and exercises install/doctor/uninstall against a temporary Codex home.
It writes no user Codex configuration.

## Exit-code contract

- `0`: requested operation passed.
- `1`: validation or comparison completed and found a contract/regression
  failure.
- `2`: invalid invocation, malformed input, unsafe archive, I/O failure, or
  refused lifecycle operation.
