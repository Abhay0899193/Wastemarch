class_name City
extends Node3D

## Phase 3 proof of concept: a grid you can build on.
##
##   $GODOT --path game res://city/City.tscn
##
## Pick a building from the bar, move the mouse to aim, click to place. Click a
## finished building to select it and a short row appears underneath with its
## level and an upgrade button. Drag with the right button to pan, scroll to
## zoom. Buildings take time to finish and then produce a resource; what they
## produce pays for the next one, so the loop closes.
##
## | | |
## |---|---|
## | Pan | one finger, right-drag, middle-drag, arrow keys or `WASD` |
## | Zoom | two-finger pinch, wheel, trackpad pinch, `+` and `-` |
## | Place | pick a card, tap the ground |
## | Select | tap a finished building |
## | Cancel | right-click without dragging |
## | Save / load | `Ctrl+S` / `Ctrl+L` |
## | Recentre | `Home` |
## | Quit | `Escape` |
##
## **What this is and is not.** It is the smallest thing that is actually
## playable: place, wait, collect, place again. `MASTER_PLAN.md` Phase 3 also
## wants six buildings, upgrades, save migrations and Durn's tutorial, and its
## test is *"you can play for twenty minutes and want to keep going"*. This is
## not that yet. It is the skeleton that the rest hangs on, and it proves the
## parts fit: the locked camera, the grid, the models, the icons, the data file.
##
## Balance lives in `game/data/buildings.json` and every number in it is
## placeholder — `CLAUDE.md` forbids magic numbers in code, and Phase 5 tunes the
## real curve.
##
## **The Sun in `City.tscn` deliberately casts no shadow.** Clash of Clans casts
## none either — not from buildings, trees or troops — and the dark under a
## building is painted into the building instead. Ours comes from the ambient
## occlusion bake, which is the same trick. Long cast shadows are the fastest way
## to make an isometric base look muddy, and a shadow pass is one of the more
## expensive things a phone does. Measured and argued in
## `docs/reference/COC_TEARDOWN.md`.

const GRID_SIZE := 44
const TILE := 1.0

## How far fully zoomed in is from fully zoomed out. **4.0 is measured** — the
## same Clash of Clans building was matched between their most zoomed-out and
## most zoomed-in screenshots and came out at exactly a quarter the size. See
## `docs/reference/COC_TEARDOWN.md`. Ours used to be a free 10x range, which let
## the player zoom out until the city was a smudge and in until it was furniture.
const ZOOM_RANGE := 4.0

## Slack around the grid at full zoom-out, so the border is visible rather than
## exactly clipped. Theirs is about 6%.
const ZOOM_OUT_MARGIN := 1.06

## One notch of the wheel, and one press of the zoom key. The key steps harder
## because a laptop user is pressing it rather than rolling it.
const WHEEL_ZOOM_STEP := 1.1
const KEY_ZOOM_STEP := 1.25

## How far the mouse may move between press and release and still count as a
## click rather than a drag.
const CLICK_SLOP_PX := 6.0

## Keyboard panning, in screen-heights per second. Independent of zoom, so it
## covers the same fraction of what you can see however far in you are.
const KEY_PAN_PER_SECOND := 0.9

## How far past the edge of the grid the view may be pushed.
const PAN_MARGIN := 6.0
const DATA_PATH := "res://data/buildings.json"
const SAVE_PATH := "user://city_save.json"
const MODEL_DIR := "res://assets/models/"

@onready var _camera: Camera3D = $Camera3D
@onready var _ground: MeshInstance3D = $Ground
@onready var _placed: Node3D = $Placed
@onready var _hud: Control = $HUD/Root

var _defs: Dictionary = {}                  ## id -> definition
var _level_look: Array = []                 ## per-level scale and tint, from data
var _order: Array[String] = []
var _resources: Dictionary = {}
var _occupied: Dictionary = {}              ## Vector2i -> building id
var _built: Array[Dictionary] = []          ## live buildings, saved and loaded
var _selected: String = ""
var _ghost: Node3D = null
var _ghost_cell := Vector2i(9999, 9999)
var _ghost_valid := false
var _camera_home := Vector3.ZERO
var _zoom_out := 32.0                       ## fully out — set in _ready
var _zoom_in := 8.0                         ## fully in — set in _ready
var _obstacles: Dictionary = {}             ## Vector2i -> prop id, blocks building
var _scenes: Dictionary = {}                ## id -> PackedScene, loaded once
var _cards: Dictionary = {}                 ## id -> its card in the bottom bar
var _resource_labels: Dictionary = {}
var _status: Label = null
## The selected building is remembered by its **cell**, not by holding on to the
## dictionary. Godot compares dictionaries by reference and `_load` rebuilds
## every one of them, so a held reference would quietly point at a building that
## no longer exists. A cell is a fact about the world.
var _chosen_cell := Vector2i(9999, 9999)
var _panel: VBoxContainer = null
var _panel_title: Label = null
var _panel_gain: Label = null
var _tutorial: CityTutorial = null
var _panel_button: Button = null
var _grabbing := false                      ## right or middle button held
var _grab := Vector3.ZERO                   ## the ground point being dragged
var _drag_px := 0.0                         ## how far the mouse moved while held


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

func _ready() -> void:
	_camera_home = _camera.position
	_set_zoom_limits()
	_scatter_props()
	_load_definitions()
	_preload_models()
	_build_hud()
	_build_panel()
	_refresh_hud()
	_start_tutorial()
	set_process(true)


