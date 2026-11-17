"""Build a bone-first, rigid plate armor study with editable FK poses.

blender --background --threads 4 --python dev-samples/3d-stage1/rigged-armor/build.py
"""
import math
from pathlib import Path

import bmesh
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
        f'hip_plate.{side}': ((sign*.19, -.122, .997), (sign*.19, -.122, .741), 'pelvis'),
    })


def material(name, color, metallic=0, roughness=.38, emission=None, strength=0,
             rim=None, rim_strength=0):
    """Principled material with the heroic sprites' optional Fresnel rim glow
    (see ../build-heroic.py material())."""
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    shader = nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (*color, 1)
    shader.inputs['Metallic'].default_value = metallic
    shader.inputs['Roughness'].default_value = roughness
    shader.inputs['IOR'].default_value = 1.45
    if emission:
        shader.inputs['Emission Color'].default_value = (*emission, 1)
        shader.inputs['Emission Strength'].default_value = strength
    if rim:
        weight = nodes.new('ShaderNodeLayerWeight')
        weight.inputs['Blend'].default_value = .3
        power = nodes.new('ShaderNodeMath')
        power.operation = 'POWER'
        power.inputs[1].default_value = 3.5
        glow = nodes.new('ShaderNodeEmission')
        glow.inputs['Color'].default_value = (*rim, 1)
        glow.inputs['Strength'].default_value = rim_strength
        add = nodes.new('ShaderNodeAddShader')
        mix = nodes.new('ShaderNodeMixShader')
        links.new(weight.outputs['Facing'], power.inputs[0])
        links.new(power.outputs[0], mix.inputs['Fac'])
        links.new(shader.outputs[0], add.inputs[0])
        links.new(glow.outputs[0], add.inputs[1])
        links.new(shader.outputs[0], mix.inputs[1])
        links.new(add.outputs[0], mix.inputs[2])
        links.new(mix.outputs[0], nodes['Material Output'].inputs['Surface'])
    return mat


