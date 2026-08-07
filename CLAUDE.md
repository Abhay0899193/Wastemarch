# CLAUDE.md — Operating rules for Wastemarch

You are the sole engineer on **Wastemarch**, a mobile isometric base-builder + real-time strategy game.
The authority for *what* to build is `MASTER_PLAN.md`. This file governs *how* you work.

---

## 1. Session protocol — non-negotiable

### At the start of EVERY session

1. Read `.agent/STATE.json`
2. Read `.agent/PLAN.md` — the **RESUME HERE** block is at the top
3. Read `.agent/MEMORY.md`
4. Read the last two entries in `.agent/JOURNAL.md`
5. Run `git log --oneline -10` and `git status`
6. Say, in one short paragraph: what phase we're in, what happened last session, what you're doing now
7. Then work

Do not skip this even if the session feels like a continuation.

### At EVERY milestone (roughly every 45–90 minutes of work)

1. Run tests: `cargo test -p sim-core` and the Godot validator
2. Update `.agent/PLAN.md` — tick completed items, rewrite the **Next 3 actions** block
3. Update `.agent/MEMORY.md` if anything durable was learned
4. Append a dated entry to `.agent/JOURNAL.md`
5. Update `.agent/STATE.json`
6. Update any `docs/` file the change affected
7. `git add -A && git commit -m "phase(N): <what changed>"`
8. Report to the user in **three lines or fewer**

### At session close — mandatory

1. Do the full milestone sequence above
2. `git status` must be clean. If it isn't, commit the remainder as `wip: <description>`
3. Write a **RESUME HERE** block at the top of `.agent/PLAN.md` with:
   - the exact next command to run
   - the expected state of the working tree
   - anything left half-finished
4. Push

**Never end a session with uncommitted work.** This rule has no exceptions.

---

## 2. Local environment

Verify these on first run and record the results in `docs/ENVIRONMENT.md`. Do not assume — `ls` first.

```bash
# Expected locations (confirm actual .app names)
/Users/singha7/Applications/Godot.app/Contents/MacOS/Godot     --version
/Users/singha7/Applications/Blender.app/Contents/MacOS/Blender --version
```

Pin exact versions in `docs/ENVIRONMENT.md`. Target: **Godot 4.7.1-stable**. If the installed version differs, stop and tell the user before proceeding.

Common invocations:

```bash
# Headless Blender asset build
$BLENDER --background --factory-startup --python tools/blender/build_asset.py -- --asset town_hall

# Headless Godot import + validation
$GODOT --headless --path game --script res://tools/validate_assets.gd

# Determinism test
cargo test -p sim-core --release -- --nocapture
```

---

## 3. Hard technical rules

### Simulation (`sim/sim-core`)
- **Zero floating-point.** No `f32`, no `f64`, anywhere in `sim-core`. Fixed-point integer maths only. There is a CI lint for this — do not bypass it.
- No I/O, no system time, no threading, no engine types. Inputs in, deterministic state out.
- All randomness from a single seeded PCG. The seed is part of the battle record.
- Fixed 20 Hz tick. Rendering interpolates; rendering never writes to sim state.
- Every change to sim logic must keep the cross-platform hash test green (macOS + Linux + arm64 must agree bit-for-bit).

### Godot (`game/`)
- Renderer: **Mobile** (`forward_mobile`). Never Forward+.
- Budgets, enforced by the asset validator: **≤120 draw calls, ≤250k tris on screen, 60 FPS on iPhone 12 / Pixel 6a.**
- Repeated props (walls, trees, crops, decor) use `MultiMeshInstance3D`. Never hundreds of individual nodes.
- One shared material per art tier so Godot can batch.
- Shipped textures are KTX2 + ASTC. No PNG in the build.
- Object-pool everything spawned during a battle. Zero allocation mid-battle.
- **All balance values live in `game/data/` as `.tres`/`.json`.** Zero magic numbers in code.
- GDScript is statically typed. `class_name` on anything reused.

### Assets
- No asset ships without passing `tools/pipeline/validate.py`: poly budget, texel density, correct scale (1 unit = 1 m), origin at footprint centre, no n-gons, no loose geometry.
- Every generated asset records model name, prompt, seed, and workflow hash in its manifest entry. This is both reproducibility and legal provenance.
- **Only Apache-2.0 / MIT models.** Z-Image Turbo, Qwen-Image-Edit-2509, Kokoro, Chatterbox. **Never Flux Kontext, never XTTS-v2** — both are licence-blocked for commercial use.
- Blender MCP is allowed **only** in `tools/blender/scratch/`. Anything that ships must come from a committed, headless-runnable Python script.

### What never enters this project
No ads or ad SDKs. No loot boxes. No pay-to-win. No runtime LLM calls. No user chat or UGC in V1. No Firebase. No code copied from any sibling project (model *weights* may be copied; code may not).

---

## 4. Docs — write for a non-programmer

`docs/` is for the project owner, who is not reading the source.

- Short sentences. Define every technical term the first time it appears.
- Every doc opens with a 3-sentence **"What this is"** block.
- Diagrams in Mermaid so they render on GitHub.
- `docs/README.md` is an index with one line per document.
- A stale doc is a bug. Fix it in the same commit as the code that made it stale.

`.agent/` is for you, and can be as technical as you like — but keep it current, because a future session with none of this context depends entirely on it.

---

## 5. Working style

- **Phase gates are real.** Do not start Phase N+1 until Phase N's "done when" criterion in the master plan is objectively met.
- New ideas go in `docs/BACKLOG.md`. They never get quietly added to the current phase.
- Any decision not already settled by `MASTER_PLAN.md` → **ask the user first**, then record it as an ADR in `docs/decisions/`.
- Test on a **physical device** at the end of every phase. The simulator lies about performance.
- When something fails twice the same way, write it in `.agent/MEMORY.md` under "Do not retry" before trying a third approach.
- Prefer boring, obvious code. This project is long; cleverness costs more than it saves.
- Keep responses to the user short. They have been watching the task list.