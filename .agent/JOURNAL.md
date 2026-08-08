# JOURNAL

Append-only. Newest entry at the bottom. One block per session.

---

## 2026-08-08 — Session 1 — Phase 0 foundation

**Starting state:** one commit (`37683e0 "first"`) containing three markdown files —
`claude.md`, `Master plan.md`, `Story.md`. No code, no LFS, no docs, no CI. Remote already
existed at `git@github.com:Abhay0899193/Wastemarch.git`.

### Environment verified before anything else

- Godot `4.7.1.stable.official.a13da4feb` — matches target exactly. ~~Export templates for
  `4.7.1.stable` already installed.~~ **Wrong — corrected under M2 below: web templates
  only.** Left visible rather than deleted, because the mistake was assuming a directory's
  existence meant its contents.
- Blender `5.2.0 LTS` (2026-07-14). Master plan does not pin Blender; recorded as-is.
  **Not 4.x** — this matters for Phase 2 scripting.
- Rust 1.95.0, `aarch64-apple-darwin` only. Xcode 26.3. Python 3.14.1. Git 2.41.0.
- Missing: `git-lfs`, Android SDK, Java, `gh`.

### Decisions taken with the owner

1. **Landscape 1920×1080**, overriding the master plan's literal 1080×1920 → ADR-0002.
2. **iOS first.** Android SDK deferred; owner installs manually and reports back.
3. Repo and remote already existed, so no `gh` install was needed.

### What happened

**M0 — `faa5cb3`.** `brew install git-lfs` failed: `/usr/local/bin` is root-owned so
Homebrew cannot create its symlink. Rather than block on a `sudo` the owner would have to
type, installed git-lfs 3.7.1 from the official GitHub release into `~/.local/bin`
(user-owned, already first on PATH), SHA-256 verified against the published hash
`76260fb3…c94b2`. `git lfs install` succeeded.

Wrote `.gitattributes` (the six patterns from `MASTER_PLAN.md` §6 plus jpg/exr/tga/psd/
gltf/fbx/mp3/safetensors/gguf, with `.tscn`/`.tres`/`.gd` explicitly kept as text so they
stay diffable) and `.gitignore`.

Renamed to canonical names. `claude.md` → `CLAUDE.md` needed the two-step `git mv` — a
case-only rename silently no-ops on macOS's case-insensitive filesystem and would have left
the repo lowercase on GitHub's Linux checkout, breaking every `CLAUDE.md` reference. Now in
MEMORY.md.

Verified: `git check-attr filter -- assets-src/keep.blend` → `lfs`;
`game/data/buildings.tres` → `unspecified`. Correct both ways.

**M1.** `.agent/` — MEMORY, PLAN (with RESUME HERE), JOURNAL, STATE. `docs/` — README,
ARCHITECTURE, ENVIRONMENT, ROADMAP, GAME_DESIGN, ART_BIBLE, ASSET_PIPELINE, TESTING,
BACKLOG, and two ADRs. `Story.md` moved to `docs/STORY.md` and linked from the index.

Two deliberate partials, both flagged in the documents themselves rather than left silent:

- **`ART_BIBLE.md` ships without a locked colour palette.** Every rule the master plan
  settles is written and binding — camera, budgets, texel density, silhouette test,
  materials. The nine hex values are marked as needing the owner's sign-off. Inventing them
  alone would be the wrong call on the one risk the register calls *critical*, and locking
  them wrong is expensive after bulk generation starts.
- **`RELEASE.md` skipped.** It is Phase 7 content and would be an empty file for five
  months. In BACKLOG with a reconsider-when.

**M2 — `85c7502`.** Godot project. `project.godot` with `forward_mobile`, 1920×1080
landscape, `canvas_items`/`expand` stretch, ETC2-ASTC compression. Directory skeleton per
`MASTER_PLAN.md` §5. `WorldRoot.tscn` = orthographic camera at 30°/45°, one
DirectionalLight3D with a single shadow cascade, ground plane, grey cube.

Two things went wrong here and both are now in MEMORY:

