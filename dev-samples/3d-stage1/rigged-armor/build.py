"""Build a bone-first, rigid plate armor study with editable FK poses.

blender --background --threads 4 --python dev-samples/3d-stage1/rigged-armor/build.py
"""
import math
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent

# Z up, -Y forward, character's left is +X. All geometry derives from these bones.
BONES = {
    'root': ((0, 0, 0), (0, 0, .18), None),
    'pelvis': ((0, 0, .88), (0, 0, 1.02), 'root'),
    'waist': ((0, 0, 1.02), (0, 0, 1.18), 'pelvis'),
    'chest': ((0, 0, 1.18), (0, 0, 1.48), 'waist'),
    'neck': ((0, 0, 1.48), (0, 0, 1.57), 'chest'),
    'head': ((0, 0, 1.57), (0, 0, 1.79), 'neck'),
}
for side, sign in [('L', 1), ('R', -1)]:
    BONES.update({
        f'clavicle.{side}': ((0, 0, 1.44), (sign*.25, 0, 1.44), 'chest'),
        f'upper_arm.{side}': ((sign*.25, 0, 1.44), (sign*.40, 0, 1.16), f'clavicle.{side}'),
        f'forearm.{side}': ((sign*.40, 0, 1.16), (sign*.47, -.015, .91), f'upper_arm.{side}'),
        f'hand.{side}': ((sign*.47, -.015, .91), (sign*.49, -.025, .80), f'forearm.{side}'),
        f'thigh.{side}': ((sign*.13, 0, .91), (sign*.15, -.025, .52), 'pelvis'),
        f'shin.{side}': ((sign*.15, -.025, .52), (sign*.15, 0, .12), f'thigh.{side}'),
        f'foot.{side}': ((sign*.15, 0, .12), (sign*.15, -.20, .065), f'shin.{side}'),
        # Hinge at the top of the lower diagonal waist plate; driven by the thigh.
        f'hip_plate.{side}': ((sign*.19, -.122, .98), (sign*.19, -.122, .66), 'pelvis'),
    })


def material(name, color, metallic=0):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (*color, 1)
    shader.inputs['Metallic'].default_value = metallic
    shader.inputs['Roughness'].default_value = .38
    return mat


def create_rig():
    data = bpy.data.armatures.new('Human skeleton')
    rig = bpy.data.objects.new('Hero rig', data)
    bpy.context.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    rig.show_in_front = True
    data.display_type = 'OCTAHEDRAL'
    bpy.ops.object.mode_set(mode='EDIT')
    for name, (head, tail, parent) in BONES.items():
        bone = data.edit_bones.new(name)
        bone.head, bone.tail = head, tail
        # Local X is the flexion axis for limbs; local Y follows the bone.
        bone.align_roll(Vector((0, -1, 0)))
        if parent:
            bone.parent = data.edit_bones[parent]
            bone.use_connect = (bone.head - bone.parent.tail).length < .0001
    bpy.ops.object.mode_set(mode='OBJECT')
    for bone in rig.pose.bones:
        bone.rotation_mode = 'XYZ'
        if bone.name != 'root':
            bone.lock_location = (True, True, True)
            bone.lock_scale = (True, True, True)
        if bone.name.startswith(('forearm.', 'shin.')):
            bone.lock_rotation = (False, True, True)
            limit = bone.constraints.new('LIMIT_ROTATION')
            limit.name = 'Hinge range'
            limit.owner_space = 'LOCAL'
            limit.use_limit_x = limit.use_limit_y = limit.use_limit_z = True
            # Positive X folds elbows forward; knees fold backward.
            limit.min_x, limit.max_x = ((0, math.radians(145))
                if bone.name.startswith('forearm.') else (math.radians(-145), 0))
        if bone.name.startswith('hip_plate.'):
            # Swing forward with a raised thigh; hang still when it moves back.
            bone.lock_rotation = (True, True, True)
            follow = bone.constraints.new('COPY_ROTATION')
            follow.name = 'Follow thigh'
            follow.target, follow.subtarget = rig, 'thigh.' + bone.name[-1]
            follow.use_y = follow.use_z = False
            follow.owner_space = follow.target_space = 'LOCAL'
            limit = bone.constraints.new('LIMIT_ROTATION')
            limit.name = 'Forward swing only'
            limit.owner_space = 'LOCAL'
            limit.use_limit_x = True
            limit.min_x, limit.max_x = 0, math.radians(90)
    return rig


