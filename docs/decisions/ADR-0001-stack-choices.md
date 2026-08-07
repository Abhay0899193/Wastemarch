# ADR-0001 — Stack choices

- **Status:** Accepted
- **Date:** 8 August 2026
- **Decides:** Ratifies the technology choices in `MASTER_PLAN.md` §4 as the project's
  starting position.

---

**What this is.** A decision record is a short note explaining one choice — what we decided,
what else was on the table, and why. They are never edited after the fact; if we change our
minds, a new record supersedes this one. This first record simply confirms the master plan's
technology choices so that later records have something to refer back to.

---

## Context

The master plan already argued these choices out. This record exists so that the reasoning
lives in the numbered series rather than only inside a document we have agreed not to edit,
and so that anything superseding it has a target.

The constraints these choices had to satisfy:

- Ships on iPhone and Android from one project.
- Version 1 works entirely offline; version 2 adds player-versus-player **without a rewrite**.
- Built by one person over roughly six months.
- No advertising, no loot boxes, no pay-to-win, no player data sent anywhere at runtime.
- Runs acceptably on modest hardware — an iPhone 12 and a Pixel 6a at 60 frames per second.

---

## Decisions

### Engine: Godot 4.7.1-stable

Free and open source, so there is no per-revenue licence fee and no vendor who can change
terms later. One project exports to both phone platforms. The version is pinned exactly and
recorded in [ENVIRONMENT.md](../ENVIRONMENT.md).

*Considered:* Unity — capable, but its licensing history since 2023 is a business risk we
have no way to hedge. Unreal — excellent, and far heavier than this game needs on mobile.

### Renderer: Mobile (`forward_mobile`), not Forward+

Godot offers two rendering paths. **Forward+** is built for desktop graphics cards.
**Mobile** is built for the tile-based graphics chips phones actually use, and still supports
real-time shadows.

Choosing Forward+ on a phone is a common and expensive mistake. It is not a "higher quality"
setting — it is a differently-shaped one, and on phone hardware it behaves badly.

### Rendering approach: real-time 3D, not pre-rendered 2D sprites

The genre's most famous example uses pre-rendered sprites, but that was the right call for
2012 hardware and is technical debt they now maintain rather than a model to copy.
Essentially every base-builder since about 2016 renders real 3D through an isometric camera.

Reasoning in full in `MASTER_PLAN.md` §1.3. The short version: with sprites, adding one
building level means re-rendering it from eight directions and shipping a new app; with 3D it
is often a data-only change. Day/night, weather, and zoom are free in 3D and impossible in
sprites. App size at scale is tens of megabytes against gigabytes.

### Simulation: a separate Rust crate, whole numbers only

This is the decision that makes online play in version 2 an addition rather than a rewrite,
and it is the one everything else bends around.

The rules of the game live in self-contained Rust with no graphics, no clock, no file access,
and **no decimal arithmetic**. It compiles two ways: as an extension the phone loads, and as
a library our server loads. Same code, same results, both places.

Decimal ("floating-point") numbers can produce microscopically different answers on different
processors. In a simulation, one microscopic difference changes which target a unit picks,
and from there the two machines disagree entirely. Whole-number arithmetic is identical on
every processor ever made.

An automatic check enforces this, set up in Phase 0 before any code existed. See
[TESTING.md](../TESTING.md).

*Considered:* writing the simulation in GDScript, Godot's own language. Simpler in the short
term, and it forecloses server-side validation permanently — GDScript cannot run inside our
server, so version 2 would mean reimplementing every rule a second time and keeping two
implementations in perfect agreement forever.

### Game and interface code: GDScript

Godot's own language. Quick to work with, and the performance-sensitive work is in Rust
anyway. Statically typed throughout, so mistakes are caught before running.

### Saves: local encrypted file with versioned migrations

Godot has encrypted file support built in. **Migrations** mean that when the save format
changes, old saves are converted rather than discarded. A player losing their town to an
update is unrecoverable, so this is designed in from the start rather than added when it
first happens.

### Backend for version 2: Nakama, self-hosted

Open source, runs on a €20/month server, no per-player fee. Written in Go, and it can load
our Rust simulation directly to re-check battles players submit.

*Considered:* PlayFab and similar managed services — a per-player cost that grows with
success and a dependency on someone else's business decisions.

### Analytics: self-hosted PostHog or Aptabase. Crash reporting: Sentry.

Both keep player data under our control and both avoid pulling in an advertising company's
code.

### Explicitly excluded

No advertising and no advertising toolkit. No loot boxes. No purchasable power. No AI model
running inside the shipped game. No player chat or player-created content in version 1. No
Firebase.

Each is either a legal exposure, a privacy exposure, or something that makes the game worse.
Each is listed in [BACKLOG.md](../BACKLOG.md) under *Rejected* so it does not quietly return.

---

## Consequences

**Good.** Version 2's online play is additive. Replays cost about two kilobytes. Balance
changes need no programmer. No third-party code can change its terms underneath us.

**Costly.** Rust is harder to write than GDScript, and whole-number arithmetic is more
awkward than decimals — every distance and speed has to be expressed in fixed units and
converted for display. This cost is paid every day of Phase 1. It buys the entire version 2
architecture.

**Locked in.** Changing the simulation language later means rewriting it. This is the one
decision that is genuinely expensive to reverse, which is why it is argued at length rather
than assumed.

---

## Related

- [ARCHITECTURE.md](../ARCHITECTURE.md) — what these choices produce in practice
- [ADR-0002](ADR-0002-landscape-orientation.md) — the first amendment to the master plan