## Fully zoomed out frames the whole grid; fully zoomed in is `ZOOM_RANGE` closer.
##
## Seen from 30 degrees up and 45 degrees round, a square grid of N tiles is a
## diamond `N * sqrt(2)` wide and half that tall in world units. A Godot
## orthographic camera's `size` is its *vertical* extent, so on a narrow screen
## the width is what runs out first and the limit has to come from the aspect —
## which is why this is computed rather than typed in. A phone is about 2.17:1
## and lands on 32; a 16:9 screen lands on 37.
func _set_zoom_limits() -> void:
	var diamond_w := float(GRID_SIZE) * TILE * sqrt(2.0)
	var diamond_h := diamond_w * 0.5
	var view := get_viewport().get_visible_rect().size
	var aspect: float = maxf(0.1, view.x / view.y)
	_zoom_out = maxf(diamond_h, diamond_w / aspect) * ZOOM_OUT_MARGIN
	_zoom_in = _zoom_out / ZOOM_RANGE
	# Clash of Clans opens fully zoomed out, but onto a field already full of
	# props and buildings. Ours starts with three buildings on 1,936 tiles, and
	# fully out makes them specks. Halfway is the honest compromise until the
	# city is dense enough to carry the wide shot.
	_camera.size = _zoom_out * 0.5


# ---------------------------------------------------------------------------
# The camera
#
# **Both of these work by grabbing the ground rather than by accumulating a
# speed, and that is the whole trick.** The old pan multiplied mouse pixels by
# `size / 600.0` and applied the same number to both axes. Two things were wrong
# with it: 600 is not the height of anybody's window, and the ground is
# foreshortened 2:1 vertically at a 30 degree camera, so a vertical drag has to
# move the camera *twice* as far as a horizontal one of the same length. At
# 1920x1080 that made horizontal panning 1.8x too fast and vertical panning half
# the speed it should be relative to it, so the world slid diagonally away from
# the cursor. That is what "pan is not working correctly" was.
#
# Working out the correct multiplier is possible, but it has to be re-derived
# every time the camera angle or the window changes. Putting the grabbed point
# back under the cursor needs no multiplier at all and cannot drift: for an
# orthographic camera, translating the camera by D moves the ground point under
# a fixed pixel by exactly D.
# ---------------------------------------------------------------------------

## Put the ground point grabbed at press-time back under the cursor.
func pan_to(screen: Vector2) -> void:
	_camera.position += _grab - _ground_at(screen)
	_clamp_camera()


## Zoom, keeping whatever is under `at` where it is. Zooming to the middle of the
## screen when you are looking at a corner throws away what you were looking at.
func zoom_by(factor: float, at: Vector2) -> void:
	var before := _ground_at(at)
	_camera.size = clampf(_camera.size * factor, _zoom_in, _zoom_out)
	_camera.position += before - _ground_at(at)
	_clamp_camera()


## Stop the view leaving the map. Measured at the middle of the screen, because
## that is where the player thinks the camera is.
func _clamp_camera() -> void:
	var centre := _ground_at(get_viewport().get_visible_rect().size * 0.5)
	var limit := float(GRID_SIZE) * TILE * 0.5 + PAN_MARGIN
	var inside := Vector3(clampf(centre.x, -limit, limit), 0.0,
						  clampf(centre.z, -limit, limit))
	_camera.position += inside - centre


## Arrow keys and WASD, for the laptop with no mouse wheel and no third button.
## Continuous rather than per-keystroke, so holding a key glides.
func _keyboard_pan(delta: float) -> void:
	var move := Vector2(
			float(Input.is_key_pressed(KEY_RIGHT) or Input.is_key_pressed(KEY_D))
			- float(Input.is_key_pressed(KEY_LEFT) or Input.is_key_pressed(KEY_A)),
			float(Input.is_key_pressed(KEY_DOWN) or Input.is_key_pressed(KEY_S))
			- float(Input.is_key_pressed(KEY_UP) or Input.is_key_pressed(KEY_W)))
	if move == Vector2.ZERO:
		return
	# Same trick again: ask where two screen points land on the ground and move
	# by the difference, so the speed is right at every zoom and angle for free.
	var view := get_viewport().get_visible_rect().size
	var step := move.normalized() * view.y * KEY_PAN_PER_SECOND * delta
	var middle := view * 0.5
	_camera.position += _ground_at(middle + step) - _ground_at(middle)
	_clamp_camera()


## Trees and rocks over the whole field, in two draw calls.
##
## **Bare ground is what makes a small base look unfinished rather than early.**
## Clash of Clans covers its empty tiles in props and it is a large part of why
## their first screen does not look empty — `docs/reference/COC_TEARDOWN.md`.
##
## `MultiMeshInstance3D` draws any number of copies of one mesh in a single call,
## which is the only reason a hundred and fifty of these is affordable —
## `CLAUDE.md` requires it for anything repeated.
##
## They are laid out from a fixed seed rather than saved, so the same village
## always looks the same and the save file never has to carry scenery. They are
## kept out of `_occupied` for the same reason: `_load` clears that dictionary,
## and scenery that vanished after loading would be a bug you would find later
## and at a worse time.
const PROP_SEED := 20260809
const PINES := 100
const BOULDERS := 60
const PROP_CLEAR_RADIUS := 10                ## tiles round the middle left bare

func _scatter_props() -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = PROP_SEED
	_scatter_one("pine", PINES, rng)
	_scatter_one("boulder", BOULDERS, rng)


