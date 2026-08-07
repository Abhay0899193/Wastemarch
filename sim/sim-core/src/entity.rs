//! Units and buildings, and the storage that holds them.
//!
//! # Why identifiers carry a generation
//!
//! Entities are stored in a dense `Vec` and their slots are reused when something
//! dies. A plain index would then be ambiguous: an archer dies, a new soldier
//! takes slot 7, and anything still holding "slot 7" now silently points at the
//! soldier. Attacks would land on the wrong unit, and only sometimes.
//!
//! So an [`EntityId`] is a slot **plus a generation**, and the generation
//! increases every time a slot is reused. A stale id fails to resolve instead of
//! resolving to the wrong thing.
//!
//! # Why not a hash map
//!
//! Because iterating one is not deterministic. Rust's `HashMap` deliberately
//! randomises its ordering, so two machines would process units in different
//! orders and diverge on the first tie. **Never put simulation state in a
//! `HashMap`.** Dense storage, iterated in index order, always.

use crate::{Fx, Point, StateHasher};

/// Which side an entity belongs to.
#[derive(Clone, Copy, PartialEq, Eq, Debug, Hash)]
#[repr(u8)]
pub enum Team {
    /// The player's holding.
    Holding = 0,
    /// Whatever came out of the Duskwood.
    Duskwood = 1,
}

/// What an entity is.
#[derive(Clone, Copy, PartialEq, Eq, Debug, Hash)]
#[repr(u8)]
pub enum EntityKind {
    /// Moves, attacks, can be killed.
    Troop = 0,
    /// Does not move. Occupies tiles.
    Building = 1,
}

/// A handle to an entity.
///
/// Copyable and small, so it can be stored freely — but it is only meaningful
/// alongside the [`Entities`] it came from, and only until that entity dies.
#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Debug, Hash)]
pub struct EntityId {
    index: u32,
    generation: u32,
}

impl EntityId {
    /// The slot this id refers to. For storage internals and debugging.
    #[inline]
    pub const fn index(self) -> u32 {
        self.index
    }

    /// How many times the slot had been reused when this id was issued.
    #[inline]
    pub const fn generation(self) -> u32 {
        self.generation
    }
}

/// A unit or building in the world.
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct Entity {
    pub kind: EntityKind,
    pub team: Team,
    pub position: Point,
    pub health: Fx,
    pub max_health: Fx,
}

impl Entity {
    /// A new entity at full health.
    pub fn new(kind: EntityKind, team: Team, position: Point, max_health: Fx) -> Entity {
        Entity {
            kind,
            team,
            position,
            health: max_health,
            max_health,
        }
    }

    /// Whether this entity still counts as alive.
    #[inline]
    pub fn is_alive(&self) -> bool {
        self.health > Fx::ZERO
    }

    /// Applies damage, never dropping below zero.
    ///
    /// Clamped rather than allowed to go negative so that "how dead is it" cannot
    /// vary — two units landing a killing blow in different orders must leave the
    /// same state behind.
    pub fn take_damage(&mut self, amount: Fx) {
        self.health = (self.health - amount).max(Fx::ZERO);
    }

    fn hash_into(&self, hasher: &mut StateHasher) {
        hasher.write_u8(self.kind as u8);
        hasher.write_u8(self.team as u8);
        hasher.write_fx(self.position.x);
        hasher.write_fx(self.position.y);
        hasher.write_fx(self.health);
        hasher.write_fx(self.max_health);
    }
}

/// One storage slot: either occupied, or free and waiting to be reused.
#[derive(Clone, PartialEq, Eq, Debug)]
struct Slot {
    generation: u32,
    entity: Option<Entity>,
}

/// All entities in a battle.
///
/// Iteration is always in slot order, so every machine processes units in the
/// same sequence.
#[derive(Clone, PartialEq, Eq, Debug, Default)]
pub struct Entities {
    slots: Vec<Slot>,
    /// Slots free for reuse. Used as a stack, so the ordering is deterministic.
    free: Vec<u32>,
    alive: u32,
}

impl Entities {
    pub fn new() -> Entities {
        Entities::default()
    }

    /// How many entities are alive.
    #[inline]
    pub fn len(&self) -> usize {
        self.alive as usize
    }

    #[inline]
    pub fn is_empty(&self) -> bool {
        self.alive == 0
    }

    /// Adds an entity and returns its id.
    pub fn spawn(&mut self, entity: Entity) -> EntityId {
        match self.free.pop() {
            Some(index) => {
                let slot = &mut self.slots[index as usize];
                // Bumping the generation is what invalidates every id that
                // referred to whatever used to live here.
                slot.generation += 1;
                slot.entity = Some(entity);
                self.alive += 1;
                EntityId {
                    index,
                    generation: slot.generation,
                }
            }
            None => {
                let index = self.slots.len() as u32;
                self.slots.push(Slot {
                    generation: 0,
                    entity: Some(entity),
                });
                self.alive += 1;
                EntityId {
                    index,
                    generation: 0,
                }
            }
        }
    }

