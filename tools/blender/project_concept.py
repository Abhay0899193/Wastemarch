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

# How much of a model may land on empty background before it is a defect rather
# than a rounding error. Every such face renders as a flat grey patch.
MAX_UNPAINTED = 0.08

# How far inside the painted building the model is fitted, as a fraction of the
# building's size. Enough to keep the outermost faces off the painting's own
# edge, small enough that nothing visibly shifts.
INSET = 0.02


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


def dilate_into_background(image, passes: int = 90):
    """Grow the painted building outward over the background.

    **This is why grey patches happened at all, and why chasing coverage to zero
    was the wrong fix.** A model's outline will never sit exactly on a painted
    building's outline; somewhere a merlon or a roof edge is a few pixels proud,
    and every one of those faces sampled flat background and rendered as a grey
    hole. Tuning proportions shrank the problem and could not remove it.

    Texture atlases have solved this for decades and the answer is *padding*:
    bleed the artwork outward past its own edge, so anything sampling slightly
    off the edge picks up plausible colour instead of emptiness. The building
    grows a skirt of its own edge pixels and the grey has nowhere to appear.

    Ninety passes is about ninety pixels of bleed at 1024, which is far more than
    any misalignment seen so far and costs a fraction of a second.
    """
    import numpy as np

    w, h = image.size
    px = np.empty(w * h * 4, dtype=np.float32)
    image.pixels.foreach_get(px)
    rgba = px.reshape(h, w, 4)
    rgb = rgba[:, :, :3]

    bg = rgb[0, 0].copy()
    filled = np.abs(rgb - bg).sum(axis=2) > BACKGROUND_TOLERANCE

    for _ in range(passes):
        if filled.all():
            break
        # Any empty pixel with a filled neighbour takes that neighbour's colour.
        for shift, axis in ((1, 0), (-1, 0), (1, 1), (-1, 1)):
            src = np.roll(filled, shift, axis=axis)
            src_rgb = np.roll(rgb, shift, axis=axis)
            take = src & ~filled
            if not take.any():
                continue
            rgb[take] = src_rgb[take]
            filled |= take

    rgba[:, :, :3] = rgb
    rgba[:, :, 3] = 1.0
    image.pixels.foreach_set(rgba.reshape(-1))
    image.update()
    return float(filled.mean())


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


def fit_uvs(obj, model_box, concept_box, inset: float = INSET) -> None:
    """Stretch the projected UVs so the model lands on the painted building.

    **Slightly inside it, not exactly on it.** Fitting the two outlines exactly
    leaves the model's outermost geometry sampling the last pixel of the
    painting or the first pixel past it, and that produced a pale sliver down the
    left silhouette of every building — the concept's brightly lit left wall
    bleeding outward. Landing a few percent inside means every face samples real
    paint and only the painting's outermost pixels go unused.

    This is the opposite of bleeding outward, and it is the better half of the
    pair: bleed covers gross misalignment, inset covers the edge itself.
    """
    mx0, my0, mx1, my1 = model_box
    cx0, cy0, cx1, cy1 = concept_box
    px = (cx1 - cx0) * inset
    py = (cy1 - cy0) * inset
    cx0, cx1 = cx0 + px, cx1 - px
    cy0, cy1 = cy0 + py, cy1 - py
    sx = (cx1 - cx0) / max(1e-6, mx1 - mx0)
    sy = (cy1 - cy0) / max(1e-6, my1 - my0)

    uv = obj.data.uv_layers.active
    for d in uv.data:
        d.uv = (cx0 + (d.uv[0] - mx0) * sx,
                cy0 + (d.uv[1] - my0) * sy)


def _screen_area(uv, poly) -> float:
    """A polygon's area as the player sees it, from its projected UVs.

    **Not its surface area in metres, which is what this used to measure and
    which was wrong.** A roof seen from 30 degrees above covers far more of the
    screen than a wall of the same size, so weighting by surface area made a
    visually obvious grey roof read as "3% — fine". The camera decides how big
    something looks, so the camera has to decide how much it counts.
    """
    pts = [uv.data[li].uv for li in poly.loop_indices]
    a = 0.0
    for i in range(len(pts)):
        j = (i + 1) % len(pts)
        a += pts[i][0] * pts[j][1] - pts[j][0] * pts[i][1]
    return abs(a) / 2