func _scatter_one(id: String, count: int, rng: RandomNumberGenerator) -> void:
	var mesh := _mesh_of(id)
	if mesh == null:
		push_warning("no prop mesh for %s — nothing scattered" % id)
		return

	var cells: Array[Vector2i] = []
	var half := GRID_SIZE / 2
	# Rejection sampling with a cap: a tile that is taken is simply skipped. The
	# cap is what stops an unlucky seed or a crowded field spinning forever.
	var attempts := 0
	while cells.size() < count and attempts < count * 30:
		attempts += 1
		var c := Vector2i(rng.randi_range(-half, half - 1),
						  rng.randi_range(-half, half - 1))
		if maxi(absi(c.x), absi(c.y)) < PROP_CLEAR_RADIUS:
			continue                          # leave the middle buildable
		if _obstacles.has(c):
			continue
		_obstacles[c] = id
		cells.append(c)

	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.mesh = mesh
	mm.instance_count = cells.size()
	for i in cells.size():
		var t := Transform3D().rotated(Vector3.UP, rng.randf() * TAU)
		var s := rng.randf_range(0.8, 1.2)
		t = t.scaled(Vector3(s, s, s))
		# Off-centre within its own tile, so the scatter does not read as a grid.
		t.origin = Vector3(
				float(cells[i].x) * TILE + TILE * 0.5 + rng.randf_range(-0.2, 0.2),
				0.0,
				float(cells[i].y) * TILE + TILE * 0.5 + rng.randf_range(-0.2, 0.2))
		mm.set_instance_transform(i, t)

	var node := MultiMeshInstance3D.new()
	node.name = "Scatter_" + id
	node.multimesh = mm
	add_child(node)


## The mesh inside a `.glb`, for a MultiMesh — which needs a `Mesh`, not a scene.
##
## The material can live on the mesh surface *or* as an override on the
## MeshInstance3D depending on how the exporter felt, so both are checked. Miss
## that and the props draw untextured white, which looks like a lighting bug and
## is not one.
func _mesh_of(id: String) -> Mesh:
	var path := MODEL_DIR + id + "_L1.glb"
	if not ResourceLoader.exists(path):
		return null
	var scene := (load(path) as PackedScene).instantiate()
	var mesh: Mesh = null
	for child in scene.find_children("*", "MeshInstance3D", true, false):
		var mi := child as MeshInstance3D
		mesh = mi.mesh
		if mesh and mesh.surface_get_material(0) == null:
			var over := mi.get_surface_override_material(0)
			if over:
				mesh.surface_set_material(0, over)
		break
	scene.queue_free()
	return mesh


func _load_definitions() -> void:
	var raw := FileAccess.get_file_as_string(DATA_PATH)
	var data: Dictionary = JSON.parse_string(raw)
	if data.is_empty():
		push_error("could not read %s" % DATA_PATH)
		return
	for entry in data["buildings"]:
		_defs[entry["id"]] = entry
		_order.append(entry["id"])
	_resources = (data["starting_resources"] as Dictionary).duplicate()
	_level_look = data["level_look"]


# ---------------------------------------------------------------------------
# The grid
# ---------------------------------------------------------------------------

## Load every building model once, up front.
##
## **Measured, not assumed.** Placing the first of each of three buildings cost a
## 1,376 ms frame; the models are 5 to 10 MB of glTF with baked 2,048-pixel
## textures, and none of that had been touched until the moment of the click.
## Loading them at startup moves the cost to where a pause is expected and where
## a loading screen will eventually live.
func _preload_models() -> void:
	for id in _order:
		for level in range(1, _max_level(id) + 1):
			var path := "%s%s_L%d.glb" % [MODEL_DIR, id, level]
			if ResourceLoader.exists(path) and not _scenes.has(path):
				_scenes[path] = load(path)


func _cell_to_world(cell: Vector2i, footprint: Array) -> Vector3:
	# A building's origin is the centre of its footprint (ART_BIBLE), so an
	# even-sized building sits on a tile corner and an odd one on a tile centre.
	var w := float(footprint[0]) * TILE
	var d := float(footprint[1]) * TILE
	return Vector3(cell.x * TILE + w * 0.5, 0.0, cell.y * TILE + d * 0.5)


func _cells_for(cell: Vector2i, footprint: Array) -> Array[Vector2i]:
	var out: Array[Vector2i] = []
	for dx in range(int(footprint[0])):
		for dy in range(int(footprint[1])):
			out.append(Vector2i(cell.x + dx, cell.y + dy))
	return out


func _can_place(cell: Vector2i, id: String) -> bool:
	if not _defs.has(id):
		return false
	var half := GRID_SIZE / 2
	for c in _cells_for(cell, _defs[id]["footprint"]):
		if c.x < -half or c.x >= half or c.y < -half or c.y >= half:
			return false
		if _occupied.has(c) or _obstacles.has(c):
			return false
	return _can_afford(id)


# ---------------------------------------------------------------------------
# Levels
#
# Every number a level changes comes out of `buildings.json` — a base value and
# a multiplier per level — so none of it is written here. `CLAUDE.md` forbids
# balance numbers in code, and this is the file that would otherwise collect
# them.
#
# **The art does not have to keep up with the levels.** A building may have a
# model for level 1 only, or for 1, 3 and 5 as the keep does. `_model_for` takes
# the highest one at or below the level being asked for, so a level 4 keep uses
# the level 3 model and a level 4 croft uses its level 1 model. Building thirty
# models to prove that a level counter works would be the wrong order to do
# things in.
# ---------------------------------------------------------------------------

func _growth(def: Dictionary, key: String, level: int) -> float:
	return pow(float(def["upgrade"][key]), float(level - 1))


func _cost_at(id: String, level: int) -> Dictionary:
	var def: Dictionary = _defs[id]
	var factor := _growth(def, "cost", level)
	var out := {}
	for res in (def["cost"] as Dictionary):
		out[res] = int(round(float(def["cost"][res]) * factor))
	return out


