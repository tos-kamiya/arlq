"""Render the Stage 6 emergency rations beside the player from the saved others' scene.

Run after build-heroic.py:
blender --background --threads 4 --python dev-samples/3d-stage1/preview-rations.py
"""
from pathlib import Path
import math

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parent
SHOWN = [('@', 'PLAYER'), ('ration-hyorogan', 'HYOROGAN'), ('ration-hardtack', 'HARDTACK'),
         ('ration-jerky', 'JERKY')]
SPACING = 1.6

bpy.ops.wm.open_mainfile(filepath=str(ROOT / 'heroic' / 'characters-others-angle60.blend'))
scene = bpy.context.scene
centers = scene['sprite_centers']
ink = bpy.data.materials['Ivory lettering']
shown = set()
for i, (char, name) in enumerate(SHOWN):
    collection = next(c for c in bpy.data.collections
                      if c.name.startswith('Character ' + char + ' '))
    x, y = centers[char]
    px = (i - (len(SHOWN) - 1) / 2) * SPACING
    move = Matrix.Translation((px - x, -y, 0))
    for obj in collection.objects:
        if obj.get('sprite'):
            obj.matrix_world = move @ obj.matrix_world
            shown.add(obj)
    bpy.ops.object.text_add(location=(px, -0.75, 0.005))
    text = bpy.context.object
    text.data.body = name
    text.data.align_x = 'CENTER'
    text.data.size = 0.14
    text.data.materials.append(ink)
    shown.add(text)
for obj in scene.objects:
    obj.hide_render = not (obj in shown or obj.name.startswith('Backdrop')
                           or obj.type in ('LIGHT', 'CAMERA'))
# Same lighting swap as the group preview: suns from each area light's
# direction, so everything is lit alike.
for light in [obj for obj in scene.objects if obj.type == 'LIGHT']:
    distance = light.location.length
    sun = bpy.data.lights.new(light.name + ' sun', 'SUN')
    sun.energy = light.data.energy / (math.pi * distance * distance)
    sun.angle = 2 * math.atan(light.data.size / 2 / distance)
    sun.color = light.data.color
    light.data = sun
camera = scene.camera
angle = math.radians(60)
target = Vector((0, -0.2, 0.7))
camera.location = target + Vector((0, -15 * math.cos(angle), 15 * math.sin(angle)))
camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
camera.data.ortho_scale = len(SHOWN) * SPACING + 0.2
scene.render.resolution_x = 1400
scene.render.resolution_y = round(1400 * 2.6 / camera.data.ortho_scale)
scene.render.filepath = str(ROOT / 'heroic' / 'preview-rations.png')
bpy.ops.render.render(write_still=True)
