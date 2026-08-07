# WASTEMARCH — Master Build Plan
### End-to-end production brief for Claude Code (Opus 5)

**Owner:** Lt (abhay000singh@gmail.com)
**Date:** 7 August 2026
**Working title:** *Wastemarch* (see §1.6 — do **not** ship as "Clash of Land")
**Primary platform:** iOS + Android. **Secondary:** Steam (macOS/Windows).
**Local tool paths:** `/Users/singha7/Applications` (Godot, Blender)

---

## 0. How to use this document

This is the single source of truth handed to Claude Code. Claude Code should:

1. Read this file **once, fully**, at project start.
2. Immediately generate the repo scaffold in §6 and the docs in §7.
3. From then on, work **only** from `.agent/PLAN.md` + `.agent/MEMORY.md` + `docs/`, which it keeps updated.
4. Never treat this file as editable. If something here turns out wrong, write an ADR (§7.4) explaining the change instead.

Everything below is either **VERIFIED** (checked against current sources, Aug 2026) or **DECISION** (a design call with stated reasoning).

---

# PART I — VERDICT ON THE ORIGINAL PLAN

Your instinct was right on ~70% of it. Five things needed to change. Here is each one, with the reason.

## 1.1 ❌ Drop Flux Kontext. → ✅ Z-Image Turbo + Qwen-Image-Edit 2509

**VERIFIED.** FLUX.1 Kontext [dev] ships under the *FLUX.1 [dev] Non-Commercial License v1.1.1*. The outputs are commercially usable, but the licence restricts **use of the model itself** to non-commercial purposes — running it as the asset factory for a game you intend to monetise is exactly the case that requires a paid commercial licence from Black Forest Labs. You said commercial release with IAP. That makes Kontext a liability sitting at the centre of your pipeline.

**Replacement, both Apache 2.0, both fully commercial-safe, both run in ComfyUI:**

| Role | Model | Licence |
|---|---|---|
| Text→image (concept art, textures, UI, icons) | **Z-Image Turbo** (Tongyi-MAI, 6B) | Apache 2.0 |
| Image→image editing / structure-preserving refinement | **Qwen-Image-Edit-2509** (Alibaba, 20B, GGUF Q4 on your Mac) | Apache 2.0 |

Qwen-Image-Edit-2509 does the exact job you wanted Kontext for — edit an image while preserving structure — and it natively supports ControlNet conditions (depth, sketch, keypoints), which is *better* for our pipeline because we can condition on Blender depth/normal passes.

> Z-Image Turbo already exists locally in your `mentoros` sibling project. Per your instruction, **copy the weights, not the code.** Wastemarch gets its own clean ComfyUI setup.

## 1.2 ❌ Demote Blender MCP from production tool → dev-time toy

**DECISION.** Blender MCP is real and genuinely good at *exploration*: "make me a procedural building facade with 8 floors." It is the wrong tool for a **production pipeline**, because:

- It is a live, stateful, interactive session. Production asset builds must be **reproducible from a clean checkout**.
- Its output isn't versioned. If a model regenerates slightly differently next month, your game's art drifts and you can't diff it.
- It can't run in CI, can't run overnight in batch, can't run on a fresh machine.

**Production rule:** every 3D asset is produced by a **committed Python script** run headless:

```bash
/Users/singha7/Applications/Blender.app/Contents/MacOS/Blender \
  --background --factory-startup \
  --python tools/blender/build_asset.py -- --asset town_hall --level 3
```

Deterministic, diffable, git-tracked, re-runnable. Blender MCP stays installed and is allowed **only** in `tools/blender/scratch/` for figuring out *how* to do something — the answer then gets written into a committed script.

## 1.3 ❌ Pre-rendered isometric sprites → ✅ Real-time 3D under an orthographic isometric camera

This was your biggest question and it deserves the long answer.

**How the industry actually does it:**

- *Clash of Clans* (2012) uses pre-rendered 2D sprites. That was the correct call **for 2012 hardware** and Supercell has been locked into it ever since — it's technical debt they maintain, not a model to copy.
- *Boom Beach*, *SimCity BuildIt*, *Rise of Kingdoms*, *Lords Mobile*, *Township*'s newer content, and essentially every base-builder shipped after ~2016 render **real 3D** through an orthographic or shallow-perspective isometric camera.

**Why 3D wins for you specifically:**

