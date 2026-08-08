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

	if _failures == 0:
		print("PASS — place, refuse, build, produce, save and load all work")
		quit(0)
	else:
		printerr("FAILED — %d check(s)" % _failures)
		quit(1)
	return
