# Final visual QA

Release: **v0.1.1**

Result: **pass**

## Corrective context

The v0.1.0 review incorrectly treated the clean final-atlas contact sheet as
proof that the separately generated public GIFs were also clean. Those GIFs
actually came from pre-despill intermediate frames and retained fluorescent
green chroma outlines. This claim was invalid and is superseded by the v0.1.1
corrective review.

v0.1.1 renders every public GIF directly from `pet/spritesheet.webp`, the exact
packaged atlas. The packaged atlas remains byte-identical, with SHA-256
`529125d140845a1e45866284e272a2b5d620e1d1b17816816ed1f306221984ec`.
The reported v0.1.0 copies measured 681 affected boundary pixels in
`waving.gif` and 2,902 in `running-right.gif`; their v0.1.1 replacements both
measure zero.

## Independent review

An isolated, read-only reviewer inspected all nine repaired GIFs frame by
frame, the original-size light/dark background sheet, the machine audit, and
representative standard rows in the packaged atlas.

The reviewer confirmed:

- all 57 GIF frames are 192×208, loop with the contract timing, and contain
  zero chroma-colored boundary pixels;
- no fluorescent green edge, transparency contamination, continuous black
  fringe, white halo, clipping, or canvas-edge contact remains;
- every frame retains at least five pixels of outer margin;
- idle, directional running, waving, jumping, failed, waiting, active-work,
  and review animations remain ordered and readable;
- screen-left and screen-right locomotion face and move in the correct
  direction;
- the hat, costume, white leg wrap, dark stocking, face, palette, cape, and
  staff remain coherent across rows;
- the small separated red shape inside the staff hook is the intentional
  floating magic stone, not a broken or detached sprite fragment;
- the final-frame holds of 220–320 ms are intentional timing, not frozen or
  duplicated frames.

Machine evidence: `artwork/qa/preview-audit.json`.

Background evidence: `artwork/qa/preview-background-check.png`.
