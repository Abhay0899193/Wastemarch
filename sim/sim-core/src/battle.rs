//! A running battle: the tick loop that ties everything else together.
//!
//! # The order of a tick is part of the simulation
//!
//! Every tick does the same five things in the same order:
//!
//! 1. Rebuild the flow fields, if the board changed since last tick.
//! 2. Acquire targets for anything that has none, or whose target has died.
//! 3. Move anything that is out of range of its target.
//! 4. Attack, for anything in range with its cooldown expired.
//! 5. Remove the dead.
//!
//! Swapping any two of those changes the outcome. Moving before targeting, for
//! instance, means a unit chases where its enemy *was*. So the order is fixed and
//! a change to it is a change to the game, not a refactor.
//!
//! # A unit that dies this tick still lands its blow
//!
//! Attackers are deliberately **not** checked for being alive when attacks
//! resolve. Everything that was alive at the start of the tick swings, and the
//! dead are cleared at the end. Two units that kill each other therefore both
//! die, rather than the lower-numbered one winning by being earlier in the list.
//!
//! That is the honest reading of a fixed timestep, and it removes slot order as a
//! source of asymmetry. **Adding an `is_alive` check to the attacker would change
//! the game**, not tidy it — `two_units_can_kill_each_other_on_the_same_tick`
//! pins the behaviour.
//!
//! An earlier version gathered damage and applied it afterwards, believing that
//! was what produced simultaneity. It was not: with no alive check on the
//! attacker the two are identical, which a perturbation test demonstrated. The
//! buffer was removed — it allocated every tick for nothing, and
//! `MASTER_PLAN.md` §5 wants zero allocation mid-battle.

use crate::entity::{Entities, Entity, EntityId, EntityKind, Team};
use crate::grid::{Grid, Tile};
use crate::pathfind::{Direction, FlowField};
use crate::{Fx, Pcg32, Point, StateHasher};

/// One running battle.
pub struct Battle {
    pub grid: Grid,
    pub entities: Entities,
    rng: Pcg32,
    tick: u32,
    /// Flow field leading each team to its enemies. Index by [`Team`] as `usize`.
    fields: [Option<FlowField>; 2],
    /// Set when the board changes in a way that invalidates the fields.
    fields_dirty: bool,
}

impl Battle {
    /// A new battle on a board, from a seed.
    ///
    /// The seed is the whole of the battle's randomness and belongs in the battle
    /// record. Same seed and same inputs, same battle, on any machine.
    pub fn new(grid: Grid, seed: u64) -> Battle {
        Battle {
            grid,
            entities: Entities::new(),
            rng: Pcg32::new(seed),
            tick: 0,
            fields: [None, None],
            fields_dirty: true,
        }
    }

    /// Ticks elapsed. At [`TICKS_PER_SECOND`](crate::TICKS_PER_SECOND) per second.
    #[inline]
    pub fn tick(&self) -> u32 {
        self.tick
    }

    /// Adds an entity to the battle.
    pub fn spawn(&mut self, entity: Entity) -> EntityId {
        // A building changes what can be walked through, and any spawn changes
        // what there is to path towards.
        if entity.kind == EntityKind::Building {
            self.grid.set(entity.position.tile(), crate::Terrain::Built);
        }
        self.fields_dirty = true;
        self.entities.spawn(entity)
    }

    /// Whether the battle is over: one side has nothing left.
    pub fn is_over(&self) -> bool {
        let mut holding = false;
        let mut duskwood = false;
        for (_, entity) in self.entities.iter() {
            match entity.team {
                Team::Holding => holding = true,
                Team::Duskwood => duskwood = true,
            }
        }
        !(holding && duskwood)
    }

