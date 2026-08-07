//! GDExtension binding — the doorway from Godot into [`sim_core`].
//!
//! This crate is the only place allowed to know about both Godot and the
//! simulation. Keeping the boundary here is what lets `sim-server` reuse
//! `sim-core` untouched.
//!
//! Phase 1 adds the `godot` crate and the actual bindings. Until then this
//! exists so the workspace shape, the build, and CI are settled.

#![forbid(unsafe_code)]

/// Re-exported so a future session can confirm the dependency edge is live
/// without opening `Cargo.toml`.
pub use sim_core::TICKS_PER_SECOND;

#[cfg(test)]
mod tests {
    #[test]
    fn links_against_sim_core() {
        assert_eq!(super::TICKS_PER_SECOND, sim_core::TICKS_PER_SECOND);
    }
}
