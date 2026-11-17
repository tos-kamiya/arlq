"""Render the low head-to-body rig as top-down sprites, posed like the game.

blender --background --threads 4 --python dev-samples/3d-stage1/rigged-armor/render-chibi-sprites.py [-- --sword chimera|cursed|blessed]

Run build-chibi.py first; this opens hero-rig-chibi.blend. The camera looks
down at 60 degrees, orthographic, as in the game. For each sample pose and
facing (down, left, right, up) the figure is turned about its feet, then
the whole body leans back a little about the feet and the head tilts back
further at the neck, so the face reads from above. Both are rigid turns
about the screen's horizontal axis, applied to baked copies of the evaluated
meshes, so the rig itself is left unchanged. Writes
sprite-<pose>-<facing>.png next to this script.
"""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
BODY_LEAN, HEAD_TILT = 0.1, 0.3    # radians, back from the camera
FACINGS = {'down': 0, 'left': -90, 'right': 90, 'up': 180}    # turn in degrees
POSE_FRAMES = {'rest': 1, 'guard': 40, 'step': 80, 'collapsed': 120}
# The sword in the right hand: the parts whose names start with each prefix.
SWORDS = {'own': 'Sword ', 'chimera': 'Chimera sword ', 'cursed': 'Cursed sword ',
          'blessed': 'Blessed sword '}


def main():
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    sword = args[args.index('--sword') + 1] if '--sword' in args else 'own'
    bpy.ops.wm.open_mainfile(filepath=str(HERE / 'hero-rig-chibi.blend'))
    scene = bpy.context.scene
    rig = bpy.data.objects['Hero rig']
    for obj in scene.objects:
        for name, prefix in SWORDS.items():
            if obj.name.startswith(prefix):
                obj.hide_render = obj.hide_viewport = name != sword
    floor = bpy.data.objects['Studio floor'].location.z + .005
    camera = scene.camera
    angle, target = math.radians(60), Vector((0, .05, .5))
    camera.location = target + Vector((0, -10 * math.cos(angle), 10 * math.sin(angle)))
    camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera.data.ortho_scale = 1.75
    scene.render.resolution_x = scene.render.resolution_y = 400
    parts = [o for o in scene.objects if o.type == 'MESH' and o.parent == rig and not o.hide_render]
    feet = Vector((0, 0, floor))
    lean = Matrix.Translation(feet) @ Matrix.Rotation(-BODY_LEAN, 4, 'X') @ Matrix.Translation(-feet)
    for pose, frame in POSE_FRAMES.items():
        # The collapsed figure is laid out by its pose (head toward screen
        # lower right), drawn once, unleaned and without a sword.
        collapsed = pose == 'collapsed'
        for obj in scene.objects:
            for name, prefix in SWORDS.items():
                if obj.name.startswith(prefix):
                    obj.hide_render = obj.hide_viewport = collapsed or name != sword
        visible = [part for part in parts if not part.hide_render]
        for facing, turn in ({'down': 0} if collapsed else FACINGS).items():
            rig.rotation_euler.z = math.radians(turn)
            scene.frame_set(frame)
            bpy.context.view_layer.update()
            depsgraph = bpy.context.evaluated_depsgraph_get()
            body = Matrix.Identity(4) if collapsed else lean
            neck = body @ (rig.matrix_world @ rig.pose.bones['head'].head)
            tilt = body if collapsed else (Matrix.Translation(neck) @ Matrix.Rotation(-HEAD_TILT, 4, 'X')
                                           @ Matrix.Translation(-neck) @ body)
            copies = []
            for part in visible:
                evaluated = part.evaluated_get(depsgraph)
                mesh = bpy.data.meshes.new_from_object(evaluated, preserve_all_data_layers=True,
                                                       depsgraph=depsgraph)
                on_head = part.parent_type == 'BONE' and part.parent_bone == 'head'
                mesh.transform((tilt if on_head else body) @ evaluated.matrix_world)
                copy = bpy.data.objects.new(part.name + ' sprite', mesh)
                scene.collection.objects.link(copy)
                copies.append(copy)
                part.hide_render = True
            suffix = '' if sword == 'own' or collapsed else f'-{sword}'
            name = 'sprite-collapsed' if collapsed else f'sprite-{pose}-{facing}{suffix}'
            scene.render.filepath = str(HERE / f'{name}.png')
            bpy.ops.render.render(write_still=True)
            for copy in copies:
                mesh = copy.data
                bpy.data.objects.remove(copy)
                bpy.data.meshes.remove(mesh)
            for part in visible:
                part.hide_render = False


if __name__ == '__main__':
    main()
