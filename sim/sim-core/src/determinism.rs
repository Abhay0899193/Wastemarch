//! The cross-platform determinism check.
//!
//! Runs a fixed workload that exercises every arithmetic path in the crate and
//! reduces it to a single number. That number is written into the test below as a
//! constant. Every platform that runs the test suite must produce it exactly.
//!
//! This is Phase 1's completion criterion in miniature. It is deliberately built
//! now, while the crate is nearly empty and the workload is trivial, because a
//! check that has been green since the first commit stays green — whereas one
//! introduced after a divergence exists is a debugging session, not a test.
//!
//! # When this test fails
//!
//! **Do not update the expected number to make it pass.** A failure means one of:
//!
//! 1. The simulation changed, deliberately. Recompute the constant, and say so in
//!    the commit message — every previously recorded battle no longer replays.
//! 2. The simulation changed by accident. Find out what.
//! 3. Two platforms genuinely disagree. This is the emergency the crate exists to
//!    prevent; stop and investigate before anything else.
//!
//! Only case 1 justifies a new number.

use crate::hash::StateHasher;
use crate::rng::Pcg32;
use crate::{Fx, TICKS_PER_SECOND};

/// Runs the reference workload and returns its hash.
///
/// Exercises the paths where platforms are most likely to disagree: wide
/// multiplication, division and rounding of both signs, square roots, and the
/// generator's rejection loop.
pub fn reference_workload_hash() -> u64 {
    let mut hasher = StateHasher::new();
    let mut rng = Pcg32::new(0x5741_5354_454d_4152); // "WASTEMAR" in ASCII

    // Enough ticks that any per-step rounding difference compounds into an
    // obviously different hash rather than a near-miss.
    for tick in 0..(TICKS_PER_SECOND * 60) {
        hasher.write_u32(tick);

        // Values spanning both signs and a wide magnitude range.
        let a = Fx::from_ratio(rng.range(-10_000, 10_000), 97);
        let b = Fx::from_ratio(rng.range(-10_000, 10_000), 31);
        hasher.write_fx(a);
        hasher.write_fx(b);

        hasher.write_fx(a + b);
        hasher.write_fx(a - b);
        hasher.write_fx(a * b);
        if b != Fx::ZERO {
            hasher.write_fx(a / b);
        }
        hasher.write_fx(a.abs().sqrt());
        hasher.write_i32(a.floor_to_int());
        hasher.write_i32(a.round_to_int());
        hasher.write_fx(a.fract());
        hasher.write_fx(a.clamp(-Fx::ONE, Fx::ONE));

        // The bounded draw's rejection loop: a bound that is not a power of two,
        // so rejections actually happen.
        hasher.write_u32(rng.below(1000));
    }

    hash_rounding_boundaries(&mut hasher);
    hash_world_state(&mut hasher);

    hasher.finish()
}

