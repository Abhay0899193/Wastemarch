//! Battle records — a whole battle in about half a kilobyte.
//!
//! A replay here is **not a video**. It is the starting seed, a fingerprint of
//! the starting board, and a list of what the player did and when. Playing it
//! back re-runs the battle, and because the simulation is deterministic it comes
//! out identical.
//!
//! `MASTER_PLAN.md` §1.4 puts the cost at roughly two kilobytes.
//! [`tests::a_realistic_record_is_about_two_kilobytes`] measures it rather than
//! trusting it.
//!
//! # This is also how V2 stops cheating
//!
//! A client submits one of these instead of "I won". The server re-runs it with
//! the same code and compares the resulting state hash. A client that lies about
//! the outcome has to produce inputs that genuinely produce that outcome, which
//! is not cheating so much as playing.
//!
//! # The setup fingerprint
//!
//! A record only means something against the board it was made on. Replaying
//! against a different board silently produces a different battle, which as a
//! bug is nearly impossible to find — so the setup is fingerprinted, stored, and
//! checked before replay begins.

use crate::battle::Battle;
use crate::entity::{Combat, Entity, EntityKind, Team};
use crate::grid::{Grid, Tile};
use crate::{Fx, StateHasher};

/// Identifies this as a Wastemarch battle record: "WMBR".
const MAGIC: u32 = 0x574d_4252;
/// Encoding version. Bump when the byte layout changes; old records then fail
/// to load rather than being misread.
const VERSION: u16 = 1;
/// Bytes per encoded input.
const INPUT_BYTES: usize = 11;
/// Bytes before the first input.
const HEADER_BYTES: usize = 4 + 2 + 8 + 8 + 4;

/// One kind of troop or building that can be deployed.
///
/// Balance data, so it comes from `game/data/` via the caller (`CLAUDE.md` §3).
/// A record stores only the *index* into the roster, which is what keeps it small
/// and what makes a record meaningless without its setup.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct TroopSpec {
    pub kind: EntityKind,
    pub team: Team,
    pub max_health: Fx,
    pub combat: Combat,
}

impl TroopSpec {
    fn hash_into(&self, hasher: &mut StateHasher) {
        hasher.write_u8(self.kind as u8);
        hasher.write_u8(self.team as u8);
        hasher.write_fx(self.max_health);
        hasher.write_fx(self.combat.speed);
        hasher.write_fx(self.combat.damage);
        hasher.write_fx(self.combat.range);
        hasher.write_u32(self.combat.cooldown);
    }
}

/// Something the player did.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Input {
    /// Put a troop from the roster onto a tile.
    Deploy { spec: u16, tile: Tile },
}

/// An input and the tick it happened on.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct TimedInput {
    pub tick: u32,
    pub input: Input,
}

/// Everything needed to start a battle, other than the player's actions.
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct BattleSetup {
    pub grid: Grid,
    pub roster: Vec<TroopSpec>,
    /// Whatever is already on the board: index into `roster`, and where.
    pub initial: Vec<(u16, Tile)>,
}

impl BattleSetup {
    /// The fingerprint stored in a record and checked before replay.
    pub fn fingerprint(&self) -> u64 {
        let mut hasher = StateHasher::new();
        self.grid.hash_into(&mut hasher);
        hasher.write_u32(self.roster.len() as u32);
        for spec in &self.roster {
            spec.hash_into(&mut hasher);
        }
        hasher.write_u32(self.initial.len() as u32);
        for (spec, tile) in &self.initial {
            hasher.write_u32(*spec as u32);
            hasher.write_i32(tile.x);
            hasher.write_i32(tile.y);
        }
        hasher.finish()
    }
}

/// What went wrong replaying a record.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum ReplayError {
    /// The record was made against a different board or roster.
    SetupMismatch { expected: u64, found: u64 },
    /// Inputs are not in tick order. Applying them out of order would produce a
    /// different battle, so this is refused rather than guessed at.
    InputsOutOfOrder { at: usize },
    /// An input names a roster entry that does not exist.
    UnknownSpec { spec: u16 },
    /// Not a battle record, or a version this build cannot read.
    Malformed,
}