def attach(obj, rig, bone_name, mat):
    """Bone parenting with explicit rest inverse: plates never deform."""
    obj.data.materials.append(mat)
    world = obj.matrix_world.copy()
    obj.parent = rig
    obj.parent_type = 'BONE'
    obj.parent_bone = bone_name
    bone = rig.data.bones[bone_name]
    rest_parent = rig.matrix_world @ bone.matrix_local @ Matrix.Translation((0, bone.length, 0))
    obj.matrix_parent_inverse = rest_parent.inverted()
    obj.matrix_basis = world
    obj['attached_to'] = bone_name
    if hasattr(obj.data, 'use_auto_smooth'):
        obj.data.use_auto_smooth = True
    bevel = obj.modifiers.new('Forged edge', 'BEVEL')
    bevel.width, bevel.segments = .008, 2
    obj.modifiers.new('Plate normals', 'WEIGHTED_NORMAL')
    return obj


def plate(rig, bone_name, name, rings, mat, joint_inner_front=None, open_ends=False,
          top_cap=True):
    """Rings in bone coordinates: (distance along bone, half-width, half-depth)."""
    matrix = rig.data.bones[bone_name].matrix_local
    count = 32 if joint_inner_front is not None or open_ends else 12
    verts = [matrix @ Vector((width*math.sin(i*2*math.pi/count),
                             along * (.95 + (-.80 if joint_inner_front else .80) *
                                      math.cos(i*2*math.pi/count)
                                      if joint_inner_front is not None else 1),
                             depth*math.cos(i*2*math.pi/count)))
             for along, width, depth in rings for i in range(count)]
    faces = [] if open_ends else [tuple(reversed(range(count)))]
    for row in range(len(rings)-1):
        for i in range(count):
            if open_ends:
                side = -1 if bone_name.endswith('.L') else 1
                if side * math.sin((i + .5) * 2 * math.pi / count) < -.5:
                    continue
            a, b = row*count+i, row*count+(i+1)%count
            faces.append((a, b, b+count, a+count))
    if open_ends and top_cap:
        side = -1 if bone_name.endswith('.L') else 1
        faces.append(tuple(reversed([i for i in range(count)
                                     if side * math.sin(i * 2 * math.pi / count) >= -.5])))
    if not open_ends:
        faces.append(tuple((len(rings)-1)*count+i for i in range(count)))
    # Ring order in local X/Z has its normal along -Y.
    faces = [tuple(reversed(face)) for face in faces]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    attach(obj, rig, bone_name, mat)
    if open_ends:
        shell = obj.modifiers.new('Armor shell thickness', 'SOLIDIFY')
        shell.thickness = .009
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_move_up(modifier=shell.name)
        bpy.ops.object.modifier_move_up(modifier=shell.name)
    return obj


def joint(rig, bone_name, radius, mat):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8,
                                      radius=radius, location=BONES[bone_name][0])
    obj = bpy.context.object
    obj.name = 'Joint ' + bone_name
    return attach(obj, rig, bone_name, mat)


