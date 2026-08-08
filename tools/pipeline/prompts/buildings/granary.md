# Granary — the small agricultural building, and the adjacency test case

Small building, 2x2 tiles, ≤1,500 triangles. Sits beside farms for the adjacency bonus, so it
must read as agricultural at a glance and never be mistaken for housing.

**Prompt history, third version.**

1. The first asked for a grain chute and produced a convincing barn with a *lit window* — the
   "mistaken for housing" failure it was written to prevent.
2. The second led with the chute and got it, but the owner preferred `granary_1004` from the
   first batch anyway, and on inspection it read as a store more convincingly.
3. This one takes its design from an image the owner generated elsewhere, which was better than
   anything in either batch: heavy timber planking with exposed beams, a deep thatch roof with
   a real overhang, stone footings, and a lean-to holding grain sacks with a fire inside it.

**The background instruction is load-bearing now, not decoration.** Since `project_concept.py`
paints models with their concept art, the pipeline has to find the building's outline in the
image by thresholding against a flat background. The owner's version had a vignette and a
ground disc, which makes the outline unfindable and leaves the model patchy grey. Flat
background, no ground, no vignette, or the image cannot be used as a texture.

Everything below the line is prompt text.

---
a small timber grain store on low stone footings, walls of heavy vertical planking with
exposed horizontal beams and visible grain in the wood, a deep steeply pitched thatched roof
with a thick ragged edge and a generous overhang past the walls, a ridge pole running along the
top, a plain plank door with an iron handle on the gable end, and along one side a low open
lean-to under its own shallow plank roof holding stacked grain sacks with a small warm fire
glowing among them, weathered and worked-in, no windows, standing alone on nothing, no ground,
no base, no dirt, no vignette, flat even neutral grey background
