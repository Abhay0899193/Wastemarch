# ADR-0004 — The colour palette, locked

- **Status:** Accepted
- **Date:** 8 August 2026
- **Decided by:** the project owner, session 5
- **Settles:** the ⚠️ open section of [ART_BIBLE.md](../ART_BIBLE.md), which blocked Phase 2

---

**What this is.** Wastemarch now has ten fixed colours, and every asset ever made will use
them. This record says what they are, why two of the nine originally proposed had to move,
and what was measured rather than argued about.

---

## Context

The risk register in `MASTER_PLAN.md` calls inconsistent art the single **critical** risk in
the project — the one that, if it goes wrong, defeats the whole goal of looking premium.
Colour is where inconsistency shows first and worst, so the palette was deliberately left
unlocked until it could be signed off rather than invented in passing.

The owner proposed nine values and had them reviewed elsewhere. The Art Bible required, before
locking, "a colourblind-safety check and a test render of all nine against each other at phone
size." That check was written as `tools/art/palette_check.py` and run, rather than eyeballed.

## What the measurement found

**The proposed set had four real failures**, all in the same place: dry ochre, Ostmere gold
and firelight sat inside an 8-degree band of hue.

| Pair | Difference, normal vision | Worst under colour blindness |
|---|---|---|
| Ostmere gold / Firelight | 10.5 | **4.9** (protanopia) |
| Dry ochre / Ostmere gold | 16.3 | **10.4** (tritanopia) |

The scale is CIE76 *delta-E*: below about 10 two colours are easy to confuse at a glance,
below 5 they are effectively the same colour. So to a player with the most common form of
red-green colour blindness, **"wealth" and "life" were the same colour**.

Two further problems came out of the same numbers and had not been noticed by anyone:

- **Firelight was darker than bone grey.** Lightness 72.6 against 76.5. A lit window would
  have read *dimmer* than the stone wall around it, which makes the pillar "light tells the
  story of progress" not merely hard but arithmetically impossible.
- **Dry ochre was too saturated for its own job.** Chroma 41.5, against gold's 54 and
  firelight's 57. The Art Bible says the environment is drab *so that accents mean
  something*; ochre was competing with the accents it exists to make room for.

A suggestion from the external review — desaturating firelight from `#E8A54B` to `#D99543` —
was tested and **rejected because it makes the problem worse**: it moves firelight onto gold's
lightness exactly, and the protanopia difference falls from 4.9 to 3.6. The collision is along
the lightness axis, so desaturating cannot fix it.

## Decision

**Ten values, locked.** Six unchanged from the proposal, two moved, one split into two roles.

| Role | Value | Change |
|---|---|---|
| Dead soil | `#8B8071` | — |
| Bone grey | `#C4BCAE` | — |
| Dry ochre | `#9B8459` | **moved** — desaturated, so the environment is actually drab |
| Duskwood near | `#1C2E2C` | — |
| Duskwood deep | `#0A1412` | — (now restricted to background and sky) |
| Ostmere crimson | `#8C2323` | — |
| Ostmere gold | `#C4942F` | **moved** — deeper, so it clears firelight |
| Firelight core | `#F7CE7C` | **new** — the lit surface itself, now the brightest thing on screen |
| Firelight glow | `#E8A54B` | the originally proposed firelight, **reclassified as a light colour** |
| Duskglass | `#3E7C8C` | — |

Plus the ten rules written into `ART_BIBLE.md`, of which three are new and load-bearing:
value must beat hue, colour is never the only gameplay signal, and nothing the player must
read goes below lightness 20.

On this set the checker passes: every pair of colours with different meanings stays
distinguishable in normal vision **and** under all three simulated forms of colour blindness.

## Why these particular fixes

**Splitting firelight in two is the key move.** The original `#E8A54B` was being asked to be
two things at once: the colour of a lit window *surface*, and the colour of the light a fire
*casts*. Those have different constraints. A surface has to hold its own against every other
surface in the palette; a cast light is always seen next to its own bright source and is never
a flat fill beside another colour. Separating them means the owner's chosen value survives
intact in the role it was actually good at, and the surface role gets a value bright enough to
do its job.

**Gold is a material, not a hue.** Gold and dry ochre remain only 3° apart in hue even after
the fix, and the checker still warns about it. That is accepted deliberately: gold reads as
gold because it is metallic and catches a moving highlight, not because of its albedo colour.
The rule that follows — gold only in small, sharp, trimmed accents — is in the Art Bible.

## Alternatives considered

**Lock the original nine unchanged and handle collisions with shape and material.** Defensible
— rule 8 already requires two signals for anything important. Rejected because it spends the
accessibility budget covering for an avoidable colour problem, and because the firelight
lightness bug would have quietly undermined the game's best screenshot.

**Lock relationships rather than hex values,** as the external review suggested. Right as
reasoning, unusable as practice: ComfyUI prompts and Blender materials need literal values,
and "medium-low saturation" generated a hundred times produces a hundred different colours.
The relationships are recorded as the *rules*, which is where they do their work; the hex
values are their implementation.

## Consequences

**Good.** Phase 2 is unblocked. The palette is now checkable by a script rather than by
memory, and that script runs in CI, so a value cannot drift silently between the document and
the pipeline. The accessibility work Phase 7 requires is largely done already.

**Costly.** These values are now expensive to change. Every generated asset from this point
carries them.

**Follow-on.** Rules 7 and 8 — grayscale readability and two-signal identification — need to
become **automatic checks** alongside the existing silhouette test, or they will decay into
good intentions. Recorded in `docs/BACKLOG.md`.

**Reversibility.** Cheap until the first bulk generation run, effectively impossible after.
That is exactly why it was settled before Phase 2 rather than during it.
