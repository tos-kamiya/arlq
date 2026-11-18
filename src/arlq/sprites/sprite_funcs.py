"""Pyglet frontend with character sprites and the original text fallback."""

import json
import math
import random
import time
from functools import partial
from pathlib import Path

import pyglet
from pyglet.window import key as pgkey

from .. import defs as d
from .. import display as ui_display
from ..arlq import barrier_lp_damage
from ..i18n import t as tr
from ..game_events import Combat, FloorChanged, Rewound
from .sprite_fx import Presenter
from .sprite_defs import (
    NEIGHBOR_SCALE,
    SPRITE_REFERENCE_PIXELS,
    SPRITE_GROUND_OFFSET_PIXELS,
    TERRAIN_SIDE,
    ROCK_SPRITE,
    SPRITE_CELL_SIZE_X,
    LOW_RESOLUTION_DETAIL_SCALE,
    GROUND_DISC_RADIUS,
    DUNGEON_CORE_CELL_UNITS,
)
from .sprite_effects import SpriteEffectsMixin
from .sprite_terrain import (
    WALL_PARTS,
    WALL_IMAGE_GAIN,
    FLOOR_PARTS,
    FLOOR_TINTS,
    FLOOR_CHECKER_SHADE,
    TERRAIN_THEMES,
    STAGE_TERRAIN_THEMES,
    THEME_SPRITES,
    BARRIER_REDUCED_SCALE,
    TERRAIN_FILES,
    TERRAIN_EXPLORED_SHADE,
    SpriteTerrainMixin,
)
from .sprite_images import (
    FOLLOWER_SCALE,
    GROUND_DISC_FLATTEN,
    PILLAR_HEIGHT,
    PILLAR_RADIUS,
    RESPAWN_COLUMN_GAP_SHADE,
    RESPAWN_COLUMN_HEIGHT,
    RESPAWN_COLUMN_RADIUS,
    _luminance,
    barrier_image,
    brightened_image,
    gray_image,
    ground_disc_image,
    mipmapped,
    pillar_image,
    respawn_column_image,
    smoke_image,
    soft_outline_image,
)
from ..pyglet_funcs import (
    CELL_SIZE_X,
    CELL_SIZE_Y,
    CI_BLUE,
    CI_GREEN,
    CI_YELLOW,
    COLOR_MAP,
    FIELD_SIDEBAR_GAP,
    FONT_HEIGHT_RATIO,
    MAX_UI_SCALE,
    MESSAGE_FONT_SIZE_SCALE,
    MIN_UI_SCALE,
    STRENGTH_COLUMN_PADDING,
    PygletUI,
    _font_glyph_metrics,
)

SPRITE_FILES = {
    '@': 'player.png',
    'a': 'amoeba.png',
    'A': 'rare-amoeba.png',
    'b': 'bison.png',
    'B': 'buffalo.png',
    'c': 'chimera.png',
    'd': 'comodo-dragon.png',
    'D': 'dragon.png',
    'T': 'treasure.png',
    'M': 'mimic.png',
    'l': 'loop-watch.png',
    'n': 'nomicon.png',
    'o': 'ocular.png',
    'C': 'rare-chimera.png',
    'F': 'fire-drake.png',
    'f': 'flame-cobra.png',
    'g': 'golem.png',
    'k': 'marksman.png',
    'V': 'vortex.png',
    'w': 'wyrm.png',
    'W': 'dread-wyrm.png',
    'm': 'spore.png',
    'e': 'erebus.png',
    'E': 'rare-erebus.png',
    'X': 'caltrop-plant.png',
    'i': 'ivy.png',
    'p': 'pegasus.png',
    'H': 'high-elf.png',
    'I': 'isolated-elf.png',
    'J': 'javelin-elf.png',
    'K': 'collector-elf.png',
    'L': 'lifebringer-elf.png',
    'S': 'sylvan-elf.png',
    # Not a glyph: the rubble drawn on walls a defeated Golem raised.
    'golem rock': 'golem-rock.png',
    # Not a glyph: the player collapsed from hunger, face down without a sword.
    'player collapsed': 'player-collapsed.png',
    # Not glyphs: the player holding a chimera's sword taken from it, or its
    # own sword glowing blue after the Collector Elf's blessing.
    'player sword': 'player-sword.png',
    'player cursed sword': 'player-cursed-sword.png',
    'player blessed': 'player-blessed.png',
    # Not a glyph: the plastic toy chest drawn for 'T' in Stage 5.
    'T-toy': 'treasure-toy.png',
    # Unidentified monsters (and traps), fairies and elves.
    '?': 'unknown-question.png',
    '!': 'unknown-exclamation.png',
    '&': 'unknown-ampersand.png',
}
# The unidentified symbols stand in a light pillar of their text color; the
# near-white symbol takes on only this fraction of that color.
UNKNOWN_SPRITES = ('?', '!', '&')
UNKNOWN_TINT = 0.4
# Their pillar is dimmed to this fraction, so it does not outshine the
# identified characters around it.
UNKNOWN_PILLAR = 0.21
# Their ground disc is darkened, if needed, to no brighter (by luminance) than
# the blue disc of a beatable identified monster.
UNKNOWN_DISC_REFERENCE = CI_BLUE
# Member sprite files are named '<job>-<gender>-<skin>.png': gender f, m, or
# n for a job drawn alike for both; skin l(ight), m(edium) or d(ark). The
# Dungeon Explorer, a dragon, has one build whose scales lean blue (l), sit
# midway (m) or lean green (d).
MEMBER_SPRITES = {'J': ('jester-n',), 'H': ('healer-f', 'healer-m'),
                  'R': ('rogue-n',), 'K': ('knight-n',),
                  'G': ('guardian-n',), 'D': ('explorer-n',),
                  'S': ('seer-f', 'seer-m')}
CAT_SPRITE = 'yawning-cat'
SPRITE_FILES[CAT_SPRITE] = 'yawning-cat.png'
# The player's images facing up, left and right; facing down (the camera) is
# the plain image. Keys add the facing to the plain image's key, e.g.
# 'player sword left' for player-sword-left.png.
PLAYER_FACINGS = ('up', 'left', 'right')
PLAYER_FACING_BY_MOVE = {(0, -1): 'up', (0, 1): 'down', (-1, 0): 'left', (1, 0): 'right'}
PLAYER_SPRITE_FILES = {
    '@': 'player', 'player sword': 'player-sword',
    'player cursed sword': 'player-cursed-sword', 'player blessed': 'player-blessed',
}
SPRITE_FILES.update({f'{key} {facing}': f'{name}-{facing}.png'
                     for key, name in PLAYER_SPRITE_FILES.items()
                     for facing in PLAYER_FACINGS})
SPRITE_FILES.update({f'{key} {facing} {pose}': f'{name}-{facing}-{pose}.png'
                     for key, name in PLAYER_SPRITE_FILES.items()
                     for facing in ('down', *PLAYER_FACINGS)
                     for pose in ('walk-right', 'walk-left')})
MEMBER_SKINS = ('l', 'm', 'd')
SPRITE_FILES.update({f'{name}-{skin}': f'{name}-{skin}.png'
                     for names in MEMBER_SPRITES.values() for name in names
                     for skin in MEMBER_SKINS})
SPRITE_NAMES = {
    '@': 'Player', 'a': 'Amoeba', 'A': 'Rare Amoeba', 'b': 'Bison',
    'B': 'Buffalo', 'c': 'Chimera', 'C': 'Rare Chimera', 'd': 'Komodo Dragon',
    'D': 'Dragon', 'T': 'Treasure', 'M': 'Mimic', 'l': 'Loop Fairy',
    'n': 'Nomicon', 'o': 'Ocular', 'F': 'Fire Drake', 'f': 'Flame Cobra',
    'g': 'Golem', 'i': 'Ivy', 'k': 'Marksman', 'V': 'Vortex', 'w': 'Wyrm',
    'W': 'Dread Wyrm', 'm': 'Spore', 'e': 'Erebus', 'E': 'Rare Erebus',
    'X': 'Caltrop Plant', 'p': 'Pegasus', 'H': 'High Elf', 'I': 'Isolated Elf',
    'J': 'Javelin Elf', 'K': 'Collector Elf', 'L': 'Lifebringer Elf',
    'S': 'Sylvan Elf', '?': 'Unidentified Monster',
    '!': 'Unidentified Fairy', '&': 'Unidentified Elf',
}
SPRITE_NAMES.update(dict.fromkeys(
    ('player sword', 'player cursed sword', 'player blessed', 'player collapsed'), 'Player'))
SPRITE_NAMES.update(dict.fromkeys(
    (key for key in SPRITE_FILES if key.endswith((' walk-right', ' walk-left'))), 'Player'))
SPRITE_NAMES.update({f'{name}-{skin}': role
                     for role, char in d.MEMBER_GLYPHS.items()
                     for name in MEMBER_SPRITES.get(char, ())
                     for skin in MEMBER_SKINS})
