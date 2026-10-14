"""Render accepted models at 60 degrees below horizontal, orthographically."""
from pathlib import Path
import math
import sys
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parent
for directory, filename in [('attached-cones', 'stage1-characters.blend'),
                            ('player-arms', 'player.blend')]:
    bpy.ops.wm.open_mainfile(filepath=str(ROOT / directory / filename))
    scene = bpy.context.scene
    camera = scene.camera
    distance = 15
    angle = math.radians(60)
    camera.location = (0, -distance * math.cos(angle), distance * math.sin(angle))
    camera.rotation_euler = (Vector((0, 0, 0)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
    target = Path(filename).stem + '-angle60.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / directory / target))
    if '--save-only' in sys.argv:
        continue
    scene.render.filepath = str(ROOT / directory / 'preview-angle60.png')
    bpy.ops.render.render(write_still=True)
