//! Fixed-point arithmetic — the only number type permitted in the simulation.
//!
//! [`Fx`] is a 32-bit signed integer holding a value scaled by
//! [`FIXED_ONE`](crate::FIXED_ONE). The low [`FIXED_POINT_BITS`](crate::FIXED_POINT_BITS)
//! bits are the fraction, the rest are the whole part. Every operation is integer
//! arithmetic, so results are identical on every CPU that has ever existed. See
//! `docs/ARCHITECTURE.md` for why that matters more here than speed.
//!
//! # Range and resolution
//!
//! With 12 fractional bits: values from about -524288 to +524288, in steps of
//! 1/4096 (about 0.00024). The world grid is 44x44 tiles at one metre each, so
//! this is a very long way from the limits.
//!
//! # Rounding
//!
//! [`Fx::mul`] and [`Fx::div`] both **round half toward positive infinity**. The
//! rule matters far less than the fact that both use the same one — mixed rounding
//! is exactly the kind of subtle asymmetry that produces a desync nobody can find.
//!
//! # Overflow
//!
//! Overflow panics, always, in every build profile. A silently truncated multiply
//! yields a plausible-looking wrong number, and in V2 that is a phone and a server
//! disagreeing about a battle with no way to reproduce it. A panic is a bug report.

use core::fmt;
use core::ops::{Add, AddAssign, Div, Mul, Neg, Sub, SubAssign};

use crate::{FIXED_ONE, FIXED_POINT_BITS};

/// Half of one fixed-point unit, used to round half toward positive infinity.
const HALF: i64 = 1 << (FIXED_POINT_BITS - 1);

/// A fixed-point number. See the [module documentation](self).
#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Default)]
pub struct Fx(i32);

/// Narrows a wide intermediate back to 32 bits, panicking rather than truncating.
///
/// Deliberately not a `debug_assert`. Truncation is deterministic but wrong, and
/// "deterministic and wrong" is the failure mode this whole crate exists to avoid.
#[inline]
const fn narrow(wide: i64) -> Fx {
    assert!(
        wide >= i32::MIN as i64 && wide <= i32::MAX as i64,
        "fixed-point overflow"
    );
    Fx(wide as i32)
}

impl Fx {
    /// Zero.
    pub const ZERO: Fx = Fx(0);
    /// One.
    pub const ONE: Fx = Fx(FIXED_ONE);
    /// The smallest representable step, 1/4096.
    pub const EPSILON: Fx = Fx(1);
    /// The most negative representable value.
    pub const MIN: Fx = Fx(i32::MIN);
    /// The largest representable value.
    pub const MAX: Fx = Fx(i32::MAX);

    /// Wraps a raw scaled integer. For serialisation and tests, not for arithmetic.
    #[inline]
    pub const fn from_bits(bits: i32) -> Fx {
        Fx(bits)
    }

    /// The raw scaled integer. This is what gets written into a battle record.
    #[inline]
    pub const fn to_bits(self) -> i32 {
        self.0
    }

    /// Converts a whole number. Panics if it does not fit.
    #[inline]
    pub const fn from_int(n: i32) -> Fx {
        narrow((n as i64) * (FIXED_ONE as i64))
    }

    /// Builds a value from a ratio, e.g. `Fx::from_ratio(3, 2)` is 1.5.
    ///
    /// This is how constants are written, since the crate cannot spell a decimal
    /// literal. Usable in a `const` context, so balance values cost nothing at run
    /// time.
    #[inline]
    pub const fn from_ratio(numerator: i32, denominator: i32) -> Fx {
        assert!(denominator != 0, "Fx::from_ratio with a zero denominator");
        let num = (numerator as i64) * (FIXED_ONE as i64);
        let den = denominator as i64;
        narrow(round_div(num, den))
    }

    /// Largest whole number less than or equal to this value.
    #[inline]
    pub const fn floor_to_int(self) -> i32 {
        self.0 >> FIXED_POINT_BITS
    }

    /// Nearest whole number, halves going toward positive infinity.
    #[inline]
    pub const fn round_to_int(self) -> i32 {
        ((self.0 as i64 + HALF) >> FIXED_POINT_BITS) as i32
    }

    /// The fractional part, always in `[0, 1)` — including for negative values.
    #[inline]
    pub const fn fract(self) -> Fx {
        Fx(self.0 & (FIXED_ONE - 1))
    }