1. **The scene rendered an empty frame.** I hand-wrote the camera basis as a
   `Transform3D(...)` literal listing *columns*. Godot's 12-float literal fills **rows**, so
   it got the transpose — the inverse rotation — and the camera pointed away from the world
   with no error of any kind. Diagnosed with `cam.unproject_position(Vector3.ZERO)`, which
   returned `(107.8, 1537.9)` in a 1920×1080 viewport. Rewrote as `position` +
   `rotation_degrees`; origin now unprojects to `(960, 540)`, dead centre. Screenshot
   confirms the cube, the ortho projection and the shadow.
   **The lesson is not "I made an arithmetic slip", it is that a wrong camera in Godot fails
   silently.** Verify framing by unprojection, never by reading the maths.

2. **Correction to my own environment survey.** I reported the 4.7.1 export templates as
   installed because the version directory exists. It contains **only the eight `web_*.zip`
   files** — no `ios.zip`, no Android templates. Both phone exports fail at step one. This is
   a hard blocker on the Phase 0 gate and I had it wrong for most of the session. Corrected
   in ENVIRONMENT.md, MEMORY.md, STATE.json and PLAN.md.
   Android additionally fails on the missing SDK, as expected.

`export_presets.cfg` written for both platforms and confirmed parsed by Godot (it lists
"iOS" and "Android"). Committed rather than gitignored — reasoning in MEMORY.

`tools/capture.gd` renders a scene to PNG. It needs a real rendering device, so it must not
be run with `--headless`. Phase 2 grows it into `validate_assets.gd`.

**M3 — `ccd6f28`.** Cargo workspace. `sim-core` with zero dependencies and the three
constants everything else will build on (`TICKS_PER_SECOND = 20`, `FIXED_POINT_BITS = 12`,
`FIXED_ONE = 4096`); `sim-godot` and `sim-server` as stubs that genuinely depend on
`sim-core`, so the dependency edges are exercised by CI from the first commit rather than
asserted in a comment. `rust-toolchain.toml` pins 1.95.0. Release profile sets
`codegen-units = 1` and `overflow-checks = true` — determinism is worth more than the last
few percent of speed.

**`ci/no-floats.sh` proven, not assumed.** Planted `pub const BAD: f32 = 1.0;` in
`sim-core/src/lib.rs`, ran the script: exit 1 with the offending line and file:line. Removed
it: exit 0. A check that has never been observed to fail is not a check. Recorded in
TESTING.md too.

CI: `sim` (float lint first, then fmt, clippy `-D warnings`, test) and `godot` (fetch 4.7.1
headless, import, run 5 frames, fail on any `ERROR:`) on ubuntu. `ios` is an honest stub on
`workflow_dispatch` — a real iOS build needs signing material that cannot live on a hosted
runner. Dropped the `setup-rust` action so `rust-toolchain.toml` is the only place the
version lives; added `set -euo pipefail` to the Godot steps so a crash inside a `tee`
pipeline cannot pass silently.

### End-of-session verification — all green

LFS routes `.blend` → lfs and `.tres` → text · `no-floats.sh` OK · 4/4 cargo tests · clippy
clean · fmt clean · Godot imports with 0 errors · main scene runs 5 frames.

### Phase 0 is NOT complete

Gate is "grey cube on a physical iPhone and a physical Android device from a CI-produced
build". The cube renders on the Mac. No phone build has been attempted because the export
templates are absent. Blockers and next actions in PLAN.md.

### Judgement calls worth flagging

- `ART_BIBLE.md` ships with the palette deliberately unlocked. Every rule the master plan
  settles is written and binding; the nine hex values need the owner. Inventing them alone
  would be the wrong call on the one risk the register calls *critical*, and it is expensive
  to reverse once bulk generation starts.
- Skipped `docs/RELEASE.md` — Phase 7 content, would be an empty file for five months.
- Did **not** download the ~1 GB export templates unprompted. Flagged to the owner instead;
  they may prefer the editor's template manager, which handles mirrors.

---

## 2026-08-08 — Session 2 — Phase 1 foundations

