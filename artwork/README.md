# Artwork workflow and release evidence

The committed files in `hatch-run/` are deterministic layout guides and
generated prompts for the Codex v2 hatch process. The approved v2 atlas is
packaged under `pet/`; compact review evidence is committed under `artwork/qa/`.

Local state files (`imagegen-jobs.json` and `pet_request.json`) are ignored
because they contain machine-specific absolute paths. Generated source images,
assembled atlases, and heavy preview media remain local until they pass the
required visual and deterministic reviews.

Release artwork requirements:

1. Generate one original base sprite from the text-only identity brief; do not
   attach or copy official artwork.
2. Generate each coherent animation row through ImageGen. A programmatic fake
   row is not acceptable.
3. Generate the four cardinal look anchors, then the two complete eight-pose
   look rows.
4. Assemble the 8×11 atlas with the hatch scripts and validate all 73 required
   cells, the optional neutral pose at row 0 / col 6, and 14 transparent
   reserved cells.
5. Record three isolated blind direction classifications and one separate
   isolated final identity/animation/package review.
6. Commit the final approved atlas, `pet.lock.json`, provenance record, contact
   sheet, and compact motion previews.

The selected chroma key is pure `#00FF00`, which is excluded from the pet
palette. See `RIGHTS_AND_ASSETS.md` for the noncommercial fanwork boundary.

The final atlas hash, generated-row hashes, cardinal remap, and QA file map are
recorded in [`qa/provenance.json`](qa/provenance.json). The approved contact
sheet, look-direction sheet, blind verdict, continuity report, strict
validation, final visual review, and compact GIFs are stored beside it.
