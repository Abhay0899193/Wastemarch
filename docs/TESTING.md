# Testing — the checks that guard the project

**What this is.** This lists every automatic check the project runs, what each one protects
against, and how to run it yourself. Right now there are eight; more arrive with each phase.
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

Check 6 is the exception: it needs an emulated Android phone running on your Mac, so it is
run by hand rather than on GitHub.

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

**Proven working.** On 8 August 2026, **thirteen** separate one-line changes were made to the
simulation and the test was confirmed to catch every one: a shifted rounding threshold,
multiplication truncating instead of rounding, division rounding the other way, a
random-number constant changed by 2, a square root off by one step, the order neighbouring
tiles are examined in, a queue ordering made ambiguous, a tie broken the other way, the cost
of mud changed by one, the order the steps of a battle happen in, and two ways of choosing
which enemy to attack.

**Two of the thirteen were not caught, and both taught us something.** One showed that a piece
of the battle code believed to matter actually did nothing at all — it was removed, and the
number did not change, which proved the point. The other is a change the check genuinely
cannot see, and it is not the kind of change this check exists to catch. Both are written
down rather than glossed over.

That exercise also found a real gap. The first version of the workload used only
randomly-chosen numbers, and *missed* the shifted rounding threshold — because random values
almost never land exactly on a half, which is the only case that change affects. Values that
sit exactly on a rounding boundary are precisely where two implementations diverge, so a set
of them is now included deliberately. **This is why a check has to be watched failing before
it can be trusted.**

## 6. The simulation agrees with itself on an Android phone

**What it protects against:** the same arithmetic giving a different answer once it is compiled
for a phone's processor rather than a computer's. If that ever happened, two players' phones
could watch the same battle end differently, and nothing else in this list would notice.

Check 5 compares a Mac and a Linux server. This check adds a third, genuinely different
machine: the Android build of the simulation, running on an Android system, on an ARM
processor. It runs in an **emulator** — a full Android phone simulated on the Mac — so it
needs no hardware.

```bash
export ADB=~/Android/sdk/platform-tools/adb
export GODOT=/Users/singha7/Applications/Godot.app/Contents/MacOS/Godot

# 1. Start the emulated phone (leave it running; it takes about half a minute to boot).
~/Android/sdk/emulator/emulator -avd wastemarch_p6a -no-snapshot -no-boot-anim &

# 2. Build the simulation for phone processors, then package the game.
(cd sim && cargo build -p sim-godot --target aarch64-linux-android)
"$GODOT" --headless --path game --export-debug "Android" /tmp/wastemarch.apk

# 3. Install it and read what it says.
$ADB install -r /tmp/wastemarch.apk
$ADB logcat -c
$ADB shell am start -n com.wastemarch.game/com.godot.game.GodotAppLauncher
sleep 20 && $ADB logcat -d | grep "godot   :"
```

**What a pass looks like** — the last line must read:

```
PASS — the Rust simulation is running inside Godot and agrees with CI
```

and the hash line above it must show the same value as `sim/sim-core/src/determinism.rs`.

**Step 2 is not optional.** The game package contains a *copy* of the simulation built for
phones. If you skip the build, the copy is whatever was built last time, and the check will
report a mismatch that looks exactly like a real cross-platform bug but is only a stale file.
This happened on the very first run of this check.

**What this check does NOT cover: speed, or anything you can see.** The emulator borrows the
Mac's graphics card, so its frame rate means nothing, and a screenshot of it comes back black
because of how the emulator handles 3D. Frame rate, draw calls and heat are still only
answerable on a real phone.

---

## 7. The asset pipeline, end to end

```bash
python3 tools/pipeline/build.py --all
```

**What it protects against:** an art pipeline that quietly stops working. It builds every
building from scratch — geometry, texture, ambient occlusion, interface icon — imports each into
the game, and then **reads the finished file back** to check it contains what the build claimed.

That last step is the point. During Phase 0 the Android app shipped with the simulation as a
zero-byte file and the build reported success. **A build saying "done" is not evidence that
anything came out of it.** So this checks triangle counts, that a texture is actually present,
and that the icon is not blank.

It also fails on any rule from [ART_BIBLE.md](ART_BIBLE.md) a script can judge: over the
triangle budget, holes in the geometry, a model that floats above the ground or sinks into it,
a model that fills more than 80% of its own plot, or one taller than 0.6 × its footprint —
either of which would hide whatever stands behind it. Those last two numbers are measured off
Clash of Clans rather than chosen; see [reference/COC_TEARDOWN.md](reference/COC_TEARDOWN.md).

## 8. The city plays correctly

```bash
$GODOT --headless --path game --script res://tools/city_smoke.gd
```

**What it protects against:** the first part of the project with real changing state — resources
that go down when you spend and up when you wait, ground that can only hold one building, timers
that finish, levels that cost more and yield more, and a save format that has to keep reading
files written by older builds. All of it is quick to break and slow to notice by hand: a
build-timer fault takes twelve seconds to see and a saving fault takes a restart.

**It writes an old save by hand and loads it.** The migration check does not save-then-load with
today's code — that would pass even if migration did nothing. It writes a version 1 file in the
exact shape the old build wrote, with no `level` field anywhere, and checks it comes back as a
level 1 building. It also writes a version 99 file and checks the game refuses it instead of
guessing, because silently dropping fields a newer build wrote is how a downgrade eats
somebody's town.

It plays a short game with nobody watching: places a building, tries to place a second one on
top of it, tries to build off the edge of the map, tries to build something it cannot afford,
waits for the first to finish, checks it starts producing, saves, wipes the world, loads, and
checks everything came back.

**One lesson from writing it is worth repeating.** Its first version said overlapping was
refused while the game happily allowed it, because the test called the placing function directly
and the check that stopped you lived in the *click handler* — two different routes, only one of
them guarded. **A test must go through the same door the player uses.** A check that calls
something the player never touches will keep passing while the game is broken.

---

## Checks that arrive later

| Check | Arrives | What it will protect |
|---|---|---|
| Determinism on a real phone | Phase 1 | The check above covers Linux and macOS. An Android emulator now covers the ARM leg too — see check 6. A physical phone is still outstanding. |
| Asset budget validation | Phase 2 | Every 3D asset within its triangle budget, correct scale, correct texel density, no bad geometry. |
| Silhouette legibility | Phase 2 | Every building still identifiable as a solid black shape at 64 pixels. |
| Replay determinism | Phase 4 | A battle replays identically from its record, twice. The Phase 4 completion test. |
| On-device performance | Phase 3 onward | 60 frames per second on an iPhone 12 and a Pixel 6a, within 120 draw calls and 250,000 triangles. |
| Grayscale and two-signal checks | Phase 2/3 | [ART_BIBLE.md](ART_BIBLE.md) rules 7 and 8 are still prose. See [BACKLOG.md](BACKLOG.md). |

---

## The check no script can perform

**Testing on a real phone at the end of every phase.**

The simulator on your Mac runs the game on desktop hardware. It will happily report smooth
performance for something that stutters badly on an actual phone, and it does not model heat,
battery drain, or what happens when the phone throttles itself after ten minutes.

**The simulator lies about performance.** Every phase ends on real hardware.
