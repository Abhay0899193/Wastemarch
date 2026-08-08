"""Stage 3, properly: bake a real UV texture, with ambient occlusion.

    $BLENDER --background --factory-startup --python tools/blender/bake_asset.py -- --asset keep

**Buildings are textured from the five tiled palette materials**, then baked into
a real unwrap with ambient occlusion and emission. That is the default and the
path; `--from-concept` bakes a projected concept image instead and is kept only
because the machinery works and its findings are recorded.

**Why not the concept art.** Projecting concept art on gave a livelier surface and
cost more than it was worth: it only holds from one camera angle, needed an inset
hack to stop pale slivers at the silhouette, produced a different look per
building depending on how well each concept happened to fit its model, and left
the 3D barely earning its keep. The owner chose consistency — every building
made of the same five materials, the way the watchtower already was — over
per-asset fidelity to a painting. `assets-src/concept/` is now reference for
*modelling*, which is what concept art is normally for.

The three things that survived from that work and are keeping their value:
ambient occlusion, baked emission, and the real UV unwrap.

This does it the way `MASTER_PLAN.md` section 7.3 always specified:

    1. unwrap the model properly, every face with its own patch of texture
    2. project the concept art on as before — but only as a *source*
    3. **bake** that into the real unwrap, so every face owns its pixels
    4. bake ambient occlusion and multiply it in
    5. throw the camera projection away

What that buys, concretely: every face is correct from any angle, so shadows and
future camera work do not break; there are no silhouette slivers because nothing
is sampling a shared image at a shared edge; and ambient occlusion — the largest
remaining difference from the concept art — has somewhere to live.

Ambient occlusion is the darkening in corners, under eaves and where a wall meets
the ground. Godot's mobile renderer cannot compute it at run time, so it has to
be baked into the texture here or it does not exist at all.
"""

import argparse
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_asset as ba  # noqa: E402
import project_concept as pc  # noqa: E402

REPO = Path(__file__).resolve().parent.parent.parent
OUT_DIR = REPO / "assets-src" / "model"
TEX_DIR = REPO / "assets-src" / "baked"

# 2048, not 1024. One texture is stretched over a whole building, so it holds far
# less resolution per face than a 1024 concept image that spent all of itself on
# the three visible sides. At 1024 the buildings came out visibly blurry beside
# their own concepts. 2048 costs 4x the texture memory and is still one texture.
BAKE_PX = 2048
AO_SAMPLES = 24          # plenty for soft contact shadows on box geometry
AO_STRENGTH = 0.85       # 1.0 is very dark in corners; this keeps it readable
MARGIN_PX = 16           # bleed past each UV island, so seams do not show


def unwrap_for_baking(obj) -> None:
    """A real unwrap: every face gets its own place in the 0..1 square.

    `smart_project` rather than `cube_project` here — the tiled-material path
    wants UVs that run on in metres, but a baked texture wants every face packed
    once with no overlap, which is the opposite requirement.
    """
    uv = obj.data.uv_layers.new(name="baked")
    obj.data.uv_layers.active = uv
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=1.15, island_margin=0.02)
    bpy.ops.object.mode_set(mode="OBJECT")


def new_image(name: str, colour) -> bpy.types.Image:
    img = bpy.data.images.new(name, BAKE_PX, BAKE_PX, float_buffer=True)
    img.generated_color = colour
    return img


def add_bake_target(mat, img, uv_name: str):
    """Point a material's bake at an image, using a named UV layer.

    Blender bakes into whichever Image Texture node is *selected and active*, a
    piece of hidden state that has no equivalent in the Python API — the node
    has to be made active explicitly or the bake goes somewhere unexpected.
    """
    nt = mat.node_tree
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    uvmap = nt.nodes.new("ShaderNodeUVMap")
    uvmap.uv_map = uv_name
    nt.links.new(uvmap.outputs["UV"], tex.inputs["Vector"])
    for n in nt.nodes:
        n.select = False
    tex.select = True
    nt.nodes.active = tex
    return tex