def coverage(obj, image, concept_box) -> tuple:
    """How much of what the player sees lands on empty background.

    Samples the concept image at the centre of every polygon. A face whose
    centre falls on background renders as a flat grey patch in the game, so this
    counts exactly the defect that is visible — weighted by how much of the
    screen each face actually occupies.

    Also returns the worst offenders, because a single number says a model is
    wrong and a list says which part of it to fix.
    """
    w, h = image.size
    px = [0.0] * (w * h * 4)
    image.pixels.foreach_get(px)
    bg = (px[0], px[1], px[2])

    def is_background(u, v):
        x = min(w - 1, max(0, int(u * w)))
        y = min(h - 1, max(0, int(v * h)))
        j = (y * w + x) * 4
        return (abs(px[j] - bg[0]) + abs(px[j + 1] - bg[1])
                + abs(px[j + 2] - bg[2])) <= BACKGROUND_TOLERANCE

    uv = obj.data.uv_layers.active
    missed = 0.0
    total = 0.0
    offenders = []
    for poly in obj.data.polygons:
        area = _screen_area(uv, poly)
        total += area

        # **Sampled across the face, not at its centre.** Centre-sampling was
        # the second thing wrong with this measurement: the granary's roof is a
        # single large quad whose centre sits comfortably on the painted roof
        # while half of it hangs off into background. One sample said "painted",
        # the screen said otherwise, and the screen was right.
        #
        # A grid over the polygon's own UV bounds, clipped to the polygon by
        # barycentric-style averaging of its corners, is enough: what matters is
        # the *fraction* of the face that misses, not its exact outline.
        pts = [uv.data[li].uv for li in poly.loop_indices]
        n = len(pts)
        samples = []
        for i in range(n):                       # corners, pulled slightly in
            j2 = (i + 1) % n
            cx = sum(p[0] for p in pts) / n
            cy = sum(p[1] for p in pts) / n
            samples.append((pts[i][0] * 0.8 + cx * 0.2,
                            pts[i][1] * 0.8 + cy * 0.2))
            samples.append(((pts[i][0] + pts[j2][0]) / 2,      # edge midpoints
                            (pts[i][1] + pts[j2][1]) / 2))
            samples.append(((pts[i][0] + cx) / 2, (pts[i][1] + cy) / 2))
        samples.append((sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n))

        bad = sum(1 for u, v in samples if is_background(u, v))
        frac = bad / len(samples)
        if frac > 0.0:
            missed += area * frac
            c = poly.center
            offenders.append((area * frac,
                              (round(c.x, 2), round(c.y, 2), round(c.z, 2)),
                              frac))

    offenders.sort(reverse=True)
    return (missed / total if total else 1.0), offenders


def render_for_paint(obj, path: Path, size: int = 1024) -> None:
    """Render the model flat, at the game camera, for an image model to paint over.

    **This inverts the whole problem.** Tuning a model to match a painting is
    guesswork with four or five parameters against an image that was never drawn
    to any dimensions. Painting over the model's own render instead means the
    painting has the model's proportions exactly, and projecting it back lands on
    every face by construction.

    The background must be the flat grey `concept_bounds` looks for, and the
    lighting must be even — this is a base for painting, not a beauty shot.
    """
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = scene.render.resolution_y = size
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"

    world = bpy.data.worlds.new("paint_bg")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.28, 0.28, 0.29, 1.0)
    bg.inputs[1].default_value = 1.0
    scene.world = world

    sun_data = bpy.data.lights.new("sun", type="SUN")
    sun_data.energy = 2.6
    sun = bpy.data.objects.new("sun", sun_data)
    sun.rotation_euler = (math.radians(48), 0, math.radians(-55))
    bpy.context.collection.objects.link(sun)

    path.parent.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--asset", required=True)
    ap.add_argument("--level", type=int, default=1)
    ap.add_argument("--render-for-paint",
                    help="render the model flat at the game camera and stop")
    ap.add_argument("--paint-from",
                    help="use this image instead of the picked concept")
    args = ap.parse_args(argv)

    if args.asset not in ba.BUILDERS:
        raise SystemExit(f"No builder for '{args.asset}'")
    if args.asset not in ba.PROJECTED:
        raise SystemExit(
            f"'{args.asset}' is not painted by projection — see PROJECTED in\n"
            f"build_asset.py. It is an open structure, so most of it would land\n"
            f"on empty background. Build it with build_asset.py instead.")

    if args.render_for_paint:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        obj, _, _ = ba.BUILDERS[args.asset](args.level)
        game_camera(obj)
        render_for_paint(obj, Path(args.render_for_paint))
        print(f"rendered {args.asset} for painting -> {args.render_for_paint}")
        return 0

    # Resolved against the repo, so a relative path typed on the command line
    # works the same as an absolute one.
    concept = (Path(args.paint_from) if args.paint_from
               else picked_concept(args.asset))
    if args.paint_from and not concept.is_absolute():
        concept = (REPO / concept).resolve()
    try:
        shown = concept.relative_to(REPO)
    except ValueError:
        shown = concept
    print(f"projecting {shown} onto {args.asset}")

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
    # Without this glTF exports `doubleSided: true` and the engine draws the
    # inside of far walls, showing the projection smeared through the model.
    mat.use_backface_culling = True
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

    # Bounds must be measured BEFORE the bleed, or the building's outline is the
    # whole image and the fit is meaningless.
    cbox = concept_bounds(img)
    covered = dilate_into_background(img)
    print(f"  bled edges outward, {covered:.0%} of the image now painted")
    print(f"  model in frame  {tuple(round(v, 3) for v in model_box)}")
    print(f"  concept subject {tuple(round(v, 3) for v in cbox)}")
    fit_uvs(obj, model_box, cbox)

    missed, offenders = coverage(obj, img, cbox)
    print(f"  on background   {missed:.1%} of what the player sees")
    if offenders:
        share = sum(a for a, _, _ in offenders)
        print("  worst unpainted faces, by how much screen they take:")
        for area, centre, frac in offenders[:5]:
            print(f"    {area / share:5.1%} of the grey — face at {centre} "
                  f"is {frac:.0%} off the painting")
    if missed > MAX_UNPAINTED:
        print(f"  WARNING: over {MAX_UNPAINTED:.0%} of what the player sees lands\n"
              f"           on empty background and renders as flat grey. Use the\n"
              f"           positions above to find which part of the model does\n"
              f"           not match its concept.")

    report = ba.validate(obj, size_class, footprint)
    out = OUT_DIR / f"{args.asset}_L{args.level}.glb"
    ba.export([obj], out)
    print(f"\nOK — {report['triangles']} triangles, {1 - missed:.0%} painted, "
          f"from {concept.name}, written to {out.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    raise SystemExit(main(argv))
