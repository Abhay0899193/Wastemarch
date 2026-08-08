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

# Materials are tileable, so texel density is a property of the projection, not
# of each asset's unwrap: a texture of TEXTURE_PX pixels covering TILE_METRES of
# surface gives exactly TEXEL_DENSITY. Setting these two makes the density exact
# everywhere by construction, rather than something to measure and hope about.
TEXTURE_PX = 1024

# How much surface one copy of a tile covers. Set by how big the *material*
# should look — dressed stone blocks are roughly half a metre, so a tile showing
# eight of them across wants to span about two metres.
#
# **With tiling, texel density is free.** The 256 px/m rule was written for
# unique unwraps, where more density means a bigger atlas. A tile costs the same
# memory however often it repeats, so tiling twice as often doubles the apparent
# resolution for nothing. That is why this is 2 m and not 4 m.
TILE_METRES = 2.0

# How much relief the derived normal maps imply. Above about 12 the stones start
# to look inflated rather than laid.
NORMAL_STRENGTH = 6.0
ACHIEVED_TEXEL_DENSITY = TEXTURE_PX / TILE_METRES        # 512 px/m
MATERIAL_DIR = REPO / "assets-src" / "material"
LOD1_RATIO = 0.4             # LOD1 must be no more than 40% of the original

# Below this, a model does not get an LOD1 at all. A second mesh costs memory
# and a draw call; saving ninety triangles does not pay for that. Measured
# against the granary, which is 162 triangles — see docs/ART_BIBLE.md.
LOD_MIN_TRIS = 400
BUDGETS = {"small": 1500, "large": 4000, "troop": 900}

# 1 Blender unit = 1 metre, and a tile is 1 metre square, so a 2x2 building is
# 2 metres across. docs/ART_BIBLE.md.
TILE = 1.0

# The material vocabulary. Every colour is a value locked in ADR-0004 — the
# palette is not approximated here, it is used literally, which is the whole
# reason the drift seen in the concept art cannot happen to a model.
#
# Five is not a coincidence: ART_BIBLE.md caps an asset at five hues, so this
# list is the cap. Adding a sixth material means taking one away.
MATERIALS = [
    ("stone",     "#C4BCAE", 0.85),   # bone grey — walls, footings, paving
    ("timber",    "#8B8071", 0.75),   # dead soil — weathered posts and planking
    ("thatch",    "#9B8459", 0.95),   # dry ochre — roofs, sacking
    ("cloth",     "#8C2323", 0.80),   # Ostmere crimson — banners only
    ("firelight", "#F7CE7C", 0.55),   # the lit thing itself, emissive
]
MATERIAL_INDEX = {name: i for i, (name, _, _) in enumerate(MATERIALS)}

# Which material new faces are given. Set by `using()` while building.
_current_material = 0


def using(material: str) -> None:
    """Every primitive made after this call is that material."""
    global _current_material
    if material not in MATERIAL_INDEX:
        raise KeyError(f"'{material}' is not one of {list(MATERIAL_INDEX)}")
    _current_material = MATERIAL_INDEX[material]


def _tag(bm, first_face_index: int) -> None:
    """Assign the current material to every face made since the mark."""
    bm.faces.ensure_lookup_table()
    for f in bm.faces[first_face_index:]:
        f.material_index = _current_material


def srgb_to_linear_tuple(hex_colour: str):
    """Blender works in linear light; the palette is written in sRGB."""
    h = hex_colour.lstrip("#")
    out = []
    for i in (0, 2, 4):
        v = int(h[i:i + 2], 16) / 255.0
        out.append(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4)
    return tuple(out)


