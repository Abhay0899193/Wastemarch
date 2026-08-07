# PLAN

## RESUME HERE

**Last session:** 8 August 2026 (session 2). **Phase 0 gate still open. Phase 1 started
partially, deliberately.**

**Expected working tree:** clean, on `main`, pushed.

**Nothing is half-finished.**

**First command of the next session** — the protocol from `CLAUDE.md` §1, then:

```bash
cd /Users/singha7/Documents/abhay/Wastemarch && \
git log --oneline -10 && git status && \
sh ci/no-floats.sh && \
(cd sim && cargo test --workspace && cargo clippy --workspace --all-targets -- -D warnings) && \
/Users/singha7/Applications/Godot.app/Contents/MacOS/Godot --headless --path game --quit
```

Expect 46 tests green and no errors.

**Also check, if the owner has opened the Godot editor since:** it rewrites
`game/project.godot` and strips comments. Confirm the settings listed in MEMORY under
"Comments in game/project.godot do not survive" are still correct.

---

## Why Phase 1 started with Phase 0's gate open

The owner asked for it while installing the export templates. The gate was flagged, and the
split was drawn where it actually means something:

- **Started:** `sim-core`. Pure Rust, no Godot dependency, its own correctness verified by
  CI on Linux and macOS. Phase 0's gate — a cube on a phone — cannot affect any of it.
- **NOT started:** the `godot-rust` GDExtension. It needs the export templates and a device,
  which is exactly what the gate guards. **Do not start it until the gate closes.**

If a future session is tempted to pull the GDExtension forward: that is the one piece where
the gate is load-bearing. Everything else in Phase 1 is safe.

---

## Phase 0 — Foundation · gate NOT met

**Gate:** a grey cube renders on a physical iPhone **and** a physical Android device, from a
CI-produced build.

| Blocker | Owner | Status |
|---|---|---|
| Godot export templates — `ios.zip` and Android absent, web only | owner (in progress) | **Blocking.** Verify: `ls ~/Library/Application\ Support/Godot/export_templates/4.7.1.stable/ \| grep ios` |
| iOS signing certificate + provisioning profile | engineer, needs owner's Apple ID | Not started |
| Self-hosted macOS runner (hosted runners cannot hold signing material) | engineer | Not started |
| Android SDK + Java | **owner** | Owner will report when done. Command in `docs/ENVIRONMENT.md`. Needs `sudo chown -R $(whoami) /usr/local/bin` first. |

### Remaining Phase 0 work, in order

- [ ] Export templates present
- [ ] Manual iOS export installed on the owner's iPhone, cube confirmed **by hand first** —
      a manual success makes a CI failure diagnosable; the reverse is not true
- [ ] Self-hosted macOS runner; `ios` job moved off `workflow_dispatch`
- [ ] Cube on the iPhone from a **CI** build
- [ ] Same two steps for Android once the SDK lands
- [ ] On-device check: 60 fps, ≤120 draw calls, ≤250k tris

---

## Phase 1 — Deterministic sim core · foundations done

**Gate:** a headless battle produces an identical state hash on macOS, Linux, **and an ARM
device**.

Two thirds of that gate already runs on every push — the CI `sim` job is a matrix over
`ubuntu-latest` and `macos-latest`, and `sim-core` carries a golden hash of a reference
workload. The ARM-device third needs the GDExtension, so it waits on Phase 0.

### Next 3 actions

1. **Grid and entities.** Fixed 44×44 tile grid, entity storage with stable identifiers.
   Stable ordering is mandatory — **never iterate a `HashMap`** in simulation code; its order
   is not deterministic and the state hash will expose it as a desync. Prefer dense `Vec`
   indexed by a generational id.
2. **Extend the determinism canary** to cover the grid and entities as they land, rather
   than after. It is far easier to keep green than to make green.
3. **Flow-field pathfinding.** The one algorithm here with real subtlety; do it after the
   grid is settled and tested.

Then, once the Phase 0 gate closes: the `godot` crate in `sim-godot`, plus
`rustup target add x86_64-unknown-linux-gnu aarch64-linux-android`.

### Done

- [x] **M4** — fixed-point `Fx` type, 21 tests
- [x] **M5** — PCG32, FNV-1a state hashing, determinism canary proven against five
      perturbations, CI matrix over Linux + macOS

### Frozen numeric contract

See MEMORY, "`sim-core` numeric contract". Changing any of it invalidates every recorded
battle and the golden hash. Sometimes correct; never incidental. Say so in the commit message.

### Still to build

- [ ] Grid, entities
- [ ] Flow-field pathfinding
- [ ] Targeting, damage
- [ ] `BattleRecord` and replay
- [ ] Property tests over 10,000 seeded battles
- [ ] **Blocked on Phase 0:** GDExtension, on-device hash agreement

---

## Deliberately out of scope

`docs/RELEASE.md` (Phase 7) · colour palette lock (Phase 2, **blocks bulk asset work**) ·
Homebrew permission fix (when next needed). All in `docs/BACKLOG.md` with a reconsider-when.
