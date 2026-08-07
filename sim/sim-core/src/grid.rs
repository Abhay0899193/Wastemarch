//! The world grid — 44 x 44 tiles, per `MASTER_PLAN.md` §3.4.
//!
//! Positions come in two flavours and mixing them up is the easiest bug to write
//! here, so they are separate types the compiler will not let you confuse:
//!
//! - [`Tile`] — whole-tile coordinates. Where a building sits.
//! - [`Point`] — fixed-point coordinates. Where a unit is, part-way between tiles.
//!
//! One tile is one metre, matching the art scale in `docs/ART_BIBLE.md`, so the
//! two convert without a scale factor.

use crate::Fx;

/// Grid width and height in tiles. Expansion wedges in Phase 5 grow the *usable*
/// area within this, they do not change this number.
pub const GRID_SIZE: i32 = 44;

/// A whole-tile coordinate.
#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Debug, Hash, Default)]
pub struct Tile {
    pub x: i32,
    pub y: i32,
}

impl Tile {
    pub const fn new(x: i32, y: i32) -> Tile {
        Tile { x, y }
    }

    /// Whether this tile is inside the grid.
    #[inline]
    pub const fn in_bounds(self) -> bool {
        self.x >= 0 && self.x < GRID_SIZE && self.y >= 0 && self.y < GRID_SIZE
    }

    /// A single index for this tile, for storing one value per tile in a `Vec`.
    ///
    /// Returns `None` when out of bounds, so callers cannot accidentally index a
    /// wrapped-around tile.
    #[inline]
    pub const fn index(self) -> Option<usize> {
        if self.in_bounds() {
            Some((self.y * GRID_SIZE + self.x) as usize)
        } else {
            None
        }
    }

    /// The tile at a given index. Inverse of [`Tile::index`].
    #[inline]
    pub const fn from_index(index: usize) -> Tile {
        let i = index as i32;
        Tile {
            x: i % GRID_SIZE,
            y: i / GRID_SIZE,
        }
    }

    /// The centre of this tile in fixed-point coordinates.
    ///
    /// Units stand at tile *centres*, not corners, so a unit on a tile is
    /// visually in the middle of it.
    #[inline]
    pub const fn centre(self) -> Point {
        Point {
            x: Fx::from_bits(self.x * crate::FIXED_ONE + crate::FIXED_ONE / 2),
            y: Fx::from_bits(self.y * crate::FIXED_ONE + crate::FIXED_ONE / 2),
        }
    }

    /// The four tiles sharing an edge with this one, in a fixed order.
    ///
    /// **The order is part of the simulation.** Pathfinding ties are broken by
    /// whichever neighbour is examined first, so changing this order changes
    /// which way units walk, and would change every recorded battle.
    #[inline]
    pub const fn neighbours(self) -> [Tile; 4] {
        [
            Tile::new(self.x, self.y - 1), // north
            Tile::new(self.x + 1, self.y), // east
            Tile::new(self.x, self.y + 1), // south
            Tile::new(self.x - 1, self.y), // west
        ]
    }

    /// Number of tiles between two tiles moving only along the grid.
    #[inline]
    pub const fn manhattan_distance(self, other: Tile) -> i32 {
        (self.x - other.x).abs() + (self.y - other.y).abs()
    }
}

/// A fixed-point position within the world.
#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Debug, Default)]
pub struct Point {
    pub x: Fx,
    pub y: Fx,
}

impl Point {
    pub const fn new(x: Fx, y: Fx) -> Point {
        Point { x, y }
    }

    /// The tile containing this point.
    #[inline]
    pub const fn tile(self) -> Tile {
        Tile {
            x: self.x.floor_to_int(),
            y: self.y.floor_to_int(),
        }
    }

