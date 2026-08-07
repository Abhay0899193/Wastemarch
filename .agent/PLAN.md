# PLAN

## RESUME HERE

**Last session:** 8 August 2026 (session 1). **Phase 0, not yet complete.**

**Expected working tree:** clean, on `main`, pushed. Last commit `phase(0): session 1 close`.

**Nothing is half-finished.** All four milestones committed, all verification green.

**First command of the next session** — the session-start protocol from `CLAUDE.md` §1,
then confirm nothing rotted:

```bash
cd /Users/singha7/Documents/abhay/Wastemarch && \
git log --oneline -10 && git status && \
sh ci/no-floats.sh && \
(cd sim && cargo test --workspace) && \
/Users/singha7/Applications/Godot.app/Contents/MacOS/Godot --headless --path game --quit
```

All of that should pass in well under a minute. If it does, pick up at **Next 3 actions**.

**What the next session is waiting on.** Phase 0's gate cannot close without three things,
two of which need the owner:

| | Owner | Status |
|---|---|---|
| Godot export templates (`ios.zip` + Android are missing; only `web_*` present) | owner or engineer | **Blocking.** ~1 GB. Editor → Manage Export Templates → Download and Install. Command also in `docs/ENVIRONMENT.md`. |
| Android SDK + Java | **owner** | Owner said they will install manually and report back. Command in `docs/ENVIRONMENT.md`. |
| iOS signing certificate + self-hosted macOS runner | engineer, needs owner's Apple ID | Not started. |

**Do not start Phase 1 until the gate closes.** Phase gates are real (`CLAUDE.md` §5).
Reviewing the Phase 1 design, or drafting the fixed-point maths on paper, is fine. Committing
Phase 1 code is not.

---

## Phase 0 — Foundation

**Gate (`MASTER_PLAN.md` §9):** a grey cube renders on a physical iPhone **and** a physical
Android device, from a CI-produced build.

**Status: not met.** The cube renders correctly on the Mac under the locked game camera. No
phone build has been attempted, because the export templates for both phone platforms are
absent.

### Next 3 actions

1. **Install the Godot export templates.** Nothing else about the gate can be tested until
   `ios.zip` exists. Verify with
   `ls ~/Library/Application\ Support/Godot/export_templates/4.7.1.stable/ | grep ios`.
2. **Export an iOS debug build locally and install it on the owner's iPhone.** Prove the
   cube renders on real hardware *by hand* before automating it — a manual success makes CI
   failures diagnosable, and the reverse does not.
3. **Stand up a self-hosted macOS runner** and move the `ios` job off
   `workflow_dispatch`. Then the gate reads "from a CI-produced build" honestly.

When the owner reports the Android SDK is installed, action 2 and 3 repeat for Android.

### Milestones — session 1, all committed

- [x] **M0** — Git LFS 3.7.1, `.gitattributes`, `.gitignore`, canonical filenames · `faa5cb3`
- [x] **M1** — `.agent/` working memory + `docs/` (11 files, 2 ADRs) · `15ccdee`
- [x] **M2** — Godot project, landscape mobile, grey cube verified by render · `85c7502`
- [x] **M3** — Cargo workspace, zero-float lint proven, CI skeleton · `ccd6f28`

### Remaining Phase 0 work

- [ ] Godot export templates for iOS and Android — **blocking everything below**
- [ ] iOS signing certificate and provisioning profile
- [ ] Manual iOS build installed on the owner's iPhone, cube confirmed
- [ ] Self-hosted macOS GitHub runner; `ios` job made real
- [ ] Grey cube on the iPhone from a **CI** build
- [ ] **Blocked on owner:** Android SDK + Java. Owner will report when done.
- [ ] Manual Android build, then a CI Android build, cube confirmed
- [ ] On-device check: 60 fps, ≤120 draw calls, ≤250k tris

### Deliberately out of scope for Phase 0

`docs/RELEASE.md` (Phase 7) · colour palette lock (Phase 2) · the `godot` crate in
`sim-godot` (Phase 1) · extra Rust build targets (Phase 1) · Homebrew permission fix (when
next needed). All in `docs/BACKLOG.md` with a reconsider-when.

---

## Phase 1 — Deterministic sim core · not started

First actions when the gate opens, in order:

1. `rustup target add x86_64-unknown-linux-gnu aarch64-linux-android`
2. Add the `godot` crate (gdext) to `sim-godot` and pin it against Godot 4.7.
3. Fixed-point maths and the seeded PCG **before** any entity code — everything else is
   built on them, and retrofitting the number type is a full rewrite.
4. Stand up the cross-platform hash test early, while there is almost nothing to hash. It is
   the Phase 1 gate and it is much easier to keep green than to make green.

`sim/sim-core/src/lib.rs` already fixes `TICKS_PER_SECOND = 20`, `FIXED_POINT_BITS = 12`,
`FIXED_ONE = 4096`.
