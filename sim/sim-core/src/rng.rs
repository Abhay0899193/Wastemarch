//! The simulation's only source of randomness.
//!
//! A PCG generator (permuted congruential generator): a 64-bit state advanced by
//! a multiply-and-add, then permuted down to 32 output bits. Small, fast, good
//! statistical quality, and — the part that matters here — built entirely from
//! wrapping integer arithmetic, so it produces the identical stream on every
//! platform.
//!
//! # Rules
//!
//! **Never use any other source of randomness in the simulation.** Not the
//! system generator, not a hash of a pointer, not the clock. The seed is part of
//! the battle record, and a battle must replay exactly from `(seed, inputs)`.
//!
//! **Never draw from this generator outside the simulation.** Drawing a number for
//! a visual effect would advance the state and change the battle. Rendering gets
//! its own generator, or none.
//!
//! Reference: M.E. O'Neill, *PCG: A Family of Better Random Number Generators*
//! (2014). This is `pcg32`, the 64-bit-state variant.

/// The multiplier from the reference implementation. Do not change it — a
/// different constant is a different generator, and every recorded battle would
/// replay differently.
const MULTIPLIER: u64 = 6_364_136_223_846_793_005;

/// Default stream selector, used when a caller does not pick one.
const DEFAULT_STREAM: u64 = 0xda3e_39cb_94b9_5bdb;

/// A seeded, reproducible random number generator.
///
/// Two generators built with the same seed and stream produce the same sequence,
/// forever, on every platform.
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct Pcg32 {
    state: u64,
    /// Always odd. Selects one of 2^63 distinct sequences.
    increment: u64,
}

impl Pcg32 {
    /// Creates a generator from a seed, on the default stream.
    #[inline]
    pub fn new(seed: u64) -> Self {
        Self::with_stream(seed, DEFAULT_STREAM)
    }

    /// Creates a generator from a seed on a chosen stream.
    ///
    /// Separate streams let independent parts of the simulation draw numbers
    /// without interfering — troop targeting on one, loot rolls on another —
    /// so adding a draw in one place cannot shift results in the other.
    pub fn with_stream(seed: u64, stream: u64) -> Self {
        let mut rng = Pcg32 {
            state: 0,
            // The low bit must be set, so the increment is odd and the sequence
            // has the full period.
            increment: (stream << 1) | 1,
        };
        // The reference seeding procedure: step, add the seed, step again.
        rng.step();
        rng.state = rng.state.wrapping_add(seed);
        rng.step();
        rng
    }

    /// Advances the internal state by one.
    #[inline]
    fn step(&mut self) {
        self.state = self
            .state
            .wrapping_mul(MULTIPLIER)
            .wrapping_add(self.increment);
    }

    /// Draws the next 32-bit value.
    #[inline]
    pub fn next_u32(&mut self) -> u32 {
        let previous = self.state;
        self.step();
        // The permutation: an xorshift chosen by the top bits, then a rotation
        // also chosen by the top bits. This is what turns a mediocre linear
        // congruential sequence into a good one.
        let xorshifted = (((previous >> 18) ^ previous) >> 27) as u32;
        let rotation = (previous >> 59) as u32;
        xorshifted.rotate_right(rotation)
    }

    /// Draws a value in `0..bound`, with every value equally likely.
    ///
    /// Panics if `bound` is zero.
    ///
    /// A plain `next_u32() % bound` would be very slightly biased toward small
    /// values, because 2^32 is not usually a multiple of `bound`. Over a season of
    /// loot rolls that bias is real, so the few values that would cause it are
    /// rejected and redrawn. The loop is deterministic: the same seed rejects the
    /// same draws in the same order on every machine.
    pub fn below(&mut self, bound: u32) -> u32 {
        assert!(bound != 0, "Pcg32::below(0)");
        // The first `threshold` values of the 32-bit range are the ones that would
        // skew the result. Equivalent to (2^32 - bound) % bound.
        let threshold = bound.wrapping_neg() % bound;
        loop {
            let draw = self.next_u32();
            if draw >= threshold {
                return draw % bound;
            }
        }
    }

