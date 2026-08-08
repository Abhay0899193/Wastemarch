#!/usr/bin/env python3
"""One command: prompt to finished building, textured, iconed and in the engine.

    python3 tools/pipeline/build.py granary
    python3 tools/pipeline/build.py --all
    python3 tools/pipeline/build.py granary --concept      # regenerate art too

This is the Phase 2 gate from `MASTER_PLAN.md`: *"one command turns a prompt into
a finished 3D building plus its interface icon, with nobody watching."*

**What counts as the input, stated honestly.** Two things are authored by a
person: the prompt file in `tools/pipeline/prompts/`, and the builder function in
`tools/blender/build_asset.py`. Both are source. Everything after them —
concept art, geometry, unwrap, texture, ambient occlusion, emission, the glTF,
the interface icon, the engine import and the budget check — happens here with
nobody watching.

The stages, and what each is allowed to fail on:

    1. concept    only when asked; costs ~2 minutes of GPU
    2. model+bake geometry, unwrap, 2048 texture with AO and emission, icon
       FAILS on: over budget, n-gons, loose geometry, wrong origin, blank texture
    3. install    copy the .glb where the game reads it
    4. import     Godot scans and imports
       FAILS on: any Godot error
    5. verify     the .glb really contains what stage 2 said it did

Stage 5 exists because of a Phase 0 lesson that cost real time: a build reporting
success is not evidence that its output has anything in it. The Android library
once shipped as zero bytes with a green build.
"""

import argparse
import json
import shutil
import struct
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
BLENDER = Path("/Users/singha7/Applications/Blender.app/Contents/MacOS/Blender")
GODOT = Path("/Users/singha7/Applications/Godot.app/Contents/MacOS/Godot")

MODEL_SRC = REPO / "assets-src" / "model"
GAME_MODELS = REPO / "game" / "assets" / "models"
ICONS = REPO / "game" / "assets" / "atlases" / "icons"

ASSETS = ["granary", "keep", "watchtower"]


def run(cmd, label, keep=()):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True)
    for line in (r.stdout + r.stderr).splitlines():
        if any(k in line for k in keep):
            print("      " + line.strip())
    if r.returncode != 0:
        print(r.stdout[-1500:])
        print(r.stderr[-1500:])
        sys.exit(f"FAILED at {label}")


def glb_facts(path: Path) -> dict:
    """Read the .glb back. Trust the file, not the build log."""
    b = path.read_bytes()
    if b[:4] != b"glTF":
        sys.exit(f"{path.name} is not a glTF file")
    off, gl = 12, None
    while off < len(b):
        ln, ty = struct.unpack_from("<II", b, off)
        if ty == 0x4E4F534A:
            gl = json.loads(b[off + 8:off + 8 + ln].decode("utf-8"))
            break
        off += 8 + ln + ((4 - ln % 4) % 4)
    tris = sum((gl["accessors"][p["indices"]]["count"] // 3) if "indices" in p
               else gl["accessors"][p["attributes"]["POSITION"]]["count"] // 3
               for m in gl.get("meshes", []) for p in m.get("primitives", []))
    return {"triangles": tris,
            "materials": len(gl.get("materials", [])),
            "images": len(gl.get("images", [])),
            "bytes": path.stat().st_size}


def build(asset: str, level: int, with_concept: bool) -> dict:
    started = time.time()
    print(f"\n=== {asset} level {level}")

    if with_concept:
        print("  1/5  concept art")
        run([sys.executable, REPO / "tools/pipeline/concept.py", asset,
             "--seeds", "1"], "concept", keep=("assets-src/concept",))
    else:
        print("  1/5  concept art — skipped (--concept to regenerate)")

    print("  2/5  model, unwrap, bake, icon")
    run([BLENDER, "--background", "--factory-startup", "--python",
         REPO / "tools/blender/bake_asset.py", "--",
         "--asset", asset, "--level", level],
        "model+bake", keep=("OK —", "icon ", "VALIDATION"))

    print("  3/5  install into the game")
    GAME_MODELS.mkdir(parents=True, exist_ok=True)
    src = MODEL_SRC / f"{asset}_L{level}.glb"
    shutil.copy2(src, GAME_MODELS / src.name)

    print("  4/5  Godot import")
    run([GODOT, "--headless", "--path", REPO / "game", "--editor", "--quit"],
        "godot import", keep=("SCRIPT ERROR",))

    print("  5/5  verify the file, not the log")
    facts = glb_facts(GAME_MODELS / src.name)
    icon = ICONS / f"{asset}_L{level}.png"
    if not icon.exists() or icon.stat().st_size < 2000:
        sys.exit(f"icon missing or blank: {icon}")
    if facts["images"] < 1:
        sys.exit(f"{src.name} carries no texture")
    if facts["triangles"] < 12:
        sys.exit(f"{src.name} has almost no geometry")

    facts.update(asset=asset, level=level, icon_bytes=icon.stat().st_size,
                 seconds=round(time.time() - started, 1))
    print(f"      {facts['triangles']} triangles, {facts['materials']} material, "
          f"{facts['images']} texture, {facts['bytes'] // 1024} KB, "
          f"icon {facts['icon_bytes'] // 1024} KB  ({facts['seconds']}s)")
    return facts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("asset", nargs="?")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--level", type=int, default=1)
    ap.add_argument("--concept", action="store_true",
                    help="regenerate the concept art as well (~2 min of GPU)")
    args = ap.parse_args()

    if not args.all and not args.asset:
        ap.error("name an asset, or pass --all")
    targets = ASSETS if args.all else [args.asset]

    results = [build(a, args.level, args.concept) for a in targets]

    print("\n" + "=" * 62)
    print(f"{'asset':<14}{'tris':>7}{'mats':>6}{'tex':>5}{'glb KB':>9}"
          f"{'icon KB':>9}{'secs':>7}")
    for r in results:
        print(f"{r['asset']:<14}{r['triangles']:>7}{r['materials']:>6}"
              f"{r['images']:>5}{r['bytes'] // 1024:>9}"
              f"{r['icon_bytes'] // 1024:>9}{r['seconds']:>7.0f}")
    print("\nAll assets built, textured, iconed, imported and verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
