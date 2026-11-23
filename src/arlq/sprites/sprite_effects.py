"""Combat and floor transition effects for the sprite frontend."""

import math
import random
import time
from pathlib import Path

import pyglet

from .. import defs as d
from ..pyglet_funcs import CI_GREEN, COLOR_MAP
from .sprite_defs import (
    NEIGHBOR_SCALE,
    SPRITE_GROUND_OFFSET_PIXELS,
    SPRITE_REFERENCE_PIXELS,
    TERRAIN_OVERHANG,
    TERRAIN_SIDE,
    TERRAIN_TINT,
)

# The slash of a won fight, cut the way the player attacked: slash.png is
# the cut of an attack up the screen (see build-slash.py).
SLASH_FILES = {'up': 'slash.png', 'down': 'slash-down.png',
               'left': 'slash-left.png', 'right': 'slash-right.png'}
# Between floors (draw_floor_transition): a near-black field with only the
# player, standing on the landing of a floating switchback when taking stairs
# (gold), both the size they are in play and on the cell the player left
# from, where the stairs or pit were on screen. The landing image covers that
# cell like the up stairs' image; the player's feet go LANDING_FEET_HEIGHT cell heights
# above its south edge, the height of the landing's tread. Climbing out of a
# pit, a rope segment ROPE_LENGTH times the player's height, the color of the
# Dungeon Explorer's hemp rope, is drawn over the player: ROPE_WIDTH cell
# widths wide and ROPE_OFFSET right of its centre. Behind the player, a faint
# glow in the green of discovered passages' floor light runs along the rope:
# the ground disc's fading image stretched ROPE_GLOW_WIDTH cell widths wide
# and ROPE_GLOW_LENGTH times the rope's length, at ROPE_GLOW_OPACITY.
TRANSITION_BACKGROUND = (6, 6, 8)
# The floor transition's timeline, as fractions of its set time: the old
# floor fades to black over the first FLOOR_TRANSITION_FADE, the player then
# moves at a steady speed, and over the last FLOOR_TRANSITION_FADE the new
# floor, already drawn underneath, fades in from black. On stairs and the
# rope the player moves FLOOR_TRANSITION_STEP cells up or down (down a
# staircase it dims to FLOOR_TRANSITION_STAIRS_DIM, up one it brightens from
# it). The stairs turn back at the landing like a "く", so on them the
# player first goes up or down to the right, out to
# FLOOR_TRANSITION_STAIRS_SIDE cells, and then back to the left. A fall
# covers FLOOR_TRANSITION_FALL cells in the same time, so it looks fast, and
# the player shrinks to FLOOR_TRANSITION_FALL_SHRINK and fades out.
FLOOR_TRANSITION_FADE = 0.15
FLOOR_TRANSITION_STEP = 0.25
FLOOR_TRANSITION_STAIRS_SIDE = 0.125
FLOOR_TRANSITION_FALL = 0.5
FLOOR_TRANSITION_STAIRS_DIM = 0.4
FLOOR_TRANSITION_FALL_SHRINK = 0.7
LANDING_FEET_HEIGHT = 0.725
ROPE_COLOR = (160, 134, 96)
ROPE_WIDTH, ROPE_OFFSET, ROPE_LENGTH = 0.08, 0.1, 2.0
ROPE_GLOW_WIDTH, ROPE_GLOW_LENGTH, ROPE_GLOW_OPACITY = 0.9, 1.3, 90
# A defeated Vortex (draw_vortex_effect): its storm (vortex-storm.png, see
# build-vortex-storm.py) is shown over the floor for VORTEX_SECONDS_FACTOR
# times the combat effect's time, the funnel's eye, VORTEX_STORM_FOOT of the
# image's height below its centre, on the Vortex's cell. The storm's reach,
# VORTEX_STORM_REACH of the image's width from the eye, is drawn
# VORTEX_RADIUS_RATIO the size of the area the Vortex rearranges.
VORTEX_STORM_REACH = 1.0 / 2.6
VORTEX_STORM_FOOT = 0.07
VORTEX_RADIUS_RATIO = 1 / 4
VORTEX_SECONDS_FACTOR = 4 / 3


# Iris's ration rises glowing above her as she hands it over. The image is
# picked with Python's random, never the game's.
IRIS_RATION_SECONDS = 0.7
IRIS_RATION_FILES = ('ration-hyorogan.png', 'ration-hardtack.png', 'ration-jerky.png')
IRIS_RATION_SIZE = 1.5  # sprite units
IRIS_RATION_HEIGHT = (1.0, 1.4)  # cells above her cell's centre, rising
IRIS_RATION_GLOW_COLOR = (255, 214, 120)
IRIS_RATION_GLOW_SIZE = 2.6  # sprite units
IRIS_RATION_SPARKS = 12

# A stage boss's afterglow (draw_boss_afterglow), over BOSS_AFTERGLOW_SECONDS
# on the cell where it fell: a pillar of BOSS_AFTERGLOW_COLOR light, a
# brighter BOSS_AFTERGLOW_CORE_COLOR core inside it, shoots up
# BOSS_PILLAR_HEIGHT cells over the first BOSS_PILLAR_RISE, then slowly
# narrows and fades; a ring spreads over the ground out to BOSS_RING_RADIUS
# cell widths; and BOSS_SPARKS sparks drift up from the cell, starting over
# the first BOSS_SPARK_DELAY, each living BOSS_SPARK_LIFE of the time.
# All are drawn additively, at BOSS_AFTERGLOW_OPACITY so they stay a little
# see-through.
BOSS_AFTERGLOW_SECONDS = 14 / 15
BOSS_AFTERGLOW_OPACITY = 0.6
BOSS_AFTERGLOW_COLOR = (255, 196, 110)
BOSS_AFTERGLOW_CORE_COLOR = (255, 238, 200)
BOSS_PILLAR_WIDTH, BOSS_PILLAR_CORE_WIDTH = 1.8, 0.4  # cell widths
BOSS_PILLAR_HEIGHT, BOSS_PILLAR_RISE = 5.0, 0.15
BOSS_RING_RADIUS, BOSS_RING_SEGMENTS = 2.4, 40
BOSS_SPARKS, BOSS_SPARK_DELAY, BOSS_SPARK_LIFE = 30, 0.5, (0.35, 0.5)
BOSS_SPARK_HEIGHT = (2.0, 4.5)  # cells


