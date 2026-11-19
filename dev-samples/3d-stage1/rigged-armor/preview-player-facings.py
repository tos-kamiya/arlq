"""Render the armor's sword states, facings and two ending poses in a grid.

Run after build-chibi.py. Writes preview-player-facings.jpg in this directory.
"""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from sprite_pose import SWORDS, bake, figure_parts, standing_extent

bpy.ops.wm.open_mainfile(filepath=str(HERE / 'hero-rig-chibi.blend'))
scene = bpy.context.scene
rig = bpy.data.objects['Hero rig']
all_parts = [obj for obj in scene.objects if obj.type == 'MESH' and obj.parent == rig]
armor = [obj for obj in figure_parts(scene, rig) if not obj.name.startswith(tuple(SWORDS.values()))]
floor, _ = standing_extent(scene, rig, armor)
bpy.data.objects['Studio floor'].location.z = floor - .002

for light in (obj for obj in scene.objects if obj.type == 'LIGHT'):
    distance = light.location.length
    sun = bpy.data.lights.new(light.name + ' sun', 'SUN')
    sun.energy = light.data.energy / (math.pi * distance ** 2)
    sun.angle = 2 * math.atan(light.data.size / (2 * distance))
    sun.color = light.data.color
    light.data = sun

camera = scene.camera
last_y = -6.4
target = Vector((-.45, .04 + last_y / 2, .54))
camera.location = target + Vector((0, -5, 5 * math.sqrt(3)))
camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
camera.data.ortho_scale = 8.35
scene.render.resolution_x = 1600
scene.render.resolution_y = 400 - round(last_y * 158)
scene.render.image_settings.file_format = 'JPEG'
scene.render.image_settings.color_mode = 'RGB'
scene.render.image_settings.quality = 90
scene.cycles.samples = 24
scene.cycles.use_denoising = True

ink = bpy.data.materials.new('Facing labels')
ink.use_nodes = True
nodes = ink.node_tree.nodes
emission = nodes.new('ShaderNodeEmission')
emission.inputs['Color'].default_value = (.75, .8, .9, 1)
ink.node_tree.links.new(emission.outputs[0], nodes['Material Output'].inputs['Surface'])
screen_rotation = camera.rotation_euler.to_quaternion()


def label_on_screen(label, x, y, size=.095):
    font = bpy.data.curves.new(label, 'FONT')
    font.body = label
    font.align_x = 'CENTER'
    font.size = size
    font.materials.append(ink)
    text = bpy.data.objects.new(label, font)
    scene.collection.objects.link(text)
    text.location = camera.location + screen_rotation @ Vector((x, y, -8.4))
    text.rotation_euler = camera.rotation_euler


columns = (
    ('down', 'rest', 'DOWN', -2.81),
    ('left', 'rest', 'LEFT', -1.55),
    ('right', 'rest', 'RIGHT', -.29),
    ('up', 'rest', 'UP', .97),
    ('down', 'walk-right', 'DOWN / RIGHT FOOT', 2.65),
)
rows = (('OWN SWORD', 'own'), ('CHIMERA SWORD (c)', 'chimera'),
        ('CURSED SWORD (C)', 'cursed'), ('K BLESSING', 'blessed'))
for _, _, label, x in columns:
    label_on_screen(label, x - target.x, .70 - last_y * math.sqrt(3) / 4)
for row, (label, sword) in enumerate(rows):
    y = -1.6 * row
    parts = armor + [obj for obj in all_parts if obj.name.startswith(SWORDS[sword])]
    for part in parts:
        part.hide_render = part.hide_viewport = False
    for facing, pose, _, x in columns:
        bake(scene, rig, parts, pose, facing, floor, place=Matrix.Translation((x, y, 0)))
    label_on_screen(label, -3.55, (.8 * -last_y / 2 + y) * math.sqrt(3) / 2, .083)

for pose, label, col in (('collapsed', 'COLLAPSED (HUNGER)', 0),
                         ('kneeling', 'KNEELING (CORE)', 1)):
    x = columns[col][3]
    bake(scene, rig, armor, pose, 'down', floor, place=Matrix.Translation((x, last_y, 0)))
    label_on_screen(label, x - target.x, (.8 * -last_y / 2 + last_y) * math.sqrt(3) / 2 - .16, .075)
for part in all_parts:
    part.hide_render = True
scene.render.filepath = str(HERE / 'preview-player-facings.jpg')
bpy.ops.render.render(write_still=True)
