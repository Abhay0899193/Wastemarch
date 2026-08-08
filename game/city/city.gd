class_name City
extends Node3D

## Phase 3 proof of concept: a grid you can build on.
##
##   $GODOT --path game res://city/City.tscn
##
## Pick a building from the bar, move the mouse to aim, click to place. Drag with
## the right button to pan, scroll to zoom. Buildings take time to finish and
## then produce a resource; what they produce pays for the next one, so the loop
## closes. `S` saves, `L` loads, `Escape` quits.
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
const DATA_PATH := "res://data/buildings.json"
const SAVE_PATH := "user://city_save.json"
const MODEL_DIR := "res://assets/models/"

@onready var _camera: Camera3D = $Camera3D
@onready var _ground: MeshInstance3D = $Ground
@onready var _placed: Node3D = $Placed
@onready var _hud: Control = $HUD/Root

var _defs: Dictionary = {}                  ## id -> definition
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
var _resource_labels: Dictionary = {}
var _status: Label = null


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

func _ready() -> void:
	_camera_home = _camera.position
	_set_zoom_limits()
	_load_definitions()
	_build_hud()
	_refresh_hud()
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
	_camera.size = _zoom_out                 # they open fully zoomed out, so do we


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


# ---------------------------------------------------------------------------
# The grid
# ---------------------------------------------------------------------------

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
		if _occupied.has(c):
			return false
	return _can_afford(id)


func _can_afford(id: String) -> bool:
	for res in (_defs[id]["cost"] as Dictionary):
		if _resources.get(res, 0) < _defs[id]["cost"][res]:
			return false
	return true


## Where the mouse is pointing, as a grid cell. The ground is the y=0 plane, so
## this is a ray-plane intersection rather than a physics query — no colliders
## needed, and it cannot be blocked by a building standing in the way.
func _cell_under_mouse() -> Vector2i:
	var mouse := get_viewport().get_mouse_position()
	var from := _camera.project_ray_origin(mouse)
	var dir := _camera.project_ray_normal(mouse)
	if absf(dir.y) < 0.0001:
		return Vector2i(9999, 9999)
	var t := -from.y / dir.y
	var hit := from + dir * t
	return Vector2i(floori(hit.x / TILE), floori(hit.z / TILE))


# ---------------------------------------------------------------------------
# Placing
# ---------------------------------------------------------------------------

func _select(id: String) -> void:
	_selected = id
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


func _spawn_model(id: String) -> Node3D:
	var path := MODEL_DIR + id + "_L1.glb"
	if not ResourceLoader.exists(path):
		push_warning("no model for %s at %s" % [id, path])
		return null
	return (load(path) as PackedScene).instantiate()


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
	for res in (def["cost"] as Dictionary):
		_resources[res] -= def["cost"][res]
	for c in _cells_for(cell, def["footprint"]):
		_occupied[c] = id

	var node := _spawn_model(id)
	if node == null:
		return false
	node.position = _cell_to_world(cell, def["footprint"])
	_placed.add_child(node)
	_tint(node, Color(0.55, 0.62, 0.75, 0.75))       # under construction

	_built.append({
		"id": id, "cell": [cell.x, cell.y], "node": node,
		"remaining": float(def["build_s"]),
		"tick": float(def["produces"]["interval"]),
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
	_update_ghost()
	for b in _built:
		if b["remaining"] > 0.0:
			b["remaining"] -= delta
			if b["remaining"] <= 0.0:
				_finish(b)
		else:
			b["tick"] -= delta
			if b["tick"] <= 0.0:
				var p: Dictionary = _defs[b["id"]]["produces"]
				b["tick"] = float(p["interval"])
				_resources[p["resource"]] = _resources.get(p["resource"], 0) \
						+ int(p["amount"])
				_refresh_hud()


func _finish(b: Dictionary) -> void:
	var node: Node3D = b["node"]
	if is_instance_valid(node):
		# Drop the override entirely rather than tint it back: the baked texture
		# is on the mesh's own material, and an override would hide it forever.
		for child in node.find_children("*", "MeshInstance3D", true, false):
			var mesh := child as MeshInstance3D
			for i in range(mesh.get_surface_override_material_count()):
				mesh.set_surface_override_material(i, null)
	_set_status("%s finished" % _defs[b["id"]]["name"])


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
		bar.add_child(_build_button(id))


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


func _set_status(text: String) -> void:
	if _status:
		_status.text = text


# ---------------------------------------------------------------------------
# Saving
# ---------------------------------------------------------------------------

func _save() -> void:
	var rows: Array = []
	for b in _built:
		rows.append({"id": b["id"], "cell": b["cell"],
					 "remaining": b["remaining"], "tick": b["tick"]})
	# `version` is here from the first save on purpose. Adding it later means a
	# migration that cannot tell old saves apart from new ones.
	var payload := {"version": 1, "resources": _resources, "buildings": rows}
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
	if payload.get("version", 0) != 1:
		_set_status("Save is version %s, this build reads 1"
				% payload.get("version", "?"))
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
		var node := _spawn_model(id)
		node.position = _cell_to_world(cell, def["footprint"])
		_placed.add_child(node)
		var entry := {"id": id, "cell": [cell.x, cell.y], "node": node,
					  "remaining": float(row["remaining"]),
					  "tick": float(row["tick"])}
		if entry["remaining"] > 0.0:
			_tint(node, Color(0.55, 0.62, 0.75, 0.75))
		_built.append(entry)

	_refresh_hud()
	_set_status("Loaded %d buildings" % _built.size())


# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		var mb: InputEventMouseButton = event
		if mb.button_index == MOUSE_BUTTON_WHEEL_UP:
			_camera.size = maxf(_zoom_in, _camera.size * 0.9)
		elif mb.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			_camera.size = minf(_zoom_out, _camera.size * 1.1)
		elif mb.button_index == MOUSE_BUTTON_LEFT and mb.pressed:
			if _selected != "":
				var cell := _cell_under_mouse()
				if _place(cell, _selected):
					if not _can_afford(_selected):
						_select("")
						_set_status("Not enough to build another")
				elif _occupied.has(cell):
					_set_status("Something is already there")
				elif not _can_afford(_selected):
					_set_status("Not enough to build that")
				else:
					_set_status("Outside the buildable ground")
		elif mb.button_index == MOUSE_BUTTON_RIGHT and mb.pressed:
			_select("")
			_set_status("")
	elif event is InputEventMouseMotion:
		var mm: InputEventMouseMotion = event
		if mm.button_mask & MOUSE_BUTTON_MASK_RIGHT:
			var speed: float = _camera.size / 600.0
			var right: Vector3 = _camera.global_transform.basis.x
			var fwd: Vector3 = -_camera.global_transform.basis.z
			fwd.y = 0.0
			_camera.position -= right * mm.relative.x * speed
			_camera.position -= fwd.normalized() * mm.relative.y * speed
	elif event is InputEventKey and event.is_pressed():
		var key: InputEventKey = event
		match key.keycode:
			KEY_ESCAPE: get_tree().quit()
			KEY_S: _save()
			KEY_L: _load()
			KEY_HOME: _camera.position = _camera_home