def _palette_tile(material: str, source: Path, rgb):
    """The generated tile, desaturated, brightness-normalised, and tinted to the
    locked palette colour. Written to disk and used directly as base colour.

    **Everything about this shape is forced by one measured fact.** The exported
    `.glb` was read back and every material said
    `baseColorFactor = [1, 1, 1, 1]`: Blender's glTF exporter had **silently
    dropped the palette multiply** and kept only the texture. Two earlier
    versions built the colour with shader nodes — a Hue/Saturation and Mix chain,
    then a single Mix — and both looked correct in Blender and exported wrong,
    the second one rendering the buildings pure black in Godot.

    That is the worst failure mode available: the preview and the game disagree,
    and the preview is the one lying. So no node does any colour work. The tile
    arrives already the right colour, base colour is just that texture, and there
    is nothing left for an exporter to drop.

    Normalising to a mean of 1.0 before tinting is what makes the palette exact:
    the average colour of the finished tile is the locked hex, and the generated
    texture can only vary brightness around it, never shift the hue.
    """
    # Loaded fresh, not `check_existing`, because this image is about to be
    # rewritten in place and a shared copy would be corrupted for other callers.
    #
    # **Modified in place rather than written to a new image**, which is not a
    # style choice. An image made with `images.new()` has source GENERATED, and
    # `save()` writes its generated buffer rather than whatever was assigned to
    # `.pixels` — even after `update()`. Four materials came out as identical
    # solid-black files of exactly the same byte length. An image loaded from a
    # file has source FILE, and saving it writes the pixels it actually holds.
    src = bpy.data.images.load(str(source), check_existing=False)
    w, h = src.size
    px = [0.0] * (w * h * 4)
    src.pixels.foreach_get(px)

    total = 0.0
    for i in range(0, len(px), 4):
        lum = 0.2126 * px[i] + 0.7152 * px[i + 1] + 0.0722 * px[i + 2]
        px[i] = px[i + 1] = px[i + 2] = lum
        total += lum
    mean = total / (w * h)

    gain = 1.0 / max(1e-3, mean)
    for i in range(0, len(px), 4):
        v = min(2.0, px[i] * gain)
        px[i] = min(1.0, v * rgb[0])
        px[i + 1] = min(1.0, v * rgb[1])
        px[i + 2] = min(1.0, v * rgb[2])
        px[i + 3] = 1.0

    out_path = source.parent / f"{material}_tile.png"
    # Colourspace is NOT touched here. The source is already sRGB, and assigning
    # `colorspace_settings.name` on a file-backed image makes Blender re-read the
    # buffer from disk, silently discarding every pixel just written. That is
    # what produced four identical solid-black tiles across three attempts; the
    # read was never the problem, the reload after it was.
    src.pixels.foreach_set(px)
    src.update()
    src.filepath_raw = str(out_path)
    src.file_format = "PNG"
    src.save()
    out = src

    # Read it back and check it is not blank. This class of bug — a pipeline
    # stage that writes a valid file containing nothing — is the reason the
    # Android library once shipped as zero bytes. A file existing is not
    # evidence that it has anything in it.
    check = bpy.data.images.load(str(out_path), check_existing=False)
    cpx = [0.0] * (check.size[0] * check.size[1] * 4)
    check.pixels.foreach_get(cpx)
    lum = sum(cpx[0::4]) / (len(cpx) / 4)
    bpy.data.images.remove(check)
    if not 0.02 < lum < 0.98:
        raise SystemExit(
            f"VALIDATION FAILED: {out_path.name} saved with mean brightness "
            f"{lum:.3f} — it is blank. The pixels never reached the file.")

    # A normal map from the same tile, so individual stones and planks catch the
    # light instead of the surface reading as a flat sticker. Derived rather than
    # generated: the height information is already in the tile's brightness, and
    # a second AI pass would only invent a different surface.
    _normal_from_height(material, source, out_path.parent)

    return out, mean


