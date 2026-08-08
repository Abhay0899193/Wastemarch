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

### Stage 3 works, and it cost five attempts to write one PNG

Four tileable materials generated by Z-Image Turbo, tinted to the locked palette, on three
buildings, in the engine: **2,548 triangles, 10 draw calls.**

Getting there was the worst debugging of the project so far and worth recording exactly.

**The first regression was invisible.** Wiring the generated tile into Base Color made the
buildings *look* textured and quietly threw the palette away — the generated stone, a pale
clean `#EFEBE4`, simply replaced bone grey. Precisely the drift this approach was chosen to
prevent, arriving through the back door.

**The second was worse and taught the real lesson.** Building the colour with shader nodes
looked correct in Blender and rendered pure black in Godot. Reading the exported `.glb` back —
its JSON chunk is plain text — said in seconds what an hour of renders would not:
`baseColorFactor = [1,1,1,1]` on every material. **Blender's exporter had dropped the palette
multiply.** glTF carries one texture times one colour and nothing else.

So no node does colour work now. Tiles arrive already tinted; base colour is that texture and
there is nothing left for an exporter to drop.

**Then writing the tinted tile failed five times in a row, silently**, producing four identical
solid-black PNGs of exactly 27,749 bytes. Two attempts were lost to `images.new()` having
source GENERATED, whose `save()` ignores assigned pixels. The actual cause was found only by
measuring rather than guessing: **assigning `colorspace_settings.name` on a file-backed image
makes Blender re-read the buffer from disk and discard the pixels just written.** The read was
never wrong — it returned a correct mean of 0.372 the whole time. The reload after it was.

**The check I added mid-struggle is the durable part.** It reads the saved file back and fails
if the mean brightness is outside 0.02–0.98. Same lesson as the zero-byte `.so` in the APK
during Phase 0: *a file existing is not evidence that anything is in it.* It turned a silent
black building into a named error, which is why attempts four and five were quick.

**Two rules changed as a consequence**, both in `ART_BIBLE.md`: colour is baked into the tile
rather than expressed in a material, and texel density is now 512 rather than 256 — not a
violation but a consequence, because with tiling, density is set by repeat frequency and
repeating more often costs nothing.

### The owner said the models look nothing like the concepts, and was right

Diagnosis, worst first: no ambient occlusion; a sixth of the triangle budget being used; no
normal map; zero hue variation inside a material; flat lighting.

Fixed this session — **normal maps** derived from each tile's luminance by Sobel gradient
(glTF carries a normal texture natively, unlike the colour mix it dropped earlier), and
**geometry**: the keep went from 660 to 1,104 triangles with a stepped plinth, corner quoins,
buttresses, recessed arrow slits and a doorway with jambs and a lintel. Quoins are the best
value of the lot — twelve triangles each and the clearest "this is masonry" cue available.

**Budgets are a ceiling and I had been treating them as a target.** Three buildings are 3,436
of 250,000 triangles. Draw calls are the real mobile constraint, not geometry.

**One silent bug worth the scar.** `_newest_tile()` excluded `_tile.png` by name and took the
alphabetically last of the rest. Adding `_normal.png` — which sorts after `_1001.png` — made
the *normal map* the base-colour source. The stone turned pale, lost its mortar, and nothing
failed. Now it matches `<material>_<digits>.png`: a blocklist of suffixes goes stale the moment
a new output appears, an allowlist of what a source looks like does not.

Still open, in order: ambient occlusion, lighting, and bounded hue variation within a material.

### Decision: tiled palette materials everywhere, concept projection dropped

After a long run at getting the models to match their concept art — camera projection, edge
bleed, inset fitting, repainting over the model's own render, baking to a real unwrap — the
owner asked to see the concept art standing in the engine as sprites instead.

**The sprites looked clearly better than the models.** Recorded plainly; it is the honest
result of the experiment and it is why the question was worth asking.

The owner then chose to **keep 3D and drop the concept texturing**: every building textured
from the same five tiled palette materials, the way the watchtower already was. Consistency
over per-asset fidelity to a painting.

That is a defensible call and probably the right one. Projection gave a livelier surface and
cost: it only held from one camera angle, needed an inset hack to stop pale slivers, and made
each building look different depending on how well its concept happened to fit its model —
which is the *opposite* of what an art bible is for.

