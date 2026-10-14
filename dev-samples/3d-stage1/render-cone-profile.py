"""Render the obtuse cone perpendicular to its axis for shape inspection."""
from pathlib import Path
import bpy
from mathutils import Vector

out = Path(__file__).resolve().parent / 'obtuse-cones'
bpy.ops.wm.open_mainfile(filepath=str(out / 'stage1-characters.blend'))
scene = bpy.context.scene
cone = bpy.data.objects['AMOEBA rounded radial cone']
for obj in scene.objects:
    obj.hide_render = obj != cone and obj.type not in ('LIGHT', 'CAMERA')
camera = scene.camera
axis = cone.rotation_euler.to_matrix() @ Vector((0, 0, 1))
side = axis.cross(Vector((0, 0, 1))).normalized()
camera.location = cone.location + side * 3
camera.rotation_euler = (cone.location - camera.location).to_track_quat('-Z', 'Y').to_euler()
camera.data.ortho_scale = 1.05
scene.render.resolution_x = 700
scene.render.resolution_y = 700
scene.render.filepath = str(out / 'cone-side.png')
bpy.ops.render.render(write_still=True)
