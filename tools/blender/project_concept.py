"""Paint a model with its own concept art, projected from the game camera.

    $BLENDER --background --factory-startup --python tools/blender/project_concept.py -- --asset keep

**The idea.** Camera projection — painting a flat image onto geometry along one
viewing direction — is the standard way of getting concept art onto a model. It
is normally a compromise, because the texture is only correct from the angle it
was projected along and smears from anywhere else.

**Wastemarch has no other angle.** `docs/ART_BIBLE.md` locks the camera to
orthographic, 30 degrees elevation, 45 degrees yaw, pan and zoom only, no
rotation. Under an orthographic projection every building sees the camera from
the same direction no matter where it stands on the grid, and zoom changes scale
without changing angle. The single condition that makes camera projection
unusable in most games is the condition this game removed on purpose in Phase 0.

So the concept art's colour and painted detail land on the model exactly, from
the only viewpoint that exists.

**What this does not fix.** The two faces turned away from the camera receive the
same texture stretched through the model. They are never visible, so it does not
matter — but it does mean these models are correct *for this camera* and would
have to be re-textured if the camera rule ever changed. That is a trade the Art
Bible already makes everywhere else.
"""

import argparse
import math
import sys
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_asset as ba  # noqa: E402

REPO = Path(__file__).resolve().parent.parent.parent
CONCEPT_DIR = REPO / "assets-src" / "concept"
PICKS_FILE = CONCEPT_DIR / "PICKS.md"
OUT_DIR = REPO / "assets-src" / "model"

ELEVATION_DEG = 30.0
YAW_DEG = 45.0

# The concept images are generated on a flat neutral background. Anything within
# this distance of the frame's corner colour is background, not building.
BACKGROUND_TOLERANCE = 0.06


def picked_concept(asset: str) -> Path:
    """The image the owner chose, read from PICKS.md rather than guessed.

    Reading it from the file is the point: the choice was the owner's and it is
    recorded, so nothing here gets to have an opinion about which concept is the
    reference.
    """
    text = PICKS_FILE.read_text()
    for line in text.splitlines():
        if f"`{asset}/" in line and line.lstrip().startswith("|"):
            for cell in line.split("|"):
                cell = cell.strip().strip("`")
                if cell.startswith(f"{asset}/") and cell.endswith(".png"):
                    path = CONCEPT_DIR / cell
                    if path.exists():
                        return path
    raise SystemExit(f"No picked concept for '{asset}' in {PICKS_FILE.name}")


def game_camera(obj):
    """The locked camera, framed on the object exactly as the concept framing."""
    cam_data = bpy.data.cameras.new("game_camera")
    cam_data.type = "ORTHO"

    zs = [v.co.z for v in obj.data.vertices]
    xs = [v.co.x for v in obj.data.vertices]
    ys = [v.co.y for v in obj.data.vertices]
    height = max(zs) - min(zs)
    width = max(max(xs) - min(xs), max(ys) - min(ys))
    cam_data.ortho_scale = max(width * 1.8, height * 1.8)

    cam = bpy.data.objects.new("game_camera", cam_data)
    bpy.context.collection.objects.link(cam)

    elev, yaw = math.radians(ELEVATION_DEG), math.radians(YAW_DEG)
    dist = 40.0
    cam.location = (dist * math.cos(elev) * math.sin(yaw),
                    -dist * math.cos(elev) * math.cos(yaw),
                    dist * math.sin(elev) + height / 2)
    cam.rotation_euler = (math.radians(90) - elev, 0.0, yaw)
    bpy.context.scene.camera = cam
    bpy.context.view_layer.update()
    return cam


