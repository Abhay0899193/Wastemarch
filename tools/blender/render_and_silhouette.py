"""Render every building at the game camera, and run the silhouette test.

    $BLENDER --background --factory-startup --python tools/blender/render_and_silhouette.py

Writes two things per building into `assets-src/render/`:

  * `<asset>_L<n>.png`      — a look at it, at the real game camera
  * `<asset>_L<n>_sil.png`  — the same thing as a solid black shape, 64 px tall

and then compares every pair of silhouettes and **fails** if two buildings are
too similar.

**Why a machine can run this test at all.** `docs/ART_BIBLE.md` states the rule
as "fill the building with solid black, shrink it to 64 pixels, and you must
still be able to tell which building it is". Whether a person recognises a shape
is not something a script can judge. What a script *can* judge is the thing that
makes recognition impossible: two buildings whose black shapes are nearly the
same. That is the failure the rule exists to prevent, and it is measurable.

So this reports overlap between every pair. Two buildings sharing more than
`MAX_SIMILARITY` of their silhouette are a defect — not because the number is
sacred, but because at that point the player is being asked to tell apart shapes
that are, in fact, the same shape.
"""

import math
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_asset as ba  # noqa: E402

REPO = Path(__file__).resolve().parent.parent.parent
OUT = REPO / "assets-src" / "render"

# From docs/ART_BIBLE.md — the camera everything is designed for.
ELEVATION_DEG = 30.0
YAW_DEG = 45.0

SIL_PX = 64          # the size the rule names
LOOK_PX = 512        # big enough to judge, small enough to commit
MAX_SIMILARITY = 0.80

# What to render. The keep appears twice because its whole point is that it
# changes shape as it upgrades, and the two ends must not be confusable either.
SUBJECTS = [("granary", 1), ("watchtower", 1), ("keep", 1), ("keep", 5),
            ("croft", 1), ("logging_camp", 1), ("mine", 1)]


def game_camera(ortho_scale: float, target_height: float):
    """An orthographic camera at 30 degrees elevation and 45 degrees yaw.

    **The scale is the same for every building, deliberately.** An earlier
    version fitted the frame to each subject, which made a 4.2 m watchtower and a
    2.5 m shed the same size on screen — and size is a large part of how a player
    tells buildings apart in a game where they all stand on the same ground. A
    silhouette test that normalises away the size difference is measuring
    something the player never sees.
    """
    cam_data = bpy.data.cameras.new("game_camera")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = ortho_scale
    cam = bpy.data.objects.new("game_camera", cam_data)
    bpy.context.collection.objects.link(cam)

    elev, yaw = math.radians(ELEVATION_DEG), math.radians(YAW_DEG)
    dist = 30.0
    cam.location = (dist * math.cos(elev) * math.sin(yaw),
                    -dist * math.cos(elev) * math.cos(yaw),
                    dist * math.sin(elev) + target_height / 2)
    # Point at the middle of the subject. Written as angles rather than a matrix
    # for the same reason the .tscn files are — a transposed basis is silent.
    cam.rotation_euler = (math.radians(90) - elev, 0.0, yaw)
    bpy.context.scene.camera = cam
    return cam


def setup_scene(silhouette: bool, size_px: int, ortho_scale: float, subject_h: float):
    scene = bpy.context.scene
    # Blender 5.2 lists this as BLENDER_EEVEE. The 4.x-era name
    # BLENDER_EEVEE_NEXT, which most examples online still use, raises here.
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = scene.render.resolution_y = size_px
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"

    world = bpy.data.worlds.new("w")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.0, 0.0, 0.0, 1.0) if silhouette else (0.35, 0.36, 0.38, 1)
    bg.inputs[1].default_value = 0.0 if silhouette else 1.1
    scene.world = world

    if not silhouette:
        sun_data = bpy.data.lights.new("sun", type="SUN")
        sun_data.energy = 3.2
        sun = bpy.data.objects.new("sun", sun_data)
        sun.rotation_euler = (math.radians(50), 0, math.radians(-55))
        bpy.context.collection.objects.link(sun)

    game_camera(ortho_scale, subject_h)