def diagonal_waist_plates(rig, mat):
    """Hang curved tassets around the front-side quarters of the hips.

    The upper band is fixed to the pelvis. The lower plate tucks under it and
    swings on hip_plate so a raised thigh does not pass through it.
    """
    # Arc centered 50 degrees away from the front, wrapping toward the side.
    parts = [('Diagonal waist plate', 'pelvis',
              [(1.065, .19, .145, 23), (.98, .25, .19, 29)]),
             ('Diagonal waist plate lower', 'hip_plate',
              [(.995, .238, .178, 29), (.80, .28, .21, 29), (.66, .27, .20, 24)])]
    for side, sign in (('L', 1), ('R', -1)):
        for name, bone_name, rows in parts:
            vertices = []
            for z, radius_x, radius_y, half_angle in rows:
                for i in range(13):
                    angle = math.radians(50 + half_angle * (2 * i / 12 - 1))
                    vertices.append((sign * radius_x * math.sin(angle),
                                     -radius_y * math.cos(angle), z))
            faces = []
            for row in range(len(rows) - 1):
                for i in range(12):
                    a = row * 13 + i
                    face = (a, a + 1, a + 14, a + 13)
                    faces.append(face if sign == 1 else tuple(reversed(face)))
            mesh = bpy.data.meshes.new(f'{name} {side}')
            mesh.from_pydata(vertices, [], faces)
            mesh.update()
            obj = bpy.data.objects.new(mesh.name, mesh)
            bpy.context.collection.objects.link(obj)
            attach(obj, rig, bone_name if bone_name == 'pelvis' else f'{bone_name}.{side}', mat)
            solidify = obj.modifiers.new('Plate thickness', 'SOLIDIFY')
            solidify.thickness = .012
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.modifier_move_up(modifier=solidify.name)
            bpy.ops.object.modifier_move_up(modifier=solidify.name)


def build_armor(rig):
    steel = material('Satin steel', (.32, .43, .55), .75)
    trim = material('Blackened joint steel', (.09, .105, .125), .85)
    trim.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value = .28
    dark = material('Dark joint lining', (.025, .034, .045), .15)
    plate(rig, 'pelvis', 'Hip armor', [(0,.17,.12),(.08,.19,.14),(.205,.16,.12)], steel)
    plate(rig, 'waist', 'Flexible waist lining', [(0,.135,.10),(.16,.145,.11)], dark)
    diagonal_waist_plates(rig, steel)
    breastplate = plate(rig, 'chest', 'Breast and back plate', [(-.085,.175,.13),(.04,.205,.145),
          (.20,.235,.16),(.27,.20,.13),(.30,.115,.09)], steel)
    # Extend the front center of the lower rim into a shallow V over the abdomen.
    for i in range(12):
        angle = i * 2 * math.pi / 12
        breastplate.data.vertices[i].co.z -= .025 * max(0, math.cos(angle)) * (1 - abs(math.sin(angle)))
    for vertex in breastplate.data.vertices:
        vertex.co.x *= 1.1
    breastplate.data.update()
    joint(rig, 'neck', .075, dark)
    helmet_rings = [(-.035,.10,.105),(.025,.13,.13),
                    (.15,.125,.13),(.21,.10,.105),(.23,.055,.06)]
    helmet = plate(rig, 'head', 'Helmet', helmet_rings, steel)
    matrix = rig.data.bones['head'].matrix_local
    for row, (along, width, depth) in enumerate(helmet_rings):
        for i in range(12):
            angle = i * 2 * math.pi / 12
            x, z = math.sin(angle), math.cos(angle)
            helmet.data.vertices[row * 12 + i].co = matrix @ Vector((
                width * math.copysign(abs(x) ** .8, x), along,
                depth * math.copysign(abs(z) ** .8, z)))
    helmet.data.update()
    # Visor follows head, with front toward -Y in world space.
    def curved_visor(name, width, height, offset, mat):
        vertices = []
        for z in (1.66 - height / 2, 1.66 + height / 2):
            for i in range(25):
                x = width * (i / 24 - .5)
                y = -.13 * (1 - (abs(x) / .128) ** 2.5) ** .4 - offset
                vertices.append((x, y, z))
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(vertices, [], [(i, i + 1, i + 26, i + 25) for i in range(24)])
        mesh.update()
        obj = bpy.data.objects.new(name, mesh)
        bpy.context.collection.objects.link(obj)
        attach(obj, rig, 'head', mat)
        obj.modifiers['Forged edge'].width = .002
        shell = obj.modifiers.new('Visor thickness', 'SOLIDIFY')
        shell.thickness = .004
        for face in mesh.polygons:
            face.use_smooth = True
    curved_visor('Visor curved rim', .20, .075, .008, dark)
    glow = material('Visor pale cyan', (.22, .68, .78))
    shader = glow.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Emission Color'].default_value = (.12, .65, .8, 1)
    shader.inputs['Emission Strength'].default_value = 1.5
    curved_visor('Visor illuminated opening', .15, .032, .014, glow)
    for side in ('L','R'):
        for part, radius in [('upper_arm',.085),('forearm',.062),('hand',.05),
                             ('thigh',.085),('shin',.075),('foot',.055)]:
            joint(rig, f'{part}.{side}', radius, dark)
        for part, width, depth in [('upper_arm',.072,.075),('forearm',.066,.07),
                                    ('thigh',.092,.095),('shin',.072,.078),('hand',.06,.05)]:
            bone_name = f'{part}.{side}'
            length = rig.data.bones[bone_name].length
            plate(rig, bone_name, f'{part} plate {side}',
                  [(.045,width*.85,depth*.85),(length*.4,width,depth),
                   (length-.025,width*.75,depth*.8)], steel)
        plate(rig, f'upper_arm.{side}', f'Pauldron {side}',
              [(-.095,.008,.008),(-.088,.04,.04),(-.07,.07,.07),
               (-.04,.095,.095),(0,.115,.115),(.04,.122,.122),
               (.08,.117,.113),(.11,.105,.098),(.13,.095,.085)],
              trim, open_ends=True)
        plate(rig, f'shin.{side}', f'Knee cap {side}',
              [(-.035,.057,.065),(-.028,.073,.082),(-.012,.086,.095),
               (.01,.091,.10),(.032,.086,.094),(.048,.073,.08),(.055,.062,.068)], trim,
              joint_inner_front=False)
        plate(rig, f'forearm.{side}', f'Elbow cap {side}',
              [(-.025,.045,.052),(-.018,.061,.068),(-.004,.073,.08),
               (.014,.078,.085),(.032,.072,.079),(.045,.058,.064),(.05,.049,.055)], trim,
              joint_inner_front=True)
        plate(rig, f'foot.{side}', f'Sabaton {side}',
              [(-.025,.065,.055),(.075,.08,.06),(.20,.065,.04)], steel)
        # Cuisse shell hugs the thigh plate, open on the inner thigh; its top
        # edge starts inside the hip armor so no flat rim shows.
        plate(rig, f'thigh.{side}', f'Cuisse {side}',
              [(.03,.098,.104),(.08,.106,.112),(.15,.106,.112),
               (.21,.099,.104),(.25,.092,.097)], steel,
              open_ends=True, top_cap=False)
    for obj in bpy.context.scene.objects:
        if obj.name.startswith(('Pauldron ', 'Knee cap ', 'Elbow cap ', 'Cuisse ')):
            bevel = obj.modifiers['Forged edge']
            bevel.width, bevel.segments = .014, 4
            for face in obj.data.polygons:
                face.use_smooth = len(face.vertices) == 4


