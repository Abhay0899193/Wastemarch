class_name AssetPreview
extends Node3D

## Places every built model on the ground under the locked game camera.
##
## Two jobs, one scene:
##
##   1. **Looking at them.** Run it with a window and you see the buildings in
##      the real engine, real renderer, real camera — not a Blender render.
##
##          $GODOT --path game res://world/AssetPreview.tscn
##
##      Drag to pan, scroll to zoom, Home to recentre, Escape to quit. There is
##      no rotation, because the game has none: `docs/ART_BIBLE.md` locks the
##      camera at 30 degrees elevation and 45 degrees yaw, and a preview that
##      rotates would be showing angles no player will ever see.
##
##   2. **Checking the budget.** It prints triangles and draw calls, which is
##      what `MASTER_PLAN.md` stage 6 asks for. Those numbers need a real
##      graphics device, so this cannot be run with `--headless` — the counters
##      come back as zero rather than as an error, which is worse than failing.

## From docs/ART_BIBLE.md. Buildings sit on a 1 metre grid.
const TILE := 1.0
const MAX_DRAW_CALLS := 120
const MAX_TRIANGLES := 250_000

## Which models to show, and where to stand them. Grid coordinates, so the
## spacing is in tiles and matches how the game will place them.
const LAYOUT := {
	"granary_L1": Vector2i(-6, 0),
	"watchtower_L1": Vector2i(-2, 0),
	"keep_L1": Vector2i(3, 0),
}

const MODEL_DIR := "res://assets/models/"

@onready var _camera: Camera3D = $Camera3D

var _camera_home := Vector3.ZERO


func _ready() -> void:
	_camera_home = _camera.position
	_place_models()
	# Two frames, so the renderer has actually drawn something before the
	# counters are read. Reading them in _ready gives the previous frame's
	# numbers, which for the first frame is nothing at all.
	await get_tree().process_frame
	await get_tree().process_frame
	_report()


func _place_models() -> void:
	for model_name in LAYOUT:
		var path: String = MODEL_DIR + model_name + ".glb"
		if not ResourceLoader.exists(path):
			push_warning("No model at %s — run tools/blender/build_asset.py" % path)
			continue
		var scene: PackedScene = load(path)
		var node: Node3D = scene.instantiate()
		var cell: Vector2i = LAYOUT[model_name]
		node.position = Vector3(cell.x * TILE, 0.0, cell.y * TILE)
		add_child(node)
		print("  placed %s at %s" % [model_name, cell])


func _report() -> void:
	var tris: int = RenderingServer.get_rendering_info(
		RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME)
	var draws: int = RenderingServer.get_rendering_info(
		RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME)

	print("\n=== scene budget (docs/ART_BIBLE.md) ===")
	print("  triangles   %8d / %d" % [tris, MAX_TRIANGLES])
	print("  draw calls  %8d / %d" % [draws, MAX_DRAW_CALLS])

	if tris == 0 and draws == 0:
		print("  both zero — this was almost certainly run with --headless,")
		print("  which has no graphics device to count. Run it with a window.")
		return

	var over: Array[String] = []
	if tris > MAX_TRIANGLES:
		over.append("triangles")
	if draws > MAX_DRAW_CALLS:
		over.append("draw calls")
	if over.is_empty():
		print("  OK — within budget")
	else:
		printerr("  OVER BUDGET: %s" % ", ".join(over))


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
			# Pan across the ground, not across the screen: move along the
			# camera's own right and flattened forward axes, so dragging feels
			# attached to the world rather than to the viewport.
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