def flat_material(colour):
    mat = bpy.data.materials.new("flat")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    if colour is None:                       # pure black, unlit — the silhouette
        shader = nt.nodes.new("ShaderNodeEmission")
        shader.inputs[0].default_value = (0, 0, 0, 1)
        shader.inputs[1].default_value = 1.0
    else:
        shader = nt.nodes.new("ShaderNodeBsdfDiffuse")
        shader.inputs[0].default_value = (*colour, 1.0)
    nt.links.new(shader.outputs[0], out.inputs["Surface"])
    return mat


def subject_size(asset: str, level: int) -> tuple[float, float]:
    """Height and footprint radius in metres, without rendering anything."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    # **Through `ba.build`, never `ba.BUILDERS` directly.** This was the third
    # place that made its own copy of a model, and like the other two it skipped
    # reproportioning — so the silhouette test was faithfully measuring geometry
    # the game never sees. A shared builder with three entry points is a bug
    # generator; there is one entry point now.
    obj, _, footprint, _ = ba.build(asset, level)
    zs = [v.co.z for v in obj.data.vertices]
    return max(zs) - min(zs), max(footprint) * ba.TILE


def render_one(asset: str, level: int, silhouette: bool, ortho_scale: float) -> Path:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    obj, _, _, _ = ba.build(asset, level)

    zs = [v.co.z for v in obj.data.vertices]
    height = max(zs) - min(zs)

    setup_scene(silhouette, SIL_PX if silhouette else LOOK_PX, ortho_scale, height)

    if silhouette:
        # One solid black material replacing all of them — the silhouette is
        # about shape only, and any colour at all would leak into the mask.
        obj.data.materials.clear()
        obj.data.materials.append(flat_material(None))
        for poly in obj.data.polygons:
            poly.material_index = 0

    suffix = "_sil" if silhouette else ""
    path = OUT / f"{asset}_L{level}{suffix}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.context.scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    return path


def silhouette_mask(path: Path) -> list[bool]:
    """Which pixels the building covers. Alpha, because the film is transparent."""
    img = bpy.data.images.load(str(path))
    px = list(img.pixels)
    mask = [px[i + 3] > 0.5 for i in range(0, len(px), 4)]
    bpy.data.images.remove(img)
    return mask


def similarity(a: list[bool], b: list[bool]) -> float:
    """Intersection over union — 1.0 means the same shape, 0.0 means no overlap."""
    inter = sum(1 for x, y in zip(a, b) if x and y)
    union = sum(1 for x, y in zip(a, b) if x or y)
    return inter / union if union else 1.0


def main() -> int:
    # One framing for everything, set by whichever building is biggest, so the
    # renders are comparable to each other and to the game.
    sizes = [subject_size(a, l) for a, l in SUBJECTS]
    ortho_scale = max(max(h * 1.5, r * 2.4) for h, r in sizes)
    print(f"framing every subject at ortho scale {ortho_scale:.2f} m\n")

    masks = {}
    for asset, level in SUBJECTS:
        look = render_one(asset, level, False, ortho_scale)
        sil = render_one(asset, level, True, ortho_scale)
        name = f"{asset}_L{level}"
        masks[name] = silhouette_mask(sil)
        covered = sum(masks[name]) / len(masks[name])
        print(f"  rendered {name:<16} {look.name}, {sil.name}, "
              f"covers {covered:.1%} of the frame")

    print("\n=== silhouette overlap (1.00 would be the same shape) ===")
    names = list(masks)
    failures = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            s = similarity(masks[a], masks[b])
            flag = "  <-- TOO SIMILAR" if s > MAX_SIMILARITY else ""
            print(f"  {a:<16} vs {b:<16} {s:.2f}{flag}")
            if s > MAX_SIMILARITY:
                failures.append(f"{a} and {b} share {s:.0%} of their silhouette")

    if failures:
        print("\nSILHOUETTE TEST FAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"\nOK — every pair differs by more than "
          f"{1 - MAX_SIMILARITY:.0%} of its silhouette")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