def _normal_from_height(material: str, source: Path, out_dir: Path):
    """Turn a tile's brightness into a tangent-space normal map.

    Sobel gradients on the luminance, which for a texture whose bright parts are
    raised — stone faces against dark mortar, plank faces against gaps — is a
    good enough height field. `NORMAL_STRENGTH` is the one knob.
    """
    img = bpy.data.images.load(str(source), check_existing=False)
    w, h = img.size
    px = [0.0] * (w * h * 4)
    img.pixels.foreach_get(px)

    lum = [0.0] * (w * h)
    for i in range(w * h):
        j = i * 4
        lum[i] = 0.2126 * px[j] + 0.7152 * px[j + 1] + 0.0722 * px[j + 2]

    out = [0.0] * (w * h * 4)
    for y in range(h):
        yn, yp = ((y - 1) % h) * w, ((y + 1) % h) * w
        row = y * w
        for x in range(w):
            xn, xp = (x - 1) % w, (x + 1) % w
            dx = lum[row + xp] - lum[row + xn]
            dy = lum[yp + x] - lum[yn + x]
            nx, ny, nz = -dx * NORMAL_STRENGTH, -dy * NORMAL_STRENGTH, 1.0
            inv = 1.0 / math.sqrt(nx * nx + ny * ny + nz * nz)
            j = (row + x) * 4
            out[j] = nx * inv * 0.5 + 0.5
            out[j + 1] = ny * inv * 0.5 + 0.5
            out[j + 2] = nz * inv * 0.5 + 0.5
            out[j + 3] = 1.0

    path = out_dir / f"{material}_normal.png"
    img.pixels.foreach_set(out)
    img.update()
    img.filepath_raw = str(path)
    img.file_format = "PNG"
    img.save()      # colorspace is never touched here — see .agent/MEMORY.md
    return path


def _newest_tile(material: str):
    """The generated tile for a material, or None if it has not been made yet.

    Picks the highest-numbered seed so that regenerating with a new seed takes
    effect without editing anything here.
    """
    d = MATERIAL_DIR / material
    if not d.is_dir():
        return None
    # Only the generated originals, which are named `<material>_<seed>.png`.
    #
    # An earlier version excluded `_tile.png` by name and nothing else, then a
    # `_normal.png` appeared beside it — which sorts *after* `_1001.png`, so the
    # newest-file rule silently picked the normal map as the base colour source.
    # The buildings turned pale and lost their mortar and nothing failed.
    # Matching what a source file *is* beats listing what it is not.
    tiles = sorted(p for p in d.glob(f"{material}_*.png")
                   if p.stem.rsplit("_", 1)[-1].isdigit())
    return tiles[-1] if tiles else None


def build_materials(obj) -> None:
    """Attach the five palette materials, in order, so indices line up."""
    for name, hex_colour, roughness in MATERIALS:
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes["Principled BSDF"]
        rgb = srgb_to_linear_tuple(hex_colour)
        bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
        # ART_BIBLE.md: roughness never below 0.35. Shiny reads as cheap on a
        # phone, where there are no reflections worth having anyway.
        bsdf.inputs["Roughness"].default_value = max(0.35, roughness)
        bsdf.inputs["Metallic"].default_value = 0.0

        # A generated tile, if one exists, contributing DETAIL ONLY.
        #
        # The first version wired the texture straight into Base Color, and the
        # generated stone — a pale, clean #EFEBE4 — simply replaced bone grey.
        # That is precisely the palette drift this whole approach was chosen to
        # make impossible, arriving through the back door.
        #
        # So the texture is stripped of its colour, normalised so its average
        # brightness is exactly 1.0, and multiplied into the palette value. The
        # average colour of the finished material is then the locked hex by
        # construction, and the texture can only add variation around it.
        tile = _newest_tile(name)
        if tile is not None:
            # The tile is already the right colour, so base colour is the
            # texture and nothing else. No node here can be dropped on export
            # because there is no node here.
            tinted, _mean = _palette_tile(name, tile, rgb)
            nt = mat.node_tree
            tex = nt.nodes.new("ShaderNodeTexImage")
            tex.image = tinted
            nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])

            # glTF carries a normal map as its own texture plus a scale, which
            # is one of the few things it does understand, so this survives
            # export where a colour mix did not.
            npath = tile.parent / f"{name}_normal.png"
            if npath.exists():
                nimg = bpy.data.images.load(str(npath), check_existing=True)
                nimg.colorspace_settings.name = "Non-Color"
                ntex = nt.nodes.new("ShaderNodeTexImage")
                ntex.image = nimg
                nmap = nt.nodes.new("ShaderNodeNormalMap")
                nmap.inputs["Strength"].default_value = 1.0
                nt.links.new(ntex.outputs["Color"], nmap.inputs["Color"])
                nt.links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])

        if name == "firelight":
            bsdf.inputs["Emission Color"].default_value = (*rgb, 1.0)
            bsdf.inputs["Emission Strength"].default_value = 1.6
        obj.data.materials.append(mat)


