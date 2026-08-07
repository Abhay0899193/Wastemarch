//! Flow-field pathfinding.
//!
//! # Why a flow field rather than a path per unit
//!
//! In a raid, twenty troops head for the same few targets. Working out a separate
//! route for each is twenty times the work for nearly the same answer.
//!
//! A flow field inverts it: solve the whole board **once**, from the goal
//! outward, and store at every tile which way to step next. Then each unit does a
//! single lookup per tick. Cost stops depending on how many units there are, and
//! starts depending only on how often the board changes — which is when a
//! building falls.
//!
//! It is two passes:
//!
//! 1. **Integration field** — cheapest total cost from every tile to the nearest
//!    goal, by Dijkstra outward from the goals.
//! 2. **Flow field** — at each tile, the neighbour with the lowest integration
//!    cost. That is the direction to walk.
//!
//! # Goals may be impassable, on purpose
//!
//! A troop attacking the town hall wants to reach the tile *next to* it, not walk
//! into it. So goal tiles are seeded at zero cost whether or not they are
//! passable, but the search only ever expands *through* walkable tiles. A unit
//! standing beside a building therefore has a flow direction pointing at it,
//! which is exactly the signal "you have arrived, start hitting it".
//!
//! # Determinism
//!
//! Two things here could quietly differ between machines and neither does:
//!
//! - The priority queue is keyed on `(cost, tile index)`, never on cost alone, so
//!   equal costs resolve by tile index rather than by whatever order the heap
//!   happens to hold them in.
//! - Equal-cost neighbours resolve by [`Tile::neighbours`] order, which is fixed
//!   and tested. Change that order and every unit walks differently.

use core::cmp::Reverse;
use std::collections::BinaryHeap;

use crate::StateHasher;
use crate::grid::{GRID_SIZE, Grid, Tile};

/// Integration cost meaning "no route to any goal".
pub const UNREACHABLE: u32 = u32::MAX;

/// Which way to step. Four directions, matching [`Tile::neighbours`].
#[derive(Clone, Copy, PartialEq, Eq, Debug, Default)]
#[repr(u8)]
pub enum Direction {
    /// Nowhere to go: either standing on a goal, or cut off from every goal.
    #[default]
    None = 0,
    North = 1,
    East = 2,
    South = 3,
    West = 4,
}

impl Direction {
    /// The tile one step this way.
    #[inline]
    pub const fn step_from(self, tile: Tile) -> Tile {
        match self {
            Direction::None => tile,
            Direction::North => Tile::new(tile.x, tile.y - 1),
            Direction::East => Tile::new(tile.x + 1, tile.y),
            Direction::South => Tile::new(tile.x, tile.y + 1),
            Direction::West => Tile::new(tile.x - 1, tile.y),
        }
    }

    /// The direction matching an index into [`Tile::neighbours`].
    #[inline]
    const fn from_neighbour_index(index: usize) -> Direction {
        match index {
            0 => Direction::North,
            1 => Direction::East,
            2 => Direction::South,
            _ => Direction::West,
        }
    }
}

/// A solved board: where to walk from anywhere, to reach the nearest goal.
///
// ponytail: four-way movement, so routes are blocky at corners. Eight-way needs
// corner-cutting rules (a diagonal between two blocked tiles must be refused) and
// a second cost scale for diagonal steps. Upgrade when the movement actually
// looks wrong on screen in Phase 4, not before.
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct FlowField {
    cost: Vec<u32>,
    flow: Vec<Direction>,
}