| Concern | Pre-rendered 2D | Real-time 3D |
|---|---|---|
| Adding a building level | Re-render 8 dirs × N frames, rebuild atlas, ship new APK | Swap mesh/material — often a data-only patch |
| App size at scale (20 buildings × 15 levels × skins) | Gigabytes of atlases | Tens of MB of meshes + shared textures |
| Day/night, weather, seasonal events | Impossible without re-rendering everything | Free — it's just lighting |
| Camera zoom / slight rotation (premium feel) | Impossible | Free |
| Troop animation | Rig **and** render 8 directions × every anim | Rig once, export glTF, done |
| Your AI texture pipeline | Applied after render (fragile, breaks structure) | Applied to UV texture maps (stable, correct) |
| Mobile perf on low-end | Slightly better | Fine for stylised low-poly on Godot's Mobile renderer |

The pre-rendered path is *more* work per asset, not less, and it caps your live-ops ceiling permanently. **DECISION: real-time 3D.**

**What survives from your original pipeline:** the Blender→render→atlas step doesn't die, it **moves to UI**. A CoC-style game needs hundreds of crisp 2D icons (building cards, troop portraits, resource icons, shop tiles). Those are batch-rendered headlessly from the *same* 3D assets with a fixed hero camera and packed into atlases. So you get one 3D source of truth and free, always-consistent UI art.

**Revised pipeline:**

```
Claude Code
   ↓ maintains ART_BIBLE.md (the style contract) + writes Blender Python
Z-Image Turbo (ComfyUI)
   ↓ concept sheet: 3 orthographic views + silhouette, per asset
Blender (headless, scripted)
   ↓ low-poly modelling to match concept, UV unwrap, LOD0/LOD1
Z-Image Turbo + Qwen-Image-Edit (ComfyUI)
   ↓ generate + refine albedo/roughness/emissive in UV space
   ↓ conditioned on Blender-baked depth/normal/AO passes
Blender (headless)
   ↓ bake normals from high-poly, pack ORM, validate budgets, export .glb
Godot 4.7 import
   ↓ 3D world, orthographic camera        ← gameplay
Blender (headless, hero camera)
   ↓ batch icon render → atlas             ← UI art
```

## 1.4 ✅ Added: deterministic simulation core in Rust (GDExtension)

You asked for "offline V1, online-ready architecture, PvP in V2 right after." There is exactly one architectural decision that makes that a **backend swap instead of a rewrite**, and this is it.

Combat and the economy tick run inside a **pure Rust crate** with:
- **fixed-point integer maths only** — no `f32`/`f64` anywhere in the sim (floats desync across CPU architectures)
- seeded deterministic RNG (xorshift/PCG, seed is part of the battle record)
- no I/O, no time-of-day, no engine types — inputs in, state out

That crate compiles two ways:
1. **`godot-rust` GDExtension** → the phone runs it as the game.
2. **`cdylib` / native lib** → in V2, the Nakama server runs the *identical binary logic* to re-simulate and validate every battle a client submits.

Same code, same result, on an iPhone and on a Linux server. That's how Supercell does it (their replays are input-recordings re-simulated, not videos) and it's the only honest way to build "offline now, PvP later" without throwing the game away.

**Bonus:** replays cost ~2KB (seed + timestamped taps), not megabytes. Sim runs at 20Hz fixed timestep, rendering interpolates.

## 1.5 ✅ Voice: Kokoro (Apache 2.0) + Chatterbox (MIT)

**VERIFIED.** XTTS-v2 is under the Coqui Public Model License — **non-commercial only**, and Coqui shut down in 2024, so there is no licensing path. Do not use it.

- **Kokoro** (82M, Apache 2.0) — narrator, UI barks, tutorial lines. Tiny, fast, runs anywhere.
- **Chatterbox** (350M, MIT) — the three named characters, where emotional range matters.
- **Never clone a real person's voice.** Generate original synthetic voices only. Log the model + seed + prompt for every line in `assets/audio/voice/MANIFEST.json`.

Scope V1 voice tightly: full VO for the prologue and the three companions' tutorial lines; everything else is text + SFX. Voice is the easiest place to burn a month for little player value.

## 1.6 ⚠️ Legal: rename before you ship

"Clash of Land" is a near-miss on *Clash of Clans* / *Clash Royale* / *Clash Mini*. Supercell enforces the "Clash" mark aggressively and Apple/Google both action trademark complaints by pulling the app, usually without warning. Combined with a matching genre and isometric art style, it's an invitation.

Codename used throughout this plan: **Wastemarch**. Other candidates: *Ashfall Barony*, *Thornmarch*, *The Ninth Holding*, *Bleakhold*, *Warden of the Waste*. Run a USPTO/EUIPO search and a store search before committing, and register the name early.