def chainmail_material(name, pitch=.016):
    """Blackened iron mail: staggered rows of raised rings, each overlapping
    its neighbors, over a dark gap,
    laid out on the mesh UVs (in meters, so `pitch` is the ring spacing)."""
    mat = material(name, (.10, .10, .115), 1.0, .38)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    shader = nodes['Principled BSDF']

    def math_node(op, a, b=None):
        node = nodes.new('ShaderNodeMath')
        node.operation = op
        for socket, value in ((node.inputs[0], a), (node.inputs[1], b)):
            if value is None:
                continue
            if isinstance(value, (int, float)):
                socket.default_value = value
            else:
                links.new(value, socket)
        return node.outputs[0]

    uv = nodes.new('ShaderNodeTexCoord').outputs['UV']
    split = nodes.new('ShaderNodeSeparateXYZ')
    links.new(uv, split.inputs[0])
    x = math_node('DIVIDE', split.outputs['X'], pitch)
    # Rows overlap like real mail, so they sit closer than the ring spacing.
    y = math_node('DIVIDE', split.outputs['Y'], pitch * .75)
    # Every other row shifts by half a ring.
    odd = math_node('FLOORED_MODULO', math_node('FLOOR', y), 2)
    x = math_node('ADD', x, math_node('MULTIPLY', odd, .5))
    fx = math_node('SUBTRACT', math_node('FRACT', x), .5)
    fy = math_node('MULTIPLY', math_node('SUBTRACT', math_node('FRACT', y), .5), .75)
    distance = math_node('SQRT', math_node('ADD', math_node('MULTIPLY', fx, fx),
                                           math_node('MULTIPLY', fy, fy)))
    off_wire = math_node('ABSOLUTE', math_node('SUBTRACT', distance, .44))
    ring = nodes.new('ShaderNodeMapRange')
    ring.interpolation_type = 'SMOOTHSTEP'
    ring.inputs['From Min'].default_value, ring.inputs['From Max'].default_value = 0, .09
    ring.inputs['To Min'].default_value, ring.inputs['To Max'].default_value = 1, 0
    links.new(off_wire, ring.inputs['Value'])
    wire = ring.outputs['Result']
    color = nodes.new('ShaderNodeMix')
    color.data_type = 'RGBA'
    color.inputs['A'].default_value = (.008, .009, .012, 1)
    color.inputs['B'].default_value = (.13, .13, .15, 1)
    links.new(wire, color.inputs['Factor'])
    links.new(color.outputs['Result'], shader.inputs['Base Color'])
    links.new(math_node('SUBTRACT', .75, math_node('MULTIPLY', wire, .45)),
              shader.inputs['Roughness'])
    bump = nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = .8
    bump.inputs['Distance'].default_value = .003
    links.new(wire, bump.inputs['Height'])
    links.new(bump.outputs['Normal'], shader.inputs['Normal'])
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
    count = (64 if joint_inner_front is not None and open_ends else
             32 if joint_inner_front is not None or open_ends else 12)
    def opening(i):
        """Above .5 lies in the cut-out: the bend's inner side for hinge caps
        (local +Z is front), otherwise the side facing the body center."""
        angle = i * 2 * math.pi / count
        if joint_inner_front is not None:
            return (1 if joint_inner_front else -1) * math.cos(angle)
        return (1 if bone_name.endswith('.L') else -1) * math.sin(angle)
    alongs = [[along * (.95 + (-.80 if joint_inner_front else .80) *
                        math.cos(i*2*math.pi/count)
                        if joint_inner_front is not None else 1)
               for i in range(count)] for along, _, _ in rings]
    sizes = [[(width, depth)] * count for _, width, depth in rings]
    tapered = open_ends and joint_inner_front is not None
    if tapered:
        # Hinge caps narrow toward the cut-out and close with a rounded end
        # at the height of the widest ring, tucked in to the slimmest radius.
        widest = max(range(len(rings)), key=lambda r: rings[r][1])
        edge = math.acos(max(opening(i) for i in range(count) if opening(i) <= .5))
        for i in range(count):
            t = min(1, max(0, (math.acos(max(-1, min(1, opening(i)))) - edge)
                           / (math.pi - edge)))
            # Elliptic profile: vertical at the edge, so the tip is rounded.
            taper = math.sqrt(t * (2 - t))
            middle = alongs[widest][i]
            mid_w, mid_d = min(s[i][0] for s in sizes), min(s[i][1] for s in sizes)
            for r in range(len(rings)):
                width, depth = sizes[r][i]
                alongs[r][i] = middle + (alongs[r][i] - middle) * taper
                sizes[r][i] = (mid_w + (width - mid_w) * taper,
                               mid_d + (depth - mid_d) * taper)
    verts = [matrix @ Vector((sizes[r][i][0]*math.sin(i*2*math.pi/count), alongs[r][i],
                             sizes[r][i][1]*math.cos(i*2*math.pi/count)))
             for r in range(len(rings)) for i in range(count)]
    faces = [] if open_ends else [tuple(reversed(range(count)))]
    for row in range(len(rings)-1):
        for i in range(count):
            if open_ends and opening(i + .5) > .5:
                continue
            a, b = row*count+i, row*count+(i+1)%count
            faces.append((a, b, b+count, a+count))
    if open_ends and top_cap:
        faces.append(tuple(reversed([i for i in range(count) if opening(i) <= .5])))
    if not open_ends:
        faces.append(tuple((len(rings)-1)*count+i for i in range(count)))
    # Ring order in local X/Z has its normal along -Y.
    faces = [tuple(reversed(face)) for face in faces]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    if tapered:
        # Weld each collapsed edge column into a single tip vertex.
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
        bm.to_mesh(mesh)
        bm.free()
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


# Hip armor rings on the pelvis bone: (distance along bone, half-width, half-depth).
HIP_RINGS = [(0, .17, .12), (.08, .19, .14), (.205, .16, .12)]


