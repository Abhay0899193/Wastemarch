# Art Bible — the rules every asset obeys

**What this is.** This is the contract that makes a few hundred separately-generated art
assets look like one team made them on purpose. It is the prompt-truth for every image
generated and the specification every 3D model is checked against. Nothing gets made in
bulk until this document is finished and you have personally approved three finished
reference buildings against it.

> **Status: binding.** Every rule below is in force, including the colour palette, which was
> locked on 8 August 2026 — see [ADR-0004](decisions/ADR-0004-colour-palette.md). What is
> still missing is the part no document can supply: the three finished reference buildings at
> the bottom of this file. Until those exist and you have approved them, nothing is generated
> in bulk.

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

Practically this means: each building needs one distinctive shape feature. A roof angle, a
chimney, a tower, an overhang. Not decoration on a shared box.

### How a script can run a test about recognition

```bash
$BLENDER --background --factory-startup --python tools/blender/render_and_silhouette.py
```

Whether *you* recognise a shape is not something a script can judge. What a script can judge
is the thing that makes recognition impossible: **two buildings whose black shapes are nearly
the same**. So the check renders every building as a solid black 64-pixel shape at the game
camera and compares every pair. Sharing more than **80%** of a silhouette fails the build.

Two details make the difference between this measuring the rule and measuring nothing:

- **Every building is framed at the same scale.** The first version fitted the frame to each
  subject, which drew a 4.2-metre watchtower and a 2.5-metre shed at the same size. Size is a
  large part of how you tell buildings apart on a screen where they all stand on the same
  ground, and normalising it away made the test measure something the player never sees.
  Fixing it moved granary-versus-keep from 0.69 to **0.33** — the test had been reporting the
  wrong answer, in the safe direction, which is the worst kind.
- **A building is compared against its own upgrade levels too.** A level 5 keep must still be
  recognisably a keep, and still be tellable from a level 1 one. Measured at **0.71** — the
  closest pair in the set, and correctly so.

Current results, 8 August 2026:

| | granary | watchtower | keep L1 | keep L5 |
|---|---|---|---|---|
| **granary** | — | 0.54 | 0.33 | 0.24 |
| **watchtower** | | — | 0.38 | 0.28 |
| **keep L1** | | | — | **0.71** |

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
or small on screen, where nobody can tell the difference.

The build **fails** if an asset is over budget. It is not a warning.

### How LOD1 is made, and when it is not made at all

Two rules here were written from measurement on the first real building, on 8 August 2026, and
they replace the obvious approach:

**LOD1 is built by leaving parts out, not by simplifying triangles.** The obvious method is
Blender's *decimate* modifier, which collapses triangles until the model is 40% of its
original size. On buildings made of boxes it eats corners — that is, it destroys exactly the
silhouette this document spends a whole section protecting. Measured on the granary it also
produced a mesh Blender's own checker reported as broken, which the exporter then warned "may
export wrongly".

So each building script marks its parts as structure or as detail. The grain sacks under the
granary's lean-to are detail; the lean-to itself is structure and is never dropped. Turning
detail off is exact, repeatable, and cannot round off an outline.

**Below 400 triangles a model gets no LOD1 at all.** A second mesh costs memory and a draw
call. The granary is 162 triangles; saving 97 of them does not pay for that. The LOD exists to
save work, and below this size it creates more than it saves.

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

**What this costs, measured.** The granary — a 2×2-tile shed — has 39.4 square metres of
surface, which at 256 texels per metre is **2.6 million texels**, or a 1,607-pixel square if it
had a texture to itself. It does not have one: all buildings share a single texture sheet, so
what an asset really has is a *claim on the shared sheet*. The build reports that claim rather
than a per-asset texture size, because an asset that "needs a 4096 texture" is a unit error,
not a fact.

Whether 256 is the right number is a **fair question and it is not settled by this document**:
at typical phone zoom a building renders at roughly 60–100 pixels per metre, so 256 is two to
four times the resolution actually on screen. That headroom buys zooming in. It is revisited
when stage 3 first generates real textures — the geometry does not change either way, so this
is a cheap decision to defer and an expensive one to guess at.

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

### The five materials, and why there are exactly five

Every building is made of these and nothing else. The cap above *is* this list — adding a
sixth material means removing one.

| Material | Palette value | Roughness | Used for |
|---|---|---|---|
| stone | Bone grey `#C4BCAE` | 0.85 | Walls, footings, paving, steps |
| timber | Dead soil `#8B8071` | 0.75 | Posts, planking, doors, railings |
| thatch | Dry ochre `#9B8459` | 0.95 | Roofs, sacking |
| cloth | Ostmere crimson `#8C2323` | 0.80 | Banners and pennants **only** |
| firelight | Firelight core `#F7CE7C` | 0.55 | Braziers, lit windows. Emissive |

**The colours are used literally, not approximated.** The building scripts read the same hex
values this document locks, so the palette drift visible in concept art physically cannot
happen to a model. That is the point of doing colour in the model rather than only in a
generated texture.

### Rendering at the locked camera is a design check, not a preview

The watchtower's roof was built with a comfortable gap beneath it, which looks correct in a
side view and **completely hid the brazier** when seen from 30 degrees above — the only angle
this game has. The brazier is that building's entire "life" signal.

The fix was taller posts and a tighter roof overhang. The point is that no amount of care in
elevation would have found it: a building must be judged at the camera it will be seen at, and
that is why `render_and_silhouette.py` renders there and nowhere else.

---

## Lighting — almost none of it is real

"Chapter 6 is a town with two hundred lit windows" is the emotional core of this game. It is
also the single easiest way to make a phone run at fifteen frames per second, so how it is
built matters more than how it looks in a still image.

