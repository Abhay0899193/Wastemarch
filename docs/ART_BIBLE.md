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
| Tile shape on screen | **2 wide : 1 tall**, which follows from the 30° |
| Movement | Pan and pinch-zoom. **No rotation.** |
| Zoom range | **exactly 4×**, fully out to fully in |
| Fully zoomed out shows | the whole 44 × 44 grid with ~6% margin |
| Opening view | fully zoomed out |
| Screen | Landscape, 1920 × 1080 base — see [ADR-0002](decisions/ADR-0002-landscape-orientation.md) |

> **This was checked against Clash of Clans and is correct to the degree.** Their tile
> diamonds measure 2:1 on screen, which is what a 30° elevation produces and nothing else
> does. The zoom range was measured at 4.00×. See
> [COC_TEARDOWN.md](reference/COC_TEARDOWN.md) for the method.
>
> The zoom limits are computed at runtime in `game/city/city.gd` from the grid size and the
> shape of the screen, because a phone is about 2.17:1 and a tablet 1.33:1 — a single number
> would be wrong on one of them.

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

Current results, 9 August 2026, at the reproportioned sizes:

| | granary | watchtower | keep L1 | keep L5 |
|---|---|---|---|---|
| **granary** | — | 0.40 | 0.23 | 0.17 |
| **watchtower** | | — | 0.35 | 0.26 |
| **keep L1** | | | — | **0.74** |

> **This test was measuring the wrong models until 9 August 2026.** It built its subjects
> straight from the builder functions and so skipped the reproportion step, meaning it
> faithfully reported on geometry the game never shows. It was the third place in the codebase
> that made its own copy of a model; there is one way to get one now, `build_asset.build()`,
> and all three go through it. **A test that quietly measures the wrong thing is worse than no
> test**, because it is also spending your confidence.

---

## Proportion — the rule that decides whether a base looks like a town

**A building may be no taller than 0.6 × the shorter side of its footprint, and its geometry
may fill no more than 80% of the tiles it occupies.** Both are enforced by
`tools/blender/build_asset.py` and both **fail** the build.

**Each asset may also declare its own pair of numbers, tighter or taller than the default.**
What hides the ground behind a building is its *area* on screen, not its height alone: a
3 metre mast half a tile wide blocks less than a 2 metre barn three tiles wide. So a building
buys height by being thin. The watchtower is declared at `fill 0.5, height 1.0` and reads as a
tower; at the shared default it read as a shed. The hard ceiling nothing may pass is
`fill 0.8, height 1.2`. See `PROPORTION` in `build_asset.py`.

These are the two most important numbers in this document, and neither was chosen — both were
measured off Clash of Clans screenshots at known zoom. Their Town Hall is 0.55 as tall as its
4×4 plot is wide and its art covers 69% of that plot. Ours were previously allowed 1.6 and
were *encouraged* to overhang their tiles.

**Why height is expensive.** At 30° elevation a building of height *h* hides roughly 1.7 × *h*
tiles of ground behind it. The ground behind is where the next building goes. So a keep at
1.0 blots out seven tiles of its own neighbourhood and a keep at 0.6 blots out four — the
difference between a base that reads as a pile and one that reads as a settlement.

**Why the 80% matters.** The ring of grass left round each building is what stops two
neighbours merging into one shape at phone size. It does the job the old overhang allowance
was preventing.

| Building | Footprint | Width | Height | Ratio |
|---|---|---|---|---|
| Granary | 2×2 | 1.60 m | 1.20 m | 0.60 |
| Watchtower | 3×3 | 1.50 m | 3.00 m | 1.00 |
| Keep | 4×4 | 3.20 m | 2.40 m | 0.60 |

**The squash is measured once, on level 1, and reused for every level.** Measuring it per
level normalises every level into the same box — a level 5 keep came out exactly the size of a
level 1 one and the entire upgrade interpolation vanished. The silhouette test caught it at
0.95 overlap, which is what that test is for.

---

## The ground

The whole field is **one shader on one quad**. Forty-four squared is 1,936 tiles; as meshes
that is a draw-call problem and as a texture a memory one, but as arithmetic it is free and
stays sharp at every zoom.

| Rule | Why |
|---|---|
| **No grid lines.** Tiles alternate in brightness by about **5%** | Clash of Clans has no lines at all. You can always tell where a building will land; you never consciously see a grid. Lines at this camera read as graph paper. |
| Each tile also gets a tiny random brightness offset | Stops the checker looking mechanical |
| Three scales of mottling over the top | A flat colour reads as a flat colour |
| Patches of scrub over soil, from broad noise | One palette colour across 1,936 tiles reads as desert |
| The old field lines, at an angle to the grid | The Art Bible's own instruction at the top of this file, and it costs two lines of shader |
| Beyond the playable square, the ground goes to **Duskwood** over 2 m | Frames the field the way their treeline does, without a fence |

**The pattern must be computed from world position.** In a Godot fragment shader `VERTEX` is
in *view* space, so using it directly pins the pattern to the screen: the checker came out as
screen-aligned squares instead of diamonds and the edge of the world was a horizontal line
across the middle of the frame. One `INV_VIEW_MATRIX` multiply is the difference between a
grid on the ground and a grid on your eye.

