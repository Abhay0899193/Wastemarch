# ADR-0002 — Landscape orientation, 1920 × 1080

- **Status:** Accepted
- **Date:** 8 August 2026
- **Decided by:** the project owner, during the Phase 0 planning session
- **Amends:** `MASTER_PLAN.md` §5, which specifies a 1080 × 1920 base resolution

---

**What this is.** The master plan gives the screen size as 1080 × 1920, which is a portrait
(tall) phone screen. We are instead building the game landscape (wide), at 1920 × 1080. This
record explains why and what it costs.

---

## Context

`MASTER_PLAN.md` §5 states the Godot project should use *"1080x1920 base, canvas_items
stretch."* Those numbers describe a phone held upright.

But the master plan also names *Clash of Clans* and *SimCity BuildIt* as the two reference
games for the two halves of the loop, and **both are landscape**. The plan never states an
orientation in words; the resolution was the only signal, and it pointed the opposite way
from the design it sits beside.

This needed resolving in Phase 0 rather than later, because orientation determines how every
camera shot is framed, how the interface is laid out, and how much of the base fits on
screen. Changing it in Phase 3 would mean redoing all of that.

## Decision

**Landscape, 1920 × 1080 base resolution, orientation locked.**

Godot settings:

```
display/window/size/viewport_width  = 1920
display/window/size/viewport_height = 1080
display/window/handheld/orientation = "landscape"
display/window/stretch/mode         = "canvas_items"
display/window/stretch/aspect       = "expand"
```

The `canvas_items` stretch mode and `expand` aspect from the master plan are unchanged.
Together they mean the interface scales to fit any phone, and phones with a wider or
narrower screen than 16:9 see slightly more or less of the world rather than black bars or a
squashed picture.

## Why

**The genre is landscape.** Both named reference games are, and so is essentially every
base-builder with a real-time combat half. Players arrive with that expectation.

**Combat needs the width.** You deploy troops along the edge of an enemy base and watch them
advance. A wide frame shows you the base and your deployment edge at once. A tall frame
forces you to choose between seeing where you are dropping and seeing what happens next.

**The Duskwood must always be on screen.** [ART_BIBLE.md](../ART_BIBLE.md) requires black
trees along the north edge of the frame at every angle and every zoom. A wide frame gives
that a real presence. In portrait it is a thin strip.

**The story's best shot is wide.** The opening scene is a cart crossing an empty grey bowl
with a wall of black trees filling a third of the frame. [STORY.md](../STORY.md) §3.1. That
is a landscape composition and it is the game's first impression.

## Alternatives considered

**Portrait, as literally written.** Works well for the building half — *Township* and
*Royal Match* are portrait and successful — and allows one-handed play. Rejected because the
combat half is the harder problem and portrait makes it harder still, and because it fights
the visual direction the story bible already commits to.

**Support both.** Rejected outright. It doubles interface work forever and neither
orientation ends up designed properly. This is a single-person project.

**Defer the decision to Phase 3.** Rejected. Phase 0's job is to configure the project, and
"configured except for the setting that determines every frame" is not configured. Deferring
would mean the first camera work, the first interface, and the first concept art all get made
against an unknown.

## Consequences

**Good.** Combat reads properly. The Duskwood stays present. The opening shot works as
composed. Concept art generated from Phase 2 onward is framed correctly from the first image.

**Costly.** One-handed play is out; this is a two-handed game. Vertically stacked interface
panels have less room, so menus need care.

**Follow-on.** The master plan's 1080 × 1920 is now wrong wherever it appears. The plan is
never edited — this record is the correction, and [ARCHITECTURE.md](../ARCHITECTURE.md),
[ART_BIBLE.md](../ART_BIBLE.md), and `game/project.godot` all reflect the landscape decision.

**Reversibility.** Cheap now, expensive later. Today it is four lines in a settings file.
After Phase 2 has generated concept art and Phase 3 has laid out the interface, it is weeks
of rework. That is precisely why it was settled here.
