"""Rewind reconstruction for multi-floor stages."""

from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from typing import Optional

from . import defs as d
from .i18n import trp
from .stage_types import Floor, ReplayContext
from .stage_world import _spawn
from .utils import zip_strict


@dataclass
class _RewindKnowledge:
    """Discoveries carried across reconstruction; encounter state is excluded."""

    known_monsters: set[str]
    known_c_floors: set[int]
    elf_floors: dict[str, int]
    known_elf_floors: set[str]
    known_member_floors: dict[str, int]
    seen_members: set[str]
    seen: list[list[list[int]]]
    discovered_secrets: list[dict[d.Point, str]]

    @classmethod
    def capture(cls, floors: list[Floor], player: d.Player) -> "_RewindKnowledge":
        return cls(
            known_monsters=set(player.known_monsters),
            known_c_floors=set(player.known_c_floors),
            elf_floors=deepcopy(player.elf_stage_floors),
            known_elf_floors=set(player.known_elf_floors),
            known_member_floors=deepcopy(player.known_member_floors),
            seen_members=set(player.seen_members),
            seen=deepcopy([floor_data.seen for floor_data in floors]),
            discovered_secrets=[
                {
                    (x, y): cell
                    for y, row in enumerate(floor_data.field)
                    for x, cell in enumerate(row)
                    if cell in (
                        d.CHAR_SCHOLAR_STAIRS_UP,
                        d.CHAR_SCHOLAR_STAIRS_DOWN,
                        d.CHAR_D_GATE,
                    )
                }
                for floor_data in floors
            ],
        )

    def restore(self, floors: list[Floor], player: d.Player) -> None:
        for index, (floor_data, preserved_seen, preserved_secrets) in enumerate(zip_strict(
            floors, self.seen, self.discovered_secrets
        )):
            floor_data.seen = preserved_seen
            for (x, y), cell in preserved_secrets.items():
                if cell == d.CHAR_SCHOLAR_STAIRS_UP and (x, y) not in floor_data.scholar_up_stairs:
                    if (index == 0 or floors[index - 1].field[y][x] != d.CHAR_COLLAPSE
                            or floor_data.field[y][x] != d.CHAR_FLOOR):
                        continue
                floor_data.field[y][x] = cell
            floor_data.update_outer_wall_decor()
        player.known_monsters = self.known_monsters
        player.known_c_floors = self.known_c_floors
        player.elf_stage_floors = self.elf_floors
        player.known_elf_floors = self.known_elf_floors
        player.known_member_floors = self.known_member_floors
        player.seen_members = self.seen_members


def rewind(
    floors: list[Floor],
    player: d.Player,
    floor: list[int],
    checkpoint: list[d.Point],
    queue: Counter[tuple[int, str]],
    replay_context: ReplayContext,
    *,
    operation_count: int,
    loop_floor_index: Optional[int] = None,
) -> str:
    """Restore a saved state and carry over the player's current knowledge."""
    knowledge = _RewindKnowledge.capture(floors, player)

    target_count = replay_context.rewind_targets.get(
        operation_count, max(0, operation_count - d.LOOP_TURNS),
    )
    (
        restored_floors, restored_player_state, restored_floor,
        restored_checkpoint, restored_queue,
    ) = replay_context.load_snapshot(target_count)
    floors[:] = restored_floors
    floor[0] = restored_floor
    checkpoint[0] = restored_checkpoint
    queue.clear()
    queue.update(restored_queue)

    player.__dict__.update(restored_player_state.__dict__)
    knowledge.restore(floors, player)

    respawn_floor = floor[0] if loop_floor_index is None else loop_floor_index
    loop_floor = floors[respawn_floor]
    restored_entities = loop_floor.entities
    for index, restored in enumerate(restored_entities):
        if isinstance(restored, d.Fairy) and restored.tribe.char == "l":
            del restored_entities[index]
            break
    l_position = _spawn(
        restored_entities,
        loop_floor.field,
        "l",
        {(player.x, player.y)} if respawn_floor == floor[0] else set(),
        loop_floor.island,
        respawn_floor,
    )
    for restored in restored_entities:
        if (
            isinstance(restored, d.Fairy)
            and restored.tribe.char == "l"
            and (restored.x, restored.y) == l_position
        ):
            restored.revealed = True
            break

    return trp("-- Time folds back to the beginning of the recorded past.", 9)