/// A complete, replayable battle.
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct BattleRecord {
    pub seed: u64,
    pub setup_fingerprint: u64,
    inputs: Vec<TimedInput>,
}

impl BattleRecord {
    /// An empty record for a battle about to be played.
    pub fn new(seed: u64, setup: &BattleSetup) -> BattleRecord {
        BattleRecord {
            seed,
            setup_fingerprint: setup.fingerprint(),
            inputs: Vec::new(),
        }
    }

    /// Appends an input.
    ///
    /// Ticks must not go backwards. Returns whether it was accepted — a rejected
    /// input means the caller has a bug, since inputs arrive as the battle runs.
    pub fn push(&mut self, tick: u32, input: Input) -> bool {
        if self.inputs.last().is_some_and(|last| last.tick > tick) {
            return false;
        }
        self.inputs.push(TimedInput { tick, input });
        true
    }

    pub fn inputs(&self) -> &[TimedInput] {
        &self.inputs
    }

    #[inline]
    pub fn len(&self) -> usize {
        self.inputs.len()
    }

    #[inline]
    pub fn is_empty(&self) -> bool {
        self.inputs.is_empty()
    }

    /// Encoded size in bytes, without doing the encoding.
    #[inline]
    pub fn encoded_len(&self) -> usize {
        HEADER_BYTES + self.inputs.len() * INPUT_BYTES
    }

    /// Encodes to bytes. Little-endian throughout, never host order, so a record
    /// written on one machine reads correctly on any other.
    pub fn to_bytes(&self) -> Vec<u8> {
        let mut out = Vec::with_capacity(self.encoded_len());
        out.extend_from_slice(&MAGIC.to_le_bytes());
        out.extend_from_slice(&VERSION.to_le_bytes());
        out.extend_from_slice(&self.seed.to_le_bytes());
        out.extend_from_slice(&self.setup_fingerprint.to_le_bytes());
        out.extend_from_slice(&(self.inputs.len() as u32).to_le_bytes());
        for timed in &self.inputs {
            out.extend_from_slice(&timed.tick.to_le_bytes());
            match timed.input {
                Input::Deploy { spec, tile } => {
                    out.push(0);
                    out.extend_from_slice(&spec.to_le_bytes());
                    // Tiles fit in 16 bits with room to spare; the grid is 44x44.
                    out.extend_from_slice(&(tile.x as i16).to_le_bytes());
                    out.extend_from_slice(&(tile.y as i16).to_le_bytes());
                }
            }
        }
        debug_assert_eq!(out.len(), self.encoded_len());
        out
    }

    /// Decodes bytes written by [`BattleRecord::to_bytes`].
    pub fn from_bytes(bytes: &[u8]) -> Result<BattleRecord, ReplayError> {
        if bytes.len() < HEADER_BYTES {
            return Err(ReplayError::Malformed);
        }
        let magic = u32::from_le_bytes(bytes[0..4].try_into().map_err(|_| ReplayError::Malformed)?);
        let version =
            u16::from_le_bytes(bytes[4..6].try_into().map_err(|_| ReplayError::Malformed)?);
        if magic != MAGIC || version != VERSION {
            return Err(ReplayError::Malformed);
        }
        let seed = u64::from_le_bytes(
            bytes[6..14]
                .try_into()
                .map_err(|_| ReplayError::Malformed)?,
        );
        let fingerprint = u64::from_le_bytes(
            bytes[14..22]
                .try_into()
                .map_err(|_| ReplayError::Malformed)?,
        );
        let count = u32::from_le_bytes(
            bytes[22..26]
                .try_into()
                .map_err(|_| ReplayError::Malformed)?,
        ) as usize;

        // Check the length before allocating, so a corrupt count cannot ask for a
        // huge allocation.
        if bytes.len() != HEADER_BYTES + count * INPUT_BYTES {
            return Err(ReplayError::Malformed);
        }

        let mut inputs = Vec::with_capacity(count);
        for i in 0..count {
            let at = HEADER_BYTES + i * INPUT_BYTES;
            let tick = u32::from_le_bytes(
                bytes[at..at + 4]
                    .try_into()
                    .map_err(|_| ReplayError::Malformed)?,
            );
            if bytes[at + 4] != 0 {
                return Err(ReplayError::Malformed);
            }
            let spec = u16::from_le_bytes(
                bytes[at + 5..at + 7]
                    .try_into()
                    .map_err(|_| ReplayError::Malformed)?,
            );
            let x = i16::from_le_bytes(
                bytes[at + 7..at + 9]
                    .try_into()
                    .map_err(|_| ReplayError::Malformed)?,
            );
            let y = i16::from_le_bytes(
                bytes[at + 9..at + 11]
                    .try_into()
                    .map_err(|_| ReplayError::Malformed)?,
            );
            inputs.push(TimedInput {
                tick,
                input: Input::Deploy {
                    spec,
                    tile: Tile::new(x as i32, y as i32),
                },
            });
        }

        Ok(BattleRecord {
            seed,
            setup_fingerprint: fingerprint,
            inputs,
        })
    }
}

