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
