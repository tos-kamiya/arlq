"""Render the player in every sword state and facing from the saved heroic others' scene.

Rows are the sword states (own sword, chimera's sword, cursed sword, K
blessing) and columns the facings (down, left, right, up). Run after
build-heroic.py:
blender --background --threads 4 --python dev-samples/3d-stage1/preview-player-facings.py
"""
from pathlib import Path
import math

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parent
SWORDS = [('@', 'OWN SWORD'), ('@c', 'CHIMERA SWORD (c)'), ('@C', 'CURSED SWORD (C)'),
          ('@K', 'K BLESSING')]
FACINGS = [('', 'DOWN'), ('<', 'LEFT'), ('>', 'RIGHT'), ('^', 'UP')]
SPACING_X = 1.8
SPACING_Y = 2.4

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
    return ((col - (len(FACINGS) - 1) / 2) * SPACING_X, -row * SPACING_Y)


shown = set()
for row, (sword, sword_name) in enumerate(SWORDS):
    for col, (suffix, facing_name) in enumerate(FACINGS):
        char = sword + suffix
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
    left, cy = cell(0, row)
    shown.add(label(sword_name, (left - SPACING_X * 0.55, cy - 0.3, 0.005), 0.14, 'RIGHT'))
for col, (_, facing_name) in enumerate(FACINGS):
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
width = len(FACINGS) * SPACING_X + 3.2
depth = len(SWORDS) * SPACING_Y + 0.6
target = Vector((-0.8, -(len(SWORDS) - 1) * SPACING_Y / 2 + 0.75, 0.5))
camera.location = target + Vector((0, -15 * math.cos(angle), 15 * math.sin(angle)))
camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
camera.data.ortho_scale = width
scene.render.resolution_x = 1400
scene.render.resolution_y = round(1400 * (depth * math.sin(angle) + 2.4) / width)
scene.render.filepath = str(ROOT / 'heroic' / 'preview-player-facings.png')
bpy.ops.render.render(write_still=True)
