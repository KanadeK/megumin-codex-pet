# Megumin Codex Pet + PetDiff

[![CI](https://github.com/KanadeK/megumin-codex-pet/actions/workflows/ci.yml/badge.svg)](https://github.com/KanadeK/megumin-codex-pet/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/KanadeK/megumin-codex-pet)](https://github.com/KanadeK/megumin-codex-pet/releases/latest)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB)](https://www.python.org/)
[![License: MIT code](https://img.shields.io/badge/code-MIT-green.svg)](LICENSE)

An unofficial, original-art Codex v2 desktop pet inspired by **Megumin**, plus
**PetDiff**: a real command-line regression reviewer for Codex pet atlases.

<p align="center">
  <img src="artwork/qa/previews/waving.gif" alt="Megumin waving animation" width="192">
  <img src="artwork/qa/previews/running-right.gif" alt="Megumin running animation" width="192">
</p>

PetDiff turns an 8×11 atlas into deterministic per-cell evidence, compares an
upgrade against explicit budgets, emits JSON and a self-contained HTML report,
builds byte-reproducible packages, and performs recoverable installs. It is not
a gallery or installer-only shell.

Version 0.1.1 corrects the public transparent GIFs, adds deterministic preview
rendering and chroma-fringe enforcement, and keeps the already-clean packaged
8×11 atlas byte-identical to v0.1.0.

[See all 11 animation rows and 16 look directions.](artwork/qa/contact-sheet.png)
[Download the latest `.codex-pet` package.](https://github.com/KanadeK/megumin-codex-pet/releases/latest)

## What is actually runnable

- Strict Codex v2 contract validation: `1536×2288`, 8×11 cells, 73 required
  poses, one optional neutral pose, 14 transparent reserved cells, safe
  manifest paths, and cell-edge clipping detection.
- `pet.lock.json` snapshots with SHA-256, alpha area, bounding box, weighted
  centroid, 16×16 silhouette/RGBA fingerprints, and loop-motion metrics.
- Policy-based regressions for every active cell and every animation loop.
- Deterministic JSON and self-contained HTML review artifacts.
- Deterministic transparent GIF previews rendered only from the final packaged
  atlas, with frame/duration checks and a zero-tolerance chroma-fringe audit.
- Byte-reproducible `.codex-pet` archives with internal checksums and zip-slip,
  duplicate-entry, encryption, and size defenses.
- Transactional install with retained backups, an installed-pet doctor, and
  recoverable uninstall to `.trash`.
- Windows and Linux CI, a reusable composite GitHub Action, unit/integration
  tests, and a release gate that rebuilds packages twice with a deliberate
  time gap.
- Committed visual evidence: contact sheet, GIFs, cardinal provenance,
  three-reviewer blind direction verdict, chroma audit, and strict v2 report.

## Quick start

Python 3.11 or newer is required.

```bash
python -m venv .venv
python -m pip install -e ".[dev]"
petdiff --version
```

Validate and lock an unpacked pet:

```bash
petdiff validate pet --json-out build/validation.json
petdiff snapshot pet --out pet/pet.lock.json
```

Render and audit the nine public animation previews:

```bash
petdiff render-previews pet \
  --out-dir artwork/qa/previews \
  --qa-sheet artwork/qa/preview-background-check.png \
  --json-out artwork/qa/preview-audit.json
petdiff audit-previews artwork/qa/previews
```

Review an atlas upgrade:

```bash
petdiff compare pet/pet.lock.json pet \
  --policy examples/review-policy.json \
  --json-out build/petdiff.json \
  --html-out build/petdiff.html
```

Package and install:

```bash
petdiff package pet --out dist/megumin.codex-pet
petdiff verify-package dist/megumin.codex-pet
petdiff install dist/megumin.codex-pet
petdiff doctor megumin --lock pet/pet.lock.json
```

`install` writes only beneath `${CODEX_HOME}/pets` (or `~/.codex/pets`).
Replacing an existing pet retains the previous version under `.backups`.
`uninstall` moves the pet under `.trash`; it does not permanently delete it.

## Acceptance

The release-equivalent local gate is:

```bash
python scripts/release_check.py --strict --json --json-out build/release-check.json
```

It must report `ok: true`. The individual CI commands are:

```bash
ruff check .
mypy src
pytest --cov=megumin_pet --cov-report=term-missing
python -m build --no-isolation
petdiff check-lock pet pet/pet.lock.json \
  --policy examples/release-policy.json \
  --json-out build/petdiff-release.json \
  --html-out build/petdiff-release.html
petdiff audit-previews artwork/qa/previews \
  --json-out build/preview-audit.json
```

The v0.1.1 release gate passes 58 tests at 91.07% coverage. The atlas SHA-256
is `529125d140845a1e45866284e272a2b5d620e1d1b17816816ed1f306221984ec`;
the reproducible `.codex-pet` SHA-256 is
`934aa77aa2ed1fba010f60e9451acb9d4fda3e84ddbbdda0e6114cb298871d7d`.

See [docs/ACCEPTANCE.md](docs/ACCEPTANCE.md) for expected evidence and
[docs/REPAIR.md](docs/REPAIR.md) for failure-specific recovery commands.

## Why Megumin, and why the rights boundary matters

The character was selected after a local/GitHub duplication audit and a
popularity check. KADOKAWA's 2019 official character election placed Megumin
second with 755,870 points, and she later became the focus of an official
spin-off anime. This repository does **not** copy official images, animation
frames, logos, dialogue, or audio.

The source code is MIT-licensed. The character identity and fan-art atlas are
not relicensed by that MIT grant. Read [RIGHTS_AND_ASSETS.md](RIGHTS_AND_ASSETS.md)
before redistribution or reuse. This project is unofficial and unaffiliated
with KADOKAWA, the authors, publishers, studios, or OpenAI.

## Documentation

- [Research and non-duplication audit](docs/RESEARCH.md)
- [Architecture and trust boundaries](docs/ARCHITECTURE.md)
- [Acceptance matrix](docs/ACCEPTANCE.md)
- [Repair playbook](docs/REPAIR.md)
- [Chinese guide / 中文说明](docs/README.zh-CN.md)
- [Security policy](SECURITY.md)
- [Contributing](CONTRIBUTING.md)

## License

Code and documentation: [MIT](LICENSE). Character and asset caveats:
[RIGHTS_AND_ASSETS.md](RIGHTS_AND_ASSETS.md).