func _build_s_at(id: String, level: int) -> float:
	return float(_defs[id]["build_s"]) * _growth(_defs[id], "build_s", level)


func _yield_at(id: String, level: int) -> int:
	var def: Dictionary = _defs[id]
	return int(round(float(def["produces"]["amount"])
			* _growth(def, "produces", level)))


func _max_level(id: String) -> int:
	return int(_defs[id]["max_level"])


func _can_pay(cost: Dictionary) -> bool:
	for res in cost:
		if _resources.get(res, 0) < cost[res]:
			return false
	return true


func _pay(cost: Dictionary) -> void:
	for res in cost:
		_resources[res] -= cost[res]


func _can_afford(id: String) -> bool:
	return _can_pay(_cost_at(id, 1))


## Where the mouse is pointing, as a grid cell. The ground is the y=0 plane, so
## this is a ray-plane intersection rather than a physics query — no colliders
## needed, and it cannot be blocked by a building standing in the way.
## Where a screen position lands on the ground.
##
## The ground is the y = 0 plane, so this is a ray-plane intersection rather
## than a physics query — no colliders needed, and it cannot be blocked by a
## building standing in the way.
func _ground_at(screen: Vector2) -> Vector3:
	var from := _camera.project_ray_origin(screen)
	var dir := _camera.project_ray_normal(screen)
	if absf(dir.y) < 0.0001:
		return Vector3.ZERO
	return from + dir * (-from.y / dir.y)


func _cell_under_mouse() -> Vector2i:
	var hit := _ground_at(get_viewport().get_mouse_position())
	return Vector2i(floori(hit.x / TILE), floori(hit.z / TILE))


# ---------------------------------------------------------------------------
# Placing
# ---------------------------------------------------------------------------

func _select(id: String) -> void:
	_selected = id
	if id != "":
		_choose(Vector2i(9999, 9999))
	_clear_ghost()
	if id == "":
		return
	_ghost = _spawn_model(id)
	if _ghost:
		_tint(_ghost, Color(0.4, 1.0, 0.4, 0.55))
		add_child(_ghost)
	_ghost_cell = Vector2i(9999, 9999)
	_set_status("Placing %s — click to build, right-click to cancel"
			% _defs[id]["name"])


func _clear_ghost() -> void:
	if _ghost and is_instance_valid(_ghost):
		_ghost.queue_free()
	_ghost = null


## The best model this building has at or below `level`.
##
## Returns the path, not the scene, so the caller can compare it against the one
## already standing and skip the swap when nothing changed.
func _model_for(id: String, level: int) -> String:
	for n in range(level, 0, -1):
		var path := "%s%s_L%d.glb" % [MODEL_DIR, id, n]
		if ResourceLoader.exists(path):
			return path
	return ""


func _spawn_model(id: String, level: int = 1) -> Node3D:
	var path := _model_for(id, level)
	if path == "":
		push_warning("no model for %s at any level up to %d" % [id, level])
		return null
	if not _scenes.has(path):
		_scenes[path] = load(path)
	var node := (_scenes[path] as PackedScene).instantiate() as Node3D
	_apply_level_look(node, level)
	return node


## Make an upgrade visible on a building that has no separate model for its
## level.
##
## **"There is no change in the building after an upgrade" was a fair report.**
## Only the keep has art past level 1, so five of the six buildings looked
## identical at every level, and nothing on screen said otherwise.
##
## Distinct art for every level is thirty models and a few hundred megabytes of
## baked texture, for buildings that are still placeholder — that is in
## `docs/BACKLOG.md`, not in this session. What Clash of Clans does for most of
## its own level-ups is cheaper and works: the building gets a little bigger and
## its colour moves. Both read at a glance and neither costs an asset.
##
## The numbers are in `buildings.json` under `level_look`, because they are
## values and `CLAUDE.md` does not allow values here.
func _apply_level_look(node: Node3D, level: int) -> void:
	if _level_look.is_empty():
		return
	var look: Dictionary = _level_look[clampi(level - 1, 0, _level_look.size() - 1)]
	node.scale = Vector3.ONE * float(look["scale"])

	var t: Array = look["tint"]
	var tint := Color(float(t[0]), float(t[1]), float(t[2]))
	if tint.is_equal_approx(Color.WHITE):
		return
	for child in node.find_children("*", "MeshInstance3D", true, false):
		var mesh := child as MeshInstance3D
		for i in range(mesh.get_surface_override_material_count()):
			var src := mesh.mesh.surface_get_material(i) if mesh.mesh else null
			if src == null:
				continue
			var mat: BaseMaterial3D = src.duplicate()
			mat.albedo_color = tint
			mesh.set_surface_override_material(i, mat)


## What a building looks like while it is being built.
##
## **This used to replace the model with a flat unshaded blue blob**, which for
## the six to twelve seconds of the build timer looked exactly like a building
## whose texture had not loaded — the owner reported it as "it takes ten seconds
## to render". It was not a rendering problem at all; there is no stall, the
## worst frame measured 138 ms. It was the *look* of the under-construction
## state saying "broken" instead of "working".
##
## So the real material is kept and merely darkened: `albedo_color` multiplies
## the baked texture, so the building reads as itself, in shade, with a timer
## over it. The timer is the other half — a wait nobody can see the end of feels
## like a fault.
func _under_construction(node: Node3D, seconds: float) -> Label3D:
	for child in node.find_children("*", "MeshInstance3D", true, false):
		var mesh := child as MeshInstance3D
		for i in range(mesh.get_surface_override_material_count()):
			var src := mesh.mesh.surface_get_material(i) if mesh.mesh else null
			var mat: BaseMaterial3D = src.duplicate() if src else StandardMaterial3D.new()
			mat.albedo_color = Color(0.60, 0.62, 0.66)
			mesh.set_surface_override_material(i, mat)

	var top := 1.0
	for child in node.find_children("*", "MeshInstance3D", true, false):
		top = maxf(top, (child as MeshInstance3D).get_aabb().end.y)

	var label := Label3D.new()
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.no_depth_test = true
	label.pixel_size = 0.006
	label.modulate = Color(1.0, 0.87, 0.6)
	label.outline_size = 10
	label.position.y = top + 0.5
	label.text = "%.0fs" % ceilf(seconds)
	node.add_child(label)
	return label


