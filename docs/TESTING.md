# Testing — the checks that guard the project

**What this is.** This lists every automatic check the project runs, what each one protects
against, and how to run it yourself. Right now there are five; more arrive with each phase.
The list is short on purpose — a check that nobody trusts is worse than no check.

---

## Run everything

```bash
export GODOT=/Users/singha7/Applications/Godot.app/Contents/MacOS/Godot

sh ci/no-floats.sh                      # 1. no decimal numbers in the simulation
cd sim && cargo test --workspace && cd ..   # 2 & 5. the simulation's tests
cd sim && cargo clippy --workspace -- -D warnings && cd ..   # 3. code quality
$GODOT --headless --path game --quit    # 4. the game project imports cleanly
```

All of these also run automatically on GitHub every time anything is pushed, and the
simulation tests run on **two different kinds of computer at once** — see check 5. If any one
of them fails, the change is marked broken.

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

**Currently 92 tests**, covering the foundation pieces built so far:

- **Fixed-point arithmetic** — that adding 4096 smallest steps makes exactly one with no
  drift, that multiplication gives the same answer whichever way round you write it, that
  positive and negative numbers round by the same rule, that overflow stops the program
  rather than producing a wrong number quietly.
- **The random number generator** — that the same seed replays identically (checked across
  10,000 different seeds), that nearby seeds do not produce similar results, and that a
  six-sided die rolled 60,000 times lands about 10,000 times on each face.
- **State hashing** — checked against the published reference values for the algorithm, so
  a future change that quietly alters it cannot go unnoticed.
- **The world grid** — that writing outside the grid is ignored rather than corrupting some
  distant tile, and that the cost of crossing a whole map of the slowest terrain cannot
  overflow (if it could, a long route would come back looking cheap and troops would walk the
  wrong way).
- **Units and buildings** — that a reference to a dead unit fails rather than silently
  pointing at whoever reused its slot.
- **Finding a way around walls** — that every step gets strictly closer, which is what
  guarantees troops cannot walk in circles forever; that a walled-in troop stops instead of
  spinning; and that mud is walked around when that is cheaper and through when it is not.

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

## 5. Cross-platform determinism

```bash
cd sim && cargo test -p sim-core determinism
```

**What it protects.** The single most important property in the project: that a Mac, a Linux
server and a phone all compute the *same answer*. Full explanation of why in
[ARCHITECTURE.md](ARCHITECTURE.md#the-important-idea-determinism).

**How it works.** A fixed workload runs a minute of simulated time — 1,200 steps of adding,
multiplying, dividing, square roots and random draws — and squeezes the whole thing down to
one 64-bit number. That number is written into the code as a constant. Every machine that
runs the test must produce it exactly.

It runs automatically on **both** Intel Linux and Apple Silicon macOS on every push. If the
two ever disagree, one goes red and the other stays green, and the disagreement is
impossible to miss.

**If this test fails, do not change the expected number to make it pass.** A failure means
one of three things: the simulation was changed deliberately (recompute it, and note in the
commit message that previously recorded battles no longer replay), it was changed by
accident (find out how), or two platforms genuinely disagree (stop everything). Only the
first justifies a new number.

**Proven working.** On 8 August 2026, **nine** separate one-line changes were made to the
simulation and the test was confirmed to catch every one: a shifted rounding threshold,
multiplication truncating instead of rounding, division rounding the other way, a
random-number constant changed by 2, a square root off by one step, the order neighbouring
tiles are examined in, a queue ordering made ambiguous, a tie broken the other way, and the
cost of mud changed by one.

That exercise also found a real gap. The first version of the workload used only
randomly-chosen numbers, and *missed* the shifted rounding threshold — because random values
almost never land exactly on a half, which is the only case that change affects. Values that
sit exactly on a rounding boundary are precisely where two implementations diverge, so a set
of them is now included deliberately. **This is why a check has to be watched failing before
it can be trusted.**

## Checks that arrive later

| Check | Arrives | What it will protect |
|---|---|---|
| Determinism on a real phone | Phase 1 | The check above covers Linux and macOS. The Phase 1 gate also requires an ARM device to agree. |
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