# A destroyed Dungeon Core (draw_core_burst), over CORE_BURST_SECONDS on its
# cell: a dark, see-through hemisphere (dome_images), its rim glowing in
# CORE_BURST_RIM_COLOR, swells to CORE_BURST_RADIUS cell widths over the
# first CORE_BURST_SWELL, then comes apart into CORE_BURST_PUFFS puffs of
# dark mist and CORE_BURST_MOTES violet motes drifting out from its surface
# as it fades. The dome is at most CORE_BURST_OPACITY opaque, thinning to
# CORE_BURST_THIN of that as it swells; each puff
# CORE_BURST_PUFF_OPACITY.
CORE_BURST_SECONDS = 1.0
CORE_BURST_RADIUS = 4.0
CORE_BURST_SWELL = 0.35
CORE_BURST_OPACITY = 0.75
CORE_BURST_THIN = 0.5
# The dome's violet glow is drawn at CORE_BURST_GLOW_OPACITY.
CORE_BURST_GLOW_OPACITY = 0.6
CORE_BURST_RIM_COLOR = (170, 90, 255)
CORE_BURST_PUFFS, CORE_BURST_MOTES = 48, 28
CORE_BURST_PUFF_OPACITY = 0.45
# The puffs and motes are drawn at CORE_BURST_PARTICLE_OPACITY and drift and
# grow CORE_BURST_PARTICLE_SPREAD as far as their own figures say.
CORE_BURST_PARTICLE_OPACITY = 0.6
CORE_BURST_PARTICLE_SPREAD = 0.5
DOME_ELEVATION = math.radians(60)  # the character sprites' view
# The dome's band of light is CORE_BURST_BAND cell widths wide, from thick
# while the dome is small to thin once it has swollen; the glow image whose
# band (a fraction of the radius, DOME_GLOW_BANDS) comes closest is used.
CORE_BURST_BAND = (0.9, 0.15)
DOME_GLOW_BANDS = tuple(0.03 * 1.4 ** k for k in range(10))


# A won stage's treasure glow (draw_treasure_glow), shown for as long as the
# final screen stays up, centred on the chest's cell: a hazy hemisphere of
# TREASURE_GLOW_COLOR light (soft_dome_image, brightest inside and fading
# out toward its outline) TREASURE_GLOW_RADIUS cell widths across swells up
# over TREASURE_GLOW_SWELL seconds and then breathes, its brightness swaying
# TREASURE_GLOW_BREATH over TREASURE_GLOW_BREATH_SECONDS. Inside it
# TREASURE_MOTES glowing motes float about: each rises and wanders for
# TREASURE_MOTE_LIFE seconds, fading in and out, and then starts again
# somewhere else in the dome; while it floats its light gently swells and
# ebbs (TREASURE_MOTE_SHIMMER). Frames are redrawn at most
# TREASURE_GLOW_FPS times a second.
TREASURE_GLOW_COLOR = (255, 200, 100)
TREASURE_MOTE_COLORS = ((255, 244, 210), (255, 214, 120))
TREASURE_GLOW_RADIUS = 5.0
TREASURE_GLOW_SWELL = 0.9
TREASURE_GLOW_OPACITY = 0.5
TREASURE_GLOW_BREATH, TREASURE_GLOW_BREATH_SECONDS = 0.15, 2.6
TREASURE_MOTES = 34
TREASURE_MOTE_LIFE = (2.5, 4.5)
TREASURE_MOTE_HALO = (0.1, 0.18)  # cell widths, the soft light around a mote
TREASURE_MOTE_RISE = (0.25, 0.55)  # dome radii over a mote's life
TREASURE_MOTE_SHIMMER = 0.35
TREASURE_GLOW_FPS = 30

# The Stage 6 Dungeon Core running wild at the time limit
# (draw_core_calamity): over CORE_CALAMITY_SECONDS the core blazes up while
# arms of black smoke, rimmed with violet light, reach out from it and
# scatter away (assets/effects/core-calamity, see build-core-calamity.py:
# each frame's smoke drawn over the floor, its glow and lightning added as
# light). The eye of the arms, CORE_CALAMITY_FOOT of an image's height below
# its centre, is on the core's cell; a full arm, CORE_CALAMITY_REACH of an
# image's width from the eye, reaches CORE_CALAMITY_REACH_CELLS cell widths
# across the floor (less up and down the screen, like the Vortex's storm).
# The core's own blaze (a hazy dome of CORE_CALAMITY_GLOW_COLOR light
# CORE_CALAMITY_GLOW_RADIUS cell widths across) swells to its full over the
# first CORE_CALAMITY_BLAZE of the time, as the arms reach out, and eases to
# CORE_CALAMITY_GLOW_END while they scatter.
CORE_CALAMITY_SECONDS = 1.5
CORE_CALAMITY_FRAMES = 20
CORE_CALAMITY_FOOT = 0.010353
CORE_CALAMITY_REACH = 1 / 3
CORE_CALAMITY_REACH_CELLS = 8
CORE_CALAMITY_GLOW_COLOR = (225, 175, 255)
CORE_CALAMITY_GLOW_RADIUS = 4.0
CORE_CALAMITY_GLOW_OPACITY = 0.6
CORE_CALAMITY_BLAZE = 0.4
CORE_CALAMITY_GLOW_END = 0.7