    /// Squared distance to another point.
    ///
    /// **Prefer this over [`Point::distance`] wherever you are only comparing.**
    /// It avoids a square root, and more importantly avoids the rounding a square
    /// root introduces — comparisons on exact values cannot produce ties that
    /// resolve differently.
    #[inline]
    pub fn distance_squared(self, other: Point) -> Fx {
        let dx = self.x - other.x;
        let dy = self.y - other.y;
        dx * dx + dy * dy
    }

    /// Straight-line distance to another point.
    #[inline]
    pub fn distance(self, other: Point) -> Fx {
        self.distance_squared(other).sqrt()
    }

    /// This point moved by an offset.
    #[inline]
    pub fn offset(self, dx: Fx, dy: Fx) -> Point {
        Point {
            x: self.x + dx,
            y: self.y + dy,
        }
    }
}

/// What occupies a tile. Drives both pathfinding and placement rules.
#[derive(Clone, Copy, PartialEq, Eq, Debug, Default)]
#[repr(u8)]
pub enum Terrain {
    /// Ordinary ground. Walkable, no modifier.
    #[default]
    Open = 0,
    /// Slows movement. `MASTER_PLAN.md` §3.3 — terrain is a real decision.
    Mud = 1,
    /// Blocks movement and line of sight.
    Rock = 2,
    /// Blocks line of sight, passable. The Duskwood edge.
    Treeline = 3,
    /// Occupied by a building.
    Built = 4,
}

impl Terrain {
    /// Whether a ground unit can enter.
    #[inline]
    pub const fn is_walkable(self) -> bool {
        matches!(self, Terrain::Open | Terrain::Mud | Terrain::Treeline)
    }

    /// Whether this tile blocks sight through it.
    #[inline]
    pub const fn blocks_sight(self) -> bool {
        matches!(self, Terrain::Rock | Terrain::Treeline | Terrain::Built)
    }

    /// Cost of crossing, in whole units where ordinary ground is 100.
    ///
    /// Whole numbers rather than fixed-point because these are summed over long
    /// paths, and integers keep that exact with no rounding at all.
    /// [`IMPASSABLE`] marks a tile that cannot be entered.
    #[inline]
    pub const fn move_cost(self) -> u32 {
        match self {
            Terrain::Open => 100,
            Terrain::Mud => 250,
            Terrain::Treeline => 160,
            Terrain::Rock | Terrain::Built => IMPASSABLE,
        }
    }
}

/// Movement cost meaning "cannot enter". Chosen far below `u32::MAX` so costs can
/// be summed without overflowing.
pub const IMPASSABLE: u32 = u32::MAX / 4;

/// The terrain of every tile in the world.
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct Grid {
    tiles: Vec<Terrain>,
}

impl Default for Grid {
    fn default() -> Self {
        Self::new()
    }
}

impl Grid {
    /// A grid of open ground.
    pub fn new() -> Grid {
        Grid {
            tiles: vec![Terrain::Open; (GRID_SIZE * GRID_SIZE) as usize],
        }
    }

    /// The terrain at a tile. Out-of-bounds reads as [`Terrain::Rock`], so the
    /// edge of the world behaves like a wall without every caller checking.
    #[inline]
    pub fn get(&self, tile: Tile) -> Terrain {
        match tile.index() {
            Some(i) => self.tiles[i],
            None => Terrain::Rock,
        }
    }

    /// Sets the terrain at a tile. Out-of-bounds writes are ignored.
    #[inline]
    pub fn set(&mut self, tile: Tile, terrain: Terrain) {
        if let Some(i) = tile.index() {
            self.tiles[i] = terrain;
        }
    }

    /// Whether a ground unit can stand here.
    #[inline]
    pub fn is_walkable(&self, tile: Tile) -> bool {
        self.get(tile).is_walkable()
    }

    /// Cost of entering a tile.
    #[inline]
    pub fn move_cost(&self, tile: Tile) -> u32 {
        self.get(tile).move_cost()
    }