impl FlowField {
    /// Solves the board for a set of goal tiles.
    ///
    /// Out-of-bounds goals are ignored. With no reachable goals every tile comes
    /// back [`UNREACHABLE`] and [`Direction::None`], which callers must handle —
    /// it happens legitimately when a unit is walled in.
    pub fn towards(grid: &Grid, goals: &[Tile]) -> FlowField {
        let tile_count = (GRID_SIZE * GRID_SIZE) as usize;
        let mut cost = vec![UNREACHABLE; tile_count];

        // Keyed on (cost, index) so equal costs resolve by tile index rather than
        // by heap order. Reverse makes it a min-heap.
        let mut queue: BinaryHeap<Reverse<(u32, u32)>> = BinaryHeap::new();

        for goal in goals {
            if let Some(index) = goal.index() {
                // Seeded whether or not the goal is passable: a troop attacking a
                // building routes to the tile beside it, never into it.
                if cost[index] != 0 {
                    cost[index] = 0;
                    queue.push(Reverse((0, index as u32)));
                }
            }
        }

        while let Some(Reverse((popped_cost, index))) = queue.pop() {
            // A tile can be queued more than once; skip the stale entries.
            if popped_cost > cost[index as usize] {
                continue;
            }
            let tile = Tile::from_index(index as usize);

            for neighbour in tile.neighbours() {
                let Some(neighbour_index) = neighbour.index() else {
                    continue;
                };
                // Expansion only ever travels through walkable ground, which is
                // what keeps an impassable goal from becoming a through-route.
                if !grid.is_walkable(neighbour) {
                    continue;
                }
                let step = grid.move_cost(neighbour);
                let next = popped_cost.saturating_add(step);
                if next < cost[neighbour_index] {
                    cost[neighbour_index] = next;
                    queue.push(Reverse((next, neighbour_index as u32)));
                }
            }
        }

        // Second pass: point every tile at its cheapest neighbour.
        let mut flow = vec![Direction::None; tile_count];
        for index in 0..tile_count {
            if cost[index] == 0 || cost[index] == UNREACHABLE {
                continue; // already arrived, or nowhere to go
            }
            let tile = Tile::from_index(index);
            let mut best = cost[index];
            let mut best_direction = Direction::None;
            for (i, neighbour) in tile.neighbours().iter().enumerate() {
                let Some(neighbour_index) = neighbour.index() else {
                    continue;
                };
                // Strictly less than, so the first neighbour in the fixed order
                // wins a tie. That is what makes ties deterministic.
                if cost[neighbour_index] < best {
                    best = cost[neighbour_index];
                    best_direction = Direction::from_neighbour_index(i);
                }
            }
            flow[index] = best_direction;
        }

        FlowField { cost, flow }
    }

    /// Total movement cost from a tile to the nearest goal.
    ///
    /// [`UNREACHABLE`] when there is no route. Out-of-bounds also reads as
    /// [`UNREACHABLE`].
    #[inline]
    pub fn cost_at(&self, tile: Tile) -> u32 {
        match tile.index() {
            Some(i) => self.cost[i],
            None => UNREACHABLE,
        }
    }

    /// Which way to step from a tile.
    #[inline]
    pub fn direction_at(&self, tile: Tile) -> Direction {
        match tile.index() {
            Some(i) => self.flow[i],
            None => Direction::None,
        }
    }

    /// Whether any goal can be reached from here.
    #[inline]
    pub fn is_reachable(&self, tile: Tile) -> bool {
        self.cost_at(tile) != UNREACHABLE
    }

    /// Walks the field from a tile, for tests and debugging.
    ///
    /// Stops on arrival, on running out of route, or after `limit` steps. The
    /// limit is a guard: a malformed field could otherwise loop forever, and this
    /// turns that into a visible short route instead of a hang.
    pub fn trace(&self, start: Tile, limit: usize) -> Vec<Tile> {
        let mut path = vec![start];
        let mut current = start;
        for _ in 0..limit {
            let direction = self.direction_at(current);
            if direction == Direction::None {
                break;
            }
            current = direction.step_from(current);
            path.push(current);
            if self.cost_at(current) == 0 {
                break;
            }
        }
        path
    }

