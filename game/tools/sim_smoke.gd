extends SceneTree

## Headless smoke test for the Rust simulation running inside Godot.
##
##   $GODOT --headless --path game --script res://tools/sim_smoke.gd
##
## Exits 0 if every check passes, 1 otherwise, so it can be wired into CI.
##
## The checks themselves live in `sim_checks.gd`, because an exported build
## ignores `--script` and needs to run the same checks from a node instead.


func _initialize() -> void:
	quit(1 if SimChecks.new().run() > 0 else 0)
