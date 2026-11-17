"""Render the low head-to-body rig as top-down sprites, posed like the game.

blender --background --threads 4 --python dev-samples/3d-stage1/rigged-armor/render-chibi-sprites.py [-- --sword chimera|cursed|blessed]

Run build-chibi.py first; this opens hero-rig-chibi.blend. The camera looks
down at 60 degrees, orthographic, as in the game. Each sample pose is drawn
in the four facings (the collapsed one once, without a sword) as
sprite_pose.py poses it. Writes sprite-<pose>-<facing>.png (and
sprite-collapsed.png) next to this script.
"""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from sprite_pose import (CHIBI_BLEND, FACINGS, POSE_FRAMES, bake, figure_parts, show_sword,
                         standing_extent)


def main():
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    sword = args[args.index('--sword') + 1] if '--sword' in args else 'own'
    bpy.ops.wm.open_mainfile(filepath=str(CHIBI_BLEND))
    scene = bpy.context.scene
    rig = bpy.data.objects['Hero rig']
    camera = scene.camera
    angle, target = math.radians(60), Vector((0, .05, .5))
    camera.location = target + Vector((0, -10 * math.cos(angle), 10 * math.sin(angle)))
    camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera.data.ortho_scale = 1.75
    scene.render.resolution_x = scene.render.resolution_y = 400
    show_sword(scene.objects, sword)
    parts = figure_parts(scene, rig)
    floor, _ = standing_extent(scene, rig, parts)
    for pose in POSE_FRAMES:
        collapsed = pose == 'collapsed'
        for facing in ('down',) if collapsed else FACINGS:
            copies = bake(scene, rig, parts, pose, facing, floor)
            for part in parts:
                part.hide_render = True
            suffix = '' if sword == 'own' or collapsed else f'-{sword}'
            name = 'sprite-collapsed' if collapsed else f'sprite-{pose}-{facing}{suffix}'
            scene.render.filepath = str(HERE / f'{name}.png')
            bpy.ops.render.render(write_still=True)
            for copy in copies:
                mesh = copy.data
                bpy.data.objects.remove(copy)
                bpy.data.meshes.remove(mesh)
            for part in parts:
                part.hide_render = False


if __name__ == '__main__':
    main()
