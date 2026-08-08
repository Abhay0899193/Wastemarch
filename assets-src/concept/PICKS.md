# Picked concepts — the reference each 3D model is built to match

**What this is.** Concept generation produces several images per building from different
random seeds. One is chosen. This file records which, so the modelling stage and any later
comparison read it from a file rather than from someone's memory.

Provenance for every image — model, seed, full prompt, recipe hash — is in
`tools/pipeline/provenance.json`.

**Chosen by the project owner, 8 August 2026.**

| Asset | Level | Picked | Chosen because |
|---|---|---|---|
| `granary` | 1 | `granary/granary_3002.png` | Replaces `granary_1004` on 8 Aug 2026. The owner generated a better granary elsewhere — heavy timber planking with exposed beams, a deep thatch roof with a real overhang, stone footings, a lean-to holding sacks with a fire in it — and that design was regenerated through our own pipeline so it lands on the **flat background** camera projection requires. The owner's own version had a vignette and a ground disc, which makes the building's outline unfindable. |
| `watchtower` | 1 | `watchtower/watchtower_1004.png` | Stone core with splayed timber bracing legs, external ladder, railed platform, brazier, paved base. Better structural logic than the alternatives and the silhouette is still unmistakable. |
| `keep` | 1–2 | `keep/keep_1002.png` | Compact and vertical. The early keep: one tower, tight walls, firelight and steps at the door. |
| `keep` | 4–5 | `keep/keep_1003.png` | The same building **grown up** — larger walled enclosure, more crenellation, tower set back behind a courtyard. |

### The keep has two references, on purpose

`keep_1002` and `keep_1003` are the *same building at different upgrade levels*, not two
candidate designs. The parametric builder reads them as the two ends of the progression and
interpolates the levels between. This is exactly the case `MASTER_PLAN.md` section 7.3 argues
for scripted models over hand-made ones: five hand-modelled keeps would drift apart, one
script with a `level` parameter cannot.

## Known drift, accepted at this stage

All fifteen concepts are **brighter and more saturated than the locked palette** — the thatch
especially, and the reds sit closer to pure red than Ostmere crimson `#8C2323`.

This is accepted here and must not be accepted later. A concept only has to be right about
**shape, proportion and identity**. Colour is decided in stage 3, where albedo is generated in
UV space and can be measured against `docs/ART_BIBLE.md` numerically. If the drift survives
stage 3, it is a defect.

## The rejected images are still committed

They are cheap, they are already in Git LFS, and they are the honest record of what the prompt
actually produced — including the ones that came out as houses, which is why the granary prompt file
carries its own history section.

That history is worth reading with a caveat: the rewritten prompt (`granary_2001`–`2003`) did
produce the grain chute it was asked for, but the owner picked `granary_1004` from the
*original* batch anyway, and on inspection it reads as a grain store more convincingly. The
lesson is not that the prompt fix was wrong — it is that "the prompt did what I asked" and
"the picture is better" are different questions, and only the second one matters.