    /// Removes an entity. Returns whether it was there to remove.
    pub fn despawn(&mut self, id: EntityId) -> bool {
        if !self.contains(id) {
            return false;
        }
        self.slots[id.index as usize].entity = None;
        self.free.push(id.index);
        self.alive -= 1;
        true
    }

    /// Whether this id still refers to a live entity.
    #[inline]
    pub fn contains(&self, id: EntityId) -> bool {
        self.slots
            .get(id.index as usize)
            .is_some_and(|slot| slot.generation == id.generation && slot.entity.is_some())
    }

    /// The entity for an id, or `None` if it has died or the id is stale.
    #[inline]
    pub fn get(&self, id: EntityId) -> Option<&Entity> {
        let slot = self.slots.get(id.index as usize)?;
        if slot.generation != id.generation {
            return None;
        }
        slot.entity.as_ref()
    }

    /// Mutable access to an entity.
    #[inline]
    pub fn get_mut(&mut self, id: EntityId) -> Option<&mut Entity> {
        let slot = self.slots.get_mut(id.index as usize)?;
        if slot.generation != id.generation {
            return None;
        }
        slot.entity.as_mut()
    }

    /// Every live entity with its id, in slot order.
    pub fn iter(&self) -> impl Iterator<Item = (EntityId, &Entity)> + '_ {
        self.slots.iter().enumerate().filter_map(|(i, slot)| {
            slot.entity.as_ref().map(|e| {
                (
                    EntityId {
                        index: i as u32,
                        generation: slot.generation,
                    },
                    e,
                )
            })
        })
    }

    /// The ids of every live entity, in slot order.
    pub fn ids(&self) -> Vec<EntityId> {
        self.iter().map(|(id, _)| id).collect()
    }

    /// Removes everything whose health has reached zero, returning their ids in
    /// slot order.
    pub fn remove_dead(&mut self) -> Vec<EntityId> {
        let dead: Vec<EntityId> = self
            .iter()
            .filter(|(_, e)| !e.is_alive())
            .map(|(id, _)| id)
            .collect();
        for id in &dead {
            self.despawn(*id);
        }
        dead
    }

    /// Absorbs every entity into a state hash, in slot order.
    ///
    /// Empty slots are hashed too, as a marker byte. Two worlds holding the same
    /// units in different slots are genuinely different states — the next spawn
    /// would land somewhere else — so they must not hash alike.
    pub fn hash_into(&self, hasher: &mut StateHasher) {
        hasher.write_u32(self.alive);
        for slot in &self.slots {
            hasher.write_u32(slot.generation);
            match &slot.entity {
                Some(entity) => {
                    hasher.write_u8(1);
                    entity.hash_into(hasher);
                }
                None => hasher.write_u8(0),
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn troop_at(x: i32, y: i32) -> Entity {
        Entity::new(
            EntityKind::Troop,
            Team::Holding,
            Point::new(Fx::from_int(x), Fx::from_int(y)),
            Fx::from_int(100),
        )
    }

    #[test]
    fn spawn_and_read_back() {
        let mut entities = Entities::new();
        assert!(entities.is_empty());

        let id = entities.spawn(troop_at(3, 4));
        assert_eq!(entities.len(), 1);
        let entity = entities.get(id).expect("just spawned");
        assert_eq!(entity.position.x, Fx::from_int(3));
        assert_eq!(entity.health, Fx::from_int(100));
    }

    #[test]
    fn despawn_removes_it() {
        let mut entities = Entities::new();
        let id = entities.spawn(troop_at(0, 0));
        assert!(entities.despawn(id));
        assert!(entities.is_empty());
        assert!(entities.get(id).is_none());
        assert!(!entities.contains(id));
        // Despawning twice is not an error, it just does nothing.
        assert!(!entities.despawn(id));
    }

    #[test]
    fn a_stale_id_does_not_resolve_to_the_slots_new_occupant() {
        // The bug generational ids exist to prevent. Without the generation, the
        // final assertion would hand back the second unit.
        let mut entities = Entities::new();
        let first = entities.spawn(troop_at(1, 1));
        entities.despawn(first);

        let second = entities.spawn(troop_at(9, 9));
        assert_eq!(second.index(), first.index(), "slot should be reused");
        assert_ne!(second.generation(), first.generation());

        assert!(entities.get(first).is_none(), "stale id must not resolve");
        assert_eq!(
            entities.get(second).expect("live").position.x,
            Fx::from_int(9)
        );
    }

    #[test]
    fn mutation_through_an_id() {
        let mut entities = Entities::new();
        let id = entities.spawn(troop_at(0, 0));
        entities
            .get_mut(id)
            .expect("live")
            .take_damage(Fx::from_int(30));
        assert_eq!(entities.get(id).expect("live").health, Fx::from_int(70));
    }

    #[test]
    fn damage_stops_at_zero() {
        let mut entity = troop_at(0, 0);
        entity.take_damage(Fx::from_int(150));
        assert_eq!(entity.health, Fx::ZERO);
        assert!(!entity.is_alive());

        // Overkill twice must land in the same place as overkill once, or the
        // order two attackers resolve in would change the stored state.
        let mut other = troop_at(0, 0);
        other.take_damage(Fx::from_int(100));
        other.take_damage(Fx::from_int(100));
        assert_eq!(other.health, entity.health);
    }

    #[test]
    fn an_entity_on_exactly_zero_is_dead() {
        let mut entity = troop_at(0, 0);
        assert!(entity.is_alive());
        entity.take_damage(Fx::from_int(100));
        assert_eq!(entity.health, Fx::ZERO);
        assert!(!entity.is_alive());
    }

    #[test]
    fn iteration_is_in_slot_order_and_repeatable() {
        let mut entities = Entities::new();
        let ids: Vec<EntityId> = (0..5).map(|i| entities.spawn(troop_at(i, 0))).collect();

        let first: Vec<EntityId> = entities.ids();
        let second: Vec<EntityId> = entities.ids();
        assert_eq!(first, second);
        assert_eq!(first, ids);
    }

    #[test]
    fn iteration_skips_holes_and_stays_ordered() {
        let mut entities = Entities::new();
        let ids: Vec<EntityId> = (0..5).map(|i| entities.spawn(troop_at(i, 0))).collect();
        entities.despawn(ids[1]);
        entities.despawn(ids[3]);

        let remaining: Vec<u32> = entities.ids().iter().map(|id| id.index()).collect();
        assert_eq!(remaining, vec![0, 2, 4]);
    }

    #[test]
    fn remove_dead_takes_exactly_the_dead() {
        let mut entities = Entities::new();
        let ids: Vec<EntityId> = (0..4).map(|i| entities.spawn(troop_at(i, 0))).collect();
        entities
            .get_mut(ids[1])
            .expect("live")
            .take_damage(Fx::from_int(100));
        entities
            .get_mut(ids[2])
            .expect("live")
            .take_damage(Fx::from_int(100));

        let removed = entities.remove_dead();
        assert_eq!(removed, vec![ids[1], ids[2]]);
        assert_eq!(entities.len(), 2);
        assert!(entities.contains(ids[0]));
        assert!(entities.contains(ids[3]));
    }

    #[test]
    fn slot_reuse_order_is_deterministic() {
        // Two runs of identical operations must reuse slots identically, or the
        // hash diverges even though the same units are alive.
        fn run() -> Vec<u32> {
            let mut entities = Entities::new();
            let ids: Vec<EntityId> = (0..6).map(|i| entities.spawn(troop_at(i, 0))).collect();
            entities.despawn(ids[4]);
            entities.despawn(ids[0]);
            entities.despawn(ids[2]);
            (0..3)
                .map(|i| entities.spawn(troop_at(i, 9)).index())
                .collect()
        }
        assert_eq!(run(), run());
    }

    #[test]
    fn hashing_reflects_state_changes() {
        let mut entities = Entities::new();
        let id = entities.spawn(troop_at(1, 1));

        let mut before = StateHasher::new();
        entities.hash_into(&mut before);

        entities
            .get_mut(id)
            .expect("live")
            .take_damage(Fx::from_int(1));

        let mut after = StateHasher::new();
        entities.hash_into(&mut after);
        assert_ne!(before.finish(), after.finish());
    }

    #[test]
    fn the_same_units_in_different_slots_hash_differently() {
        // They really are different states: the next spawn lands elsewhere.
        let mut a = Entities::new();
        a.spawn(troop_at(1, 1));
        a.spawn(troop_at(2, 2));

        let mut b = Entities::new();
        let first = b.spawn(troop_at(0, 0));
        b.spawn(troop_at(1, 1));
        b.despawn(first);
        b.spawn(troop_at(2, 2));

        let mut ha = StateHasher::new();
        a.hash_into(&mut ha);
        let mut hb = StateHasher::new();
        b.hash_into(&mut hb);
        assert_ne!(ha.finish(), hb.finish());
    }

    #[test]
    fn identical_histories_hash_identically() {
        fn build() -> Entities {
            let mut entities = Entities::new();
            let ids: Vec<EntityId> = (0..5).map(|i| entities.spawn(troop_at(i, i))).collect();
            entities.despawn(ids[2]);
            entities
                .get_mut(ids[3])
                .expect("live")
                .take_damage(Fx::from_ratio(45, 2));
            entities.spawn(troop_at(7, 7));
            entities
        }
        let mut first = StateHasher::new();
        build().hash_into(&mut first);
        let mut second = StateHasher::new();
        build().hash_into(&mut second);
        assert_eq!(first.finish(), second.finish());
    }
}
