# Art Bible — the rules every asset obeys

**What this is.** This is the contract that makes a few hundred separately-generated art
assets look like one team made them on purpose. It is the prompt-truth for every image
generated and the specification every 3D model is checked against. Nothing gets made in
bulk until this document is finished and you have personally approved three finished
reference buildings against it.

> **Status: partial.** The rules the master plan settles are written below and are binding
> now. **The colour palette is not yet locked** — see the section marked ⚠️. Locking it is a
> Phase 2 decision that needs your sign-off, because the risk register calls inconsistent
> art the one *critical* risk in the project, and colour is where inconsistency shows first.

---

## The one instruction that matters most

> **Every location must look like it had a life before the player arrived.**

Everything below is in service of that. Concretely:

- **Ruins with a purpose.** Not generic rubble — a collapsed *granary*, with the grain chute
  still visible. Not a broken wall — a wall broken *in one specific place*, by one specific
  thing.
- **The old field lines never go away.** Even at maximum base level, the pale straight lines
  of hundred-year-old field boundaries run under your buildings. This is a single texture
  decision that gives the entire map a history for almost no cost.
- **The Duskwood is always on screen.** From every camera angle, at every zoom level, the
  north edge of the frame has black trees in it. The player should never fully relax.
- **Light tells the story of progress.** Chapter 1 is one fire in the dark. Chapter 6 is a
  town with two hundred lit windows. The same camera angle at Chapter 1 and Chapter 6 should
  be the best screenshot in the game — put that comparison in the store listing.

---

## The camera — locked

Everything is designed for one camera and one camera only.

| | |
|---|---|
| Type | **Orthographic** |
| Elevation | **30°** above the horizon |
| Yaw (rotation around) | **45°** |
| Movement | Pan and pinch-zoom. **No rotation.** |
| Screen | Landscape, 1920 × 1080 base — see [ADR-0002](decisions/ADR-0002-landscape-orientation.md) |

**Orthographic** means there is no perspective: parallel lines stay parallel and something
far away is drawn exactly the same size as something near. It is what gives isometric games
their clean, diagram-like readability. The alternative, *perspective*, makes distant
buildings smaller and is wrong for this genre.

**All concept art must be generated at this angle.** A beautiful painting from any other
angle is unusable, because the model built from it will not read correctly in the game.

---

## Silhouette — the test every building must pass

**Fill the building with solid black, shrink it to 64 pixels tall, and look at it. You must
still be able to tell which building it is.**

This is not a stylistic preference, it is a legibility requirement. On a phone, buildings
are small and often partly hidden. If two buildings share a silhouette, players misread
their own base.

This test is **scripted and automatic** — it runs as part of asset validation, not as a
thing someone remembers to do.

Practically this means: each building needs one distinctive shape feature. A roof angle, a
chimney, a tower, an overhang. Not decoration on a shared box.

---

## Geometry budgets — enforced automatically

A **triangle** (*tri*) is the basic unit 3D graphics are built from. More triangles means
more detail and more work for the phone.

| Asset | Maximum triangles |
|---|---|
| Small building | 1,500 |
| Large building | 4,000 |
| Troop | 900 |
| **LOD1** (see below) | 40% of the original |

**LOD** stands for "level of detail" — a simplified copy of a model used when it is far away
or small on screen, where nobody can tell the difference. Every asset ships with two: the
full one and a 40% one.

The build **fails** if an asset is over budget. It is not a warning.

### Whole-scene budgets

| | |
|---|---|
| Draw calls on screen | **≤ 120** |
| Triangles on screen | **≤ 250,000** |
| Frame rate | **60 per second on an iPhone 12 and a Pixel 6a** |

A **draw call** is one instruction from the game to the graphics chip: "draw this batch of
stuff." They are expensive, and on mobile they are usually the thing that limits speed —
more so than triangle count. Two rules keep them low:

- **Repeated objects are drawn as one call.** Four hundred wall segments, trees, or crop
  rows are a single instruction, not four hundred. (The technique is called *instancing*.)
