class_name SimChecks
extends RefCounted

## The Godot-to-Rust boundary checks, in one place so they can run two ways.
##
##   1. Headless on a desktop, via `tools/sim_smoke.gd` and `--script`.
##   2. Inside a running build, from `WorldRoot._ready()`.
##
## The second one exists because **an exported app ignores `--script`**. On a
## phone or an emulator there is no other way to see the determinism hash, and
## the hash on a real ARM device is the Phase 1 gate. Read it with:
##
##   adb logcat -s godot:V | grep "sim "
##
## What this guards: both sides are tested on their own — sim-core by
## `cargo test`, the Godot project by importing cleanly — but nothing else
## checks that they agree once loaded together. A mismatched GDExtension build
## fails here and nowhere else.

## Kept in step with determinism.rs::tests::EXPECTED_HASH. If you change one,
## change both — and see that file's documentation before changing either.
const EXPECTED_HASH := "0x6de277a1cf08225b"
const EXPECTED_TICK_RATE := 20

var _failures := 0


func _check(label: String, actual: Variant, expected: Variant) -> void:
	if actual == expected:
		print("  ok    %s = %s" % [label, actual])
	else:
		_failures += 1
		printerr("  FAIL  %s: expected %s, got %s" % [label, expected, actual])


## Runs every check and prints the result. Returns the number of failures,
## so 0 means pass.
func run() -> int:
	print("sim smoke test")

	if not ClassDB.class_exists("WastemarchSim"):
		printerr("  FAIL  WastemarchSim is not registered.")
		printerr("        The GDExtension did not load. Usually one of:")
		printerr("          - `cargo build` has not been run in sim/")
		printerr("          - the editor has not scanned since sim.gdextension was added;")
		printerr("            run `$GODOT --headless --path game --editor --quit` once")
		printerr("          - on a device: the .so for this architecture is missing or")
		printerr("            zero bytes in the package — check `unzip -l <apk> | grep lib/`")
		return 1

	var sim: Object = ClassDB.instantiate("WastemarchSim")

	_check("tick_rate", sim.tick_rate(), EXPECTED_TICK_RATE)

	# 3/2 in fixed point is 1.5, which is 6144 raw units at 12 fractional bits.
	_check("fx_ratio(3,2)", sim.fx_ratio(3, 2), 6144)
	_check("fx_to_display", sim.fx_to_display(sim.fx_ratio(3, 2)), 1.5)

	# The same seed must produce the same draws. This is the property the whole
	# architecture rests on, checked across the boundary rather than inside Rust.
	sim.start(12345)
	var first: Array = []
	for i in range(8):
		first.append(sim.draw_below(100))
		sim.step()
	_check("tick advanced", sim.tick(), 8)

	sim.start(12345)
	var second: Array = []
	for i in range(8):
		second.append(sim.draw_below(100))
	_check("same seed replays", second, first)

	# A different seed must NOT produce the same draws, or the seed is being
	# ignored and the check above would pass for the wrong reason.
	sim.start(54321)
	var different: Array = []
	for i in range(8):
		different.append(sim.draw_below(100))
	if different == first:
		_failures += 1
		printerr("  FAIL  different seed produced identical draws — seed ignored?")
	else:
		print("  ok    different seed differs")

	_check("determinism hash", sim.determinism_hash(), EXPECTED_HASH)

	if _failures == 0:
		print("PASS — the Rust simulation is running inside Godot and agrees with CI")
	else:
		printerr("FAILED — %d check(s)" % _failures)
	return _failures