POSES = {
    1: ('REST', {}),
    40: ('GUARD', {'waist': (0, 0, 18), 'neck': (0, 0, -12),
         'upper_arm.R': (25, 0, -15), 'forearm.R': (95, 0, 0),
         'upper_arm.L': (35, 0, 15), 'forearm.L': (75, 0, 0),
         'thigh.L': (12, 0, 0), 'shin.L': (-18, 0, 0)}),
    80: ('STEP', {'waist': (0, 0, -10), 'neck': (0, 0, 10),
         'upper_arm.L': (-22, 0, 0), 'forearm.L': (20, 0, 0),
         'upper_arm.R': (25, 0, 0), 'forearm.R': (40, 0, 0),
         'thigh.L': (32, 0, 0), 'shin.L': (-40, 0, 0),
         'thigh.R': (-15, 0, 0), 'shin.R': (-12, 0, 0)}),
}


def animate(rig, scene):
    for frame, (label, rotations) in POSES.items():
        scene.timeline_markers.new(label, frame=frame)
        for bone in rig.pose.bones:
            if bone.name.startswith('hip_plate.'):
                continue
            angles = rotations.get(bone.name, (0,0,0))
            # Waist/neck twist around bone-local Y, which is upright.
            if bone.name in ('waist','neck'):
                angles = (angles[0], angles[2], angles[1])
            bone.rotation_euler = tuple(math.radians(v) for v in angles)
            bone.keyframe_insert('rotation_euler', frame=frame, group=bone.name)
    rig.animation_data.action.name = 'Rest - guard - step (FK studies)'
    scene.frame_end = 80
    scene.frame_set(1)