def hip_radius(z):
    """Half-width and half-depth of the hip armor at height z."""
    base = BONES['pelvis'][0][2]
    for (a0, w0, d0), (a1, w1, d1) in zip(HIP_RINGS, HIP_RINGS[1:]):
        if base + a0 <= z <= base + a1:
            f = (z - base - a0) / (a1 - a0)
            return w0 + (w1 - w0) * f, d0 + (d1 - d0) * f
    raise ValueError(z)


# Belt strap around the top of the hip armor, below the breastplate hem; the
# mail skirts hang from inside it. BELT_RX/RY is the ellipse just inside the
# strap where the mail's top edge sits.
BELT_Z, BELT_WIDTH, BELT_THICKNESS = 1.045, .045, .008
BELT_RX, BELT_RY = (r + .004 for r in hip_radius(BELT_Z))


def helmet_crest_and_horns(rig, mat):
    """Crest and horns of the heroic player's helm (../build-heroic.py),
    scaled 0.8 about its head center (0, -.04, .83) onto this helmet's center."""
    def heroic(x, y, z):
        return Vector((x * .8, (y + .04) * .8, 1.67 + (z - .83) * .8))

    # A thin plate, a horn-like triangle from the side: its base runs along
    # the top of the helm and it sweeps forward and up past the visor.
    profile = [heroic(0, -.02, .985), heroic(0, -.17, .955), heroic(0, -.23, 1.063)]
    vertices = [(side * .02, p.y, p.z) for side in (-1, 1) for p in profile]
    faces = [(0, 1, 2), (5, 4, 3), (0, 3, 4, 1), (1, 4, 5, 2), (2, 5, 3, 0)]
    mesh = bpy.data.meshes.new('Helmet crest')
    mesh.from_pydata(vertices, [], faces)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    crest = bpy.data.objects.new('Helmet crest', mesh)
    bpy.context.collection.objects.link(crest)
    attach(crest, rig, 'head', mat).modifiers['Forged edge'].width = .003
    # Four-sided horns from the sides of the helm, out, back and up.
    for side, sign in (('L', 1), ('R', -1)):
        start = heroic(sign * .15, 0, .90)
        end = heroic(sign * .27, .11, 1.06)
        delta = end - start
        bpy.ops.mesh.primitive_cone_add(vertices=4, radius1=.055 * .8, radius2=0,
                                        depth=delta.length, location=(start + end) / 2)
        horn = bpy.context.object
        horn.name = f'Helmet horn {side}'
        horn.rotation_euler = delta.to_track_quat('Z', 'Y').to_euler()
        # attach() reads matrix_world, which only picks up the rotation after an update.
        bpy.context.view_layer.update()
        attach(horn, rig, 'head', mat).modifiers['Forged edge'].width = .003


def belt(rig, strap_mat, buckle_mat):
    """Flat strap hugging the tapered hip armor, with a square front buckle."""
    count, vertices = 64, []
    for z in (BELT_Z - BELT_WIDTH / 2, BELT_Z + BELT_WIDTH / 2):
        width, depth = hip_radius(z)
        width, depth = width + .009, depth + .009
        for i in range(count):
            angle = i * 2 * math.pi / count
            vertices.append((width * math.sin(angle), -depth * math.cos(angle), z))
    # Ordered so the normals face outward.
    faces = [(i, i + count, (i + 1) % count + count, (i + 1) % count)
             for i in range(count)]
    mesh = bpy.data.meshes.new('Belt')
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    strap = bpy.data.objects.new('Belt', mesh)
    bpy.context.collection.objects.link(strap)
    for face in mesh.polygons:
        face.use_smooth = True
    attach(strap, rig, 'pelvis', strap_mat).modifiers['Forged edge'].width = .002
    shell = strap.modifiers.new('Strap thickness', 'SOLIDIFY')
    shell.thickness = BELT_THICKNESS
    bpy.context.view_layer.objects.active = strap
    bpy.ops.object.modifier_move_up(modifier=shell.name)
    bpy.ops.object.modifier_move_up(modifier=shell.name)

    # Buckle: a plain square plate, just proud of the strap.
    # The hip armor flares downward, so clear the strap's lower (outer) edge.
    front = hip_radius(BELT_Z - BELT_WIDTH / 2)[1] + .009 + .004
    bpy.ops.mesh.primitive_cube_add(location=(0, -front, BELT_Z))
    buckle = bpy.context.object
    buckle.name = 'Belt buckle'
    buckle.scale = (.03, .004, .028)
    # attach() reads matrix_world, which only picks up the scale after an update.
    bpy.context.view_layer.update()
    bevel = attach(buckle, rig, 'pelvis', buckle_mat).modifiers['Forged edge']
    bevel.width, bevel.segments = .003, 3


