# Testing — the checks that guard the project

**What this is.** This lists every automatic check the project runs, what each one protects
against, and how to run it yourself. Right now there are four; more arrive with each phase.
The list is short on purpose — a check that nobody trusts is worse than no check.

---

## Run everything

```bash
export GODOT=/Users/singha7/Applications/Godot.app/Contents/MacOS/Godot

sh ci/no-floats.sh                      # 1. no decimal numbers in the simulation
cd sim && cargo test --workspace && cd ..   # 2. the simulation's own tests
cd sim && cargo clippy --workspace -- -D warnings && cd ..   # 3. code quality
$GODOT --headless --path game --quit    # 4. the game project imports cleanly
```

All four also run automatically on GitHub every time anything is pushed. If any one of them
fails, the change is marked broken.

---

## 1. No decimal numbers in the simulation

```bash
sh ci/no-floats.sh
```

**What it protects.** The simulation must produce byte-for-byte identical results on an
iPhone, an Android phone, and a Linux server. Decimal ("floating-point") arithmetic can
differ very slightly between processor designs, and one tiny difference cascades into two
machines completely disagreeing about who won a battle. Full explanation in
[ARCHITECTURE.md](ARCHITECTURE.md#the-important-idea-determinism).

**How it works.** It searches the simulation core's source for the two decimal number types
and fails if it finds either.

**Why it exists already, with no code to check.** It was deliberately set up in Phase 0,
before the simulation was written. A rule introduced *after* the violations exist gets
suppressed with an exception "just this once." A rule that has been green since the first
day never accumulates one.

**Known limitation.** It is a plain text search, so it would also flag the letters `f32`
inside a comment or a piece of text. That is a fair trade for a check that is three lines
long and impossible to misunderstand. If it ever becomes annoying, it gets upgraded to
something that understands code structure.

**Proven working.** On 8 August 2026 a decimal number was deliberately added to the
simulation, the check was confirmed to fail, and it was removed. A check that has never been
seen to fail is not a check.

## 2. The simulation's tests

```bash
cd sim && cargo test --workspace
```

**What it protects.** That the simulation's rules do what they are supposed to.

**Currently.** The crates are empty stubs with one trivial test each, which proves the test
machinery itself is correctly wired. The real tests arrive in Phase 1, including the
important one: run the same battle ten thousand times with ten thousand different seeds and
confirm the results are reproducible every time.

## 3. Code quality

```bash
cd sim && cargo clippy --workspace -- -D warnings
```

**Clippy** is Rust's built-in advisor — it points out code that works but is fragile,
confusing, or slower than it needs to be. `-D warnings` means treat every one of its
suggestions as an error rather than a note.

**What it protects.** Small problems compounding. Over six months, warnings you can ignore
become warnings everyone ignores, and then a real one hides among them.

## 4. The game project imports cleanly

```bash
$GODOT --headless --path game --quit
```

**What it protects.** That the Godot project actually opens, every file it references
exists, and nothing is corrupt. Cheap, fast, and catches broken references immediately
instead of when someone next opens the editor.

**Headless** means with no window and no graphics — how a computer runs a task unattended.

---

## Checks that arrive later

| Check | Arrives | What it will protect |
|---|---|---|
| Cross-platform determinism | Phase 1 | The same battle on macOS, Linux, and an ARM chip must produce an identical result hash. This is the Phase 1 completion test. |
| Asset budget validation | Phase 2 | Every 3D asset within its triangle budget, correct scale, correct texel density, no bad geometry. |
| Silhouette legibility | Phase 2 | Every building still identifiable as a solid black shape at 64 pixels. |
| Replay determinism | Phase 4 | A battle replays identically from its record, twice. The Phase 4 completion test. |
| On-device performance | Phase 3 onward | 60 frames per second on an iPhone 12 and a Pixel 6a, within 120 draw calls and 250,000 triangles. |

---

## The check no script can perform

**Testing on a real phone at the end of every phase.**

The simulator on your Mac runs the game on desktop hardware. It will happily report smooth
performance for something that stutters badly on an actual phone, and it does not model heat,
battery drain, or what happens when the phone throttles itself after ten minutes.

**The simulator lies about performance.** Every phase ends on real hardware.
