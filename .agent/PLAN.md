# PLAN

## RESUME HERE

**Last session:** 8 August 2026 (session 3). Working tree clean, on `main`, pushed.
**Nothing is half-finished.**

**First command of the next session** — protocol from `CLAUDE.md` §1, then:

```bash
cd /Users/singha7/Documents/abhay/Wastemarch && \
git log --oneline -10 && git status && \
sh ci/no-floats.sh && \
(cd sim && cargo test --workspace && cargo clippy --workspace --all-targets -- -D warnings) && \
/Users/singha7/Applications/Godot.app/Contents/MacOS/Godot --headless --path game --script res://tools/sim_smoke.gd
```

Expect **92 tests green** and `PASS — the Rust simulation is running inside Godot`.

**If the smoke test says WastemarchSim is not registered:** the dylib is stale or the editor
has not scanned. Run `cd sim && cargo build` then
`$GODOT --headless --path game --editor --quit` once.

**If the owner has opened the Godot editor since:** it rewrites `game/project.godot` and
strips comments. Check the settings list in MEMORY under "Comments in game/project.godot do
not survive".

### Next 3 actions

1. **Targeting** — which enemy a unit picks. Ties must break by `EntityId`, never by
   iteration accident. Extend the canary as it lands, not after.
2. **Damage and the tick loop** — a `step()` that actually advances a battle: move along the
   flow field, acquire targets, apply damage, remove the dead. This is where `TICKS_PER_SECOND`
   finally means something.
3. **`BattleRecord`** — `{ seed, base_snapshot_hash, Vec<TimedInput> }`, and replay. Then the
   10,000-seeded-battles property test the master plan asks for.

### The two blockers, both needing the owner

| | Owner | What |
|---|---|---|
| **iOS** | someone with admin | `sudo xcodebuild -runFirstLaunch`, once. Then a **free** Apple ID is enough. **The paid programme does NOT work around this** — see MEMORY. |
| **Android device** | owner | Connect a phone with USB debugging on. The APK is built and complete; `adb devices` lists nothing. |

Nothing else in Phase 1 is waiting on either of them.

---

## Phase 0 — gate NOT met

**Gate:** grey cube on a physical iPhone **and** a physical Android device, from a CI build.

- [x] Godot project, mobile renderer, landscape, grey cube verified by render
- [x] Export templates (owner installed the full set)
- [x] Android toolchain, user-local, no admin
- [x] **Complete signed APK** — 123MB, `sdkVersion:'24'`, arm64-v8a only, real 100MB sim
      library. Verified by reading the artifact, not the settings.
- [x] Placeholder `icon.svg`
- [ ] **Android device** — owner
- [ ] **iOS admin action** — owner
- [ ] iOS signing (free Apple ID, after the admin step)
- [ ] Self-hosted macOS runner; `ios` CI job made real
- [ ] Both devices from a **CI** build
- [ ] On-device: 60 fps, ≤120 draw calls, ≤250k tris

---

## Phase 1 — Deterministic sim core

**Gate:** a headless battle produces an identical state hash on macOS, Linux, **and an ARM
device**.

macOS and Linux agree on every push (CI matrix). The ARM third needs a device.

### Done

- [x] `Fx` fixed-point, `Pcg32`, `StateHasher`
- [x] Determinism canary, **proven against 9 perturbations** across three extensions
- [x] `Grid` — 44×44, terrain, move costs
- [x] `Entities` — generational ids, no `HashMap`
- [x] `FlowField` — Dijkstra, deterministic tie-breaking
- [x] GDExtension: the sim runs inside Godot and agrees with CI

### Still to build

- [ ] Targeting
- [ ] Damage + the tick loop
- [ ] `BattleRecord` + replay
- [ ] 10,000-seeded-battle property test
- [ ] Cross-compile checks in CI for the Android target
- [ ] **Blocked on a device:** on-device hash agreement

### Frozen numeric contract

See MEMORY, "`sim-core` numeric contract". Golden hash **`0x60d0b217ca281e07`**, duplicated
in `game/tools/sim_smoke.gd` on purpose and guarded by a test. Changing it invalidates every
recorded battle — sometimes correct, never incidental, always say so in the commit message.

---

## Deliberately out of scope

`docs/RELEASE.md` (Phase 7) · colour palette lock (Phase 2, **blocks bulk asset work**) ·
eight-way movement (Phase 4, if four-way looks wrong on screen) · Homebrew permission fix
(not needed — everything installs under `$HOME`). All in `docs/BACKLOG.md`.
