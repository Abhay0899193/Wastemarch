extends SceneTree

## Renders a scene for a few frames and writes a PNG. Used to eyeball the locked
## game camera without opening the editor.
##
## Requires a real rendering device, so do NOT pass --headless:
##   $GODOT --path game --script res://tools/capture.gd -- res://world/WorldRoot.tscn out.png
##
## Phase 2 grows this into tools/validate_assets.gd, which also checks draw calls
## and triangle counts against the budgets in docs/ART_BIBLE.md.

const WARMUP_FRAMES := 5

var _frames := 0
var _scene_path := "res://world/WorldRoot.tscn"
var _out_path := "capture.png"


func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() > 0:
		_scene_path = args[0]
	if args.size() > 1:
		_out_path = args[1]

	var packed: PackedScene = load(_scene_path)
	if packed == null:
		push_error("capture: could not load %s" % _scene_path)
		quit(1)
		return
	root.add_child(packed.instantiate())


func _process(_delta: float) -> bool:
	# Shadows and the environment need a few frames to settle before the capture.
	_frames += 1
	if _frames < WARMUP_FRAMES:
		return false

	var image: Image = root.get_texture().get_image()
	if image == null:
		push_error("capture: no viewport texture. Running with --headless?")
		quit(1)
		return true

	var err := image.save_png(_out_path)
	if err != OK:
		push_error("capture: save_png failed (%d) for %s" % [err, _out_path])
		quit(1)
		return true

	print("capture: wrote %s" % _out_path)
	quit(0)
	return true