    /// Absolute value. Panics on [`Fx::MIN`], which has no positive counterpart.
    #[inline]
    pub const fn abs(self) -> Fx {
        narrow((self.0 as i64).abs())
    }

    /// Multiplication, rounding half toward positive infinity.
    #[inline]
    pub const fn mul(self, rhs: Fx) -> Fx {
        let wide = (self.0 as i64) * (rhs.0 as i64);
        narrow((wide + HALF) >> FIXED_POINT_BITS)
    }

    /// Division, rounding half toward positive infinity. Panics on divide by zero.
    #[inline]
    pub const fn div(self, rhs: Fx) -> Fx {
        assert!(rhs.0 != 0, "fixed-point divide by zero");
        let num = (self.0 as i64) << FIXED_POINT_BITS;
        narrow(round_div(num, rhs.0 as i64))
    }

    /// Square root. Panics on a negative input.
    ///
    /// Uses the standard library's integer square root, which is exact and
    /// therefore identical everywhere. Needed for real distances; prefer comparing
    /// squared distances where you can and skip this entirely.
    #[inline]
    pub const fn sqrt(self) -> Fx {
        assert!(self.0 >= 0, "square root of a negative value");
        // sqrt(x / ONE) * ONE == sqrt(x * ONE), and x * ONE always fits in 64 bits.
        narrow(((self.0 as i64) << FIXED_POINT_BITS).isqrt())
    }

    /// The smaller of two values.
    #[inline]
    pub const fn min(self, rhs: Fx) -> Fx {
        if self.0 < rhs.0 { self } else { rhs }
    }

    /// The larger of two values.
    #[inline]
    pub const fn max(self, rhs: Fx) -> Fx {
        if self.0 > rhs.0 { self } else { rhs }
    }

    /// Clamps into `[lo, hi]`. Panics if `lo > hi`.
    #[inline]
    pub const fn clamp(self, lo: Fx, hi: Fx) -> Fx {
        assert!(lo.0 <= hi.0, "Fx::clamp with lo greater than hi");
        self.max(lo).min(hi)
    }
}

/// Division rounding half toward positive infinity, for any sign of divisor.
///
/// Rust's `/` truncates toward zero, which rounds negatives the opposite way from
/// positives. Normalising the divisor to positive first makes one rule apply to
/// both.
#[inline]
const fn round_div(num: i64, den: i64) -> i64 {
    let (num, den) = if den < 0 { (-num, -den) } else { (num, den) };
    (num + den / 2).div_euclid(den)
}

impl Add for Fx {
    type Output = Fx;
    #[inline]
    fn add(self, rhs: Fx) -> Fx {
        narrow(self.0 as i64 + rhs.0 as i64)
    }
}

impl Sub for Fx {
    type Output = Fx;
    #[inline]
    fn sub(self, rhs: Fx) -> Fx {
        narrow(self.0 as i64 - rhs.0 as i64)
    }
}

impl Mul for Fx {
    type Output = Fx;
    #[inline]
    fn mul(self, rhs: Fx) -> Fx {
        Fx::mul(self, rhs)
    }
}

impl Div for Fx {
    type Output = Fx;
    #[inline]
    fn div(self, rhs: Fx) -> Fx {
        Fx::div(self, rhs)
    }
}

impl Neg for Fx {
    type Output = Fx;
    #[inline]
    fn neg(self) -> Fx {
        narrow(-(self.0 as i64))
    }
}

impl AddAssign for Fx {
    #[inline]
    fn add_assign(&mut self, rhs: Fx) {
        *self = *self + rhs;
    }
}

impl SubAssign for Fx {
    #[inline]
    fn sub_assign(&mut self, rhs: Fx) {
        *self = *self - rhs;
    }
}

impl fmt::Display for Fx {
    /// Four decimal places, produced by integer arithmetic only.
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        // Widen before taking the magnitude: i32::MIN has no positive counterpart.
        let magnitude = (self.0 as i64).abs();
        let whole = magnitude >> FIXED_POINT_BITS;
        let fraction = magnitude & (FIXED_ONE as i64 - 1);
        let decimals = (fraction * 10_000) >> FIXED_POINT_BITS;
        if self.0 < 0 {
            write!(f, "-")?;
        }
        write!(f, "{whole}.{decimals:04}")
    }
}