    /// Advances the battle by exactly one tick.
    ///
    /// See the module documentation: the order of the phases below is part of the
    /// simulation, not an implementation detail.
    pub fn step(&mut self) {
        self.tick += 1;

        self.rebuild_fields_if_needed();
        self.acquire_targets();
        self.move_units();
        self.resolve_attacks();

        if !self.entities.remove_dead().is_empty() {
            self.fields_dirty = true;
        }
    }

    /// Runs until the battle ends or `max_ticks` pass.
    ///
    /// The cap is a guard, not a rule: a stalemate — two sides that cannot reach
    /// each other — would otherwise run forever. Returns the ticks actually run.
    pub fn run(&mut self, max_ticks: u32) -> u32 {
        let start = self.tick;
        while self.tick - start < max_ticks && !self.is_over() {
            self.step();
        }
        self.tick - start
    }

    fn rebuild_fields_if_needed(&mut self) {
        if !self.fields_dirty {
            return;
        }
        for team in [Team::Holding, Team::Duskwood] {
            // Goals are the enemy's positions, collected in slot order so the
            // goal list itself is deterministic.
            let goals: Vec<Tile> = self
                .entities
                .iter()
                .filter(|(_, e)| e.team != team)
                .map(|(_, e)| e.position.tile())
                .collect();
            self.fields[team as usize] = if goals.is_empty() {
                None
            } else {
                Some(FlowField::towards(&self.grid, &goals))
            };
        }
        self.fields_dirty = false;
    }

    /// Picks a target for anything without a live one.
    ///
    /// Nearest enemy by squared distance, ties broken by [`EntityId`]. Squared
    /// rather than true distance because it avoids a square root and, more
    /// importantly, avoids the rounding a square root introduces — comparisons on
    /// exact values cannot produce ties that resolve differently.
    fn acquire_targets(&mut self) {
        let ids = self.entities.ids();
        for id in &ids {
            let Some(entity) = self.entities.get(*id) else {
                continue;
            };
            // Buildings do not seek. A defensive tower gets a non-zero range and
            // range checking below handles it.
            if entity.combat.damage == Fx::ZERO {
                continue;
            }
            let still_valid = entity
                .target
                .is_some_and(|t| self.entities.get(t).is_some_and(|e| e.is_alive()));
            if still_valid {
                continue;
            }

            let position = entity.position;
            let team = entity.team;
            let mut best: Option<(Fx, EntityId)> = None;
            for (candidate_id, candidate) in self.entities.iter() {
                if candidate.team == team || !candidate.is_alive() {
                    continue;
                }
                let distance = position.distance_squared(candidate.position);
                // Strictly less, so an equal distance leaves the earlier
                // candidate in place. Iteration is in slot order, so that is
                // the lower EntityId — deterministic, and independent of how the
                // list happens to be laid out.
                let better = match best {
                    None => true,
                    Some((best_distance, _)) => distance < best_distance,
                };
                if better {
                    best = Some((distance, candidate_id));
                }
            }

            if let Some(entity) = self.entities.get_mut(*id) {
                entity.target = best.map(|(_, id)| id);
            }
        }
    }

    /// Moves everything that has somewhere to be.
    // ponytail: each phase calls entities.ids(), which allocates a Vec per tick —
    // three allocations a tick against MASTER_PLAN.md §5's "zero allocation
    // mid-battle". Harmless at Phase 1 scale and premature to fix before there is
    // anything to profile. Replace with a reusable buffer on Battle when Phase 4
    // measures it.
    fn move_units(&mut self) {
        let ids = self.entities.ids();
        for id in &ids {
            let Some(entity) = self.entities.get(*id) else {
                continue;
            };
            if entity.combat.speed == Fx::ZERO || entity.kind == EntityKind::Building {
                continue;
            }
            let Some(target_id) = entity.target else {
                continue;
            };
            let Some(target) = self.entities.get(target_id) else {
                continue;
            };

            // Already close enough — stand and fight rather than shuffling.
            let range = entity.combat.range;
            if entity.position.distance_squared(target.position) <= range * range {
                continue;
            }

            let Some(field) = self.fields[entity.team as usize].as_ref() else {
                continue;
            };
            let current_tile = entity.position.tile();
            let direction = field.direction_at(current_tile);
            if direction == Direction::None {
                continue;
            }

            let destination = direction.step_from(current_tile).centre();
            let moved = step_towards(entity.position, destination, entity.combat.speed);
            if let Some(entity) = self.entities.get_mut(*id) {
                entity.position = moved;
            }
        }
    }