    /// Draws a value in `low..=high`. Panics if `low > high`.
    pub fn range(&mut self, low: i32, high: i32) -> i32 {
        assert!(low <= high, "Pcg32::range with low greater than high");
        let span = (high as i64 - low as i64 + 1) as u32;
        low + self.below(span) as i32
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashSet;

    #[test]
    fn the_same_seed_gives_the_same_sequence() {
        let mut a = Pcg32::new(12345);
        let mut b = Pcg32::new(12345);
        for _ in 0..1000 {
            assert_eq!(a.next_u32(), b.next_u32());
        }
        assert_eq!(a, b);
    }

    #[test]
    fn different_seeds_give_different_sequences() {
        let mut a = Pcg32::new(1);
        let mut b = Pcg32::new(2);
        let a_draws: Vec<u32> = (0..32).map(|_| a.next_u32()).collect();
        let b_draws: Vec<u32> = (0..32).map(|_| b.next_u32()).collect();
        assert_ne!(a_draws, b_draws);
    }

    #[test]
    fn different_streams_give_different_sequences() {
        let mut a = Pcg32::with_stream(7, 1);
        let mut b = Pcg32::with_stream(7, 2);
        let a_draws: Vec<u32> = (0..32).map(|_| a.next_u32()).collect();
        let b_draws: Vec<u32> = (0..32).map(|_| b.next_u32()).collect();
        assert_ne!(a_draws, b_draws);
    }

    #[test]
    fn ten_thousand_seeds_each_replay_exactly() {
        // The property the whole architecture rests on, at the smallest scale it
        // can be tested: replaying from a seed reproduces the run. Phase 1 grows
        // this into the same assertion over a whole battle.
        for seed in 0..10_000u64 {
            let mut first = Pcg32::new(seed);
            let mut second = Pcg32::new(seed);
            for _ in 0..16 {
                assert_eq!(first.next_u32(), second.next_u32(), "seed {seed}");
            }
        }
    }

    #[test]
    fn seeds_do_not_collide_in_the_small() {
        // Nearby seeds must not produce the same opening draw, or every battle
        // started in the same second would look alike.
        let firsts: HashSet<u32> = (0..10_000u64)
            .map(|seed| Pcg32::new(seed).next_u32())
            .collect();
        assert_eq!(firsts.len(), 10_000);
    }

    #[test]
    fn below_stays_in_range() {
        let mut rng = Pcg32::new(99);
        for bound in [1u32, 2, 3, 6, 7, 100, 1000] {
            for _ in 0..1000 {
                let draw = rng.below(bound);
                assert!(draw < bound, "{draw} not below {bound}");
            }
        }
    }

    #[test]
    fn below_one_is_always_zero() {
        let mut rng = Pcg32::new(5);
        for _ in 0..100 {
            assert_eq!(rng.below(1), 0);
        }
    }

    #[test]
    fn below_is_roughly_uniform() {
        // A six-sided die, 60,000 times. Each face should come up about 10,000
        // times. A 5% tolerance catches a badly broken generator without being
        // flaky — and since the seed is fixed, this test either always passes or
        // always fails. It is never intermittent.
        let mut rng = Pcg32::new(0xfeed);
        let mut counts = [0u32; 6];
        for _ in 0..60_000 {
            counts[rng.below(6) as usize] += 1;
        }
        for (face, count) in counts.iter().enumerate() {
            assert!(
                (9_500..=10_500).contains(count),
                "face {face} came up {count} times"
            );
        }
    }

    #[test]
    fn range_covers_its_bounds() {
        let mut rng = Pcg32::new(2024);
        let mut saw_low = false;
        let mut saw_high = false;
        for _ in 0..1000 {
            let draw = rng.range(-3, 3);
            assert!((-3..=3).contains(&draw), "{draw} out of range");
            saw_low |= draw == -3;
            saw_high |= draw == 3;
        }
        assert!(saw_low && saw_high, "range never reached its endpoints");
    }

    #[test]
    fn range_with_equal_bounds_is_constant() {
        let mut rng = Pcg32::new(1);
        for _ in 0..50 {
            assert_eq!(rng.range(42, 42), 42);
        }
    }

    #[test]
    #[should_panic(expected = "Pcg32::below(0)")]
    fn below_zero_panics() {
        Pcg32::new(1).below(0);
    }

    #[test]
    #[should_panic(expected = "low greater than high")]
    fn range_with_inverted_bounds_panics() {
        Pcg32::new(1).range(5, 4);
    }
}