/// Exercises the grid and entity storage, and folds the result in.
///
/// Extended as each piece of the simulation lands, rather than afterwards. A
/// canary is only sensitive to what its workload actually touches, so state that
/// is never hashed here is state whose divergence nobody would notice.
fn hash_world_state(hasher: &mut StateHasher) {
    use crate::grid::{Grid, Terrain, Tile};
    use crate::{Entities, Entity, EntityKind, Team};

    let mut rng = Pcg32::with_stream(0x4f53_544d_4552_4500, 7); // "OSTMERE\0"

    // A grid with every terrain scattered across it by seeded draws, so tile
    // indexing and bounds behaviour are both covered.
    let mut grid = Grid::new();
    for _ in 0..2_000 {
        let tile = Tile::new(rng.range(-2, crate::grid::GRID_SIZE + 1), rng.range(-2, 45));
        let terrain = match rng.below(5) {
            0 => Terrain::Open,
            1 => Terrain::Mud,
            2 => Terrain::Rock,
            3 => Terrain::Treeline,
            _ => Terrain::Built,
        };
        // Deliberately includes out-of-bounds tiles: those writes must be
        // ignored, and a change to that behaviour must show up here.
        grid.set(tile, terrain);
        hasher.write_u8(grid.get(tile) as u8);
        hasher.write_u32(grid.move_cost(tile));
    }
    grid.hash_into(hasher);

    // Spawn, damage, and remove entities so slot reuse order is covered too.
    let mut entities = Entities::new();
    let mut ids = Vec::new();
    for i in 0..200 {
        let team = if i % 3 == 0 {
            Team::Duskwood
        } else {
            Team::Holding
        };
        let kind = if i % 7 == 0 {
            EntityKind::Building
        } else {
            EntityKind::Troop
        };
        let tile = Tile::new(rng.range(0, crate::grid::GRID_SIZE - 1), rng.range(0, 43));
        ids.push(entities.spawn(Entity::new(
            kind,
            team,
            tile.centre(),
            Fx::from_ratio(rng.range(50, 400), 3),
        )));
    }
    for _ in 0..400 {
        let victim = ids[rng.below(ids.len() as u32) as usize];
        if let Some(entity) = entities.get_mut(victim) {
            entity.take_damage(Fx::from_ratio(rng.range(1, 90), 7));
        }
        for id in entities.remove_dead() {
            hasher.write_u32(id.index());
            hasher.write_u32(id.generation());
        }
    }
    entities.hash_into(hasher);

    // Pathfinding, on the board built above. This is the most valuable thing in
    // the whole workload: it is the only part with a priority queue, and a
    // priority queue is exactly where a platform difference in tie ordering would
    // hide. Several goals, some of them on impassable tiles, so the
    // approach-but-do-not-enter rule is covered too.
    let goals = [
        Tile::new(4, 4),
        Tile::new(40, 39),
        Tile::new(21, 22),
        Tile::new(-3, 12), // out of bounds; must be ignored
    ];
    let field = crate::FlowField::towards(&grid, &goals);
    field.hash_into(hasher);

    // Trace a few routes so the walked path, not just the stored field, is
    // covered — the two could disagree if direction selection ever changed.
    for start in [
        Tile::new(0, 0),
        Tile::new(43, 43),
        Tile::new(17, 31),
        Tile::new(30, 2),
    ] {
        for tile in field.trace(start, 512) {
            hasher.write_i32(tile.x);
            hasher.write_i32(tile.y);
        }
    }

    hash_a_whole_battle(hasher);
}

/// Runs an actual battle and folds its state into the hash.
///
/// This is the best workload in the file, because it is the only one that
/// exercises everything at once and in the order the real game uses it:
/// targeting, movement geometry, simultaneous damage, death, and flow fields
/// rebuilt as the board changes. Anything that diverges between two machines
/// almost certainly shows up here first.
///
/// Hashed every tick rather than only at the end — a battle that ends with
/// everyone dead leaves an empty entity list, which hashes the same no matter how
/// it got there.
fn hash_a_whole_battle(hasher: &mut StateHasher) {
    use crate::grid::{Grid, Terrain, Tile};
    use crate::{Battle, Combat, Entity, EntityKind, Team};

    let mut rng = Pcg32::with_stream(0x4475_736b_776f_6f64, 3); // "Duskwood"

    let mut grid = Grid::new();
    for _ in 0..120 {
        grid.set(
            Tile::new(rng.range(0, 43), rng.range(0, 43)),
            if rng.below(2) == 0 {
                Terrain::Rock
            } else {
                Terrain::Mud
            },
        );
    }

    let mut battle = Battle::new(grid, 0x5761_7220);

    for i in 0..24 {
        let attacker = Combat {
            speed: Fx::from_ratio(rng.range(1, 4), 20),
            damage: Fx::from_ratio(rng.range(20, 140), 10),
            range: Fx::from_ratio(rng.range(10, 45), 10),
            cooldown: rng.below(6),
        };
        battle.spawn(
            Entity::new(
                EntityKind::Troop,
                Team::Holding,
                Tile::new(rng.range(0, 20), rng.range(0, 43)).centre(),
                Fx::from_ratio(rng.range(200, 900), 4),
            )
            .with_combat(attacker),
        );

        let defender = Combat {
            speed: Fx::from_ratio(rng.range(1, 4), 20),
            damage: Fx::from_ratio(rng.range(20, 140), 10),
            range: Fx::from_ratio(rng.range(10, 45), 10),
            cooldown: rng.below(6),
        };
        battle.spawn(
            Entity::new(
                if i % 5 == 0 {
                    EntityKind::Building
                } else {
                    EntityKind::Troop
                },
                Team::Duskwood,
                Tile::new(rng.range(24, 43), rng.range(0, 43)).centre(),
                Fx::from_ratio(rng.range(200, 900), 4),
            )
            .with_combat(defender),
        );
    }

    for _ in 0..600 {
        battle.step();
        hasher.write_u64(battle.state_hash());
        if battle.is_over() {
            break;
        }
    }
    hasher.write_u32(battle.tick());
    hasher.write_u64(battle.state_hash());
}

