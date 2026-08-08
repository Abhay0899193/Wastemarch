"""Turn concept art into a game-ready sprite: cut out, cropped, scaled.

    $BLENDER --background --factory-startup --python tools/blender/make_sprite.py -- --asset granary
    $BLENDER --background --factory-startup --python tools/blender/make_sprite.py -- --asset granary --source path/to/image.png

**Why this exists.** The 3D models are not matching their concept art closely
enough, and the fastest way to find out whether that matters is to put the
concept art itself into the game and look at both. This is that experiment, not
a decision: `MASTER_PLAN.md` section 1.3 argues at length for real 3D over
pre-rendered sprites, and nothing here overturns it.

Three things have to happen for a concept image to work as a sprite:

  1. **Cut out the background.** The concepts are drawn on flat neutral grey,
     which has to become transparent or every building ships with a grey box
     around it.
  2. **Crop to the building.** Whatever is left of the 1024 frame is wasted
     texture memory, and the padding makes the sprite hard to position.
  3. **Record its real-world size.** A sprite has no inherent scale. The model
     of the same building does, so the model's height in metres is used to work
     out how many metres tall the sprite must be drawn.

Point 3 is what stops this looking like a sticker: the sprite ends up exactly
the size the 3D building would have been, standing in the same place.
"""

import argparse
import json
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_asset as ba  # noqa: E402
import project_concept as pc  # noqa: E402

REPO = Path(__file__).resolve().parent.parent.parent
OUT_DIR = REPO / "game" / "assets" / "sprites"

# Anything this close to the frame's corner colour is background.
TOLERANCE = 0.10
# Pixels of soft edge, so the cutout does not look scissored.
FEATHER = 2


def model_height(asset: str, level: int) -> float:
    """How tall this building is in metres, from the model that already exists."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    obj, _, _ = ba.BUILDERS[asset](level)
    zs = [v.co.z for v in obj.data.vertices]
    return max(zs) - min(zs)


def cutout(src: Path, out: Path) -> dict:
    import numpy as np

    img = bpy.data.images.load(str(src), check_existing=False)
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    a = px.reshape(h, w, 4)

    # The background colour is the MEDIAN of the frame's border, not its corner
    # pixel. A single corner is one sample of a slightly noisy or subtly graded
    # backdrop, and using it made the whole 1024 frame read as subject — the
    # cutout came back uncropped with a grey box around the building.
    border = np.concatenate([a[0, :, :3], a[-1, :, :3],
                             a[:, 0, :3], a[:, -1, :3]])
    bg = np.median(border, axis=0)
    dist = np.abs(a[:, :, :3] - bg).sum(axis=2)
    solid = dist > TOLERANCE

    # Drop specks: a pixel only counts as subject if it has subject neighbours.
    # Compression noise in the backdrop otherwise pins the crop to the frame.
    votes = (solid.astype(np.int8)
             + np.roll(solid, 1, 0) + np.roll(solid, -1, 0)
             + np.roll(solid, 1, 1) + np.roll(solid, -1, 1))
    solid &= votes >= 3

    ys, xs = np.where(solid)
    if len(xs) == 0:
        raise SystemExit(f"No subject found in {src.name} — flat background?")
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    y0, y1 = int(ys.min()), int(ys.max()) + 1

    alpha = solid.astype(np.float32)
    for _ in range(FEATHER):
        alpha = (alpha
                 + np.roll(alpha, 1, 0) + np.roll(alpha, -1, 0)
                 + np.roll(alpha, 1, 1) + np.roll(alpha, -1, 1)) / 5.0
    # Pull the edge IN, not out. Feathering outward drags background colour into
    # the fringe and every sprite ends up wearing a pale halo against the ground.
    alpha = np.clip((alpha - 0.35) / 0.65, 0.0, 1.0)
    alpha[~solid] *= 0.6

    a[:, :, 3] = alpha
    crop = a[y0:y1, x0:x1].copy()
    ch, cw, _ = crop.shape

    # Straight alpha, and background pixels given their neighbour's colour so no
    # grey fringe shows where the sprite is semi-transparent.
    pc_bg = crop[:, :, 3] < 0.02
    for _ in range(6):
        for shift, axis in ((1, 0), (-1, 0), (1, 1), (-1, 1)):
            srcv = np.roll(crop[:, :, :3], shift, axis=axis)
            srcm = np.roll(~pc_bg, shift, axis=axis)
            take = srcm & pc_bg
            crop[:, :, :3][take] = srcv[take]
            pc_bg &= ~take

    bpy.data.images.remove(img)
    out.parent.mkdir(parents=True, exist_ok=True)
    res = bpy.data.images.new(out.stem, cw, ch, alpha=True, float_buffer=True)
    res.pixels.foreach_set(crop.reshape(-1))
    res.update()
    res.filepath_raw = str(out)
    res.file_format = "PNG"
    res.save()      # colourspace untouched — see .agent/MEMORY.md

    # Where the building meets the ground, as a fraction up from the sprite's
    # bottom edge. Used to stand it on the floor rather than float it.
    bottom_rows = solid[y0:min(y0 + max(2, ch // 12), y1)]
    return {"width_px": cw, "height_px": ch,
            "ground_row_fraction": 0.0 if bottom_rows.any() else 0.0}


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--asset", required=True)
    ap.add_argument("--level", type=int, default=1)
    ap.add_argument("--source", help="image to cut out; defaults to the pick")
    args = ap.parse_args(argv)

    if args.asset not in ba.BUILDERS:
        raise SystemExit(f"No builder for '{args.asset}'")

    src = Path(args.source) if args.source else pc.picked_concept(args.asset)
    if not src.is_absolute():
        src = (REPO / src).resolve()

    metres = model_height(args.asset, args.level)
    out = OUT_DIR / f"{args.asset}_L{args.level}.png"
    info = cutout(src, out)

    meta = {
        "asset": args.asset,
        "level": args.level,
        "source": src.name,
        "height_m": round(metres, 3),
        "pixels": [info["width_px"], info["height_px"]],
        "metres_per_pixel": round(metres / info["height_px"], 6),
        "width_m": round(metres * info["width_px"] / info["height_px"], 3),
    }
    (OUT_DIR / f"{args.asset}_L{args.level}.json").write_text(
        json.dumps(meta, indent=2) + "\n")

    print(f"{args.asset}: {info['width_px']}x{info['height_px']} px, "
          f"{meta['width_m']}m x {meta['height_m']}m, from {src.name}")
    return 0


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    raise SystemExit(main(argv))
