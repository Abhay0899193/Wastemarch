extends SceneTree

## Drives the city proof of concept without a person, and checks it works.
##
##   $GODOT --headless --path game --script res://tools/city_smoke.gd
##
## Exits 0 if every check passes, 1 otherwise.
##
## **Why this exists.** The city is the first thing in the project with real
## state: resources that go down when you spend and up when you wait, tiles that
## can only hold one building, timers that finish. All of that is easy to break
## and slow to test by hand — a build timer bug takes twelve seconds to notice
## and a save bug takes a restart.
##
## It plays a short game: place a granary, refuse to place a second one on top of
## it, wait for it to finish, check it produces, save, wipe, load, and check the
## world came back the same.

const SCENE := "res://city/City.tscn"

var _failures := 0
var _city: Node = null


func _check(label: String, actual: Variant, expected: Variant) -> void:
	if actual == expected:
		print("  ok    %s = %s" % [label, actual])
	else:
		_failures += 1
		printerr("  FAIL  %s: expected %s, got %s" % [label, expected, actual])


func _ok(label: String, condition: bool) -> void:
	if condition:
		print("  ok    %s" % label)
	else:
		_failures += 1
		printerr("  FAIL  %s" % label)


## Runs the city's own `_process` for a stretch of simulated time, in the same
## sized steps the game uses. Advancing by one big delta would hide any bug that
## only shows when a timer crosses zero more than once.
func _advance(seconds: float) -> void:
	var step := 1.0 / 30.0
	var elapsed := 0.0
	while elapsed < seconds:
		_city._process(step)
		elapsed += step


## **The checks cannot run in `_initialize`.** `root.add_child()` there does not
## put the node in the tree immediately — the tree enters it when the main loop
## next iterates — so `_ready` has not run yet and every field is still empty.
## The first version of this test failed with "expected 90, got 0" for exactly
## that reason and the bug was in the test, not the city.
func _initialize() -> void:
	print("city smoke test")
	var packed: PackedScene = load(SCENE)
	if packed == null:
		printerr("  FAIL  could not load %s" % SCENE)
		quit(1)
		return
	_city = packed.instantiate()
	root.add_child(_city)


func _process(_delta: float) -> bool:
	if not _city.is_inside_tree():
		return false
	_run()
	return true


