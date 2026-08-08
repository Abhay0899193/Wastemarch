# MEMORY — durable facts, gotchas, and things not to retry

Append-only in spirit. Delete an entry only when it becomes factually wrong, and say so in
JOURNAL.md when you do.

---

## Environment

- **Godot** `4.7.1.stable.official.a13da4feb` at
  `/Users/singha7/Applications/Godot.app/Contents/MacOS/Godot`. Matches the target exactly.
- **Export templates: COMPLETE** as of 8 Aug 2026 — all 35 files including `ios.zip`,
  `android_debug.apk`, `android_release.apk`, `macos.zip`. Resolved by the owner.
  *Historical note worth keeping:* they were previously web-only while the directory looked
  populated. **Never take "the directory exists" as "the templates are installed" — `ls` for
  the specific file.**
- **Blender is 5.2.0 LTS, not 4.x.** Nearly every Blender-Python example online targets 4.x
  and several operators moved in 5.0. Verify against the 5.x API before copying any snippet.
  This will cost time in Phase 2 if forgotten.
- **Rust 1.95.0** with `aarch64-apple-darwin` and `aarch64-linux-android`.
  **`rustup target add` must be run from inside `sim/`** — elsewhere it attaches the target to
  the *default* toolchain while cargo in `sim/` uses the 1.95.0 pinned by
  `rust-toolchain.toml`. The symptom is a baffling "can't find crate for `std`" for a target
  `rustup target list --installed` happily reports. Cost real time on 8 Aug 2026.
- **Android toolchain installed** — JDK 21.0.12, SDK, NDK 29.0.14206865, all under `$HOME`.
  See the section below.
- Xcode 26.3 present but **iOS is blocked on an admin action** — see below. Not a signing
  problem; `xcodebuild` itself will not start.

## Do not retry

### `brew install` fails — `/usr/local/bin` is root-owned

Homebrew's prefix here is `/usr/local` (Intel-layout Homebrew on an arm64 Mac). The final
symlink step fails with a permissions error. **`brew install <anything>` will fail the same
way every time** until the owner runs `sudo chown -R $(whoami) /usr/local/bin`.

Workaround used for git-lfs: downloaded the official release binary, verified its SHA-256
against the published hash, installed it to `~/.local/bin` (user-owned, already first on
PATH). Same approach works for any other single-binary tool. Noted in `docs/BACKLOG.md`.

### Case-only renames silently no-op on macOS

`git mv claude.md CLAUDE.md` does nothing on a case-insensitive filesystem — the repo keeps
the lowercase name and GitHub's Linux checkout gets `claude.md`, so `CLAUDE.md` references
break there. **Always use the two-step:**

```bash
git mv claude.md CLAUDE.tmp && git mv CLAUDE.tmp CLAUDE.md
```

### Godot `Transform3D(...)` literals in .tscn fill ROWS, not columns

Writing a camera basis as columns produces the transposed (= inverted) rotation, and the
camera silently points the wrong way — the scene renders the environment background only,
with no error and no warning. Cost about fifteen minutes in session 1.

**Prefer `position = Vector3(...)` + `rotation_degrees = Vector3(...)` in hand-written
.tscn files.** Godot applies them correctly, and "30 degrees elevation, 45 yaw" stays
readable in the diff. Reserve raw `Transform3D` literals for files Godot itself wrote.

**Verify camera framing empirically, never by eye on the maths:**
`cam.unproject_position(Vector3.ZERO)` must land near the centre of `root.size`.
`game/tools/capture.gd` renders a scene to PNG for exactly this. It needs a real rendering
device — do **not** pass `--headless`, or `root.get_texture()` returns null.

### Comments in `game/project.godot` do not survive

Opening the editor rewrites the file from its own template and **strips every comment**. It
also drops `renderer/rendering_method.mobile` as redundant whenever the base
`rendering_method` already says `mobile` — that is normal, not a lost setting, so do not
re-add it thinking something went missing.

Do not put rationale in `project.godot`. It lives in `docs/decisions/ADR-0002`, this file,
and `docs/ARCHITECTURE.md`, all of which Godot cannot touch.

Settings that must stay true, checked after any editor session:
`renderer/rendering_method="mobile"` · `viewport_width=1920` / `viewport_height=1080` ·
`stretch/mode="canvas_items"` / `aspect="expand"` · `handheld/orientation="landscape"` ·
`import_etc2_astc=true` · `config/features` contains `"Mobile"`.

`export_presets.cfg` is only rewritten when an export preset is saved, so its comments have
survived so far. Do not rely on that.

### iOS is blocked on ONE admin action — investigated fully, do not re-derive

The owner has **no admin rights on this Mac**. Xcode 26.3 and iOS SDK 26.2 are installed, but
Xcode's first-launch components in `/Library/Developer/PrivateFrameworks/` are not, and only
an administrator can install them.

- `CoreDevice.framework` — **absent**. Needed to install onto a physical iPhone.
- `CoreSimulator.framework` — **absent**. Needed for the Simulator **and by `xcodebuild`
  itself**, which refuses to start without it even for a device-only, unsigned build:
  `xcodebuild failed to load a required plug-in ... run 'xcodebuild -runFirstLaunch'`.

So **no iOS build of any kind is possible** — not device, not simulator, not an App Store
archive.

**The paid Developer Program does NOT route around this.** TestFlight installs over the air,
which looks like a way to dodge the missing device tooling, but producing the `.ipa` to upload
still needs `xcodebuild`. Do not suggest spending the money as a workaround; it buys nothing
until the admin step happens.

**Fix:** an administrator runs `sudo xcodebuild -runFirstLaunch` once (or opens Xcode and
accepts the prompt). After that a **free** Apple ID and Personal Team is enough for device
installs — the paid programme is a Phase 8 concern.

**Verified working without admin:** Godot generates the complete iOS Xcode project, device and
simulator xcframeworks, MoltenVK and the PCK. It stops only on missing app icons — ordinary
work, not a permissions wall. So everything up to where Apple's tooling takes over is sound.

**Android needs no admin at all.** `$HOME` and `~/.local/bin` are writable; only
`/usr/local/bin` is not. Install the JDK and Android SDK under `$HOME` — never via Homebrew
`--cask`, which writes to `/usr/local` and fails. Full commands in `docs/ENVIRONMENT.md`.

### Android toolchain — installed user-local, no admin (8 Aug 2026)

| | |
|---|---|
| JDK | Temurin 21.0.12, `~/Library/Java/JavaVirtualMachines/jdk-21.0.12+8/Contents/Home` |
| Android SDK | `~/Android/sdk` — platform-tools (adb 1.0.41), platforms;android-34, build-tools;34.0.0 |
| Debug keystore | `~/.android/debug.keystore`, alias `androiddebugkey`, pass `android` |

