# Security policy

## Supported versions

Security fixes are provided for the latest released minor version.

## Reporting

Please use GitHub's private vulnerability reporting for:

- archive traversal, unsafe extraction, or checksum bypass;
- install paths escaping the selected Codex home;
- HTML injection in generated reports;
- denial-of-service paths that bypass documented archive limits;
- accidental inclusion of credentials or private user data.

Do not open a public proof-of-concept issue before a fix is available. Include a
minimal reproducer, affected version, impact, and suggested remediation.

Rights-holder removal requests may use the same private channel; see
`RIGHTS_AND_ASSETS.md`.

## Design constraints

PetDiff does not execute files from pet packages. Installation copies only the
validated manifest and referenced atlas. Packages have per-entry and total-size
limits and reject encryption, duplicate names, unsafe paths, unlisted files,
and digest mismatches.
