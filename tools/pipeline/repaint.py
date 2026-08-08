#!/usr/bin/env python3
"""Paint a building by painting over its own render, then project that back.

    python3 tools/pipeline/repaint.py granary
    python3 tools/pipeline/repaint.py granary --strength 0.6

**Why this exists.** Projecting a concept image onto a model only works where the
model's outline matches the painted building's. Tuning a model to match a
painting means guessing at four or five parameters against an image that was
never drawn to any dimensions — and it plateaued: the granary got stuck around
10% of its visible surface landing on empty background, no matter which
combination was tried.

Painting over the model's *own render* inverts that. The painting has the model's
proportions exactly, because it started as the model. Projecting it back lands on
every face by construction, and the numbers stop being something to chase.

    model -> flat render at the game camera -> image model paints detail onto it
          -> projected straight back onto the model it came from

`--strength` is how far the painter may stray from the render. Low keeps the
shape and adds little; high paints beautifully and stops matching.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
BLENDER = Path("/Users/singha7/Applications/Blender.app/Contents/MacOS/Blender")
PROJECT = REPO / "tools" / "blender" / "project_concept.py"
PAINT_DIR = REPO / "assets-src" / "painted"

sys.path.insert(0, str(Path(__file__).resolve().parent))
import concept as cn  # noqa: E402


def blender(*args) -> None:
    cmd = [str(BLENDER), "--background", "--factory-startup",
           "--python", str(PROJECT), "--"] + [str(a) for a in args]
    r = subprocess.run(cmd, capture_output=True, text=True)
    for line in r.stdout.splitlines():
        if any(k in line for k in ("OK —", "on background", "of the grey",
                                   "WARNING", "rendered", "Error", "FAILED")):
            print("  " + line.strip())
    if r.returncode != 0:
        print(r.stdout[-2000:], r.stderr[-2000:])
        sys.exit(f"Blender failed: {' '.join(str(a) for a in args)}")


def paint(base: Path, out: Path, prompt: str, seed: int, strength: float) -> None:
    env = os.environ.copy()
    env.setdefault("HF_HOME", str(Path.home() / "mentoros-imagegen" / "hf-cache"))
    env["HF_HUB_DISABLE_XET"] = "1"
    env["HF_HUB_OFFLINE"] = "1"
    out.unlink(missing_ok=True)
    cmd = [str(cn.BINARY),
           "--model", cn.MODEL_REPO, "--base-model", cn.BASE_MODEL,
           "--prompt", prompt,
           "--image-path", str(base), "--image-strength", str(strength),
           "--seed", str(seed), "--steps", "8",
           "--width", "1024", "--height", "1024",
           "--output", str(out)]
    if subprocess.run(cmd, env=env).returncode != 0 or not out.exists():
        sys.exit("painting failed")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("asset")
    ap.add_argument("--level", type=int, default=1)
    ap.add_argument("--seed", type=int, default=4001)
    # mflux's --image-strength is how strongly the init image DOMINATES, which
    # is the opposite of the usual denoise convention: higher keeps the flat
    # render, lower lets the painter loose. Measured on the granary:
    #
    #   0.82  0.3% off-model, and almost no painting at all
    #   0.55  1.2% off-model, moderate detail
    #   0.50  the balance used here
    #   0.42  6.7% off-model, real thatch and stonework
    #   0.30  5.2% off-model, and starting to invent geometry
    ap.add_argument("--strength", type=float, default=0.50)
    args = ap.parse_args()

    ok, why = cn.model_is_permitted(cn.MODEL_REPO)
    if not ok:
        sys.exit(f"REFUSING: {why}")

    PAINT_DIR.mkdir(parents=True, exist_ok=True)
    base = PAINT_DIR / f"{args.asset}_L{args.level}_base.png"
    painted = PAINT_DIR / f"{args.asset}_L{args.level}_painted.png"

    print(f"1/3  rendering {args.asset} at the game camera")
    blender("--asset", args.asset, "--level", args.level,
            "--render-for-paint", base)

    print(f"2/3  painting over it, strength {args.strength}")
    prompt = f"{cn.style_prompt('buildings')} {cn.asset_prompt('buildings', args.asset)}"
    paint(base, painted, prompt, args.seed, args.strength)

    print("3/3  projecting the painting back onto the model")
    blender("--asset", args.asset, "--level", args.level,
            "--paint-from", painted)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
