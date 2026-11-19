"""Prototype a kneeling pose using the generated chibi armor rig."""
from pathlib import Path
import sys

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from sprite_pose import apply_kneeling_pose, figure_parts, standing_extent
bpy.ops.wm.open_mainfile(filepath=str(HERE / 'hero-rig-chibi.blend'))
scene = bpy.context.scene
scene.frame_set(1)
rig = bpy.data.objects['Hero rig']
parts = figure_parts(scene, rig)
floor, _ = standing_extent(scene, rig, parts)
rig.animation_data_clear()
for obj in scene.objects:
    if obj.name.startswith(('Sword ', 'Chimera sword ', 'Cursed sword ', 'Blessed sword ')):
        obj.hide_render = True
apply_kneeling_pose(scene, rig, parts, floor)
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
# A level side view makes the cape's clearance from the back visible.
scene.camera.location = target + Vector((8, 0, 0))
scene.camera.rotation_euler = (target - scene.camera.location).to_track_quat('-Z', 'Y').to_euler()
scene.render.filepath = str(HERE / 'chibi-kneeling-side-preview.png')
bpy.ops.render.render(write_still=True)
