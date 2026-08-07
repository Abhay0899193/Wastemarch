//! Wastemarch deterministic simulation core.
//!
//! Inputs in, state out. No I/O, no system clock, no threading, no engine types.
//! The same inputs must produce a bit-identical result on macOS, Linux, and an
//! ARM phone — that property is what makes server-validated PvP in V2 an addition
//! rather than a rewrite.
//!
//! # The one rule
//!
//! **No floating-point anywhere in this crate.** Decimal arithmetic can differ in
//! the last bits between CPU architectures, and one such difference changes which
//! target a unit picks, which changes the whole battle. All maths is fixed-point:
//! integers with an agreed number of fractional bits.
//!
//! `ci/no-floats.sh` enforces this on every push and refuses the build otherwise.
//! It was added in Phase 0, before this file had any content, so there has never
//! been a violation to grandfather in.
//!
//! Phase 1 fills this in: fixed-point maths, a seeded PCG, entities, the grid,
//! flow-field pathfinding, targeting, damage.

#![forbid(unsafe_code)]

pub mod battle;
pub mod determinism;
pub mod entity;
pub mod fx;
pub mod grid;
pub mod hash;
pub mod pathfind;
pub mod record;
pub mod rng;

pub use battle::Battle;
pub use entity::{Combat, Entities, Entity, EntityId, EntityKind, Team};
pub use fx::Fx;
pub use grid::{Grid, Point, Terrain, Tile};
pub use hash::StateHasher;
pub use pathfind::{Direction, FlowField};
pub use record::{BattleRecord, BattleSetup, Input, ReplayError, TimedInput, TroopSpec, replay};
pub use rng::Pcg32;

/// Simulation ticks per second. Fixed forever — rendering interpolates between
/// ticks, and never writes back into simulation state.
pub const TICKS_PER_SECOND: u32 = 20;

/// Number of fractional bits in the fixed-point representation.
///
/// A value of `1 << FIXED_POINT_BITS` represents 1.0, so one world metre divides
/// into 4096 steps. Chosen as a power of two so scaling is a shift, which is exact
/// and identical everywhere.
pub const FIXED_POINT_BITS: u32 = 12;

/// One whole unit in fixed-point. 1.0 metre, 1.0 second, 1.0 of anything.
pub const FIXED_ONE: i32 = 1 << FIXED_POINT_BITS;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fixed_point_constants_are_consistent() {
        assert_eq!(FIXED_ONE, 4096);
        // Halving and doubling must round-trip exactly. If this ever fails, the
        // representation is not a clean power of two and every derived value is
        // suspect.
        assert_eq!((FIXED_ONE / 2) * 2, FIXED_ONE);
    }

    #[test]
    fn a_tick_divides_a_second_exactly() {
        // 20 Hz is chosen partly because 60 fps rendering is exactly three frames
        // per tick. If someone changes the tick rate, interpolation stops being
        // exact and this test is the reminder.
        assert_eq!(60 % TICKS_PER_SECOND, 0);
    }
}
