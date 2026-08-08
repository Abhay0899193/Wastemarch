"""Stage 2 of the asset pipeline — build a building, headless, from a script.

    $BLENDER --background --factory-startup --python tools/blender/build_asset.py -- --asset granary
    $BLENDER --background --factory-startup --python tools/blender/build_asset.py -- --list

Runs inside Blender, so it can only use Blender's own Python. Never import
anything from `tools/pipeline/` here.

**Why buildings are built by script rather than modelled by hand.** Every
building exists at five upgrade levels. Five hand-made models per building, times
twenty-four buildings, is a hundred and twenty models to make and then to keep
consistent forever. One script with a `level` parameter is one thing to fix when
the art direction moves. `MASTER_PLAN.md` section 7.3 makes this the rule, not a
preference.

Every asset is validated as it is built and the build **fails** rather than
warns. A budget that only warns is a budget that gets exceeded.
"""

import argparse
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy

REPO = Path(__file__).resolve().parent.parent.parent
OUT_DIR = REPO / "assets-src" / "model"

# From docs/ART_BIBLE.md. These are the numbers the build fails on.
TEXEL_DENSITY = 256          # pixels per world metre, uniform, no exceptions
LOD1_RATIO = 0.4             # LOD1 must be no more than 40% of the original

# Below this, a model does not get an LOD1 at all. A second mesh costs memory
# and a draw call; saving ninety triangles does not pay for that. Measured
# against the granary, which is 162 triangles — see docs/ART_BIBLE.md.
LOD_MIN_TRIS = 400
BUDGETS = {"small": 1500, "large": 4000, "troop": 900}

# 1 Blender unit = 1 metre, and a tile is 1 metre square, so a 2x2 building is
# 2 metres across. docs/ART_BIBLE.md.
TILE = 1.0


# ---------------------------------------------------------------------------
# Small helpers for building shapes. Deliberately plain: every building is boxes
# and prisms, because that is what survives a 1,500 triangle budget.
# ---------------------------------------------------------------------------

