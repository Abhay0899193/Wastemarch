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

**M2, M3, close:** see the next entry if this session was interrupted before them.
