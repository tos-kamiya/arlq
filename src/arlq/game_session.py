"""State owned by a game session, independent of a user interface."""

from typing import Optional

from . import defs as d
from .arlq import GameConfig
from .utils import rand


class GameSession:
    """Initialize the world for one game.

    Turn processing remains in the game loop until it is moved into this
    class; the world and player are shared with that loop in the meantime.
    """

    def __init__(self, stage_num: int = 3, config: Optional[GameConfig] = None):
        # Keep the existing builders in game_engine so their callers and test
        # substitutions keep using the same implementations.
        from . import game_engine as engine

        self.config = config if config is not None else GameConfig()
        self.stage_num = stage_num
        self.initial_seed = rand.get_seed()
        self.single_floor_stage = stage_num in (1, 2)
        if self.single_floor_stage:
            self.floors, self.player = engine.build_single_floor(self.config, stage_num)
        elif stage_num == 6:
            self.floors, self.player = engine.stage6.build(self.config)
        elif stage_num == 5:
            self.floors, self.player = engine.stage5.build_member_trial(self.config)
        else:
            self.floors, self.player = engine.build(
                self.config.corridor_h_width,
                self.config.corridor_v_width,
                stage_num,
            )
        for floor_data in self.floors:
            floor_data.update_outer_wall_decor()
        self.player.known_monsters = set(d.INITIALLY_KNOWN_MONSTERS)
        self.player.boss_defeated = False
        self.player.dungeon_core_destroyed = False
        self.player.treasure_collected = False