**Three things from that work survive and keep their value:** the real UV unwrap, baked
ambient occlusion, and baked emission. Those are why the buildings look better now than they
did before any of it, even with the concept art removed.

`assets-src/concept/` is now modelling reference, which is what concept art is normally for.

---

## 2026-08-08 — Session 6 — Phase 2 pipeline closed, Phase 3 playable

A long session, most of it spent on one question the owner kept asking and I kept
half-answering: **why don't the buildings look like the concept art?**

### The art road, and where it ended

Camera projection → edge bleed → inset fitting → repainting over the model's own render →
baking to a real unwrap. Each step was a genuine improvement on the last and none of them
closed the gap.

Two things I got wrong and reported as fixes:

1. **`doubleSided` was a red herring.** glTF really did export it, and backface culling is a
   correct change worth keeping, but culling changed nothing visible. **Confirming *a* real
   problem is not confirming *the* problem**, and I presented it as though it were.
2. **The coverage metric was wrong twice**, both times reporting a *lower* number than reality
   — the direction that never gets caught. Weighted by surface area rather than screen area,
   then sampling polygon centres so a big roof quad read "painted" while half of it hung off.

The owner then asked to see the concept art standing in the engine as sprites. **The sprites
looked clearly better and it was not close.** They chose 3D anyway and dropped the concept
texturing: every building from the same five tiled materials, consistency over per-asset
fidelity. That is defensible and probably right — projection made each building look different
depending on how well its concept happened to fit its model, which is the opposite of what an
art bible is for.

Three things from that work survive and are why the buildings look better now than before any
of it: the real UV unwrap, baked ambient occlusion, and baked emission.

### The biggest single win was two lines

Ambient light was 0.6 of neutral grey against a 1.1 sun, so the shadow side was lit almost as
brightly as the front and every model read flat regardless of its texture. A warm 2.0 sun
against a cool 0.32 ambient did more than everything else that day combined. The owner spotted
it themselves in Clash of Clans and called it "single side shadow".

**I should have rendered the shipped asset beside its concept three sessions earlier.** Doing
it made four gaps obvious in one image. `tools/blender/render_and_silhouette.py` and
`game/tools/zoomcap.gd` exist so this is one command now — and the second lesson is that a
full-scene capture is too small to judge art by. Every defect the owner found had been
invisible in mine.

### Phase 2's gate

`python3 tools/pipeline/build.py --all`. Prompt file and builder function are authored;
everything after is not. Its fifth stage reads the `.glb` back rather than trusting the build
log, which is the Phase 0 zero-byte-`.so` lesson made into a habit.

The gate's other half — three reference buildings the owner approves — is **not met**, and the
owner has been clear about that. Recorded as their decision to make, not mine to declare.

### Phase 3, and three rounds of one bug

The city is playable: place, wait, produce, place again, save, load. 22 headless checks.

The owner reported buildings overlapping **three times**, and I looked in the wrong place twice.

- **First time it was a real bug and my test was complicit.** `_place()` was unguarded and the
  check lived in the click handler, so the test — which called `_place()` directly — passed
  while the game was broken. **A test must go through the same door the player uses.**
- **Third time it was not a placement bug at all.** The towers were on different tiles. At 30
  degrees a building of height `h` hides about 1.7×h tiles behind it, and the watchtower was
  4.64 m on a 2×2 footprint. The placement was right and the proportion was wrong. Now 3×3 and
  shorter, with `HEIGHT_TO_FOOTPRINT_LIMIT = 1.6` failing the build so it cannot come back.

The reason it took three rounds is that every check I had ran on a **single building** while
every complaint was about a **dense base**. `game/tools/pack.gd` now places ten shoulder to
shoulder and photographs it in one command.

### State

125 Rust tests, palette check, sim smoke, city smoke, full asset rebuild — all green. Phase 3
in progress. Nothing waiting on the owner except the art bar, which does not block the city.

---

## 2026-08-09 — Session 7 — Clash of Clans, measured rather than admired

**What happened.** The owner supplied sixteen screenshots of CoC's opening and asked for the
flow documented, the modelling studied, and anything of ours that gets in the way changed —
explicitly including the art bible, the grid shape, sprites, camera and zoom.

**Measured, not guessed.** Two techniques, both throwaway scripts in the scratchpad:

- **Projection.** Footprint-diamond edge slope = 0.507 → 2:1 isometric → 30° elevation, 45°
  yaw, orthographic. **Which is exactly what `ART_BIBLE.md` already specified.** The useful
  negative finding of the session: the camera needed nothing.
- **Zoom.** Template-matched the same Town Hall between their most zoomed-out and most
  zoomed-in shots across a scale sweep. Best match 0.892 at scale **0.25** — the zoom range is
  exactly 4×, not the 10× we allowed.
- **Proportion.** Their Town Hall is **0.55** of its 4×4 footprint tall and covers **0.69** of
  it. Barracks 0.44. Ours were 0.98 to 1.42 against a limit of 1.6.
- **Shadows.** They cast none. Not buildings, not trees, not troops.

**Changed.**

- `HEIGHT_TO_FOOTPRINT_LIMIT` 1.6 → **0.6**; new `FOOTPRINT_FILL = 0.8` replacing the overhang
  allowance, which permitted the opposite of what it should have.
- New `reproportion()` squashes a finished model into both limits, and new `build()` is now the
  single path to a finished object — `bake_asset.py` had been building its own copy and
  skipping the squash, which failed the pipeline the first time in a usefully loud way.
- `city.gd` computes zoom limits at runtime from the grid and the viewport aspect, 4× range,
  opens fully zoomed out.
- `City.tscn` sun no longer casts shadows.
- `docs/reference/COC_TEARDOWN.md` — the full teardown, method included.
- `ADR-0005`; `ART_BIBLE.md` camera, proportion, lighting and colour sections; `TESTING.md`;
  three new `BACKLOG.md` items.

**Verified.** no-floats ok · 125 Rust tests · palette ok · sim hash `0x6de277a1cf08225b` ·
city smoke 22 checks · `build.py --all` green (granary 294, keep 1488, watchtower 558 tris) ·
silhouette worst pair keep L1 vs L5 at 0.71, new worst non-self pair watchtower vs keep 0.52.

**Sprites: asked and answered.** The owner offered them again. Rejected in ADR-0005 with the
reason that matters — the look comes from proportion, colour discipline and painted shading,
all available in 3D — plus the fact that it is not a one-way door, because scripted Blender
models can be rendered to sprites at the locked camera whenever we want.

**Left deliberately undone.** The three buildings are *squashed* into the new proportions, not
redesigned at them, and every one lands exactly on the cap so the set has no variety of
proportion. Both are `ponytail:`-marked and in the backlog, to be done once the owner has
looked at the reproportioned city.

---

## 2026-08-09 — Session 8 — the watchtower was fat, and the ground was on the wrong plane

**Owner's feedback:** the watchtower reads fat now that it is short — make it skinnier; the
grid and ground do not look good; fix the details; carry on with the next step.

**The watchtower, and the rule behind it.** One shared proportion cap put every building at
0.6 and a tower at 0.6 is a shed. What actually hides the ground behind a building is its
*area* on screen, not its height — a thin mast blocks less than a wide barn. So proportion is
now a **pair of numbers per asset**, `PROPORTION` in `build_asset.py`, under a hard ceiling of
`fill 0.8, height 1.2`. The watchtower is `fill 0.5, height 1.0`: 1.5 m wide and 3.0 m tall on
its 3x3, and it is a tower again.

**Two bugs, one shape.** Both were "the same model built in more than one place":

- `render_and_silhouette.py` built its subjects straight from `BUILDERS` and skipped
  reproportion — the third such path after `bake_asset.py`. It had been measuring geometry the
  game never shows and reporting green. Everything goes through `ba.build()` now.
- Reproportioning **per level** normalised every upgrade level into the same box. Keep L5 came
  out identical to L1; the silhouette test said 0.95 the instant it started telling the truth.
  The scale is now measured once on level 1 and reused for every level. Back to 0.74.

**The ground was in view space.** `VERTEX` in a Godot fragment shader is *view* space, so the
old shader's grid and world edge were pinned to the screen: screen-aligned squares instead of
diamonds, and the edge of the world as a horizontal line across the frame. One
`INV_VIEW_MATRIX` multiply. This had been wrong since the shader was written and nobody saw it
because grid *lines* look like grid lines either way.