**Context.** Owner asked for Phase 1 to start while they install the Godot export templates.
Phase 0's gate is still open, so I flagged it and started only the part of Phase 1 that the
gate cannot affect: `sim-core` is pure Rust with no Godot dependency and its own gate is
tested in CI on Linux and macOS. **The `godot-rust` GDExtension is deliberately still not
started** — it needs the export templates and a device, which is exactly what the gate
guards. Gate still doing its job on the part it actually protects.

**Godot rewrote `game/project.godot`** when the owner opened the editor. Every load-bearing
setting survived; my comment header did not, and `renderer/rendering_method.mobile` was
dropped as redundant. Comments in that file are futile — noted in MEMORY with the checklist
of settings to re-verify after any editor session.

### M4 — fixed-point arithmetic

`fx.rs`. `Fx(i32)`, 12 fractional bits. Add/sub/mul/div/neg/abs/sqrt/min/max/clamp,
floor/round conversion, `from_ratio` for const balance values, `Display` producing four
decimals **without floating point** (the lint scans test code too, so the whole file has to
obey the rule it enforces).

Two decisions I want a future session to not "simplify":

- **`narrow()` panics on overflow in every profile, not `debug_assert`.** Truncation is
  deterministic *and wrong*. Deterministic-and-wrong is precisely the failure mode this crate
  exists to prevent; a panic is a bug report, a wrapped value is an unreproducible desync.
- **`mul` and `div` round by the same rule** (half toward +inf). Rust's `/` truncates toward
  zero, so `round_div` normalises a negative divisor first. Mixed rounding between two
  operations is the kind of asymmetry that produces a desync nobody can find.

21 tests. The one that matters most is `multiplication_is_commutative` — not a given for
fixed-point, and required because unit A hitting unit B must compute the same number as B
hitting A.

### M5 — PCG, state hashing, determinism canary

`rng.rs` — PCG32, reference constants. `below()` rejects the biasing draws rather than using
a plain modulo; the rejection loop is deterministic because the same seed rejects the same
draws in the same order. Streams supported so independent subsystems cannot shift each
other's results by adding a draw.

`hash.rs` — FNV-1a 64, hand-written, verified against the published vectors. **I initially
wrote the `"foobar"` vector from memory and it was the FNV-1 value, not FNV-1a.** Caught by
computing all four independently in Python before trusting them. Do not recall constants;
compute them.

Deliberately **not** `std::hash::DefaultHasher` — it is explicitly not stable across releases
or platforms, so it would pass every local test and then disagree between phone and server.
That is the precise failure this hash exists to detect.

`determinism.rs` — a fixed 1,200-tick workload reduced to one `u64`, with the value recorded
as a constant. CI matrix now runs `sim` on **ubuntu-latest and macos-latest** with
`fail-fast: false`, so a platform disagreement shows as one red and one green.

### The canary had a real hole, and only failure-testing found it

Proved the check the same way as the float lint — by breaking things. First perturbation,
`HALF` 2048 → 2047 (a direct change to the rounding threshold), **passed**. The workload drew
pseudo-random operands, and random operands essentially never land on exactly one half, which
is the only case that change affects.

Added `hash_rounding_boundaries`: explicit exact-tie cases for mul, div, round/floor
conversion, and sqrt either side of a perfect square. Recomputed the golden hash. Re-ran all
five perturbations — shifted rounding threshold, mul truncating, div rounding toward zero,
PCG multiplier off by 2, sqrt off by one — **all five caught**.

**The general lesson, now in MEMORY:** a canary is only sensitive to what its inputs actually
exercise. Random inputs cover the common path and systematically miss boundaries, which is
exactly where two implementations diverge. Always add explicit boundary cases, and never
trust a check you have not watched fail.

### Verification

46 tests green · clippy `-D warnings` clean · fmt clean · float lint OK · determinism canary
proven against five distinct perturbations · CI YAML validated.

### State

Phase 1 foundations done. Phase 0 gate still open. Next: entities and the grid can proceed
without the gate; the GDExtension cannot.

---

## 2026-08-08 — Session 3 — Android toolchain + Phase 1 core