Also flagged, all VERIFIED for 2026:
- **Google Play requires visible in-app AI-content labels from April 2026.** Add a settings entry: "Art and audio in this game were produced with AI-assisted tools." Cheap, and it's a policy requirement.
- **Apple guideline 5.1.2(i)** only bites if you send *user* data to third-party AI providers at runtime. Our AI is offline, build-time only → not applicable. Keep it that way; don't add a runtime LLM without revisiting this.
- **Google Play Billing Library v7+** is mandatory. Godot's first-party `GodotGooglePlayBilling` plugin (3.3.0, updated July 2026) covers Godot 4.3–4.8. For one codebase across both stores, use **`godot-iap`** (OpenIAP protocol, StoreKit 2 + Play Billing 8, typed GDScript API).

---

# PART II — THE GAME

## 2. Story bible

### 2.1 Premise

You died on Earth. You woke as **Aldric Vareth**, fourth child of the Vareth royal line, ruler of the Kingdom of Ostmere — with every memory of your old life intact.

In this world, nobility is measured by an **Awakened Sigil**: a mark of magical aptitude that surfaces at age ten. Yours never came. For eight years you were the family's quiet embarrassment. On your eighteenth nameday, the King solved the problem elegantly — he did not disown you. He *promoted* you.

You were granted the **Ninth Holding**: a border wasteland no lord has held for a century, the land nobody wants and everyone is glad to be rid of. Sent with you, as a final courtesy, were the two servants the palace was most eager to lose.

They kept your memories. They did not count on what a mind from Earth knows about irrigation, crop rotation, supply lines, standing armies, sanitation, and compound interest.

### 2.2 The Ninth Holding — geography

The holding sits in a bowl of dead ground. Four borders, four pressures:

| Direction | Border | Meaning in gameplay |
|---|---|---|
| **North** | **The Duskwood** — vast dark forest | Primary threat. Beast waves, corrupted things, the source of *Blightwood* and *Duskglass*. Beyond it: the Demon King's territory. Main PvE combat front. |
| **East** | **The Rimefang Mountains** — impassable cold peaks | Beyond them lies **Kharzuun**, a huge dark nation. No conflict — the mountains prevent it. Only occasional traders survive the passes. Late-game rare-goods trickle + a slow-burn narrative thread. |
| **South** | **The Sundered Coast** — ocean | Salt, fish, shipwreck salvage. Later: harbour, trade routes, a naval expansion vector. |
| **West** | **Ostmere's own wastes**, then the kingdom | Your family. Tax collectors, inspectors, envoys. The political front — approval, demands, and eventually leverage. |

Where the Duskwood meets the mountains, in the far north-east, is the **Old Compact** — a ruin from before the wasteland was waste. It holds the answer to why this land died, and it is the season-one endgame.

### 2.3 The three characters

**Aldric Vareth** — the player. No magic. His edge is that he is thinking two centuries ahead of everyone around him. Player voice is dry, practical, unimpressed by ceremony.

**Seraphine Vaull** — maid-butler. Formally a household servant; functionally a war scholar. Ostmere's archives were open to servants because nobody imagined a servant reading them. She has memorised three hundred years of campaign histories and was exiled for correcting a general in public.

*Systems role:* combat advisor. Introduces army composition, troop counters, scouting, camp capacity. Her tutorial lines are strategic, not hand-holding — "You can win this. You cannot win it *and* keep the third wave alive. Choose."

**Durn Brakkelbeard** — dwarf builder. Genuinely the finest city-builder alive; also a chronic slacker who has been fired from four royal projects for missing deadlines. He isn't lazy — he refuses to build anything he considers stupid, and every royal project so far has been stupid.

*Systems role:* build advisor. Introduces layout, adjacency bonuses, upgrade queues, storage. Comic register, occasional total sincerity when the player designs something genuinely elegant.

### 2.4 Emotional arc (Season 1, ~12 hours to endgame)

1. **Arrival** — three people, one broken keep, no walls. First night, something comes out of the treeline.
2. **Foothold** — first harvest, first wall, first survivors arriving from other failed holdings.
3. **Recognition** — Ostmere notices the Ninth Holding is paying taxes. A tax inspector arrives expecting nothing.
4. **Pressure** — the Duskwood pushes back. Named beast lieutenants. Seraphine's real value emerges.
5. **The Old Compact** — why the land died. It was not natural.
6. **Leverage** — the King who cast you aside now needs something from you.