SPRITE_NAMES[CAT_SPRITE] = d.MEMBER_YAWNING_CAT
# An elf the player has met (drawn without bold as text) is shown with its
# sprite and ground disc darkened to this fraction.
MET_ELF_SHADE = 0.6
# A dark translucent backing keeps the elf and treasure progress marks legible
# when the tall field sprites extend behind the bottom status row.
TEXT_PANEL_ALPHA = 112
TEXT_PANEL_PADDING = 4
# Field text kept as text (such as "+" and ".") is raised by this fraction of
# a cell, so it stays within its cell above the flagstone joint.
FIELD_TEXT_RAISE = 0.1
# Width of the strength column's sprite area in field cells. Each entry keeps
# its smaller label on the left and, once the
# player has identified that type (as on the field), shows the character's
# sprite to its right, at the same size as on the field (larger ones may
# overflow their row).
STRENGTH_SPRITE_CELLS = 2
# Keep the complete field and strength column in the initial window.
HORIZONTAL_VIEW_SCROLL_CELLS = 3
HOVER_SCALE = 2.0
MOUSE_CURSOR_SECONDS = 3.0
STRENGTH_TEXT_SCALE = 0.7
# After the idle delay, characters in view hop between two heights every
# IDLE_BOB_INTERVAL seconds, all in step. The hop is whole texels of the
# low-resolution render target (1 window pixel at 100%).
IDLE_BOB_DELAY = 5.0
IDLE_BOB_INTERVAL = 0.7
IDLE_BOB_TEXELS = 2
# When the player's LP runs out, once its last turn has been shown, it sinks
# as far as an idle hop (its knees giving way) for COLLAPSE_SINK_SECONDS, and
# then lies collapsed ('player collapsed') on the final screen.
COLLAPSE_SINK_SECONDS = 0.45
# Empowered-rank marks, rendered as raised apostrophes in near-white resin and
# drawn white whatever the monster's strength color. They float at the upper
# right of the sprite instead of in the next cell: centre offset from the
# ground point in cell widths east and cell heights north.
MARK_FILES = {"'": 'mark-rank2.png', '"': 'mark-rank3.png'}
MARK_OFFSET = (0.6, 0.65)
# The player's LP gauge, drawn just above its head like a fighting game's:
# this fraction of its ground disc's width, this tall and this far above the
# head (both in cell widths), on a dark backing framed in this color.
# The gauge is fully opaque so its values remain legible over any field.
LP_GAUGE_WIDTH = 0.8
LP_GAUGE_HEIGHT = 0.22
LP_GAUGE_GAP = 0.52
LP_GAUGE_BACKING = (0, 0, 0, 255)
LP_GAUGE_FRAME = (235, 235, 235)
LP_GAUGE_OPACITY = 1.0
# A respawn cell where no character sprite is drawn (a hidden or text-only
# character) lights its column alone, in this neutral color, so the
# character's strength stays unknown.
RESPAWN_COLUMN_UNSEEN_COLOR = COLOR_MAP['default']
# The fairy travelling with the player floats small at its right shoulder:
# size relative to a normal sprite, and its ground point from the player's
# cell centre (cell widths east, cell heights north).
FAMILIAR_SIZE = 0.6
FAMILIAR_OFFSET = (0.7, 0.15)
# The landing image of the floor transition (see sprite_effects).
LANDING_FILE = 'stairs/stairs-landing.png'


