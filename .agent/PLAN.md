# PLAN

## RESUME HERE

**Last session:** 8 August 2026 (session 5). Working tree clean, on `main`, pushed.
**Nothing is half-finished.**

**Phase 1's ARM leg is verified — on an emulator, not yet on a phone.** The Android build of
the simulation produces `0x6de277a1cf08225b`, the same hash as macOS and Linux, running on a
real `arm64-v8a` Android system. See `docs/TESTING.md` check 6.

**One open question for the owner: does that close the Phase 1 gate?** The emulator is the
same Apple M4 Pro silicon as the macOS leg, so it proves the Android toolchain and ABI agree
but not that a Qualcomm chip does. `sim-core` is pure integer, which is exactly why that is a
small risk. The gate is left **open** pending the owner's call and a physical phone.

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
| **Android device** | Connect a phone with USB debugging on | Only **performance** now needs it. Correctness is answered by the emulator. `adb devices` lists no physical device. |

**The emulator removed the correctness half of the Android blocker.** What is still hardware-only:
frame rate, draw calls, triangle count, heat and throttling — the Phase 0 budget gate. iOS is
unchanged and still needs the admin password.

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
- [x] On-device hash agreement — **Android emulator, `arm64-v8a`, hash matches CI**
- [ ] Same, on a physical phone — owner's call whether the gate needs it

### Next 3 actions

1. **Owner decides** whether the emulator closes the Phase 1 gate, or whether a physical
   phone is required. Everything else is unblocked either way.
2. Add an `aarch64-linux-android` cross-compile check to CI. The first emulator run failed on
   a **stale** `.so`, not a real divergence (see MEMORY) — CI building that target would have
   caught it, and would also stop the library silently regressing to zero bytes again.
3. Start Phase 2 (art pipeline) — **blocked on the colour palette decision**, see below.

### If the owner would rather keep building than wait

Phase 2 (art pipeline) is the master plan's parallel track and does **not** need a device.
Its first real step needs the **colour palette locked** — nine proposed values in
`docs/ART_BIBLE.md`, awaiting the owner. That is the single highest-value decision
outstanding.

---

## Frozen numeric contract

See MEMORY, "`sim-core` numeric contract". Golden hash **`0x6de277a1cf08225b`**, duplicated in
`game/tools/sim_checks.gd` on purpose and guarded by a test. Changing it invalidates every
recorded battle — sometimes correct, never incidental, always say so in the commit message.

## Deliberately out of scope

`docs/RELEASE.md` (Phase 7) · eight-way movement (Phase 4, if four-way looks wrong) ·
per-tick allocation in the battle loop (Phase 4, marked `ponytail:` at the site) ·
Homebrew permission fix (not needed). All in `docs/BACKLOG.md`.