    /// Every tile, in index order. Deterministic by construction.
    pub fn iter(&self) -> impl Iterator<Item = (Tile, Terrain)> + '_ {
        self.tiles
            .iter()
            .enumerate()
            .map(|(i, &t)| (Tile::from_index(i), t))
    }

    /// Absorbs the whole grid into a state hash.
    pub fn hash_into(&self, hasher: &mut crate::StateHasher) {
        for &terrain in &self.tiles {
            hasher.write_u8(terrain as u8);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bounds_are_checked() {
        assert!(Tile::new(0, 0).in_bounds());
        assert!(Tile::new(43, 43).in_bounds());
        assert!(!Tile::new(44, 0).in_bounds());
        assert!(!Tile::new(0, 44).in_bounds());
        assert!(!Tile::new(-1, 0).in_bounds());
        assert!(!Tile::new(0, -1).in_bounds());
    }

    #[test]
    fn index_round_trips_for_every_tile() {
        for y in 0..GRID_SIZE {
            for x in 0..GRID_SIZE {
                let tile = Tile::new(x, y);
                let index = tile.index().expect("in bounds");
                assert_eq!(Tile::from_index(index), tile);
            }
        }
    }

    #[test]
    fn index_covers_the_grid_exactly_once() {
        let mut seen = vec![false; (GRID_SIZE * GRID_SIZE) as usize];
        for y in 0..GRID_SIZE {
            for x in 0..GRID_SIZE {
                let i = Tile::new(x, y).index().expect("in bounds");
                assert!(!seen[i], "index {i} produced twice");
                seen[i] = true;
            }
        }
        assert!(seen.iter().all(|&s| s));
    }

    #[test]
    fn out_of_bounds_tiles_have_no_index() {
        // The guard that stops a negative coordinate wrapping into a valid slot.
        assert_eq!(Tile::new(-1, 0).index(), None);
        assert_eq!(Tile::new(0, -1).index(), None);
        assert_eq!(Tile::new(GRID_SIZE, 0).index(), None);
    }

    #[test]
    fn tile_centres_are_half_a_tile_in() {
        let centre = Tile::new(0, 0).centre();
        assert_eq!(centre.x, Fx::from_ratio(1, 2));
        assert_eq!(centre.y, Fx::from_ratio(1, 2));

        let centre = Tile::new(3, 5).centre();
        assert_eq!(centre.x, Fx::from_ratio(7, 2));
        assert_eq!(centre.y, Fx::from_ratio(11, 2));
    }

    #[test]
    fn a_tile_centre_maps_back_to_its_tile() {
        for y in 0..GRID_SIZE {
            for x in 0..GRID_SIZE {
                let tile = Tile::new(x, y);
                assert_eq!(tile.centre().tile(), tile);
            }
        }
    }

    #[test]
    fn neighbour_order_is_fixed() {
        // Pathfinding breaks ties by this order, so it is part of the simulation.
        // If this test fails, every recorded battle replays differently.
        assert_eq!(
            Tile::new(5, 5).neighbours(),
            [
                Tile::new(5, 4),
                Tile::new(6, 5),
                Tile::new(5, 6),
                Tile::new(4, 5)
            ]
        );
    }

    #[test]
    fn manhattan_distance_is_symmetric() {
        let a = Tile::new(2, 7);
        let b = Tile::new(9, 3);
        assert_eq!(a.manhattan_distance(b), b.manhattan_distance(a));
        assert_eq!(a.manhattan_distance(b), 11);
        assert_eq!(a.manhattan_distance(a), 0);
    }

    #[test]
    fn distance_is_correct_for_a_known_triangle() {
        let a = Point::new(Fx::ZERO, Fx::ZERO);
        let b = Point::new(Fx::from_int(3), Fx::from_int(4));
        assert_eq!(a.distance_squared(b), Fx::from_int(25));
        assert_eq!(a.distance(b), Fx::from_int(5));
    }

    #[test]
    fn distance_is_symmetric() {
        let a = Point::new(Fx::from_ratio(7, 3), Fx::from_ratio(-11, 5));
        let b = Point::new(Fx::from_ratio(2, 7), Fx::from_int(4));
        assert_eq!(a.distance_squared(b), b.distance_squared(a));
        assert_eq!(a.distance(b), b.distance(a));
    }

    #[test]
    fn outside_the_grid_reads_as_rock() {
        // So the world edge behaves like a wall without every caller checking.
        let grid = Grid::new();
        assert_eq!(grid.get(Tile::new(-1, 0)), Terrain::Rock);
        assert_eq!(grid.get(Tile::new(GRID_SIZE, 0)), Terrain::Rock);
        assert!(!grid.is_walkable(Tile::new(-1, -1)));
    }

    #[test]
    fn terrain_can_be_set_and_read() {
        let mut grid = Grid::new();
        assert_eq!(grid.get(Tile::new(10, 10)), Terrain::Open);
        grid.set(Tile::new(10, 10), Terrain::Mud);
        assert_eq!(grid.get(Tile::new(10, 10)), Terrain::Mud);
        // Neighbours untouched.
        assert_eq!(grid.get(Tile::new(11, 10)), Terrain::Open);
    }

    #[test]
    fn writing_out_of_bounds_is_ignored_not_wrapped() {
        let mut grid = Grid::new();
        grid.set(Tile::new(-1, 0), Terrain::Rock);
        grid.set(Tile::new(GRID_SIZE, 0), Terrain::Rock);
        // If a negative coordinate wrapped, some real tile would have changed.
        assert!(grid.iter().all(|(_, t)| t == Terrain::Open));
    }

    #[test]
    fn walkability_and_sight_match_the_design() {
        assert!(Terrain::Open.is_walkable());
        assert!(Terrain::Mud.is_walkable());
        assert!(Terrain::Treeline.is_walkable());
        assert!(!Terrain::Rock.is_walkable());
        assert!(!Terrain::Built.is_walkable());

        // The treeline is the interesting one: you can walk into it but not see
        // through it. That is what makes the Duskwood edge tense.
        assert!(Terrain::Treeline.is_walkable());
        assert!(Terrain::Treeline.blocks_sight());
        assert!(!Terrain::Open.blocks_sight());
    }

    #[test]
    fn move_costs_are_ordered_and_summable() {
        assert!(Terrain::Open.move_cost() < Terrain::Treeline.move_cost());
        assert!(Terrain::Treeline.move_cost() < Terrain::Mud.move_cost());
        assert_eq!(Terrain::Rock.move_cost(), IMPASSABLE);

        // A whole grid of the worst passable terrain must not overflow when
        // summed, or a long path's cost wraps to something small and units take
        // an absurd route.
        let worst = Terrain::Mud.move_cost() as u64 * (GRID_SIZE * GRID_SIZE) as u64;
        assert!(worst < u32::MAX as u64);
    }

    #[test]
    fn iteration_order_is_stable() {
        let grid = Grid::new();
        let first: Vec<Tile> = grid.iter().map(|(t, _)| t).collect();
        let second: Vec<Tile> = grid.iter().map(|(t, _)| t).collect();
        assert_eq!(first, second);
        assert_eq!(first.len(), (GRID_SIZE * GRID_SIZE) as usize);
        assert_eq!(first[0], Tile::new(0, 0));
        assert_eq!(first[1], Tile::new(1, 0));
    }

    #[test]
    fn the_grid_hashes_and_changes_when_it_changes() {
        let mut grid = Grid::new();
        let mut before = crate::StateHasher::new();
        grid.hash_into(&mut before);

        grid.set(Tile::new(20, 20), Terrain::Mud);
        let mut after = crate::StateHasher::new();
        grid.hash_into(&mut after);

        assert_ne!(before.finish(), after.finish());
    }
}