def diagonal_waist_plates(rig, mat):
    """Hang curved mail skirts around the front-side quarters of the hips.

    The upper band is fixed to the pelvis. The lower plate tucks under it and
    swings on hip_plate so a raised thigh does not pass through it.
    """
    # Arc centered 50 degrees away from the front, wrapping toward the side.
    parts = [('Diagonal waist plate', 'pelvis',
              # Top edge on the belt's centerline, hidden inside it.
              [(BELT_Z, BELT_RX, BELT_RY, 24), (.997, .25, .19, 29)]),
             ('Diagonal waist plate lower', 'hip_plate',
              [(1.009, .238, .178, 29), (.853, .28, .21, 29), (.741, .27, .20, 24)])]
    for side, sign in (('L', 1), ('R', -1)):
        for name, bone_name, rows in parts:
            vertices, uvs = [], []
            for z, radius_x, radius_y, half_angle in rows:
                for i in range(13):
                    angle = math.radians(50 + half_angle * (2 * i / 12 - 1))
                    vertices.append((sign * radius_x * math.sin(angle),
                                     -radius_y * math.cos(angle), z))
                    # Arc length and height in meters, shared by both parts
                    # so the mail pattern runs on across the seam.
                    uvs.append((sign * (angle - math.radians(50)) * .25, z))
            faces = []
            for row in range(len(rows) - 1):
                for i in range(12):
                    a = row * 13 + i
                    face = (a, a + 1, a + 14, a + 13)
                    faces.append(face if sign == 1 else tuple(reversed(face)))
            mesh = bpy.data.meshes.new(f'{name} {side}')
            mesh.from_pydata(vertices, [], faces)
            layer = mesh.uv_layers.new(name='Mail')
            for loop in mesh.loops:
                layer.data[loop.index].uv = uvs[loop.vertex_index]
            mesh.update()
            obj = bpy.data.objects.new(mesh.name, mesh)
            bpy.context.collection.objects.link(obj)
            attach(obj, rig, bone_name if bone_name == 'pelvis' else f'{bone_name}.{side}', mat)
            for face in mesh.polygons:
                face.use_smooth = True
            # Mail is thinner than plate.
            solidify = obj.modifiers.new('Mail thickness', 'SOLIDIFY')
            solidify.thickness = .007
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.modifier_move_up(modifier=solidify.name)
            bpy.ops.object.modifier_move_up(modifier=solidify.name)