## Recolour every surface of a model without touching the shared material — a
## per-instance override, so tinting the ghost cannot tint every building.
func _tint(node: Node3D, colour: Color) -> void:
	for child in node.find_children("*", "MeshInstance3D", true, false):
		var mesh := child as MeshInstance3D
		var mat := StandardMaterial3D.new()
		mat.albedo_color = colour
		mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		for i in range(mesh.get_surface_override_material_count()):
			mesh.set_surface_override_material(i, mat)


func _place(cell: Vector2i, id: String) -> bool:
	# **The guard lives here, not in the click handler.** Every route to placing a
	# building goes through this function, so refusing here refuses everywhere —
	# the click, a future keyboard shortcut, a tutorial script. Checking in the
	# caller left exactly one hole and buildings went straight through it.
	if not _can_place(cell, id):
		return false

	var def: Dictionary = _defs[id]
	_pay(_cost_at(id, 1))
	for c in _cells_for(cell, def["footprint"]):
		_occupied[c] = id

	var node := _spawn_model(id)
	if node == null:
		return false
	node.position = _cell_to_world(cell, def["footprint"])
	_placed.add_child(node)

	_built.append({
		"id": id, "cell": [cell.x, cell.y], "node": node, "level": 1,
		"remaining": float(def["build_s"]),
		"tick": float(def["produces"]["interval"]),
		"label": _under_construction(node, float(def["build_s"])),
	})
	_set_status("%s started — %.0f seconds" % [def["name"], def["build_s"]])
	_refresh_hud()

	# Force the ghost to re-evaluate. `_update_ghost` skips the work when the
	# mouse has not moved to a different cell, and the tiles under it have just
	# become occupied — so without this the ghost stays green over ground it can
	# no longer use, and a second click drops a building straight through the
	# first one.
	_ghost_cell = Vector2i(9999, 9999)
	return true


# ---------------------------------------------------------------------------
# Time
# ---------------------------------------------------------------------------

func _process(delta: float) -> void:
	_keyboard_pan(delta)
	_update_ghost()
	_place_panel()
	for b in _built:
		if b["remaining"] > 0.0:
			b["remaining"] -= delta
			var label: Label3D = b.get("label")
			if label and is_instance_valid(label):
				label.text = "%.0fs" % maxf(ceilf(b["remaining"]), 0.0)
			if b["remaining"] <= 0.0:
				_finish(b)
		else:
			b["tick"] -= delta
			if b["tick"] <= 0.0:
				var p: Dictionary = _defs[b["id"]]["produces"]
				b["tick"] = float(p["interval"])
				_resources[p["resource"]] = _resources.get(p["resource"], 0) \
						+ _yield_at(b["id"], int(b["level"]))
				_refresh_hud()


## Upgrade a finished building one level.
##
## The model is only swapped when the new level actually has different art —
## `_model_for` falls back down the levels — so a level 4 keep is a visible
## change and a level 4 croft is not. That is deliberate: a level counter should
## not be blocked on thirty models existing.
func _upgrade(b: Dictionary) -> bool:
	var id: String = b["id"]
	var level := int(b["level"])
	if level >= _max_level(id):
		_set_status("%s is at its highest level" % _defs[id]["name"])
		return false
	if b["remaining"] > 0.0:
		_set_status("%s is still being built" % _defs[id]["name"])
		return false

	var next := level + 1
	var cost := _cost_at(id, next)
	if not _can_pay(cost):
		_set_status("Not enough for %s level %d" % [_defs[id]["name"], next])
		return false
	_pay(cost)
	b["level"] = next

	var cell := Vector2i(int(b["cell"][0]), int(b["cell"][1]))
	if _model_for(id, next) != _model_for(id, level):
		var old: Node3D = b["node"]
		if is_instance_valid(old):
			old.queue_free()
		var node := _spawn_model(id, next)
		node.position = _cell_to_world(cell, _defs[id]["footprint"])
		_placed.add_child(node)
		b["node"] = node
	else:
		# Same model, new level: the look still has to move, or the upgrade is
		# invisible. This branch is the common one — only the keep has art past
		# level 1.
		_apply_level_look(b["node"], next)

	b["remaining"] = _build_s_at(id, next)
	b["label"] = _under_construction(b["node"], b["remaining"])
	_set_status("%s upgrading to level %d" % [_defs[id]["name"], next])
	_refresh_hud()
	return true


func _finish(b: Dictionary) -> void:
	var label: Label3D = b.get("label")
	if label and is_instance_valid(label):
		label.queue_free()
	b["label"] = null
	var node: Node3D = b["node"]
	if is_instance_valid(node):
		# Clear the construction override, then put the level's look back.
		# Dropping the override alone would also drop the level tint, and the
		# building would quietly revert to its level 1 colour the moment it
		# finished — which is exactly the bug being fixed.
		for child in node.find_children("*", "MeshInstance3D", true, false):
			var mesh := child as MeshInstance3D
			for i in range(mesh.get_surface_override_material_count()):
				mesh.set_surface_override_material(i, null)
		_apply_level_look(node, int(b["level"]))
	_set_status("%s finished" % _defs[b["id"]]["name"])
	_refresh_panel()


