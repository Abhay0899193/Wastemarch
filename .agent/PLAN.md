# PLAN

## RESUME HERE

**Last session:** 8 August 2026 (session 6). Working tree clean, on `main`.
**Nothing is half-finished. Commits are NOT pushed — the owner pushes.**

**Where we are: Phase 3, with a playable city.**

```bash
$GODOT --path game res://city/City.tscn
```

Pick a building, click to place, right-drag to pan, wheel to zoom, `S` save, `L` load.
Three buildings, each paying for the next.

**First command of the next session** — protocol from `CLAUDE.md` §1, then:

```bash
export GODOT=/Users/singha7/Applications/Godot.app/Contents/MacOS/Godot && \
git log --oneline -10 && git status && \
sh ci/no-floats.sh && \
(cd sim && cargo test --workspace --exclude sim-godot) && \
python3 tools/art/palette_check.py && \
$GODOT --headless --path game --script res://tools/sim_smoke.gd && \
$GODOT --headless --path game --script res://tools/city_smoke.gd
```

Expect **125 Rust tests green**, palette ok, `PASS — the Rust simulation…`, and
`PASS — place, refuse, build, produce, save and load all work`.

**Do not run `cargo test --workspace` without `--exclude sim-godot`** unless `GODOT4_BIN` is
set. **Force a clippy re-lint** with `touch sim/*/src/*.rs` before trusting a green run.

---

## Next 3 actions

1. **Three more buildings**, to get from three to the six Phase 3 asks for. Housing, a farm,
   and a drill yard would exercise the adjacency rules `MASTER_PLAN.md` §Phase 5 wants.
   Each one is a prompt file plus a builder function; the pipeline does the rest.
2. **Upgrade levels in the city.** The models already interpolate level 1→5 and `build_s`,
   `cost` and `produces` are per-level-able in `game/data/buildings.json`. Nothing in the city
   reads a level yet.
3. **Save migrations.** The save carries `version: 1` from the first write. Write the second
   version and the migration before the format has to change under pressure.

## The art question, which is the owner's and not blocking

The owner is **not happy with the buildings** and said so repeatedly. Phase 2's mechanical
gate is met; its "three reference buildings you approve" half is not. Phase 3 can proceed on
these assets and swap them later — nothing about the city depends on how they look.

Three options are on the table, all evidenced rather than argued:

- **More hand-authored geometry.** Budgets have room: keep 1,488 of 4,000, granary 294 of
  1,500, watchtower 558 of 1,500.
- **Squatter buildings.** `HEIGHT_TO_FOOTPRINT_LIMIT` in `build_asset.py` is 1.6; lowering it
  reduces how much each building hides behind it.
- **Sprites.** `$GODOT --path game res://world/SpritePreview.tscn` stands the concept art
  beside the models. The owner judged the sprites clearly better. `MASTER_PLAN.md` §1.3
  argues against them and lists what they cost — day/night, zoom, per-pixel troop occlusion,
  and every upgrade level becoming an app update.

---

## Phase 2 — pipeline complete, art approval outstanding

```bash
python3 tools/pipeline/build.py --all
```

Prompt file and builder function are authored; concept art, geometry, unwrap, texture,
ambient occlusion, emission, glTF, interface icon, engine import and budget check are not.
About ten seconds a building.

- [x] Concept generation with provenance — `tools/pipeline/concept.py`
- [x] Parametric models with validation — `tools/blender/build_asset.py`
- [x] Tiled palette materials, baked to a real unwrap with AO and emission
- [x] Interface icons from the same model as the game art
- [x] Scripted silhouette test, palette check in CI
- [x] The one-command gate
- [ ] **Three reference buildings the owner approves** — owner's call

## Phase 3 — city builder, in progress

- [x] 3D world at the locked camera, pan and zoom
- [x] Grid, placement with snapping, validity and refusal reasons
- [x] Build timers, production, four resource types on the HUD
- [x] Save and load, versioned from the first write
- [x] 22 headless checks — `tools/city_smoke.gd`
- [ ] Six buildings rather than three
- [ ] Upgrade levels
- [ ] Save migrations
- [ ] Durn's build tutorial
- [ ] **Gate:** twenty minutes on a phone that leaves you wanting to continue

---

## The two blockers, both the owner's

