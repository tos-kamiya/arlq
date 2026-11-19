"""Prototype a kneeling pose using the generated chibi armor rig."""
import math
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
bpy.ops.wm.open_mainfile(filepath=str(HERE / 'hero-rig-chibi.blend'))
scene = bpy.context.scene
scene.frame_set(1)
rig = bpy.data.objects['Hero rig']
rig.animation_data_clear()
for obj in scene.objects:
    if obj.name.startswith(('Sword ', 'Chimera sword ', 'Cursed sword ', 'Blessed sword ')):
        obj.hide_render = True

rotations = {
    'waist': (48, 0, 0), 'chest': (18, 0, 0), 'neck': (25, 0, 0), 'head': (18, 0, 0),
    'thigh.L': (35, 0, 0), 'thigh.R': (35, 0, 0),
    'shin.L': (-140, 0, 0), 'shin.R': (-140, 0, 0),
    'foot.L': (35, 0, 0), 'foot.R': (35, 0, 0),
    'upper_arm.L': (65, 0, 8), 'upper_arm.R': (65, 0, -8),
    'forearm.L': (5, 0, 0), 'forearm.R': (5, 0, 0),
}
for name, angles in rotations.items():
    rig.pose.bones[name].rotation_euler = tuple(math.radians(v) for v in angles)
bpy.context.view_layer.update()
depsgraph = bpy.context.evaluated_depsgraph_get()
points = []
for obj in scene.objects:
    if obj.type == 'MESH' and obj.parent == rig and not obj.hide_render and not obj.name.startswith('Cape'):
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        points.extend(evaluated.matrix_world @ v.co for v in mesh.vertices)
        evaluated.to_mesh_clear()
# The studio floor is at z=0.
rig.pose.bones['root'].location.y -= min(p.z for p in points)
bpy.context.view_layer.update()
bpy.ops.wm.save_as_mainfile(filepath=str(HERE / 'hero-rig-chibi-kneeling-preview.blend'))
scene.render.filepath = str(HERE / 'chibi-kneeling-preview.png')
bpy.ops.render.render(write_still=True)
# Match the game's 60-degree overhead camera for a second view.
target = Vector((0, 0, .3))
scene.camera.location = target + Vector((0, -4, 6.928))
scene.camera.rotation_euler = (target - scene.camera.location).to_track_quat('-Z', 'Y').to_euler()
scene.render.filepath = str(HERE / 'chibi-kneeling-top-preview.png')
bpy.ops.render.render(write_still=True)