func _update_ghost() -> void:
	if _ghost == null or not is_instance_valid(_ghost):
		return
	var cell := _cell_under_mouse()
	if cell == _ghost_cell:
		return
	_ghost_cell = cell
	var def: Dictionary = _defs[_selected]
	_ghost.position = _cell_to_world(cell, def["footprint"])
	_ghost_valid = _can_place(cell, _selected)
	_tint(_ghost, Color(0.35, 1.0, 0.4, 0.5) if _ghost_valid
			else Color(1.0, 0.25, 0.2, 0.5))


# ---------------------------------------------------------------------------
# Interface
# ---------------------------------------------------------------------------

func _build_hud() -> void:
	var top := HBoxContainer.new()
	top.add_theme_constant_override("separation", 18)
	top.position = Vector2(18, 12)
	_hud.add_child(top)
	for res in ["grain", "timber", "stone", "iron"]:
		var label := Label.new()
		label.add_theme_font_size_override("font_size", 20)
		top.add_child(label)
		_resource_labels[res] = label

	_status = Label.new()
	_status.add_theme_font_size_override("font_size", 16)
	_status.position = Vector2(18, 44)
	_status.modulate = Color(1, 1, 1, 0.75)
	_hud.add_child(_status)

	var bar := HBoxContainer.new()
	bar.add_theme_constant_override("separation", 10)
	bar.anchor_top = 1.0
	bar.anchor_bottom = 1.0
	bar.offset_top = -128
	bar.offset_left = 18
	bar.offset_bottom = -18
	_hud.add_child(bar)

	for id in _order:
		var button := _build_button(id)
		_cards[id] = button
		bar.add_child(button)


## The bottom-bar card for a building, so the tutorial can point at it.
func card_for(id: String) -> Button:
	return _cards.get(id)


func _build_button(id: String) -> Control:
	var def: Dictionary = _defs[id]
	var button := Button.new()
	button.custom_minimum_size = Vector2(112, 110)
	button.tooltip_text = "%s\n%s" % [def["name"], def["blurb"]]
	button.icon = load("res://assets/atlases/icons/%s_L1.png" % id) \
			if ResourceLoader.exists("res://assets/atlases/icons/%s_L1.png" % id) \
			else null
	button.expand_icon = true
	button.vertical_icon_alignment = VERTICAL_ALIGNMENT_TOP
	button.text = "\n\n\n\n%s" % _cost_text(def)
	button.add_theme_font_size_override("font_size", 12)
	button.pressed.connect(func() -> void: _select(id))
	return button


func _cost_text(def: Dictionary) -> String:
	var parts: Array[String] = []
	for res in (def["cost"] as Dictionary):
		parts.append("%d %s" % [def["cost"][res], res.substr(0, 2)])
	return " ".join(parts)


func _refresh_hud() -> void:
	for res in _resource_labels:
		(_resource_labels[res] as Label).text = "%s %d" % [
			res.capitalize(), _resources.get(res, 0)]


## The panel that appears under a building you tap.
##
## **Under the building, not at the edge of the screen.** Clash of Clans puts a
## short row of buttons directly beneath whatever you selected — Info, Upgrade,
## and the cost — so your eye never leaves the thing you are deciding about.
## Copying that is nearly free: the panel is one `Control` and its position is
## `unproject_position` of the building's own world position, re-read every frame
## because the camera pans and zooms under it.
func _build_panel() -> void:
	_panel = VBoxContainer.new()
	_panel.visible = false
	_panel.alignment = BoxContainer.ALIGNMENT_CENTER
	_hud.add_child(_panel)

	_panel_title = Label.new()
	_panel_title.add_theme_font_size_override("font_size", 16)
	_panel_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_panel.add_child(_panel_title)

	# **What the upgrade actually buys, as before and after.** Their upgrade
	# dialog shows "400 + 400", not "800", and that is most of why an upgrade
	# feels like something happened. A level number on its own does not.
	_panel_gain = Label.new()
	_panel_gain.add_theme_font_size_override("font_size", 13)
	_panel_gain.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_panel_gain.modulate = Color(0.72, 0.92, 0.66)
	_panel.add_child(_panel_gain)

	_panel_button = Button.new()
	_panel_button.custom_minimum_size = Vector2(150, 40)
	_panel_button.pressed.connect(func() -> void:
		var b: Variant = _building_at(_chosen_cell)
		if b != null:
			_upgrade(b)
			_refresh_panel())
	_panel.add_child(_panel_button)


## Which placed building, if any, occupies a cell.
func _building_at(cell: Vector2i) -> Variant:
	for b in _built:
		var origin := Vector2i(int(b["cell"][0]), int(b["cell"][1]))
		for c in _cells_for(origin, _defs[b["id"]]["footprint"]):
			if c == cell:
				return b
	return null


func _choose(cell: Vector2i) -> void:
	_chosen_cell = cell
	_refresh_panel()


func _refresh_panel() -> void:
	if _panel == null:
		return
	var found: Variant = _building_at(_chosen_cell)
	if found == null:
		_panel.visible = false
		return
	var b: Dictionary = found
	var id: String = b["id"]
	var level := int(b["level"])
	var produces: Dictionary = _defs[id]["produces"]
	_panel.visible = true
	_panel_title.text = "%s — level %d" % [_defs[id]["name"], level]
	if level >= _max_level(id):
		_panel_gain.text = "%d %s every %.0fs" % [
				_yield_at(id, level), produces["resource"], produces["interval"]]
		_panel_button.text = "Highest level"
		_panel_button.disabled = true
	else:
		_panel_gain.text = "%s  %d \u2192 %d every %.0fs" % [
				produces["resource"].capitalize(), _yield_at(id, level),
				_yield_at(id, level + 1), produces["interval"]]
		var cost := _cost_at(id, level + 1)
		var parts: Array[String] = []
		for res in cost:
			parts.append("%d %s" % [cost[res], res.substr(0, 2)])
		_panel_button.text = "Upgrade  " + " ".join(parts)
		_panel_button.disabled = b["remaining"] > 0.0 or not _can_pay(cost)


