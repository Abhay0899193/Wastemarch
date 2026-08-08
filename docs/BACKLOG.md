# Backlog — good ideas we are deliberately not doing yet

**What this is.** Everything that is worth doing but is not part of the current phase lives
here. Putting an idea in this file is how it gets taken seriously without derailing the work
in progress. Nothing moves out of here except by being scheduled into a specific phase.

**Why this file exists.** Scope creep is the most common reason solo projects never ship. The
defence is not discipline, it is a place to put things. An idea written down stops nagging.

---

## Format

Each entry says what it is, why it is not now, and roughly when it should be reconsidered.

---

## Documentation

### `RELEASE.md`
The master plan lists it. It would be an empty file for five months — everything in it
(store listings, privacy policy, the release checklist) is Phase 7 work that cannot be
written meaningfully today.
**Reconsider:** Phase 7.

### `docs/art/reference/`
The three approved reference buildings that the Art Bible is ultimately judged against.
Cannot exist until the pipeline can produce a building.
**Reconsider:** Phase 2 — this is the Phase 2 completion test.

---

## Decisions needing your input

### The final name
"Wastemarch" is a working title. Needs a trademark search (USPTO and EUIPO) and an app store
search before any public listing. The master plan lists alternatives: *Ashfall Barony*,
*Thornmarch*, *The Ninth Holding*, *Bleakhold*, *Warden of the Waste*.
**Reconsider:** before Phase 8. Register the name as soon as it is chosen.

---

## Technical

### Set up a self-hosted GitHub runner on your Mac
Building for iPhone requires macOS, and GitHub's hosted Mac machines cannot hold your signing
certificates safely. Needed to complete Phase 0's test — an automatically produced build
installed on a real phone.
**Reconsider:** end of Phase 0. **Blocks the Phase 0 gate.**

### Fix Homebrew's permissions
`/usr/local/bin` is owned by root, so `brew install` fails at its last step. Git LFS was
installed by hand around it. Every future `brew install` will hit the same wall.
One command fixes it: `sudo chown -R $(whoami) /usr/local/bin`.
**Reconsider:** whenever the next Homebrew install is needed — the Android toolchain will
need it.

### Add the `godot` Rust binding to `sim-godot`
The crate that connects the Rust simulation to Godot is currently an empty stub with no
dependencies, on purpose — pinning it against Godot 4.7 is real work and there is nothing
yet for it to connect.
**Reconsider:** Phase 1, as soon as `sim-core` does anything worth calling.

### Add extra Rust build targets
Only `aarch64-apple-darwin` (Apple Silicon) is installed. Cross-platform determinism testing
needs Linux and Android targets too.
**Reconsider:** Phase 1, alongside the determinism test.

---

## Design ideas — parked

### Player-built forward bases — a second, defensive base type

**The owner's idea, 8 August 2026, and a good one.** A dense settlement at the centre of the
wasteland that the player grows into a real town, plus smaller fortified outposts built near
enemy territory and contested resources — the town half plays like *SimCity BuildIt*, the
outpost half plays like *Clash of Clans*.

**Why it is worth doing.** It is the dominant shape of successful mid-core mobile right now,
and for a good reason: the two halves want different things from the player. A town rewards
patience and optimisation; an outpost rewards reading a threat and committing. Wastemarch's
story already justifies it — you are a warden pushing a frontier back, and a frontier needs
holdings.

**Why it is parked rather than started.** Three specific costs:

1. **It doubles the balance surface.** Two building sets, two economies, two upgrade curves,
   two save schemas. `MASTER_PLAN.md` budgets six to seven months for *one*.
2. **The failure mode is known and has a name.** *Clash of Clans'* Builder Base is the
   cautionary case: a second base disconnected from the first that most players stop
   visiting. The fix is that outposts must **feed the town** — resources, unlock pressure,
   a reason to look at them every session. That is an economy design problem, and it cannot
   be answered before the core loop exists and is proven fun.
3. ~~**"Modern city" needs settling.**~~ **Settled 8 Aug 2026 by the owner:** "modern" means
   advanced *relative to the wasteland's current state*, in the idiom of Ostmere itself, and
   eventually **exceeding** the kingdom. Not skyscrapers. No conflict with
   [STORY.md](STORY.md) or the palette in
   [ADR-0004](decisions/ADR-0004-colour-palette.md) — and the "eventually exceed Ostmere"
   ceiling is a genuinely good long-game target that the current design does not yet reach
   for. Worth a look in Phase 5 when the progression curve is built.

**What it costs technically: less than it sounds.** The simulation is already grid-based and
placement-agnostic; an outpost is the same `Grid`, `Entities` and pathfinding with a
different building subset. The one real constraint is that `GRID_SIZE` in
`sim/sim-core/src/grid.rs` is a **compile-time constant of 44**. Two base types of the *same*
size cost nothing. Two of *different* sizes means making the grid carry its own dimensions,
which touches pathfinding and changes the golden hash. **So: if this happens, both bases are
44×44.**

**Reconsider:** end of Phase 4, when the core loop has been played and is known to be fun.
The honest sequencing is to ship V1 with the town plus attacking pre-made enemy camps —
which is already the plan and already delivers most of this feeling — and add player-built
outposts as the first major post-launch feature.

### Automatic checks for the two new palette rules

[ART_BIBLE.md](ART_BIBLE.md) rules 7 and 8 — readable in grayscale, and never colour alone —
are currently prose. The silhouette test is already scripted; these are the same idea applied
to brightness and to signal redundancy, and they belong in the same validator or they will
decay into good intentions.
**Reconsider:** Phase 2, alongside the asset validator. Cheap while that code is being
written, annoying afterwards.

### Naval expansion along the Sundered Coast
The southern border has a harbour, trade routes, and shipwreck salvage in the story bible.
No mechanics designed. A natural expansion but a whole new system.
**Reconsider:** post-launch content, or Season 2.

### The Kharzuun trade thread
The eastern nation beyond the impassable mountains, from which a trader survives the passes
maybe twice a year carrying something strange. Very high flavour for very little work — a
rare-goods trickle plus a slow-burn narrative thread.
**Reconsider:** Phase 5 or 6, if there is room. Cheap and characterful.

### Cloud saves
iCloud on iPhone, Google Play Games on Android. The master plan puts this at version 1.1.
**Reconsider:** after launch.

---

## Rejected — recorded so they do not come back

| Idea | Why not |
|---|---|
| Advertising of any kind | Third-party tracking code we cannot audit, and it makes a premium game feel cheap. |
| Loot boxes | Banned in Belgium and the Netherlands, regulated in the EU and UK. The revenue is not worth the exposure. |
| Anything purchasable that makes you stronger | Contradicts the game's own premise: a man with no advantages who wins by thinking better. |
| Firebase | Ties us to Google's data practices for no benefit we cannot get from a self-hosted alternative. |
| An AI model running inside the shipped game | Turns the app into a data-processing product under Apple's guideline 5.1.2(i), with all the compliance that implies. All AI here is build-time only. |
| Player chat or player-created content | Requires moderation we cannot staff. |
| Pre-rendered 2D sprites instead of real 3D | Discussed at length in the master plan §1.3. More work per asset, gigabytes of app size, and it permanently caps what we can add after launch. |