def bake(kind: str) -> None:
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = AO_SAMPLES if kind == "AO" else 1
    scene.cycles.use_denoising = False
    scene.render.bake.margin = MARGIN_PX
    scene.render.bake.use_selected_to_active = False
    if kind == "DIFFUSE":
        # Colour only. Without this the bake includes lighting, and the texture
        # arrives with a sun baked into it that then gets lit again in the game.
        scene.render.bake.use_pass_direct = False
        scene.render.bake.use_pass_indirect = False
        scene.render.bake.use_pass_color = True
    bpy.ops.object.bake(type=kind)


def multiply_into(albedo, ao, strength: float) -> None:
    """Darken the albedo by the occlusion, in place."""
    import numpy as np
    n = BAKE_PX * BAKE_PX * 4
    a = np.empty(n, dtype=np.float32)
    o = np.empty(n, dtype=np.float32)
    albedo.pixels.foreach_get(a)
    ao.pixels.foreach_get(o)
    a = a.reshape(-1, 4)
    o = o.reshape(-1, 4)
    shade = 1.0 - (1.0 - o[:, 0:1]) * strength
    a[:, :3] *= shade
    a[:, 3] = 1.0
    albedo.pixels.foreach_set(a.reshape(-1))
    albedo.update()


def _has_any_light(img) -> bool:
    """Whether an emission bake found anything at all."""
    import numpy as np
    a = np.empty(BAKE_PX * BAKE_PX * 4, dtype=np.float32)
    img.pixels.foreach_get(a)
    return bool(a.reshape(-1, 4)[:, :3].max() > 0.02)