**Context.** Owner has no admin rights, so iOS is blocked. They asked me to install Android
in-shell and keep building, testing in Godot meanwhile.

### iOS — investigated to a definitive answer

Xcode 26.3 and iOS SDK 26.2 are present. `/Library/Developer/PrivateFrameworks/`
`CoreDevice` and `CoreSimulator` are **not**, and only an admin can install them.
`CoreSimulator` is required by **`xcodebuild` itself** — it refuses to start even for a
device-only unsigned build. So there is no iOS build of any kind.

**Recorded loudly because it is the obvious wrong turn:** the paid Developer Program does NOT
route around this. TestFlight installs over the air, but producing the `.ipa` still needs
`xcodebuild`. Fix is `sudo xcodebuild -runFirstLaunch`, once. Then a *free* Apple ID suffices.

Proven working without admin: Godot generates the full iOS Xcode project, device and
simulator xcframeworks, MoltenVK and the PCK. It stopped only on missing app icons.

### Android — done, no admin

JDK 21.0.12 and SDK under `$HOME`. Homebrew is unusable here (casks write to root-owned
`/usr/local`). Keystore generated, Godot editor settings corrected — its defaults pointed at
a non-existent SDK path and keystore.

**The APK was silently broken and the export said success.** `lib/arm64-v8a/libsim_godot.so`
was **0 bytes**, because sim-godot had never been cross-compiled. Two causes: no NDK, and
`rustup target add` had been run outside `sim/`, attaching the target to the *default*
toolchain while cargo inside `sim/` uses the 1.95.0 pinned by `rust-toolchain.toml` — giving
a baffling "can't find crate for std" for a target rustup listed as installed.

Now: 123MB signed APK, `sdkVersion:'24'`, arm64-v8a only, a real 100,676,016-byte sim
library. **Verify by size, never by presence.**

Added `icon.svg` — SVG not PNG, so it stays diffable and out of LFS. Cleared the last Android
warning and the error that also stopped the iOS export.

### GDExtension — the sim now runs inside Godot

Previously deferred as "needs export templates and a device". That was true for *shipping*
and wrong for the *editor*. gdext 0.5.4 predates Godot 4.7.1, so `api-custom` generates
bindings from the actual binary; Godot confirms the match at load. `sim-godot` uses `deny`
rather than `forbid` for unsafe, with the entry point quarantined in its own module.

`game/tools/sim_smoke.gd` checks the boundary neither side's own tests cover. Its hash
constant is duplicated from Rust **deliberately** — reading it from the library would let a
stale build agree with itself — so a Rust test now reads the `.gd` file to stop the
duplication rotting.

### Phase 1 — grid, entities, pathfinding

Grid: `Tile` and `Point` as distinct types. Out-of-bounds reads as Rock, writes ignored not
wrapped. Move costs are integers because they are summed over long paths.

Entities: generational ids. Without them a dead archer's reused slot means stale references
silently attack the wrong unit. No `HashMap` anywhere — Rust randomises iteration order.

Pathfinding: flow field, Dijkstra from the goals. Goals seeded even when impassable so troops
route *beside* a building. Queue keyed on `(cost, tile index)` never cost alone; ties resolve
by fixed neighbour order via strict `<`.

### The canary, extended three times and perturbation-tested each time

Nine distinct perturbations caught across the session. The pathfinding four are the most
valuable — that is the only code with a priority queue, and a queue is exactly where a
cross-platform tie-ordering difference would hide.

Golden hash is now `0x60d0b217ca281e07`. It changed three times today; each change is in a
commit message saying so.

### State

92 tests. Two blockers left, both hardware/permission: an admin password for iOS, and a
physical Android device. Nothing else is waiting on anything.

---

## 2026-08-08 — Session 4 — Phase 1 complete except the device

### CI went red and it was my own gap

Adding gdext broke **both** `sim` matrix legs. The signature is the useful part: this matrix
exists to detect cross-platform divergence, which shows as **one leg red and one green**.
Both red is a build problem. Cause: `sim-godot` needs `GODOT4_BIN` at build time and
`sim/.cargo/config.toml` hard-codes a macOS path no runner has. Clippy runs before tests, so
it died there and the tests never ran.