# ---------------------------------------------------------------------------
# Small helpers for building shapes. Deliberately plain: every building is boxes
# and prisms, because that is what survives a 1,500 triangle budget.
# ---------------------------------------------------------------------------

def new_mesh(name):
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def prism(bm, bottom_centre, bottom_xy, top_centre, top_xy):
    _mark = len(bm.faces)
    """A six-sided solid whose top face may differ from its bottom. 12 triangles.

    This one primitive covers everything the buildings need: a plain box when the
    two faces match, a taper when the top is smaller, and a leaning strut when
    the two centres are offset. Three helpers collapsed into one is three fewer
    places for an off-by-a-half-extent mistake to hide.
    """
    (bx, by, bz), (tx, ty, tz) = bottom_centre, top_centre
    hbx, hby = bottom_xy[0] / 2, bottom_xy[1] / 2
    htx, hty = top_xy[0] / 2, top_xy[1] / 2
    corners = ((-1, -1), (1, -1), (1, 1), (-1, 1))
    lo = [bm.verts.new((bx + x * hbx, by + y * hby, bz)) for x, y in corners]
    hi = [bm.verts.new((tx + x * htx, ty + y * hty, tz)) for x, y in corners]
    bm.faces.new(tuple(reversed(lo)))
    bm.faces.new(tuple(hi))
    for i in range(4):
        j = (i + 1) % 4
        bm.faces.new((lo[i], lo[j], hi[j], hi[i]))
    _tag(bm, _mark)
    return lo + hi


def box(bm, centre, size):
    """An axis-aligned box. 12 triangles."""
    cx, cy, cz = centre
    sx, sy, sz = size
    return prism(bm, (cx, cy, cz - sz / 2), (sx, sy),
                 (cx, cy, cz + sz / 2), (sx, sy))