class SpriteUI(SpriteTerrainMixin, SpriteEffectsMixin, PygletUI):
    """Reuse input, menus, visibility and glyph selection without duplicating rules."""

    supports_horizontal_view = True
    show_treasure_brackets = False
    show_core_brackets = False
    show_treasure_sparkles = False
    supports_floor_transition = True
    supports_idle_bob = True
    dim_protected_hazards = False

    # Decorations of the floor being drawn (see draw_stage), and the cells to
    # draw fallen rocks on once the characters of this frame are known.
    _decor = None
    _fallen_rock_draws = ()
    _field_text_cells = frozenset()
    # The player's cell this frame (None while viewing another floor), and
    # whether characters next to it are enlarged (off while drawing followers).
    _player_cell = None
    _enlarge_neighbors = True
    # Monster types the player has identified, for the strength column.
    _known_types = frozenset()
    # Current view and, while barriers are weakened, the player's cell that
    # cools the barrier stones around it.
    _cur_torched = None
    # The way the player last moved: 'down' (the camera), 'up', 'left' or
    # 'right'. Display only; no rule reads it.
    _player_facing = 'down'
    # The way the player attacked in the fight being shown (see
    # sprite_fx.Presenter); picks the slash image.
    _attack_facing = 'up'
    # The view the turn being presented leads to (see present_turn).
    _next_view = None
    _cooling_center = None
    _cooling_damage = None
    # The field being drawn, for stairs and pits that spread over neighbouring floor.
    _stage_field = None
    _stage_discovered_at = None
    # Terrain look of the stage being drawn (see TERRAIN_THEMES).
    _theme_images = {}
    _terrain_theme = 'ruins'
    _floor_tints = FLOOR_TINTS
    _floor_checker_shade = FLOOR_CHECKER_SHADE
    _wall_tints = TERRAIN_THEMES['ruins'][4]
    _respawn_glows = frozenset()
    # Respawn cells of this frame on known cells, and those whose column a
    # character's sprite has drawn.
    _respawn_draws = ()
    _respawn_columns_drawn = frozenset()
    _show_pit_up_marker = True
    _standing_turn = None
    _player_walk_pose = None
    _idle_bobbing = False
    # The cell of the chest that won the stage, drawn behind the player.
    _won_chest_cell = None
    # While a turn is being presented the player still stands, even with no
    # LP left; it collapses only after (see present_turn).
    _presenting_turn = False
    # The player sinking just before it collapses (see _show_collapse).
    _player_sinking = False

    def _initialize_state(self):
        super()._initialize_state()
        self._switching_fullscreen = False
        self._presenter = Presenter()
        self._player_facing = 'down'
        # Sprites that hop while waiting for input, as (sprite, base y).
        self._bobbing = []
        self._bob_raised = False
        self._bob_clock = time.monotonic
        self._last_bob_activity = self._bob_clock()
        # The won stage's treasure glow (see draw_treasure_glow).
        self._treasure_glow = None
        self._treasure_glow_since = None
        # Effect images, made on first use.
        self._pillar_image = None
        self._dome_images = None
        self._soft_dome_image = None
        self._uncached_drawables = []
        self._mouse_position = None
        self._mouse_visible_until = None
        self._edge_shade_fields = {}
        self._horizontal_scroll_px = 0
        self._floor_tiles = None
        self._floor_backdrops = {}
        self._use_floor_backdrop = False
        self._floor_backdrop_pending = False
        self._edge_shade_pending = False
        self._sprite_images = {}
        self._sprite_head_room = {}
        # Image data kept for followers' faded-outline copies, made on first use.
        self._sprite_data = {}
        self._follower_images = {}
        self._theme_floor_tiles = {}
        self._wall_rect_colors = {}

    def __init__(self, scale=None, key_repeat_interval=None, samurai=False):
        self._member_variants = {char: random.choice(names) for char, names in MEMBER_SPRITES.items()}
        self._member_skins = {char: random.choice(MEMBER_SKINS) for char in MEMBER_SPRITES}
        self._last_stage_draw = None
        self._resize_redraw_pending = False
        self._render_framebuffer = None
        self._render_texture = None
        self._composite_batch = None
        self._composite_sprite = None
        self._render_target_size = None
        self._failed_render_target_size = None
        super().__init__(scale, key_repeat_interval, resizable=True)
        self.window.push_handlers(
            on_key_press=self._on_fullscreen_key_press,
            on_key_release=self._on_fullscreen_key_release,
            on_mouse_motion=self._on_mouse_motion,
            on_mouse_drag=self._on_mouse_drag,
            on_mouse_leave=self._on_mouse_leave,
        )
        self._text_batch = pyglet.graphics.Batch()
        self._hud_row_height = self._menu_cell_size_y
        self._set_scaled_dimensions()
        self.window.set_size(self.window_width, self.window_height)
        self._drawing_hud = False
        self.window.set_caption(self.window.caption.replace('Pyglet mix', 'Sprite mix'))
        self._update_minimum_window_size()
        directory = Path(__file__).parent.parent / 'assets' / 'characters'
        self._gray_images = {}
        for char, filename in SPRITE_FILES.items():
            if samurai and (char in ('@', 'player collapsed')
                            or char.startswith(('player sword', 'player cursed sword',
                                                'player blessed', '@ '))):
                filename = 'samurai-' + filename
            path = directory / filename
            if not path.is_file():
                continue
            data = pyglet.image.load(str(path)).get_image_data()
            self._sprite_images[char] = mipmapped(data)
            self._sprite_data[char] = data
            rgba = data.get_data('RGBA', data.width * 4)
            # Fully transparent rows above the character (rows run bottom
            # to top), so things drawn over its head sit on the head itself.
            row_bytes = data.width * 4
            opaque_rows = [y for y in range(data.height)
                           if any(rgba[y * row_bytes + 3:(y + 1) * row_bytes:4])]
            self._sprite_head_room[char] = data.height - 1 - max(opaque_rows, default=0)
            self._gray_images[char] = mipmapped(gray_image(data))
        self._mark_images = {mark: mipmapped(pyglet.image.load(str(directory / filename)))
                             for mark, filename in MARK_FILES.items()
                             if (directory / filename).is_file()}
        # Cells where a character sprite was drawn this frame; a rank mark in
        # the next cell belongs to that sprite.
        self._sprite_cells = {}
        self._disc_image = ground_disc_image()
        self._disc_halves = (ground_disc_image('lower-left'), ground_disc_image('upper-right'))
        self._disc_group = pyglet.graphics.Group(order=1)
        self._pillar_images = {side: pillar_image(side) for side in ('back', 'front')}
        self._respawn_column_images = {
            (side, gaps): respawn_column_image(side, gaps)
            for side in ('back', 'front') for gaps in (False, True)
        }
        assets = Path(__file__).parent.parent / 'assets'
        # Per theme: wall parts, floor images and their grayscale copies for
        # the map display. A theme whose images are missing uses the ruins'.
        self._theme_images = {}
        for theme, (floor_prefix, wall_prefix, *_) in TERRAIN_THEMES.items():
            walls = None
            if wall_prefix is not None:
                paths = [assets / 'walls' / (wall_prefix + part + '.png') for part in WALL_PARTS]
                if all(path.is_file() for path in paths):
                    walls = {part: mipmapped(brightened_image(
                                 pyglet.image.load(str(path)).get_image_data(),
                                 WALL_IMAGE_GAIN.get(theme, 1)))
                             for part, path in zip(WALL_PARTS, paths)}
            floor_paths = [assets / 'floor' / (floor_prefix + part + '.png')
                           for part in FLOOR_PARTS]
            floors = grays = None
            if all(path.is_file() for path in floor_paths):
                data = [pyglet.image.load(str(path)).get_image_data() for path in floor_paths]
                floors = [mipmapped(image) for image in data]
                grays = [mipmapped(gray_image(image)) for image in data]
            ruins = self._theme_images.get('ruins', (None, None, None))
            if wall_prefix is not None and walls is None:
                walls = ruins[0]
            self._theme_images[theme] = (walls, floors or ruins[1],
                                         grays if floors else ruins[2])
        self._set_terrain_theme('ruins')
        self._terrain_images = {char: mipmapped(pyglet.image.load(str(assets / filename)))
                                for char, filename in TERRAIN_FILES.items()
                                if (assets / filename).is_file()}
        bridgehead_path = assets / 'bridgehead' / 'bridgehead.png'
        if bridgehead_path.is_file():
            placement = json.loads((bridgehead_path.parent / 'bridgehead.json').read_text())
            self._bridgehead_under = placement['under']
            self._bridgehead_height = 1 + placement['under'] + placement['overhang']
            bridgehead = mipmapped(pyglet.image.load(str(bridgehead_path)))
            half = bridgehead.width // 2
            self._bridgehead_images = {part: bridgehead.get_region(i * half, 0, half, bridgehead.height)
                                       for i, part in enumerate(('/', '\\'))}
        else:
            self._bridgehead_images = {}
        self._terrain_regions = {}
        core_dir = assets / 'dungeon-core'
        core_paths = {growth: core_dir / f'dungeon-core-{growth}.png'
                      for growth in d.DUNGEON_CORE_GROWTHS}
        self._dungeon_core_images = {}
        self._dungeon_core_under = self._dungeon_core_overhang = 0.0
        self._dungeon_core_cells = 1.0
        if all(path.is_file() for path in core_paths.values()):
            placement = json.loads((core_dir / 'dungeon-core.json').read_text())
            self._dungeon_core_under = placement['under']
            self._dungeon_core_overhang = placement['overhang']
            self._dungeon_core_cells = placement['cells']
            self._dungeon_core_images = {growth: mipmapped(pyglet.image.load(str(path)))
                                         for growth, path in core_paths.items()}
        self._dungeon_core_growth = 'small'
        self._landing_image = (mipmapped(pyglet.image.load(str(assets / LANDING_FILE)))
                               if (assets / LANDING_FILE).is_file() else None)
        self._barrier_images = [barrier_image(variant) for variant in (0, 1)]
        self._reduced_barrier_images = [barrier_image(variant, BARRIER_REDUCED_SCALE)
                                        for variant in (0, 1)]
        self._smoke_images = [smoke_image(barrier) for barrier in self._barrier_images]
        self._floor_group = pyglet.graphics.Group(order=-1)
        self._floor_backdrop_group = pyglet.graphics.Group(order=-2)
        # Between the floor and the ground discs.
        self._edge_shade_group = pyglet.graphics.Group(order=0)
        self._edge_shade_image = None
        self._edge_shade_bounds = None
        # Rows are painted north to south: a row's walls, then its characters,
        # so walls overlap characters to their north but not to their south.
        self._row_groups = {}
        self._overlay_group = pyglet.graphics.Group(order=10000)
        # Above every field row, below the HUD panels.
        self._lp_gauge_group = pyglet.graphics.Group(order=9000)
        self._text_panel_group = pyglet.graphics.Group(order=9999)
        self._text_overlay_group = pyglet.graphics.Group(order=10001)
        self._sidebar_bg_group = pyglet.graphics.Group(order=9998)
        self._sidebar_group = pyglet.graphics.Group(order=9999)
        self._floor_cells = {}
        for theme in TERRAIN_THEMES:
            self._set_terrain_theme(theme)
            self._create_floor_tiles()
            self._theme_floor_tiles[theme] = (self._floor_tiles, self._floor_cell_tiles)
        self._set_terrain_theme('ruins')
        self._use_floor_backdrop = True

    def _row_group(self, y, layer):
        if layer == 'hover':
            order = 9500
        elif layer == 'hover-mark':
            order = 9501
        elif layer == 'hover-name':
            order = 9502
        else:
            order = 10 + len(self.ROW_LAYERS) * y + self.ROW_LAYERS.index(layer)
        if order not in self._row_groups:
            self._row_groups[order] = pyglet.graphics.Group(order=order)
        return self._row_groups[order]

    def draw_stage(self, *, decor=None, **kwargs):
        self._update_strength_column_width()
        self.field_pixel_width = max(
            self.cell_size_x, self.window_width - self.strength_column_width,
        )
        field = kwargs.get('field')
        if field:
            self._set_edge_shade_field(field)
        self._last_stage_draw = (decor, kwargs.copy())
        turn = kwargs.get('turn')
        self._player_walk_pose = (
            None if not turn or turn == self._standing_turn
            else 'walk-right' if turn % 2 else 'walk-left'
        )
        if turn == 0:
            self._standing_turn = None
            # A stage starts with the player facing the camera.
            self._player_facing = 'down'
        theme = STAGE_TERRAIN_THEMES.get(kwargs.get('stage_num'), 'ruins')
        if theme != self._terrain_theme and theme in self._theme_images:
            self._set_terrain_theme(theme)
        self._decor = decor
        self._respawn_glows = kwargs.get('respawn_glows') or set()
        self._known_types = kwargs.get('known_types') or set()
        self._cur_torched = kwargs.get('cur_torched')
        self._dungeon_core_growth = d.dungeon_core_growth(kwargs.get('turn') or 0)
        player = kwargs.get('player')
        self._show_pit_up_marker = (
            player is not None and d.has_member(player, d.MEMBER_DUNGEON_EXPLORER)
        )
        if player is not None and not kwargs.get('floor_view'):
            player_pos = (player.x, player.y, player.current_floor)
            if (
                self._last_camera_player_pos is not None
                and player_pos != self._last_camera_player_pos
            ):
                self._camera_follow_player = True
            self._last_camera_player_pos = player_pos
            if self._camera_follow_player:
                self._center_camera_on_player(player.x)
        self._cooling_center = (
            (player.x, player.y)
            if player is not None and not kwargs.get('floor_view') and barrier_lp_damage(player) < d.BARRIER_LP_DAMAGE
            else None
        )
        self._cooling_damage = barrier_lp_damage(player) if self._cooling_center else None
        won = (player is not None and player.treasure_collected and player.stage_won
               and not kwargs.get('floor_view') and not self.map_mode)
        # The game ends on the chest's cell: the taken chest stays in sight
        # there, behind the player, inside its glow (see _draw_player).
        self._won_chest_cell = (player.x, player.y) if won else None
        if not won:
            self._treasure_glow_since = None
        result = super().draw_stage(decor=decor, **kwargs)
        return result

    def _draw_text(
        self,
        pos,
        text,
        color,
        bold=False,
        x_offset=0,
        size_scale=1.0,
        group=None,
        y_offset=0,
    ):
        if self._menu_active:
            return super()._draw_text(
                pos, text, color, bold, x_offset, size_scale, group, y_offset,
            )
        x = pos[0] * self.cell_size_x + x_offset
        y = self.window_height - pos[1] * self.cell_size_y + y_offset
        hud_bottom = 2 * self._hud_row_height
        if (
            not self._drawing_hud
            and x < self.field_pixel_width
            and y > hud_bottom
            and group is not self._text_overlay_group
        ):
            return super()._draw_text(
                pos, text, color, bold, x_offset, size_scale, group, y_offset,
            )

        scene_batch = self.batch
        self.batch = self._text_batch
        try:
            return super()._draw_text(
                pos, text, color, bold, x_offset, size_scale, group, y_offset,
            )
        finally:
            self.batch = scene_batch

    def _flip(self):
        self._draw_and_flip()

    def _bob_offset(self):
        return IDLE_BOB_TEXELS * self.scale / LOW_RESOLUTION_DETAIL_SCALE

    def _idle_bob_active(self):
        return (self.idle_bob_enabled and self._stage_input_active and not self.map_mode
                and self._bob_clock() - self._last_bob_activity >= IDLE_BOB_DELAY)

    def _idle_bob_raised(self):
        hop_seconds = self._bob_clock() - self._last_bob_activity - IDLE_BOB_DELAY
        return self._idle_bob_active() and int(hop_seconds / IDLE_BOB_INTERVAL) % 2 == 0

    def _update_idle_bob(self):
        """Move the hopping sprites when the hop height changes; nothing is
        drawn in between, so waiting stays cheap."""
        if (
            self._menu_active
            or not self._stage_input_active
            or self.map_mode
            or self._key_queue
            or self._held_direction_keys
            or self._gamepad_held_buttons
            or (self.controller and self._controller_direction(self.controller) != (0, 0))
        ):
            self._last_bob_activity = self._bob_clock()
        if self._menu_active:
            return
        active = self._idle_bob_active()
        pose_changed = active != self._idle_bobbing
        self._idle_bobbing = active
        raised = self._idle_bob_raised()
        if pose_changed and self._player_walk_pose and self._last_stage_draw is not None:
            decor, view = self._last_stage_draw
            if view.get('player') is not None and not view.get('floor_view'):
                self._bob_raised = raised
                self.draw_stage(decor=decor, **view)
                return
        if raised == self._bob_raised:
            return
        self._bob_raised = raised
        if not self._bobbing:
            return
        offset = self._bob_offset() if raised else 0
        for sprite, base_y in self._bobbing:
            sprite.y = base_y + offset
        self._flip()

    def _follower_image(self, text):
        """The faded-outline copy of a sprite (gray on the map), made once."""
        key = (text, self.map_mode)
        image = self._follower_images.get(key)
        if image is None:
            data = self._sprite_data.get(text)
            if data is None:
                return (self._gray_images if self.map_mode else self._sprite_images)[text]
            soft = soft_outline_image(data)
            image = mipmapped(gray_image(soft) if self.map_mode else soft)
            self._follower_images[key] = image
        return image

    def _in_view(self, pos):
        grid = self._cur_torched
        x, y = pos
        return (
            grid is not None
            and 0 <= y < len(grid)
            and 0 <= x < len(grid[y])
            and bool(grid[y][x])
        )

    def _framebuffer_size(self):
        get_size = getattr(self.window, 'get_framebuffer_size', None)
        if get_size is not None:
            return get_size()
        return self.window.width, self.window.height

    def _render_target_dimensions(self):
        density = LOW_RESOLUTION_DETAIL_SCALE / self.scale
        return (
            max(1, math.ceil(self.window.width * density)),
            max(1, math.ceil(self.window.height * density)),
        )

    def _ensure_render_target(self):
        target_size = self._render_target_dimensions()
        if (target_size == self._render_target_size
                or target_size == self._failed_render_target_size):
            return

        if self._composite_sprite is not None:
            self._composite_sprite.delete()
            self._composite_sprite = None
        self._composite_batch = None
        if self._render_framebuffer is not None:
            self._render_framebuffer.delete()
        if self._render_texture is not None:
            self._render_texture.delete()

        texture = pyglet.image.Texture.create(
            *target_size,
            min_filter=pyglet.gl.GL_LINEAR,
            mag_filter=pyglet.gl.GL_LINEAR,
        )
        framebuffer = pyglet.image.Framebuffer()
        framebuffer.attach_texture(texture, attachment=pyglet.gl.GL_COLOR_ATTACHMENT0)
        framebuffer.bind()
        framebuffer_complete = framebuffer.is_complete
        framebuffer.unbind()
        if not framebuffer_complete:
            framebuffer.delete()
            texture.delete()
            self._render_framebuffer = None
            self._render_texture = None
            self._render_target_size = None
            self._failed_render_target_size = target_size
            return

        self._render_texture = texture
        self._render_framebuffer = framebuffer
        self._render_target_size = target_size
        self._failed_render_target_size = None
        self._composite_batch = pyglet.graphics.Batch()
        # Copy the target as is: its alpha was already blended into the colors,
        # and blending it again would darken translucent parts.
        self._composite_sprite = pyglet.sprite.Sprite(
            texture, x=0, y=0, batch=self._composite_batch,
            blend_src=pyglet.gl.GL_ONE, blend_dest=pyglet.gl.GL_ZERO,
        )
        self._update_composite_scale()

    def _update_composite_scale(self):
        if self._composite_sprite is None:
            return
        unit = self.scale / LOW_RESOLUTION_DETAIL_SCALE
        self._composite_sprite.scale = unit
        self._composite_sprite.y = self.window.height - self._render_texture.height * unit

    def _draw_and_flip(self):
        self.window.switch_to()
        if not self._menu_active:
            self._ensure_render_target()
        self._update_composite_scale()
        use_render_target = self._render_framebuffer is not None and not self._menu_active
        projection = self.window.projection
        if use_render_target:
            self._render_framebuffer.bind()
            pyglet.gl.glViewport(0, 0, *self._render_target_size)
            unit = self.scale / LOW_RESOLUTION_DETAIL_SCALE
            width, height = self._render_target_size
            self.window.projection = pyglet.math.Mat4.orthogonal_projection(
                0, width * unit, self.window_height - height * unit,
                self.window_height, -255, 255,
            )
        try:
            self.window.clear()
            self._finish_drawables()
            self.batch.draw()
        finally:
            if use_render_target:
                self._render_framebuffer.unbind()
                self.window.projection = projection
                pyglet.gl.glViewport(0, 0, *self._framebuffer_size())
        if use_render_target:
            self.window.clear()
            self._composite_batch.draw()
        self._text_batch.draw()
        self.window.flip()

    def _pump(self):
        super()._pump()
        self._update_idle_bob()
        self._update_treasure_glow()
        deadline = self._mouse_visible_until
        if deadline is not None and time.monotonic() >= deadline:
            self.window.set_mouse_visible(False)
            self._mouse_visible_until = None
            self._mouse_position = None
            self._resize_redraw_pending = True
        if not self._resize_redraw_pending or not self._stage_input_active:
            return
        self._resize_redraw_pending = False
        if self._last_stage_draw is not None:
            decor, kwargs = self._last_stage_draw
            self.draw_stage(decor=decor, **kwargs)

    def _on_mouse_motion(self, x, y, dx, dy):
        self._mouse_position = (x, y)
        self._mouse_visible_until = time.monotonic() + MOUSE_CURSOR_SECONDS
        self.window.set_mouse_visible(True)
        self._resize_redraw_pending = True

    def _on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        self._on_mouse_motion(x, y, dx, dy)

    def _on_mouse_leave(self, x, y):
        self._mouse_position = None
        self._mouse_visible_until = None
        self.window.set_mouse_visible(False)
        self._resize_redraw_pending = True

    def _hovered_cell(self):
        mouse = self._mouse_position
        if mouse is None or self._menu_active:
            return None
        x, y = mouse
        field_y = self.window_height - y
        if not (0 <= x < self.field_pixel_width
                and 0 <= field_y < self.field_height * self.cell_size_y):
            return None
        col = math.floor((x + self._horizontal_scroll_px) / self.cell_size_x)
        row = math.floor(field_y / self.cell_size_y)
        if 0 <= col < self.field_width:
            return col, row
        return None

    def present_turn(self, result, view):
        self._update_player_facing(result)
        if any(isinstance(event, (FloorChanged, Rewound)) for event in result.events):
            self._standing_turn = view.get('turn')
        # A floor transition draws the next view under its fade-in.
        self._next_view = view
        self._presenting_turn = True
        try:
            if not self._presenter.play(self, result, view):
                return False
            # Defeat effects use the destination frame after the immediate step.
            defeats = [event for event in result.events
                       if isinstance(event, Combat) and event.floor == result.floor_after
                       and (event.boss_at is not None or event.core_at is not None)]
            if defeats and not self._closed:
                self.draw_stage(**view)
            for event in defeats:
                if self._closed:
                    break
                if event.boss_at is not None:
                    self.draw_boss_afterglow(event.boss_at)
                if event.core_at is not None:
                    self.draw_core_burst(event.core_at)
            player = view.get('player')
            if player is not None and player.lp <= 0 and not self._closed:
                self._show_collapse(view)
            return not self._closed
        finally:
            self._next_view = None
            self._presenting_turn = False

    def _show_collapse(self, view):
        """The player has no LP left: let it sink for a moment before the
        final screen shows it collapsed."""
        if (self.combat_effect_seconds == 0 or self.map_mode or view.get('floor_view')
                or 'player collapsed' not in self._sprite_images):
            return
        self._player_sinking = True
        try:
            self.draw_stage(**view)
            self._presenter.hold(self, COLLAPSE_SINK_SECONDS, lambda: [])
        finally:
            self._player_sinking = False

    def _update_player_facing(self, result):
        """Face the last move, even one that left the player in place; face
        the camera again after stairs, a fall or a Loop rewind."""
        if result.move is not None:
            self._player_facing = PLAYER_FACING_BY_MOVE.get(result.move, self._player_facing)
        if any(isinstance(event, (FloorChanged, Rewound)) for event in result.events):
            self._player_facing = 'down'

    def _draw_player(self, pos, player):
        if pos == self._won_chest_cell:
            # Made here, before draw_stage shows the frame, so a redraw never
            # shows the final screen without its glow.
            self.draw_treasure_glow(pos)
        if '@' not in self._sprite_images:
            return super()._draw_player(pos, player)
        if pos == self._won_chest_cell:
            self._draw_sprite(pos, d.CHAR_TREASURE, COLOR_MAP[CI_YELLOW], disc_scale=0.0,
                              layer='chest-back')
        # Low/warning LP colors the ground disc instead of filling the cell;
        # poison turns the disc's upper-right half purple.
        self._player_cell = pos
        _, background = ui_display.player_appearance(player)
        poison = self._tone_color('magenta') if player.item == d.ITEM_POISONED else None
        sprite = self._player_sprite(player)
        # Sinking or collapsed, the player does not hop.
        top = self._draw_sprite(pos, sprite,
                                self._tone_color(background or 'default'), poison,
                                bob=not self._player_sinking and sprite != 'player collapsed',
                                sink=self._bob_offset() if self._player_sinking else 0)
        self._draw_lp_gauge(pos, player, top)

    def _draw_player_wall_break_glyph(self, player):
        return

    def _status_shows_lp_gauge(self):
        # The gauge is drawn over the player instead (see _draw_lp_gauge).
        return '@' not in self._sprite_images

    def _draw_lp_gauge(self, pos, player, head_top):
        """The LP gauge centred just above the player's head (field pixel
        `head_top`), a little narrower than the player's ground disc."""
        unit = self._sprite_unit()
        width = round(LP_GAUGE_WIDTH * 2 * GROUND_DISC_RADIUS * unit)
        height = max(2, round(LP_GAUGE_HEIGHT * unit))
        frame = max(1, round(self.scale))
        cx = self._field_col_x(pos[0]) + self.cell_size_x / 2
        left = round(cx - width / 2)
        top = max(frame, round(head_top - LP_GAUGE_GAP * unit) - height)
        fill = round(width * self._lp_gauge_ratio(player))
        # The frame is four strips, and the fill and empty backing sit side
        # by side so the opaque gauge does not cover any part of itself.
        outer_w = width + 2 * frame
        for x, y, w, h, color in (
                (left - frame, top - frame, outer_w, frame, LP_GAUGE_FRAME),
                (left - frame, top + height, outer_w, frame, LP_GAUGE_FRAME),
                (left - frame, top, frame, height, LP_GAUGE_FRAME),
                (left + width, top, frame, height, LP_GAUGE_FRAME),
                (left, top, fill, height, self._lp_gauge_color(player)),
                (left + fill, top, width - fill, height, LP_GAUGE_BACKING)):
            if w <= 0:
                continue
            bottom = self.window_height - y - h
            alpha = color[3] if len(color) == 4 else 255
            draw_color = self._display_color((*color[:3], round(alpha * LP_GAUGE_OPACITY)))
            signature = ('rectangle', x, bottom, w, h, draw_color, id(self._lp_gauge_group))
            self._draw_bounded_object(
                x, w, signature,
                partial(pyglet.shapes.Rectangle, x, bottom, w, h, color=draw_color,
                        batch=self.batch, group=self._lp_gauge_group),
            )

    def _player_sprite(self, player):
        pose = None if self._idle_bobbing else self._player_walk_pose
        return self._player_pose_sprite(player, self._player_facing, pose)

    def _player_pose_sprite(self, player, facing, pose):
        """The player's image for its sword: a chimera's sword it holds, else
        its own sword, glowing after the Collector Elf's blessing. With no LP
        left, once its last turn has been shown, it lies collapsed."""
        if (player.lp <= 0 and not self._presenting_turn
                and 'player collapsed' in self._sprite_images):
            return 'player collapsed'
        if player.item == d.ITEM_SWORD_X1_5:
            sprite = 'player sword'
        elif player.item == d.ITEM_SWORD_CURSED:
            sprite = 'player cursed sword'
        elif player.elf_stage_flags & d.ELF_STAGE_K_FLAG:
            sprite = 'player blessed'
        else:
            sprite = '@'
        if sprite not in self._sprite_images:
            sprite = '@'
        turned = f'{sprite} {facing}'
        if pose:
            walking = f'{turned} {pose}'
            if walking in self._sprite_images:
                return walking
        return turned if turned in self._sprite_images else sprite

    def _set_scaled_dimensions(self):
        super()._set_scaled_dimensions()
        self.cell_size_x = max(1, round(SPRITE_CELL_SIZE_X * self.scale))
        self.field_pixel_width = self.field_width * self.cell_size_x
        self._select_font_size()
        self._update_strength_column_width()
        self._map_pixel_width = self.field_pixel_width
        if hasattr(self, '_hud_row_height'):
            self._hud_row_height = self._row_height_for_width(self.window_width)
            self.window_height = round(
                self.field_height * self.cell_size_y + 2 * self._hud_row_height
            )
        self.window_width = (
            self._map_pixel_width + FIELD_SIDEBAR_GAP * self.cell_size_x
            + self.strength_column_width
        )
        self.field_pixel_width = max(
            self.cell_size_x, self.window_width - self.strength_column_width
        )
        self._horizontal_scroll_px = 0
        self._camera_follow_player = True
        self._last_camera_player_pos = None

    def _sprite_unit(self):
        """Width that sizes characters, discs and the sidebar (not field cells)."""
        return CELL_SIZE_X * self.scale

    def _select_font_size(self):
        self.font_size = self._font_size_for_cells(self._sprite_unit(), self.cell_size_y)

    def _row_height_for_width(self, width):
        return self._menu_cell_size_y

    def _status_font_scale(self):
        return self._menu_font_size / self.font_size

    def _strength_text_scale(self):
        hud_font_size = (
            self.font_size if self._menu_font_size is None else self._menu_font_size
        )
        return min(STRENGTH_TEXT_SCALE, hud_font_size / self.font_size)

    def _update_strength_column_width(self):
        try:
            font_size = self.font_size * self._strength_text_scale()
            text_width = 2 * max(
                _font_glyph_metrics(self.font_name, font_size, weight)[0]
                for weight in ('normal', 'bold')
            )
        except (AttributeError, OSError, RuntimeError, ValueError):
            text_width = 2 * self._sprite_unit() * self._strength_text_scale()
        self.strength_column_width = math.ceil(
            text_width + STRENGTH_SPRITE_CELLS * self._sprite_unit()
            + 2 * self.strength_column_padding
        )

    def _status_uses_window_width(self):
        return True

    def _status_row_height(self):
        return self._hud_row_height

    def _status_row_y_offset(self, row):
        return -row * self._hud_row_height

    def _update_minimum_window_size(self):
        max_cell_width = CELL_SIZE_X * MAX_UI_SCALE
        max_padding = max(1, round(STRENGTH_COLUMN_PADDING * MAX_UI_SCALE))
        max_strength_width = (
            (2 * STRENGTH_TEXT_SCALE + STRENGTH_SPRITE_CELLS) * max_cell_width
            + 2 * max_padding
        )
        minimum_width = math.ceil(max_strength_width + SPRITE_CELL_SIZE_X * MAX_UI_SCALE)
        minimum_height = math.ceil(
            self.field_height * CELL_SIZE_Y * MIN_UI_SCALE
            + 2 * self._menu_cell_size_y
        )
        self.window.set_minimum_size(
            minimum_width,
            minimum_height,
        )

    def _draw_rect(self, x, y, width, height, color, group=None):
        if (not self._menu_active and not self._drawing_hud
                and not self._intersects_window(x, width)):
            return
        if not self._drawing_hud:
            if (
                x == self.field_pixel_width
                and y == 0
                and width == self.strength_column_width
                and height == self.field_height * self.cell_size_y
            ):
                y_bottom = self.window_height - y - height
                if self.field_pixel_width >= self._map_pixel_width:
                    background = self._display_color((0, 0, 0))
                    signature = ('rectangle', x, y_bottom, width, height,
                                 background, id(self._sidebar_bg_group))
                    self._draw_object(
                        signature,
                        lambda: pyglet.shapes.Rectangle(
                            x, y_bottom, width, height, color=background,
                            batch=self._text_batch, group=self._sidebar_bg_group,
                        ),
                    )

                panel_color = self._display_color((0, 0, 0, TEXT_PANEL_ALPHA))
                signature = ('rectangle', x, y_bottom, width, height,
                             panel_color, id(self._sidebar_group))
                self._draw_object(
                    signature,
                    lambda: pyglet.shapes.Rectangle(
                        x, y_bottom, width, height, color=panel_color,
                        batch=self._text_batch, group=self._sidebar_group,
                    ),
                )
                return
            return super()._draw_rect(x, y, width, height, color, group=group)
        scene_batch = self.batch
        self.batch = self._text_batch
        try:
            return super()._draw_rect(x, y, width, height, color, group=group)
        finally:
            self.batch = scene_batch

    def _draw_line(self, x1, y1, x2, y2, color, thickness=1):
        if self._drawing_hud:
            scene_batch = self.batch
            self.batch = self._text_batch
            try:
                return super()._draw_line(x1, y1, x2, y2, color, thickness)
            finally:
                self.batch = scene_batch

        if not self._intersects_window(min(x1, x2) - thickness,
                                       abs(x2 - x1) + 2 * thickness):
            return

        # Visibility boundaries and other field lines stay above sprites.
        y1, y2 = self.window_height - y1, self.window_height - y2
        draw_color = self._display_color(color)
        signature = ('line', x1, y1, x2, y2, thickness, draw_color,
                     id(self._overlay_group))
        return self._draw_object(
            signature,
            lambda: pyglet.shapes.Line(
                x1, y1, x2, y2, thickness=thickness, color=draw_color,
                batch=self.batch, group=self._overlay_group,
            ),
        )

    def draw_status_bar(self, turn, player, stage_num, message, extra_keys, game_start_turn=None):
        self._drawing_hud = True
        try:
            result = super().draw_status_bar(
                turn, player, stage_num, message, extra_keys, game_start_turn,
            )
            return result
        finally:
            self._drawing_hud = False

    def _on_fullscreen_key_press(self, symbol, modifiers):
        if symbol == pgkey.F11:
            return pyglet.event.EVENT_HANDLED

    def _on_fullscreen_key_release(self, symbol, modifiers):
        if symbol == pgkey.F11:
            self._draw_rebuilding_message()
            self._switching_fullscreen = True
            try:
                if self.window.fullscreen:
                    self.window.set_fullscreen(False)
                else:
                    self.window.set_fullscreen(True, screen=self._windowed_screen())
            finally:
                self._switching_fullscreen = False
            self._draw_rebuilding_message()
            self._on_window_resize(*self.window.get_size())
            if not self._menu_active and not self._stage_input_active:
                self._flip()
            return pyglet.event.EVENT_HANDLED

    def _draw_rebuilding_message(self):
        self.window.switch_to()
        width, height = self.window.get_size()
        message = tr("[Rebuilding display data...]")
        font_name, size_scale = self.font_name, 1.0
        if not message.isascii():
            font_name, size_scale = self._non_ascii_font(self._menu_font_size)
        label = pyglet.text.Label(
            message, font_name=font_name, font_size=self._menu_font_size * size_scale,
            x=width / 2, y=height / 2, anchor_x="center", anchor_y="center",
        )
        try:
            self.window.clear()
            label.draw()
            self.window.flip()
        finally:
            label.delete()

    def _windowed_screen(self):
        window = self.window
        screens = window.display.get_screens()
        if pyglet.compat_platform == "darwin" and not pyglet.options.headless:
            # Cocoa's window location uses the current screen's height.
            native_screen = window._nswindow.screen()
            return next(
                (screen for screen in screens if native_screen
                 and native_screen.isEqual_(screen.get_nsscreen())),
                window.screen,
            )

        location = window.get_location()
        if location is None:
            return window.screen
        x, y = location
        width, height = window.get_framebuffer_size()

        def overlap(screen):
            overlap_width = min(x + width, screen.x + screen.width) - max(x, screen.x)
            overlap_height = min(y + height, screen.y + screen.height) - max(y, screen.y)
            return max(0, overlap_width) * max(0, overlap_height)

        screen = max(screens, key=overlap, default=window.screen)
        return screen if overlap(screen) > 0 else window.screen

    def _on_window_resize(self, width, height):
        if self._switching_fullscreen:
            return
        if (width, height) != (self.window_width, self.window_height):
            # Rebuilding the field for a new size takes a moment.
            self._draw_rebuilding_message()
        old_cell_width = self.cell_size_x
        old_scroll_cells = self._horizontal_scroll_px / old_cell_width
        follow_player = self._camera_follow_player
        last_player_pos = self._last_camera_player_pos
        height_changed = height != self.window_height
        hud_row_height = self._row_height_for_width(width)
        if height_changed:
            self._set_resized_dimensions(width, height, hud_row_height)
            self._non_ascii_font_result = None
            if self._menu_active:
                self._menu_font_resize_pending = True
            else:
                self._select_font_size()
            self._camera_follow_player = follow_player
            self._last_camera_player_pos = last_player_pos
            self._horizontal_scroll_px = old_scroll_cells * self.cell_size_x
        else:
            self.window_width = width
            self.window_height = height
        self._update_strength_column_width()
        self.field_pixel_width = max(
            self.cell_size_x, width - self.strength_column_width
        )
        if self.field_pixel_width >= self._map_pixel_width:
            self._horizontal_scroll_px = 0
            self._camera_follow_player = True
        else:
            min_scroll, max_scroll = self._horizontal_scroll_bounds()
            self._horizontal_scroll_px = min(
                max_scroll,
                max(min_scroll, self._horizontal_scroll_px),
            )
        if self._camera_follow_player and self._last_camera_player_pos is not None:
            self._center_camera_on_player(self._last_camera_player_pos[0])
        self._resize_redraw_pending = True
        if self._menu_active:
            self._redraw_menu_text()

    def _set_resized_dimensions(self, width, height, hud_row_height):
        field_pixel_height = height - 2 * hud_row_height
        self.scale = max(
            MIN_UI_SCALE, field_pixel_height / (self.field_height * CELL_SIZE_Y)
        )
        self.cell_size_x = SPRITE_CELL_SIZE_X * self.scale
        self.cell_size_y = self.scale * CELL_SIZE_Y
        self.font_size = max(1, round(self.cell_size_y * FONT_HEIGHT_RATIO))
        self.strength_column_padding = max(
            1, round(STRENGTH_COLUMN_PADDING * self.scale)
        )
        self._map_pixel_width = self.field_width * self.cell_size_x
        self.window_width = width
        self._hud_row_height = hud_row_height
        # Keep the WM's actual size even below the minimum drawing scale.
        # Requesting another size here can overwrite its restore geometry.
        self.window_height = height

    def _intersects_window(self, left, width):
        # The translucent sidebar still reveals the scene behind it.
        window_width = self.window_width
        # Linear enlargement can sample the adjacent render-target texel.
        guard = self.scale / LOW_RESOLUTION_DETAIL_SCALE
        return window_width is None or (left <= window_width + guard
                                        and left + width >= -guard)

    def _draw_bounded_object(self, left, width, signature, factory):
        if not self._intersects_window(left, width):
            return None
        return self._draw_object(signature, factory)

    def _field_draw_columns(self, width):
        window_width = self.window_width
        if window_width is None:
            return range(width)
        scroll = self._horizontal_scroll_px
        # Include terrain overhang, stair discs and the one-pixel seam overlap.
        margin = max(TERRAIN_SIDE, GROUND_DISC_RADIUS) * self.cell_size_x + 1
        rock = self._sprite_images.get(ROCK_SPRITE)
        if rock is not None:
            padding = max(1, round(self.scale))
            rock_scale = 1.8 * max(1, self._sprite_unit() - 2 * padding) / SPRITE_REFERENCE_PIXELS
            margin = max(margin, rock.width * rock_scale / 2 + 1)
        first = math.floor((scroll - margin) / self.cell_size_x)
        stop = math.ceil((scroll + window_width + margin) / self.cell_size_x)
        return range(max(0, first // 2 * 2), min(width, (stop + 1) // 2 * 2))

    def _field_col_x(self, col):
        return col * self.cell_size_x - self._horizontal_scroll_px

    def _field_text_x_offset(self):
        # Text is sized for a CELL_SIZE_X-wide cell; center it in the wider one.
        return ((self.cell_size_x - self._sprite_unit()) / 2
                - self._horizontal_scroll_px)

    def _horizontal_scroll_bounds(self):
        if self.field_pixel_width >= self._map_pixel_width:
            return (0, 0)
        return (0, max(0, self._map_pixel_width
                       + FIELD_SIDEBAR_GAP * self.cell_size_x - self.field_pixel_width))

    def _center_camera_on_player(self, player_x):
        min_scroll, max_scroll = self._horizontal_scroll_bounds()
        player_center = (player_x + 0.5) * self.cell_size_x
        self._horizontal_scroll_px = min(
            max_scroll,
            max(min_scroll, round(player_center - self.field_pixel_width / 2)),
        )

    def _handle_horizontal_view_key(self, symbol):
        if self.field_pixel_width >= self._map_pixel_width:
            return (0, 0)
        min_scroll, max_scroll = self._horizontal_scroll_bounds()
        direction = -1 if symbol == pyglet.window.key.LEFT else 1
        self._horizontal_scroll_px = min(
            max_scroll,
            max(min_scroll, self._horizontal_scroll_px
                + direction * HORIZONTAL_VIEW_SCROLL_CELLS * self.cell_size_x),
        )
        self._camera_follow_player = False
        return (direction, 0)

    def _draw_strength_entry(self, row, label, is_player):
        # Keep the sidebar at native resolution on top of the composited field.
        scene_batch = self.batch
        self.batch = self._text_batch
        try:
            return self._draw_strength_entry_content(row, label, is_player)
        finally:
            self.batch = scene_batch

    def _draw_strength_entry_content(self, row, label, is_player):
        """A small label on the left, and the character's sprite to its right.

        Labels such as "b'" show the base character with its rank mark. A
        monster type shows its sprite only once identified, as on the field.
        """
        left = self.field_pixel_width + self.strength_column_padding
        self._draw_text((0, row), label, COLOR_MAP["default"], bold=is_player,
                        x_offset=left, size_scale=self._strength_text_scale(),
                        group=self._overlay_group)
        base, mark = label[0], label[1:]
        type_key = base + {"'": '2', '"': '3'}.get(mark, '')
        if base not in self._sprite_images or not (is_player or type_key in self._known_types):
            return
        images = self._gray_images if self.map_mode else self._sprite_images
        picture = images[base]
        box_width = STRENGTH_SPRITE_CELLS * self._sprite_unit()
        padding = max(1, round(self.scale))
        scale = 1.8 * max(1, self._sprite_unit() - 2 * padding) / SPRITE_REFERENCE_PIXELS
        cx = (self.field_pixel_width + self.strength_column_width
              - self.strength_column_padding - box_width / 2)
        cy = self.window_height - (row + 0.5) * self.cell_size_y
        left, bottom = cx - picture.width * scale / 2, cy - picture.height * scale / 2
        tint = self._display_color((255, 255, 255))
        signature = ('sprite', id(picture), left, bottom, scale, scale,
                     id(self._overlay_group), tint)
        sprite = self._draw_object(
            signature,
            lambda: pyglet.sprite.Sprite(
                picture, x=left, y=bottom, batch=self.batch, group=self._overlay_group,
            ),
        )
        self._set_drawable_attribute(sprite, 'scale', scale)
        self._set_drawable_attribute(sprite, 'color', tint)
        if mark in self._mark_images:
            # The rank mark at the sprite's right, at the field's scale, kept
            # within the entry's own row.
            image = self._mark_images[mark]
            badge_scale = scale
            badge_x = cx + min(box_width, picture.width * scale) / 2 - image.width * badge_scale / 2
            badge_y = cy - image.height * badge_scale / 2
            badge_color = self._display_color(COLOR_MAP['default'])
            signature = ('sprite', id(image), badge_x, badge_y, badge_scale, badge_scale,
                         id(self._overlay_group), badge_color)
            badge = self._draw_object(
                signature,
                lambda: pyglet.sprite.Sprite(
                    image, x=badge_x, y=badge_y,
                    batch=self.batch, group=self._overlay_group,
                ),
            )
            self._set_drawable_attribute(badge, 'scale', badge_scale)
            self._set_drawable_attribute(badge, 'color', badge_color)

    def _clear_drawables(self):
        for drawable in self._uncached_drawables:
            drawable.delete()
        self._uncached_drawables = []
        self._treasure_glow = None
        self._bobbing = []
        super()._clear_drawables()
        self._sprite_cells.clear()
        self._player_cell = None
        self._fallen_rock_draws = ()
        self._respawn_draws = ()
        self._respawn_columns_drawn = frozenset()
        self._field_text_cells = frozenset()
        self._floor_cells = {}
        self._edge_shade_pending = False
        self._floor_backdrop_pending = False

    def _retain_drawable(self, signature):
        return signature[0] in {
            'tile', 'floor-copy', 'floor-backdrop', 'terrain-cell',
            'wall-cell', 'barrier-cell', 'edge-shade',
        }

    def _draw_object(self, signature, factory):
        if self._retain_drawable(signature):
            return super()._draw_object(signature, factory)
        drawable = factory()
        self._uncached_drawables.append(drawable)
        self._drawables.append(drawable)
        return drawable

    def _finish_drawables(self):
        if self._frame_drawable_cache is None:
            return
        occupied = set(self._sprite_cells) | self._field_text_cells | {self._player_cell}
        for pos in self._fallen_rock_draws:
            if pos not in occupied:
                self._draw_terrain(pos, d.DECOR_FALLEN_ROCKS, 'wall')
        for x, y in self._respawn_draws:
            if (x, y) not in self._respawn_columns_drawn:
                self._draw_respawn_column(self._field_col_x(x) + self.cell_size_x / 2,
                                          (y + 0.5) * self.cell_size_y, 1.0, y,
                                          RESPAWN_COLUMN_UNSEEN_COLOR)
        if self._floor_backdrop_pending:
            self._draw_floor_backdrop()
        if self._floor_cells:
            self._draw_floor_tiles()
        if self._edge_shade_pending:
            self._edge_shade_pending = False
            self._draw_edge_shade()
        super()._finish_drawables()

    def _progress_mark_group(self):
        return self._text_overlay_group

    def _progress_mark_x_offset(self):
        return max(1, round(TEXT_PANEL_PADDING * self._menu_scale))

    def _field_overlay_font_scale(self):
        return self._status_font_scale()

    def _field_overlay_cell_width(self):
        return self._menu_cell_size_x

    def _draw_progress_panel(self, marks):
        if not marks:
            return
        cells = sum(len(label) + 1 for label, _ in marks) - 1
        self._draw_text_panel('progress', 0, cells * self._menu_cell_size_x)

    def _floor_label_group(self):
        return self._text_overlay_group

    def _draw_floor_label_panel(self, label, x, width):
        self._draw_text_panel('floor', x, width)

    def _draw_dialogue_panel(self, x, y, width, height):
        if width > 0 and height > 0:
            # Drawn with the HUD, under its text.
            drawing_hud, self._drawing_hud = self._drawing_hud, True
            try:
                self._draw_rect(
                    x,
                    y,
                    width,
                    height,
                    (0, 0, 0, TEXT_PANEL_ALPHA),
                    group=self._overlay_group,
                )
            finally:
                self._drawing_hud = drawing_hud

    def _draw_text_panel(self, kind, x, width):
        padding = max(1, round(TEXT_PANEL_PADDING * self._menu_scale))
        left = max(0, x - padding)
        row = self.field_height - 1
        top = self.window_height - row * self.cell_size_y
        bottom = top - self._menu_font_size - padding
        panel_width = width + 2 * padding
        height = self._menu_font_size + 2 * padding
        color = (0, 0, 0, TEXT_PANEL_ALPHA)
        signature = ('text-panel', kind, left, bottom, panel_width, height, color,
                     id(self._text_panel_group))
        batch = self._text_batch
        self._draw_object(
            signature,
            lambda: pyglet.shapes.Rectangle(
                left, bottom, panel_width, height, color=color, batch=batch,
                group=self._text_panel_group,
            ),
        )

    def _draw_golem_rubble(self, pos, visible):
        pass

    def _draw_member(self, glyph):
        name = (None if glyph.member_role == d.MEMBER_JAVELIN_ELF
                else self._member_variants.get(glyph.char))
        key = ("J" if glyph.member_role == d.MEMBER_JAVELIN_ELF else
               CAT_SPRITE if glyph.char == 'Y' else
               f'{name}-{self._member_skins[glyph.char]}' if name else None)
        if key not in self._sprite_images:
            return super()._draw_member(glyph)
        color = self._tone_color('default')
        if glyph.member_role == d.MEMBER_JAVELIN_ELF:
            self._enlarge_neighbors = False
        try:
            # Followers stay still, smaller and with a faded outline; members
            # waiting to be met hop.
            self._draw_sprite((glyph.x, glyph.y), key, color,
                              disc_scale=0.0 if glyph.tone == 'member' else 1.0,
                              bob=glyph.tone == 'member_waiting',
                              follower=glyph.tone == 'member')
        finally:
            self._enlarge_neighbors = True

    def _loop_trail_group(self, y):
        return self._row_group(y, 'mark')

    def _draw_field_text(self, pos, text, color, bold=False):
        x, y = pos
        if text == d.CHAR_DUNGEON_CORE and self._dungeon_core_images:
            self._draw_dungeon_core(pos)
            return
        if text == d.CHAR_BARRIER and self._floor_images is not None:
            return  # shown by the barrier light itself
        if text in self._mark_images and (x - 1, y) in self._sprite_cells:
            return self._draw_rank_mark((x - 1, y), text, color)
        self._field_text_cells = self._field_text_cells | {pos}
        if text not in self._sprite_images:
            if self.window_width is not None:
                left = x * self.cell_size_x + self._field_text_x_offset()
                padding = self.cell_size_x
                if not self._intersects_window(left - padding,
                                               self._text_width(text, bold) + 2 * padding):
                    return
            return super()._draw_field_text((x, y - FIELD_TEXT_RAISE), text, color, bold)
        tribe = d.CHAR_TO_MONSTER_TRIBE.get(text)
        met_elf = tribe is not None and tribe.is_elf and not bold
        # Monsters (elves included), fairies, and unidentified characters hop;
        # treasure chests stay still.
        bob = (text in d.CHAR_TO_MONSTER_TRIBE or text in d.CHAR_TO_FAIRY_TRIBE
               or text in UNKNOWN_SPRITES)
        self._draw_sprite(pos, text, color, shade=MET_ELF_SHADE if met_elf else 1.0,
                          bob=bob)

    def _draw_dungeon_core(self, pos):
        x, y = pos
        image = self._dungeon_core_images[self._dungeon_core_growth]
        cx = self._field_col_x(x) + self.cell_size_x / 2
        cy = (y + 0.5) * self.cell_size_y
        shade = 1.0 if self._cur_torched is not None and self._cur_torched[y][x] else TERRAIN_EXPLORED_SHADE
        glow = self._display_color(tuple(round(c * shade) for c in COLOR_MAP[CI_YELLOW]))
        self._draw_ground_disc(cx, cy, GROUND_DISC_RADIUS * self._sprite_unit(), glow)
        cells = self._dungeon_core_cells
        width = (cells * DUNGEON_CORE_CELL_UNITS
                 * max(1, self._sprite_unit() - 2 * max(1, round(self.scale))))
        factor = width / (cells * self.cell_size_x)
        left = self._field_col_x(x) + (self.cell_size_x - width) / 2
        bottom = self.window_height - (
            y + 0.5 + (0.5 + self._dungeon_core_under) * factor
        ) * self.cell_size_y
        scale_x = width / image.width
        scale_y = (
            (1 + self._dungeon_core_under + self._dungeon_core_overhang)
            * self.cell_size_y * factor
            / image.height
        )
        tint = self._display_color((255, 255, 255))
        group = self._row_group(y, 'wall')
        signature = ('dungeon-core', id(image), left, bottom, scale_x, scale_y,
                     id(group), tint)
        sprite = self._draw_bounded_object(
            left, width, signature,
            lambda: pyglet.sprite.Sprite(image, x=left, y=bottom,
                                         batch=self.batch, group=group),
        )
        self._set_drawable_attribute(sprite, 'scale_x', scale_x)
        self._set_drawable_attribute(sprite, 'scale_y', scale_y)
        self._set_drawable_attribute(sprite, 'color', tint)

    def _draw_rank_mark(self, pos, mark, color):
        """Tinted 3D apostrophe(s) at the upper right of the sprite in `pos`."""
        x, y = pos
        image = self._mark_images[mark]
        size = self._sprite_cells[pos]
        padding = max(1, round(self.scale))
        scale = size * 1.8 * max(1, self._sprite_unit() - 2 * padding) / SPRITE_REFERENCE_PIXELS
        dx, dy = (size * offset for offset in MARK_OFFSET)
        left = (self._field_col_x(x) + 0.5 * self.cell_size_x + dx * self._sprite_unit()
                - image.width * scale / 2)
        bottom = self.window_height - (y + 0.5 - dy) * self.cell_size_y - image.height * scale / 2
        group = self._row_group(y, 'hover-mark' if pos == self._hovered_cell() else 'mark')
        # White like the strength column, not the strength color; only the
        # half-bright dimming of the glyph is kept.
        white = COLOR_MAP['default']
        dimmed = color in {self._dim_color(value) for value in COLOR_MAP.values()}
        tint = self._display_color(self._dim_color(white) if dimmed else white)
        signature = ('sprite', id(image), left, bottom, scale, scale, id(group), tint)
        sprite = self._draw_bounded_object(
            left, image.width * scale, signature,
            lambda: pyglet.sprite.Sprite(
                image, x=left, y=bottom, batch=self.batch, group=group,
            ),
        )
        self._set_drawable_attribute(sprite, 'scale', scale)
        self._set_drawable_attribute(sprite, 'color', tint)

    def _draw_fairy_slot(self, pos, char):
        if char not in self._sprite_images:
            return super()._draw_fairy_slot(pos, char)
        x, y = pos
        dx, dy = FAMILIAR_OFFSET
        cx = self._field_col_x(x - 1) + 0.5 * self.cell_size_x + dx * self._sprite_unit()
        cy = (y + 0.5 - dy) * self.cell_size_y
        self._place_sprite(char, cx, cy, FAMILIAR_SIZE, y, 'familiar', dimmed=False)
        self._draw_pillar(cx, cy, FAMILIAR_SIZE, y, COLOR_MAP[CI_GREEN], familiar=True)

    def _neighbor_of_player(self, pos):
        if not self._enlarge_neighbors or self._player_cell is None:
            return False
        px, py = self._player_cell
        return abs(pos[0] - px) + abs(pos[1] - py) == 1

    def _draw_sprite(self, pos, text, color, upper_right_color=None, shade=1.0, disc_scale=1.0,
                     bob=False, follower=False, layer=None, sink=0):
        x, y = pos
        cx, cy = self._field_col_x(x) + self.cell_size_x / 2, (y + 0.5) * self.cell_size_y
        dimmed = color in {self._dim_color(value) for value in COLOR_MAP.values()}
        if self.map_mode and max(color) <= 128 and max(color) - min(color) <= 16:
            # Map sprites use a grey texture. Preserve the half-bright marker
            # for dim neutral colors supplied by callers outside COLOR_MAP.
            dimmed = True
        if follower:
            size = FOLLOWER_SCALE
        else:
            size = NEIGHBOR_SCALE if self._neighbor_of_player(pos) else 1.0
        hovered = pos == self._hovered_cell()
        if hovered:
            size *= HOVER_SCALE
        glow = color if text in UNKNOWN_SPRITES else None
        top = self._place_sprite(text, cx, cy, size, y,
                                 layer or ('hover' if hovered else 'sprite'), dimmed, shade, glow,
                                 bob=bob and not self.map_mode and self._in_view(pos),
                                 follower=follower, sink=sink)
        if hovered:
            self._draw_hover_name(pos, text, top)
        self._sprite_cells[pos] = size
        if text in d.CHAR_TO_FAIRY_TRIBE:
            green = COLOR_MAP[CI_GREEN]
            self._draw_pillar(cx, cy, size, y, self._dim_color(green) if dimmed else green)
        elif text in UNKNOWN_SPRITES:
            self._draw_pillar(cx, cy, size, y,
                              tuple(round(c * shade * UNKNOWN_PILLAR) for c in color))
        tribe = d.CHAR_TO_MONSTER_TRIBE.get(text)
        if (upper_right_color is None and tribe is not None
                and tribe.effect == d.EFFECT_UNLOCK_TREASURE
                and color in (COLOR_MAP[CI_YELLOW], self._dim_color(COLOR_MAP[CI_YELLOW]))):
            # A beatable boss: blue like any beatable monster, with the
            # upper-right half yellow for the treasure it unlocks.
            blue = COLOR_MAP[CI_BLUE]
            color, upper_right_color = self._dim_color(blue) if dimmed else blue, color
        # Keep the original semantic color (strength, poison, etc.) readable
        # as a glowing disc on the ground the character stands on.
        if text in UNKNOWN_SPRITES:
            reference = COLOR_MAP[UNKNOWN_DISC_REFERENCE]
            if dimmed:
                reference = self._dim_color(reference)
            shade *= min(1.0, _luminance(reference) / max(_luminance(color), 1))
        color = tuple(round(c * shade) for c in color)
        if disc_scale:
            self._draw_ground_disc(cx, cy, disc_scale * GROUND_DISC_RADIUS * self._sprite_unit(),
                                   color, upper_right_color)
            if pos in self._respawn_draws:
                self._draw_respawn_column(cx, cy, size, y, color)
                self._respawn_columns_drawn = self._respawn_columns_drawn | {pos}
        return top

    def _draw_hover_name(self, pos, text, head_top):
        if text in UNKNOWN_SPRITES:
            return
        name = tr(SPRITE_NAMES[text]) if text in SPRITE_NAMES else text
        size_scale = self._status_font_scale() * MESSAGE_FONT_SIZE_SCALE
        font_size = self.font_size * size_scale
        font_name = self.font_name
        if not name.isascii():
            font_name, ratio = self._non_ascii_font(self.font_size)
            font_size *= ratio
        cx = self._field_col_x(pos[0]) + self.cell_size_x / 2
        bottom = self.window_height - head_top + LP_GAUGE_GAP * self._sprite_unit()
        anchor_y = 'bottom'
        # The first walkable row sits just below the dungeon's top wall.
        if pos[1] <= 1:
            bottom = (self.window_height - (pos[1] + 0.5) * self.cell_size_y
                      - LP_GAUGE_GAP * self._sprite_unit())
            anchor_y = 'top'
        group = self._row_group(pos[1], 'hover-name')
        color = (*self._display_color(COLOR_MAP['default']), 255)
        signature = ('hover-name', name, font_name, font_size, cx, bottom,
                     anchor_y, color, id(group))
        self._draw_object(
            signature,
            lambda: pyglet.text.Label(
                name, font_name=font_name, font_size=font_size,
                weight='bold',
                x=cx, y=bottom, anchor_x='center', anchor_y=anchor_y,
                color=color, batch=self._text_batch, group=group,
            ),
        )

    def _place_sprite(self, text, cx, cy, size, row, layer, dimmed, shade=1.0, glow=None,
                      bob=False, follower=False, sink=0):
        """Draw a character image with its feet at field pixel (cx, cy); returns
        the field pixel y of the top of the character in it. `sink` lowers the
        image alone by that many pixels; the returned top stays put.

        With `glow`, the image is tinted slightly (UNKNOWN_TINT) toward that color.
        """
        images = self._gray_images if self.map_mode else self._sprite_images
        swapped = THEME_SPRITES.get(self._terrain_theme, {}).get(text)
        if swapped in images:
            text = swapped
        picture = self._follower_image(text) if follower else images[text]
        padding = max(1, round(self.scale))
        width = max(1, self._sprite_unit() - 2 * padding)
        scale = size * 1.8 * width / SPRITE_REFERENCE_PIXELS
        left = cx - picture.width * scale / 2
        bottom = (self.window_height - cy - (picture.height / 2 - SPRITE_GROUND_OFFSET_PIXELS) * scale
                  - sink)
        group = self._row_group(row, layer)
        tint = ((128, 128, 128) if dimmed else
                (round(255 * shade),) * 3 if shade < 1 else (255, 255, 255))
        if glow is not None:
            peak = max(max(glow), 1)
            tint = tuple(round(t * (1 - UNKNOWN_TINT + UNKNOWN_TINT * g / peak))
                         for t, g in zip(tint, glow))
        tint = self._display_color(tint)
        signature = ('sprite', id(picture), left, bottom, scale, scale, id(group), tint)
        sprite = self._draw_bounded_object(
            left, picture.width * scale, signature,
            lambda: pyglet.sprite.Sprite(
                picture, x=left, y=bottom, batch=self.batch, group=group,
            ),
        )
        self._set_drawable_attribute(sprite, 'scale', scale)
        self._set_drawable_attribute(sprite, 'color', tint)
        if bob and sprite is not None:
            # Only the character hops; its disc and pillar stay on the ground.
            self._bobbing.append((sprite, bottom))
            if self._bob_raised:
                sprite.y = bottom + self._bob_offset()
        head_room = self._sprite_head_room.get(text, 0)
        return cy - (picture.height / 2 + SPRITE_GROUND_OFFSET_PIXELS - head_room) * scale

    def _draw_pillar(self, cx, cy, size, row, color, familiar=False):
        """Additive light cylinder around a fairy: far wall behind, near wall over it."""
        for side in ('back', 'front'):
            self._draw_light_wall(self._pillar_images[side], side, cx, cy,
                                  size * PILLAR_RADIUS, size * PILLAR_HEIGHT, row, color,
                                  familiar)

    def _draw_respawn_column(self, cx, cy, size, row, color):
        """Swirled light column of a respawned character, in its ground disc's main color.

        The space between the bands takes a dimmer copy of that color.
        """
        gap_color = tuple(round(c * RESPAWN_COLUMN_GAP_SHADE) for c in color)
        for side in ('back', 'front'):
            for gaps, tint in ((False, color), (True, gap_color)):
                self._draw_light_wall(self._respawn_column_images[side, gaps], side, cx, cy,
                                      size * RESPAWN_COLUMN_RADIUS,
                                      size * RESPAWN_COLUMN_HEIGHT, row, tint)

    def _draw_light_wall(self, image, side, cx, cy, radius, height, row, color,
                         familiar=False):
        """One additive wall of a light cylinder; radius and height in cell widths."""
        unit = self._sprite_unit()
        radius *= unit
        layer = 'pillar-back' if side == 'back' else 'pillar-front'
        left = cx - radius
        bottom = self.window_height - cy - radius * GROUND_DISC_FLATTEN
        scale_x = 2 * radius / image.width
        scale_y = (height * unit + 2 * radius * GROUND_DISC_FLATTEN) / image.height
        group = self._row_group(row, 'familiar-front' if familiar and side == 'front'
                                else layer)
        tint = self._display_color(color)
        signature = ('sprite', id(image), left, bottom, scale_x, scale_y,
                     id(group), pyglet.gl.GL_SRC_ALPHA, pyglet.gl.GL_ONE, tint)
        pillar = self._draw_bounded_object(
            left, image.width * scale_x, signature,
            partial(
                pyglet.sprite.Sprite, image, x=left, y=bottom,
                blend_src=pyglet.gl.GL_SRC_ALPHA, blend_dest=pyglet.gl.GL_ONE,
                batch=self.batch, group=group,
            ),
        )
        self._set_drawable_attribute(pillar, 'scale_x', scale_x)
        self._set_drawable_attribute(pillar, 'scale_y', scale_y)
        self._set_drawable_attribute(pillar, 'color', tint)

    def _draw_ground_disc(self, cx, cy, radius, color, upper_right_color=None, opacity=255):
        """A disc seen at the sprites' 60-degree view, fading outward, below the sprite.

        With `upper_right_color`, that half of the disc takes the second color.
        """
        if upper_right_color is None:
            parts = [(self._disc_image, color)]
        else:
            parts = list(zip(self._disc_halves, (color, upper_right_color)))
        ry = radius * GROUND_DISC_FLATTEN
        for image, tint in parts:
            left, bottom = cx - radius, self.window_height - cy - ry
            scale_x = 2 * radius / image.width
            scale_y = 2 * ry / image.height
            draw_tint = self._display_color(tint)
            signature = ('sprite', id(image), left, bottom, scale_x, scale_y,
                         id(self._disc_group), draw_tint, opacity)
            disc = self._draw_bounded_object(
                left, image.width * scale_x, signature,
                partial(
                    pyglet.sprite.Sprite, image, x=left, y=bottom,
                    batch=self.batch, group=self._disc_group,
                ),
            )
            self._set_drawable_attribute(disc, 'scale_x', scale_x)
            self._set_drawable_attribute(disc, 'scale_y', scale_y)
            self._set_drawable_attribute(disc, 'color', draw_tint)
            self._set_drawable_attribute(disc, 'opacity', opacity)
