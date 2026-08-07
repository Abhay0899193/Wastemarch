# PLAN

## RESUME HERE

**Session in progress — 8 August 2026.** This block is rewritten at session close.

**Current position:** Phase 0, milestone M1 (docs and working memory) being committed.

**Expected working tree:** `.agent/` and `docs/` populated, `game/` and `sim/` not yet
created.

**Next command:**

```bash
cd /Users/singha7/Documents/abhay/Wastemarch && git log --oneline -5 && git status
```

---

## Phase 0 — Foundation

**Gate (`MASTER_PLAN.md` §9):** a grey cube renders on a physical iPhone **and** a physical
Android device, from a CI-produced build.

**Not met yet.** The cube exists; the device half does not.

### Next 3 actions

1. **M2** — Godot 4.7.1 project: `forward_mobile`, 1920×1080 landscape, `canvas_items`
   stretch, directory skeleton per `MASTER_PLAN.md` §5, `Main.tscn` with an orthographic
   camera at 30°/45° and a grey cube, `export_presets.cfg` for iOS and Android.
2. **M3** — Cargo workspace `sim/` with `sim-core` / `sim-godot` / `sim-server` stubs,
   `rust-toolchain.toml` pinned to 1.95.0, `ci/no-floats.sh` proven red-then-green, and
   `.github/workflows/ci.yml`.
3. **Session close** — run the full verification list, update all four `.agent/` files,
   rewrite this RESUME HERE block, confirm a clean tree, push, check CI is green.

### Milestones

- [x] **M0** — Git LFS 3.7.1, `.gitattributes`, `.gitignore`, canonical filenames · `faa5cb3`
- [ ] **M1** — `.agent/` working memory + `docs/` (11 files, 2 ADRs)
- [ ] **M2** — Godot project, landscape mobile, grey cube
- [ ] **M3** — Cargo workspace, zero-float lint, CI skeleton

### Remaining Phase 0 work, beyond this session

- [ ] iOS signing certificates and a provisioning profile
- [ ] Self-hosted macOS GitHub runner (hosted runners cannot hold signing material safely)
- [ ] Grey cube installed on the owner's iPhone from a CI build
- [ ] **Blocked on owner:** Android SDK + Java install — command in `docs/ENVIRONMENT.md`.
      Owner will report when done.
- [ ] Grey cube installed on a physical Android device from a CI build
- [ ] On-device confirmation of 60 fps and the draw-call budget

### Deliberately out of scope for Phase 0

`docs/RELEASE.md` (Phase 7), the colour palette lock (Phase 2), the `godot` crate dependency
in `sim-godot` (Phase 1), extra Rust build targets (Phase 1). All recorded in
`docs/BACKLOG.md` with a reconsider-when.

---

## Phase 1 — Deterministic sim core · not started

Do not begin until the Phase 0 gate above is objectively met. Phase gates are real
(`CLAUDE.md` §5).

First actions when it opens: add `rustup target add x86_64-unknown-linux-gnu` and the
Android targets, add the `godot` crate to `sim-godot`, then fixed-point maths and the seeded
PCG before any entity code.
