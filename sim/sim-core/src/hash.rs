//! State hashing — how two machines compare simulations.
//!
//! Reduces a whole simulation state to one 64-bit number. If a phone and a server
//! run the same battle and produce the same number, they agree. If they do not,
//! something is wrong and the battle is rejected. That comparison is Phase 1's
//! completion test and, in V2, the entire basis for trusting a submitted battle.
//!
//! # Why not the standard library's hasher
//!
//! Rust's [`std::collections::hash_map::DefaultHasher`] explicitly **does not**
//! guarantee a stable result across releases or platforms. It is designed for hash
//! maps, where only within-process consistency matters. Using it here would work
//! perfectly in testing and then silently disagree between an iPhone and a Linux
//! server — the exact failure this crate exists to prevent.
//!
//! So: FNV-1a, specified bit-for-bit, implemented in ten lines, frozen forever.
//!
//! # What this is not
//!
//! Not cryptographic. An attacker who can pick inputs can find collisions. That is
//! acceptable, because the server re-runs the battle rather than trusting the
//! client's number — the hash detects disagreement, it does not prove honesty.

/// FNV-1a 64-bit starting value, from the specification.
const OFFSET_BASIS: u64 = 0xcbf2_9ce4_8422_2325;
/// FNV-1a 64-bit multiplier, from the specification.
const PRIME: u64 = 0x0000_0100_0000_01b3;

/// Accumulates a simulation state into one comparable number.
///
/// Order matters: feeding the same values in a different order gives a different
/// result. That is wanted — two states holding the same units in a different order
/// really are different states, and iterating a collection whose order is not
/// deterministic is a bug this hash will expose.
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct StateHasher {
    hash: u64,
}

impl Default for StateHasher {
    fn default() -> Self {
        Self::new()
    }
}

impl StateHasher {
    /// A fresh hasher.
    #[inline]
    pub const fn new() -> Self {
        StateHasher { hash: OFFSET_BASIS }
    }

    /// Absorbs one byte. Everything else is built on this.
    #[inline]
    pub const fn write_u8(&mut self, value: u8) {
        self.hash ^= value as u64;
        self.hash = self.hash.wrapping_mul(PRIME);
    }

    /// Absorbs an unsigned 32-bit value, least significant byte first.
    ///
    /// The byte order is fixed here rather than taken from the host, so a
    /// big-endian machine would produce the same result as a little-endian one.
    #[inline]
    pub const fn write_u32(&mut self, value: u32) {
        let bytes = value.to_le_bytes();
        let mut i = 0;
        while i < bytes.len() {
            self.write_u8(bytes[i]);
            i += 1;
        }
    }

    /// Absorbs an unsigned 64-bit value, least significant byte first.
    #[inline]
    pub const fn write_u64(&mut self, value: u64) {
        let bytes = value.to_le_bytes();
        let mut i = 0;
        while i < bytes.len() {
            self.write_u8(bytes[i]);
            i += 1;
        }
    }

    /// Absorbs a signed 32-bit value. Two's complement, so this is exact.
    #[inline]
    pub const fn write_i32(&mut self, value: i32) {
        self.write_u32(value as u32);
    }

    /// Absorbs a fixed-point value by its raw bits.
    #[inline]
    pub const fn write_fx(&mut self, value: crate::Fx) {
        self.write_i32(value.to_bits());
    }

    /// Absorbs a slice of bytes.
    #[inline]
    pub const fn write_bytes(&mut self, bytes: &[u8]) {
        let mut i = 0;
        while i < bytes.len() {
            self.write_u8(bytes[i]);
            i += 1;
        }
    }

    /// The accumulated hash.
    #[inline]
    pub const fn finish(&self) -> u64 {
        self.hash
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::Fx;

    #[test]
    fn matches_the_published_fnv1a_vectors() {
        // Test vectors from the FNV specification. If these ever change, the
        // implementation has drifted from the standard and every recorded hash in
        // the project is invalidated.
        let cases: [(&str, u64); 4] = [
            ("", 0xcbf2_9ce4_8422_2325),
            ("a", 0xaf63_dc4c_8601_ec8c),
            ("foobar", 0x8594_4171_f739_67e8),
            ("wastemarch", 0x6473_bd33_6833_6540),
        ];
        for (input, expected) in cases {
            let mut hasher = StateHasher::new();
            hasher.write_bytes(input.as_bytes());
            assert_eq!(hasher.finish(), expected, "input {input:?}");
        }
    }

    #[test]
    fn an_empty_hasher_is_the_offset_basis() {
        assert_eq!(StateHasher::new().finish(), OFFSET_BASIS);
        assert_eq!(StateHasher::default().finish(), OFFSET_BASIS);
    }

    #[test]
    fn order_changes_the_result() {
        let mut forward = StateHasher::new();
        forward.write_u32(1);
        forward.write_u32(2);

        let mut backward = StateHasher::new();
        backward.write_u32(2);
        backward.write_u32(1);

        assert_ne!(forward.finish(), backward.finish());
    }

    #[test]
    fn a_single_bit_changes_the_result() {
        let mut a = StateHasher::new();
        a.write_i32(1024);
        let mut b = StateHasher::new();
        b.write_i32(1025);
        assert_ne!(a.finish(), b.finish());
    }

    #[test]
    fn width_matters() {
        // Writing 1 as 32 bits and as 64 bits must differ, or a refactor that
        // changed a field's width would go unnoticed.
        let mut narrow = StateHasher::new();
        narrow.write_u32(1);
        let mut wide = StateHasher::new();
        wide.write_u64(1);
        assert_ne!(narrow.finish(), wide.finish());
    }

    #[test]
    fn negative_values_are_handled() {
        let mut a = StateHasher::new();
        a.write_i32(-1);
        let mut b = StateHasher::new();
        b.write_u32(u32::MAX);
        // -1 and u32::MAX are the same 32 bits, so these agree by design.
        assert_eq!(a.finish(), b.finish());
    }

    #[test]
    fn fixed_point_values_hash_by_their_bits() {
        let mut viafx = StateHasher::new();
        viafx.write_fx(Fx::ONE);
        let mut viabits = StateHasher::new();
        viabits.write_i32(Fx::ONE.to_bits());
        assert_eq!(viafx.finish(), viabits.finish());
    }

    #[test]
    fn works_in_a_const_context() {
        // Every method is const, so a golden hash can be computed at compile time.
        const HASH: u64 = {
            let mut h = StateHasher::new();
            h.write_u32(42);
            h.finish()
        };
        let mut runtime = StateHasher::new();
        runtime.write_u32(42);
        assert_eq!(HASH, runtime.finish());
    }
}
