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
- **Rust 1.95.0**, only `aarch64-apple-darwin` installed. Phase 1's cross-platform
  determinism test needs Linux and Android targets added.
- Xcode 26.3 present → iOS builds are possible. **No Android SDK and no Java.** The owner
  will install those manually and report back; the command is in `docs/ENVIRONMENT.md`.

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
