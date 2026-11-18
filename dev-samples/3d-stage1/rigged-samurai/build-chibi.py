"""Build hero-rig-chibi.blend and pose previews using armor's rig rescaling.

Run with Blender in background mode after generating rigged-armor/hero-rig.blend.
"""

import importlib.util
import math
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent


def load_builder(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tall = load_builder('samurai_tall', HERE / 'build.py')
armor_chibi = load_builder('armor_chibi', tall.RIG_DIR / 'build-chibi.py')


def add_gauntlets(rig):
    iron = bpy.data.materials['Player dark iron trim']
    for side in ('L', 'R'):
        old_hand = bpy.data.objects.get(f'hand plate {side}')
        if old_hand:
            old_hand.hide_render = old_hand.hide_viewport = True
        bone = rig.data.bones[f'hand.{side}']
        center = bone.head_local.lerp(bone.tail_local, .55)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=.068,
                                            location=center)
        gauntlet = bpy.context.object
        gauntlet.name = f'Gauntlet {side}'
        tall.attach(gauntlet, rig, bone.name, iron)
        for face in gauntlet.data.polygons:
            face.use_smooth = True


def narrow_shoulders(rig):
    shifts = {}
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')
    bones = rig.data.edit_bones
    for side in ('L', 'R'):
        arm = bones[f'upper_arm.{side}']
        shift = Vector((-.07 * arm.head.x, 0, 0))
        targets = {}
        for segment in ('upper_arm', 'forearm', 'hand'):
            bone = bones[f'{segment}.{side}']
            targets[bone.name] = (bone.head + shift, bone.tail + shift)
            shifts[bone.name] = shift
        bones[f'clavicle.{side}'].tail = targets[arm.name][0]
        for name, (head, tail) in targets.items():
            bones[name].head = head
            bones[name].tail = tail
    bpy.ops.object.mode_set(mode='OBJECT')

    for obj in rig.children:
        if obj.type == 'MESH' and obj.parent_bone in shifts:
            bone = rig.data.bones[obj.parent_bone]
            tip = Matrix.Translation((0, bone.length, 0))
            obj.matrix_parent_inverse = (rig.matrix_world @ bone.matrix_local @ tip).inverted()
            obj.data.transform(Matrix.Translation(shifts[bone.name]))
    bpy.context.view_layer.update()


def chibify_samurai(scene, rig):
    grip = bpy.data.objects['Katana hand mount']
    bone = rig.data.bones['hand.R']
    original_head = bone.head_local.copy()
    old_parent = rig.matrix_world @ bone.matrix_local @ Matrix.Translation((0, bone.length, 0))
    original_mount = old_parent @ grip.matrix_parent_inverse
    # The armor rescaler works on bone-parented meshes. Keep the five katana
    # pieces together and scale the mount uniformly with the hand afterward.
    grip.parent = None
    armor_chibi.chibify(rig, scene)
    narrow_shoulders(rig)

    bone = rig.data.bones['hand.R']
    tip = Matrix.Translation((0, bone.length, 0))
    rest_parent = rig.matrix_world @ bone.matrix_local @ tip
    shrink = (Matrix.Translation(bone.head_local)
              @ Matrix.Scale(armor_chibi.region_scale(bone.name), 4)
              @ Matrix.Translation(-original_head))
    grip.parent = rig
    grip.parent_type = 'BONE'
    grip.parent_bone = bone.name
    grip.matrix_parent_inverse = rest_parent.inverted() @ shrink @ original_mount

    forward = Vector((0, -1, 0))
    for frame in (1, 40, 80):
        scene.frame_set(frame)
        wrist = rig.matrix_world @ rig.pose.bones[bone.name].matrix @ tip
        unrolled = wrist @ grip.matrix_parent_inverse
        local_forward = unrolled.to_3x3().inverted() @ forward
        grip.rotation_euler.x = math.atan2(local_forward.z, local_forward.y)
        grip.keyframe_insert(data_path='rotation_euler', index=0, frame=frame)
    scene.frame_set(1)


def widen_limbs(rig):
    for side, outward in (('L', 1), ('R', -1)):
        for segment in ('upper_arm', 'forearm', 'shin'):
            bone = rig.data.bones[f'{segment}.{side}']
            rest = bone.matrix_local
            across = Matrix.Diagonal((1.12, 1.0, 1.12, 1.0))
            bpy.data.objects[f'{segment} plate {side}'].data.transform(
                rest @ across @ rest.inverted()
            )

        trousers = bpy.data.objects[f'Baggy trousers {side}']
        thigh = rig.data.bones[f'thigh.{side}']
        to_bone = thigh.matrix_local.inverted()
        for vertex in trousers.data.vertices:
            along = (to_bone @ vertex.co).y / thigh.length
            if .35 < along < 1:
                weight = math.sin(math.pi * (along - .35) / .65) ** 2
                axis_x = thigh.head_local.lerp(thigh.tail_local, along).x
                outside = max(0, outward * (vertex.co.x - axis_x))
                vertex.co.x += outward * outside * .10 * weight
        trousers.data.update()