Season 2 (V2) opens the borders → other lords' holdings → PvP raiding, framed as a border-lords' war that Ostmere is too weak to prevent.

## 3. Game design

### 3.1 Core loop

```
BUILD & UPGRADE (city sim — SimCity BuildIt / Township register)
   ↓ produces resources & unlocks
TRAIN ARMY (composition, counters, camp capacity)
   ↓ spend on
RAID / DEFEND (real-time deployment — Clash of Clans register)
   ↓ yields loot + story progress
BUILD & UPGRADE (bigger)
```

Layered on top: **Duskwood pressure**, a rising timer that periodically attacks *your* base. This gives the offline V1 the tension that PvP provides in CoC, and it's a system, not content, so it scales cheaply.

### 3.2 Resources

| Resource | Source | Purpose |
|---|---|---|
| **Grain** | Farms, fisheries | Troop training, population upkeep |
| **Timber** | Duskwood edge camps (risky — increases pressure) | Construction |
| **Stone** | Quarries | Walls, defensive structures |
| **Iron** | Deep mines | Advanced troops, weapon tiers |
| **Duskglass** | Duskwood raids only | Premium upgrade material — the "gem-equivalent", **earnable, never the paywall** |
| **Crowns** | Trade, taxes, coastal salvage | Soft currency, instant-finish, Ostmere politics |