    /// Applies every attack that lands this tick.
    ///
    /// Attackers are not alive-checked, on purpose — see the module
    /// documentation. Everything alive at the start of the tick swings.
    fn resolve_attacks(&mut self) {
        let ids = self.entities.ids();

        for id in &ids {
            let Some(entity) = self.entities.get(*id) else {
                continue;
            };
            if entity.cooldown_remaining > 0 || entity.combat.damage == Fx::ZERO {
                continue;
            }
            let Some(target_id) = entity.target else {
                continue;
            };
            let Some(target) = self.entities.get(target_id) else {
                continue;
            };
            let range = entity.combat.range;
            if entity.position.distance_squared(target.position) > range * range {
                continue;
            }
            let damage = entity.combat.damage;
            if let Some(entity) = self.entities.get_mut(*id) {
                entity.cooldown_remaining = entity.combat.cooldown;
            }
            if let Some(target) = self.entities.get_mut(target_id) {
                target.take_damage(damage);
            }
        }

        // Cooldowns tick down after attacks, so a cooldown of 1 means "every
        // other tick" rather than "every tick".
        for id in &ids {
            if let Some(entity) = self.entities.get_mut(*id)
                && entity.cooldown_remaining > 0
            {
                entity.cooldown_remaining -= 1;
            }
        }
    }

    /// A hash of the entire battle state.
    ///
    /// This is the number two machines compare. If it matches after the same
    /// number of ticks from the same seed, they ran the same battle.
    pub fn state_hash(&self) -> u64 {
        let mut hasher = StateHasher::new();
        hasher.write_u32(self.tick);
        self.grid.hash_into(&mut hasher);
        self.entities.hash_into(&mut hasher);
        hasher.finish()
    }

    /// The generator, for systems that need randomness inside the simulation.
    ///
    /// Anything drawing from this changes the battle, so nothing outside the
    /// simulation may touch it.
    #[inline]
    pub fn rng(&mut self) -> &mut Pcg32 {
        &mut self.rng
    }
}

