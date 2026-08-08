extends Node3D

## Phase 0/1 gate scene. The only behaviour it has is to prove, from inside a
## real running build, that the Rust simulation loaded and produces the same
## determinism hash as CI does on macOS and Linux.
##
## This has to happen here rather than in a `--script` run because an exported
## app ignores `--script` entirely. On an Android device or emulator, read it
## with `adb logcat -s godot:V`.


func _ready() -> void:
	SimChecks.new().run()
