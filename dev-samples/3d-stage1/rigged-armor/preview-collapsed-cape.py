"""Compare the collapsed cape bones with a small bend, without drape projection."""
import math
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
bpy.ops.wm.open_mainfile(filepath=str(HERE / 'hero-rig-chibi.blend'))
scene = bpy.context.scene
scene.frame_set(120)
rig = bpy.data.objects['Hero rig']
rig.animation_data_clear()
cape = bpy.data.objects['Cape']
# Only the cape's original armature deformation is used for this study.
for name in ('Drape detail', 'Drape when collapsed', 'Soften drape'):
    if name in cape.modifiers:
        cape.modifiers.remove(cape.modifiers[name])
for obj in scene.objects:
    if obj.name.startswith(('Sword ', 'Chimera sword ', 'Cursed sword ', 'Blessed sword ')):
        obj.hide_render = True
scene.cycles.samples = 32
scene.camera.data.ortho_scale = 1.6
for label, bend, leg_bend in (('knee', 22, 21),):
    for side in 'LCR':
        rig.pose.bones[f'cape.{side}.2'].rotation_euler.x = math.radians(bend)
        rig.pose.bones[f'cape.{side}.3'].rotation_euler.x = math.radians(leg_bend + (3 if side == 'C' else 0))
        rig.pose.bones[f'cape.{side}.4'].rotation_euler.x = math.radians(-8 if side == 'C' else -12)
    bpy.context.view_layer.update()
    target = Vector((0, 0, .23))
    for view, offset in (('side', Vector((6, 6, 1.8))),
                         ('top', Vector((0, -4, 6.928)))):
        scene.camera.location = target + offset
        scene.camera.rotation_euler = (target - scene.camera.location).to_track_quat('-Z', 'Y').to_euler()
        scene.render.filepath = str(HERE / f'collapsed-cape-{label}-{view}.png')
        bpy.ops.render.render(write_still=True)