Split into a separate `sim-godot` job that downloads Godot. Also learned that local
`cargo clippy` does not re-lint unchanged crates — `touch` the sources or a clean CI run
fails where local passes. That lesson paid off within the hour: it caught two malformed hex
literals later the same session.

### The tick loop

Five phases in fixed order. Combat stats live on the entity and come from the caller, never
as constants — `sim-core` does no I/O, so it defines the shape and `game/data/` fills it.

**A perturbation proved my own design was decoration.** The damage phase gathered blows and
applied them afterwards, documented as producing simultaneity. Reordering it did not fail the
canary — because attackers are never alive-checked, so deferred and immediate are identical.
It was dead code allocating a `Vec` per tick against `MASTER_PLAN.md` §5. Removed; **the
golden hash did not move**, which is the proof. Simultaneity comes from the *absence* of an
alive check, now documented and pinned by two tests instead of being an accident.

Thirteen perturbations across sessions: **eleven caught, two missed**, both misses explained
in MEMORY rather than glossed.

My own overflow guard caught me too — a test gave a wall 1,000,000 health against an `Fx`
ceiling near 524,288, and `narrow()` panicked. Exactly the design working.

### Battle records

1015 bytes for a busy three-minute battle. `MASTER_PLAN.md` §1.4 says "roughly two
kilobytes" — now measured, not believed.

The setup fingerprint is the load-bearing part: a record replayed against a different board
silently produces a different battle. Grid, roster and starting layout are hashed and checked
before replay. Changing one balance number refuses the record.

Encoding is explicitly little-endian with a magic number and version, and the input count is
validated against buffer length **before** allocating so a corrupt count cannot request a
huge allocation.

### The 10,000-seed sweep, and a measurement worth having

157 seconds in debug, **6 seconds in release** — the difference is overflow checks. So a
1,000-seed version runs everywhere as the early warning, and CI runs the full sweep in
release on the **Linux leg only**: GitHub bills macOS runners at ten times the rate, and the
cross-platform question is already answered by the golden hash both legs check.

The sweep also asserts different seeds produce *different* battles. Without that, a
simulation ignoring its inputs entirely would pass the replay loop perfectly.

### State

125 tests plus the gated sweep. Phase 1 is **complete except the ARM-device third of its
gate**, which needs hardware. Two blockers remain and both are the owner's: an admin password
for iOS, and a physical Android device.

---

## 2026-08-08 — Session 5 — the ARM leg, on an emulator

### The question

Owner asked whether anything could be tested while a physical Android phone and an admin
password are being arranged, and whether a simulator would do. Answer for Android: yes,
completely, for correctness. Answer for iOS: no — the missing framework *is* the simulator,
so there is nothing to fall back to.

### The emulator

`system-images;android-34;default;arm64-v8a` plus `emulator`, installed under `$HOME` with no
admin, AVD `wastemarch_p6a` on the pixel_6a profile. On Apple Silicon this runs the real
`aarch64-linux-android` library natively under HVF with real bionic — a genuine third leg for
the hash, not a translation layer.

### Making the hash visible on a device at all

**An exported app ignores `--script`**, so `tools/sim_smoke.gd` cannot run on a phone. Split
the checks into `tools/sim_checks.gd` (a `RefCounted` with `run() -> int`); `sim_smoke.gd` is
now a six-line shim and `world/world_root.gd` calls the same thing from `_ready()`. One set of
checks, two entry points, no duplication. `adb logcat -s godot:V` reads it.

The Rust test that pins the hash constant into GDScript failed within minutes of the move,
which is exactly what it is for. Repointed at the new file.

### The false emergency

First on-device run: `expected 0x6de277a1cf08225b, got 0x8f71831f894f8205`. That is the
signature MEMORY describes as "stop everything". It was a **stale `.so`** — built 01:36, with
`sim-core` last touched 02:05, across three golden-hash changes. `cargo test` on the desktop
never rebuilds the Android target, so nothing else in the project would ever have noticed.
Rebuilt, re-exported, hash matched exactly.

