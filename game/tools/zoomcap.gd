extends SceneTree

## Capture the asset preview at a chosen zoom, at 1920x1080.
##
##   $GODOT --path game --resolution 1920x1080 \
##       --script res://tools/zoomcap.gd -- out.png 9
##
## `tools/capture.gd` frames the whole scene, which is where every art defect in
## this project has hidden: at that size the buildings are a few hundred pixels
## across and a pale sliver down one edge is invisible. The owner spotted three
## separate problems by zooming in that a full-scene capture had shown as fine.
##
## **Look at art the size it will be judged, not the size that is convenient.**
var _f := 0
var _out := "zoom.png"
var _size := 9.0

func _initialize() -> void:
	var a := OS.get_cmdline_user_args()
	if a.size() > 0: _out = a[0]
	if a.size() > 1: _size = float(a[1])
	var packed: PackedScene = load("res://world/AssetPreview.tscn")
	var n := packed.instantiate()
	root.add_child(n)
	var cam: Camera3D = n.get_node("Camera3D")
	cam.size = _size
	get_root().set_content_scale_size(Vector2i(1920, 1080))

func _process(_d: float) -> bool:
	_f += 1
	if _f < 12: return false
	var img := root.get_texture().get_image()
	img.save_png(_out)
	print("wrote %s at ortho size %s" % [_out, _size])
	quit()
	return true
