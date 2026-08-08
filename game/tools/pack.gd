extends SceneTree

## Packs buildings shoulder to shoulder and photographs the result.
##
##   $GODOT --path game --resolution 1920x1080 \
##       --script res://tools/pack.gd -- packed.png
##
## The case that keeps producing complaints is a *dense* base, and placing ten
## buildings by hand to check a proportion change is slow enough that it does not
## get done. This does it in one command.
##
## What to look for: buildings standing on distinct tiles should not appear to
## pass through one another. Some occlusion is unavoidable — at 30 degrees a
## building of height h hides about 1.7 x h tiles behind it, and every isometric
## game has this — but a building should not look like it was placed *inside* its
## neighbour.
var _c: Node = null
var _f := 0
func _initialize() -> void:
	_c = load("res://city/City.tscn").instantiate()
	root.add_child(_c)
func _process(_d: float) -> bool:
	_f += 1
	if _f == 2:
		_c._resources = {"grain": 9999, "timber": 9999, "stone": 9999, "iron": 0}
		for cell in [Vector2i(-9,-3), Vector2i(-6,-3), Vector2i(-3,-3),
					 Vector2i(-9,0), Vector2i(-6,0)]:
			_c._place(cell, "watchtower")
		for cell in [Vector2i(0,-3), Vector2i(2,-3), Vector2i(0,-1), Vector2i(2,-1)]:
			_c._place(cell, "granary")
		_c._place(Vector2i(5,-3), "keep")
		for b in _c._built:
			b["remaining"] = -1.0
			_c._finish(b)
		var cam: Camera3D = _c.get_node("Camera3D")
		cam.size = 26.0
		get_root().set_content_scale_size(Vector2i(1920,1080))
		print("placed ", _c._built.size(), " buildings")
	if _f < 12:
		return false
	root.get_texture().get_image().save_png(OS.get_cmdline_user_args()[0])
	print("wrote")
	quit()
	return true
