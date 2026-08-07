# PLAN

## RESUME HERE

**Last session:** 8 August 2026 (session 4). Working tree clean, on `main`, pushed.
**Nothing is half-finished.**

**Phase 1 is complete except the ARM-device third of its gate.** Everything that can be built
without hardware has been built.

**First command of the next session** — protocol from `CLAUDE.md` §1, then:

```bash
cd /Users/singha7/Documents/abhay/Wastemarch && \
git log --oneline -10 && git status && \
sh ci/no-floats.sh && \
(cd sim && cargo test --workspace --exclude sim-godot && \
          cargo clippy --workspace --exclude sim-godot --all-targets -- -D warnings) && \
/Users/singha7/Applications/Godot.app/Contents/MacOS/Godot --headless --path game --script res://tools/sim_smoke.gd
```

Expect **125 tests green, 1 ignored** and `PASS — the Rust simulation is running inside Godot`.

**Do not run `cargo test --workspace` without `--exclude sim-godot`** unless `GODOT4_BIN` is
set; the binding needs the engine at build time. Its own check is
`cargo build -p sim-godot`, which picks the path up from `sim/.cargo/config.toml`.

**Forced clippy re-lint before trusting a green run:**
`touch sim/*/src/*.rs` first. Clippy caches and will not re-lint unchanged crates.

**The full 10,000-seed sweep** is `#[ignore]`d because it is 157s in debug and 6s in release:
`cargo test -p sim-core --release -- --ignored`.

---

## The two blockers, both the owner's

| | What | Why it is stuck |
|---|---|---|
| **iOS** | `sudo xcodebuild -runFirstLaunch`, once, by someone with admin | `CoreSimulator.framework` is absent and `xcodebuild` will not start without it. **The paid Developer Program does NOT work around this** — see MEMORY. A *free* Apple ID suffices afterwards. |
| **Android device** | Connect a phone with USB debugging on | The APK is built, signed and complete. `adb devices` lists nothing. |

**Nothing else is waiting on either.** Both Phase 0 and Phase 1 gates need physical hardware
and nothing more.

---

## Phase 0 — gate NOT met

- [x] Godot project, mobile renderer, landscape, grey cube verified by render
- [x] Export templates, Android toolchain (user-local, no admin), NDK
- [x] Complete signed APK — `sdkVersion:'24'`, arm64-v8a only, real 100MB sim library
- [ ] **Android device** · **iOS admin action** — owner
- [ ] Self-hosted macOS runner; `ios` CI job made real
- [ ] Both devices from a **CI** build
- [ ] On-device: 60 fps, ≤120 draw calls, ≤250k tris

## Phase 1 — gate NOT met (hardware only)

**Gate:** a headless battle produces an identical state hash on macOS, Linux **and an ARM
device**. The first two agree on every push; the third needs a device.

- [x] `Fx` fixed-point · `Pcg32` · `StateHasher`
- [x] `Grid`, `Entities` (generational ids), `FlowField`
- [x] `Battle` tick loop — targeting, movement, damage, death
- [x] `BattleRecord` + replay, byte encoding, setup fingerprint
- [x] 10,000-seeded-run property test
- [x] Determinism canary — **13 perturbations tried, 11 caught, 2 explained**
- [x] GDExtension: the sim runs inside Godot and agrees with CI
- [ ] **Blocked on a device:** on-device hash agreement

### Next 3 actions, once a device exists

1. Install the APK, run the sim smoke test on-device, compare the hash to CI's.
2. Close both gates, then start Phase 2 (art pipeline) — **which is blocked on the colour
   palette decision**, see below.
3. Add an `aarch64-linux-android` cross-compile check to CI so the Android library cannot
   silently regress to zero bytes again.

### If the owner would rather keep building than wait

Phase 2 (art pipeline) is the master plan's parallel track and does **not** need a device.
Its first real step needs the **colour palette locked** — nine proposed values in
`docs/ART_BIBLE.md`, awaiting the owner. That is the single highest-value decision
outstanding.

---

## Frozen numeric contract

See MEMORY, "`sim-core` numeric contract". Golden hash **`0x6de277a1cf08225b`**, duplicated in
`game/tools/sim_smoke.gd` on purpose and guarded by a test. Changing it invalidates every
recorded battle — sometimes correct, never incidental, always say so in the commit message.

## Deliberately out of scope

`docs/RELEASE.md` (Phase 7) · eight-way movement (Phase 4, if four-way looks wrong) ·
per-tick allocation in the battle loop (Phase 4, marked `ponytail:` at the site) ·
Homebrew permission fix (not needed). All in `docs/BACKLOG.md`.
