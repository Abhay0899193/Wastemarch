# MEMORY — durable facts, gotchas, and things not to retry

Append-only in spirit. Delete an entry only when it becomes factually wrong, and say so in
JOURNAL.md when you do.

---

## Environment

- **Godot** `4.7.1.stable.official.a13da4feb` at
  `/Users/singha7/Applications/Godot.app/Contents/MacOS/Godot`. Matches the target exactly.
- **Export templates are WEB-ONLY.** The `4.7.1.stable` template directory exists and looks
  populated, but holds only the eight `web_*.zip` files. `ios.zip` and the Android templates
  are absent, so both phone exports fail at the first step. **Do not assume "the directory
  exists" means "templates are installed" — always `ls` for the specific file.** Fix and
  verification command in `docs/ENVIRONMENT.md`. Blocks the Phase 0 gate.
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
