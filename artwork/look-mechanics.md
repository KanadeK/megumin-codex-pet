# Megumin look mechanics

Megumin is a humanoid pet with a separate head, large expressive eyes, a wide
soft hat, a short cloak, and a rigid staff held in her left hand. Looking is
therefore led by both irises and eyelids, followed by a small head and neck
turn, then restrained shoulder, hat-tip, hair, and cloak follow-through. Her
feet, lower torso, hand-to-staff contact, scale, and baseline stay anchored.
The staff remains rigid and attached; it may lag the shoulders by a few pixels
but never swaps hands, floats, bends, or crosses through the body.

## Cardinal pose families

- `000` up: irises and upper eyelids lift, eyebrows rise slightly, chin and hat
  brim tilt up, and a little more face/forehead becomes visible. The torso stays
  frontal and grounded; the hat tip follows upward without rotating the whole
  sprite.
- `090` screen-right: eyes, nose, chin, and head turn unmistakably toward the
  viewer's right edge. More of the character's left cheek and the far edge of
  the hat become visible, the near right cheek narrows, and the shoulders follow
  subtly. The staff remains on the screen-left side and lags the turn.
- `180` down: irises and eyelids lower, eyebrows soften, chin tucks, and the hat
  brim hides slightly more forehead. The upper torso inclines only a little;
  feet and staff base remain fixed.
- `270` screen-left: eyes, nose, chin, and head turn unmistakably toward the
  viewer's left edge. More of the character's right cheek becomes visible and
  the opposite cheek narrows. The staff is still held on the screen-left, may
  become slightly more side-on or partly occluded, but never detaches.

## Continuity and motion budget

Each 22.5-degree step advances the eyes first and the head/neck second by a
similar visual amount. Shoulder, hair, hat tip, cloak edge, and staff follow
with less displacement than the face. No adjacent step may change head size,
body height, staff hand, hat design, leg arrangement, or baseline. The motion
forms one clockwise loop: up to right to down to left and back to up, with no
backtracking, whole-sprite rotation, skull warping, replacement eyes, or
independently recentered poses.
