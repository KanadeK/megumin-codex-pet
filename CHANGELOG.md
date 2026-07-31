# Changelog

All notable changes follow Keep a Changelog conventions.

## [Unreleased]

## [0.1.1] - 2026-07-31

### Added

- `petdiff render-previews` for deterministic transparent GIFs generated from
  the final packaged atlas.
- `petdiff audit-previews` for dimensions, frame counts, durations, and
  chroma-colored boundary pixels.
- Light/dark background QA evidence and a preview audit in local and CI release
  gates.

### Fixed

- Replaced all nine public GIF previews that had been generated from
  pre-despill intermediate frames and showed fluorescent green outlines.

## [0.1.0] - 2026-07-31

### Added

- Original Codex v2 Megumin pet hatch workflow.
- Strict 8×11 atlas and manifest validator.
- PetDiff deterministic snapshots, policy comparison, and HTML evidence.
- Reproducible packages with hardened verification.
- Transactional install, doctor, retained backups, and recoverable uninstall.
- Cross-platform CI, composite GitHub Action, documentation, and release gate.

[Unreleased]: https://github.com/KanadeK/megumin-codex-pet/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/KanadeK/megumin-codex-pet/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/KanadeK/megumin-codex-pet/releases/tag/v0.1.0
