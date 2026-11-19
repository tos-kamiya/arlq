"""Render the player in every sword state and facing from the saved heroic others' scene.

Rows are the sword states (own sword, chimera's sword, cursed sword, K
blessing) and columns the facings (down, left, right, up) plus a down-facing
step with the right foot forward. A last row shows
the player collapsed from hunger, in the first column. Run after
build-heroic.py:
blender --factory-startup --background --threads 4 --python dev-samples/3d-stage1/preview-player-facings.py
Writes heroic/preview-player-facings.jpg; needs ImageMagick's `convert`.
"""
from pathlib import Path
import math
import subprocess
import sys

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'rigged-armor'))
from sprite_pose import HEROIC_PLAYER_SIZE, heroic_player

SWORDS = [('@', 'OWN SWORD'), ('@c', 'CHIMERA SWORD (c)'), ('@C', 'CURSED SWORD (C)'),
          ('@K', 'K BLESSING')]
PLAYER_SWORDS = {'@': None, '@c': 'c', '@C': 'C', '@K': 'blessed'}
FACINGS = [('', 'DOWN'), ('<', 'LEFT'), ('>', 'RIGHT'), ('^', 'UP')]
COLUMNS = [name for _, name in FACINGS] + ['DOWN / RIGHT FOOT']
# The collapsed player has one pose, shown under the down column.
COLLAPSED = ('@_', 'COLLAPSED (HUNGER)')
ROWS = len(SWORDS) + 1
SPACING_X = 1.8
SPACING_Y = 2.4
WALK_COLUMN_GAP = SPACING_X * 0.5

bpy.ops.wm.open_mainfile(filepath=str(ROOT / 'heroic' / 'characters-others-angle60.blend'))
scene = bpy.context.scene
centers = scene['sprite_centers']
ink = bpy.data.materials.new('Preview label ink')
ink.use_nodes = True
emission = ink.node_tree.nodes.new('ShaderNodeEmission')
emission.inputs['Color'].default_value = (0.75, 0.8, 0.9, 1)
ink.node_tree.links.new(emission.outputs[0],
                        ink.node_tree.nodes['Material Output'].inputs['Surface'])


def label(value, pos, size, align='CENTER'):
    bpy.ops.object.text_add(location=pos)
    obj = bpy.context.object
    obj.data.body = value
    obj.data.align_x = align
    obj.data.size = size
    obj.data.materials.append(ink)
    return obj


def cell(col, row):
    x = (col - (len(COLUMNS) - 1) / 2) * SPACING_X
    if col == len(FACINGS):
        x += WALK_COLUMN_GAP
    return x, -row * SPACING_Y


shown = set()


def place(char, col, row):
    """Move the character `char` to the cell (col, row) and show it."""
    collection = next(c for c in bpy.data.collections
                      if c.name.startswith('Character ' + char + ' '))
    x, y = centers[char]
    cx, cy = cell(col, row)
    move = Matrix.Translation((cx - x, cy - y, 0))
    for obj in collection.objects:
        if not obj.get('sprite'):
            continue
        obj.matrix_world = move @ obj.matrix_world
        obj.hide_render = False
        shown.add(obj)


def place_player(sword, col, row, facing, pose='rest'):
    x, y = cell(col, row)
    pivot = Matrix.Translation((x, y, 0))
    resize = pivot @ Matrix.Scale(HEROIC_PLAYER_SIZE, 4) @ pivot.inverted()
    for obj in heroic_player(x, y, PLAYER_SWORDS[sword], facing, pose=pose):
        obj.matrix_world = resize @ obj.matrix_world
        shown.add(obj)

rows = [(sword_name, [sword + suffix for suffix, _ in FACINGS]) for sword, sword_name in SWORDS]
rows.append((COLLAPSED[1], [COLLAPSED[0]]))
for row, (row_name, chars) in enumerate(rows):
    for col, char in enumerate(chars):
        if FACINGS[col][0] == '<':
            place_player(SWORDS[row][0], col, row, 'left')
        else:
            place(char, col, row)
    if row < len(SWORDS):
        place_player(SWORDS[row][0], len(FACINGS), row, 'down', 'walk-right')
    left, cy = cell(0, row)
    shown.add(label(row_name, (left - SPACING_X * 0.55, cy - 0.3, 0.005), 0.14, 'RIGHT'))
for col, facing_name in enumerate(COLUMNS):
    cx, _ = cell(col, 0)
    # Above the back row's helmets, which rise well above their cells on screen.
    shown.add(label(facing_name, (cx, SPACING_Y * 0.55 + 1.1, 0.005), 0.16))
for obj in scene.objects:
    obj.hide_render = not (obj in shown or obj.name.startswith('Backdrop')
                           or obj.type in ('LIGHT', 'CAMERA'))
# Same lighting swap as the group preview: suns from each area light's
# direction, so every figure is lit alike.
for light in [obj for obj in scene.objects if obj.type == 'LIGHT']:
    distance = light.location.length
    sun = bpy.data.lights.new(light.name + ' sun', 'SUN')
    sun.energy = light.data.energy / (math.pi * distance * distance)
    sun.angle = 2 * math.atan(light.data.size / 2 / distance)
    sun.color = light.data.color
    light.data = sun
camera = scene.camera
angle = math.radians(60)
# Room on the left for the longest row label, on the right for the swords
# held out by the last column, above for the column labels, and below for
# the collapsed player's flung arm.
width = len(COLUMNS) * SPACING_X + WALK_COLUMN_GAP + 5.2
depth = ROWS * SPACING_Y + 3.4
target = Vector((-0.6 + WALK_COLUMN_GAP / 2, -(ROWS - 1) * SPACING_Y / 2 + 0.2, 0.5))
camera.location = target + Vector((0, -15 * math.cos(angle), 15 * math.sin(angle)))
camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
camera.data.ortho_scale = width
pixels_per_unit = 1400 / (len(FACINGS) * SPACING_X + 5.2)
scene.render.resolution_x = round(width * pixels_per_unit)
scene.render.resolution_y = round((depth * math.sin(angle) + 2.4) * pixels_per_unit)
png = ROOT / 'heroic' / 'preview-player-facings.png'
scene.render.filepath = str(png)
bpy.ops.render.render(write_still=True)
# Only the JPEG goes in the repository.
subprocess.run(['convert', str(png), '-quality', '90', str(png.with_suffix('.jpg'))], check=True)
png.unlink()