    /// Absorbs the whole field into a state hash.
    pub fn hash_into(&self, hasher: &mut StateHasher) {
        for &c in &self.cost {
            hasher.write_u32(c);
        }
        for &d in &self.flow {
            hasher.write_u8(d as u8);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::grid::Terrain;

    fn open_grid() -> Grid {
        Grid::new()
    }

    #[test]
    fn the_goal_costs_nothing() {
        let field = FlowField::towards(&open_grid(), &[Tile::new(10, 10)]);
        assert_eq!(field.cost_at(Tile::new(10, 10)), 0);
        assert_eq!(field.direction_at(Tile::new(10, 10)), Direction::None);
    }

    #[test]
    fn cost_rises_with_distance_on_open_ground() {
        let field = FlowField::towards(&open_grid(), &[Tile::new(0, 0)]);
        assert_eq!(field.cost_at(Tile::new(1, 0)), 100);
        assert_eq!(field.cost_at(Tile::new(2, 0)), 200);
        assert_eq!(field.cost_at(Tile::new(0, 3)), 300);
        // Diagonal is reached by walking two sides, since movement is four-way.
        assert_eq!(field.cost_at(Tile::new(1, 1)), 200);
    }

    #[test]
    fn walking_the_field_arrives() {
        let field = FlowField::towards(&open_grid(), &[Tile::new(5, 5)]);
        let path = field.trace(Tile::new(20, 20), 200);
        assert_eq!(*path.last().expect("non-empty"), Tile::new(5, 5));
        // Manhattan distance is 30, and four-way movement cannot beat it.
        assert_eq!(path.len(), 31);
    }

    #[test]
    fn every_step_gets_strictly_closer() {
        // The property that guarantees units cannot loop forever.
        let mut grid = open_grid();
        for y in 4..40 {
            grid.set(Tile::new(20, y), Terrain::Rock);
        }
        let field = FlowField::towards(&grid, &[Tile::new(5, 20)]);

        for y in 0..GRID_SIZE {
            for x in 0..GRID_SIZE {
                let tile = Tile::new(x, y);
                if !field.is_reachable(tile) || field.cost_at(tile) == 0 {
                    continue;
                }
                let next = field.direction_at(tile).step_from(tile);
                assert!(
                    field.cost_at(next) < field.cost_at(tile),
                    "{tile:?} -> {next:?} did not decrease cost"
                );
            }
        }
    }

    #[test]
    fn a_wall_forces_a_detour() {
        let mut grid = open_grid();
        // A wall across the middle with a gap at the top.
        for y in 5..GRID_SIZE {
            grid.set(Tile::new(20, y), Terrain::Rock);
        }
        let field = FlowField::towards(&grid, &[Tile::new(30, 30)]);

        let path = field.trace(Tile::new(10, 30), 500);
        assert_eq!(*path.last().expect("non-empty"), Tile::new(30, 30));
        // It must go up and round through the gap, never through the wall.
        assert!(path.iter().all(|t| grid.is_walkable(*t)));
        assert!(
            path.iter().any(|t| t.y < 5),
            "path did not use the gap at the top"
        );
    }

    #[test]
    fn a_sealed_region_is_unreachable() {
        let mut grid = open_grid();
        // Box in a single tile completely.
        for (dx, dy) in [(0, -1), (1, 0), (0, 1), (-1, 0)] {
            grid.set(Tile::new(10 + dx, 10 + dy), Terrain::Rock);
        }
        let field = FlowField::towards(&grid, &[Tile::new(30, 30)]);

        assert!(!field.is_reachable(Tile::new(10, 10)));
        assert_eq!(field.cost_at(Tile::new(10, 10)), UNREACHABLE);
        assert_eq!(field.direction_at(Tile::new(10, 10)), Direction::None);
        // Tracing from a sealed tile must terminate immediately, not spin.
        assert_eq!(field.trace(Tile::new(10, 10), 500), vec![Tile::new(10, 10)]);
    }

    #[test]
    fn mud_is_avoided_when_going_round_is_cheaper() {
        let mut grid = open_grid();
        // A short mud channel. Mud costs 250 a tile against open ground's 100, so
        // stepping around it is cheaper and the field must prefer that.
        for x in 1..4 {
            grid.set(Tile::new(x, 1), Terrain::Mud);
        }
        let field = FlowField::towards(&grid, &[Tile::new(0, 1)]);

        let path = field.trace(Tile::new(4, 1), 100);
        assert_eq!(*path.last().expect("non-empty"), Tile::new(0, 1));
        let mud_tiles = path
            .iter()
            .filter(|t| grid.get(**t) == Terrain::Mud)
            .count();
        assert!(
            mud_tiles < 3,
            "route went straight through the mud: {path:?}"
        );
    }

    #[test]
    fn mud_is_crossed_when_there_is_no_way_round() {
        let mut grid = open_grid();
        // Mud spanning a corridor walled top and bottom: crossing is the only option.
        for x in 0..GRID_SIZE {
            grid.set(Tile::new(x, 0), Terrain::Rock);
            grid.set(Tile::new(x, 2), Terrain::Rock);
        }
        for x in 3..6 {
            grid.set(Tile::new(x, 1), Terrain::Mud);
        }
        let field = FlowField::towards(&grid, &[Tile::new(0, 1)]);
        let path = field.trace(Tile::new(8, 1), 100);
        assert_eq!(*path.last().expect("non-empty"), Tile::new(0, 1));
        assert!(path.iter().any(|t| grid.get(*t) == Terrain::Mud));
    }

    #[test]
    fn an_impassable_goal_is_approached_but_not_entered() {
        // The case the module documentation calls out: a troop attacking a
        // building routes beside it, never through it.
        let mut grid = open_grid();
        let hall = Tile::new(20, 20);
        grid.set(hall, Terrain::Built);
        let field = FlowField::towards(&grid, &[hall]);

        assert_eq!(field.cost_at(hall), 0);
        // The neighbour is reachable and points at the building.
        let beside = Tile::new(21, 20);
        assert_eq!(field.cost_at(beside), 100);
        assert_eq!(field.direction_at(beside), Direction::West);

        // And the building is not usable as a shortcut: going around it costs the
        // same as if it were solid, which it is.
        let path = field.trace(Tile::new(24, 20), 100);
        assert!(path.iter().filter(|t| **t == hall).count() <= 1);
    }

    #[test]
    fn several_goals_route_to_the_nearest() {
        let grid = open_grid();
        let field = FlowField::towards(&grid, &[Tile::new(0, 0), Tile::new(40, 40)]);

        assert_eq!(field.cost_at(Tile::new(1, 0)), 100);
        assert_eq!(field.cost_at(Tile::new(39, 40)), 100);
        // A tile near one goal must not be routed to the far one.
        assert_eq!(
            *field.trace(Tile::new(3, 3), 200).last().unwrap(),
            Tile::new(0, 0)
        );
        assert_eq!(
            *field.trace(Tile::new(38, 38), 200).last().unwrap(),
            Tile::new(40, 40)
        );
    }

    #[test]
    fn no_goals_means_nothing_is_reachable() {
        let field = FlowField::towards(&open_grid(), &[]);
        assert!(!field.is_reachable(Tile::new(0, 0)));
        assert!(!field.is_reachable(Tile::new(43, 43)));
    }

    #[test]
    fn out_of_bounds_goals_are_ignored_not_wrapped() {
        let field = FlowField::towards(&open_grid(), &[Tile::new(-1, -1), Tile::new(99, 99)]);
        // If either had wrapped into a valid index, some tile would have cost 0.
        assert!(!field.is_reachable(Tile::new(0, 0)));
    }

    #[test]
    fn ties_resolve_by_neighbour_order() {
        // From the diagonal, north and west are equally good. Neighbour order is
        // north, east, south, west — so north must win. This is arbitrary but it
        // must be *consistently* arbitrary, or two machines pick differently.
        let field = FlowField::towards(&open_grid(), &[Tile::new(0, 0)]);
        assert_eq!(
            field.cost_at(Tile::new(1, 0)),
            field.cost_at(Tile::new(0, 1))
        );
        assert_eq!(field.direction_at(Tile::new(1, 1)), Direction::North);
    }

    #[test]
    fn the_same_board_always_solves_the_same_way() {
        let mut grid = open_grid();
        let mut rng = crate::Pcg32::new(0xBEEF);
        for _ in 0..300 {
            let tile = Tile::new(rng.range(0, 43), rng.range(0, 43));
            let terrain = match rng.below(3) {
                0 => Terrain::Rock,
                1 => Terrain::Mud,
                _ => Terrain::Treeline,
            };
            grid.set(tile, terrain);
        }
        let goals = [Tile::new(22, 22), Tile::new(3, 40)];

        let first = FlowField::towards(&grid, &goals);
        let second = FlowField::towards(&grid, &goals);
        assert_eq!(first, second);

        let mut ha = StateHasher::new();
        first.hash_into(&mut ha);
        let mut hb = StateHasher::new();
        second.hash_into(&mut hb);
        assert_eq!(ha.finish(), hb.finish());
    }

    #[test]
    fn goal_order_does_not_change_the_answer() {
        // Callers must not have to care what order they list goals in.
        let grid = open_grid();
        let a = FlowField::towards(&grid, &[Tile::new(5, 5), Tile::new(30, 30)]);
        let b = FlowField::towards(&grid, &[Tile::new(30, 30), Tile::new(5, 5)]);
        assert_eq!(a, b);
    }

    #[test]
    fn a_duplicated_goal_changes_nothing() {
        let grid = open_grid();
        let once = FlowField::towards(&grid, &[Tile::new(7, 7)]);
        let twice = FlowField::towards(&grid, &[Tile::new(7, 7), Tile::new(7, 7)]);
        assert_eq!(once, twice);
    }

    #[test]
    fn costs_cannot_overflow_on_the_worst_board() {
        // Every passable tile at the highest cost, goal in one corner. If the
        // running total could wrap, a far tile would come back cheap and units
        // would walk away from the goal.
        let mut grid = open_grid();
        for y in 0..GRID_SIZE {
            for x in 0..GRID_SIZE {
                grid.set(Tile::new(x, y), Terrain::Mud);
            }
        }
        let field = FlowField::towards(&grid, &[Tile::new(0, 0)]);
        let far = field.cost_at(Tile::new(43, 43));
        assert!(far != UNREACHABLE);
        assert_eq!(far, 250 * 86); // 86 steps of mud, exact
    }
}
