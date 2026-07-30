# Failure and repair playbook

Never bypass the release gate. Use the finding code to repair the smallest
scope, then rerun the failing command and the full strict gate.

## `manifest-*`, `manifest-missing`, or `atlas-missing`

1. Restore `pet/pet.json`.
2. Keep `spriteVersionNumber` equal to `2`.
3. Use a normalized relative `.webp` or `.png` path with forward slashes.
4. Confirm the referenced file exists inside `pet/`.
5. Run `petdiff validate pet`.

Do not use `..`, an absolute path, a symlink escape, or a path outside the pet.

## `atlas-dimensions`

The final v2 atlas must be exactly `1536×2288`: eight 192×208 columns and eleven
rows. Re-run the hatch assembly script from approved row strips. Do not resize a
wrong grid until it merely has the expected outer dimensions.

## `required-cell-empty`

The named cell is one of the 73 required poses. Return to the complete generated
row, repair/regenerate that row according to the hatch workflow, reassemble, and
run:

```bash
petdiff validate pet --json-out build/validation.json
```

Do not paste an unrelated one-off frame into a coherent generated row.

## `unused-cell-visible`

Only standard rows have unused cells. Row 0 / col 6 is the one optional
neutral/default pose and may be visible or transparent; it must not trigger
this finding. Clear any other named reserved cell to full alpha zero through
the deterministic hatch assembler, not by hiding it with a background color.

## `cell-edge-contact`

Foreground alpha touches a cell border. Re-register the complete row with a
smaller common scale or safer centering, then inspect neighboring cells for
continuity. Cropping a single frame usually causes size jitter.

## `cell-budget-exceeded`

Open the HTML report and decide whether the change is intentional.

- Accidental: restore or regenerate the affected row.
- Intentional redesign: record the reason in the PR, attach before/after
  previews, obtain visual approval, and use a one-time review policy.
- Do not loosen `examples/release-policy.json` merely to make CI green.

After approval, regenerate `pet/pet.lock.json` from the exact final atlas and
commit the atlas and lock together.

## `motion-budget-exceeded`

Inspect the named loop including its last-to-first seam. Common repairs are:

- restore consistent scale and baseline across the row;
- remove a single large centroid jump;
- restore alternating locomotion cadence;
- regenerate the complete look row if direction continuity breaks.

## `look-low-diversity`

This warning means fewer than eight distinct downsampled RGBA poses exist among
the 16 look directions. Inspect direction semantics and regenerate complete row
9 or row 10. Never silence it before the blind direction review.

## Package errors

- `unsafe archive entry`: discard the package; rebuild with `petdiff package`.
- `checksum mismatch`: discard the package; it was modified or corrupted.
- content mismatch/duplicate/encrypted/oversized: do not extract manually;
  rebuild from the validated unpacked pet.

## Install errors

- Existing `.petdiff-install.lock`: confirm no install process is running, then
  remove only that exact stale lock file.
- Failed replacement: the installer restores the prior target when possible.
  Inspect `.backups/<pet-id>/` before retrying.
- Recover an uninstall by moving the chosen
  `.trash/<pet-id>/<token>` directory back to `pets/<pet-id>` while Codex is
  closed, then run `petdiff doctor`.

## CI versus local mismatch

1. Use Python 3.11 or 3.12.
2. Recreate the virtual environment.
3. Install with `python -m pip install -e ".[dev]"`.
4. Run the exact commands in `docs/ACCEPTANCE.md`.
5. Compare Python, Pillow, and PetDiff versions in logs.

If a release asset hash differs remotely, stop distribution, delete or mark the
release as affected, rebuild from the tagged commit, and publish a new patch
version. Never silently replace a released binary under the same version.