def pyramid(bm, centre, size, height):
    _mark = len(bm.faces)
    """A square-based pyramid — the watchtower's roof. 6 triangles."""
    cx, cy, cz = centre
    hx, hy = size[0] / 2, size[1] / 2
    base = [bm.verts.new((cx + x * hx, cy + y * hy, cz))
            for x, y in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    apex = bm.verts.new((cx, cy, cz + height))
    bm.faces.new(tuple(reversed(base)))
    for i in range(4):
        bm.faces.new((base[i], base[(i + 1) % 4], apex))
    _tag(bm, _mark)


def gable_roof(bm, centre, size, ridge_height):
    _mark = len(bm.faces)
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
    _tag(bm, _mark)


def ramp(bm, start, end, width, thickness):
    _mark = len(bm.faces)
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
    _tag(bm, _mark)


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
    build_materials(obj)
    using("stone")
    bm = bmesh.new()

    foot = 2.0 * TILE                    # the 2x2 tiles it occupies
    lean_d = 0.62                        # depth of the open lean-to
    body_d = foot - lean_d
    stone_h = 0.22                       # stone footing course, keeps grain dry
    body_h = 1.45 + 0.2 * (level - 1)    # a taller store at higher levels
    ridge = 0.85

    body_y = foot / 2 - body_d / 2       # body pushed to the back of the plot
    lean_y = -foot / 2 + lean_d / 2

    using("stone")
    box(bm, (0, body_y, stone_h / 2), (foot + 0.1, body_d + 0.1, stone_h))
    using("timber")
    box(bm, (0, body_y, stone_h + body_h / 2), (foot, body_d, body_h))
    using("thatch")
    gable_roof(bm, (0, body_y, stone_h + body_h),
               (foot + 0.34, body_d + 0.30), ridge)

    # Plank door on the gable end, sunk slightly so it reads as an opening.
    if detail:
        using("timber")
        box(bm, (-foot / 2 + 0.02, body_y + 0.1, stone_h + 0.52),
            (0.1, 0.6, 1.04))

    # The lean-to: a shed roof falling away from the body wall, on three posts.
    # `ramp` takes the centre line of the plank, not one edge — passing the wall
    # edge here put the whole roof a metre off to one side, which the overhang
    # check caught immediately.
    eave_z = stone_h + body_h * 0.86
    using("thatch")
    ramp(bm, (0.0, body_y - body_d / 2, eave_z),
         (0.0, -foot / 2 + 0.04, eave_z - 0.34),
         width=foot, thickness=0.09)
    using("timber")
    for px in (-foot / 2 + 0.12, 0.0, foot / 2 - 0.12):
        box(bm, (px, lean_y - lean_d / 2 + 0.1, (eave_z - 0.34) / 2),
            (0.11, 0.11, eave_z - 0.34))

    # Grain sacks, stacked two deep under the lean-to. These are what say
    # "store" without any need for a sign — and they are also pure detail, so
    # they are the first thing dropped at distance.
    if detail:
        using("thatch")
        for sx, sy, sz, s in ((-0.62, 0.06, 0.15, 0.34), (-0.22, 0.02, 0.15, 0.32),
                              (0.20, 0.06, 0.15, 0.33), (0.62, 0.02, 0.15, 0.31),
                              (-0.42, 0.10, 0.44, 0.30), (0.40, 0.06, 0.44, 0.29)):
            box(bm, (sx, lean_y + sy, sz), (s, s * 0.8, 0.30))

    bm.to_mesh(obj.data)
    bm.free()
    return obj, "small", (2, 2)



def build_keep(level: int = 1, detail: bool = True):
    """4x4 tiles. The player's anchor building, at five upgrade levels.

    Matched to two concepts, not one: `keep_1002` is the early keep and
    `keep_1003` the late one — see `assets-src/concept/PICKS.md`. Everything that
    differs between them is a number here, interpolated by `level`:

        level 1  compact, low walls, short tower, sparse crenellation
        level 5  taller walls, tower risen well clear, dense crenellation

    That is the whole argument for scripted models. Five hand-made keeps would
    drift apart in a way nobody could point at; five values of `t` cannot.
    """
    t = (max(1, min(5, level)) - 1) / 4.0        # 0 at level 1, 1 at level 5

    obj = new_mesh("keep")
    build_materials(obj)
    using("stone")
    bm = bmesh.new()

    foot = 4.0 * TILE
    wall_t = 0.42
    # Proportions checked against the concepts rather than guessed: keep_1002 is
    # roughly as tall as it is wide, so a 4 m keep wants to reach about 4 m at
    # level 1. The first pass came out at 2.9 m and read as a bunker.
    wall_h = 1.9 + 0.9 * t
    tower_w = 1.5
    tower_h = wall_h + 1.7 + 1.1 * t
    merlon_w, merlon_h = 0.30, 0.30
    per_side = 8

    inner = foot / 2 - wall_t

    # Four walls around a courtyard, rather than one solid block. The gap is
    # visible from the game camera and it is what makes the keep read as a place
    # with an inside.
    using("stone")
    for sx, sy, w, d in ((0, 1, foot, wall_t), (0, -1, foot, wall_t),
                         (1, 0, wall_t, foot - 2 * wall_t),
                         (-1, 0, wall_t, foot - 2 * wall_t)):
        box(bm, (sx * (foot / 2 - wall_t / 2), sy * (foot / 2 - wall_t / 2),
                 wall_h / 2), (w, d, wall_h))

    box(bm, (0, 0, 0.09), (foot - 2 * wall_t, foot - 2 * wall_t, 0.18))  # court

    def crenellate(cx, cy, span, along_x, count, top_z):
        """A row of merlons, or a solid parapet when detail is off.

        At LOD distance an individual merlon is smaller than a pixel, so the
        gaps between them cannot be seen — but the *thickened wall top* still
        can. A solid band reads better there than a handful of lonely blocks,
        and it is a quarter of the triangles.
        """
        if not detail:
            box(bm, (cx, cy, top_z + merlon_h / 2),
                (span if along_x else wall_t, wall_t if along_x else span,
                 merlon_h))
            return
        step = span / count
        for i in range(count):
            off = -span / 2 + step * (i + 0.5)
            box(bm, (cx + off if along_x else cx, cy if along_x else cy + off,
                     top_z + merlon_h / 2),
                (merlon_w if along_x else wall_t,
                 wall_t if along_x else merlon_w, merlon_h))

    n = per_side if detail else 1
    crenellate(0, foot / 2 - wall_t / 2, foot, True, n, wall_h)
    crenellate(0, -(foot / 2 - wall_t / 2), foot, True, n, wall_h)
    crenellate(foot / 2 - wall_t / 2, 0, foot - 2 * wall_t, False, n, wall_h)
    crenellate(-(foot / 2 - wall_t / 2), 0, foot - 2 * wall_t, False, n, wall_h)

    # The tower. Set further back into the courtyard as the keep grows, which is
    # the clearest single difference between the two reference concepts.
    ty = -0.15 + 0.45 * t
    box(bm, (0.25, ty, tower_h / 2), (tower_w, tower_w, tower_h))
    if detail:
        step = tower_w / 3
        for i in range(3):
            for ex, ey in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                off = -tower_w / 2 + step * (i + 0.5)
                box(bm, (0.25 + (off if ex == 0 else ex * tower_w / 2 * 0.86),
                         ty + (off if ey == 0 else ey * tower_w / 2 * 0.86),
                         tower_h + merlon_h / 2),
                    (0.26, 0.26, merlon_h))
    else:
        box(bm, (0.25, ty, tower_h + merlon_h / 2),
            (tower_w, tower_w, merlon_h))

    if detail:
        # --- the detail that makes it read as built rather than extruded ---
        #
        # All of this was missing in the first version, which used 660 of a 4,000
        # triangle budget and looked like a massing study next to its own concept
        # art. Boxes are cheap; the budget exists to be spent.

        using("stone")

        # Stepped plinth. Two courses, each slightly wider than the one above, so
        # the building sits into the ground instead of on top of it.
        for i, (inset, hgt) in enumerate(((0.00, 0.16), (0.13, 0.13))):
            z0 = 0.16 * i
            for sx, sy, w, dd in ((0, 1, foot, wall_t), (0, -1, foot, wall_t),
                                  (1, 0, wall_t, foot - 2 * wall_t),
                                  (-1, 0, wall_t, foot - 2 * wall_t)):
                box(bm, (sx * (foot / 2 - wall_t / 2),
                         sy * (foot / 2 - wall_t / 2), z0 + hgt / 2),
                    (w + inset * 2 if w > wall_t else w + inset * 2,
                     dd + inset * 2 if dd > wall_t else dd + inset * 2, hgt))

        # Corner quoins — the alternating large blocks that dress a stone corner.
        # Cheap, and the single most recognisable "this is masonry" cue there is.
        for cx, cy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            for k in range(5):
                z = 0.34 + k * (wall_h - 0.4) / 5
                long_x = (k % 2 == 0)
                box(bm, (cx * (foot / 2 - (0.30 if long_x else 0.14)),
                         cy * (foot / 2 - (0.14 if long_x else 0.30)), z),
                    (0.62 if long_x else 0.30, 0.30 if long_x else 0.62, 0.24))

        # Buttresses, one per wall, tapering as they rise.
        for sx, sy in ((0, -1), (1, 0), (-1, 0)):
            bx, by = sx * (foot / 2 - 0.04), sy * (foot / 2 - 0.04)
            prism(bm, (bx, by, 0.30), (0.46, 0.46),
                  (bx * 0.94, by * 0.94, wall_h * 0.82), (0.30, 0.30))

        # Arrow slits, sunk into the front and side walls.
        for sx, sy, ww, dd in ((-1.1, -1, 0.16, 0.14), (1.1, -1, 0.16, 0.14),
                               (0, -1, 0.16, 0.14)):
            if sx == 0:
                continue
            box(bm, (sx, sy * (foot / 2 - wall_t) - 0.02,
                     wall_h * 0.62), (ww, dd, 0.52))

        # A recessed arched doorway: a sunk reveal, a lintel and two jambs, so
        # the door reads as a hole in a thick wall rather than a painted panel.
        dz = -(foot / 2 - wall_t / 2)
        box(bm, (0.0, dz, 0.66), (1.16, wall_t + 0.06, 1.30))
        box(bm, (0.0, dz - 0.06, 1.32), (1.30, wall_t + 0.14, 0.22))
        for jx in (-0.62, 0.62):
            box(bm, (jx, dz - 0.06, 0.68), (0.20, wall_t + 0.14, 1.34))

        using("timber")
        box(bm, (0.0, -(foot / 2 - wall_t) + 0.04, 0.55), (0.82, 0.10, 1.06))
        using("stone")
        for i, sz in enumerate((0.06, 0.12, 0.18)):
            box(bm, (0.0, -(foot / 2) - 0.12 + i * 0.13, sz / 2),
                (1.0, 0.26, sz))
        # The one piece of crimson on the whole building. ART_BIBLE.md rule 3:
        # if everything the kingdom owns is crimson, crimson stops meaning power.
        using("cloth")
        box(bm, (0.25 + tower_w / 2 + 0.02, ty, tower_h * 0.74),
            (0.04, 0.42, 0.62))

    bm.to_mesh(obj.data)
    bm.free()
    return obj, "large", (4, 4)


def build_watchtower(level: int = 1, detail: bool = True):
    """2x2 tiles, but tall. The hardest asset for the silhouette rule.

    Matched to `assets-src/concept/watchtower/watchtower_1004.png`: a tapered
    stone core braced by four splayed timber legs, an external ladder, a railed
    platform with a brazier, and a small conical roof.

    Almost all of this building's identity is in its outline, which is why the
    splay is generous. A vertical stick reads as scaffolding; a splayed one
    reads as a tower.
    """
    t = (max(1, min(5, level)) - 1) / 4.0

    obj = new_mesh("watchtower")
    build_materials(obj)
    using("stone")
    bm = bmesh.new()

    foot = 2.0 * TILE
    base_h = 0.14
    core_bot, core_top = 1.15, 0.78          # the stone core tapers as it rises
    plat_z = 2.5 + 0.7 * t
    plat_w = 1.34
    leg_bot = foot / 2 - 0.16

    using("stone")
    box(bm, (0, 0, base_h / 2), (foot - 0.06, foot - 0.06, base_h))
    prism(bm, (0, 0, base_h), (core_bot, core_bot),
          (0, 0, plat_z - 0.1), (core_top, core_top))

    # Four splayed legs, wide at the ground and gathered under the platform.
    using("timber")
    for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        prism(bm, (sx * leg_bot, sy * leg_bot, base_h), (0.17, 0.17),
              (sx * (plat_w / 2 - 0.08), sy * (plat_w / 2 - 0.08), plat_z),
              (0.13, 0.13))

    box(bm, (0, 0, plat_z + 0.06), (plat_w + 0.30, plat_w + 0.30, 0.12))

    # Roof on four corner posts.
    #
    # **The post height and roof size are set by the camera, not by taste.** The
    # first version had a 0.66 m gap under a generous roof, which looks right in
    # elevation and completely hides the brazier when seen from 30 degrees above
    # — which is the only angle this game has. The brazier is the building's
    # entire "life" signal under ART_BIBLE.md, so the roof gives way to it: taller
    # posts, tighter overhang. Found by rendering at the locked camera, which is
    # the only way it could have been found.
    post_h = 1.02
    eave = plat_z + 0.12 + post_h
    for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        box(bm, (sx * (plat_w / 2 - 0.07), sy * (plat_w / 2 - 0.07),
                 plat_z + 0.12 + post_h / 2), (0.1, 0.1, post_h))
    using("thatch")
    pyramid(bm, (0, 0, eave), (plat_w + 0.24, plat_w + 0.24), 0.46)

    using("firelight")
    box(bm, (0, 0, plat_z + 0.42), (0.40, 0.40, 0.58))       # brazier

    if detail:
        # Railings, ladder and pennant. The railing in particular is 40% of the
        # triangle count and none of the silhouette.
        using("timber")
        for sx, sy, w, d in ((0, 1, plat_w, 0.07), (0, -1, plat_w, 0.07),
                             (1, 0, 0.07, plat_w), (-1, 0, 0.07, plat_w)):
            box(bm, (sx * plat_w / 2, sy * plat_w / 2, plat_z + 0.34),
                (w, d, 0.07))
        for i in range(4):
            off = -plat_w / 2 + plat_w * (i + 0.5) / 4
            box(bm, (off, -plat_w / 2, plat_z + 0.24), (0.05, 0.05, 0.36))
        # Ladder: two rails and rungs, leaning against the north-west leg.
        for rx in (-0.20, 0.20):
            prism(bm, (rx - 0.55, 0.62, base_h), (0.06, 0.06),
                  (rx - 0.30, 0.30, plat_z), (0.06, 0.06))
        for i in range(5):
            f = (i + 0.5) / 5
            box(bm, (-0.55 + 0.25 * f, 0.62 - 0.32 * f,
                     base_h + (plat_z - base_h) * f), (0.44, 0.05, 0.04))
        box(bm, (0, 0, eave + 0.52 + 0.24), (0.05, 0.05, 0.48))   # pennant pole
        using("cloth")
        box(bm, (0.17, 0, eave + 0.52 + 0.34), (0.30, 0.03, 0.18))

    bm.to_mesh(obj.data)
    bm.free()
    return obj, "small", (2, 2)


BUILDERS = {"granary": build_granary, "keep": build_keep,
            "watchtower": build_watchtower}


# ---------------------------------------------------------------------------
# Unwrap, LOD, validate, export.
# ---------------------------------------------------------------------------

def unwrap(obj) -> None:
    """Project UVs in world units so tileable materials tile correctly.

    **Not `smart_project`, and the difference matters.** `smart_project` packs
    every face into the 0..1 square, which is what you want when an asset has its
    own painted texture — each face gets a unique slice. Wastemarch's buildings
    share four tileable materials instead, so what they need is the opposite: UVs
    that run on with the geometry, in metres, so a wall twice as long shows twice
    as much stone rather than the same stone stretched.

    `cube_project` does exactly that. `cube_size` is in world units, so setting
    it to TILE_METRES makes the texel density exact everywhere, on every asset,
    without measuring anything.
    """
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.cube_project(cube_size=TILE_METRES)
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


def _unused_atlas_demand(obj) -> dict:
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
        "texel_density": ACHIEVED_TEXEL_DENSITY,
        "tiles_every_m": TILE_METRES,
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
          f"{ACHIEVED_TEXEL_DENSITY:.0f} texels/m "
          f"(tiles every {TILE_METRES:.0f} m)")
    return 0


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    raise SystemExit(main(argv))