Godot editor settings (`~/Library/Application Support/Godot/editor_settings-4.7.tres`) point
at all of the above. **Godot's defaults were wrong** — it shipped with
`android_sdk_path = ~/Library/Android/sdk` and a keystore path that did not exist.

**Never use Homebrew for this.** Its casks write to root-owned `/usr/local` and the owner has
no admin.

### Android export gotchas

- **`gradle_build/min_sdk` and `target_sdk` cannot be set unless `use_gradle_build` is true.**
  Godot refuses the export entirely: *"Min SDK can only be overridden when Use Gradle Build is
  enabled."* Do not re-add them to `export_presets.cfg`. The prebuilt template's own values
  are used, and they are correct — a produced APK reports `sdkVersion:'24'` and ships
  `arm64-v8a` only, both matching `MASTER_PLAN.md` §4. Verify with
  `~/Android/sdk/build-tools/34.0.0/aapt2 dump badging <apk>`.
- **A missing GDExtension library becomes a ZERO-BYTE entry in the APK, silently.** The first
  APK contained `lib/arm64-v8a/libsim_godot.so` at 0 bytes because the Rust crate had never
  been cross-compiled for Android. The export reported success. **Always check the size**, not
  just the presence, of every `.so` the `.gdextension` lists:
  `unzip -l <apk> | grep lib/`.

### A stale cross-compiled `.so` looks EXACTLY like a determinism emergency

First run of the sim checks on Android reported
`FAIL determinism hash: expected 0x6de277a1cf08225b, got 0x8f71831f894f8205`. That is the
signature MEMORY calls "stop everything". It was not divergence. The Android `.so` was built
at 01:36 and `sim-core/src/*.rs` last changed at 02:05 — the golden hash moved three times
that session and the phone build predated the last move.

Godot's export copies whatever `sim.gdextension` points at. `cargo test` on the desktop does
**not** rebuild the Android target, so nothing else in the project notices.

**Before believing any cross-platform hash failure, compare mtimes:**

```bash
ls -l sim/target/aarch64-linux-android/debug/libsim_godot.so sim/sim-core/src/*.rs
```

Rebuild first — `cargo build -p sim-godot --target aarch64-linux-android` — then re-export,
**then** panic if it still disagrees. After the rebuild the hash matched exactly.

Same trap applies to `aarch64-apple-ios` whenever iOS unblocks.

### The Android emulator runs the real ARM build — use it, but only for correctness

`system-images;android-34;default;arm64-v8a` on Apple Silicon executes the actual
`aarch64-linux-android` library natively under HVF, with real bionic. So it is a genuine third
leg for the determinism hash, and it verifies the Android toolchain and ABI. Setup and
commands are in `docs/ENVIRONMENT.md` and `docs/TESTING.md` check 6. AVD name
`wastemarch_p6a`.

**What it does not answer:** it is the same Apple M4 Pro silicon as the macOS leg, so it does
not prove agreement with a Qualcomm or Exynos chip — though `sim-core` is pure integer, which
is precisely why the no-float rule exists. And it says nothing about frame rate, draw calls,
heat or throttling.

**Emulator gotchas, both hit on 8 Aug 2026:**

- `adb install` fails with `device offline` when the adb server restarts between shell
  invocations. Loop on `adb get-state` until it says `device` before installing, and
  **check the install actually said `Success`** — otherwise the previous APK stays installed
  and the next launch silently re-runs the old build.
- The launcher activity is `com.wastemarch.game/com.godot.game.GodotAppLauncher`, not
  `GodotApp` — `am start` on `GodotApp` fails with `Permission Denial ... not exported`.
- `adb exec-out screencap -p` returns **black** for the Godot app. The Vulkan surface is not
  composited into the screenshot buffer. Do not chase this; it is not evidence the render
  failed. `ERROR: Couldn't present to Vulkan queue (VkResult error 5)` at startup is
  `VK_ERROR_OUT_OF_DATE_KHR` from the rotation to landscape, and stops after three.

### The determinism hash is now duplicated in `sim_checks.gd`, and a Rust test pins it there

`game/tools/sim_checks.gd` holds the boundary checks; `tools/sim_smoke.gd` (headless,
`--script`) and `world/world_root.gd` (inside a real build) both call it. The second exists
because **an exported app ignores `--script`** — on a phone there is no other way to see the
hash.

`determinism.rs::tests::the_godot_smoke_test_expects_the_same_hash` reads that file by path.
Moving or renaming `sim_checks.gd` fails that test, by design. It caught the move within
minutes of making it.

### Godot's iOS export needs app icons

The export gets all the way through generating the Xcode project and then fails:
`Export Icons: Invalid icon (icons/settings_58x58): ''`. Placeholder icons are needed before
any iOS export completes. Cheap to fix, but it will stop the first real attempt.

### Godot export gotchas, both cost time on 8 Aug 2026

- **The macOS template ships ONE universal binary**, `godot_macos_debug.universal`. Setting
  `binary_format/architecture="arm64"` fails with `Requested template binary
  "godot_macos_debug.arm64" not found` — which reads like a missing download and is not. Use
  `"universal"`. Verify what a template actually contains with
  `unzip -l ~/Library/Application\ Support/Godot/export_templates/4.7.1.stable/macos.zip`.
- **An exported app ignores `--script`.** It just runs the main scene. `tools/capture.gd`
  therefore only works against the **editor** binary, not an export. Do not try to screenshot
  an exported build that way — it silently runs the game forever instead.
