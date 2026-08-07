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