impl fmt::Debug for Fx {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "Fx({self})")
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const HALF_FX: Fx = Fx::from_ratio(1, 2);
    const THREE_HALVES: Fx = Fx::from_ratio(3, 2);

    #[test]
    fn constants_line_up() {
        assert_eq!(Fx::ONE.to_bits(), 4096);
        assert_eq!(HALF_FX.to_bits(), 2048);
        assert_eq!(THREE_HALVES.to_bits(), 6144);
        assert_eq!(Fx::ZERO, Fx::from_int(0));
    }

    #[test]
    fn whole_numbers_round_trip() {
        for n in [-1000, -7, -1, 0, 1, 7, 1000, 524_287] {
            assert_eq!(Fx::from_int(n).floor_to_int(), n, "round trip for {n}");
        }
    }

    #[test]
    fn addition_and_subtraction_are_exact() {
        assert_eq!(HALF_FX + HALF_FX, Fx::ONE);
        assert_eq!(Fx::ONE - HALF_FX, HALF_FX);
        assert_eq!(HALF_FX - Fx::ONE, -HALF_FX);

        let mut acc = Fx::ZERO;
        for _ in 0..4096 {
            acc += Fx::EPSILON;
        }
        // 4096 smallest steps make exactly one. No accumulated drift, which is the
        // entire reason for not using decimals.
        assert_eq!(acc, Fx::ONE);
    }

    #[test]
    fn multiplication_behaves() {
        assert_eq!(Fx::ONE * Fx::ONE, Fx::ONE);
        assert_eq!(Fx::from_int(3) * Fx::from_int(4), Fx::from_int(12));
        assert_eq!(HALF_FX * HALF_FX, Fx::from_ratio(1, 4));
        assert_eq!(Fx::from_int(-3) * Fx::from_int(4), Fx::from_int(-12));
        assert_eq!(Fx::from_int(-3) * Fx::from_int(-4), Fx::from_int(12));
        assert_eq!(Fx::from_int(7) * Fx::ZERO, Fx::ZERO);
    }

    #[test]
    fn multiplication_is_commutative() {
        // Not a given for fixed-point: rounding could break it if mul were
        // asymmetric. It must hold, because unit A hitting unit B has to compute
        // the same number as unit B hitting unit A.
        let samples = [
            Fx::from_ratio(1, 3),
            Fx::from_ratio(-7, 11),
            Fx::from_int(19),
            Fx::EPSILON,
            Fx::ZERO,
            Fx::from_ratio(22, 7),
        ];
        for a in samples {
            for b in samples {
                assert_eq!(a * b, b * a, "{a} * {b}");
            }
        }
    }

    #[test]
    fn division_behaves() {
        assert_eq!(Fx::from_int(12) / Fx::from_int(4), Fx::from_int(3));
        assert_eq!(Fx::ONE / Fx::from_int(2), HALF_FX);
        assert_eq!(Fx::from_int(-12) / Fx::from_int(4), Fx::from_int(-3));
        assert_eq!(Fx::from_int(-12) / Fx::from_int(-4), Fx::from_int(3));
        assert_eq!(Fx::ZERO / Fx::from_int(5), Fx::ZERO);
    }

    #[test]
    fn multiply_then_divide_returns_close_to_the_original() {
        // Fixed-point is lossy, so this is a tolerance check, not an equality one.
        // One step of tolerance is what a single rounding can cost.
        for n in [1, 2, 3, 7, 100, 1000] {
            let x = Fx::from_int(n);
            let divisor = Fx::from_int(3);
            let back = (x / divisor) * divisor;
            let drift = (back - x).abs();
            assert!(drift <= Fx::from_bits(2), "n={n} drifted by {drift}");
        }
    }

    #[test]
    fn rounding_is_the_same_rule_for_both_signs() {
        // Half toward positive infinity, consistently. If mul and div ever disagree
        // about this, a desync follows.
        assert_eq!(Fx::from_bits(1) / Fx::from_int(2), Fx::from_bits(1)); // 0.5 -> 1
        assert_eq!(Fx::from_bits(-1) / Fx::from_int(2), Fx::from_bits(0)); // -0.5 -> 0
        assert_eq!(Fx::from_bits(3) / Fx::from_int(2), Fx::from_bits(2)); // 1.5 -> 2
        assert_eq!(Fx::from_bits(-3) / Fx::from_int(2), Fx::from_bits(-1)); // -1.5 -> -1
    }

    #[test]
    fn floor_and_round_differ_where_they_should() {
        assert_eq!(THREE_HALVES.floor_to_int(), 1);
        assert_eq!(THREE_HALVES.round_to_int(), 2);
        assert_eq!((-THREE_HALVES).floor_to_int(), -2);
        assert_eq!((-THREE_HALVES).round_to_int(), -1);
    }

    #[test]
    fn fract_is_never_negative() {
        assert_eq!(THREE_HALVES.fract(), HALF_FX);
        // -1.5 is floor -2 plus fraction 0.5. Keeping fract in [0, 1) means
        // floor + fract reconstructs the value for negatives too.
        assert_eq!((-THREE_HALVES).fract(), HALF_FX);
        let x = -THREE_HALVES;
        assert_eq!(Fx::from_int(x.floor_to_int()) + x.fract(), x);
    }

    #[test]
    fn square_roots_are_exact_for_perfect_squares() {
        assert_eq!(Fx::from_int(0).sqrt(), Fx::ZERO);
        assert_eq!(Fx::from_int(1).sqrt(), Fx::ONE);
        assert_eq!(Fx::from_int(4).sqrt(), Fx::from_int(2));
        assert_eq!(Fx::from_int(144).sqrt(), Fx::from_int(12));
        assert_eq!(Fx::from_ratio(1, 4).sqrt(), HALF_FX);
    }

    #[test]
    fn square_root_of_two_squares_back() {
        let root = Fx::from_int(2).sqrt();
        assert_eq!(root.to_bits(), 5792); // 1.4141..., the exact fixed-point value
        let squared = root * root;
        assert!(
            (squared - Fx::from_int(2)).abs() <= Fx::from_bits(3),
            "sqrt(2)^2 was {squared}"
        );
    }

    #[test]
    fn ordering_matches_the_numbers() {
        assert!(Fx::from_int(-5) < Fx::from_int(-4));
        assert!(Fx::from_int(-1) < Fx::ZERO);
        assert!(Fx::ZERO < Fx::EPSILON);
        assert!(HALF_FX < Fx::ONE);
        let mut values = [Fx::from_int(3), Fx::from_int(-2), Fx::ZERO, Fx::ONE];
        values.sort();
        assert_eq!(
            values,
            [Fx::from_int(-2), Fx::ZERO, Fx::ONE, Fx::from_int(3)]
        );
    }

    #[test]
    fn min_max_clamp() {
        let lo = Fx::from_int(-2);
        let hi = Fx::from_int(5);
        assert_eq!(lo.min(hi), lo);
        assert_eq!(lo.max(hi), hi);
        assert_eq!(Fx::from_int(9).clamp(lo, hi), hi);
        assert_eq!(Fx::from_int(-9).clamp(lo, hi), lo);
        assert_eq!(Fx::ONE.clamp(lo, hi), Fx::ONE);
    }

    #[test]
    fn display_uses_four_decimals() {
        assert_eq!(Fx::ONE.to_string(), "1.0000");
        assert_eq!(HALF_FX.to_string(), "0.5000");
        assert_eq!(THREE_HALVES.to_string(), "1.5000");
        assert_eq!((-THREE_HALVES).to_string(), "-1.5000");
        assert_eq!(Fx::ZERO.to_string(), "0.0000");
        assert_eq!(Fx::from_ratio(1, 4).to_string(), "0.2500");
        assert_eq!(format!("{:?}", Fx::ONE), "Fx(1.0000)");
    }

    #[test]
    #[should_panic(expected = "fixed-point divide by zero")]
    fn dividing_by_zero_panics() {
        let _ = Fx::ONE / Fx::ZERO;
    }

    #[test]
    #[should_panic(expected = "fixed-point overflow")]
    fn overflow_panics_instead_of_truncating() {
        let _ = Fx::MAX * Fx::from_int(2);
    }

    #[test]
    #[should_panic(expected = "square root of a negative value")]
    fn square_root_of_a_negative_panics() {
        let _ = Fx::from_int(-1).sqrt();
    }

    #[test]
    fn from_int_rejects_values_that_do_not_fit() {
        // 524288 * 4096 is exactly 2^31, one past the top.
        assert!(std::panic::catch_unwind(|| Fx::from_int(524_288)).is_err());
    }
}
