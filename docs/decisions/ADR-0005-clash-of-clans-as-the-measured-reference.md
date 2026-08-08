# ADR-0005 — Clash of Clans is the measured reference for camera, zoom and proportion

**Status:** accepted, 9 August 2026
**Supersedes:** the proportion rules in `docs/ART_BIBLE.md` as they stood on 8 August 2026
**Related:** [ADR-0002](ADR-0002-landscape-orientation.md), [ADR-0004](ADR-0004-colour-palette.md),
[COC_TEARDOWN.md](../reference/COC_TEARDOWN.md)

---

## What this is

The owner supplied sixteen screenshots of Clash of Clans' opening and said, in effect: match
this, and change anything of ours that gets in the way. This record says what was measured,
what changed as a result, and what was deliberately *not* changed.

## The decision

**Where Clash of Clans can be measured, its numbers win over ours.** Specifically:

| Thing | Decided |
|---|---|
| Camera | Orthographic, 30° elevation, 45° yaw — **unchanged**, because measurement confirmed we already matched them |
| Zoom range | **4.0×**, replacing a free 10× range |
| Fully zoomed out | frames the whole 44×44 grid with ~6% margin, computed from the screen shape at runtime |
| Building height | **≤ 0.6 × footprint**, replacing 1.6 |
| Building spread | **≤ 80% of its footprint**, replacing a rule that permitted 35 cm of overhang |
| Ground shadows | **none**, replacing one shadow-casting sun |

## Why

Our buildings were between two and four times too tall for the ground they stood on, which at
a 30° camera means each one hides about seven tiles of whatever is behind it. That, and not
the texture work or the polygon count, is what made our base read as a pile. The teardown
document has the measurements and the method.

The camera result is worth stating plainly because it is the useful kind of negative finding:
we spent no time changing it and now know we do not need to.

## What was considered and rejected

**Switching to pre-rendered 2D sprites.** The owner explicitly offered this. Rejected, because
the look being asked for comes from proportion, colour discipline and painted shading — all of
which are available in 3D and three of which have now been applied — while the costs of
sprites are the ones already argued in `MASTER_PLAN.md` §1.3. This is not a one-way door: our
buildings are built by script in Blender, so the same models can be rendered to sprites at the
locked camera later without re-modelling anything.

**Squaring the grid or changing tile size.** Also offered. Not needed — the grid is already
44×44 unit squares, which is what they use.

## The cost we are accepting

The three existing buildings were *squashed* into the new proportions rather than redesigned
at them, which flattens roof pitches and blunts small details. It is the cheap way to see the
change now. Each builder's own constants get re-tuned once the owner approves the proportions;
there is a `ponytail:` note in `tools/blender/build_asset.py` recording that.

Every building also lands exactly on the height limit rather than varying beneath it, so the
set has less variety of proportion than Clash of Clans does. Same fix, same time.
