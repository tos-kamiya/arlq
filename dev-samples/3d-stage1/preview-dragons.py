"""Render the dragons (d, D, F, w, W) side by side from the saved heroic scene.

Run after build-heroic.py:
blender --background --threads 4 --python dev-samples/3d-stage1/preview-dragons.py
"""
from pathlib import Path
import math

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parent
DRAGONS = ['d', 'D', 'F', 'w', 'W']
SPACING = 2.6

bpy.ops.wm.open_mainfile(filepath=str(ROOT / 'heroic' / 'characters-angle60.blend'))
scene = bpy.context.scene
centers = scene['sprite_centers']
shown = set()
for i, char in enumerate(DRAGONS):
    collection = next(c for c in bpy.data.collections
                      if c.name.startswith('Character ' + char + ' '))
    x, y = centers[char]
    # Line the dragons up in one row about the origin, labels included.
    move = Matrix.Translation(((i - (len(DRAGONS) - 1) / 2) * SPACING - x, -y, 0))
    for obj in collection.objects:
        obj.matrix_world = move @ obj.matrix_world
        shown.add(obj)
for obj in scene.objects:
    obj.hide_render = not (obj in shown or obj.name.startswith('Backdrop')
                           or obj.type in ('LIGHT', 'CAMERA'))
# Same lighting swap as the group preview: suns from each area light's
# direction, so every dragon is lit alike.
for light in [obj for obj in scene.objects if obj.type == 'LIGHT']:
    distance = light.location.length
    sun = bpy.data.lights.new(light.name + ' sun', 'SUN')
    sun.energy = light.data.energy / (math.pi * distance * distance)
    sun.angle = 2 * math.atan(light.data.size / 2 / distance)
    sun.color = light.data.color
    light.data = sun
camera = scene.camera
angle = math.radians(60)
target = Vector((0, -0.6, 1.5))
camera.location = target + Vector((0, -15 * math.cos(angle), 15 * math.sin(angle)))
camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
camera.data.ortho_scale = len(DRAGONS) * SPACING + 0.4
scene.render.resolution_x = 1200
scene.render.resolution_y = round(1200 * 4.4 / camera.data.ortho_scale)
scene.render.filepath = str(ROOT / 'heroic' / 'preview-dragons.png')
bpy.ops.render.render(write_still=True)
