# ADR-0003 — An ARM Android emulator satisfies the Phase 1 gate

- **Status:** Accepted
- **Date:** 8 August 2026
- **Decided by:** the project owner, session 5
- **Interprets:** `MASTER_PLAN.md` §Phase 1, line 486 — *"a headless battle produces an
  identical state hash on macOS, Linux, and an ARM device"*

---

**What this is.** Phase 1 finishes when the same battle gives the same answer on three
different machines. Two of them are ordinary computers. The third was meant to be a phone,
which we do not have yet. This record says an emulated phone counts, and is honest about what
that does and does not prove.

---

## Context

A **hash** here is a single number computed from everything that happened in a battle. If two
machines produce the same number, they ran the battle identically. If they differ by even one
unit of damage, the numbers look completely unrelated. It is the cheapest possible way to ask
"did these two machines agree?"

The simulation already produces the same hash on macOS and on Linux, checked automatically on
every push. The third leg exists because phones use a different family of processor and a
different compiler toolchain from a Linux server, and that is where a disagreement would
realistically hide.

**No physical Android phone is available**, and acquiring one was the last thing standing
between Phase 1 and completion. An **emulator** — a complete Android phone running as a
program on the Mac — closes that in a way that is not obviously a compromise, because this
Mac and Android phones use the same kind of processor. The emulator therefore runs the *real*
phone build of our code, natively, on a real Android system. It is not pretending.

Measured on 8 August 2026: the Android build produces `0x6de277a1cf08225b`, identical to both
desktop legs. Setup and commands are in [TESTING.md](../TESTING.md) check 6.

## Decision

**The emulator result closes the Phase 1 gate. Phase 1 is complete.**

## Why

**The emulator is not an approximation.** It executes the genuine `aarch64-linux-android`
library on a real Android system with Android's own C library. The one thing it shares with
the Mac is the physical chip.

**The remaining risk is small, by design.** What the emulator cannot prove is that a Qualcomm
or Samsung chip agrees with an Apple one. But `sim-core` contains **no decimal numbers at
all** — every value is a whole number. Whole-number arithmetic is defined exactly by the
processor's instruction set and cannot vary between vendors. Decimal arithmetic is where
chips genuinely differ, and banning it is the single largest reason this project's simulation
is written the way it is. The no-decimals rule is enforced by an automatic check that cannot
be switched off.

**The real gap is somewhere else entirely.** A phone is still required for speed, draw calls,
triangle counts and heat — none of which an emulator can answer, because it borrows the Mac's
graphics card. That requirement is unchanged and sits in the **Phase 0** budget gate. Holding
Phase 1 hostage to hardware that Phase 0 already demands buys nothing.

## Alternatives considered

**Wait for a physical phone.** Rejected as pure delay. The phone is coming anyway for Phase 0,
so the same test runs on it regardless — this decision only changes whether Phase 1 waits for
it. Nothing downstream of Phase 1 was blocked by the gate: Phase 2 is gated on the colour
palette instead.

**Weaken the gate to two machines.** Rejected. The cross-platform question is the entire
reason `sim-core` exists in its current form, and the phone build is precisely the leg most
likely to break.

## Consequences

**Good.** Phase 1 closes. The emulator is now a repeatable check anyone can run in about a
minute, rather than something needing hardware on a desk.

**Costly.** A cross-vendor disagreement, if one existed, would go unnoticed until the game is
on a real handset. Judged very unlikely for whole-number arithmetic, but this is the risk
being accepted, stated plainly.

**Follow-on.** The same test **must** be run on the first physical Android phone that appears,
as part of the Phase 0 hardware pass. If the hash disagrees there, this decision was wrong and
the finding is an emergency, not a curiosity.

Continuous integration should also cross-compile the Android library on every push. The first
emulator run reported a mismatch that turned out to be a *stale* library built before the last
few changes — see `.agent/MEMORY.md`. That failure mode is far more likely than genuine
divergence and is worth automating away.

**Reversibility.** Total. Nothing is built on this beyond a tick in a checklist. If the phone
disagrees, Phase 1 reopens.