Recorded in MEMORY as a mtime check to run *before* believing any cross-platform failure. The
real fix is a CI job that cross-compiles the Android target; that is now action 2 in PLAN.

### What the emulator will not tell us

Screenshot comes back black — the Vulkan surface is not composited into `screencap`. Stopped
after two attempts rather than chasing it; it is not evidence of a render failure, and frame
rate on an emulator borrowing the Mac's GPU is meaningless anyway. Performance, draw calls,
triangles and heat remain hardware-only, which is the Phase 0 budget gate, not Phase 1's.

### State

125 tests green, hash agrees on macOS, Linux and an ARM Android system. **Left for the owner:
does an emulator close the Phase 1 gate, or does it need a physical phone?** It is the same
M4 Pro silicon as the macOS leg, so it proves the toolchain and ABI, not a second chip vendor.
`sim-core` is pure integer, which is why that risk is small — but it is the owner's call and
the gate stays open until they make it.

### Owner's decision, same session

**The emulator closes the Phase 1 gate.** Recorded as
`docs/decisions/ADR-0003-emulator-satisfies-the-phase-1-gate.md`, which states the accepted
risk plainly: it does not prove a Qualcomm chip agrees with an Apple one. The mitigation is
structural rather than procedural — `sim-core` has no floats, and whole-number arithmetic is
exactly defined by the instruction set, which is the whole reason for the no-float lint.

Follow-on recorded in the ADR: **re-run check 6 on the first physical phone**, as part of the
Phase 0 hardware pass. A disagreement there reopens Phase 1.

**Phase 1 is complete.** The only thing blocking forward progress is now the colour palette in
`docs/ART_BIBLE.md`, which the owner is reviewing. Phase 2 starts when it is locked.

### Art direction, same session

Owner reviewed `ART_BIBLE.md` and brought a nine-colour palette board plus four industry
reference screenshots and an external review of the palette.

**Wrote the check instead of arguing.** `tools/art/palette_check.py` — CIE Lab separation plus
Viénot-Brettel-Mollon simulation of the three common forms of colour blindness, stdlib only.
The proposed nine had **four failures**, worst being gold vs firelight at dE 4.9 under
protanopia: to the most common form of red-green colour blindness, "wealth" and "life" were
the same colour. The board that came with the palette had ticked "Colorblind Safety ✓".

Two more the numbers found and nobody had: firelight was **darker** than bone grey, making
"light tells the story of progress" arithmetically impossible; and dry ochre's chroma was 41.5
against gold's 54, so the environment was competing with the accents it exists to make room
for.

The external review's *diagnosis* was the best thing in it — it spotted the ochre/gold/
firelight hue cluster unaided. Its *fix* was wrong and testing it proved so: `#E8A54B` →
`#D99543` moves firelight onto gold's lightness and takes protanopia from 4.9 to 3.6. **A
lightness collision cannot be fixed by desaturating.** Accepted the review's value-beats-hue
rule and its two-signal accessibility rule; rejected its screen-percentage table as invented
numbers that cannot be enforced.

Locked as ADR-0004: six values unchanged, two moved, one split in two. The split is the real
fix — the original firelight was being asked to be both a lit *surface* and a cast *light*,
which have different constraints.

**Two technical findings became Art Bible rules**, both of which had to land before generation
rather than after: lighting on `forward_mobile` is emissive, not real lights (one sun, six
point lights, everything else painted — which changes how textures are authored, so it changes
the prompts); and the always-on-screen Duskwood treeline is a 60k-triangle budget item, not
scenery.

**Owner's design idea — a SimCity-like town plus Clash-like forward outposts.** Evaluated
properly and parked in `docs/BACKLOG.md` rather than absorbed into the current phase, per
CLAUDE.md §5. It is the dominant successful shape in mid-core mobile and the story justifies
it, but it doubles the balance surface, and its known failure mode has a name — CoC's Builder
Base, a second base players stop visiting. Reconsider at the end of Phase 4, when the core
loop is known to be fun. Noted that `GRID_SIZE` is a compile-time 44, so both bases must be
the same size or the golden hash moves.