## Props — the scatter tier

Trees, rocks and stumps are drawn by `MultiMeshInstance3D`: any number of copies of one mesh
in a single draw call. That is what makes a hundred and sixty of them affordable, and
`CLAUDE.md` requires it for anything repeated.

- **200 triangles each, maximum.** The per-copy cost is what matters when hundreds are on
  screen. A pine is 48 and a boulder 24.
- **Foliage is at least six-sided.** A four-sided cone shows the camera exactly two faces, one
  lit and one nearly unlit, so a dark tree reads as two shapes — a bright triangle with what
  looks like its own cast shadow beside it. Six faces makes that a gradient. It cost six
  triangles.
- **They block building.** Like Clash of Clans' obstacles, a prop owns its tile until it is
  cleared. They are laid out from a fixed seed rather than saved, so the save file never has
  to carry scenery.
- **Bare ground is what makes a small base look unfinished rather than early.** This is the
  cheapest large improvement available to us.

---

## Geometry budgets — enforced automatically

A **triangle** (*tri*) is the basic unit 3D graphics are built from. More triangles means
more detail and more work for the phone.

| Asset | Maximum triangles |
|---|---|
| **Prop** — tree, rock, stump | **200** |
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

**One of those five is the building's identity, and it goes on the roof.** In Clash of Clans
you name a building by its roof colour before you can make out its shape — Town Hall orange,
Barracks red, elixir purple — against neutral grey-and-brown bases and a single flat green
ground. Our palette is muted by [ADR-0004](decisions/ADR-0004-colour-palette.md) and the
setting demands it stays muted, so we cannot copy their saturation. We can copy the
*structure*: neutral base, one identifying hue on the roof, nothing on the ground competing
with it. **The palette does not yet supply enough separable roof hues to do this** — that is
an open piece of work, recorded in `docs/BACKLOG.md`.

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

### Buildings are painted with their own concept art

**The camera makes this possible, and it is the reason the camera is locked.**

Camera projection — painting a flat image onto geometry along one viewing direction — is the
standard way to get concept art onto a model. It is normally a compromise, because the texture
is only correct from the angle it was projected along and smears from anywhere else.

**Wastemarch has no other angle.** The camera above is orthographic, fixed at 30 degrees and
45 degrees, pan and zoom only. Under an orthographic projection every building sees the camera
from the same direction wherever it stands on the grid, and zoom changes scale without changing
angle. The one condition that makes camera projection unusable in most games is the condition
this game removed on purpose in Phase 0.

```bash
$BLENDER --background --factory-startup --python tools/blender/project_concept.py -- --asset keep
```

It reads which concept the owner picked from `assets-src/concept/PICKS.md`, projects it from
the game camera, and lines the model's outline up with the painted building's outline.

**This changes what a concept image is for.** It is no longer a reference to model *from*; it
is the asset's texture. Which means a concept that was never quite the right proportions is no
longer a small problem — it is a visible one.

> **The model must match its concept's proportions.** Where the model extends past the painted
> building, the projection samples flat background and the surface comes out blank grey.
> Getting a building's proportions right is now enforced by how it looks, not by anyone's
> discipline.

The two faces turned away from the camera receive the same texture stretched through the model.
They are never visible, so it does not matter — but it does mean these models are correct *for
this camera*, and a change to the camera rule would mean re-texturing everything.

### Surface detail comes from four tiles, shared by everything

Z-Image Turbo generates one seamless tile per material. `tools/blender/build_asset.py` then
strips its colour, normalises its brightness so its average is exactly 1.0, and multiplies it
into the palette value above. **The average colour of the finished surface is therefore the
locked hex by arithmetic**, and the generated texture can only vary brightness around it —
it can never shift the hue.

The tinting happens when the tile is written, not in the material, because **glTF cannot carry
a shader graph**: it understands one texture times one colour and nothing more. A material that
mixes and desaturates looks right in Blender and exports as something else entirely.

Tiles repeat every **2 metres**, which at 1024 pixels gives 512 texels per metre — twice the
number this document asks for. That is not a violation but a consequence: with tiling, texel
density is set by how often a tile repeats, and repeating more often costs no extra memory at
all. The 256 figure was written for unique per-asset unwraps, where density and atlas size
trade against each other. They do not trade here.

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
| The sun | One real directional light, from the **upper left**, **casting no shadow** | **1** |
| Hero fires — the Chapter 1 fire, the forge, story beats | Real point lights | **≤ 6 on screen** |

**The sun casts no shadow, and that is deliberate.** Clash of Clans casts none either — not
from buildings, not from trees, not from troops. The dark under a building is painted into the
building, which for us is the ambient occlusion bake. Long cast shadows are the fastest way to
make an isometric base look muddy, they double the apparent size of every building, and a
shadow pass is one of the more expensive things a phone does. Measured in
[COC_TEARDOWN.md](reference/COC_TEARDOWN.md).

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