def save(img, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img.filepath_raw = str(path)
    img.file_format = "PNG"
    img.save()      # colourspace untouched — see .agent/MEMORY.md


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--asset", required=True)
    ap.add_argument("--level", type=int, default=1)
    ap.add_argument("--source", help="image to bake from; defaults to the pick")
    ap.add_argument("--from-concept", action="store_true",
                    help="bake a projected concept image instead of the tiled "
                         "palette materials. Kept because the machinery works "
                         "and the findings are recorded, but it is not the "
                         "path — see the module docstring.")
    ap.add_argument("--ao-strength", type=float, default=AO_STRENGTH)
    args = ap.parse_args(argv)

    if args.asset not in ba.BUILDERS:
        raise SystemExit(f"No builder for '{args.asset}'")

    bpy.ops.wm.read_factory_settings(use_empty=True)
    obj, size_class, footprint = ba.BUILDERS[args.asset](args.level)
    unwrap_for_baking(obj)

    if not args.from_concept:
        # The builder already attached the five tiled palette materials. Bake
        # those, so an open structure still gets ambient occlusion — which is
        # the part it was missing, not the colour.
        print(f"baking {args.asset} from its tiled materials")
        for m in obj.data.materials:
            if m:
                m.use_backface_culling = True
        mats = [m for m in obj.data.materials if m]
        for m in mats:
            add_bake_target(m, new_image("scratch", (0, 0, 0, 1)), "baked")
    else:
        src = Path(args.source) if args.source else pc.picked_concept(args.asset)
        if not src.is_absolute():
            src = (REPO / src).resolve()
        print(f"baking {args.asset} from {src.name}")

        proj = obj.data.uv_layers.new(name="projected")
        obj.data.uv_layers.active = proj

        obj.data.materials.clear()
        for poly in obj.data.polygons:
            poly.material_index = 0

        mat = bpy.data.materials.new("bake_source")
        mat.use_nodes = True
        mat.use_backface_culling = True
        bsdf = mat.node_tree.nodes["Principled BSDF"]
        bsdf.inputs["Roughness"].default_value = 0.9
        bsdf.inputs["Metallic"].default_value = 0.0
        obj.data.materials.append(mat)

        img = bpy.data.images.load(str(src), check_existing=False)
        cam = pc.game_camera(obj)
        model_box = pc.project_uvs(obj, cam)
        cbox = pc.concept_bounds(img)
        pc.dilate_into_background(img)
        pc.fit_uvs(obj, model_box, cbox)

        nt = mat.node_tree
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = img
        uvmap = nt.nodes.new("ShaderNodeUVMap")
        uvmap.uv_map = "projected"
        nt.links.new(uvmap.outputs["UV"], tex.inputs["Vector"])
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
        mats = [mat]

    # --- 2. bake into the real unwrap ----------------------------------------
    albedo = new_image(f"{args.asset}_albedo", (0.5, 0.5, 0.5, 1.0))
    for m in mats:
        add_bake_target(m, albedo, "baked")
    obj.data.uv_layers.active = obj.data.uv_layers["baked"]
    bake("DIFFUSE")
    print("  baked albedo into the unwrap")

    # --- 3. ambient occlusion, into the same unwrap --------------------------
    ao = new_image(f"{args.asset}_ao", (1.0, 1.0, 1.0, 1.0))
    for m in mats:
        add_bake_target(m, ao, "baked")
    bake("AO")
    print(f"  baked ambient occlusion, {AO_SAMPLES} samples")

    # --- 3b. emission, which the albedo bake throws away ---------------------
    #
    # Baking DIFFUSE colour drops emission entirely, so the watchtower's brazier
    # and the keep's lit doorway came out flat. glTF carries an emissive texture
    # natively, so this bakes one and wires it up.
    emit = new_image(f"{args.asset}_emit", (0.0, 0.0, 0.0, 1.0))
    for m in mats:
        add_bake_target(m, emit, "baked")
    bake("EMIT")
    emit_path = TEX_DIR / f"{args.asset}_L{args.level}_emit.png"
    has_emit = _has_any_light(emit)
    if has_emit:
        save(emit, emit_path)
        print(f"  baked emission -> {emit_path.name}")
    else:
        print("  no emissive surfaces on this asset")

    multiply_into(albedo, ao, args.ao_strength)
    tex_path = TEX_DIR / f"{args.asset}_L{args.level}_albedo.png"
    save(albedo, tex_path)
    print(f"  wrote {tex_path.relative_to(REPO)}")

    # --- 4. a clean material using only the baked texture --------------------
    obj.data.materials.clear()
    final = bpy.data.materials.new("baked")
    final.use_nodes = True
    final.use_backface_culling = True
    fb = final.node_tree.nodes["Principled BSDF"]
    fb.inputs["Roughness"].default_value = 0.9
    fb.inputs["Metallic"].default_value = 0.0
    saved = bpy.data.images.load(str(tex_path), check_existing=False)
    ftex = final.node_tree.nodes.new("ShaderNodeTexImage")
    ftex.image = saved
    final.node_tree.links.new(ftex.outputs["Color"], fb.inputs["Base Color"])

    if has_emit:
        eimg = bpy.data.images.load(str(emit_path), check_existing=False)
        etex = final.node_tree.nodes.new("ShaderNodeTexImage")
        etex.image = eimg
        final.node_tree.links.new(etex.outputs["Color"],
                                  fb.inputs["Emission Color"])
        fb.inputs["Emission Strength"].default_value = 1.0
    obj.data.materials.append(final)

    # The camera-space UVs have done their job and must not ship: glTF would
    # export them as a second UV set and something downstream would use them.
    if "projected" in obj.data.uv_layers:
        obj.data.uv_layers.remove(obj.data.uv_layers["projected"])
    obj.data.uv_layers.active = obj.data.uv_layers["baked"]

    report = ba.validate(obj, size_class, footprint)
    out = OUT_DIR / f"{args.asset}_L{args.level}.glb"
    ba.export([obj], out)
    print(f"\nOK — {report['triangles']} triangles, one baked {BAKE_PX}px "
          f"texture with AO, {out.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    raise SystemExit(main(argv))
