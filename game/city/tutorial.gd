class_name CityTutorial
extends Control

## Durn's build tutorial: one instruction at a time, over the city.
##
## The script is `game/data/tutorial.json` and there is deliberately no logic in
## here that knows what any particular step says. Adding a step is editing that
## file.
##
## **The shape is copied from Clash of Clans, measured rather than remembered** —
## `docs/reference/COC_TEARDOWN.md`. Three things carry almost all of it:
##
## 1. **A named character in the corner, speaking**, with the bubble beside them.
##    Their ally sits bottom-left and their villain bottom-right; ours is Durn,
##    on the left, because he is on your side.
## 2. **Everything else dimmed.** A heavy vignette — theirs is roughly 40% — is
##    what makes one bright instruction readable over a bright field.
## 3. **One enormous arrow** at exactly one thing.
##
## What it does *not* do is block input. A tutorial that physically prevents you
## from touching anything else is more code, and it fails badly the first time a
## step's goal turns out to be unreachable. This one only ever suggests; if the
## player does something else first, the step it was waiting for is simply
## already done when it gets there.
##
## **Durn has no portrait yet.** A name plate stands in for it, and that is
## honest — a fake portrait would look finished and stop anyone commissioning the
## real one. `docs/BACKLOG.md`.

const DATA_PATH := "res://data/tutorial.json"
const DIM := 0.42                       ## how far the world is darkened behind it
const ARROW_BOB_PX := 10.0              ## how far the arrow travels, up and down
const ARROW_BOB_HZ := 1.6

var _city: City = null
var _steps: Array = []
var _step := 0
var _camera_start := Vector3.ZERO
var _dim: ColorRect = null
var _who: Label = null
var _bubble: PanelContainer = null
var _text: Label = null
var _next: Button = null
var _arrow: Label = null
var _elapsed := 0.0


func setup(city: City) -> void:
	_city = city
	var raw := FileAccess.get_file_as_string(DATA_PATH)
	var data: Dictionary = JSON.parse_string(raw)
	if data.is_empty():
		push_error("could not read %s" % DATA_PATH)
		return
	_steps = data["steps"]
	_camera_start = city.get_node("Camera3D").position
	_build()
	_show_step()


func step() -> int:
	return _step


## Used by the save file, so a returning player is not taught to pan again.
func skip_to(step_index: int) -> void:
	_step = clampi(step_index, 0, _steps.size())
	_show_step()


# ---------------------------------------------------------------------------
# What it looks like
# ---------------------------------------------------------------------------

func _build() -> void:
	# **`set_anchors_preset` alone leaves the size at zero**, and a zero-sized
	# Control lays every anchored child out against nothing — the whole tutorial
	# was invisible with `visible == true`. The `_and_offsets_` variant is the
	# one that actually fills the parent.
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE

	# The dim sits *behind* the bubble but in front of the world. It ignores the
	# mouse, which is the whole reason this tutorial cannot lock anyone out.
	_dim = ColorRect.new()
	_dim.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_dim.color = Color(0.02, 0.03, 0.04, DIM)
	_dim.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_dim)

	_arrow = Label.new()
	_arrow.text = "▼"
	_arrow.add_theme_font_size_override("font_size", 46)
	_arrow.modulate = Color(1.0, 0.72, 0.18)
	_arrow.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_arrow.visible = false
	add_child(_arrow)

	var box := VBoxContainer.new()
	box.anchor_top = 1.0
	box.anchor_bottom = 1.0
	box.offset_left = 26
	box.offset_top = -260
	box.offset_bottom = -150
	box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(box)

	_who = Label.new()
	_who.text = "DURN BRAKKELBEARD"
	_who.add_theme_font_size_override("font_size", 13)
	_who.modulate = Color(1.0, 0.82, 0.5)
	_who.mouse_filter = Control.MOUSE_FILTER_IGNORE
	box.add_child(_who)

	_bubble = PanelContainer.new()
	_bubble.custom_minimum_size = Vector2(560, 0)
	_bubble.mouse_filter = Control.MOUSE_FILTER_IGNORE
	box.add_child(_bubble)

	var inner := VBoxContainer.new()
	inner.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_bubble.add_child(inner)

	_text = Label.new()
	_text.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_text.custom_minimum_size = Vector2(540, 0)
	_text.add_theme_font_size_override("font_size", 17)
	_text.mouse_filter = Control.MOUSE_FILTER_IGNORE
	inner.add_child(_text)

	_next = Button.new()
	_next.text = "Right you are"
	_next.custom_minimum_size = Vector2(160, 36)
	_next.visible = false
	_next.pressed.connect(_advance)
	inner.add_child(_next)


func _show_step() -> void:
	if _step >= _steps.size():
		visible = false
		return
	visible = true
	var s: Dictionary = _steps[_step]
	_text.text = s["say"]
	_next.visible = String((s["goal"] as Dictionary)["type"]) == "none"


func _advance() -> void:
	_step += 1
	_show_step()


# ---------------------------------------------------------------------------
# Whether the player has done the thing
# ---------------------------------------------------------------------------

func _process(delta: float) -> void:
	if _city == null or _step >= _steps.size():
		return
	_elapsed += delta
	var s: Dictionary = _steps[_step]
	if _satisfied(s["goal"]):
		_advance()
		return
	_point_at(String(s.get("point", "")))


func _satisfied(goal: Dictionary) -> bool:
	match String(goal["type"]):
		"none":
			return false                       # only the button advances this one
		"camera":
			var cam: Camera3D = _city.get_node("Camera3D")
			return cam.position.distance_to(_camera_start) > 1.0 \
					or absf(cam.size - _city._zoom_out * 0.5) > 0.5
		"placed":
			return _count(String(goal["id"]), 1, false) > 0
		"finished":
			return _count(String(goal["id"]), 1, true) > 0
		"selected":
			return _city._building_at(_city._chosen_cell) != null
		"level":
			return _count(String(goal["id"]), int(goal["level"]), true) > 0
	push_warning("tutorial: unknown goal type '%s'" % goal["type"])
	return true                                 # never wedge on a typo


func _count(id: String, level: int, finished_only: bool) -> int:
	var n := 0
	for b in _city._built:
		if b["id"] == id and int(b["level"]) >= level \
				and (not finished_only or b["remaining"] <= 0.0):
			n += 1
	return n


# ---------------------------------------------------------------------------
# The arrow
# ---------------------------------------------------------------------------

func _point_at(target: String) -> void:
	var at := _target_position(target)
	_arrow.visible = at != Vector2.INF
	if not _arrow.visible:
		return
	var bob := sin(_elapsed * TAU * ARROW_BOB_HZ) * ARROW_BOB_PX
	_arrow.position = at - Vector2(_arrow.size.x * 0.5, _arrow.size.y + 6.0 - bob)


func _target_position(target: String) -> Vector2:
	if target.begins_with("card:"):
		var button := _city.card_for(target.substr(5))
		if button == null:
			return Vector2.INF
		return button.global_position + Vector2(button.size.x * 0.5, 0.0)
	if target.begins_with("building:"):
		var id := target.substr(9)
		for b in _city._built:
			if b["id"] == id and is_instance_valid(b["node"]):
				var cam: Camera3D = _city.get_node("Camera3D")
				return cam.unproject_position((b["node"] as Node3D).global_position)
		return Vector2.INF
	return Vector2.INF
