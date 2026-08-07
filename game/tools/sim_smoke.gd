extends SceneTree

## Smoke test for the Rust simulation running inside Godot.
##
##   $GODOT --headless --path game --script res://tools/sim_smoke.gd
##
## Exits 0 if every check passes, 1 otherwise, so it can be wired into CI.
##
## What this guards: the boundary between Godot and the Rust simulation. Both
## sides are tested on their own — sim-core by `cargo test`, the Godot project by
## importing cleanly — but nothing else checks that they agree once loaded
## together. A mismatched GDExtension build fails here and nowhere else.
##
## The important check is the last one. `determinism_hash` is computed by the
## same Rust code that CI runs on Linux and macOS. If the value printed here
## matches the one in `sim/sim-core/src/determinism.rs`, the arithmetic running
## inside Godot on this machine is identical to the arithmetic CI verified.

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


func _initialize() -> void:
	print("sim smoke test")

	if not ClassDB.class_exists("WastemarchSim"):
		printerr("  FAIL  WastemarchSim is not registered.")
		printerr("        The GDExtension did not load. Usually one of:")
		printerr("          - `cargo build` has not been run in sim/")
		printerr("          - the editor has not scanned since sim.gdextension was added;")
		printerr("            run `$GODOT --headless --path game --editor --quit` once")
		quit(1)
		return

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
		quit(0)
	else:
		printerr("FAILED — %d check(s)" % _failures)
		quit(1)