## Keeps the panel under its building while the camera moves.
func _place_panel() -> void:
	if _panel == null or not _panel.visible:
		return
	var found: Variant = _building_at(_chosen_cell)
	if found == null:
		_panel.visible = false
		return
	var b: Dictionary = found
	var node: Node3D = b["node"]
	if not is_instance_valid(node):
		_panel.visible = false
		return
	# The building's origin is the centre of its footprint on the ground, which
	# on screen sits *inside* the model. Projecting the near corner of the
	# footprint instead puts the panel below the building rather than across it.
	var foot: Array = _defs[b["id"]]["footprint"]
	var near := node.global_position + Vector3(
			float(foot[0]) * TILE * 0.5, 0.0, float(foot[1]) * TILE * 0.5)
	var screen := _camera.unproject_position(near)
	_panel.position = screen - Vector2(_panel.size.x * 0.5, -14.0)


## Durn, over the top of everything. Added last so it draws over the HUD.
func _start_tutorial() -> void:
	_tutorial = CityTutorial.new()
	_hud.add_child(_tutorial)
	_tutorial.setup(self)


func _set_status(text: String) -> void:
	if _status:
		_status.text = text


# ---------------------------------------------------------------------------
# Saving
# ---------------------------------------------------------------------------

## The version this build writes. Bump it in the same commit as the change that
## made the old shape wrong, and add a step to `_migrate`.
##
##   1  the first format
##   2  buildings carry a `level`
##   3  the save carries how far through the tutorial the player got
const SAVE_VERSION := 3


func _save() -> void:
	var rows: Array = []
	for b in _built:
		rows.append({"id": b["id"], "cell": b["cell"], "level": b["level"],
					 "remaining": b["remaining"], "tick": b["tick"]})
	# `version` is here from the first save on purpose. Adding it later means a
	# migration that cannot tell old saves apart from new ones.
	var payload := {"version": SAVE_VERSION, "resources": _resources,
					"buildings": rows,
					"tutorial_step": _tutorial.step() if _tutorial else 0}
	var f := FileAccess.open(SAVE_PATH, FileAccess.WRITE)
	f.store_string(JSON.stringify(payload, "  "))
	f.close()
	_set_status("Saved %d buildings" % rows.size())


func _load() -> void:
	if not FileAccess.file_exists(SAVE_PATH):
		_set_status("No save yet")
		return
	var payload: Dictionary = JSON.parse_string(
			FileAccess.get_file_as_string(SAVE_PATH))
	payload = _migrate(payload)
	if payload.is_empty():
		return

	for b in _built:
		if is_instance_valid(b["node"]):
			b["node"].queue_free()
	_built.clear()
	_occupied.clear()
	_resources = (payload["resources"] as Dictionary).duplicate()

	for row in payload["buildings"]:
		var id: String = row["id"]
		var cell := Vector2i(int(row["cell"][0]), int(row["cell"][1]))
		var def: Dictionary = _defs[id]
		for c in _cells_for(cell, def["footprint"]):
			_occupied[c] = id
		var node := _spawn_model(id, int(row["level"]))
		node.position = _cell_to_world(cell, def["footprint"])
		_placed.add_child(node)
		var entry := {"id": id, "cell": [cell.x, cell.y], "node": node,
					  "level": int(row["level"]),
					  "remaining": float(row["remaining"]),
					  "tick": float(row["tick"])}
		if entry["remaining"] > 0.0:
			entry["label"] = _under_construction(node, float(entry["remaining"]))
		_built.append(entry)

	if _tutorial:
		_tutorial.skip_to(int(payload.get("tutorial_step", 0)))
	_chosen_cell = Vector2i(9999, 9999)
	_refresh_panel()
	_refresh_hud()
	_set_status("Loaded %d buildings" % _built.size())


## Bring a save of any older version up to `SAVE_VERSION`, or return `{}`.
##
## **One step per version, applied in order, never a special case per field.**
## The temptation with the first migration is to write `if not row.has("level")`
## somewhere in the loading code and move on. That works exactly once; the second
## time, nothing can tell a version 1 save from a version 2 one that happens to
## be missing a field, and every later reader has to guess. A version number and
## a chain of steps is the only shape that keeps working.
##
## A save from the *future* is refused rather than guessed at. Silently dropping
## fields a newer build wrote is how a downgrade eats somebody's town.
func _migrate(payload: Dictionary) -> Dictionary:
	var version := int(payload.get("version", 0))
	if version < 1 or version > SAVE_VERSION:
		_set_status("Save is version %s, this build reads 1 to %d"
				% [payload.get("version", "?"), SAVE_VERSION])
		return {}

	if version == 1:
		# Version 1 had no levels; everything in one is level 1.
		for row in payload["buildings"]:
			row["level"] = 1
		version = 2

	if version == 2:
		# Version 2 predates the tutorial. Anyone who has a version 2 save has
		# already played, so they are past it rather than at the start of it.
		payload["tutorial_step"] = 9999
		version = 3

	payload["version"] = version
	return payload