def project_uvs(obj, cam) -> tuple:
    """Write camera-space coordinates into a UV layer.

    Done arithmetically with `world_to_camera_view` rather than with Blender's
    `uv.project_from_view` operator, which needs a 3D viewport and therefore
    cannot run in background mode at all. For an orthographic camera the two are
    the same projection.

    Returns the model's bounding box in UV space, which the caller needs in
    order to line the model up with the building in the concept image.
    """
    scene = bpy.context.scene
    uv = obj.data.uv_layers.active or obj.data.uv_layers.new(name="projected")
    lo = [1e9, 1e9]
    hi = [-1e9, -1e9]

    for poly in obj.data.polygons:
        for li in poly.loop_indices:
            vi = obj.data.loops[li].vertex_index
            world = obj.matrix_world @ obj.data.vertices[vi].co
            co = world_to_camera_view(scene, cam, Vector(world))
            uv.data[li].uv = (co.x, co.y)
            lo[0], lo[1] = min(lo[0], co.x), min(lo[1], co.y)
            hi[0], hi[1] = max(hi[0], co.x), max(hi[1], co.y)

    return (lo[0], lo[1], hi[0], hi[1])


def concept_bounds(image) -> tuple:
    """Where the building sits inside the concept image, as 0..1 coordinates.

    The concept is a building on a flat neutral field. Everything close to the
    corner colour is background; what is left is the subject. Aligning the two
    bounding boxes is what makes the projection land on the building rather than
    somewhere near it.
    """
    w, h = image.size
    px = [0.0] * (w * h * 4)
    image.pixels.foreach_get(px)

    bg = (px[0], px[1], px[2])
    lo = [1e9, 1e9]
    hi = [-1e9, -1e9]

    for y in range(0, h, 2):
        row = y * w
        for x in range(0, w, 2):
            j = (row + x) * 4
            d = (abs(px[j] - bg[0]) + abs(px[j + 1] - bg[1])
                 + abs(px[j + 2] - bg[2]))
            if d > BACKGROUND_TOLERANCE:
                lo[0], lo[1] = min(lo[0], x), min(lo[1], y)
                hi[0], hi[1] = max(hi[0], x), max(hi[1], y)

    if hi[0] < lo[0]:
        raise SystemExit("Could not find the building in the concept image — "
                         "is its background actually flat?")
    return (lo[0] / w, lo[1] / h, hi[0] / w, hi[1] / h)


def fit_uvs(obj, model_box, concept_box) -> None:
    """Stretch the projected UVs so the model lands on the painted building."""
    mx0, my0, mx1, my1 = model_box
    cx0, cy0, cx1, cy1 = concept_box
    sx = (cx1 - cx0) / max(1e-6, mx1 - mx0)
    sy = (cy1 - cy0) / max(1e-6, my1 - my0)

    uv = obj.data.uv_layers.active
    for d in uv.data:
        d.uv = (cx0 + (d.uv[0] - mx0) * sx,
                cy0 + (d.uv[1] - my0) * sy)


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--asset", required=True)
    ap.add_argument("--level", type=int, default=1)
    args = ap.parse_args(argv)

    if args.asset not in ba.BUILDERS:
        raise SystemExit(f"No builder for '{args.asset}'")

    concept = picked_concept(args.asset)
    print(f"projecting {concept.relative_to(REPO)} onto {args.asset}")

    bpy.ops.wm.read_factory_settings(use_empty=True)
    obj, size_class, footprint = ba.BUILDERS[args.asset](args.level)

    # One material, one texture: the concept image itself.
    for m in list(obj.data.materials):
        obj.data.materials.pop()
    obj.data.materials.clear()
    for poly in obj.data.polygons:
        poly.material_index = 0

    mat = bpy.data.materials.new("concept")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = 0.9
    bsdf.inputs["Metallic"].default_value = 0.0
    img = bpy.data.images.load(str(concept), check_existing=False)
    tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.extension = "EXTEND"       # never wrap; the concept is not tileable
    mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    obj.data.materials.append(mat)

    obj.data.uv_layers.new(name="projected")
    cam = game_camera(obj)
    model_box = project_uvs(obj, cam)
    cbox = concept_bounds(img)
    print(f"  model in frame  {tuple(round(v, 3) for v in model_box)}")
    print(f"  concept subject {tuple(round(v, 3) for v in cbox)}")
    fit_uvs(obj, model_box, cbox)

    report = ba.validate(obj, size_class, footprint)
    out = OUT_DIR / f"{args.asset}_L{args.level}.glb"
    ba.export([obj], out)
    print(f"\nOK — {report['triangles']} triangles, painted from "
          f"{concept.name}, written to {out.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    raise SystemExit(main(argv))
