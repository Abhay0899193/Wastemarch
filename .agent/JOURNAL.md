# JOURNAL

Append-only. Newest entry at the bottom. One block per session.

---

## 2026-08-08 — Session 1 — Phase 0 foundation

**Starting state:** one commit (`37683e0 "first"`) containing three markdown files —
`claude.md`, `Master plan.md`, `Story.md`. No code, no LFS, no docs, no CI. Remote already
existed at `git@github.com:Abhay0899193/Wastemarch.git`.

### Environment verified before anything else

- Godot `4.7.1.stable.official.a13da4feb` — matches target exactly. Export templates for
  `4.7.1.stable` already installed.
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