/// Builds the opening state of a battle from its setup.
fn start(setup: &BattleSetup, seed: u64) -> Result<Battle, ReplayError> {
    let mut battle = Battle::new(setup.grid.clone(), seed);
    for (spec_index, tile) in &setup.initial {
        let spec = setup
            .roster
            .get(*spec_index as usize)
            .ok_or(ReplayError::UnknownSpec { spec: *spec_index })?;
        battle.spawn(entity_from(spec, *tile));
    }
    Ok(battle)
}

fn entity_from(spec: &TroopSpec, tile: Tile) -> Entity {
    Entity::new(spec.kind, spec.team, tile.centre(), spec.max_health).with_combat(spec.combat)
}

/// Replays a record and returns the final state hash.
///
/// The same record and setup always produce the same number, on any machine.
/// That equality is what the server checks in V2, and what the Phase 4 test
/// checks now.
pub fn replay(
    setup: &BattleSetup,
    record: &BattleRecord,
    max_ticks: u32,
) -> Result<u64, ReplayError> {
    let fingerprint = setup.fingerprint();
    if fingerprint != record.setup_fingerprint {
        return Err(ReplayError::SetupMismatch {
            expected: record.setup_fingerprint,
            found: fingerprint,
        });
    }
    for (i, pair) in record.inputs.windows(2).enumerate() {
        if pair[0].tick > pair[1].tick {
            return Err(ReplayError::InputsOutOfOrder { at: i + 1 });
        }
    }
    for timed in &record.inputs {
        let Input::Deploy { spec, .. } = timed.input;
        if setup.roster.get(spec as usize).is_none() {
            return Err(ReplayError::UnknownSpec { spec });
        }
    }

    let mut battle = start(setup, record.seed)?;
    let mut next = 0usize;

    // Inputs land at the START of their tick, before anything moves. Any other
    // choice is equally valid and none of them are interchangeable — a deploy
    // resolving after movement is a different battle.
    for _ in 0..max_ticks {
        let tick = battle.tick();
        while let Some(timed) = record.inputs.get(next) {
            if timed.tick != tick {
                break;
            }
            let Input::Deploy { spec, tile } = timed.input;
            let spec = &setup.roster[spec as usize];
            battle.spawn(entity_from(spec, tile));
            next += 1;
        }
        // Deliberately after inputs: a deploy on the tick a battle would
        // otherwise end must still count.
        if battle.is_over() && next >= record.inputs.len() {
            break;
        }
        battle.step();
    }

    Ok(battle.state_hash())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::grid::Terrain;

    fn roster() -> Vec<TroopSpec> {
        vec![
            TroopSpec {
                kind: EntityKind::Troop,
                team: Team::Holding,
                max_health: Fx::from_int(120),
                combat: Combat {
                    speed: Fx::from_ratio(1, 10),
                    damage: Fx::from_int(9),
                    range: Fx::from_ratio(3, 2),
                    cooldown: 5,
                },
            },
            TroopSpec {
                kind: EntityKind::Troop,
                team: Team::Duskwood,
                max_health: Fx::from_int(90),
                combat: Combat {
                    speed: Fx::from_ratio(3, 20),
                    damage: Fx::from_int(7),
                    range: Fx::from_int(1),
                    cooldown: 3,
                },
            },
            TroopSpec {
                kind: EntityKind::Building,
                team: Team::Duskwood,
                max_health: Fx::from_int(400),
                combat: Combat::default(),
            },
        ]
    }

    fn setup() -> BattleSetup {
        let mut grid = Grid::new();
        for y in 8..20 {
            grid.set(Tile::new(15, y), Terrain::Rock);
        }
        BattleSetup {
            grid,
            roster: roster(),
            initial: vec![(2, Tile::new(30, 12)), (1, Tile::new(28, 14))],
        }
    }

    fn recorded() -> BattleRecord {
        let setup = setup();
        let mut record = BattleRecord::new(0x00A1_D21C, &setup);
        record.push(
            0,
            Input::Deploy {
                spec: 0,
                tile: Tile::new(2, 12),
            },
        );
        record.push(
            0,
            Input::Deploy {
                spec: 0,
                tile: Tile::new(2, 13),
            },
        );
        record.push(
            14,
            Input::Deploy {
                spec: 0,
                tile: Tile::new(2, 14),
            },
        );
        record.push(
            40,
            Input::Deploy {
                spec: 0,
                tile: Tile::new(3, 10),
            },
        );
        record.push(
            75,
            Input::Deploy {
                spec: 0,
                tile: Tile::new(3, 16),
            },
        );
        record
    }

    #[test]
    fn a_record_replays_to_the_same_result_twice() {
        // The Phase 4 completion test, in miniature.
        let setup = setup();
        let record = recorded();
        let first = replay(&setup, &record, 600).expect("replay");
        let second = replay(&setup, &record, 600).expect("replay");
        assert_eq!(first, second);
    }

    #[test]
    fn the_inputs_actually_matter() {
        // Guards against a replay that ignores its inputs and would therefore
        // pass the test above forever.
        let setup = setup();
        let with_inputs = replay(&setup, &recorded(), 600).expect("replay");
        let empty = BattleRecord::new(0x00A1_D21C, &setup);
        let without = replay(&setup, &empty, 600).expect("replay");
        assert_ne!(with_inputs, without);
    }

    #[test]
    fn the_seed_matters() {
        let setup = setup();
        let mut other = recorded();
        other.seed ^= 0xFFFF;
        // Same inputs, different seed. Nothing in the current simulation draws
        // from the generator yet, so this documents the wiring rather than a
        // behavioural difference — it will start to differ the moment anything
        // rolls a die, and this test is where that shows up.
        let _ = replay(&setup, &other, 600).expect("replay");
    }

    #[test]
    fn a_record_from_a_different_board_is_refused() {
        // Silently replaying against the wrong board produces a different battle
        // and a bug nobody can find. Refused instead.
        let record = recorded();
        let mut different = setup();
        different.grid.set(Tile::new(1, 1), Terrain::Mud);

        match replay(&different, &record, 100) {
            Err(ReplayError::SetupMismatch { .. }) => {}
            other => panic!("expected SetupMismatch, got {other:?}"),
        }
    }

    #[test]
    fn a_changed_roster_is_also_refused() {
        // The board is identical; only a balance number moved. The record still
        // must not replay, because it would produce a different battle.
        let record = recorded();
        let mut different = setup();
        different.roster[0].combat.damage = Fx::from_int(10);
        assert!(matches!(
            replay(&different, &record, 100),
            Err(ReplayError::SetupMismatch { .. })
        ));
    }

    #[test]
    fn inputs_cannot_go_backwards() {
        let setup = setup();
        let mut record = BattleRecord::new(1, &setup);
        assert!(record.push(
            10,
            Input::Deploy {
                spec: 0,
                tile: Tile::new(1, 1)
            }
        ));
        assert!(!record.push(
            9,
            Input::Deploy {
                spec: 0,
                tile: Tile::new(1, 1)
            }
        ));
        // Equal ticks are fine: two deploys can land on the same tick.
        assert!(record.push(
            10,
            Input::Deploy {
                spec: 0,
                tile: Tile::new(2, 2)
            }
        ));
        assert_eq!(record.len(), 2);
    }

    #[test]
    fn an_unknown_spec_is_refused() {
        let setup = setup();
        let mut record = BattleRecord::new(1, &setup);
        record.push(
            0,
            Input::Deploy {
                spec: 99,
                tile: Tile::new(1, 1),
            },
        );
        assert!(matches!(
            replay(&setup, &record, 10),
            Err(ReplayError::UnknownSpec { spec: 99 })
        ));
    }

    #[test]
    fn bytes_round_trip() {
        let record = recorded();
        let bytes = record.to_bytes();
        assert_eq!(bytes.len(), record.encoded_len());
        let back = BattleRecord::from_bytes(&bytes).expect("decode");
        assert_eq!(back, record);
    }

    #[test]
    fn a_decoded_record_replays_identically() {
        // The point of the encoding: a record that has been to disk and back is
        // the same battle.
        let setup = setup();
        let record = recorded();
        let back = BattleRecord::from_bytes(&record.to_bytes()).expect("decode");
        assert_eq!(
            replay(&setup, &record, 600).expect("replay"),
            replay(&setup, &back, 600).expect("replay")
        );
    }

    #[test]
    fn corrupt_bytes_are_refused_rather_than_misread() {
        let good = recorded().to_bytes();

        assert!(BattleRecord::from_bytes(&[]).is_err());
        assert!(BattleRecord::from_bytes(&good[..HEADER_BYTES - 1]).is_err());

        let mut bad_magic = good.clone();
        bad_magic[0] ^= 0xFF;
        assert!(BattleRecord::from_bytes(&bad_magic).is_err());

        let mut bad_version = good.clone();
        bad_version[4] = 99;
        assert!(BattleRecord::from_bytes(&bad_version).is_err());

        // A count claiming far more inputs than there are bytes must be rejected
        // before anything is allocated.
        let mut bad_count = good.clone();
        bad_count[22..26].copy_from_slice(&u32::MAX.to_le_bytes());
        assert!(BattleRecord::from_bytes(&bad_count).is_err());

        let mut truncated = good.clone();
        truncated.pop();
        assert!(BattleRecord::from_bytes(&truncated).is_err());
    }

    #[test]
    fn encoding_is_little_endian_regardless_of_host() {
        // Explicit byte order, so a record written on one machine reads on any
        // other. If someone swaps these for native-endian helpers, this fails.
        let setup = setup();
        let mut record = BattleRecord::new(0x0102_0304_0506_0708, &setup);
        record.push(
            1,
            Input::Deploy {
                spec: 0,
                tile: Tile::new(1, 1),
            },
        );
        let bytes = record.to_bytes();
        assert_eq!(&bytes[0..4], &MAGIC.to_le_bytes());
        assert_eq!(
            &bytes[6..14],
            &[0x08, 0x07, 0x06, 0x05, 0x04, 0x03, 0x02, 0x01]
        );
    }

    #[test]
    fn a_realistic_record_is_about_two_kilobytes() {
        // MASTER_PLAN.md §1.4 claims a replay costs roughly two kilobytes.
        // Measured rather than believed: a three-minute battle at 20 ticks a
        // second with a deploy every couple of seconds.
        let setup = setup();
        let mut record = BattleRecord::new(1, &setup);
        for i in 0..90u32 {
            record.push(
                i * 40,
                Input::Deploy {
                    spec: 0,
                    tile: Tile::new(2, (i % 40) as i32),
                },
            );
        }
        let size = record.encoded_len();
        assert_eq!(size, HEADER_BYTES + 90 * INPUT_BYTES);
        assert!(size < 2048, "a busy three-minute battle took {size} bytes");
        assert_eq!(record.to_bytes().len(), size);
    }

    #[test]
    fn an_empty_record_still_replays() {
        // A battle nobody intervened in is a valid battle.
        let setup = setup();
        let record = BattleRecord::new(7, &setup);
        assert!(replay(&setup, &record, 200).is_ok());
    }
}