def dome_images(size=128, bands=DOME_GLOW_BANDS):
    """A unit hemisphere on the ground seen DOME_ELEVATION down: a dark
    see-through shell (darker toward its outline and its foot), and for
    each band width in `bands` (a fraction of the radius) a white glow
    along its outline and the near side of its foot that wide, with a soft
    sheen on its upper left. The anchor is on the centre of its foot."""
    sin_e, cos_e = math.sin(DOME_ELEVATION), math.cos(DOME_ELEVATION)
    light_dir = (-0.55, 0.0, 0.83)
    width, height = size, round(size / 2 * (1 + sin_e))
    shell = bytearray()
    glows = {band: bytearray() for band in bands}
    for row in range(height):
        sy = (row + 0.5) / height * (1 + sin_e) - sin_e  # up the screen
        for col in range(width):
            sx = (col + 0.5) / width * 2 - 1
            inside = 1 - sx * sx - sy * sy
            depth = math.sqrt(inside) if inside > 0 else -1.0
            foot = sx * sx + (sy / sin_e) ** 2  # < 1 inside the dome's foot
            dark = shine = 0.0
            edge = None  # how far in from the glowing edge, in radii
            z = sy * cos_e + depth * sin_e
            if depth >= 0 and z >= 0:
                # On the near side of the shell; depth is how squarely it
                # faces the viewer. The point itself, on the unit sphere:
                normal = (sx, sy * sin_e - depth * cos_e, z)
                dark = min(1.0, 0.2 + 0.6 * (1 - depth) ** 1.5 + 0.2 * (1 - z))
                shine = 0.4 * max(0.0, sum(a * b for a, b in zip(normal, light_dir))) ** 40
                edge = 1 - math.sqrt(sx * sx + sy * sy)
            elif foot <= 1:
                dark = 0.45
            if foot <= 1 and sy < 0:
                to_foot = 1 - math.sqrt(foot)
                edge = to_foot if edge is None else min(edge, to_foot)
            shell += bytes((0, 0, 0, round(255 * dark)))
            for band, glow in glows.items():
                light = shine
                if edge is not None:
                    light += max(0.0, 1 - edge / band) ** 2
                glow += bytes((255, 255, 255, round(255 * min(1.0, light))))

    def image(data):
        picture = pyglet.image.ImageData(width, height, 'RGBA', bytes(data), pitch=width * 4)
        picture.anchor_x = width // 2
        picture.anchor_y = round(height * sin_e / (1 + sin_e))
        return picture

    return image(shell), {band: image(glow) for band, glow in glows.items()}


def soft_dome_image(size=128):
    """A hazy white light shaped like dome_images' hemisphere, brightest
    inside near its foot and fading smoothly to nothing at its outline.
    The anchor is on the centre of its foot."""
    sin_e = math.sin(DOME_ELEVATION)
    width, height = size, round(size / 2 * (1 + sin_e))
    rgba = bytearray()
    for row in range(height):
        sy = (row + 0.5) / height * (1 + sin_e) - sin_e  # up the screen
        for col in range(width):
            sx = (col + 0.5) / width * 2 - 1
            # How far out toward the outline: the shell above the foot's
            # centre line, the foot's ellipse below it.
            r = math.hypot(sx, sy if sy >= 0 else sy / sin_e)
            edge = max(0.0, min(1.0, (1 - r) / 0.45))
            alpha = math.exp(-1.6 * r * r) * edge * edge * (3 - 2 * edge)
            rgba += bytes((255, 255, 255, round(255 * alpha)))
    picture = pyglet.image.ImageData(width, height, 'RGBA', bytes(rgba), pitch=width * 4)
    picture.anchor_x = width // 2
    picture.anchor_y = round(height * sin_e / (1 + sin_e))
    return picture


def pillar_image(width=16, height=64):
    """White column of light: brightest along its axis and at its foot,
    fading to transparent at its sides and toward its top."""
    rgba = bytearray()
    for row in range(height):
        v = (row + 0.5) / height  # 0 at the foot, 1 at the top
        along = min(1.0, v / 0.06) * (1 - v) ** 1.3
        for col in range(width):
            u = abs((col + 0.5) / width * 2 - 1)
            rgba += bytes((255, 255, 255, round(255 * along * (1 - u) ** 1.5)))
    return pyglet.image.ImageData(width, height, 'RGBA', bytes(rgba), pitch=width * 4)