**Monetisation stance (V1 ships free, no IAP live):** the architecture supports IAP from day one but the store is disabled at launch. When it turns on: cosmetic skins, builder-slot (Durn's apprentices), time-skip bundles, battle pass. **No pay-to-win power, no loot boxes.** Loot boxes carry real regulatory exposure in the EU/UK/BE/NL and are not worth it.

### 3.3 Combat design (CoC register, but not a clone)

- Top-down deployment on the enemy base perimeter. Troops auto-path to targets by preference.
- **Deliberate differences from CoC** — needed both creatively and to avoid a clone claim:
  - **Terrain matters.** The Duskwood terrain has mud, rock, and treeline tiles that alter speed and line of sight. Deployment position is a real decision, not just a direction.
  - **Seraphine's Orders** — 3 command cards per battle (Rally, Hold, Feint), on cooldown. A thin real-time skill layer over an otherwise fire-and-forget system.
  - **No spells at launch.** Orders replace them. Cleaner, more legible, and a smaller build.
- Fully deterministic. Every battle produces a `BattleRecord { seed, base_snapshot_hash, Vec<TimedInput> }` that replays exactly.

### 3.4 Base building

- **Grid:** 44×44 tiles, expandable in wedges toward each border.
- **Adjacency bonuses** (this is the SimCity DNA and the thing that makes layout *interesting* rather than just spatial): a Granary beside Farms gives +yield; a Barracks beside a Drill Yard trains faster; Housing beside the Duskwood wall generates Unrest.
- **Two builders at start** (you and Durn), a third earned through the story, a fourth via IAP later.
- **Free redesign mode** — let players rearrange without cost. CoC's friction here is monetisation-driven and modern players hate it.

---

# PART III — TECHNICAL ARCHITECTURE

## 4. Stack

| Layer | Choice | Notes |
|---|---|---|
| Engine | **Godot 4.7.1-stable** | Current stable as of 4 Aug 2026. Pin the exact version in `docs/ENVIRONMENT.md`. |
| Renderer | **Mobile** (`forward_mobile`) | Forward+ is desktop-oriented and behaves badly on tile-based mobile GPUs. Mobile renderer targets Adreno/Mali/Apple GPUs correctly and gives us real-time shadows. |
| iOS graphics | Metal, min **A12 / iOS 15** | Godot 4.5+ defaults to A12+ for Metal. |
| Android | Vulkan, min **API 24**, `arm64-v8a` only | Drop 32-bit. |
| Sim core | **Rust** crate → `godot-rust` GDExtension | Fixed-point, deterministic, no floats. Reused server-side in V2. |
| Game/UI code | **GDScript** | Fast to iterate. Perf-critical work lives in Rust. |
| Save | Local encrypted binary + versioned migrations | Godot `FileAccess.open_encrypted_with_pass`. |
| Cloud save | iCloud KVS / Google Play Games Saves | V1.1. |
| Backend (V2) | **Nakama** (self-host on a €20/mo VPS) | Go server, our Rust sim as a native module for battle validation. Open source, no per-MAU tax. |
| IAP | `godot-iap` (OpenIAP) | One GDScript API, StoreKit 2 + Play Billing 8. Stubbed and disabled in V1. |
| Analytics | Self-hosted **PostHog** or **Aptabase** | GDPR-clean, no Firebase, no ad SDKs. |
| Crash | **Sentry** (godot-sentry) | |
| CI | GitHub Actions, self-hosted macOS runner (your Mac) | iOS builds require macOS. |

**Explicit non-goals for V1:** no ads, no ad SDK, no social login, no runtime LLM, no chat, no UGC. Every one of those is a compliance surface.

## 5. Godot project structure & perf rules

```
game/
├── project.godot                # renderer=mobile, 1080x1920 base, canvas_items stretch
├── core/                        # autoloads: EventBus, SaveManager, Audio, Localization
├── sim/                         # thin GDScript bridge to the Rust GDExtension
├── world/
│   ├── WorldRoot.tscn           # 3D scene, orthographic Camera3D
│   ├── grid/                    # GridMap terrain + placement logic
│   └── buildings/               # one scene per building, LOD via VisibilityRange
├── battle/
│   ├── BattleRoot.tscn
│   └── replay/
├── ui/
│   ├── theme/                   # single Theme resource — all UI derives from it
│   └── screens/
├── data/                        # ALL balance in .tres / .json — zero magic numbers in code
└── assets/
    ├── models/   (.glb)
    ├── textures/ (.ktx2, ASTC-compressed)
    ├── atlases/  (UI)
    └── audio/
```

**Non-negotiable performance rules** (Claude Code must enforce these in code review of its own output):

1. **60 FPS on iPhone 12 / Pixel 6a.** Budget: ≤120 draw calls, ≤250k tris on screen.
2. **`MultiMeshInstance3D` for repeated props** — walls, trees, crops, decoration. Never 400 individual nodes.
3. **One shared material per art tier.** Buildings share a single atlas-based material so Godot batches them.
4. **Textures: KTX2 + ASTC.** No PNG in the shipped build. `.import` presets committed.
5. **Baked lighting for static geometry**, one real-time DirectionalLight3D with a single shadow cascade.
6. **Object pooling for troops.** Zero allocation during a battle.
7. **Sim at fixed 20Hz** in `_physics_process`; visuals interpolate. Rendering never influences sim state.
8. **Test on device every phase.** The simulator lies about performance.

## 6. Repository layout

```
wastemarch/
├── CLAUDE.md                  ← Claude Code's operating rules (see companion file)
├── README.md                  ← plain-language: what this is, how to run it
├── .agent/                    ← Claude's own working memory (git-tracked)
│   ├── MEMORY.md              ← durable facts, decisions, gotchas
│   ├── PLAN.md                ← current phase, task list, next 3 actions
│   ├── JOURNAL.md             ← append-only session log
│   └── STATE.json             ← machine-readable: phase, milestone, versions, build hashes
├── docs/                      ← for humans. Simple language. No jargon.
│   ├── README.md              ← index — start here
│   ├── ARCHITECTURE.md
│   ├── GAME_DESIGN.md
│   ├── ART_BIBLE.md
│   ├── ASSET_PIPELINE.md
│   ├── ROADMAP.md
│   ├── ENVIRONMENT.md         ← exact tool versions + local paths
│   ├── TESTING.md
│   ├── RELEASE.md
│   └── decisions/ADR-0001-*.md
├── game/                      ← Godot project
├── sim/                       ← Rust deterministic core (cargo workspace)
│   ├── sim-core/              ← pure, no deps on Godot
│   ├── sim-godot/             ← GDExtension binding
│   └── sim-server/            ← V2 native lib for Nakama
├── tools/
│   ├── blender/               ← headless build scripts (production)
│   │   └── scratch/           ← Blender-MCP experiments only, never shipped
│   ├── comfy/                 ← ComfyUI workflow JSONs + batch runner
│   ├── voice/                 ← Kokoro/Chatterbox generation + manifest
│   └── pipeline/              ← orchestrator: asset manifest → built assets
├── assets-src/                ← concept art, hi-poly, .blend sources (Git LFS)
└── ci/
```

**Git LFS** for `*.blend *.png *.ktx2 *.glb *.wav *.ogg`. Set this up in the very first commit — retrofitting LFS is miserable.

---

# PART IV — THE ASSET PIPELINE

## 7. Pipeline design

### 7.1 The Art Bible is the contract

`docs/ART_BIBLE.md` is written **before any asset is made** and is the prompt-truth for every generation. It specifies, concretely:

- **Palette:** locked hex values. Wasteland ochres and bone-greys; Duskwood deep teal-blacks; Ostmere heraldic crimson + gold. Max 5 hues per asset.
- **Silhouette rule:** every building must be identifiable in pure black at 64px. Test this — script it.
- **Poly budgets:** small building ≤1.5k tris, large ≤4k, troop ≤900, LOD1 at 40%.
- **Texel density:** 256px per world-metre, uniform. This is what makes an AI-assisted art set look *made by one team* rather than scraped together.
- **Materials:** stylised PBR, roughness ≥0.35 (no mirror surfaces — they read as cheap on mobile), gentle rim light baked into the shader.
- **Camera:** orthographic, 30° elevation, 45° yaw, fixed. All concept art must be generated at this angle.
- **A canonical reference sheet** — 3 finished buildings rendered at the game camera, committed as `docs/art/reference/`. Every new asset is visually diffed against these.

### 7.2 Asset manifest drives everything

`tools/pipeline/manifest.yaml` lists every asset with its target state:

```yaml
- id: town_hall
  kind: building
  levels: [1, 2, 3, 4, 5]
  footprint: [4, 4]
  concept_prompt_ref: prompts/buildings/town_hall.md
  poly_budget: 4000
  status: modelled        # concept → modelled → textured → exported → in_game
```

The orchestrator (`tools/pipeline/run.py`) reads the manifest, works out what's stale, and runs only what's needed. Every stage writes a hash so nothing rebuilds without cause.

### 7.3 Stage by stage

**Stage 1 — Concept (ComfyUI / Z-Image Turbo).**
Per asset: generate a 4-panel sheet — front ortho, side ortho, 3/4 at the game camera angle, and a black silhouette. Prompt is assembled from the Art Bible header + the asset's prompt file. Seed recorded. Human picks one; picks are committed to `assets-src/concept/`.

**Stage 2 — Model (Blender headless).**
A committed Python script builds the mesh procedurally where possible (walls, towers, roofs, crop rows are all parametric — a script that makes a "keep" at 5 levels is far better than 5 hand-models), UV unwraps with `smart_project` at fixed texel density, generates LOD1 by decimation, and asserts the poly budget. **Fails the build if over budget.**

**Stage 3 — Texture (ComfyUI, UV space).**
Blender bakes depth/normal/AO/position passes from the model. ComfyUI runs Z-Image Turbo → Qwen-Image-Edit-2509 conditioned on those passes via ControlNet, producing albedo in UV space that respects the actual geometry. Roughness/metallic derived, packed to ORM. This is the step where Kontext was going to sit; Qwen does it better because it can see the geometry.

**Stage 4 — Export (Blender headless).**
Bake hi→lo normals, pack ORM, apply the shared material, export `.glb` with LODs, write `.import` presets for ASTC. Validate: no n-gons, no loose verts, correct scale (1 unit = 1 metre), origin at footprint centre.

**Stage 5 — UI icons (Blender headless).**
Same `.glb`, hero camera, transparent background, 256×256, batch-rendered → packed into atlases by a committed Python packer. Your original render-and-atlas pipeline, in the place where it actually pays off.

**Stage 6 — Godot import + smoke test.**
Godot headless imports and runs a validation scene that places every asset, screenshots it, and checks draw calls and tri counts against budget.

```bash
/Users/singha7/Applications/Godot.app/Contents/MacOS/Godot \
  --headless --path game --script res://tools/validate_assets.gd
```

### 7.4 Running this on an M4 Pro / 24 GB — realistic expectations

**VERIFIED constraint.** 24 GB unified memory is workable but tight, and ComfyUI on macOS MPS is meaningfully slower than CUDA.

- **Z-Image Turbo (6B, fp8):** comfortable. Roughly seconds-to-a-minute per 1024px image. This is your workhorse — use it for 90% of generations.
- **Qwen-Image-Edit-2509 (20B):** must use **GGUF Q4_K_M**. Expect single-digit minutes per image and close everything else first. Use it surgically, not in bulk.
- **Practical rhythm:** Claude Code queues a batch during the day; you run it overnight. `tools/comfy/batch.py` must be resumable and write per-item results so a crash at item 40 doesn't cost items 1–39.
- **Escape hatch:** if a big texture pass would take more than one night, rent an A100 on RunPod for a few hours (~$2/hr). Keep `tools/comfy/` portable — same workflow JSONs, env var for the ComfyUI endpoint — so this is a config change, not a rewrite.
- **Blender:** Cycles with Metal, or EEVEE Next for icon batches. Fine on this machine.
- **Memory hygiene:** never run ComfyUI and a Blender Cycles render at once on 24 GB. The orchestrator must serialise GPU stages.

---

# PART V — EXECUTION

## 8. Session continuity protocol

This is the part you specifically asked for, and it's what makes a months-long Claude Code project survivable.

### 8.1 Files

| File | Audience | Content |
|---|---|---|
| `.agent/STATE.json` | machine | `{phase, milestone, last_commit, godot_version, blender_version, open_blockers[]}` |
| `.agent/PLAN.md` | Claude | Current phase goal, the task list with checkboxes, **"Next 3 actions"** at the very top |
| `.agent/MEMORY.md` | Claude | Durable facts: decisions made and why, gotchas hit, paths, credentials locations (never secrets), things that failed and must not be retried |
| `.agent/JOURNAL.md` | Claude | Append-only. One dated block per session: what was done, what broke, what's next |
| `docs/*` | **you, in plain English** | No jargon. A non-programmer should understand what the game is and how the project is organised. |

### 8.2 Session start (every single time)

```
1. Read .agent/STATE.json
2. Read .agent/PLAN.md  → the "Next 3 actions" block
3. Read .agent/MEMORY.md
4. Read the last 2 entries of .agent/JOURNAL.md
5. git log --oneline -10  and  git status
6. State in one paragraph: "We are in Phase X, milestone Y. Last session did Z. I'm now doing A."
7. Work.
```

### 8.3 Milestone close (every ~45–90 minutes of work, not just at session end)

```
1. Run the test suite + the asset validator
2. Update .agent/PLAN.md (tick items, rewrite "Next 3 actions")
3. Update .agent/MEMORY.md if anything durable was learned
4. Append to .agent/JOURNAL.md
5. Update .agent/STATE.json
6. Update any affected docs/ file
7. git add -A && git commit -m "phase(N): <what changed>"
8. Report to the user in 3 lines max
```

### 8.4 Session close (mandatory, no exceptions)

```
1. Do the full milestone-close sequence above
2. Verify: git status is clean. If it isn't, commit the rest as "wip: <description>"
3. Write a "RESUME HERE" block at the top of .agent/PLAN.md containing:
   - exact next command to run
   - what state the working tree should be in
   - anything half-finished
4. Push
```

**Hard rule for Claude Code: never end a session with uncommitted work.** A dirty tree at session end has destroyed more solo projects than any bug.

### 8.5 Docs writing standard

`docs/` is for you, not for engineers. Rules Claude Code must follow:

- Short sentences. Explain any term the first time it appears.
- Every doc opens with a 3-sentence "What this is" block.
- Diagrams as Mermaid, so they render on GitHub.
- `docs/README.md` is an index with a one-line description of each doc.
- If a doc goes stale relative to the code, that's a bug — fix it in the same commit.

## 9. Roadmap

### Phase 0 — Foundation (week 1)
Repo, Git LFS, `CLAUDE.md`, `docs/` scaffold, `.agent/` scaffold, `ENVIRONMENT.md` with verified local tool paths and versions, GitHub Actions skeleton, empty Godot 4.7.1 project that builds and runs on your iPhone and an Android device.
**Done when:** a grey cube renders on both physical devices from a CI-produced build.

### Phase 1 — Deterministic sim core (weeks 2–3)
Rust `sim-core`: fixed-point maths, seeded RNG, entities, grid, pathfinding (flow-field), targeting, damage. Property tests asserting identical output across 10,000 seeded runs. `godot-rust` GDExtension. Cross-platform determinism test in CI (macOS + Linux + arm64 must agree bit-for-bit).
**Done when:** a headless battle produces an identical state hash on macOS, Linux, and an ARM device.

### Phase 2 — Art bible + pipeline (weeks 3–5, parallel with 1)
ComfyUI installed clean, Z-Image Turbo + Qwen-Image-Edit-2509 weights in place (copied from `mentoros`, no code reuse). `ART_BIBLE.md` written and validated by producing **three** finished reference buildings end-to-end through every stage. Orchestrator, manifest, hashing, resumable batch runner.
**Done when:** `python tools/pipeline/run.py --asset town_hall` goes from prompt to in-Godot `.glb` + UI icon, unattended.

### Phase 3 — City builder vertical slice (weeks 5–8)
3D world, orthographic camera, pan/pinch-zoom, grid placement with snapping and validity, build/upgrade timers, 4 resource types, 6 buildings, save/load with migrations, Durn's build tutorial.
**Done when:** you can play 20 minutes on your phone and want to keep going.

### Phase 4 — Combat vertical slice (weeks 8–11)
Battle scene over the sim core, deployment UI, 4 troop types with counters, defensive structures, Seraphine's Orders, damage/destruction VFX, battle results, replay playback from `BattleRecord`.
**Done when:** a battle replays frame-identically from its record, twice.

### Phase 5 — Content + economy (weeks 11–16)
Full building set (~24 across 5 levels), 8 troop types, Duskwood pressure system, adjacency bonuses, progression curve tuned against a spreadsheet model, enemy base generator for PvE raids.
**Done when:** the balance sim shows a clean 12-hour progression with no dead-time walls.

### Phase 6 — Story + polish (weeks 16–20)
Prologue, 6 story chapters, character portraits, VO (Kokoro + Chatterbox), music, full UI theme pass, juice: camera shake, particles, squash-stretch, satisfying build-complete moments. **This phase is where "premium" is won or lost — budget it properly and do not compress it.**
**Done when:** a stranger playing it says it looks like a real game.

### Phase 7 — Hardening (weeks 20–23)
Localisation scaffolding (EN + 4), accessibility (text scale, colourblind-safe palette, reduced motion), device matrix testing including a low-end Android, memory/battery profiling, save-corruption recovery, Sentry, analytics, AI-content disclosure screen, privacy policy, store listings, IAP stubbed and disabled.
**Done when:** the release checklist in `docs/RELEASE.md` is fully green.

### Phase 8 — Soft launch (weeks 23–26)
TestFlight + Play Internal Test → closed beta in 2 small markets. Instrument D1/D7 retention and progression funnels. Fix the top 5 drop-off points. Then global.

### Phase 9 — V2: online (post-launch)
Nakama self-hosted. Accounts, base snapshots, matchmaking, server-side battle validation using `sim-server` (the same Rust crate), clans, leaderboards, seasons. Enable IAP. Because the sim was deterministic from Phase 1, this is additive work, not surgery.

**Realistic total to global launch: 6–7 months of consistent work.** Anyone promising less is selling something.

## 10. Risk register

| Risk | Severity | Mitigation |
|---|---|---|
| Art looks AI-generated and inconsistent | **Critical** — kills the "premium" goal outright | Art Bible written first; three human-approved reference assets before any bulk generation; every asset visually diffed against them; a human (you) approves every concept pick |
| Trademark action over the name | **High** — instant delisting | Rename before any public listing; trademark search in Phase 0 |
| Non-determinism creeps into the sim | **High** — poisons V2 | Zero floats in `sim-core`, enforced by a CI lint; cross-platform hash test in CI from Phase 1 |
| Scope creep | **High** — the #1 killer of solo projects | Phase gates with explicit "done when" criteria; anything new goes in `docs/BACKLOG.md`, never into the current phase |
| 24 GB memory ceiling on texture batches | Medium | Q4 GGUF, serialised GPU stages, resumable batches, RunPod escape hatch |
| Godot mobile perf on low-end Android | Medium | Mobile renderer + MultiMesh + budgets enforced by the validator from Phase 2; test on a cheap real device every phase |
| Losing project context between sessions | Medium | The `.agent/` protocol in §8, enforced ruthlessly |
| Burnout | **High, and underrated** | Ship a playable thing at every phase. Phase 3's "done when" is deliberately *"you want to keep playing"* — that's the fuel for the other 5 months |

---

## 11. Bootstrap prompt for Claude Code

Open Claude Code in an empty directory and paste this:

> You are building **Wastemarch**, a mobile isometric base-builder + strategy game, in Godot 4.7.1 with a Rust deterministic simulation core, targeting iOS and Android. Read `MASTER_PLAN.md` and `CLAUDE.md` in this directory in full before doing anything else.
>
> My local tools are at `/Users/singha7/Applications` — verify the exact Godot and Blender binary paths and versions and record them in `docs/ENVIRONMENT.md`.
>
> Start with **Phase 0**. Before writing any code:
> 1. Create the full repo scaffold from §6 of the master plan, including Git LFS.
> 2. Create `.agent/MEMORY.md`, `.agent/PLAN.md`, `.agent/JOURNAL.md`, `.agent/STATE.json` and populate them.
> 3. Create the `docs/` set, written in plain English a non-programmer can follow.
> 4. Make the first commit.
>
> Then follow the session protocol in §8 for the rest of the project. Commit at every milestone. Never end a session with a dirty working tree. Ask me before any decision that isn't already settled by the master plan.

---

*Master plan v1.0 — 7 August 2026. Amend only via ADRs in `docs/decisions/`.*