Ground now: no lines at all, 5% per-tile checker plus a random per-tile offset, three scales
of mottling, scrub patches over soil, the Art Bible's old field lines, and Duskwood beyond the
playable square. First frequency choice was wrong — `vnoise(p * 0.055)` spans two noise cells
over 44 tiles, so almost the whole field took one value and read as flat sand.

**Props.** `pine` (48 tris) and `boulder` (24), new `prop` size class at a 200-triangle budget
and a 256 px bake. 100 and 60 of them, scattered from a fixed seed by `MultiMeshInstance3D` —
two draw calls — kept in a separate `_obstacles` dictionary so `_load()` clearing `_occupied`
cannot delete the scenery, and blocking building the way their obstacles do. Middle 20x20 left
clear.

**Foliage must be at least six-sided.** With cast shadows off, a four-sided cone still shows
one lit face and one nearly black one, and every pine read as having its own cast shadow. Cost
six triangles to fix, and an hour to work out that the shadows I had switched off were not
shadows.

**Also:** `duskwood` added to the material vocabulary (no new colour — Duskwood near from
ADR-0004; the five-hue cap is per asset and a pine uses two). Ambient lifted to 0.55, since
with no cast shadows ambient is all that fills an unlit face. Opening zoom set to halfway
rather than their fully-out, because their fully-out frames a full village and ours frames
three buildings on 1,936 tiles.

**Verified.** no-floats ok · 125 Rust tests · palette ok · sim hash 0x6de277a1cf08225b · city
smoke 22 checks · `build.py --all` green across five assets · silhouette honest and passing,
worst pair keep L1 vs L5 0.74.

---

## 2026-08-09 — Session 9 — the ten seconds were the build timer, and three more buildings

**"After putting it, it takes 10 sec to render."** It was not a rendering problem. `prof.gd`
(new, kept) places buildings and reports any frame over 40 ms: the worst was **138 ms**. What
took ten seconds was `build_s` — keep 12, watchtower 9, granary 6 — during which the model was
replaced by a flat unshaded translucent blue material. That reads exactly like a texture that
failed to load, so the wait looked like a fault.

Three changes, in order of how much they mattered:

1. **The under-construction state keeps the real material**, merely darkened —
   `albedo_color` multiplies the baked texture, so the building reads as itself in shade.
2. **A countdown over each building** while it builds. A wait whose end you cannot see feels
   like a fault; a wait with a number on it is a wait.
3. **Placeholder build times halved** — 3 / 5 / 8 s. Data, not code.

**But the same profiler found a real stall.** First placement of three buildings cost a
**1,376 ms** frame: 5 to 10 MB of glTF with baked 2,048 px textures, none of it touched until
the click. `_preload_models()` in `_ready` moves it to startup. Placement is now **41 ms**.
That is the value of the tool — the reported bug was not real and a worse one beside it was.

**Three more buildings, so Phase 3 has its six.** `croft` (126 tris), `logging_camp` (204),
`mine` (108), each with its own `PROPORTION` entry: a field is nearly all ground at 0.35, a log
stack 0.45, a mine 0.6. Silhouette test extended to all six — twenty-one pairs, worst is still
keep L1 vs L5 at 0.74, worst new pair croft vs logging camp at 0.69 (both 3×3 and both low —
the one to watch when a seventh building arrives).

`PROPORTION_CEILING["fill"]` went 0.8 → 0.9 for the croft, which is a field and should reach
most of its plot.

**A trap paid for twice.** `add_child()` in `_initialize` does not run `_ready` first, so
resources set there are overwritten by `_load_definitions` a frame later — it is in MEMORY.md
and I still wrote it. `prof.gd` now sets them in `_process` with a comment saying why.

**Verified.** no-floats ok · 125 Rust tests · palette ok · sim hash 0x6de277a1cf08225b · city
smoke 22 checks · `build.py --all` green across eight assets · silhouette green across six
buildings · six placed in one frame with no stall over 50 ms.

---

## 2026-08-09 — Session 10 — levels, selection, and a migration that is actually tested

Phase 3's three remaining mechanical items, done together because they are one piece of work:
you cannot upgrade what you cannot select, and a level is the first thing the save format has
had to grow.

**Levels.** `max_level` and an `upgrade` multiplier block per building in `buildings.json` —
cost, build time and yield each get `multiplier^(level-1)`. A multiplier is a *placeholder
shape*, not a balance decision, and the file says so: Phase 5 replaces the block with an
explicit per-level table. The point today is that the city can read a level at all.