**Phase 2 is now unblocked and nothing is waiting on the owner.**

### Phase 2 begins — stage 1 works

Owner settled the last open question: "modern city" means advanced *within the setting*, in
Ostmere's idiom, eventually exceeding the kingdom. No conflict with the story or the palette.
Recorded in the backlog entry; the "exceed Ostmere" ceiling is a good long-game target the
current progression does not yet reach for, flagged for Phase 5.

**ComfyUI is not installed and was not needed.** `mflux` was already on the machine from the
`mentoros` sibling — MLX-native, so it runs on the GPU directly rather than through a
translation layer, and it has first-class commands for *both* permitted models. Measured
16 s/step at 1024², about two minutes an image, peak 10.7 GB.

**Two failures worth the time they cost.** `mflux-generate-z-image-turbo` with no `--model`
defaults to the full-precision upstream repo, which is not cached, and starts a silent ~16 GB
download: twenty minutes of a process at 5% CPU with an empty output file, looking hung rather
than downloading. `HF_HUB_OFFLINE=1` converts that into an immediate error naming the missing
files, which is how it was diagnosed. Both in MEMORY.

**The licence hazard is real, not theoretical.** Flux Kontext — forbidden here, non-commercial
licence — is in the same shared cache with an `mflux-generate-kontext` binary pointing at it.
`tools/pipeline/concept.py` refuses any model not on the permitted list rather than trusting
nobody mistypes.

**Delivered:** `concept.py`, a shared style header derived from the Art Bible, prompt files for
the three reference buildings, and a provenance record per image carrying model, seed, full
prompt and a workflow hash — the hash covers the recipe but deliberately not the seed, so
several seeds of one recipe are recognisably siblings.

Two buildings generated so far, a granary and the keep, and they came out visually consistent
with each other despite being very different objects. That is the style header doing its job,
and it is the whole reason the project's one critical risk is manageable.

**The keep is on-model:** bone-grey stone, a small crimson banner reading as authority rather
than decoration, warm firelight in the doorway, and the rebuilt corner the prompt asked for.

### Stage 2 — the first parametric building

Owner picked `granary_1004`, `watchtower_1004`, and **both** `keep_1002` and `keep_1003`. The
two keeps are read as the two ends of the upgrade progression rather than as rival designs,
which is exactly the case the master plan makes for scripted models: one script with a `level`
parameter cannot drift the way five hand-made keeps would. Recorded in `PICKS.md`.

Worth recording honestly: the owner's granary pick came from the batch I had written off as
"came out as houses", and on inspection it is the better building — stone footings, solid door,
no windows, and an open lean-to with grain sacks stacked under it. The lean-to is an asymmetric
silhouette feature, which is what the 64-pixel test rewards. **"The prompt did what I asked"
and "the picture is better" are different questions and only the second one matters.**

### The validator earned its keep three times in an hour

Everything below was caught by the build failing, not by looking at a render:

1. **A metre-off-centre lean-to roof.** `ramp()` takes the plank's centre line; I passed a wall
   edge. The overhang check named the exact distance.
2. **"Origin at footprint centre" was implemented wrongly** — as "the mesh bounding box must be
   centred", which failed a building whose lean-to is *meant* to overhang. Builders now declare
   their footprint in tiles and overhang is measured separately, capped at 0.35 m.
3. **Decimate produces broken meshes on box geometry.** `mesh.validate()` said the base mesh
   was clean and the decimated LOD1 needed repair; glTF then warned it "may be exported
   wrongly". Decimation also eats corners, destroying the silhouette the Art Bible protects.

That third one changed a rule rather than a line of code. LOD1 is now built by **dropping
detail parts** — builders take `detail: bool` — and below 400 triangles there is no LOD1 at
all, because a second mesh costs a draw call to save 97 triangles. Both written into
`ART_BIBLE.md`.

### A unit error caught by disbelief rather than by a test

The build first reported the granary needs a **4096×4096 texture**. Arithmetically correct and
obviously absurd for a shed. The mistake was the unit: buildings share one texture sheet, so an
asset does not have a texture size, it has a claim on atlas area. Now reported as 2.6M texels.

