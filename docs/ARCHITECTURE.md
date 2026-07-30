# Architecture

## Design goal

PetDiff answers a concrete maintenance question: **did an atlas upgrade preserve
the pet contract and intended motion, and where did it change?** The answer must
be reproducible without opening a GUI.

```text
pet directory / lock JSON
          |
          v
  manifest + atlas inspector
          |
          +--> strict contract findings
          |
          +--> 88 cell records
          |      alpha / bbox / centroid / fingerprints
          |
          +--> 10 loop-motion records
                         |
baseline + current + policy
          |
          v
       PetDiff
          |
          +--> stable JSON evidence
          +--> self-contained HTML review
          +--> process exit code
```

## Modules

- `contract.py` is the single source of truth for dimensions, rows, frame
  counts, direction angles, identifiers, and safe relative paths.
- `atlas.py` validates a pet and creates deterministic snapshots. It stores no
  timestamps or host paths inside a lock.
- `diffing.py` compares snapshots under a closed-schema policy. Unknown policy
  keys fail rather than being silently ignored.
- `packaging.py` creates a sorted, fixed-timestamp zip with internal SHA-256
  checksums, then independently verifies archive paths and limits.
- `installer.py` stages and validates before an atomic directory replacement.
  Existing installs are moved to `.backups`; uninstall moves to `.trash`.
- `cli.py` maps all successful and failed operations to machine-readable JSON
  and stable exit codes.

## Metrics and intended limits

The lock stores two downsampled fingerprints per cell:

- `silhouette_16`: alpha-only, useful for shape and pose changes;
- `rgba_16`: full RGBA, useful for palette and detail changes.

These are review fingerprints, not perceptual proofs. PetDiff also compares
alpha-area ratios and full-resolution weighted centroids. A policy can approve
large planned redesigns while a release policy keeps unreviewed drift small.

Motion metrics compare adjacent frames, including the loop seam:

- mean and maximum centroid movement;
- mean and maximum silhouette change;
- mean and maximum alpha-area change.

The 16 look directions are one clockwise loop, so the last-to-first seam is
included.

## Trust boundaries

- Manifest paths are validated before resolution and must remain inside the pet.
- Packages reject absolute paths, `..`, backslashes, duplicates, encryption,
  oversized entries, unlisted files, and checksum mismatches.
- Installation never copies arbitrary extra files from a package.
- A lock is review evidence, not a signature. CI should obtain the baseline
  lock from the base branch so a PR cannot silently update both atlas and lock.
- HTML escapes all user-controlled strings and embeds only escaped JSON.

## Deliberate non-goals

- PetDiff does not decide whether a character asset is legally distributable.
- Fingerprints do not replace visual review of identity, direction semantics,
  continuity, or animation quality.
- It does not manufacture missing animation frames.
- It does not permanently delete installed pets.
