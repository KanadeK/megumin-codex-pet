# Artwork workflow

The committed files in `hatch-run/` are deterministic layout guides and
generated prompts for the Codex v2 hatch process. They are not a finished pet.

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
   cells plus 15 transparent reserved cells.
5. Record three isolated blind reviews: identity/animation, direction
   semantics, and final package.
6. Commit the final approved atlas, `pet.lock.json`, provenance record, contact
   sheet, and compact motion previews.

The selected chroma key is pure `#00FF00`, which is excluded from the pet
palette. See `RIGHTS_AND_ASSETS.md` for the noncommercial fanwork boundary.