def new_mesh(name):
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def box(bm, centre, size):
    """An axis-aligned box. 12 triangles."""
    cx, cy, cz = centre
    sx, sy, sz = (s / 2 for s in size)
    verts = [bm.verts.new((cx + x * sx, cy + y * sy, cz + z * sz))
             for x, y, z in ((-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
                             (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1))]
    for a, b, c, d in ((0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1),
                       (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)):
        bm.faces.new((verts[a], verts[b], verts[c], verts[d]))
    return verts


def gable_roof(bm, centre, size, ridge_height):
    """A simple pitched roof: two slopes and two triangular ends. 8 triangles."""
    cx, cy, cz = centre
    sx, sy = size[0] / 2, size[1] / 2
    e = [bm.verts.new((cx + x * sx, cy + y * sy, cz))
         for x, y in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    r0 = bm.verts.new((cx - sx, cy, cz + ridge_height))
    r1 = bm.verts.new((cx + sx, cy, cz + ridge_height))
    bm.faces.new((e[0], e[1], r1, r0))     # front slope
    bm.faces.new((e[2], e[3], r0, r1))     # back slope
    bm.faces.new((e[1], e[2], r1))         # gable end
    bm.faces.new((e[3], e[0], r0))         # gable end


def ramp(bm, start, end, width, thickness):
    """A sloped plank, used for the granary's grain chute."""
    ax, ay, az = start
    bx, by, bz = end
    dx, dy = bx - ax, by - ay
    length = math.hypot(dx, dy)
    if length == 0:
        raise ValueError("ramp needs a horizontal run")
    nx, ny = -dy / length * width / 2, dx / length * width / 2
    lower = [(ax + nx, ay + ny, az), (ax - nx, ay - ny, az),
             (bx - nx, by - ny, bz), (bx + nx, by + ny, bz)]
    top = [bm.verts.new(p) for p in lower]
    bot = [bm.verts.new((x, y, z - thickness)) for x, y, z in lower]
    bm.faces.new(top)
    bm.faces.new(tuple(reversed(bot)))
    for i in range(4):
        j = (i + 1) % 4
        bm.faces.new((top[i], top[j], bot[j], bot[i]))


# ---------------------------------------------------------------------------
# The buildings. Each returns (object, size_class).
#
# Proportions come from the picked concept in assets-src/concept/PICKS.md.
# ---------------------------------------------------------------------------

def build_granary(level: int = 1, detail: bool = True):
    """2x2 tiles. Timber grain store on a stone footing, with a loading lean-to.

    Matched to `assets-src/concept/granary/granary_1004.png`.

    **The lean-to is the point.** It is what makes this building identifiable as
    a solid black shape at 64 pixels: everything else here is a box with a
    pitched roof, which describes half the buildings in the game. The asymmetric
    shed roof and the sacks under it are the silhouette, so they are generous
    rather than subtle, and they are the last thing that should ever be
    simplified away in an LOD.
    """
    obj = new_mesh("granary")
    bm = bmesh.new()

    foot = 2.0 * TILE                    # the 2x2 tiles it occupies
    lean_d = 0.62                        # depth of the open lean-to
    body_d = foot - lean_d
    stone_h = 0.22                       # stone footing course, keeps grain dry
    body_h = 1.45 + 0.2 * (level - 1)    # a taller store at higher levels
    ridge = 0.85

    body_y = foot / 2 - body_d / 2       # body pushed to the back of the plot
    lean_y = -foot / 2 + lean_d / 2

    box(bm, (0, body_y, stone_h / 2), (foot + 0.1, body_d + 0.1, stone_h))
    box(bm, (0, body_y, stone_h + body_h / 2), (foot, body_d, body_h))
    gable_roof(bm, (0, body_y, stone_h + body_h),
               (foot + 0.34, body_d + 0.30), ridge)

    # Plank door on the gable end, sunk slightly so it reads as an opening.
    if detail:
        box(bm, (-foot / 2 + 0.02, body_y + 0.1, stone_h + 0.52),
            (0.1, 0.6, 1.04))

    # The lean-to: a shed roof falling away from the body wall, on three posts.
    # `ramp` takes the centre line of the plank, not one edge — passing the wall
    # edge here put the whole roof a metre off to one side, which the overhang
    # check caught immediately.
    eave_z = stone_h + body_h * 0.86
    ramp(bm, (0.0, body_y - body_d / 2, eave_z),
         (0.0, -foot / 2 + 0.04, eave_z - 0.34),
         width=foot, thickness=0.09)
    for px in (-foot / 2 + 0.12, 0.0, foot / 2 - 0.12):
        box(bm, (px, lean_y - lean_d / 2 + 0.1, (eave_z - 0.34) / 2),
            (0.11, 0.11, eave_z - 0.34))

    # Grain sacks, stacked two deep under the lean-to. These are what say
    # "store" without any need for a sign — and they are also pure detail, so
    # they are the first thing dropped at distance.
    if detail:
        for sx, sy, sz, s in ((-0.62, 0.06, 0.15, 0.34), (-0.22, 0.02, 0.15, 0.32),
                              (0.20, 0.06, 0.15, 0.33), (0.62, 0.02, 0.15, 0.31),
                              (-0.42, 0.10, 0.44, 0.30), (0.40, 0.06, 0.44, 0.29)):
            box(bm, (sx, lean_y + sy, sz), (s, s * 0.8, 0.30))

    bm.to_mesh(obj.data)
    bm.free()
    return obj, "small", (2, 2)


BUILDERS = {"granary": build_granary}


# ---------------------------------------------------------------------------
# Unwrap, LOD, validate, export.
# ---------------------------------------------------------------------------

def unwrap(obj) -> None:
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    # angle_limit is radians in the 5.x API. 66 degrees is Blender's own default
    # and splits boxes at their corners, which is what we want.
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.02)
    bpy.ops.object.mode_set(mode="OBJECT")


def surface_area(obj) -> float:
    return sum(p.area for p in obj.data.polygons)


def uv_area(obj) -> float:
    """Fraction of the 0..1 texture square the unwrap actually covers."""
    uvs = obj.data.uv_layers.active.data
    total = 0.0
    for poly in obj.data.polygons:
        pts = [uvs[i].uv for i in poly.loop_indices]
        # Shoelace formula, which handles the quads and triangles we produce.
        a = 0.0
        for i in range(len(pts)):
            j = (i + 1) % len(pts)
            a += pts[i].x * pts[j].y - pts[j].x * pts[i].y
        total += abs(a) / 2
    return total


def atlas_demand(obj) -> dict:
    """How much of the shared texture atlas this asset needs at 256 px/metre.

    **The unit here matters and it is easy to get wrong.** An earlier version
    reported "the texture size this asset needs", which for a 2x2 shed came out
    at 4096x4096 — an absurd answer that was arithmetically correct. The mistake
    was the unit: `docs/ART_BIBLE.md` says all buildings share **one material and
    one texture sheet**, so an asset does not have a texture size. It has a claim
    on atlas area, and the packer decides where that lands.

    Texel density is pixels per metre measured across the surface, so an asset
    with `a` square metres of surface needs `a * 256^2` texels, whatever shape
    they end up. UV coverage says how much bigger its slot must be than that to
    account for the empty space between islands.
    """
    a, u = surface_area(obj), uv_area(obj)
    if a <= 0 or u <= 0:
        raise ValueError("cannot measure texel density on an empty unwrap")
    needed = a * TEXEL_DENSITY ** 2
    return {
        "texels_needed": round(needed),
        "atlas_slot_texels": round(needed / u),
        "uv_coverage": round(u, 4),
        "equivalent_square_px": round(math.sqrt(needed / u)),
    }


def triangles(obj) -> int:
    obj.data.calc_loop_triangles()
    return len(obj.data.loop_triangles)


# How far a building may stick out past the tiles it occupies. Roof eaves and
# lean-tos overhanging is normal and good — it is what stops a base looking like
# a grid of boxes. Overhanging far enough to sit on top of the neighbouring
# building is not.
MAX_OVERHANG = 0.35


def validate(obj, size_class: str, footprint_tiles) -> dict:
    """Every rule from CLAUDE.md and ART_BIBLE.md that a script can check.

    Returns a report. Raises on anything that must stop the build.

    **The footprint is declared, not measured.** An earlier version took the
    origin rule to mean "the mesh bounding box must be centred", and the first
    building failed it — correctly by that reading and wrongly in fact, because
    an overhanging lean-to is meant to be off-centre. What has to be centred is
    the *tiles the building occupies on the grid*, which the builder declares.
    Overhang beyond those tiles is then measured and capped separately.
    """
    problems = []
    fw, fd = (t * TILE for t in footprint_tiles)

    tris = triangles(obj)
    budget = BUDGETS[size_class]
    if tris > budget:
        problems.append(f"{tris} triangles over the {size_class} budget of {budget}")

    ngons = [p.index for p in obj.data.polygons if len(p.vertices) > 4]
    if ngons:
        problems.append(f"{len(ngons)} n-gon(s) — faces with more than four sides")

    used = {v for p in obj.data.polygons for v in p.vertices}
    loose = [v.index for v in obj.data.vertices if v.index not in used]
    if loose:
        problems.append(f"{len(loose)} loose vertices, attached to no face")

    if tuple(round(s, 6) for s in obj.scale) != (1.0, 1.0, 1.0):
        problems.append(f"object scale is {tuple(obj.scale)}, must be 1 — "
                        f"1 unit is 1 metre and a scaled object breaks that")

    xs = [v.co.x for v in obj.data.vertices]
    ys = [v.co.y for v in obj.data.vertices]
    zs = [v.co.z for v in obj.data.vertices]

    # The model sits on the ground. Below zero is a building sunk into the
    # terrain, which reads as a bug on every screen it appears on.
    if min(zs) < -1e-4:
        problems.append(f"lowest point is z={min(zs):.3f}, must not be below 0 — "
                        f"the model must sit on the ground, not sink into it")
    if min(zs) > 1e-3:
        problems.append(f"lowest point is z={min(zs):.3f}, must be 0 — "
                        f"the model is floating above the ground")

    overhang = max(max(xs) - fw / 2, -min(xs) - fw / 2,
                   max(ys) - fd / 2, -min(ys) - fd / 2, 0.0)
    if overhang > MAX_OVERHANG:
        problems.append(
            f"overhangs its {footprint_tiles[0]}x{footprint_tiles[1]} tile "
            f"footprint by {overhang:.3f} m, more than the {MAX_OVERHANG} m "
            f"allowed — it would sit on top of the next building")

    if not obj.data.uv_layers:
        problems.append("no UV layer — the model was never unwrapped")

    if problems:
        raise SystemExit("VALIDATION FAILED for '%s':\n  - %s"
                         % (obj.name, "\n  - ".join(problems)))

    return {
        "triangles": tris,
        "budget": budget,
        "size_class": size_class,
        "surface_area_m2": round(surface_area(obj), 3),
        **atlas_demand(obj),
        "footprint_tiles": list(footprint_tiles),
        "overhang_m": round(overhang, 3),
        "extent_m": [round(max(xs) - min(xs), 3), round(max(ys) - min(ys), 3)],
        "height_m": round(max(zs) - min(zs), 3),
    }


def make_lod1(builder, level: int):
    """The same building with its detail parts left out.

    **Not decimation, deliberately.** Blender's decimate modifier collapses
    triangles by error metric, which on hard-surface box geometry eats corners
    and rounds off exactly the silhouette the Art Bible spends a whole section
    protecting. Measured on the granary it also produced a mesh Blender's own
    `validate()` reported as broken, which glTF then warned it "may export
    wrongly".

    Dropping whole detail parts instead is deterministic, keeps every silhouette
    edge intact, and is free — the builder already knows which parts are detail,
    because a person decided that when they wrote it.
    """
    lod, _, _ = builder(level, detail=False)
    lod.name = f"{lod.name}_LOD1"
    if lod.data.validate(verbose=False):
        raise SystemExit(f"LOD1 for {lod.name} needed repair — the builder "
                         f"produced invalid geometry with detail off")
    return lod


def export(objs, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.export_scene.gltf(
        filepath=str(path),
        export_format="GLB",
        use_selection=True,
        export_yup=True,       # Godot is Y-up, Blender is Z-up
        export_apply=True,
    )


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--asset")
    ap.add_argument("--level", type=int, default=1)
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args(argv)

    if args.list or not args.asset:
        print("Buildable assets: " + ", ".join(sorted(BUILDERS)))
        return 0

    if args.asset not in BUILDERS:
        raise SystemExit(f"No builder for '{args.asset}'. "
                         f"Have: {', '.join(sorted(BUILDERS))}")

    bpy.ops.wm.read_factory_settings(use_empty=True)

    obj, size_class, footprint = BUILDERS[args.asset](args.level)
    unwrap(obj)
    report = validate(obj, size_class, footprint)

    # An LOD only pays for itself on a model big enough to save something.
    if report["triangles"] >= LOD_MIN_TRIS:
        lod = make_lod1(BUILDERS[args.asset], args.level)
        lod_tris = triangles(lod)
        allowed = int(report["triangles"] * LOD1_RATIO)
        if lod_tris > allowed:
            raise SystemExit(
                f"VALIDATION FAILED: LOD1 is {lod_tris} triangles, over the "
                f"{allowed} allowed ({LOD1_RATIO:.0%} of {report['triangles']}). "
                f"Mark more parts as detail in the builder.")
        report["lod1_triangles"] = lod_tris
        objs = [obj, lod]
    else:
        report["lod1_triangles"] = None
        report["lod1_skipped"] = (
            f"{report['triangles']} triangles is below the {LOD_MIN_TRIS} "
            f"threshold — a second mesh would cost more than it saves")
        objs = [obj]

    out = OUT_DIR / f"{args.asset}_L{args.level}.glb"
    export(objs, out)
    report["file"] = str(out.relative_to(REPO))
    report["level"] = args.level

    (OUT_DIR / f"{args.asset}_L{args.level}.json").write_text(
        json.dumps(report, indent=2) + "\n")

    print("\n=== %s level %d ===" % (args.asset, args.level))
    for k, v in report.items():
        print(f"  {k:<18} {v}")
    lod_note = (f"LOD1 {report['lod1_triangles']}" if report["lod1_triangles"]
                else "no LOD1 needed")
    print(f"\nOK — {report['triangles']}/{report['budget']} triangles, {lod_note}, "
          f"{report['atlas_slot_texels'] / 1e6:.2f}M atlas texels "
          f"(~{report['equivalent_square_px']}px square)")
    return 0


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    raise SystemExit(main(argv))