A **real light** is one the graphics chip calculates from scratch every frame. Godot's mobile
renderer supports only a handful before it slows down, and each one that casts a shadow costs
far more again. Two hundred of them is not a budget question, it is impossible.

So almost every light in Wastemarch is **painted, not calculated**:

| Thing | How it is built | Budget |
|---|---|---|
| Lit windows, embers, glowing runes | **Emissive** — the texture is simply told to be bright. Costs nothing extra | Unlimited |
| The pool of light a fire throws on the ground | A soft decal or painted texture patch | Unlimited |
| Soft shadow under a building | Painted into the ground texture, not calculated | Unlimited |
| Sun and its shadows | One real directional light | **1** |
| Hero fires — the Chapter 1 fire, the forge, story beats | Real point lights | **≤ 6 on screen** |

**Emissive** means the surface emits light of its own rather than reflecting any. On a phone
this is nearly free, and combined with a gentle bloom it is indistinguishable from a real
light at this camera distance. It is how every game in this genre does it.

**The consequence for asset authoring:** every building's texture needs its lit state
authored *into the texture* — window panes at `#F7CE7C`, warm patches on the wall beneath
them. That is a texturing decision made at generation time, not a lighting decision made
later, so it belongs in the prompt.

### The Duskwood treeline is a budget item, not scenery

The rule that the Duskwood is always on screen means a band of trees in every single frame.
At three hundred triangles a conifer and two hundred visible, that is 60,000 triangles —
roughly a quarter of the entire scene budget — spent on background the player never
interacts with.

**The treeline is built as one instanced band of low-triangle trees, with the deep rows as
flat cards.** Detailed tree models are only for the few trees the player can actually walk up
to. This is decided here rather than discovered in Phase 3, when it would mean remodelling.

---

## Colour palette — LOCKED

Locked 8 August 2026 by the project owner. Reasoning and the measurements behind it are in
[ADR-0004](decisions/ADR-0004-colour-palette.md). **Changing any value means regenerating
every asset**, so it is not a casual edit.

| Role | Value | Job | Where it appears |
|---|---|---|---|
| Dead soil | `#8B8071` | environment | The dominant ground colour |
| Bone grey | `#C4BCAE` | environment | Old stone, field boundary lines |
| Dry ochre | `#9B8459` | environment | Thatch, dead grass, timber |
| Duskwood near | `#1C2E2C` | environment, dark | The treeline |
| Duskwood deep | `#0A1412` | environment, dark | **Background and sky only** — never a surface the player must read |
| Ostmere crimson | `#8C2323` | faction | Banners, tax inspectors, the kingdom |
| Ostmere gold | `#C4942F` | wealth | Heraldry and trim. Small, sharp accents only |
| Firelight core | `#F7CE7C` | life | The lit thing itself — window panes, flame centres. The brightest thing on screen |
| Firelight glow | `#E8A54B` | **light, not a surface** | The colour fire *casts*. Never painted on anything |
| Duskglass | `#3E7C8C` | rare resource | The premium resource. Should feel *wrong* |

**The intent.** The wasteland is drab so that **firelight and Ostmere crimson are the only
warm things on screen**, and every warm pixel therefore means something. As the town grows,
warmth spreads across the frame. The player should feel the game brightening without
noticing why.

### The ten rules that make it hold

1. **Environment dominates.** Most of any frame is the muted environment palette. The drab is
   not a failure of ambition; it is what makes the accents work.
2. **Warmth means life.** Firelight, lit windows, active workshops, fed people.
3. **Crimson means authority.** Ostmere crimson is for faction identity, political power and
   heraldry. Most Ostmere buildings stay in the ordinary world palette — if everything the
   kingdom owns is crimson, crimson stops meaning power and starts meaning "wall".
4. **Gold means value**, in small sharp accents: trim, edges, icons, rewards. Gold and dry
   ochre are only 3° apart in hue; gold reads as gold because it is **metallic and catches a
   highlight**, not because of its albedo. Used as a large flat fill it becomes ochre.
5. **Duskglass means rarity.** Under 2% of any frame. Blue crystals everywhere stop being
   mysterious and become "the blue resource."
6. **Saturation is a hierarchy tool, never a global setting.** The environment stays muted so
   important things can stand out. Nothing is maximised.
7. **Value beats hue.** Every important object must still be readable with the colour
   removed. This is the same principle as the silhouette test above, applied to brightness
   instead of shape — and it is checked the same way, by script.
8. **Colour is never the only signal.** Anything that matters to play carries at least two
   of: colour, silhouette, icon, animation, glow. A player who cannot see colour must still
   be able to play. Phase 7 requires this anyway; building it in now costs nothing.
9. **Nothing the player must read goes below L\* 20** in the default weather state. Phones
   are used outdoors, at half brightness, on cheap panels. `Duskwood deep` is L\* 5.5 — it is
   sky and distance, never a floor, a wall or a unit.
10. **Light does not redefine material.** Firelight and night shift what a surface *looks*
    like; they never change what it *is*. The same timber is the same timber at noon and by
    torchlight, or the world stops feeling solid.

### The check

```bash
python3 tools/art/palette_check.py
```

It measures every pair of colours that carry different meanings, in CIE Lab, then repeats the
measurement under simulated deuteranopia, protanopia and tritanopia. It **fails the build** if
any two colours with different jobs become confusable, and it fails if this document and the
script disagree about a value. It runs in CI.

Run against the original nine proposed values it found **four failures** — see the ADR. That
is why two values moved and one was split in two.

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