def build_armor(rig):
    # Same finishes as the heroic player sprite (../build-heroic.py).
    steel = material('Player steel plate', (.55, .63, .74), .8, .32,
                     rim=(.6, .85, 1.0), rim_strength=.8)
    helm = material('Player steel helm', (.62, .70, .80), .85, .28,
                    rim=(.7, .9, 1.0), rim_strength=.9)
    greaves = material('Player steel greaves', (.45, .52, .62), .8, .35,
                       rim=(.6, .8, 1.0), rim_strength=.6)
    trim = material('Player dark iron trim', (.16, .16, .18), 1.0, .35)
    dark = material('Dark joint lining', (.025, .034, .045), .15)
    plate(rig, 'pelvis', 'Hip armor', HIP_RINGS, steel)
    plate(rig, 'waist', 'Flexible waist lining', [(0,.135,.10),(.16,.145,.11)], dark)
    belt(rig, trim, trim)
    diagonal_waist_plates(rig, chainmail_material('Blackened chainmail'))
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
    helmet = plate(rig, 'head', 'Helmet', helmet_rings, helm)
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
    glow = material('Player visor glow', (.3, .9, 1.0), roughness=.35,
                    emission=(.1, .75, 1.0), strength=2.5)
    curved_visor('Visor illuminated opening', .15, .032, .014, glow)
    helmet_crest_and_horns(rig, trim)
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
                   (length-.025,width*.75,depth*.8)],
                  greaves if part in ('thigh', 'shin') else steel)
        plate(rig, f'upper_arm.{side}', f'Pauldron {side}',
              [(-.083,.008,.008),(-.077,.04,.04),(-.061,.07,.07),
               (-.035,.095,.095),(0,.115,.115),(.035,.122,.122),
               (.07,.117,.113),(.096,.105,.098),(.114,.095,.085)],
              trim, open_ends=True)
        plate(rig, f'shin.{side}', f'Knee cap {side}',
              [(-.035,.057,.065),(-.028,.073,.082),(-.012,.086,.095),
               (.01,.091,.10),(.032,.086,.094),(.048,.073,.08),(.055,.062,.068)], trim,
              joint_inner_front=False, open_ends=True, top_cap=False)
        plate(rig, f'forearm.{side}', f'Elbow cap {side}',
              [(-.025,.045,.052),(-.018,.061,.068),(-.004,.073,.08),
               (.014,.078,.085),(.032,.072,.079),(.045,.058,.064),(.05,.049,.055)], trim,
              joint_inner_front=True, open_ends=True, top_cap=False)
        plate(rig, f'foot.{side}', f'Sabaton {side}',
              [(-.025,.065,.055),(.075,.08,.06),(.20,.065,.04)], greaves)
    for obj in bpy.context.scene.objects:
        if obj.name.startswith(('Pauldron ', 'Knee cap ', 'Elbow cap ')):
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
    # Render, world and light rig follow the heroic sprites (../build-heroic.py).
    scene.cycles.samples = 96
    scene.cycles.use_denoising = False
    scene.cycles.sample_clamp_indirect = 2.0
    scene.cycles.blur_glossy = 1.0
    scene.cycles.caustics_reflective = scene.cycles.caustics_refractive = False
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'Medium High Contrast'
    scene.world = bpy.data.worlds.new('Night studio')
    scene.world.use_nodes = True
    scene.world.node_tree.nodes['Background'].inputs['Color'].default_value = (.012, .018, .03, 1)
    floor = material('Night floor', (.006, .008, .014), roughness=.8)
    ground_z = min((obj.matrix_world @ v.co).z for obj in scene.objects
                   if obj.type == 'MESH' for v in obj.data.vertices)
    bpy.ops.mesh.primitive_plane_add(size=200)
    bpy.context.object.name = 'Studio floor'
    bpy.context.object.location.z = ground_z - .005
    bpy.context.object.data.materials.append(floor)
    # Warm key, cool fill, strong back rim lights for glossy edges.
    for name, loc, power, size, color in [
            ('Key', (-4,-6,8), 1000, 5, (1.0,.93,.85)),
            ('Fill', (6,-3,4), 250, 6, (.6,.75,1.0)),
            ('Rim left', (-7,6,4), 1300, 3, (.55,.8,1.0)),
            ('Rim right', (7,6,4), 1300, 3, (1.0,.7,.9))]:
        bpy.ops.object.light_add(type='AREA', location=loc)
        obj = bpy.context.object
        obj.name, obj.data.energy, obj.data.shape, obj.data.size = name, power, 'DISK', size
        obj.data.color = color
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