That raised a fair question the Art Bible now carries openly: **256 texels per metre is two to
four times what a phone shows** at typical zoom. Not changed — the geometry is unaffected
either way, so it is cheap to defer to stage 3 and expensive to guess at.

### End to end

`granary_L1.glb` — 162 of 1,500 triangles, 2×2 tiles, 0.17 m overhang, sitting on z=0 —
imports into Godot cleanly and produces a `.scn`. Prompt → concept → parametric model →
validated → glTF → engine, with nothing done by hand.

### The keep, the watchtower, and a test that was measuring the wrong thing

All three reference buildings now build parametrically and validate. The keep interpolates
between the owner's two picks: 3.9 m at level 1, 5.9 m at level 5, identical triangle count,
which is the entire argument for scripted models made concrete.

First keep came out 2.9 m tall on a 4 m footprint and read as a bunker. Checked against the
concept rather than adjusted by feel — `keep_1002` is roughly as tall as it is wide — and the
numbers were changed to match.

Three primitives (`box`, taper, leaning strut) collapsed into one `prism`, which is three
fewer places for an off-by-a-half-extent error. The granary came out at exactly 162 triangles
afterwards, which is how I know the refactor changed nothing.

**Merlons are the interesting case for the LOD rule.** Crenellation *is* a keep's silhouette,
so it cannot simply be dropped at distance — but an individual merlon is smaller than a pixel
there. So LOD1 replaces the row of merlons with a solid parapet band: the thickened wall top
still reads, the gaps were never visible anyway, and it is a quarter of the triangles. 660
triangles down to 132.

### The silhouette check exists now, and its first version was wrong

`ART_BIBLE.md` has claimed since Phase 0 that the silhouette test is "scripted and automatic".
It was not. It is now.

The insight that makes it automatable: a script cannot judge whether a person recognises a
shape, but it can measure the thing that makes recognition impossible — two buildings whose
black shapes are nearly the same. Overlap over 80% fails.

**The first version framed each building to fill the frame**, so a 4.2 m watchtower and a
2.5 m shed rendered the same size. Size is most of how buildings are told apart on a screen
where they all stand on the same ground. Fixing it moved granary-versus-keep from 0.69 to
0.33: the test had been giving the wrong answer *in the safe direction*, which is the kind
nobody ever catches, because it only ever says "fine".

Also worth its own line: `BLENDER_EEVEE_NEXT` does not exist in 5.2 — it is `BLENDER_EEVEE`.
Precisely the 4.x-to-5.x drift MEMORY warned would cost time in Phase 2.

### Stage 3, started at the lazy rung — and it solved a problem I had flagged

Checked the prerequisites before committing to the master plan's approach and two things came
back that changed it. `mflux-generate-qwen-edit` takes init images rather than true ControlNet
conditioning, and **Qwen-Image-Edit is not cached** — a multi-gigabyte download standing
between here and a first texture.

So stage 3 starts with material zones painted straight from the locked palette instead: five
materials, literal hex values from ADR-0004, assigned per part in the builder. Deterministic,
instant, no download.

**That also fixes something I had raised as an open risk.** The concept art drifts brighter and
more saturated than the palette; I had said it would matter if it survived stage 3. It cannot
now, because the model is never asked to interpret a colour — it is given one. An AI texture
pass later refines on top of a correct base rather than being the only source of colour.

### The camera found a fault no amount of care would have

The watchtower's roof sat on a comfortable gap that looks right in elevation and **completely
hid the brazier** from 30 degrees above, which is the only angle this game has. The brazier is
that building's entire "life" signal under the Art Bible.

Taller posts, tighter overhang, fixed. Written into `ART_BIBLE.md` as a rule: a building is
judged at the camera it will be seen at, and rendering there is a design check rather than a
preview.

### State

Three buildings, palette materials, in the engine: **2,548 triangles and 10 draw calls**
against 250,000 and 120. `game/world/AssetPreview.tscn` shows them in the real renderer at the
locked camera and prints the budget, which is `MASTER_PLAN.md` stage 6 as well as somewhere to
look.