def visible_points(rig):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    for obj in rig.children:
        if obj.type != 'MESH' or obj.hide_render:
            continue
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        yield from (evaluated.matrix_world @ vertex.co for vertex in mesh.vertices)
        evaluated.to_mesh_clear()


def add_collapsed_pose(scene, rig):
    frame = armor_chibi.build.COLLAPSED_FRAME
    _, rotations = armor_chibi.build.POSES[frame]
    standing_floor = min(point.z for point in visible_points(rig))
    scene.frame_set(frame)
    for bone in rig.pose.bones:
        if bone.name.startswith(('hip_plate.', 'tasset.', 'cape.')):
            continue
        x, y, z = rotations.get(bone.name, (0, 0, 0))
        if bone.name in ('waist', 'neck'):
            y, z = z, y
        bone.rotation_euler = tuple(math.radians(angle) for angle in (x, y, z))
        bone.keyframe_insert('rotation_euler', frame=frame, group=bone.name)
    bpy.context.view_layer.update()
    points = list(visible_points(rig))
    center_x = (min(p.x for p in points) + max(p.x for p in points)) / 2
    center_y = (min(p.y for p in points) + max(p.y for p in points)) / 2
    lift = standing_floor - min(p.z for p in points)
    root = rig.pose.bones['root']
    # Translate in the root's rest axes so the prone figure meets the floor.
    for key in (1, 40, 80, frame):
        root.location = (-center_x, lift, center_y) if key == frame else (0, 0, 0)
        root.keyframe_insert('location', frame=key, group='root')

    visor = bpy.data.materials['Mask visor glow'].node_tree.nodes['Principled BSDF']
    brightness = visor.inputs['Emission Strength']
    for key in (80, frame):
        brightness.default_value = .12 if key == frame else .8
        brightness.keyframe_insert('default_value', frame=key)
        for part in bpy.data.objects['Katana hand mount'].children:
            part.hide_render = part.hide_viewport = key == frame
            part.keyframe_insert('hide_render', frame=key)
            part.keyframe_insert('hide_viewport', frame=key)

    scene.timeline_markers.new('COLLAPSED', frame=frame)
    scene.frame_end = frame
    scene.frame_set(1)


def set_camera(camera, target, view):
    camera.location = target + Vector(view)
    camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()


def main():
    bpy.ops.wm.open_mainfile(filepath=str(tall.RIG_DIR / 'hero-rig.blend'))
    scene = bpy.context.scene
    rig = bpy.data.objects['Hero rig']
    if rig.mode != 'OBJECT':
        bpy.context.view_layer.objects.active = rig
        bpy.ops.object.mode_set(mode='OBJECT')
    scene.frame_set(1)
    tall.build_armor(rig)
    add_gauntlets(rig)
    chibify_samurai(scene, rig)
    widen_limbs(rig)
    add_collapsed_pose(scene, rig)

    visible = [obj for obj in rig.children if obj.type == 'MESH' and not obj.hide_render]
    floor = bpy.data.objects['Studio floor']
    floor.location.z = min((obj.matrix_world @ v.co).z for obj in visible
                           for v in obj.data.vertices) - .002
    scene.cycles.samples = 48
    scene.cycles.use_denoising = False
    scene.render.resolution_x, scene.render.resolution_y = 640, 720
    scene.camera.data.ortho_scale = 1.48
    target = Vector((0, 0, .57))
    front = (2, -6, 1.35)
    for name, frame, view in (
        ('chibi-rest', 1, front),
        ('chibi-step', 80, (-2.3, -6, 1.55)),
        ('chibi-top', 1, (0, -3, 5.196)),
        ('chibi-collapsed', 120, (0, -3, 5.196)),
    ):
        scene.frame_set(frame)
        set_camera(scene.camera, target, view)
        scene.render.filepath = str(HERE / f'{name}.png')
        bpy.ops.render.render(write_still=True)
    scene.frame_set(1)
    set_camera(scene.camera, target, front)
    scene.render.filepath = '//chibi-rest.png'
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(HERE / 'hero-rig-chibi.blend'))


if __name__ == '__main__':
    main()
