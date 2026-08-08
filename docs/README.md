# Wastemarch — Documentation

**What this is.** This folder explains the Wastemarch project in plain English, for the
person who owns it rather than the person writing the code. Every document here opens with
a three-sentence summary like this one, and defines each technical term the first time it
appears. If a document ever disagrees with the actual project, that is a bug — say so and
it gets fixed.

---

## Start here

| Document | What it tells you |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | How the game is put together, and why it is split into the pieces it is. |
| [ROADMAP.md](ROADMAP.md) | The nine phases from empty folder to launch, and how we know each one is finished. |
| [GAME_DESIGN.md](GAME_DESIGN.md) | What the player actually does: building, resources, army, combat. |
| [STORY.md](STORY.md) | The world, the three characters, and the script of the opening four minutes. |
| [ART_BIBLE.md](ART_BIBLE.md) | The rules every piece of art must follow so the game looks like one team made it. |
| [ASSET_PIPELINE.md](ASSET_PIPELINE.md) | How a building goes from a text prompt to something standing in the game. |
| [ENVIRONMENT.md](ENVIRONMENT.md) | Exactly which tools are installed on your Mac, which versions, and where. |
| [TESTING.md](TESTING.md) | The checks that run before anything is committed, and how to run them yourself. |
| [BACKLOG.md](BACKLOG.md) | Good ideas that are deliberately not being worked on yet. |
| [reference/COC_TEARDOWN.md](reference/COC_TEARDOWN.md) | Clash of Clans' opening ten minutes pulled apart into numbers: camera, zoom, proportions, and the flow screen by screen. |
| [decisions/](decisions/) | A numbered record of every significant decision and why it was made. |

## The two documents that outrank everything here

- **`MASTER_PLAN.md`** (in the project root) — what we are building. It is not edited. If
  something in it turns out to be wrong, that change is written up as a decision record in
  [decisions/](decisions/) instead.
- **`CLAUDE.md`** (in the project root) — the working rules the engineer follows: when to
  commit, what is never allowed into the project, how each session starts and ends.

## Decision records

A **decision record** (often shortened to *ADR*, "architecture decision record") is a short
numbered note explaining one choice: what we decided, what else we considered, and why.
They are never deleted or edited after the fact — if we change our minds, a new one
supersedes the old one. That way the reasoning survives even when the decision doesn't.

- [ADR-0001 — Stack choices](decisions/ADR-0001-stack-choices.md)
- [ADR-0002 — Landscape orientation](decisions/ADR-0002-landscape-orientation.md)
- [ADR-0003 — An ARM emulator satisfies the Phase 1 gate](decisions/ADR-0003-emulator-satisfies-the-phase-1-gate.md)
- [ADR-0004 — The colour palette, locked](decisions/ADR-0004-colour-palette.md)
- [ADR-0005 — Clash of Clans as the measured reference](decisions/ADR-0005-clash-of-clans-as-the-measured-reference.md)

## A note on the `.agent/` folder

There is a folder called `.agent/` next to this one. That is the engineer's own working
memory — the current task list, a running journal, and durable notes. It is written for a
machine and is deliberately technical. You are welcome to read it, but nothing in it is
required reading for you.