| | What | Why it is stuck |
|---|---|---|
| **iOS** | `sudo xcodebuild -runFirstLaunch`, once, by someone with admin | `CoreSimulator.framework` is absent and `xcodebuild` will not start without it. **The paid Developer Program does NOT work around this** — see MEMORY. A *free* Apple ID suffices afterwards. |
| **Android device** | Connect a phone with USB debugging on | Only **performance** now needs it. Correctness is answered by the emulator. `adb devices` lists no physical device. |

**The emulator removed the correctness half of the Android blocker.** What is still hardware-only:
frame rate, draw calls, triangle count, heat and throttling — the Phase 0 budget gate. iOS is
unchanged and still needs the admin password.

---

## Phase 0 — gate NOT met

- [x] Godot project, mobile renderer, landscape, grey cube verified by render
- [x] Export templates, Android toolchain (user-local, no admin), NDK
- [x] Complete signed APK — `sdkVersion:'24'`, arm64-v8a only, real 100MB sim library
- [ ] **Android device** · **iOS admin action** — owner
- [ ] Self-hosted macOS runner; `ios` CI job made real
- [ ] Both devices from a **CI** build
- [ ] On-device: 60 fps, ≤120 draw calls, ≤250k tris

## Phase 1 — GATE MET (ADR-0003)

**Gate:** a headless battle produces an identical state hash on macOS, Linux **and an ARM
device**. The first two agree on every push; the third needs a device.

- [x] `Fx` fixed-point · `Pcg32` · `StateHasher`
- [x] `Grid`, `Entities` (generational ids), `FlowField`
- [x] `Battle` tick loop — targeting, movement, damage, death
- [x] `BattleRecord` + replay, byte encoding, setup fingerprint
- [x] 10,000-seeded-run property test
- [x] Determinism canary — **13 perturbations tried, 11 caught, 2 explained**
- [x] GDExtension: the sim runs inside Godot and agrees with CI
- [x] On-device hash agreement — **Android emulator, `arm64-v8a`, hash matches CI**
- [x] **Gate met** — ADR-0003
- [ ] Re-run on a physical phone when one exists, as part of the Phase 0 hardware pass

### Next 3 actions

1. **Geometry.** The buildings are basic and that is now the accepted state — the owner chose
   consistency over per-asset fidelity to a painting. What is still worth doing inside the
   existing budgets: the watchtower's ladder, railings and bracing are too thin to read, and
   the keep's merlons are plain cubes. keep is 1,104 of 4,000 triangles; granary 162 of 1,500.
2. **Stage 2 for the other two buildings.** `build_granary` is the pattern to follow —
   declare the footprint in tiles, mark detail parts so LOD1 can drop them, validate at build
   time. The keep needs `level` to interpolate between `keep_1002` and `keep_1003`.
   `$BLENDER --background --factory-startup --python tools/blender/build_asset.py -- --asset granary`
3. Add an `aarch64-linux-android` cross-compile check to CI. The first emulator run failed on
   a **stale** `.so`, not a real divergence (see MEMORY) — CI building that target would have
   caught it, and would also stop the library silently regressing to zero bytes again.

### Two art-direction findings that are now rules, not opinions

Both came out of this session and are written into `docs/ART_BIBLE.md`:

- **Lighting is painted, not calculated.** Two hundred lit windows cannot be two hundred
  lights on `forward_mobile`. Emissive textures, plus one directional sun and at most six
  real point lights on screen. This changes how textures are authored, so it had to land
  before generation, not after.
- **The Duskwood treeline is a budget item.** "Always on screen" at 300 tris a conifer is
  60k triangles — a quarter of the scene budget — on background. Instanced low-tri band,
  flat cards for the deep rows.

---

## Frozen numeric contract

See MEMORY, "`sim-core` numeric contract". Golden hash **`0x6de277a1cf08225b`**, duplicated in
`game/tools/sim_checks.gd` on purpose and guarded by a test. Changing it invalidates every
recorded battle — sometimes correct, never incidental, always say so in the commit message.

## Deliberately out of scope

`docs/RELEASE.md` (Phase 7) · eight-way movement (Phase 4, if four-way looks wrong) ·
per-tick allocation in the battle loop (Phase 4, marked `ponytail:` at the site) ·
Homebrew permission fix (not needed). All in `docs/BACKLOG.md`.