/// Absorbs operations that land exactly on a rounding boundary.
///
/// These are added deliberately. Randomly chosen values almost never produce a
/// result of exactly one half, so a workload built only from them stays green even
/// if the rounding rule changes — which was verified, and is why this exists.
/// Ties are precisely where two independent implementations diverge, so the canary
/// has to cover them explicitly.
fn hash_rounding_boundaries(hasher: &mut StateHasher) {
    // Products whose fractional part is exactly one half, both signs.
    let tiny = Fx::from_bits(1);
    let half_step = Fx::from_bits(1 << (crate::FIXED_POINT_BITS - 1));
    hasher.write_fx(tiny * half_step);
    hasher.write_fx(-tiny * half_step);
    hasher.write_fx(Fx::from_bits(3) * half_step);
    hasher.write_fx(Fx::from_bits(-3) * half_step);

    // Divisions landing exactly on one half, both signs.
    let two = Fx::from_int(2);
    hasher.write_fx(Fx::from_bits(1) / two);
    hasher.write_fx(Fx::from_bits(-1) / two);
    hasher.write_fx(Fx::from_bits(3) / two);
    hasher.write_fx(Fx::from_bits(-3) / two);
    hasher.write_fx(Fx::from_bits(1) / -two);
    hasher.write_fx(Fx::from_bits(-1) / -two);

    // Whole-number conversion at exactly one half, both signs.
    let one_half = Fx::from_ratio(1, 2);
    hasher.write_i32(one_half.round_to_int());
    hasher.write_i32((-one_half).round_to_int());
    hasher.write_i32(one_half.floor_to_int());
    hasher.write_i32((-one_half).floor_to_int());

    // Square roots either side of a perfect square, where the integer root steps.
    hasher.write_fx(Fx::from_bits(Fx::from_int(4).to_bits() - 1).sqrt());
    hasher.write_fx(Fx::from_int(4).sqrt());
    hasher.write_fx(Fx::from_bits(Fx::from_int(4).to_bits() + 1).sqrt());
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The reference result. See the module documentation before changing this.
    ///
    /// Computed on macOS (Apple M4 Pro, aarch64) with rustc 1.95.0 on 8 August
    /// 2026, and verified on x86_64 Linux by CI on the same commit.
    const EXPECTED_HASH: u64 = 0x6de2_77a1_cf08_225b;

    #[test]
    fn the_reference_workload_hashes_to_the_expected_value() {
        assert_eq!(
            reference_workload_hash(),
            EXPECTED_HASH,
            "\nThe simulation produced a different result than the recorded \
             reference.\nIf this was a deliberate change to simulation logic, \
             recompute the constant\nand note in the commit message that recorded \
             battles no longer replay.\nIf it was not deliberate, or if this passes \
             on one platform and fails on\nanother, stop and investigate. See the \
             module documentation."
        );
    }

    #[test]
    fn the_godot_smoke_test_expects_the_same_hash() {
        // game/tools/sim_checks.gd hard-codes this value on purpose: reading it
        // back out of the library would make a stale build agree with itself.
        // The duplication is load-bearing, so this keeps the two in step rather
        // than leaving it to whoever edits one of them.
        let path = concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../../game/tools/sim_checks.gd"
        );
        let source =
            std::fs::read_to_string(path).unwrap_or_else(|e| panic!("cannot read {path}: {e}"));
        let expected = format!("const EXPECTED_HASH := \"{EXPECTED_HASH:#018x}\"");
        assert!(
            source.contains(&expected),
            "game/tools/sim_checks.gd is out of step with EXPECTED_HASH.\n\
             It should contain:\n  {expected}"
        );
    }

    /// Plays `count` seeded battles twice each and checks every pair matches.
    ///
    /// `MASTER_PLAN.md` §9 asks for 10,000 seeded runs. In a debug build that is
    /// about two and a half minutes — the release profile's overflow checks are
    /// most of it — against roughly six seconds in release. Too slow to sit in
    /// every debug run, trivial in release.
    ///
    /// So: a thousand seeds run everywhere in debug on every push and would catch
    /// a regression first, and the full sweep is `#[ignore]`d and run by CI in
    /// release on the Linux leg. The slow one is the contract; the fast one is
    /// the early warning.
    fn seeded_battles_replay_identically(count: u64, distinct_floor: usize) {
        use crate::grid::{Grid, Terrain, Tile};
        use crate::{Battle, Combat, Entity, EntityKind, Team};

        fn play(seed: u64) -> u64 {
            let mut rng = Pcg32::new(seed);
            let mut grid = Grid::new();
            for _ in 0..12 {
                grid.set(Tile::new(rng.range(0, 43), rng.range(0, 43)), Terrain::Rock);
            }
            let mut battle = Battle::new(grid, seed);
            for i in 0..4 {
                for team in [Team::Holding, Team::Duskwood] {
                    let combat = Combat {
                        speed: Fx::from_ratio(rng.range(1, 5), 20),
                        damage: Fx::from_ratio(rng.range(10, 90), 10),
                        range: Fx::from_ratio(rng.range(10, 40), 10),
                        cooldown: rng.below(5),
                    };
                    battle.spawn(
                        Entity::new(
                            EntityKind::Troop,
                            team,
                            Tile::new(rng.range(0, 43), rng.range(0, 43)).centre(),
                            Fx::from_ratio(rng.range(80, 400), 4),
                        )
                        .with_combat(combat),
                    );
                    let _ = i;
                }
            }
            battle.run(120);
            battle.state_hash()
        }

        let mut distinct = std::collections::HashSet::new();
        for seed in 0..count {
            let first = play(seed);
            let second = play(seed);
            assert_eq!(first, second, "seed {seed} did not replay identically");
            distinct.insert(first);
        }

        // Different seeds must mostly produce different battles. Without this a
        // simulation that ignored its inputs entirely would pass the loop above
        // with flying colours.
        assert!(
            distinct.len() > distinct_floor,
            "only {} distinct outcomes from {count} seeds — is the seed being used?",
            distinct.len()
        );
    }

    #[test]
    fn a_thousand_seeded_battles_each_replay_identically() {
        seeded_battles_replay_identically(1_000, 900);
    }

    /// The full `MASTER_PLAN.md` §9 sweep. Run it in **release**, where it takes
    /// about six seconds rather than two and a half minutes:
    ///
    /// ```text
    /// cargo test -p sim-core --release -- --ignored
    /// ```
    ///
    /// CI runs exactly that on the Linux leg.
    #[test]
    #[ignore = "slow in debug — run with --release; CI does so on the Linux leg"]
    fn ten_thousand_seeded_battles_each_replay_identically() {
        seeded_battles_replay_identically(10_000, 9_000);
    }

    #[test]
    fn the_workload_is_stable_within_a_single_run() {
        // Guards against accidental hidden state — a static, a lazily initialised
        // table, anything that would make the second call differ from the first.
        assert_eq!(reference_workload_hash(), reference_workload_hash());
    }

    #[test]
    fn the_workload_actually_depends_on_the_arithmetic() {
        // A hash that ignored its inputs would pass the test above forever. This
        // confirms the workload is genuinely wired to the values it hashes.
        let mut hasher = StateHasher::new();
        hasher.write_fx(Fx::ONE);
        assert_ne!(hasher.finish(), reference_workload_hash());
    }
}