class SpriteEffectsMixin:
    """Combat and floor transition effects of SpriteUI."""

    def _play_effect(self, seconds, create, update=None):
        self._presenter.hold(self, seconds, create, update)

    def draw_combat_effect(self, pos, won: bool) -> None:
        seconds = self.combat_effect_seconds
        if seconds == 0:
            return
        positions = [pos] if len(pos) == 2 and all(
            isinstance(value, (int, float)) for value in pos
        ) else pos
        effects = Path(__file__).parent.parent / "assets" / "effects"
        path = effects / (SLASH_FILES.get(self._attack_facing, "slash.png") if won
                          else "splash.png")
        if not path.is_file():
            path = effects / "slash.png"
        image = pyglet.image.load(str(path))

        def create():
            padding = max(1, round(self.scale))
            size = NEIGHBOR_SCALE if won else 1.0
            scale = (size * 1.8 * max(1, self._sprite_unit() - 2 * padding)
                     / SPRITE_REFERENCE_PIXELS)
            blend = ({"blend_src": pyglet.gl.GL_SRC_ALPHA,
                      "blend_dest": pyglet.gl.GL_ONE} if won else {})
            effects = []
            for x, y in positions:
                cx = self._field_col_x(x) + self.cell_size_x / 2
                cy = (y + 0.5) * self.cell_size_y
                effect = pyglet.sprite.Sprite(
                    image, x=cx - image.width * scale / 2,
                    y=self.window_height - cy - (
                        image.height / 2 - SPRITE_GROUND_OFFSET_PIXELS) * scale,
                    batch=self.batch, group=pyglet.graphics.Group(order=100000), **blend,
                )
                effect.scale = scale
                effects.append(effect)
            return effects

        self._play_effect(seconds, create)

    def draw_vortex_effect(self, pos) -> None:
        """Show the storm of a defeated Vortex over the floor around its cell."""
        seconds = self.combat_effect_seconds * VORTEX_SECONDS_FACTOR
        path = Path(__file__).parent.parent / "assets" / "effects" / "vortex-storm.png"
        if seconds == 0 or not path.is_file():
            return
        image = pyglet.image.load(str(path))
        image.anchor_x = image.width // 2
        image.anchor_y = round(image.height * (0.5 - VORTEX_STORM_FOOT))
        x, y = pos
        horizontal = round(d.FIELD_WIDTH * d.VORTEX_FLOOR_DIAMETER_RATIO / 2)
        vertical = round(horizontal / d.FOV_WIDTH_EXPANSION_RATIO)
        reach = VORTEX_STORM_REACH * image.width

        def create():
            storm = pyglet.sprite.Sprite(
                image, x=self._field_col_x(x) + self.cell_size_x / 2,
                y=self.window_height - (y + 0.5) * self.cell_size_y,
                batch=self.batch, group=pyglet.graphics.Group(order=100000),
            )
            storm.scale_x = horizontal * VORTEX_RADIUS_RATIO * self.cell_size_x / reach
            storm.scale_y = vertical * VORTEX_RADIUS_RATIO * self.cell_size_y / reach
            storm.color = self._display_color((255, 255, 255))
            return [storm]

        self._play_effect(seconds, create)

    def draw_boss_afterglow(self, pos) -> None:
        """Let a pillar of light, a spreading ring and drifting sparks
        linger where a stage boss fell."""
        if self.combat_effect_seconds == 0:
            return
        x, y = pos
        # Its own generator, so the game's random state is left alone.
        rand = random.Random(x * 1009 + y)
        sparks = [
            {
                'delay': rand.uniform(0, BOSS_SPARK_DELAY),
                'life': rand.uniform(*BOSS_SPARK_LIFE),
                'angle': rand.uniform(0, 2 * math.pi),
                'out': rand.uniform(0, 0.7),
                'height': rand.uniform(*BOSS_SPARK_HEIGHT),
                'sway': rand.uniform(0.08, 0.2),
                'turns': rand.uniform(0.5, 1.5),
                'phase': rand.uniform(0, 1),
                'size': rand.uniform(0.06, 0.12),
                'core': rand.random() < 0.4,
            }
            for _ in range(BOSS_SPARKS)
        ]
        parts = {}
        additive = {"blend_src": pyglet.gl.GL_SRC_ALPHA, "blend_dest": pyglet.gl.GL_ONE}

        def create():
            group = pyglet.graphics.Group(order=100000)
            glow = self._display_color(BOSS_AFTERGLOW_COLOR)
            core = self._display_color(BOSS_AFTERGLOW_CORE_COLOR)
            pillars = []
            if self._pillar_image is None:
                self._pillar_image = pillar_image()
            for tint in (glow, core):
                pillar = pyglet.sprite.Sprite(
                    self._pillar_image, batch=self.batch, group=group, **additive)
                pillar.color = tint
                pillars.append(pillar)
            parts['pillars'] = pillars
            parts['ground'] = pyglet.sprite.Sprite(
                self._disc_image, batch=self.batch, group=group, **additive)
            parts['ground'].color = glow
            parts['ring'] = [
                pyglet.shapes.Line(0, 0, 0, 0, color=glow, batch=self.batch,
                                   group=group, **additive)
                for _ in range(BOSS_RING_SEGMENTS)
            ]
            parts['sparks'] = [
                pyglet.shapes.Circle(0, 0, 1, color=core if spark['core'] else glow,
                                     batch=self.batch, group=group, **additive)
                for spark in sparks
            ]
            return (parts['pillars'] + [parts['ground']] + parts['ring']
                    + parts['sparks'])

        def update(progress):
            cell_x, cell_y = self.cell_size_x, self.cell_size_y
            gx = self._field_col_x(x) + cell_x / 2
            gy = self.window_height - (y + 0.5) * cell_y
            image = self._disc_image
            rise = 1 - (1 - min(1.0, progress / BOSS_PILLAR_RISE)) ** 3
            after = max(0.0, (progress - BOSS_PILLAR_RISE) / (1 - BOSS_PILLAR_RISE))
            fade = (1 - after) ** 1.5
            narrow = 1 - 0.7 * after
            height = BOSS_PILLAR_HEIGHT * cell_y * rise
            for pillar, width, strength in zip(
                    parts['pillars'], (BOSS_PILLAR_WIDTH, BOSS_PILLAR_CORE_WIDTH),
                    (255, 255)):
                w = width * cell_x * narrow
                picture = self._pillar_image
                pillar.scale_x = w / picture.width
                pillar.scale_y = max(1.0, height) / picture.height
                pillar.x = gx - w / 2
                pillar.y = gy - 0.05 * height
                pillar.opacity = round(strength * fade * BOSS_AFTERGLOW_OPACITY)

            spread = 1 - (1 - min(1.0, progress / 0.6)) ** 2
            radius = BOSS_RING_RADIUS * cell_x * (0.2 + 0.8 * spread)
            flatten = math.sin(math.radians(60))
            ground = parts['ground']
            ground.scale_x = 2 * radius * 0.7 / image.width
            ground.scale_y = 2 * radius * 0.7 * flatten / image.height
            ground.x = gx - radius * 0.7
            ground.y = gy - radius * 0.7 * flatten
            ground.opacity = round(160 * fade * BOSS_AFTERGLOW_OPACITY)
            ring_fade = (1 - min(1.0, progress / 0.7)) ** 1.2
            for k, line in enumerate(parts['ring']):
                a0 = 2 * math.pi * k / BOSS_RING_SEGMENTS
                a1 = 2 * math.pi * (k + 1) / BOSS_RING_SEGMENTS
                line.x = gx + radius * math.cos(a0)
                line.y = gy + radius * flatten * math.sin(a0)
                line.x2 = gx + radius * math.cos(a1)
                line.y2 = gy + radius * flatten * math.sin(a1)
                line.thickness = max(1.0, 0.12 * cell_x * (1 - 0.6 * spread))
                line.opacity = round(220 * ring_fade * BOSS_AFTERGLOW_OPACITY)

            for spark, dot in zip(sparks, parts['sparks']):
                t = (progress - spark['delay']) / spark['life']
                if not 0 <= t <= 1:
                    dot.opacity = 0
                    continue
                lift = 1 - (1 - t) ** 2
                sway = spark['sway'] * math.sin(
                    2 * math.pi * (spark['turns'] * t + spark['phase']))
                dot.x = gx + cell_x * (spark['out'] * math.cos(spark['angle']) + sway)
                dot.y = (gy + cell_x * spark['out'] * flatten * math.sin(spark['angle'])
                         + spark['height'] * cell_y * lift)
                dot.radius = max(1.0, spark['size'] * cell_x * (1 - 0.5 * t))
                dot.opacity = round(255 * BOSS_AFTERGLOW_OPACITY
                                * min(1.0, t / 0.15) * (1 - t) ** 1.2)

        self._play_effect(BOSS_AFTERGLOW_SECONDS, create, update)

    def draw_iris_ration(self, pos) -> None:
        """Raise a ration, picked at random, glowing above Iris with a few
        twinkles around it, as she hands it to the collapsed player."""
        if self.combat_effect_seconds == 0:
            return
        rand = random.Random()
        path = (Path(__file__).parent.parent / "assets" / "rations"
                / rand.choice(IRIS_RATION_FILES))
        if not path.is_file():
            return
        picture = pyglet.image.load(str(path))
        x, y = pos
        sparks = [
            {
                'angle': rand.uniform(0, 2 * math.pi),
                'out': rand.uniform(0.7, 1.4),
                'start': rand.uniform(0, 0.6),
                'life': rand.uniform(0.2, 0.35),
                'size': rand.uniform(0.06, 0.12),
            }
            for _ in range(IRIS_RATION_SPARKS)
        ]
        parts = {}
        additive = {"blend_src": pyglet.gl.GL_SRC_ALPHA, "blend_dest": pyglet.gl.GL_ONE}

        def create():
            glow_color = self._display_color(IRIS_RATION_GLOW_COLOR)
            back = pyglet.graphics.Group(order=100000)
            front = pyglet.graphics.Group(order=100001)
            sparkle = pyglet.graphics.Group(order=100002)
            parts['glow'] = pyglet.sprite.Sprite(
                self._disc_image, batch=self.batch, group=back, **additive)
            parts['glow'].color = glow_color
            parts['ration'] = pyglet.sprite.Sprite(picture, batch=self.batch, group=front)
            parts['ration'].color = self._display_color((255, 255, 255))
            parts['sparks'] = [
                pyglet.shapes.Circle(0, 0, 1, color=self._display_color((255, 246, 214)),
                                     batch=self.batch, group=sparkle, **additive)
                for _ in sparks
            ]
            return [parts['glow'], parts['ration'], *parts['sparks']]

        def update(progress):
            unit = self._sprite_unit()
            cx = self._field_col_x(x) + self.cell_size_x / 2
            appear = 1 - (1 - min(1.0, progress / 0.25)) ** 3
            fade = 1 - max(0.0, (progress - 0.75) / 0.25)
            low, high = IRIS_RATION_HEIGHT
            cy = (self.window_height - (y + 0.5) * self.cell_size_y
                  + (low + (high - low) * appear) * self.cell_size_y)

            ration = parts['ration']
            scale = IRIS_RATION_SIZE * unit * (0.6 + 0.4 * appear) / max(
                picture.width, picture.height)
            ration.scale = scale
            ration.x = cx - picture.width * scale / 2
            ration.y = cy - picture.height * scale / 2
            ration.opacity = round(255 * appear * fade)

            glow = parts['glow']
            pulse = 0.85 + 0.15 * math.sin(progress * 4 * math.pi)
            size = IRIS_RATION_GLOW_SIZE * unit * (0.5 + 0.5 * appear) * pulse
            glow.scale_x = size / self._disc_image.width
            glow.scale_y = size / self._disc_image.height
            glow.x = cx - size / 2
            glow.y = cy - size / 2
            glow.opacity = round(200 * appear * fade)

            for spark, dot in zip(sparks, parts['sparks']):
                t = (progress - spark['start']) / spark['life']
                if not 0 <= t <= 1:
                    dot.opacity = 0
                    continue
                dot.x = cx + unit * spark['out'] * math.cos(spark['angle'])
                dot.y = cy + unit * spark['out'] * math.sin(spark['angle'])
                dot.radius = max(1.0, spark['size'] * unit * math.sin(math.pi * t))
                dot.opacity = round(255 * math.sin(math.pi * t) * fade)

        self._play_effect(IRIS_RATION_SECONDS, create, update)

    def draw_core_burst(self, pos) -> None:
        """Swell a dark dome over the destroyed Dungeon Core's cell and let
        it come apart into drifting mist."""
        if self.combat_effect_seconds == 0:
            return
        x, y = pos
        if self._dome_images is None:
            self._dome_images = dome_images()
        shell_image, glow_images = self._dome_images
        rand = random.Random(x * 1009 + y)
        flatten = math.sin(DOME_ELEVATION)

        def surface_point():
            # A point on the dome as seen: anywhere from its foot (squashed
            # below the centre) up to its top.
            angle = rand.uniform(0, 2 * math.pi)
            reach = math.sqrt(rand.uniform(0.15, 1.0))
            squash = 1.0 if angle < math.pi else flatten
            return (reach * math.cos(angle), reach * math.sin(angle) * squash)

        puffs = [
            {'at': surface_point(), 'delay': rand.uniform(0, 0.25),
             'size': rand.uniform(0.35, 0.75), 'drift': rand.uniform(0.3, 0.7)}
            for _ in range(CORE_BURST_PUFFS)
        ]
        motes = [
            {'at': surface_point(), 'delay': rand.uniform(0, 0.4),
             'size': rand.uniform(0.05, 0.1), 'drift': rand.uniform(0.4, 1.0),
             'rise': rand.uniform(0.5, 1.5)}
            for _ in range(CORE_BURST_MOTES)
        ]
        parts = {}
        additive = {"blend_src": pyglet.gl.GL_SRC_ALPHA, "blend_dest": pyglet.gl.GL_ONE}

        def create():
            group = pyglet.graphics.Group(order=100000)
            rim = self._display_color(CORE_BURST_RIM_COLOR)
            parts['shell'] = pyglet.sprite.Sprite(shell_image, batch=self.batch, group=group)
            parts['glow'] = pyglet.sprite.Sprite(
                glow_images[DOME_GLOW_BANDS[-1]], batch=self.batch, group=group,
                **additive)
            parts['glow'].color = rim
            parts['puffs'] = []
            for _ in puffs:
                puff = pyglet.sprite.Sprite(self._disc_image, batch=self.batch, group=group)
                puff.color = (0, 0, 0)
                parts['puffs'].append(puff)
            parts['motes'] = [
                pyglet.shapes.Circle(0, 0, 1, color=rim, batch=self.batch,
                                     group=group, **additive)
                for _ in motes
            ]
            return [parts['shell'], parts['glow']] + parts['puffs'] + parts['motes']

        def update(progress):
            cell_x = self.cell_size_x
            gx = self._field_col_x(x) + cell_x / 2
            gy = self.window_height - (y + 0.5) * self.cell_size_y
            swell = min(1.0, progress / CORE_BURST_SWELL)
            after = max(0.0, (progress - CORE_BURST_SWELL) / (1 - CORE_BURST_SWELL))
            grow = 1 - (1 - swell) ** 3
            radius = CORE_BURST_RADIUS * cell_x * (0.1 + 0.9 * grow + 0.1 * after)
            # It thins out as it swells, down to CORE_BURST_THIN at full size,
            # and fades away as it comes apart.
            fade = (1 - (1 - CORE_BURST_THIN) * grow) * (1 - after) ** 1.5
            start, end = CORE_BURST_BAND
            band = (start + (end - start) * grow) * cell_x / radius
            nearest = min(DOME_GLOW_BANDS, key=lambda b: abs(math.log(b / band)))
            if parts['glow'].image is not glow_images[nearest]:
                parts['glow'].image = glow_images[nearest]
            for sprite, strength in ((parts['shell'], CORE_BURST_OPACITY),
                                     (parts['glow'], CORE_BURST_GLOW_OPACITY)):
                sprite.x, sprite.y = gx, gy
                sprite.scale = 2 * radius / sprite.image.width
                sprite.opacity = round(255 * strength * fade)

            image = self._disc_image
            for puff, spec in zip(parts['puffs'], puffs):
                t = (after - spec['delay']) / (1 - spec['delay'])
                if t <= 0:
                    puff.opacity = 0
                    continue
                ux, uy = spec['at']
                spread = 1 + CORE_BURST_PARTICLE_SPREAD * spec['drift'] * (1 - (1 - t) ** 2)
                size = spec['size'] * cell_x * (1 + CORE_BURST_PARTICLE_SPREAD * 1.5 * t)
                puff.scale_x = 2 * size / image.width
                puff.scale_y = 2 * size * flatten / image.height
                puff.x = gx + radius * ux * spread - size
                puff.y = gy + radius * uy * spread - size * flatten
                puff.opacity = round(255 * CORE_BURST_PUFF_OPACITY * CORE_BURST_PARTICLE_OPACITY
                                     * min(1.0, t / 0.15) * (1 - t) ** 1.5)
            for mote, spec in zip(parts['motes'], motes):
                t = (after - spec['delay']) / (1 - spec['delay'])
                if t <= 0:
                    mote.opacity = 0
                    continue
                ux, uy = spec['at']
                travel = CORE_BURST_PARTICLE_SPREAD * t
                spread = 1 + spec['drift'] * travel
                mote.x = gx + radius * ux * spread
                mote.y = gy + radius * uy * spread + spec['rise'] * cell_x * travel
                mote.radius = max(1.0, spec['size'] * cell_x * (1 - 0.5 * t))
                mote.opacity = round(255 * CORE_BURST_PARTICLE_OPACITY
                                     * min(1.0, t / 0.1) * (1 - t) ** 1.2)

        self._play_effect(CORE_BURST_SECONDS, create, update)

    def _core_calamity_images(self):
        cls = type(self)
        if getattr(cls, '_calamity_images', None) is None:
            folder = Path(__file__).parent.parent / "assets" / "effects" / "core-calamity"
            frames = []
            for index in range(CORE_CALAMITY_FRAMES):
                pair = []
                for layer in ('smoke', 'light'):
                    path = folder / f"frame-{index:02d}-{layer}.png"
                    if not path.is_file():
                        cls._calamity_images = []
                        return cls._calamity_images
                    image = pyglet.image.load(str(path))
                    image.anchor_x = image.width // 2
                    image.anchor_y = round(image.height * (0.5 - CORE_CALAMITY_FOOT))
                    pair.append(image)
                frames.append(tuple(pair))
            cls._calamity_images = frames
        return cls._calamity_images

    def draw_core_calamity(self, pos) -> None:
        """Let the Dungeon Core blaze up and loose arms of calamitous smoke
        that reach out from it and scatter away."""
        if self.combat_effect_seconds == 0:
            return
        frames = self._core_calamity_images()
        if not frames:
            return
        x, y = pos
        parts = {}
        additive = {"blend_src": pyglet.gl.GL_SRC_ALPHA, "blend_dest": pyglet.gl.GL_ONE}

        def create():
            smoke_image, light_image = frames[0]
            parts['smoke'] = pyglet.sprite.Sprite(
                smoke_image, batch=self.batch, group=pyglet.graphics.Group(order=100000))
            # The core stays in sight over its own smoke, blazing.
            parts['core'] = self._core_calamity_core_sprites(
                pos, pyglet.graphics.Group(order=100001))
            parts['light'] = pyglet.sprite.Sprite(
                light_image, batch=self.batch,
                group=pyglet.graphics.Group(order=100002), **additive)
            parts['glow'] = pyglet.sprite.Sprite(
                soft_dome_image(), batch=self.batch,
                group=pyglet.graphics.Group(order=100003), **additive)
            parts['glow'].color = self._display_color(CORE_CALAMITY_GLOW_COLOR)
            return [parts['smoke'], parts['light'], parts['glow'],
                    *(sprite for sprite, _ in parts['core'])]

        def update(progress):
            smoke_image, light_image = frames[
                min(CORE_CALAMITY_FRAMES - 1, int(progress * CORE_CALAMITY_FRAMES))]
            horizontal = CORE_CALAMITY_REACH_CELLS
            vertical = horizontal / d.FOV_WIDTH_EXPANSION_RATIO
            reach = CORE_CALAMITY_REACH * smoke_image.width
            gx = self._field_col_x(x) + self.cell_size_x / 2
            gy = self.window_height - (y + 0.5) * self.cell_size_y
            for sprite, image in ((parts['smoke'], smoke_image),
                                  (parts['light'], light_image)):
                if sprite.image is not image:
                    sprite.image = image
                sprite.update(x=gx, y=gy,
                              scale_x=horizontal * self.cell_size_x / reach,
                              scale_y=vertical * self.cell_size_y / reach)
            blaze = (min(1.0, progress / CORE_CALAMITY_BLAZE) if progress < CORE_CALAMITY_BLAZE
                     else 1 - (1 - CORE_CALAMITY_GLOW_END)
                     * (progress - CORE_CALAMITY_BLAZE) / (1 - CORE_CALAMITY_BLAZE))
            glow = parts['glow']
            glow.update(x=gx, y=gy,
                        scale=CORE_CALAMITY_GLOW_RADIUS * self.cell_size_x / glow.image.width)
            glow.opacity = round(255 * CORE_CALAMITY_GLOW_OPACITY * blaze)
            for sprite, strength in parts['core']:
                if strength is not None:
                    sprite.opacity = round(255 * strength * blaze)

        self._play_effect(CORE_CALAMITY_SECONDS, create, update)

    def _core_calamity_core_sprites(self, pos, group):
        """The core drawn over its smoke as (sprite, opacity at full blaze,
        or None for a steady one); none where there is no core image."""
        return []

    def draw_treasure_glow(self, pos) -> None:
        """Put the won stage's hazy golden dome and its floating motes over
        `pos`. The glow keeps its clock across redraws, so it only swells
        once."""
        if self.combat_effect_seconds == 0:
            return
        if self._soft_dome_image is None:
            self._soft_dome_image = soft_dome_image()
        if self._treasure_glow_since is None:
            self._treasure_glow_since = time.monotonic()
        x, y = pos
        rand = random.Random(x * 1009 + y)
        motes = [
            {'seed': rand.getrandbits(32), 'life': rand.uniform(*TREASURE_MOTE_LIFE),
             'offset': rand.random(), 'shimmer': rand.uniform(0.8, 1.6),
             'phase': rand.random(), 'color': rand.choice(TREASURE_MOTE_COLORS)}
            for _ in range(TREASURE_MOTES)
        ]
        group = pyglet.graphics.Group(order=100000)
        additive = {"blend_src": pyglet.gl.GL_SRC_ALPHA, "blend_dest": pyglet.gl.GL_ONE}
        dome = pyglet.sprite.Sprite(self._soft_dome_image, batch=self.batch, group=group,
                                    **additive)
        dome.color = self._display_color(TREASURE_GLOW_COLOR)
        lights = []
        for mote in motes:
            tint = self._display_color(mote['color'])
            halo = pyglet.sprite.Sprite(self._disc_image, batch=self.batch, group=group,
                                        **additive)
            halo.color = tint
            core = pyglet.shapes.Circle(0, 0, 1, color=tint, batch=self.batch,
                                        group=group, **additive)
            lights.append((halo, core))
        self._uncached_drawables.extend([dome] + [part for light in lights for part in light])
        self._treasure_glow = {'pos': pos, 'dome': dome,
                               'motes': list(zip(motes, lights)), 'drawn_at': 0.0}
        self._animate_treasure_glow()

    def _animate_treasure_glow(self):
        glow = self._treasure_glow
        now = time.monotonic()
        glow['drawn_at'] = now
        t = now - self._treasure_glow_since
        x, y = glow['pos']
        cell_x = self.cell_size_x
        gx = self._field_col_x(x) + cell_x / 2
        gy = self.window_height - (y + 0.5) * self.cell_size_y
        grow = 1 - (1 - min(1.0, t / TREASURE_GLOW_SWELL)) ** 3
        breath = 1 - TREASURE_GLOW_BREATH * (
            0.5 + 0.5 * math.cos(2 * math.pi * t / TREASURE_GLOW_BREATH_SECONDS))
        radius = TREASURE_GLOW_RADIUS * cell_x / 2 * (0.15 + 0.85 * grow)
        flatten = math.sin(DOME_ELEVATION)
        dome = glow['dome']
        dome.x, dome.y = gx, gy
        dome.scale = 2 * radius / dome.image.width
        dome.opacity = round(255 * TREASURE_GLOW_OPACITY
                             * min(1.0, t / (TREASURE_GLOW_SWELL / 2)) * breath)

        shown = max(0.0, min(1.0, (t - TREASURE_GLOW_SWELL / 3) / TREASURE_GLOW_SWELL))
        disc = self._disc_image
        for mote, (halo, core) in glow['motes']:
            age = t / mote['life'] + mote['offset']
            cycle, u = int(age), age % 1.0
            # Each life starts somewhere new, from the mote's own numbers.
            path = random.Random(mote['seed'] * 7919 + cycle)
            sx = path.uniform(-0.7, 0.7)
            room = math.sqrt(1 - sx * sx)
            sy = room * path.uniform(-0.7 * flatten, 0.45)
            drift = path.uniform(-0.15, 0.15)
            rise = path.uniform(*TREASURE_MOTE_RISE)
            wander = path.uniform(0.03, 0.08)
            turns = path.uniform(0.6, 1.4)
            size = path.uniform(*TREASURE_MOTE_HALO)
            px = gx + radius * (sx + drift * u
                                + wander * math.sin(2 * math.pi * (turns * u + mote['phase'])))
            py = gy + radius * (sy + rise * u)
            shimmer = 1 - TREASURE_MOTE_SHIMMER * (0.5 + 0.5 * math.sin(
                2 * math.pi * (t / mote['shimmer'] + mote['phase'])))
            strength = math.sin(math.pi * u) ** 1.5 * shimmer * shown
            reach = size * cell_x * (0.85 + 0.15 * shimmer)
            halo.scale_x = 2 * reach / disc.width
            halo.scale_y = 2 * reach / disc.height
            halo.x, halo.y = px - reach, py - reach
            halo.opacity = round(255 * 0.55 * strength)
            core.x, core.y = px, py
            core.radius = max(1.0, 0.035 * cell_x)
            core.opacity = round(255 * 0.9 * strength)

    def _update_treasure_glow(self):
        """While waiting on the final screen, move the sparkles on."""
        glow = self._treasure_glow
        if glow is None or self._menu_active or self._closed:
            return
        if time.monotonic() - glow['drawn_at'] < 1 / TREASURE_GLOW_FPS:
            return
        self._animate_treasure_glow()
        self._flip()

    def draw_floor_transition(self, kind, player, exit_point=None) -> None:
        """Show the moment between floors: on the landing of the stairs the
        player is taking, or alone in the dark falling through or climbing
        out of a pit, on the cell it left from. The scene fades in over the
        old floor, the player moves, and the new floor fades in from black
        (see FLOOR_TRANSITION_FADE)."""
        seconds = self.floor_transition_seconds
        if seconds == 0 or '@' not in self._sprite_images:
            return
        revealed = []

        def update(progress):
            # Draw the new floor under the scene once, as the fade out begins;
            # without it (no next view), the scene stays until the cut.
            if (not revealed and progress >= 1 - FLOOR_TRANSITION_FADE
                    and self._next_view is not None):
                revealed.append(True)
                self.draw_stage(**self._next_view)
            self._animate_floor_transition(kind, progress, bool(revealed))

        self._play_effect(
            seconds, lambda: self._create_floor_transition(kind, player, exit_point), update,
        )

    def _animate_floor_transition(self, kind, progress, fade_out):
        parts = self._transition_parts
        fade = min(1.0, progress / FLOOR_TRANSITION_FADE)
        if fade_out:
            fade = min(fade, (1 - progress) / FLOOR_TRANSITION_FADE)
        move = min(1.0, max(0.0, (progress - FLOOR_TRANSITION_FADE)
                            / (1 - 2 * FLOOR_TRANSITION_FADE)))
        size, alpha, side = 1.0, 1.0, 0.0
        if kind in ('down', 'up'):
            # Out to the right over the first half, back over the second.
            side = FLOOR_TRANSITION_STAIRS_SIDE * (1 - abs(2 * move - 1))
        if kind == 'down':
            offset = -FLOOR_TRANSITION_STEP * move
            alpha = 1 - (1 - FLOOR_TRANSITION_STAIRS_DIM) * move
        elif kind == 'up':
            offset = -FLOOR_TRANSITION_STEP * (1 - move)
            alpha = FLOOR_TRANSITION_STAIRS_DIM + (1 - FLOOR_TRANSITION_STAIRS_DIM) * move
        elif kind == 'climb':
            offset = -FLOOR_TRANSITION_STEP * (1 - move)
        else:
            offset = -FLOOR_TRANSITION_FALL * move
            size = 1 - (1 - FLOOR_TRANSITION_FALL_SHRINK) * move
            alpha = 1 - move
        # Offsets are in cells (up the screen, and to the right for `side`);
        # the feet stay the anchor.
        figure, cx, cy, picture, scale = parts['figure']
        if kind in ('down', 'up'):
            picture = parts['stair_pictures'][move >= 0.5]
            if figure.image is not picture:
                figure.image = picture
        scale *= size
        figure.scale = scale
        figure.x = cx + side * self.cell_size_x - picture.width * scale / 2
        figure.y = (self.window_height - cy + offset * self.cell_size_y
                    - (picture.height / 2 - SPRITE_GROUND_OFFSET_PIXELS) * scale)
        figure.opacity = round(255 * alpha * fade)
        for obj, opacity in parts['fading']:
            obj.opacity = round(opacity * fade)

    def _create_floor_transition(self, kind, player, exit_point):
        field_height = self.field_height * self.cell_size_y
        shapes = [pyglet.shapes.Rectangle(
            # The whole window's width: the scrolled field can show past
            # field_pixel_width.
            0, self.window_height - field_height,
            max(self.field_pixel_width, self.window_width or 0), field_height,
            color=self._display_color(TRANSITION_BACKGROUND), batch=self.batch,
            group=pyglet.graphics.Group(order=99998),
        )]
        cell_x, cell_y = self.cell_size_x, self.cell_size_y
        column, row = exit_point or (player.x, player.y)
        left = self._field_col_x(column)
        cx, cy = left + cell_x / 2, (row + 0.5) * cell_y
        image = self._landing_image
        if kind in ('down', 'up') and image is not None:
            cell_pixels = image.width / (1 + 2 * TERRAIN_SIDE)
            overhang = TERRAIN_OVERHANG[d.CHAR_STAIRS_UP]
            cell_bottom = (row + 1) * cell_y
            landing = pyglet.sprite.Sprite(
                image, x=left - TERRAIN_SIDE * cell_x,
                y=self.window_height - cell_bottom, batch=self.batch,
                group=pyglet.graphics.Group(order=99999),
            )
            landing.scale_x = cell_x / cell_pixels
            landing.scale_y = (1 + overhang) * cell_y / image.height
            landing.color = self._display_color(TERRAIN_TINT)
            shapes.append(landing)
            cy = cell_bottom - LANDING_FEET_HEIGHT * cell_y
        stair_pictures = None
        if kind in ('down', 'up'):
            stair_pictures = tuple(
                self._sprite_images[self._player_pose_sprite(player, facing, 'walk-right')]
                for facing in ('right', 'left')
            )
        sprite = self._player_sprite(player)
        picture = stair_pictures[0] if stair_pictures else self._sprite_images[sprite]
        padding = max(1, round(self.scale))
        scale = 1.8 * max(1, self._sprite_unit() - 2 * padding) / SPRITE_REFERENCE_PIXELS
        figure = pyglet.sprite.Sprite(
            picture, x=cx - picture.width * scale / 2,
            y=self.window_height - cy - (picture.height / 2 - SPRITE_GROUND_OFFSET_PIXELS) * scale,
            batch=self.batch, group=pyglet.graphics.Group(order=100000),
        )
        figure.scale = scale
        shapes.append(figure)
        # The parts the animation moves and fades (see
        # _animate_floor_transition), with each one's full opacity.
        self._transition_parts = {
            'figure': (figure, cx, cy, picture, scale),
            'stair_pictures': stair_pictures,
            'fading': [(shape, 255) for shape in shapes[:-1]],
        }
        if kind == 'climb':
            # A rope segment over the player, centred on the figure's height.
            figure_height = (picture.height / 2 + SPRITE_GROUND_OFFSET_PIXELS
                             - self._sprite_head_room.get(sprite, 0)) * scale
            length = ROPE_LENGTH * figure_height
            width = max(2, round(ROPE_WIDTH * cell_x))
            rope_x = cx + ROPE_OFFSET * cell_x
            rope_middle = cy - figure_height / 2
            glow_image = self._disc_image
            glow_width, glow_length = ROPE_GLOW_WIDTH * cell_x, ROPE_GLOW_LENGTH * length
            glow = pyglet.sprite.Sprite(
                glow_image, x=rope_x - glow_width / 2,
                y=self.window_height - rope_middle - glow_length / 2,
                batch=self.batch, group=pyglet.graphics.Group(order=99999),
            )
            glow.scale_x = glow_width / glow_image.width
            glow.scale_y = glow_length / glow_image.height
            glow.color = self._display_color(COLOR_MAP[CI_GREEN])
            glow.opacity = ROPE_GLOW_OPACITY
            shapes.append(glow)
            rope = pyglet.shapes.Rectangle(
                round(rope_x - width / 2),
                self.window_height - (rope_middle + length / 2),
                width, length, color=self._display_color(ROPE_COLOR),
                batch=self.batch, group=pyglet.graphics.Group(order=100001),
            )
            shapes.append(rope)
            self._transition_parts['fading'] += [(glow, ROPE_GLOW_OPACITY), (rope, 255)]
        return shapes