# ---------------------------------------------------------------------------
# Touch
#
# **Godot's `emulate_mouse_from_touch` is deliberately left off.** With it on, a
# finger becomes a left click, so a one-finger drag would try to *place* a
# building rather than pan, and every pinch would arrive as two competing left
# buttons. Handling touch as touch is fewer surprises than handling a mouse that
# is not there.
#
# One finger pans, two fingers pinch to zoom, and a finger that goes down and up
# again without travelling is a tap — which does what a left click does.
#
# The pan and the zoom are the same grab-the-ground functions the mouse uses, so
# there is one implementation of "put this world point under that screen point"
# and touch cannot drift out of agreement with the mouse.
# ---------------------------------------------------------------------------

## How far a finger may travel and still be a tap rather than a drag. Larger
## than the mouse's, because fingers are not precise and a phone is held in a
## moving hand.
const TOUCH_SLOP_PX := 18.0

var _touches: Dictionary = {}               ## finger index -> current position
var _pinch_span := 0.0                      ## distance between two fingers
var _touch_travel := 0.0


func _touch(event: InputEventScreenTouch) -> void:
	if event.pressed:
		_touches[event.index] = event.position
		if _touches.size() == 1:
			_grab = _ground_at(event.position)
			_touch_travel = 0.0
		elif _touches.size() == 2:
			_pinch_span = _two_finger_span()
	else:
		# A tap does what a click does. Checked before the finger is forgotten,
		# and only for the *last* finger up, so lifting one finger out of a
		# pinch does not place a building.
		if _touches.size() == 1 and _touch_travel < TOUCH_SLOP_PX:
			_tap(event.position)
		_touches.erase(event.index)
		if _touches.size() == 1:
			# Back to one finger after a pinch: re-grab, or the view jumps.
			_grab = _ground_at(_touches.values()[0])


func _touch_drag(event: InputEventScreenDrag) -> void:
	_touches[event.index] = event.position
	if _touches.size() == 1:
		_touch_travel += event.relative.length()
		pan_to(event.position)
	elif _touches.size() == 2:
		var span := _two_finger_span()
		if _pinch_span > 1.0 and span > 1.0:
			zoom_by(_pinch_span / span, _two_finger_middle())
		_pinch_span = span


func _two_finger_span() -> float:
	var p: Array = _touches.values()
	return (p[0] as Vector2).distance_to(p[1] as Vector2)


func _two_finger_middle() -> Vector2:
	var p: Array = _touches.values()
	return ((p[0] as Vector2) + (p[1] as Vector2)) * 0.5


## One place that decides what pointing at the world means, so a tap and a left
## click cannot drift apart.
func _tap(at: Vector2) -> void:
	var cell := Vector2i(floori(_ground_at(at).x / TILE), floori(_ground_at(at).z / TILE))
	if _selected == "":
		_choose(cell)
		return
	if _place(cell, _selected):
		if not _can_afford(_selected):
			_select("")
			_set_status("Not enough to build another")
	elif _occupied.has(cell) or _obstacles.has(cell):
		_set_status("Something is already there")
	elif not _can_afford(_selected):
		_set_status("Not enough to build that")
	else:
		_set_status("Outside the buildable ground")


# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		var mb: InputEventMouseButton = event
		if mb.button_index == MOUSE_BUTTON_WHEEL_UP:
			zoom_by(1.0 / WHEEL_ZOOM_STEP, mb.position)
		elif mb.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			zoom_by(WHEEL_ZOOM_STEP, mb.position)
		elif mb.button_index in [MOUSE_BUTTON_RIGHT, MOUSE_BUTTON_MIDDLE]:
			# Grab the ground rather than accumulate a speed. Press remembers the
			# world point under the cursor; every motion event afterwards puts
			# that same point back under the cursor.
			_grabbing = mb.pressed
			if mb.pressed:
				_grab = _ground_at(mb.position)
				_drag_px = 0.0
			elif mb.button_index == MOUSE_BUTTON_RIGHT \
					and _drag_px < CLICK_SLOP_PX:
				# A right *click* cancels; a right *drag* was a pan and must not.
				# Without the distance test, panning silently deselects whatever
				# you were looking at, every single time you move the camera.
				_select("")
				_choose(Vector2i(9999, 9999))
				_set_status("")
		elif mb.button_index == MOUSE_BUTTON_LEFT and mb.pressed:
			_tap(mb.position)
	elif event is InputEventMouseMotion:
		var mm: InputEventMouseMotion = event
		if _grabbing:
			_drag_px += mm.relative.length()
			pan_to(mm.position)
	elif event is InputEventScreenTouch:
		_touch(event)
	elif event is InputEventScreenDrag:
		_touch_drag(event)
	elif event is InputEventMagnifyGesture:
		# A trackpad pinch, which is what a laptop actually has.
		var mg: InputEventMagnifyGesture = event
		zoom_by(1.0 / maxf(0.2, mg.factor), mg.position)
	elif event is InputEventKey and event.is_pressed():
		var key: InputEventKey = event
		var middle := get_viewport().get_visible_rect().size * 0.5
		# **Save is Ctrl+S, not S.** S is the `WASD` pan key, and a bare S bound to
		# both meant every pan downwards also wrote a save file.
		match key.keycode:
			KEY_ESCAPE: get_tree().quit()
			KEY_S when key.ctrl_pressed or key.meta_pressed: _save()
			KEY_L when key.ctrl_pressed or key.meta_pressed: _load()
			KEY_HOME: _camera.position = _camera_home
			KEY_EQUAL, KEY_PLUS, KEY_KP_ADD: zoom_by(1.0 / KEY_ZOOM_STEP, middle)
			KEY_MINUS, KEY_KP_SUBTRACT: zoom_by(KEY_ZOOM_STEP, middle)
