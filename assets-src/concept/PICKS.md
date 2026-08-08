# Picked concepts — the reference each 3D model is built to match

**What this is.** Concept generation produces several images per building from different
random seeds. One is chosen. This file records which, so the modelling stage and any later
comparison read it from a file rather than from someone's memory.

Provenance for every image — model, seed, full prompt, recipe hash — is in
`tools/pipeline/provenance.json`.

| Asset | Picked | Recipe | Chosen because |
|---|---|---|---|
| `keep` | `keep/keep_1002.png` | `80c521459f4653d2` | Crisper stonework than the alternatives, the crimson banner reads as authority rather than decoration, firelight and steps at the door. The rebuilt corner from the prompt is visible. |
| `granary` | `granary/granary_2002.png` | `aa47c1882d7845d3` | The only take with a prominent grain chute, on staddle stones, with no interior light. Reads as storage, not a dwelling. |
| `watchtower` | `watchtower/watchtower_1002.png` | `80c521459f4653d2`-family | Passes the 64-pixel silhouette test outright — tall, thin, unmistakable outline, brazier reading as the "life" role. |

## Known drift, accepted at this stage

All fifteen concepts are **brighter and more saturated than the locked palette** — the thatch
especially, and the reds sit closer to pure red than Ostmere crimson `#8C2323`.

This is accepted here and must not be accepted later. A concept only has to be right about
**shape, proportion and identity**. Colour is decided in stage 3, where albedo is generated in
UV space and can be measured against `docs/ART_BIBLE.md` numerically. If the drift survives
stage 3, it is a defect.

## The rejected images are still committed

They are cheap, they are already in Git LFS, and they are the honest record of what the prompt
actually produced — including the four granaries that came out as houses, which is why the
granary prompt file carries its own history section.
