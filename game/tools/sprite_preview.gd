class_name SpritePreview
extends Node3D

## Concept art as sprites, standing next to the 3D models of the same buildings.
##
##   $GODOT --path game res://world/SpritePreview.tscn
##
## **This is an experiment, not a decision.** `MASTER_PLAN.md` section 1.3 argues
## at length for real 3D over pre-rendered sprites, and nothing here overturns
## that. But the models are not matching their concept art, and the fastest way
## to find out how much that costs is to stand the concept art itself in the game
## and look at the two together.
##
## Front row: sprites, cut straight out of the concept images.
## Back row: the 3D models, in the same order, at the same scale.
##
## The sprites are sized from the *models* — `tools/blender/make_sprite.py` reads
## each building's height in metres and works out how many metres tall its sprite
## must be drawn. So this is a fair comparison: same building, same size, same
## ground, same light.

const TILE := 1.0
const SPRITE_DIR := "res://assets/sprites/"
const MODEL_DIR := "res://assets/models/"

## asset -> where the sprite stands, and where its model stands behind it.
const LAYOUT := {
	"granary": Vector2(-6.0, 2.5),
	"watchtower": Vector2(-1.5, 2.5),
	"keep": Vector2(4.0, 2.5),
}
const MODEL_ROW_OFFSET := -7.0

@onready var _camera: Camera3D = $Camera3D

var _camera_home := Vector3.ZERO


func _ready() -> void:
	_camera_home = _camera.position
	for asset in LAYOUT:
		_place_sprite(asset, LAYOUT[asset])
		_place_model(asset, LAYOUT[asset] + Vector2(0.0, MODEL_ROW_OFFSET))
	await get_tree().process_frame
	await get_tree().process_frame
	_report()


func _place_sprite(asset: String, cell: Vector2) -> void:
	var tex_path: String = SPRITE_DIR + asset + "_L1.png"
	var meta_path: String = SPRITE_DIR + asset + "_L1.json"
	if not ResourceLoader.exists(tex_path):
		push_warning("no sprite for %s — run tools/blender/make_sprite.py" % asset)
		return

	var meta: Dictionary = JSON.parse_string(
		FileAccess.get_file_as_string(meta_path))
	var height_m: float = meta.get("height_m", 2.0)
	var width_m: float = meta.get("width_m", 2.0)

	var sprite := Sprite3D.new()
	sprite.texture = load(tex_path)
	sprite.pixel_size = height_m / float(meta["pixels"][1])
	sprite.centered = false
	sprite.offset = Vector2(-meta["pixels"][0] / 2.0, 0.0)

	# The camera never rotates, so the sprite does not need to track it — it just
	# has to face the one direction the camera looks from. Billboarding would be
	# wrong here: it would make the building swing as the player pans.
	sprite.billboard = BaseMaterial3D.BILLBOARD_DISABLED
	sprite.rotation_degrees = Vector3(0.0, 45.0, 0.0)

	# Alpha scissor rather than blending: the cutout is hard-edged, and blended
	# transparency does not write depth, so troops would draw through it.
	sprite.alpha_cut = SpriteBase3D.ALPHA_CUT_DISCARD
	sprite.alpha_scissor_threshold = 0.55

	# A flat quad casts a flat quad's shadow, which lands on the ground as a pale
	# parallelogram behind every building and immediately gives the trick away.
	# Sprites in this genre get a painted or projected shadow instead.
	sprite.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	sprite.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	sprite.shaded = false            # the art already has its light painted in

	var holder := Node3D.new()
	holder.position = Vector3(cell.x * TILE, 0.0, cell.y * TILE)
	holder.add_child(sprite)
	add_child(holder)
	print("  sprite %-12s %.2f x %.2f m" % [asset, width_m, height_m])


func _place_model(asset: String, cell: Vector2) -> void:
	var path: String = MODEL_DIR + asset + "_L1.glb"
	if not ResourceLoader.exists(path):
		return
	var node: Node3D = (load(path) as PackedScene).instantiate()
	node.position = Vector3(cell.x * TILE, 0.0, cell.y * TILE)
	add_child(node)


func _report() -> void:
	var tris: int = RenderingServer.get_rendering_info(
		RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME)
	var draws: int = RenderingServer.get_rendering_info(
		RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME)
	print("\n  triangles %d, draw calls %d  (sprites + models together)"
			% [tris, draws])


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		var mb: InputEventMouseButton = event
		if mb.button_index == MOUSE_BUTTON_WHEEL_UP:
			_camera.size = maxf(2.0, _camera.size * 0.9)
		elif mb.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			_camera.size = minf(80.0, _camera.size * 1.1)
	elif event is InputEventMouseMotion:
		var mm: InputEventMouseMotion = event
		if mm.button_mask & MOUSE_BUTTON_MASK_LEFT:
			var speed: float = _camera.size / 600.0
			var right: Vector3 = _camera.global_transform.basis.x
			var fwd: Vector3 = -_camera.global_transform.basis.z
			fwd.y = 0.0
			fwd = fwd.normalized()
			_camera.position -= right * mm.relative.x * speed
			_camera.position -= fwd * mm.relative.y * speed
	elif event is InputEventKey and event.is_pressed():
		var key: InputEventKey = event
		if key.keycode == KEY_ESCAPE:
			get_tree().quit()
		elif key.keycode == KEY_HOME:
			_camera.position = _camera_home