- **One shared material per art tier.** All buildings share one texture sheet, so the
  graphics chip can draw them together without stopping to switch materials.

---

## Texel density — uniform, 256 pixels per metre

A **texel** is one pixel of a texture as it appears stretched over the 3D surface. **Texel
density** is how many of them cover one real-world metre.

Every asset in Wastemarch uses **256 texels per metre**, without exception.

This single number is what most separates art that looks like a coherent product from art
that looks assembled from different sources. If one building has crisp detail and its
neighbour is soft and blurry, players notice immediately even if they cannot say why. It is
the number one giveaway of AI-assisted art sets.

Scale is likewise locked: **1 unit in Blender = 1 metre in the game**, and every model's
origin point sits at the centre of its ground footprint.

---

## Materials

| Rule | Value |
|---|---|
| Style | Stylised PBR |
| Roughness | **≥ 0.35**, always |
| Rim light | Gentle, baked into the shader |
| Maximum hues per asset | **5** |

**PBR** ("physically based rendering") is the standard modern way of describing surfaces —
how rough, how metallic, how reflective. **Stylised** PBR means we use the system but push
the values for looks rather than realism.

**Roughness never below 0.35** because shiny, mirror-like surfaces read as cheap on a phone.
Small screens, no reflections worth speaking of, and the highlights end up as distracting
white blobs. Matte is the premium look here.

**Maximum five hues per asset** forces restraint. Colour discipline is the difference between
"art directed" and "generated."

---

## ⚠️ Colour palette — NOT YET LOCKED

**This section needs your decision.** It is deliberately left open rather than invented,
because once bulk generation starts, changing the palette means regenerating everything.

The master plan specifies the *families*:

- Wasteland: ochres and bone-greys
- Duskwood: deep teal-blacks
- Ostmere heraldry: crimson and gold

### Proposed starting point, for discussion in Phase 2

Not locked. Shown so there is something concrete to react to.

| Role | Proposed | |
|---|---|---|
| Dead soil | `#8B8071` | The dominant ground colour |
| Bone grey | `#C4BCAE` | Old stone, field boundary lines |
| Dry ochre | `#A8813F` | Thatch, dead grass, timber |
| Duskwood near | `#1C2E2C` | The treeline |
| Duskwood deep | `#0A1412` | Beyond the treeline, and night |
| Ostmere crimson | `#8C2323` | Banners, tax inspectors, the kingdom |
| Ostmere gold | `#C99B3E` | Heraldry, accents. Used sparingly |
| Firelight | `#E8A54B` | The warm light in a cold place |
| Duskglass | `#3E7C8C` | The premium resource. Should feel *wrong* |

Design intent behind the proposal: the wasteland palette is deliberately drab so that
**firelight and Ostmere crimson are the only warm things on screen**, and every warm pixel
therefore means something. As the town grows, warmth spreads across the frame. The player
should feel the game brightening without noticing why.

**Before locking, we need:** your reaction to these, a colourblind-safety check (Phase 7
requires it anyway, and doing it now costs nothing), and a test render of all nine against
each other at phone size.

---

## Weather — four states, each one meaningful

| State | What it means mechanically |
|---|---|
| Cold clear | Baseline |
| Grey overcast | Baseline |
| Rain | *To be defined in Phase 5* |
| Duskwood haze — green-tinged | **Pressure is high.** Something is coming. |

**Weather that means nothing is just noise.** Four states, each carrying information, rather
than a dozen decorative ones. The haze in particular is a warning the player learns to read
without ever being told.

---

## The reference sheet

Three finished buildings, taken all the way through every pipeline stage and rendered at the
game camera, live at `docs/art/reference/`. **Every new asset is visually compared against
them before it is accepted.**

These three are the real Art Bible. This document is words about art; those are the art.

They do not exist yet — producing them is the Phase 2 gate. **They require your personal
approval.** You are the only check against the project's single critical risk.

---

## Related

- [ASSET_PIPELINE.md](ASSET_PIPELINE.md) — the machinery that produces assets to these rules
- [STORY.md](STORY.md) §5.3 — the visual direction these rules come from