func _run() -> void:
	var res: Dictionary = _city._resources
	_check("starting timber", res.get("timber", 0), 90)

	# --- placing ------------------------------------------------------------
	var cell := Vector2i(0, 0)
	_ok("granary is placeable on empty ground", _city._can_place(cell, "granary"))
	_city._place(cell, "granary")
	_check("timber after paying 30", _city._resources["timber"], 60)
	_check("tiles occupied by a 2x2", _city._occupied.size(), 4)
	_ok("the same tile is now refused", not _city._can_place(cell, "granary"))
	_ok("an overlapping tile is refused",
			not _city._can_place(Vector2i(1, 1), "granary"))
	_ok("a clear tile is still allowed",
			_city._can_place(Vector2i(6, 6), "granary"))

	# --- the bug that shipped: placing twice without moving the mouse -------
	#
	# `_update_ghost` skips its work when the cursor has not moved to a new cell,
	# so after a placement the ghost stayed green over ground it had just taken
	# and a second click put a second building straight through the first. The
	# test missed it because it called `_place` directly and the guard was in the
	# click handler. Now the guard is in `_place`, which is what every route uses.
	var before: int = _city._built.size()
	_ok("placing on top of the last building is refused",
			not _city._place(cell, "granary"))
	_check("and nothing was built", _city._built.size(), before)
	_check("and nothing was charged", _city._resources["timber"], 60)

	# --- off the edge -------------------------------------------------------
	_ok("off the north edge is refused",
			not _city._can_place(Vector2i(0, 22), "granary"))
	_ok("straddling the edge is refused",
			not _city._can_place(Vector2i(21, 0), "granary"))
	_ok("_place refuses the edge too, not just _can_place",
			not _city._place(Vector2i(21, 0), "granary"))

	# --- affordability ------------------------------------------------------
	_city._resources["timber"] = 5
	_ok("cannot place what you cannot afford",
			not _city._can_place(Vector2i(10, 10), "granary"))
	_city._resources["timber"] = 60

	# --- time ---------------------------------------------------------------
	var grain_before: int = _city._resources["grain"]
	_advance(3.0)
	_check("nothing produced while still building",
			_city._resources["grain"], grain_before)

	_advance(4.0)                       # past the 6 second build
	_ok("the building finished", _city._built[0]["remaining"] <= 0.0)

	_advance(5.5)                       # one production interval
	_ok("it produced grain once finished",
			_city._resources["grain"] > grain_before)

	# --- saving -------------------------------------------------------------
	var grain_saved: int = _city._resources["grain"]
	_city._save()
	_city._place(Vector2i(8, 8), "granary")
	_check("two buildings before loading", _city._built.size(), 2)

	_city._load()
	_check("one building after loading", _city._built.size(), 1)
	_check("resources came back", _city._resources["grain"], grain_saved)
	_check("occupancy came back", _city._occupied.size(), 4)
	_ok("the reloaded tile is still refused",
			not _city._can_place(cell, "granary"))

	# --- upgrading ----------------------------------------------------------
	var b: Dictionary = _city._built[0]
	_check("a new building is level 1", b["level"], 1)

	var l2_cost: Dictionary = _city._cost_at("granary", 2)
	_ok("level 2 costs more than level 1",
			l2_cost["timber"] > _city._cost_at("granary", 1)["timber"])
	_ok("level 2 yields more than level 1",
			_city._yield_at("granary", 2) > _city._yield_at("granary", 1))

	_city._resources["timber"] = 0
	_ok("cannot upgrade what you cannot pay for", not _city._upgrade(b))
	_check("and the level did not move", b["level"], 1)

	_city._resources["timber"] = 9999
	_ok("upgrading works", _city._upgrade(b))
	_check("the level moved", b["level"], 2)
	_ok("and it goes back under construction", b["remaining"] > 0.0)
	_ok("upgrading again is refused while it builds", not _city._upgrade(b))

	_advance(_city._build_s_at("granary", 2) + 1.0)
	_ok("the upgrade finished", b["remaining"] <= 0.0)

	var grain_l2: int = _city._resources["grain"]
	_advance(5.5)
	_check("a level 2 granary produces its level 2 yield",
			_city._resources["grain"] - grain_l2, _city._yield_at("granary", 2))

	# A building with art at one level only still upgrades — it just does not
	# change shape. Nothing should reach for a model that was never built.
	_ok("a level 5 croft falls back to the art that exists",
			_city._model_for("croft", 5) == _city._model_for("croft", 1))
	_ok("the keep does have level 3 art",
			_city._model_for("keep", 4) != _city._model_for("keep", 1))

	# --- saving carries the level ------------------------------------------
	_city._save()
	_city._load()
	_check("the level survived a save and load", _city._built[0]["level"], 2)

	# --- migrating an old save ---------------------------------------------
	# A version 1 save, written by hand exactly as the old build wrote them:
	# no `level` anywhere.
	var old := {"version": 1, "resources": {"grain": 7, "timber": 8, "stone": 9,
											"iron": 0},
				"buildings": [{"id": "granary", "cell": [3, 3],
							   "remaining": 0.0, "tick": 5.0}]}
	var f := FileAccess.open("user://city_save.json", FileAccess.WRITE)
	f.store_string(JSON.stringify(old))
	f.close()
	_city._load()
	_check("a version 1 save still loads", _city._built.size(), 1)
	_check("and its building is level 1", _city._built[0]["level"], 1)
	_check("and its resources came through", _city._resources["grain"], 7)

	# A save from a future version is refused rather than guessed at.
	var future := {"version": 99, "resources": {}, "buildings": []}
	f = FileAccess.open("user://city_save.json", FileAccess.WRITE)
	f.store_string(JSON.stringify(future))
	f.close()
	_city._load()
	_check("a future save is refused and changes nothing",
			_city._built.size(), 1)

	# --- the camera ---------------------------------------------------------
	# **The test is the definition of correct panning:** whatever ground you
	# grabbed stays under the cursor. The old pan multiplied mouse pixels by
	# `size / 600.0` and used the same figure for both axes, which is wrong twice
	# over — 600 is nobody's window height, and the ground is foreshortened 2:1
	# vertically at a 30 degree camera. Diagonal drags slid away from the cursor.
	var cam: Camera3D = _city.get_node("Camera3D")
	var start := cam.position
	var press := Vector2(700, 380)
	_city._grab = _city._ground_at(press)
	for drag in [Vector2(240, 0), Vector2(0, 190), Vector2(-310, 260)]:
		_city.pan_to(press + drag)
		var under: Vector3 = _city._ground_at(press + drag)
		_ok("drag by %s keeps the grabbed ground under the cursor" % drag,
				under.distance_to(_city._grab) < 0.01)
	_ok("and the camera actually moved", cam.position.distance_to(start) > 1.0)

	# Zoom keeps the point under the cursor where it is, so zooming at a corner
	# does not throw away what you were looking at.
	var at := Vector2(1300, 250)
	var before_zoom: Vector3 = _city._ground_at(at)
	_city.zoom_by(0.5, at)
	_ok("zooming in keeps the point under the cursor",
			_city._ground_at(at).distance_to(before_zoom) < 0.01)
	_city.zoom_by(4.0, at)
	_ok("zooming out keeps it too",
			_city._ground_at(at).distance_to(before_zoom) < 0.01)

	_ok("zoom stops at the limits",
			cam.size <= _city._zoom_out + 0.001 and cam.size >= _city._zoom_in - 0.001)

	# Panning far past the edge is clamped, so the view cannot leave the map.
	_city._grab = _city._ground_at(press)
	_city.pan_to(press + Vector2(9000, 9000))
	# The clamp measures at the middle of the *actual* viewport, which headless
	# does not size to 1920x1080. Asking for the same point rather than assuming
	# one is the difference between testing the clamp and testing a guess.
	var middle: Vector2 = _city.get_viewport().get_visible_rect().size * 0.5
	var centre: Vector3 = _city._ground_at(middle)
	var limit: float = float(_city.GRID_SIZE) * 0.5 + _city.PAN_MARGIN + 0.001
	_ok("panning off the map is clamped",
			absf(centre.x) <= limit and absf(centre.z) <= limit)

	if _failures == 0:
		print("PASS — place, refuse, build, produce, upgrade, save, load, migrate and the camera all work")
		quit(0)
	else:
		printerr("FAILED — %d check(s)" % _failures)
		quit(1)
	return