**The art does not have to keep up.** `_model_for(id, level)` walks down from the level asked
for to the best model that exists, so the keep changes shape at 3 and 5 and the croft never
does. Building thirty models to prove a counter works is the wrong order.

**Selection is the Clash of Clans pattern** — a name, a level and one button, *underneath the
building*, so your eye never leaves the thing you are deciding about. The panel is one Control
positioned from `unproject_position` each frame. Projecting the building's origin put it across
the model; projecting the near corner of its footprint puts it below, which is what they do.

**Selection is remembered by cell, not by holding the dictionary.** Godot compares dictionaries
by reference and `_load` rebuilds every one of them, so a held reference would have pointed at a
building that no longer existed. A cell is a fact about the world.

**Save version 2, with a migration chain.** One step per version, applied in order — the
temptation is `if not row.has("level")` somewhere in the loader, which works exactly once and
then nothing can tell a version 1 save from a version 2 one missing a field. A save from the
*future* is refused rather than guessed at.

**The migration test writes the old file by hand.** A save-then-load round trip with today's
code would pass even if `_migrate` did nothing at all. `city_smoke.gd` writes a version 1
payload in the shape the old build wrote, and a version 99 one, and checks both are handled.

**On the stall that came back and went away.** One run showed 1,344 ms on first placement again;
three subsequent runs showed 45 to 60 ms with nothing changed. It is the pipeline cache going
cold after an asset rebuild, not a regression. Worth knowing before chasing it: measure twice.

**Verified.** no-floats ok · 125 Rust tests · palette ok · sim hash 0x6de277a1cf08225b · city
smoke **35 checks** including upgrade, level-aware production, save round trip, a hand-written
version 1 save and a refused version 99 · no placement frame over 60 ms.

---

## 2026-08-09 — Session 11 — pan was wrong twice over, and a laptop can now zoom

**"Pan is not working correctly."** It was, and the reason is worth writing down. The old code
multiplied mouse pixels by `size / 600.0` and applied the same number to both axes:

- **600 is nobody's window height.** At 1080 that made horizontal panning 1.8x too fast.
- **The ground is foreshortened 2:1 vertically at a 30 degree camera**, so a vertical drag has
  to move the camera *twice* as far as a horizontal one of the same length. It moved the same.

The two errors do not cancel — the axes end up disagreeing by a factor of two, so the world
slides diagonally out from under the cursor. Measured before replacing it: a 240 px horizontal
drag left the grabbed point **9.07 m** from the cursor, a 190 px vertical one **16.97 m**, a
diagonal one **26.01 m**.

**The fix needs no multiplier.** For an orthographic camera, translating by D moves the ground
point under a fixed pixel by exactly D. So remember the world point under the cursor at press
time and, on every motion, `camera.position += grab - ground_at(mouse)`. Exact, cannot drift,
and stays correct if the camera angle, the zoom or the window ever change. Zoom-to-cursor is
the same three lines with the size change in the middle — so zooming at a corner no longer
throws away what you were looking at.

**Watched the old code fail the new test** before deleting it, per `docs/TESTING.md`. The
assertion is "the grabbed ground stays under the cursor", which is the *definition* of correct
panning rather than a description of the implementation, so it cannot rot.

**A right drag was also cancelling the selection**, because release did not distinguish a click
from a drag. Six pixels of slop fixes it.

**Laptop controls.** Zoom is now the wheel, a **trackpad pinch** (`InputEventMagnifyGesture`,
which is what a MacBook actually sends), and `+` / `-`. Pan is right-drag, middle-drag, or
**arrow keys / WASD**, continuous in `_process` so holding a key glides. The keyboard pan uses
the same grab-the-ground trick — ask where two screen points land and move by the difference —
so its speed is right at every zoom for free.

**`S` was bound to two things.** Save, and pan-down under WASD; every downward pan wrote a save
file. Save and load are `Ctrl+S` / `Ctrl+L` now.

Panning is also clamped so the view cannot leave the map, six metres past the edge.

**Verified.** no-floats ok · 125 Rust tests · palette ok · sim hash 0x6de277a1cf08225b · city
smoke **48 checks** including three drags, two zooms, the zoom limits and the pan clamp.
