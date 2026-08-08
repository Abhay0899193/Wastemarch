extends SceneTree

## Places every building and reports any frame that stalls.
##
##   $GODOT --path game --resolution 1920x1080 --script res://tools/prof.gd -- shot.png
##
## Written the day the owner reported "it takes ten seconds to render" after
## placing a building. It did not: the worst frame was 138 ms, and what actually
## took ten seconds was the build timer, with the model flat-tinted the whole
## time so it looked like a texture that had failed to load. But the same run
## found a real 1,376 ms stall on first placement — the models are 5 to 10 MB of
## glTF that nothing had touched until the click — which `_preload_models` now
## moves to startup.
##
## **Keep this.** A stall is invisible in a headless test and easy to argue about
## from memory; this settles it in one command.
const STALL_MS := 40

var _c: Node = null
var _f := 0
var _t := 0

func _initialize() -> void:
	_c = load("res://city/City.tscn").instantiate()
	root.add_child(_c)
	# Resources are set in _process, not here. `add_child` in `_initialize` does
	# NOT run `_ready` before `_initialize` returns, so anything set here is
	# overwritten by `_load_definitions` a frame later. See .agent/MEMORY.md.

func _process(_d: float) -> bool:
	_f += 1
	var t := Time.get_ticks_msec()
	if _f > 2 and t - _t > STALL_MS:
		print("frame ", _f, " STALL ", t - _t, " ms")
	_t = t
	if _f == 5:
		_c._resources = {"grain": 99999, "timber": 99999, "stone": 99999, "iron": 99999}
	if _f == 6:
		# Top-left corners, spaced for the largest footprint in each row.
		var cells := [Vector2i(-8, -8), Vector2i(-3, -8), Vector2i(0, -8),
					  Vector2i(-8, -3), Vector2i(-4, -3), Vector2i(0, -3)]
		var i := 0
		for id in _c._order:
			if not _c._place(cells[i], id):
				print("  REFUSED ", id, " at ", cells[i],
					  " afford=", _c._can_afford(id),
					  " canplace=", _c._can_place(cells[i], id))
			i += 1
		print("placed ", _c._built.size(), " of ", _c._order.size())
	if _f == 10:
		(_c.get_node("Camera3D") as Camera3D).size = 20.0
		get_root().set_content_scale_size(Vector2i(1920, 1080))
	if _f == 12:
		# Finish everything, then upgrade three of them to different levels, so
		# the shot shows whether an upgrade is visible at all.
		for b in _c._built:
			b["remaining"] = -1.0
			_c._finish(b)
		for i in range(_c._built.size()):
			for _n in range(i):
				_c._upgrade(_c._built[i])
				_c._built[i]["remaining"] = -1.0
				_c._finish(_c._built[i])
		_c._choose(Vector2i(-8, -8))
	if _f == 16 and OS.get_cmdline_user_args().size() > 0:
		get_root().get_texture().get_image().save_png(OS.get_cmdline_user_args()[0])
		print("wrote")
	return _f > 17
