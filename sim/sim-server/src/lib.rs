//! Server-side battle validation, for V2 (Phase 9).
//!
//! Nakama loads this as a native module and re-simulates every `BattleRecord` a
//! client submits, comparing the resulting state hash against the client's claim.
//!
//! The point of this crate is that it contains almost nothing. It wraps the exact
//! same [`sim_core`] the phone runs — not a reimplementation of it. A second
//! implementation would have to be kept in perfect agreement forever, and would
//! not be.
//!
//! Stub until Phase 9. It exists now so the workspace shape is settled and CI
//! builds all three crates from day one.

#![forbid(unsafe_code)]

pub use sim_core::TICKS_PER_SECOND;

#[cfg(test)]
mod tests {
    #[test]
    fn links_against_sim_core() {
        assert_eq!(super::TICKS_PER_SECOND, sim_core::TICKS_PER_SECOND);
    }
}