- `screencapture` from a shell is blocked by macOS Screen Recording permission ("could not
  create image from display"). Not worth pursuing; verify rendering with the editor binary
  and `tools/capture.gd`.

### Known canary blind spots — measured, not assumed

Thirteen perturbations tried across sessions 2–3; **eleven caught, two missed**. Both misses
are understood and neither is a cross-platform risk:

1. **Deferred vs immediate damage application: MISSED, and the miss was correct.** The battle
   loop used to gather blows and apply them afterwards, documented as producing simultaneity.
   It did not: attackers are not alive-checked, so the two are genuinely identical. The
   perturbation proved the buffer was dead code, and it was removed — the golden hash did not
   move, which confirms it. **Simultaneity comes from the absence of an alive check, not from
   the buffer.** Adding one would change the game.
2. **Targeting by true distance instead of squared distance: MISSED.** `sqrt` is monotonic, so
   the ordering is the same except where two distinct squared distances round to the same
   root. That never happens in the workload. Acceptable: `isqrt` is exact and deterministic,
   so this is a behaviour-change risk, not a platform-divergence risk — and the canary is for
   the latter. Squared distance is still preferred, and the reason is documented at the call
   site.

**The general point: run the perturbation, then explain the result.** A miss is sometimes the
test telling you the code was redundant.

### A determinism canary built only from random values misses tie-rounding

Discovered while proving the check, not by reasoning about it. The first
`reference_workload_hash` drew pseudo-random operands and hashed the results. Perturbing
`HALF` in `fx.rs` from 2048 to 2047 — a direct change to the rounding threshold — **did not
fail the test**, because random operands essentially never produce a result of exactly one
half, and that is the only case the change affects.

`determinism.rs::hash_rounding_boundaries` now hashes explicit exact-tie cases for `mul`,
`div`, `round_to_int`, `floor_to_int`, and `sqrt` either side of a perfect square. After
that, all five perturbations are caught.

**Generalise this:** a canary is only sensitive to what its inputs actually exercise. Random
inputs cover the common path and systematically miss boundaries — which is exactly where two
independent implementations diverge. Always add explicit boundary cases, and always verify a
new check by watching it fail.

## Decisions with non-obvious reasoning

### `sim-godot` has no `godot` crate dependency, on purpose

It is an empty `cdylib` + `rlib` stub. Adding `godot` (gdext) now means pinning a binding
version against Godot 4.7 and a multi-minute first build, for a crate with nothing in it. It
goes in at the start of Phase 1, when `sim-core` first has something worth calling.

**This is not an oversight.** The reason is also in a comment in `sim/sim-godot/Cargo.toml`.

### The float lint is a plain `grep`, not an AST walk

`ci/no-floats.sh` is three lines of `grep -rnE '\b(f32|f64)\b' sim/sim-core/src`. It will
also flag `f32` inside a comment or string literal. That is an acceptable false-positive
rate for a check nobody can misread or quietly weaken. Upgrade to a `syn`-based walk only if
it actually becomes annoying — a `ponytail:` comment in the script records this.

**Set up in Phase 0 before any Rust code existed**, deliberately. A lint added after
violations exist gets its first `#[allow]` on day one.

### `export_presets.cfg` is committed

Godot's default `.gitignore` excludes it because it can hold signing paths. Ours is
committed because the mobile configuration (arm64-only, min SDK 24, min iOS 15) is part of
the Phase 0 deliverable and must not drift. Keystore paths and signing identities come from
environment variables; `*.keystore`, `*.jks`, `*.p12`, `*.mobileprovision` are gitignored.

### `sim-core` numeric contract — frozen, do not casually change

Changing any of these invalidates every recorded battle and the golden hash. That is
sometimes correct, but it is never incidental. Say so in the commit message.

- `FIXED_POINT_BITS = 12`, `FIXED_ONE = 4096`, base type `i32`. Range about ±524288.
- **`mul` and `div` both round half toward positive infinity.** `round_div` normalises a
  negative divisor first, because Rust's `/` truncates toward zero and would otherwise round
  negatives the opposite way from positives.
- **Overflow panics in every profile**, via `narrow()`. Deliberately not a `debug_assert` —
  truncation is deterministic *and wrong*, which is the exact failure this crate exists to
  prevent. `overflow-checks = true` is also set on the release profile.
- `fract()` is always in `[0, 1)`, including for negatives, so `floor + fract` reconstructs.
- `sqrt` uses `i64::isqrt` (stdlib, exact, no floating point involved).
- PCG multiplier `6364136223846793005` and default stream `0xda3e39cb94b95bdb` are from the
  reference implementation. A different constant is a different generator.
- `StateHasher` is FNV-1a 64, hand-written. **Never use `std`'s `DefaultHasher`** — it is
  explicitly not stable across releases or platforms, so it would pass every local test and
  then silently disagree between phone and server.
- Multi-byte writes are little-endian **explicitly**, not host-endian.

Golden hash lives in `determinism.rs::tests::EXPECTED_HASH`. If it fails: deliberate change →
recompute and say so; accidental → investigate; one platform green and another red → stop
everything, that is the emergency.

### Landscape 1920×1080, overriding the master plan's 1080×1920

Owner's call during Phase 0 planning. Full reasoning in
`docs/decisions/ADR-0002-landscape-orientation.md`. The master plan is never edited — the
ADR is the correction. **Anywhere the master plan says 1080×1920, it is wrong.**

## Operational constraints to respect

- **Never run ComfyUI and a Blender Cycles render simultaneously.** 24 GB unified memory
  starts swapping and the job takes 10× longer or dies. The pipeline orchestrator must
  serialise GPU stages.
- Qwen-Image-Edit-2509 needs GGUF Q4_K_M on this machine, and takes single-digit minutes per
  image. Use it surgically. Z-Image Turbo is the workhorse for ~90% of generations.
- Batch runners must be resumable and write per-item results. A crash at item 40 must not
  cost items 1–39.
- Blender MCP is allowed **only** in `tools/blender/scratch/` (gitignored). Anything that
  ships comes from a committed headless script.

## Licensing — hard blocks

- **Never Flux Kontext** — the model licence is non-commercial. Never XTTS-v2 — non-commercial
  and the vendor is gone, so there is no path to a licence.
- Permitted: Z-Image Turbo (Apache 2.0), Qwen-Image-Edit-2509 (Apache 2.0), Kokoro
  (Apache 2.0), Chatterbox (MIT).
- Never clone a real person's voice. Log model + prompt + seed for every generated line.
- Model **weights** may be copied from the `mentoros` sibling project. **Code may not.**

## Open questions for the owner

1. **Colour palette** — nine proposed hex values in `docs/ART_BIBLE.md`, deliberately
   unlocked. Blocks bulk asset generation in Phase 2.
2. **Final product name** — "Wastemarch" is a working title. Needs a trademark search before
   any public listing.

### `sim-godot` cannot build without `GODOT4_BIN` — keep it out of the `sim` CI matrix

gdext's `api-custom` feature runs the Godot binary at build time to generate its bindings.
`sim/.cargo/config.toml` hard-codes a local macOS path, which exists on this machine and on
**neither** CI runner. Adding gdext therefore broke CI on both matrix legs at once.

**The failure signature is the useful part.** The `sim` matrix exists to detect
*cross-platform divergence*, which shows as **one leg red and one green**. Both legs red is a
build problem, never a divergence. Do not go looking for an arithmetic bug when both fail.

Structure now: `sim` runs `--workspace --exclude sim-godot` on ubuntu + macos; a separate
`sim-godot` job on ubuntu downloads Godot, sets `GODOT4_BIN` and builds the binding.

Cargo's `[env]` does **not** override a variable already in the environment unless it says
`force = true`. That is what lets CI's `GODOT4_BIN` win over the config file. Never add
`force` there.

### Local `cargo clippy` caches — a clean CI run can fail where local passes

Clippy does not re-lint unchanged crates. `touch sim/*/src/*.rs` before trusting a local
clippy run, or a warning introduced earlier passes locally and fails on CI's fresh checkout.

### The colour palette is locked, and a script owns it

`ADR-0004`. Ten values in `docs/ART_BIBLE.md`. **Do not edit a hex value there without running
`python3 tools/art/palette_check.py`** — it fails the build if two colours with different jobs
become confusable, or if the document and the script disagree about a value. It runs in CI in
the `godot` job.

Three findings worth not re-deriving:

1. **Ochre, gold and firelight all sit within an 8° hue band.** That is intrinsic to the art
   direction — it is a warm palette. Gold clears the others only because it is `#C4942F` and
   because gold is a **metallic material with a highlight**, not a flat fill. If gold ever
   appears as a large flat surface it becomes ochre. The checker still warns about this pair
   on purpose.
2. **Firelight is two values, not one.** `Firelight core #F7CE7C` is the lit surface;
   `Firelight glow #E8A54B` is the colour fire *casts* and is never painted on anything. The
   checker exempts the glow from all comparisons via the job `LIGHT-NOT-SURFACE`. Merging
   them back into one value re-creates the original bug.
3. **Desaturating cannot fix a lightness collision.** An external review suggested moving
   firelight to `#D99543`; measured, that made the protanopia difference *worse* (4.9 → 3.6).
   Two colours that already share a lightness need separating on lightness.

### Lighting on `forward_mobile` is painted, not calculated

"Two hundred lit windows" is emissive texture, not two hundred lights. Budget written into
`docs/ART_BIBLE.md`: one directional sun, **at most six real point lights on screen**,
everything else emissive or a decal. This is an asset-authoring constraint, not a rendering
one — the lit state has to be in the texture, so it has to be in the generation prompt.

Same section: the Duskwood treeline is a **budget item**, not scenery. Always-on-screen at
300 tris a conifer is 60k triangles, a quarter of the scene budget. Instanced low-tri band,
flat cards behind.

### `GRID_SIZE` is a compile-time constant of 44

`sim/sim-core/src/grid.rs`. `Tile::in_bounds` and `Tile::index` are `const fn` built on it.
Two base types of the *same* size cost nothing; two of *different* sizes means making the grid
carry its own dimensions, which touches pathfinding and moves the golden hash. Relevant to the
parked forward-bases idea in `docs/BACKLOG.md` — **if that happens, both bases are 44×44.**

## Image generation — mflux, not ComfyUI (8 Aug 2026)

**ComfyUI is not installed and has not been needed.** `mflux` (MLX, Apple-native) was already
on the machine from the `mentoros` sibling and has first-class commands for both permitted
models: `mflux-generate-z-image-turbo` and `mflux-generate-qwen-edit`. Full write-up in
`docs/ENVIRONMENT.md`.

- Weights: `~/mentoros-imagegen/hf-cache`, 53 GB, **shared not copied**. Set
  `HF_HOME` to it and `HF_HUB_OFFLINE=1`.
- Measured: **16 s/step at 1024², 8 steps ≈ 2 min, peak MLX 10.70 GB.**

### Do not retry: running `mflux-generate-z-image-turbo` without `--model`

It defaults to the full-precision upstream `Tongyi-MAI/Z-Image-Turbo`, which is **not** cached,
and starts a ~16 GB download with **no visible progress**. The symptom is a process sitting at
~5% CPU and 200 MB RSS for twenty minutes with an empty output file — it looks hung, not
downloading. Always:

```
--model filipstrand/Z-Image-Turbo-mflux-4bit --base-model z-image-turbo
```

`HF_HUB_OFFLINE=1` turns that silent hang into an immediate, readable `IncompleteSnapshotError`
naming the missing files. Worth setting for that reason alone.

### The licence-blocked model is in the same cache, one flag away

`models--akx--FLUX.1-Kontext-dev-mflux-4bit` is in `~/mentoros-imagegen/hf-cache` for the other
project. **CLAUDE.md forbids Flux Kontext here — non-commercial licence.** It is not a
hypothetical risk: it is cached, mflux has a `mflux-generate-kontext` binary, and one typo
reaches it.

`tools/pipeline/concept.py` has an explicit allow/block list and **refuses to run** rather than
relying on care. Keep that check when the pipeline grows.

### Stage 3 may still need ComfyUI — open, deliberately not pre-solved

`MASTER_PLAN.md` stage 3 conditions texture generation on Blender-baked depth/normal/AO passes
via ControlNet. mflux supports that for FLUX models but **not** for Z-Image or
Qwen-Image-Edit. Stage 1 does not need it. Do not install ComfyUI speculatively; decide when
stage 3 is actually being built.

## Blender stage 2 — findings from the first real building (8 Aug 2026)

Blender **5.2.0 LTS** headless verified working. `smart_project` (angle in **radians** in 5.x),
`DECIMATE`, and glTF export all present. Entry point:
`$BLENDER --background --factory-startup --python tools/blender/build_asset.py -- --asset granary`

### Do not use DECIMATE for LOD on box geometry

It collapses corners — destroying the silhouette the Art Bible exists to protect — and on the
granary it produced a mesh that `mesh.validate()` reported as needing repair, which glTF then
warned "may be exported wrongly". The base mesh was clean; **the decimate output was the
broken one.**

Replaced with **detail-dropping**: builders take `detail: bool`, and LOD1 is the same builder
run with `detail=False`. Exact, repeatable, silhouette-safe. Also **no LOD1 at all below 400
triangles** — a second mesh costs memory and a draw call, and the granary is 162 triangles.

### "Origin at footprint centre" means the TILES, not the bounding box

The first validator read it as "mesh bounding box must be centred" and failed a building whose
lean-to correctly overhangs. Builders now **declare** their footprint in tiles; the validator
checks the declared footprint and measures overhang separately, capped at `MAX_OVERHANG = 0.35`
so a building cannot sit on its neighbour's tile.

### Texel density is a claim on the shared atlas, not a per-asset texture size

Reporting "the texture size this asset needs" gave **4096×4096 for a 2×2 shed** — arithmetically
right, a unit error in fact. All buildings share one texture sheet (`ART_BIBLE.md`, materials),
so the meaningful number is texels claimed: granary = 39.4 m² × 256² = **2.6M texels**.

**Open and deliberately unresolved:** 256 px/m is 2–4× what a phone actually shows at typical
zoom. Revisit when stage 3 generates real textures. Geometry is unaffected either way, so it is
cheap to defer.

### `ramp()` takes the plank's centre line, not an edge

Passing a wall edge put the granary's lean-to roof a metre off-centre. The overhang check
caught it instantly, which is the whole argument for validating at build time.

### New assets need an editor scan before Godot sees them

Same rule as `.gdextension` files: `--headless --path game --quit` does **not** import a new
`.glb`. Run `--headless --path game --editor --quit` once; that writes the `.import` file and
the `.godot/imported/*.scn`.

### Blender 5.2: the render engine is `BLENDER_EEVEE`, not `BLENDER_EEVEE_NEXT`

Valid values are exactly `('BLENDER_EEVEE', 'BLENDER_WORKBENCH', 'CYCLES')`. The 4.x-era name
`BLENDER_EEVEE_NEXT`, which most examples online still use, raises `TypeError`. Exactly the
5.x drift this file warned about.

### A silhouette test must frame every subject at the SAME scale

`tools/blender/render_and_silhouette.py` first fitted the camera to each building, so a 4.2 m
watchtower and a 2.5 m shed rendered the same size. Size is a large part of how buildings are
told apart in a game where they share the ground, so normalising it away measured something
the player never sees. Fixing it moved granary-vs-keep from **0.69 to 0.33** — the test had
been giving the wrong answer *in the safe direction*, which is the kind that never gets
noticed.

Compare a building against its own upgrade levels too: `keep_L1` vs `keep_L5` is 0.71, the
closest pair in the set and correctly so — the same building, grown.

### Building materials are five palette values, assigned in the builder

`MATERIALS` in `tools/blender/build_asset.py` — stone, timber, thatch, cloth, firelight —
holding the literal hex values locked in ADR-0004. `using("thatch")` sets what following
primitives are made of; the primitives tag their own faces.

**Why this matters beyond convenience:** the palette drift visible in AI concept art cannot
happen to a model, because the model is not asked to interpret a colour, it is given one. Any
later AI texture pass refines *on top of* a correct base rather than being the only source of
colour.

Five is the cap from `ART_BIBLE.md` (max five hues per asset). Adding a sixth means removing
one.

### Judge a building at the locked camera, never in elevation

The watchtower's roof had a comfortable gap under it — correct in a side view, and it
**completely hid the brazier** at 30 degrees elevation, which is the only angle the game has.
The brazier is that building's whole "life" signal.

No amount of care in elevation finds this. `tools/blender/render_and_silhouette.py` renders at
the game camera for exactly this reason, and it is worth looking at its output after any
proportion change, not only when the silhouette numbers move.

## Blender image writing — five attempts, one cause. Do not re-derive.

Writing a modified texture to disk from Blender silently produced **four identical solid-black
PNGs of exactly 27,749 bytes**. The cause, found only by measuring:

**Assigning `image.colorspace_settings.name` on a file-backed image makes Blender re-read the
buffer from disk, discarding every pixel just written.**

The read was never the problem — `pixels.foreach_get` returned a correct mean of 0.372
throughout. The reload *after* the write was.

Working recipe, in this order:

```python
img = bpy.data.images.load(path, check_existing=False)   # source FILE, not GENERATED
px = [0.0] * (w * h * 4); img.pixels.foreach_get(px)
...modify px...
img.pixels.foreach_set(px)
img.update()
img.filepath_raw = str(out_path); img.file_format = "PNG"; img.save()
# and NEVER touch colorspace_settings anywhere in here
```

Also true and wasted two of the five attempts: an image made with `bpy.data.images.new()` has
source `GENERATED`, and `save()` writes its generated buffer rather than assigned `.pixels`,
even after `update()`. Load a real file and modify it in place instead.

**`build_asset.py` now reads the saved file back and fails if its mean brightness is outside
0.02–0.98.** Same lesson as the zero-byte `.so` in the APK: *a file existing is not evidence
that anything is in it.* That check is what turned this from silent black buildings into a
named error.

### glTF cannot carry a shader graph — bake colour into the texture

The exported `.glb` was read back and every material said `baseColorFactor = [1,1,1,1]`:
Blender's exporter had **dropped the palette multiply** and kept only the texture. glTF can
represent `baseColorTexture x baseColorFactor` and essentially nothing else, so any node chain
doing colour work is lost on export.

Two versions looked correct in Blender and exported wrong — the second rendered the buildings
pure black in Godot. **The preview and the game disagreed and the preview was the one lying.**

Fix: tiles arrive already tinted, written by `_palette_tile()`. Base colour is that texture and
nothing else, so there is no node left for an exporter to drop. **Read the `.glb` back when a
material looks wrong** — the JSON chunk is plain text and it answers in seconds what an hour of
staring at renders will not.

### Pick source files by what they ARE, not by what they are not

`_newest_tile()` excluded `_tile.png` by name and took the alphabetically last of the rest.
Then `_normal.png` appeared beside it, which sorts **after** `_1001.png` — so the newest-file
rule silently chose the *normal map* as the base-colour source. Buildings turned pale, lost
their mortar, and nothing failed.

Now it matches `<material>_<digits>.png`. **A blocklist of suffixes grows stale the moment a
new output appears; an allowlist of what a source file looks like does not.**

### Triangle budgets are a ceiling, and the first pass used a sixth of one

The keep was 660 triangles of a 4,000 budget and looked like a massing study beside its own
concept art. Adding a stepped plinth, corner quoins, buttresses, recessed arrow slits and a
proper doorway reveal took it to 1,104 — still 28% of budget — and closed most of the visible
gap.

**Quoins are the best value in the list:** alternating large blocks at each corner, twelve
triangles apiece, and they are the single most recognisable "this is masonry" cue there is.

The scene budget is even slacker: three buildings are 3,436 of 250,000 triangles. Draw calls,
not triangles, are the real mobile constraint — spend geometry freely, add materials never.

## Camera projection — concept art IS the texture (8 Aug 2026)

`tools/blender/project_concept.py`. The owner said the models looked nothing like the concepts
and was right; tiled materials plus palette tinting got the colour *correct* and nowhere near
the concept's *look*.

**The locked camera is what makes this work.** Orthographic, 30/45, no rotation, so every
building sees the camera from the same direction wherever it stands, and zoom changes scale but
not angle. The usual fatal objection to camera projection — right from one angle, smeared from
every other — does not exist here. This is the largest payoff Phase 0's camera decision has had.

Implementation notes worth keeping:

- **`bpy.ops.uv.project_from_view` needs a 3D viewport and cannot run in background mode.**
  Use `bpy_extras.object_utils.world_to_camera_view` per loop instead — for an orthographic
  camera it is the same projection, and it works headless.
- The picked concept is read out of `assets-src/concept/PICKS.md`, not guessed. The choice was
  the owner's and is recorded; nothing in the pipeline gets an opinion about it.
- Alignment is bounding box to bounding box: the model's outline in camera space onto the
  painted building's outline in the image, found by thresholding against the flat background.
- `tex.extension = "EXTEND"` — a concept is not tileable and must never wrap.

### The failure mode, and why it is a feature

Where a model extends past the painted building, the projection samples flat background and
that surface comes out **blank grey**. The keep looks transformed; the granary and watchtower
came out patchy, because their proportions were never tuned against their concepts the way the
keep's were.

So proportion accuracy is now enforced by how the asset *looks* rather than by anyone
remembering to check. Fixing the grey means fixing the model, which is the work that should
have happened anyway.

### Camera projection suits solid forms and fails on skeletal ones — measured

`project_concept.py` reports what fraction of a model's surface lands on empty background.
Every such face renders as a flat grey patch, so the number is exactly the defect that is
visible. Threshold `MAX_UNPAINTED = 0.08`.

| | on background | |
|---|---|---|
| keep | 3.1% | closed box — the paint has somewhere to land |
| granary | 2.7% | after tuning, see below |
| **watchtower** | **57.3%** | open framework, splayed legs, railings, gaps |

`PROJECTED` in `build_asset.py` names which buildings are painted. **The watchtower is not, and
no amount of proportion tuning would fix it** — any strut at a slightly different angle from
the painted one falls on background. Open structures keep the tiled materials, which suit them.

### Tuning a model against its concept is now a measurement loop

The granary went 25% → 14.7% (better-matched concept) → 7.5% (proportions) → **2.7%**. The last
and biggest step was narrowing the lean-to roof from the full width of the building to 62% of
it: a full-width roof stuck out past the painted one and rendered as a large flat grey wedge.

Sweep parameters and read the number. It beats staring at renders, and it found the lean-to
where three rounds of eyeballing had not.

### Concept images must have a FLAT background or they cannot be used as textures

The owner generated a better granary elsewhere, with a vignette and a ground disc. The
alignment step finds the building by thresholding against the background colour, so a gradient
plus a base makes the outline unfindable. The design was regenerated through our own pipeline,
whose style header already demands a flat background — `granary_3002`.

**A concept image is no longer a reference to model from, it is the asset's texture.** Concept
quality is now asset quality directly, and the background instruction is load-bearing.

### Verdict on externally generated .glb files

An AI-generated `granary_isometric.glb` (trimesh) was 7,944 triangles against a 1,500 budget,
13 materials against a one-material rule, 263 meshes, 9x8 metres against a 2x2 footprint, and
**no textures at all**. Not usable — not for looks, but because it fails every budget in
`ART_BIBLE.md` at once. Check these numbers before considering any external asset; they take
one script and settle it.

### The coverage metric was wrong twice before it was right

Both mistakes reported a *lower* number than reality — the direction that never gets caught,
because the tool only ever says "fine".

1. **Weighted by surface area in metres.** A roof seen from 30 degrees above covers far more
   screen than a wall of the same area, so an obviously grey roof measured 3%. Now weighted by
   the polygon's area in projected UV space, which is what the player sees.
2. **Sampled each polygon's centre.** The granary's roof is one large quad whose centre sat on
   the painted roof while half of it hung off into background. One sample said "painted", the
   screen said otherwise. Now samples corners, edge midpoints and inner points, and counts the
   *fraction* of the face that misses.

After both fixes the granary read 13.2% where it had read 2.7%. **When a measurement disagrees
with what is plainly visible, the measurement is wrong — do not tune against it.**

### Paint over the model's own render, do not tune the model to match a painting

`tools/pipeline/repaint.py`: render the model flat at the game camera → Z-Image paints detail
onto that render → project it straight back onto the model it came from.

Tuning proportions against a painting plateaued at ~10% off-model no matter which combination
of body height, ridge, overhang, lean-to width or 90-degree rotation was tried. Painting over
the render took the granary to **1.2%** in one step, because the painting has the model's
proportions by construction.

**`--image-strength` in mflux is INVERTED versus the usual denoise convention.** It is how
strongly the init image *dominates*. Higher keeps the flat render; lower lets the painter
loose. Measured on the granary: 0.82 → 0.3% off-model and almost no painting; 0.42 → 6.7% and
real thatch and stonework; 0.30 → starts inventing geometry.

**Use repaint only where a concept does not already fit.** The keep at 5.7% from its own
concept looks better than the keep repainted, because a concept image is a better painting than
an over-painted render. Repaint is the fallback for models whose concept does not match, not
the default.

### Grey patches: the fix is edge bleed, not better alignment

`dilate_into_background()` in `project_concept.py`. A model's outline will never sit exactly on
a painted building's outline — somewhere a merlon or a roof edge is a few pixels proud, and
every such face sampled flat background and rendered as a grey hole.

Three rounds of proportion tuning shrank it and could not remove it, because **it cannot be
removed by alignment**. Texture atlases solved this decades ago: *padding*. Bleed the artwork
outward past its own edge so anything sampling slightly off picks up plausible colour instead
of emptiness.

Ninety passes of four-neighbour dilation at 1024 — about ninety pixels of skirt, a fraction of
a second with numpy, which **is available inside Blender's Python**. Keep and granary both went
to **0.0% on background** immediately.

**Measure bounds before bleeding.** After the bleed the "building" fills most of the frame, so
`concept_bounds` must run first or the fit is meaningless.

The lesson generalises: when a defect resists three rounds of tuning, the tuning is the wrong
tool. Ask what makes the defect *impossible* rather than what makes it smaller.

### Externally generated .glb, second one, was our own model

`granary_L1_stylized.glb` came back as 162 triangles, 1 mesh, 1 material, bbox identical to
ours — GPT had taken our exported `granary_L1.glb` and re-textured it. Its texture was decent
and it had the same grey patches, because the problem was never the texture. Check `bbox` and
triangle count before assuming an external asset is new work.

### The pale slivers: fit the model INSIDE the painting, not exactly onto it

`INSET = 0.02` in `project_concept.py`. Fitting the two outlines exactly leaves the outermost
geometry sampling the painting's last pixel or the first pixel past it, which produced a pale
sliver down the left silhouette of every building — the concept's brightly lit left wall
bleeding outward.

Bleed and inset are a **pair, not alternatives**: bleed covers gross misalignment, inset covers
the edge itself. Neither alone removed the defect.

Two wrong turns before that, both worth not repeating:

- **`doubleSided` was a red herring.** glTF did export `doubleSided: true` from Blender (fixed
  with `mat.use_backface_culling = True`, which is correct and worth keeping) but culling back
  faces changed nothing visible. Confirming a real problem is not the same as confirming *the*
  problem.
- **Repainting the keep to fix the sliver made it far worse.** At the strength that preserves
  silhouette, the painter barely paints, and the keep lost all its stonework. The sliver was a
  few pixels; the cure removed the whole texture.

Current arrangement: **keep** = its concept, projected, inset. **granary** = repainted at
strength 0.42 then projected, because its concept fits the model badly (30.9% off). **watchtower**
= tiled materials, because it is an open framework.

### Look at art at the size it will be judged

Every art defect in this project has hidden in a full-scene capture, where the buildings are a
few hundred pixels across. The owner found three separate problems by zooming in that
`capture.gd` had reported as fine — and I "fixed" the metric twice while looking at images too
small to show the defect.

`game/tools/zoomcap.gd` renders the preview at 1920x1080 at a chosen ortho size. Use it, not
`capture.gd`, whenever the question is "does this look right".

## Stage 3 done properly: bake to a real unwrap (ADR-worthy, 8 Aug 2026)

`tools/blender/bake_asset.py`. The owner asked the right question — *if the whole model is not
painted like a building, what is the 3D even buying us?* — and the honest answer was: with live
camera projection, very little. It was a 2D image on geometry, with the drawbacks of both.

The pipeline now does what `MASTER_PLAN.md` §7.3 always specified:

1. `smart_project` a real unwrap — every face owns its own pixels
2. project the concept on as a **source only**
3. **bake** it into the real unwrap
4. bake ambient occlusion and multiply it in
5. delete the camera-space UVs so nothing downstream can use them

This removes the inset and bleed hacks *as load-bearing pieces* — they still run, but only to
prepare the source image, and a silhouette sliver can no longer reach the model because nothing
samples a shared image at a shared edge any more.

Blender bake facts worth not rediscovering:

- **Bake target is whichever Image Texture node is selected AND active** in the material node
  tree. Hidden state with no clean API; set `node.select` and `nodes.active` explicitly.
- **Every material on the object needs its own bake target**, or a multi-material object bakes
  only part of itself. That is why `--from-materials` loops over all five.
- `use_pass_direct/indirect = False`, `use_pass_color = True` for DIFFUSE, or the sun gets baked
  into the texture and then lit again in the game.
- Bake needs CYCLES. 24 samples is plenty for AO on box geometry.
- `bake.margin` bleeds past each island; without it seams show.

`--from-materials` bakes the tiled palette materials instead of a projection, for open
structures like the watchtower where projection cannot work. They still get AO, which was the
part they were missing.

**Known regression to fix next: emission does not survive the bake.** The watchtower's brazier
was an emissive material and is now flat pale in the baked albedo. Emissive parts need either a
separate emission texture in the glTF or to stay on their own unbaked material.

### Side-by-side beats opinion: `scratchpad/compare.py` pattern

The owner said the models looked nothing like the concepts and I kept answering with fixes
instead of looking. Rendering each shipped `.glb` at the game camera and stacking it directly
under its concept made the four real gaps obvious in one image:

1. **Sharpness** — one 1024 texture over a whole building holds far less resolution per face
   than a 1024 concept that spent all of itself on three visible sides. Now baked at **2048**.
2. **Lighting** — ambient was 0.6 of neutral grey against a 1.1 sun, so the shadow side was lit
   nearly as brightly as the front. Every model read flat. Now a **warm 2.0 sun against a cool
   0.32 ambient**, which is the hard lit-side/shadow-side split that reads as premium in this
   genre. Biggest single win of the session and it was a two-line change.
3. **Geometry** — the watchtower's ladder, railings and bracing exist but are too thin to read.
   Still open.
4. **Emission was lost in the bake.** `DIFFUSE` drops it. Now bakes `EMIT` to its own texture
   and wires it to Emission Color, which glTF carries natively.

**Render the shipped asset beside its concept before deciding what is wrong.** Three sessions
of fixes went into things that were not the main problem.

### The preview ground had no material

It rendered pure white, blew out under the stronger sun, and made every building look dark by
comparison. Now dead soil `#8B8071` from ADR-0004. The ground is most of the frame in this
game — it can never be a placeholder while judging art.

## The sprite experiment (8 Aug 2026) — concept art standing in the engine

`game/world/SpritePreview.tscn` + `tools/blender/make_sprite.py`. Front row sprites cut from
the concept art, back row the 3D models of the same buildings, same scale, same ground, same
light. Run it and look:

    $GODOT --path game res://world/SpritePreview.tscn

**Result: the sprites look considerably better than the models**, and it is not close. That is
the honest finding and it is worth keeping whichever way the decision goes.

Mechanics that made it work:

- The sprite is sized from the **model's** height in metres, so it stands exactly where the 3D
  building would and is the same size. Without that it is a sticker.
- `billboard = DISABLED` and a fixed 45° yaw. The camera never rotates, so billboarding would
  make buildings swing as the player pans — worse than not tracking at all.
- `ALPHA_CUT_DISCARD`, not blending. Blended transparency does not write depth, so troops would
  draw straight through a building.
- `cast_shadow = OFF`. A flat quad casts a flat quad's shadow and lands a pale parallelogram on
  the ground behind every building, which gives the trick away instantly.
- Background is keyed against the **median of the frame's border**, not the corner pixel. A
  single corner is one sample of a noisy backdrop and made the whole 1024 frame read as subject.

**The remaining halo is not a bug in the cutout.** The concepts have a soft contact shadow
*painted into them*, which is genuinely not background, so it survives the key. That is also
part of why they look better than the models — they carry occlusion the models only got when
AO was baked, and more of it.

## The Phase 2 gate command

    python3 tools/pipeline/build.py --all

Prompt file and builder function are the authored inputs; everything after them — concept art,
geometry, unwrap, 2048/1024 texture with AO and emission, glTF, interface icon, Godot import
and the budget check — runs unattended. Roughly 10–20 s per building without regenerating art.

**Stage 5 of that script verifies the `.glb` by reading it back**, not by trusting the build
log: triangle count, material count, texture count, file size, and that the icon is not blank.
Straight from the Phase 0 lesson where the Android library shipped as zero bytes with a green
build. A build reporting success is not evidence its output contains anything.

### Texture size is per size class, and glTF size is a real constraint

`BAKE_PX_BY_CLASS` — small 1024, large 2048, troop 512. A 2x2 shed was getting the same 2048 as
a 4x4 keep, which made a 162-triangle granary a 16 MB glTF.

Even fixed, textures are **embedded** in each `.glb`: granary 4.8 MB, keep 10 MB. Across 24
buildings x 5 levels that is ~800 MB in Git LFS against a promise of "tens of MB". The shipped
app is fine because Godot recompresses to ASTC. The repository is not. Recorded in
`docs/BACKLOG.md` with two fixes; do it before the set passes about six assets.

### A tileable material must be EVEN at large scale and varied at small scale

The stone tile had strong light and dark patches inside one tile. Tiled across a four-metre
wall those patches became a repeating stain and the keep looked mouldy rather than built.

The prompt now says this outright — "evenly lit across the whole image with no bright patches
and no dark patches, no large scale variation in brightness, detail and roughness only at the
scale of a single block" — rather than hoping for it. Anything that reads as a *patch* inside
one tile becomes a *stain* across a surface.

### Detail below about 8 cm does not exist at the game camera

At 30 degrees from nine metres, a 5 cm railing post is under a pixel. The watchtower's ladder,
railings and bracing were all modelled at 5–7 cm and the tower read as four sticks and a box
beside a concept full of structure. Everything is 9 cm or more now — which is what hand-cut
timber would be anyway — and it reads.

Two related shape lessons from the same pass:

- **Plain cubes read as Lego.** The keep's merlons got a capstone slightly proud of the block,
  twelve triangles each, and they read as dressed masonry instead.
- **Three stacked boxes read as a wedding cake.** The watchtower's roof in stepped courses
  looked wrong; one overhanging eave course under a pyramid reads as a roof.

Budgets had room four times over the whole time: keep 1,488 of 4,000, watchtower 558 of 1,500,
granary 294 of 1,500.

## Phase 3 proof of concept

    $GODOT --path game res://city/City.tscn                       # play it
    $GODOT --headless --path game --script res://tools/city_smoke.gd   # check it

`game/city/city.gd` + `City.tscn`. Place from the bar, click to build, right-drag to pan,
scroll to zoom, `S` save, `L` load. Balance is in `game/data/buildings.json`, all placeholder.

### `add_child()` in `_initialize` does NOT run `_ready` before `_initialize` returns

The node enters the tree when the main loop next iterates, so every field is still empty if
read straight after. The first city smoke test failed with "expected 90, got 0" and **the bug
was in the test**. Do setup in `_initialize`, then wait for `is_inside_tree()` in `_process`
and run the checks there.

### The grid is two lines of `fract` in the ground shader

1,936 tiles as meshes is a draw-call problem and as a texture it is a memory one. In the
shader it is free and crisp at every zoom. `game/city/City.tscn`, `Shader_ground`.

### Camera moves: grab the ground, never accumulate a speed

The first pan multiplied mouse pixels by `size / 600.0` and applied the same number to both
axes. Wrong twice: **600 is nobody's window height**, and at a 30 degree camera the ground is
foreshortened 2:1 vertically, so a vertical drag must move the camera **twice** as far as a
horizontal drag of the same pixel length. The two errors do not cancel; the axes disagree by a
factor of 2 and the world slides diagonally away from the cursor. Measured before the fix: a
240 px horizontal drag left the grabbed point **9.07 m** from the cursor, a 190 px vertical one
**16.97 m**, a diagonal one **26.01 m**.

**The fix needs no multiplier at all.** For an orthographic camera, translating the camera by D
moves the ground point under a fixed pixel by exactly D. So remember the world point under the
cursor at press time, and on every motion do `camera.position += grab - ground_at(mouse)`. It
is exact, it cannot drift, and it stays correct if the camera angle, the zoom or the window
ever change. Zoom-to-cursor is the same three lines with the size change in the middle.

**Test it by asserting the grabbed point stays under the cursor.** That assertion *is* the
definition of correct panning, so it cannot rot into testing an implementation.

**And a right *drag* must not count as a right *click*.** Without a distance threshold, panning
silently deselected whatever was selected, every time.

### Two keys cannot be one key

`S` was bound to save and, when `WASD` panning arrived, to pan-down. Every downward pan wrote a
save file. Save and load are `Ctrl+S` / `Ctrl+L` now. Check the whole keymap when adding a
movement key, not just the one being added.

### Godot picks the tile under the mouse by ray-plane, not physics

The ground is y=0, so intersecting the camera ray with that plane needs no colliders and
cannot be blocked by a building standing in the way. `_cell_under_mouse()`.

### Tint with surface *overrides*, and clear them to reveal the baked texture

`set_surface_override_material` is per instance, so tinting a ghost cannot tint every building
sharing that material. To finish a building, set the override back to `null` rather than
tinting it to white — the baked texture lives on the mesh's own material and any override
hides it permanently.

### `timeout` is not on macOS

`timeout 60 cmd` fails with "command not found" and the command silently does not run, which
looks exactly like a hang. Cost a diagnostic cycle. Use a polling loop instead.

### Put the guard where every caller routes through, not in the caller

Buildings could be placed on top of each other in the Phase 3 city, and `city_smoke.gd` said
overlap was refused — because the test called `_place()` directly while the guard lived in the
click handler. Two different paths, one of them unguarded.

The mechanism was a stale check: `_update_ghost()` skips its work when the cursor has not moved
to a new cell, so after a placement the ghost stayed green over ground it had just taken, and a
second click went straight through.

`_place()` now refuses on its own, and the click handler reads validity from its return value
rather than from cached state. **A guard in the shared function is a smaller diff than a guard
in every caller, and it cannot be bypassed by a caller nobody thought of.**

The test now exercises the same door a player uses. A check that calls a private helper the
player never touches will keep passing while the game is broken.

### Height to footprint is a real constraint, and 0.6 is the limit

*Rewritten 9 Aug 2026. It said 1.6 until Clash of Clans was actually measured; 1.6 was a guess
that felt conservative and was two to four times too permissive. Kept as a warning about
plausible-sounding numbers.*

At 30 degrees elevation a building of height `h` hides roughly **1.7 x h tiles of ground
behind it** on screen. So a tall building on a small base looks placed *through* whatever
stands behind it, however correct its tile occupancy is.

**Measured from CoC screenshots at known zoom** (method in `docs/reference/COC_TEARDOWN.md`):
their Town Hall is **0.55** of its 4x4 footprint tall and its art covers **0.69** of that
footprint. Barracks 0.44. Ours were granary 1.31, watchtower 1.42, keep 0.98 — all far too
tall, which was the whole of the look problem the owner kept reporting.

Now in `build_asset.py`:
- `HEIGHT_TO_FOOTPRINT_LIMIT = 0.6`
- `FOOTPRINT_FILL = 0.8` — a building may not fill more than 80% of its plot. The ring of
  grass is what stops neighbours merging. This replaced the old *overhang allowance*, which
  permitted the exact opposite.
- `reproportion()` squashes a finished model into both limits, and **`build()` is now the one
  way to get a finished object** because `bake_asset.py` built its own copy and skipped the
  squash. Two build paths for one model is a bug waiting to happen; there is now one.

**Do not add a comment block to a `.tscn`.** It loads fine, but the editor rewrites the file
on save and the comment goes silently. Durable "why" belongs in the `.gd`.

`game/tools/pack.gd` places ten buildings shoulder to shoulder and photographs it, which is the
case that keeps producing complaints and is too slow to set up by hand.