/// Moves `from` toward `to` by at most `distance`, never overshooting.
///
/// Kept free-standing and small because it is the only place in the tick loop
/// doing geometry, and it is the easiest place for a rounding difference to
/// creep in.
fn step_towards(from: Point, to: Point, distance: Fx) -> Point {
    let dx = to.x - from.x;
    let dy = to.y - from.y;
    let span_squared = dx * dx + dy * dy;
    if span_squared == Fx::ZERO {
        return to;
    }
    let span = span_squared.sqrt();
    if span <= distance {
        return to;
    }
    let scale = distance / span;
    Point::new(from.x + dx * scale, from.y + dy * scale)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::entity::Combat;

    fn soldier() -> Combat {
        Combat {
            speed: Fx::from_ratio(1, 10), // 2 metres a second at 20 ticks
            damage: Fx::from_int(10),
            range: Fx::from_int(1),
            cooldown: 4,
        }
    }

    fn troop(team: Team, x: i32, y: i32, health: i32) -> Entity {
        Entity::new(
            EntityKind::Troop,
            team,
            Tile::new(x, y).centre(),
            Fx::from_int(health),
        )
        .with_combat(soldier())
    }

    fn wall(team: Team, x: i32, y: i32, health: i32) -> Entity {
        Entity::new(
            EntityKind::Building,
            team,
            Tile::new(x, y).centre(),
            Fx::from_int(health),
        )
    }

    #[test]
    fn a_tick_advances_the_counter() {
        let mut battle = Battle::new(Grid::new(), 1);
        assert_eq!(battle.tick(), 0);
        battle.step();
        assert_eq!(battle.tick(), 1);
    }

    #[test]
    fn a_unit_picks_the_nearest_enemy() {
        let mut battle = Battle::new(Grid::new(), 1);
        let hero = battle.spawn(troop(Team::Holding, 0, 0, 100));
        let far = battle.spawn(troop(Team::Duskwood, 20, 0, 100));
        let near = battle.spawn(troop(Team::Duskwood, 5, 0, 100));

        battle.step();
        assert_eq!(battle.entities.get(hero).unwrap().target, Some(near));
        assert_ne!(battle.entities.get(hero).unwrap().target, Some(far));
    }

    #[test]
    fn equal_distance_targets_resolve_to_the_lower_id() {
        // Arbitrary, but it must be consistently arbitrary or two machines pick
        // different targets and the battle forks.
        let mut battle = Battle::new(Grid::new(), 1);
        let hero = battle.spawn(troop(Team::Holding, 10, 10, 100));
        let first = battle.spawn(troop(Team::Duskwood, 10, 5, 100));
        let second = battle.spawn(troop(Team::Duskwood, 10, 15, 100));

        battle.step();
        let chosen = battle.entities.get(hero).unwrap().target.unwrap();
        assert_eq!(chosen, first);
        assert!(first < second);
    }

    #[test]
    fn a_unit_walks_toward_its_target() {
        let mut battle = Battle::new(Grid::new(), 1);
        let hero = battle.spawn(troop(Team::Holding, 0, 0, 100));
        battle.spawn(troop(Team::Duskwood, 10, 0, 100));

        let start = battle.entities.get(hero).unwrap().position;
        for _ in 0..10 {
            battle.step();
        }
        let now = battle.entities.get(hero).unwrap().position;
        assert!(now.x > start.x, "did not move east: {start:?} -> {now:?}");
    }

    #[test]
    fn a_unit_stops_once_in_range() {
        let mut battle = Battle::new(Grid::new(), 1);
        let hero = battle.spawn(troop(Team::Holding, 0, 0, 100));
        // A building, not a troop: a troop would fight back and kill a
        // 100-health hero long before the walk finished.
        battle.spawn(wall(Team::Duskwood, 4, 0, 100_000));

        battle.run(400);
        let hero_position = battle.entities.get(hero).unwrap().position;
        let target_position = Tile::new(4, 0).centre();
        let gap = hero_position.distance(target_position);
        // Within range, and not on top of it.
        assert!(gap <= Fx::from_int(1), "closed to {gap}");
        assert!(gap > Fx::ZERO, "walked into the target");
    }

    #[test]
    fn attacks_land_and_kill() {
        let mut battle = Battle::new(Grid::new(), 1);
        battle.spawn(troop(Team::Holding, 0, 0, 100));
        let victim = battle.spawn(troop(Team::Duskwood, 1, 0, 30));

        battle.run(200);
        assert!(battle.entities.get(victim).is_none(), "victim survived");
        assert!(battle.is_over());
    }

    #[test]
    fn the_cooldown_paces_attacks() {
        // `cooldown: 4` means four ticks BETWEEN attacks, so blows land on ticks
        // 1, 5, 9, 13 and 17 — five of them in twenty ticks, for 50 damage. Not
        // 200, which is what no cooldown would give.
        let mut battle = Battle::new(Grid::new(), 1);
        battle.spawn(troop(Team::Holding, 0, 0, 100));
        let victim = battle.spawn(wall(Team::Duskwood, 1, 0, 10_000));

        for _ in 0..20 {
            battle.step();
        }
        let health = battle.entities.get(victim).unwrap().health;
        let dealt = Fx::from_int(10_000) - health;
        assert_eq!(dealt, Fx::from_int(50), "dealt {dealt} over 20 ticks");
    }

    #[test]
    fn cooldown_zero_attacks_every_tick() {
        // The other end of the same rule, so the meaning of `cooldown` is pinned
        // from both sides.
        let mut battle = Battle::new(Grid::new(), 1);
        let mut fast = soldier();
        fast.cooldown = 0;
        battle.spawn(
            Entity::new(
                EntityKind::Troop,
                Team::Holding,
                Tile::new(0, 0).centre(),
                Fx::from_int(100),
            )
            .with_combat(fast),
        );
        let victim = battle.spawn(wall(Team::Duskwood, 1, 0, 10_000));

        for _ in 0..20 {
            battle.step();
        }
        let dealt = Fx::from_int(10_000) - battle.entities.get(victim).unwrap().health;
        assert_eq!(dealt, Fx::from_int(200));
    }

    #[test]
    fn two_units_can_kill_each_other_on_the_same_tick() {
        // Pins the rule in the module documentation. If someone adds an
        // `is_alive` check to the attacker in resolve_attacks, the lower-numbered
        // unit starts winning every mutual kill and this fails.
        let mut battle = Battle::new(Grid::new(), 1);
        let a = battle.spawn(troop(Team::Holding, 0, 0, 10));
        let b = battle.spawn(troop(Team::Duskwood, 1, 0, 10));

        battle.step();
        assert!(battle.entities.get(a).is_none(), "a survived");
        assert!(battle.entities.get(b).is_none(), "b survived");
    }

    #[test]
    fn a_unit_killed_this_tick_still_deals_its_damage() {
        // The same rule from the other side, with unequal numbers so it cannot
        // pass by symmetry: the weaker unit dies but still lands its blow.
        let mut battle = Battle::new(Grid::new(), 1);
        let strong = battle.spawn(troop(Team::Holding, 0, 0, 100));
        let doomed = battle.spawn(troop(Team::Duskwood, 1, 0, 5));

        battle.step();
        assert!(battle.entities.get(doomed).is_none(), "doomed survived");
        let strong_health = battle.entities.get(strong).unwrap().health;
        assert_eq!(
            strong_health,
            Fx::from_int(90),
            "the dying unit's blow did not land"
        );
    }

    #[test]
    fn a_building_does_not_move_or_seek() {
        let mut battle = Battle::new(Grid::new(), 1);
        let tower = battle.spawn(wall(Team::Holding, 5, 5, 500));
        battle.spawn(troop(Team::Duskwood, 30, 30, 100));

        let start = battle.entities.get(tower).unwrap().position;
        battle.run(50);
        assert_eq!(battle.entities.get(tower).unwrap().position, start);
        assert_eq!(battle.entities.get(tower).unwrap().target, None);
    }

    #[test]
    fn a_target_that_dies_is_replaced() {
        let mut battle = Battle::new(Grid::new(), 1);
        let hero = battle.spawn(troop(Team::Holding, 0, 0, 10_000));
        let first = battle.spawn(troop(Team::Duskwood, 1, 0, 10));
        let second = battle.spawn(troop(Team::Duskwood, 3, 0, 10_000));

        battle.step();
        assert_eq!(battle.entities.get(hero).unwrap().target, Some(first));

        battle.run(60);
        assert!(battle.entities.get(first).is_none());
        assert_eq!(battle.entities.get(hero).unwrap().target, Some(second));
    }

    #[test]
    fn a_battle_ends_when_one_side_is_gone() {
        let mut battle = Battle::new(Grid::new(), 1);
        assert!(battle.is_over(), "empty battle is over");
        battle.spawn(troop(Team::Holding, 0, 0, 100));
        assert!(battle.is_over(), "one-sided battle is over");
        battle.spawn(troop(Team::Duskwood, 1, 0, 10));
        assert!(!battle.is_over());

        let ticks = battle.run(500);
        assert!(battle.is_over());
        assert!(ticks < 500, "took the full cap: {ticks}");
    }

    #[test]
    fn a_stalemate_stops_at_the_cap_instead_of_hanging() {
        // Two sides walled apart. Without the cap this runs forever.
        let mut grid = Grid::new();
        for y in 0..crate::grid::GRID_SIZE {
            grid.set(Tile::new(20, y), crate::Terrain::Rock);
        }
        let mut battle = Battle::new(grid, 1);
        battle.spawn(troop(Team::Holding, 5, 5, 100));
        battle.spawn(troop(Team::Duskwood, 35, 35, 100));

        assert_eq!(battle.run(100), 100);
        assert!(!battle.is_over());
    }

    #[test]
    fn the_same_seed_and_setup_replays_identically() {
        // The property the whole architecture exists for, at battle level.
        fn play() -> u64 {
            let mut battle = Battle::new(Grid::new(), 0xC0FFEE);
            for i in 0..12 {
                battle.spawn(troop(Team::Holding, i, 0, 60 + i * 3));
                battle.spawn(troop(Team::Duskwood, i, 12, 60 + i * 2));
            }
            battle.run(300);
            battle.state_hash()
        }
        assert_eq!(play(), play());
    }

    #[test]
    fn spawn_order_changes_the_outcome_and_that_is_expected() {
        // Not a flaw — slot order decides equal-distance ties, so two different
        // setups are two different battles. Recorded here so nobody later
        // "fixes" it into sorting entities and silently changes every replay.
        //
        // Hashed part-way through, NOT at the end. Once everyone is dead the
        // entity list is empty and hashes the same either way, which is the one
        // moment the difference is invisible — an earlier version of this test
        // compared final states and passed for that reason.
        fn play(reversed: bool) -> u64 {
            let mut battle = Battle::new(Grid::new(), 7);
            let positions: Vec<i32> = if reversed {
                (0..6).rev().collect()
            } else {
                (0..6).collect()
            };
            for i in positions {
                battle.spawn(troop(Team::Holding, i, 0, 50));
                battle.spawn(troop(Team::Duskwood, i, 6, 50));
            }
            battle.run(20);
            assert!(!battle.is_over(), "hashed too late — the fight is finished");
            battle.state_hash()
        }
        assert_ne!(play(false), play(true));
    }

    #[test]
    fn stepping_never_produces_a_position_outside_the_world() {
        let mut battle = Battle::new(Grid::new(), 99);
        battle.spawn(troop(Team::Holding, 0, 0, 10_000));
        battle.spawn(troop(Team::Duskwood, 43, 43, 10_000));
        battle.run(1_000);

        for (_, entity) in battle.entities.iter() {
            let tile = entity.position.tile();
            assert!(tile.in_bounds(), "{tile:?} left the world");
        }
    }

    #[test]
    fn step_towards_never_overshoots() {
        let from = Point::new(Fx::ZERO, Fx::ZERO);
        let to = Point::new(Fx::from_int(3), Fx::from_int(4)); // exactly 5 away

        // A step longer than the gap lands exactly on the destination.
        assert_eq!(step_towards(from, to, Fx::from_int(9)), to);
        assert_eq!(step_towards(from, to, Fx::from_int(5)), to);

        // A shorter step covers roughly that much and no more.
        let partial = step_towards(from, to, Fx::from_int(1));
        let covered = from.distance(partial);
        assert!(covered <= Fx::from_int(1) + Fx::from_bits(4), "{covered}");
        assert!(covered >= Fx::from_int(1) - Fx::from_bits(4), "{covered}");
    }

    #[test]
    fn step_towards_handles_a_zero_length_move() {
        // Guards a divide by zero: without the early return this panics.
        let point = Point::new(Fx::from_int(2), Fx::from_int(2));
        assert_eq!(step_towards(point, point, Fx::from_int(1)), point);
    }
}
