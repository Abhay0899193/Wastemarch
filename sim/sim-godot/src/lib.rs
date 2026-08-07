//! GDExtension binding — the doorway from Godot into [`sim_core`].
//!
//! This crate is the only place allowed to know about both Godot and the
//! simulation. Keeping the boundary here is what lets `sim-server` reuse
//! `sim-core` completely untouched in V2.
//!
//! # The rule this file exists to enforce
//!
//! Values cross this boundary in one direction: the simulation decides, Godot
//! draws. Nothing here may write simulation state in response to a frame, a
//! window size, a touch position, or anything else that varies with how fast the
//! device happens to be running. The moment rendering can influence the
//! simulation, determinism is gone and V2's server validation with it.
//!
//! Fixed-point values are converted to Godot floats **only on the way out, for
//! display**. Never convert back and feed the result in.

// `deny` rather than `forbid`, unlike sim-core, because registering a
// GDExtension entry point is inherently unsafe — Godot calls into this library
// through a C ABI. That one impl below is the *only* place it is permitted;
// everything else in this crate is still refused.
#![deny(unsafe_code)]

use godot::prelude::*;
use sim_core::{Fx, Pcg32, TICKS_PER_SECOND, determinism};

/// The GDExtension entry point, quarantined in its own module so the
/// `unsafe_code` exemption applies to these three lines and nothing else.
#[allow(unsafe_code)]
mod entry {
    use godot::prelude::*;

    pub struct SimGodotExtension;

    #[gdextension]
    unsafe impl ExtensionLibrary for SimGodotExtension {}
}

/// Godot-facing handle onto the simulation.
///
/// Deliberately a `RefCounted` rather than a `Node`: the simulation is not part
/// of the scene tree and must not be driven by `_process`. Whatever owns this
/// steps it on a fixed schedule.
#[derive(GodotClass)]
#[class(base = RefCounted)]
pub struct WastemarchSim {
    rng: Pcg32,
    tick: u32,
}

#[godot_api]
impl IRefCounted for WastemarchSim {
    fn init(_base: Base<RefCounted>) -> Self {
        WastemarchSim {
            rng: Pcg32::new(0),
            tick: 0,
        }
    }
}

#[godot_api]
impl WastemarchSim {
    /// Simulation steps per second. Fixed at 20 forever; rendering interpolates.
    #[func]
    fn tick_rate(&self) -> i32 {
        TICKS_PER_SECOND as i32
    }

    /// How many steps have been simulated since the last [`Self::start`].
    #[func]
    fn tick(&self) -> i32 {
        self.tick as i32
    }

    /// Begins a run from a seed. The same seed always produces the same run.
    #[func]
    fn start(&mut self, seed: i64) {
        self.rng = Pcg32::new(seed as u64);
        self.tick = 0;
    }

    /// Advances the simulation by exactly one step.
    #[func]
    fn step(&mut self) {
        self.tick += 1;
    }

    /// Draws a number in `0..bound` from the simulation's generator.
    #[func]
    fn draw_below(&mut self, bound: i32) -> i32 {
        if bound <= 0 {
            godot_error!("draw_below needs a positive bound, got {bound}");
            return 0;
        }
        self.rng.below(bound as u32) as i32
    }

    /// The cross-platform determinism hash, as a hex string.
    ///
    /// Returned as text rather than a number because Godot's integers are signed
    /// 64-bit and this is unsigned — the largest values would come out negative.
    ///
    /// If this matches what CI reports on Linux, the same arithmetic is running
    /// here, inside Godot, on this machine.
    #[func]
    fn determinism_hash() -> GString {
        GString::from(format!("{:#018x}", determinism::reference_workload_hash()).as_str())
    }

    /// Converts a fixed-point value to a Godot float, for display only.
    ///
    /// One-way on purpose. Feeding a float back into the simulation is exactly
    /// what this architecture forbids, so there is no inverse of this function.
    #[func]
    fn fx_to_display(bits: i32) -> f64 {
        Fx::from_bits(bits).to_string().parse().unwrap_or(0.0)
    }

    /// Builds a fixed-point value from a ratio and returns its raw bits.
    ///
    /// Ratios rather than decimals because the simulation cannot represent a
    /// decimal literal: `fx_ratio(3, 2)` is 1.5.
    #[func]
    fn fx_ratio(numerator: i32, denominator: i32) -> i32 {
        if denominator == 0 {
            godot_error!("fx_ratio with a zero denominator");
            return 0;
        }
        Fx::from_ratio(numerator, denominator).to_bits()
    }
}

#[cfg(test)]
mod tests {
    #[test]
    fn links_against_sim_core() {
        assert_eq!(sim_core::TICKS_PER_SECOND, 20);
    }
}