def setup_scene(scene):
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 48
    scene.cycles.use_denoising = False
    scene.world = bpy.data.worlds.new('Studio world')
    scene.world.color = (.18,.18,.18)
    floor = material('Studio floor', (.065,.08,.105))
    ground_z = min((obj.matrix_world @ v.co).z for obj in scene.objects
                   if obj.type == 'MESH' for v in obj.data.vertices)
    bpy.ops.mesh.primitive_plane_add(size=200)
    bpy.context.object.name = 'Studio floor'
    bpy.context.object.location.z = ground_z - .005
    bpy.context.object.data.materials.append(floor)
    for name, loc, power, size in [('Key', (3,-4,5), 650, 4),
                                  ('Fill', (-3,-2,3), 450, 3),
                                  ('Rim', (1,3,4), 800, 3)]:
        bpy.ops.object.light_add(type='AREA', location=loc)
        obj = bpy.context.object
        obj.name, obj.data.energy, obj.data.shape, obj.data.size = name, power, 'DISK', size
        obj.rotation_euler = (Vector((0,0,1))-obj.location).to_track_quat('-Z','Y').to_euler()
    bpy.ops.object.camera_add(location=(2.7,-6,2.7))
    camera = bpy.context.object
    camera.rotation_euler = (Vector((0,0,.95))-camera.location).to_track_quat('-Z','Y').to_euler()
    camera.data.type, camera.data.ortho_scale = 'ORTHO', 2.4
    scene.camera = camera
    scene.render.resolution_x, scene.render.resolution_y = 720, 800
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'


def validate(rig, scene):
    """Verify each required joint carries armor and actually moves it rigidly."""
    required = ['neck','waist'] + [f'{part}.{side}' for side in ('L','R')
                for part in ('upper_arm','forearm','thigh','shin')]
    meshes = [o for o in scene.objects if o.parent == rig]
    assert all(o.parent_type == 'BONE' and o.parent_bone in BONES for o in meshes)
    scene.frame_set(1)
    for name in required:
        bone = rig.pose.bones[name]
        child = next(o for o in meshes if o.parent_bone == name)
        before = child.matrix_world.copy()
        bone.rotation_euler.x = math.radians(-25 if name.startswith('shin') else 25)
        bpy.context.view_layer.update()
        after = child.matrix_world.copy()
        assert sum(abs(after[i][j]-before[i][j]) for i in range(4) for j in range(4)) > .01, name
        assert abs(after.to_3x3().determinant()-before.to_3x3().determinant()) < 1e-5, name
        bone.rotation_euler = (0,0,0)
        bpy.context.view_layer.update()
    scene.frame_set(1)
    print(f'Validated {len(required)} required joints, {len(BONES)} bones, {len(meshes)} rigid parts')


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    rig = create_rig()
    build_armor(rig)
    animate(rig, scene)
    setup_scene(scene)
    validate(rig, scene)
    bpy.ops.object.select_all(action='DESELECT')
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='POSE')
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                space = area.spaces.active
                space.region_3d.view_distance = 3.3
                space.region_3d.view_location = (0, 0, .95)
                space.region_3d.view_rotation = scene.camera.rotation_euler.to_quaternion()
                space.region_3d.view_perspective = 'ORTHO'
                space.shading.color_type = 'MATERIAL'
    bpy.ops.wm.save_as_mainfile(filepath=str(HERE / 'hero-rig.blend'))
    for frame, (label, _) in POSES.items():
        scene.frame_set(frame)
        scene.render.filepath = str(HERE / f'{label.lower()}.png')
        bpy.ops.render.render(write_still=True)


if __name__ == '__main__':
    main()
