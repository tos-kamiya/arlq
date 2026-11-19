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
        # Hinge driven by the thigh, for the samurai's side skirts (../rigged-samurai).
        f'hip_plate.{side}': ((sign*.148, -.094, .985), (sign*.148, -.094, .741), 'pelvis'),
        # Hinge at the top of the lower side tasset, on the flank; driven by the thigh.
        f'tasset.{side}': ((sign*.19, -.06, .955), (sign*.19, -.06, .79), 'pelvis'),
    })
# Angle of the side tassets' centers from the front, toward each side.
TASSET_ANGLE = 70


def material(name, color, metallic=0, roughness=.38, emission=None, strength=0,
             rim=None, rim_strength=0, transmission=0):
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
    shader.inputs['Transmission Weight'].default_value = transmission
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
        if bone.name.startswith(('hip_plate.', 'tasset.')):
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
          top_cap=True, segments=None):
    """Rings in bone coordinates: (distance along bone, half-width, half-depth)."""
    matrix = rig.data.bones[bone_name].matrix_local
    count = segments or (64 if joint_inner_front is not None and open_ends else
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


def squarish(obj, rig, bone_name, rings, exponent=.575):
    """Reshape a 12-sided plate's rings into rounded rectangles (a
    superellipse; a lower exponent gives sharper corners)."""
    matrix = rig.data.bones[bone_name].matrix_local
    for row, (along, width, depth) in enumerate(rings):
        for i in range(12):
            angle = i * 2 * math.pi / 12
            x, z = math.sin(angle), math.cos(angle)
            obj.data.vertices[row * 12 + i].co = matrix @ Vector((
                width * math.copysign(abs(x) ** exponent, x), along,
                depth * math.copysign(abs(z) ** exponent, z)))
    obj.data.update()
    return obj


def joint(rig, bone_name, radius, mat):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8,
                                      radius=radius, location=BONES[bone_name][0])
    obj = bpy.context.object
    obj.name = 'Joint ' + bone_name
    return attach(obj, rig, bone_name, mat)


def box(rig, bone_name, name, center, half_size, mat, bevel_width):
    """Rounded rigid block given by its center and half extents."""
    bpy.ops.mesh.primitive_cube_add(location=center)
    obj = bpy.context.object
    obj.name = name
    obj.scale = half_size
    # attach() reads matrix_world, which only picks up the scale after an update.
    bpy.context.view_layer.update()
    bevel = attach(obj, rig, bone_name, mat).modifiers['Forged edge']
    bevel.width, bevel.segments = bevel_width, 3
    return obj


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


# Breastplate rings on the chest bone: (distance along bone, half-width,
# half-depth); the plate is then widened by CHEST_WIDEN.
# Widest at heart height (z 1.30), narrowing gently up to the shoulders.
CHEST_RINGS = [(-.085, .175, .13), (.04, .205, .145), (.12, .225, .16),
               (.21, .213, .148), (.27, .19, .125), (.30, .115, .09)]
CHEST_WIDEN = 1.1


def ring_bar(rig, bone_name, name, points, radius, mat, cyclic=True):
    """Round bar (closed unless `cyclic` is False) through the given world
    points, rigid on a bone."""
    curve = bpy.data.curves.new(name, 'CURVE')
    curve.dimensions, curve.bevel_depth, curve.bevel_resolution = '3D', radius, 3
    spline = curve.splines.new('POLY')
    spline.points.add(len(points) - 1)
    for point, co in zip(spline.points, points):
        point.co = (*co, 1)
    spline.use_cyclic_u = cyclic
    if not cyclic:
        curve.use_fill_caps = True
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.convert(target='MESH')
    obj = bpy.context.object
    for face in obj.data.polygons:
        face.use_smooth = True
    attach(obj, rig, bone_name, mat).modifiers['Forged edge'].width = .002
    return obj


def chest_seams(rig, mat, heights=(1.21, 1.33), radius=.008):
    """Dark iron seams girdling the breastplate like the heroic player's
    plate seams (../build-heroic.py): round bars that follow the plate's
    12-sided section, half sunk into it. Heights keep the heroic torso's
    proportions between the belt and the shoulders."""
    base = BONES['chest'][0][2]
    for k, z in enumerate(heights):
        for (a0, w0, d0), (a1, w1, d1) in zip(CHEST_RINGS, CHEST_RINGS[1:]):
            if base + a0 <= z <= base + a1:
                f = (z - base - a0) / (a1 - a0)
                width, depth = (w0 + (w1 - w0) * f) * CHEST_WIDEN, d0 + (d1 - d0) * f
        points = []
        for i in range(12):
            angle = i * 2 * math.pi / 12
            corner = Vector((width * math.sin(angle), -depth * math.cos(angle), 0))
            # Push the bar's center out a little so half of it shows.
            corner += corner.normalized() * radius * .5
            points.append((corner.x, corner.y, z))
        ring_bar(rig, 'chest', f'Chest seam {k + 1}', points, radius, mat)


# Gorget rings (z, half-width, half-depth): a low chainmail cone that sits on
# the breastplate's top and narrows up to the neck, ending just below the
# helmet's lower edge. The profile is scaled by GORGET_SCALE about the top
# ring, in height and in flare alike, so its curve keeps its shape.
# GORGET_RADIUS then draws it in around the neck, as mail can hug it closely.
GORGET_SCALE, GORGET_RADIUS = .6, .8
GORGET_RINGS = [(1.525 - (1.525 - z) * GORGET_SCALE,
                 (.115 + (w - .115) * GORGET_SCALE) * GORGET_RADIUS,
                 (.10 + (d - .10) * GORGET_SCALE) * GORGET_RADIUS)
                for z, w, d in [(1.415, .235, .148), (1.45, .205, .135), (1.48, .16, .118),
                                (1.505, .128, .106), (1.525, .115, .10)]]


def shell_ring(rig, bone_name, name, rings, mat, thickness=.007, count=32, uv=False):
    """Smooth band open at both ends, through (z, half-width, half-depth) rings.
    With `uv`, U is the arc length around (seam at the back) and V the height,
    both in meters, as chainmail_material() expects."""
    vertices = [(width * math.sin(i * 2 * math.pi / count),
                 -depth * math.cos(i * 2 * math.pi / count), z)
                for z, width, depth in rings for i in range(count)]
    faces = [(r * count + i, r * count + (i + 1) % count,
              (r + 1) * count + (i + 1) % count, (r + 1) * count + i)
             for r in range(len(rings) - 1) for i in range(count)]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    if uv:
        layer = mesh.uv_layers.new(name='Mail')
        for face in mesh.polygons:
            # Angle from the front, in (-pi, pi]; faces across the back seam
            # take the continuous side.
            angles = {v: math.remainder(v % count * 2 * math.pi / count, 2 * math.pi)
                      for v in face.vertices}
            if max(angles.values()) - min(angles.values()) > math.pi:
                angles = {v: a + 2 * math.pi if a < 0 else a for v, a in angles.items()}
            for loop_index in face.loop_indices:
                v = mesh.loops[loop_index].vertex_index
                z, width, depth = rings[v // count]
                layer.data[loop_index].uv = (angles[v] * (width + depth) / 2, z)
    for face in mesh.polygons:
        face.use_smooth = True
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    attach(obj, rig, bone_name, mat).modifiers['Forged edge'].width = .002
    shell = obj.modifiers.new('Thickness', 'SOLIDIFY')
    shell.thickness = thickness
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_move_up(modifier=shell.name)
    bpy.ops.object.modifier_move_up(modifier=shell.name)
    return obj


def gorget(rig, mail, mat, count=32):
    """Chainmail gorget on the chest, a separate part over the breastplate,
    hanging from a dark iron rolled rim at its top edge."""
    shell_ring(rig, 'chest', 'Gorget', GORGET_RINGS, mail, uv=True)
    z, width, depth = GORGET_RINGS[-1]
    ring_bar(rig, 'chest', 'Gorget rim',
             [(width * math.sin(i * 2 * math.pi / count), -depth * math.cos(i * 2 * math.pi / count), z)
              for i in range(count)], .006, mat)


# Cape profile behind the body: (z, half-width, half-depth, half-span in
# degrees around the back). Its top edge wraps the back of the neck just
# outside the mail gorget; it then runs over the back of the shoulders, its
# corners tucked under the pauldrons, down to about the knees, flaring a
# little toward the hem.
CAPE_PROFILE = [(1.505, .12, .10, 60), (1.47, .20, .14, 64), (1.44, .235, .165, 66),
                (1.30, .255, .19, 70), (1.10, .265, .195, 71), (.90, .28, .21, 72),
                (.72, .30, .235, 74), (.55, .32, .26, 75)]
# Vertical folds: this many across the cape, as deep as CAPE_FOLD_DEPTH at
# the hem and flat at the top edge.
CAPE_FOLDS, CAPE_FOLD_DEPTH = 6, .022
# The cape billows like the heroic player's cloak, at half its amount: toward
# the hem it drifts back and a little toward the figure's left, growing with
# the square of the distance from the top (meters at the hem). The heroic
# cloak drifts back 0.42 and sideways 0.1 of its length.
CAPE_DRIFT_BACK, CAPE_DRIFT_SIDE = .2, .05
# Three bone chains (left, center, right) down the cape, at these angles from
# the front (180 is straight behind; left is +X), jointed at these heights.
CAPE_CHAINS = {'L': 140, 'C': 180, 'R': 220}
# Grid of the cape mesh: columns across the back, rows down from the top.
CAPE_COLUMNS, CAPE_ROWS = 48, 28
CAPE_JOINTS = [1.505, 1.24, 1.0, .78, .55]


def cape_section(z):
    """Interpolated (half-width, half-depth, half-span) of the cape at z."""
    z = min(max(z, CAPE_PROFILE[-1][0]), CAPE_PROFILE[0][0])
    for (z0, *a), (z1, *b) in zip(CAPE_PROFILE, CAPE_PROFILE[1:]):
        if z1 <= z <= z0:
            f = (z0 - z) / (z0 - z1)
            return [u + (v - u) * f for u, v in zip(a, b)]
    raise ValueError(z)


def cape_point(angle, z):
    """Point on the cape at `angle` degrees from the front, height z."""
    width, depth, _ = cape_section(z)
    top, hem = CAPE_PROFILE[0][0], CAPE_PROFILE[-1][0]
    drift = ((top - z) / (top - hem)) ** 2
    return Vector((width * math.sin(math.radians(angle)) + CAPE_DRIFT_SIDE * drift,
                   -depth * math.cos(math.radians(angle)) + CAPE_DRIFT_BACK * drift, z))


for _side, _angle in CAPE_CHAINS.items():
    for _k in range(len(CAPE_JOINTS) - 1):
        BONES[f'cape.{_side}.{_k + 1}'] = (
            tuple(cape_point(_angle, CAPE_JOINTS[_k])), tuple(cape_point(_angle, CAPE_JOINTS[_k + 1])),
            'chest' if _k == 0 else f'cape.{_side}.{_k}')


def cape(rig, mat, columns=CAPE_COLUMNS, rows=CAPE_ROWS):
    """Midnight-blue cloth cape, the one part that bends: an Armature modifier
    deforms it with the cape bone chains, each vertex weighted between the
    nearest chains around the back and the nearest bones down its length."""
    top, hem = CAPE_PROFILE[0][0], CAPE_PROFILE[-1][0]
    grid = []
    for r in range(rows + 1):
        z = top + (hem - top) * r / rows
        span = cape_section(z)[2]
        grid.append([(180 + span * (2 * c / columns - 1), z) for c in range(columns + 1)])
    def folded(angle, z, c):
        point = cape_point(angle, z)
        depth = CAPE_FOLD_DEPTH * ((top - z) / (top - hem)) ** 1.5
        wave = math.sin(c / columns * CAPE_FOLDS * 2 * math.pi)
        radial = Vector((point.x, point.y, 0)).normalized()
        return tuple(point + radial * depth * wave)
    vertices = [folded(a, z, c) for row in grid for c, (a, z) in enumerate(row)]
    faces = [(r * (columns + 1) + c, r * (columns + 1) + c + 1,
              (r + 1) * (columns + 1) + c + 1, (r + 1) * (columns + 1) + c)
             for r in range(rows) for c in range(columns)]
    mesh = bpy.data.meshes.new('Cape')
    mesh.from_pydata(vertices, [], faces)
    for face in mesh.polygons:
        face.use_smooth = True
    mesh.update()
    obj = bpy.data.objects.new('Cape', mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    obj.parent = rig
    groups = {name: obj.vertex_groups.new(name=name) for name in BONES if name.startswith('cape.')}
    mids = [(a + b) / 2 for a, b in zip(CAPE_JOINTS, CAPE_JOINTS[1:])]
    seg = CAPE_JOINTS[0] - CAPE_JOINTS[1]
    for index, (angle, z) in enumerate(a for row in grid for a in row):
        across = {s: max(0, 1 - abs(angle - a) / 40) for s, a in CAPE_CHAINS.items()}
        down = [max(0, 1 - abs(z - m) / seg) for m in mids]
        if z >= mids[0]:
            down = [1] + [0] * (len(mids) - 1)
        if z <= mids[-1]:
            down = [0] * (len(mids) - 1) + [1]
        total = sum(across.values()) * sum(down)
        for s, wa in across.items():
            for k, wd in enumerate(down):
                if wa * wd:
                    groups[f'cape.{s}.{k + 1}'].add([index], wa * wd / total, 'REPLACE')
    obj.modifiers.new('Cape bones', 'ARMATURE').object = rig
    cloth = obj.modifiers.new('Cloth thickness', 'SOLIDIFY')
    cloth.thickness = .006
    obj.modifiers.new('Soft folds', 'SUBSURF').levels = 1
    return obj




# Size of the heroic player's sword parts in this model's units: the heroic
# head is 0.34 tall and the chibi build's 0.265, and the hand shrinks to 0.55
# there, so the chibi sword keeps the heroic length relative to the head.
SWORD_UNIT = .265 / .34 / .55
# The blade is tipped this far (radians) further toward the figure's back
# than on the heroic sprite, and rolled this far about its length so its flat
# also shows when the figure faces up the screen.
SWORD_BACK_TILT, SWORD_ROLL = .2, .2


def own_sword(rig, blade_mat, guard_mat, prefix='Sword', hidden=False):
    """The player's own broad short sword in the right hand, as on the heroic
    sprite (../build-heroic.py player()): the blade points up to screen left
    and a little into the screen, its width in the screen plane; a dark iron
    guard crosses it a little along the blade from the fist. The K blessing's
    glowing sword is the same sword under another `prefix`, built `hidden`."""
    u = SWORD_UNIT
    head, tail = (Vector(p) for p in BONES['hand.R'][:2])
    fist = head + (tail - head) * .6
    ahead = Vector((-.75, .3, .32)).normalized()
    # Tip the blade toward the back (+Y).
    ahead = Matrix.Rotation(SWORD_BACK_TILT, 3, ahead.cross(Vector((0, 1, 0))).normalized()) @ ahead
    hand = fist + ahead * .06 * u
    across = ahead.cross(Vector((0, -.5, .87))).normalized()
    across = Matrix.Rotation(SWORD_ROLL, 3, ahead) @ across
    tip = hand + ahead * .42 * u
    thick = across.cross(ahead)
    vertices = []
    for center, width, depth in ((hand + (tip - hand) * .12, .075 * u, .016 * u),
                                 (tip * .94 + hand * .06, .06 * u, .014 * u)):
        vertices += [tuple(center + across * width), tuple(center + thick * depth),
                     tuple(center - across * width), tuple(center - thick * depth)]
    vertices.append(tuple(tip))
    faces = [(3, 2, 1, 0)] + [(k, (k + 1) % 4, (k + 1) % 4 + 4, k + 4) for k in range(4)]
    faces += [(k + 4, (k + 1) % 4 + 4, 8) for k in range(4)]
    mesh = bpy.data.meshes.new(f'{prefix} blade')
    mesh.from_pydata(vertices, [], faces)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    blade = bpy.data.objects.new(f'{prefix} blade', mesh)
    bpy.context.collection.objects.link(blade)
    attach(blade, rig, 'hand.R', blade_mat).modifiers['Forged edge'].width = .003
    guard = hand_bar(rig, f'{prefix} guard', hand + across * .08 * u, hand - across * .08 * u,
                     .025 * u, guard_mat)
    for obj in (blade, guard):
        obj.hide_render = obj.hide_viewport = hidden


def hand_bar(rig, name, start, end, radius, mat):
    """Straight round bar with capped ends, rigid on the right hand."""
    curve = bpy.data.curves.new(name, 'CURVE')
    curve.dimensions, curve.bevel_depth, curve.bevel_resolution = '3D', radius, 2
    curve.use_fill_caps = True
    spline = curve.splines.new('POLY')
    spline.points.add(1)
    for point, co in zip(spline.points, (start, end)):
        point.co = (*co, 1)
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.convert(target='MESH')
    obj = bpy.context.object
    attach(obj, rig, 'hand.R', mat).modifiers['Forged edge'].width = .002
    return obj


def chimera_sword(rig, cursed=False):
    """The chimera's sword in the right hand, as on the heroic sprite
    (../build-heroic.py player() and chimera_sword_materials()): a flat blade
    narrowing steadily to a sharp point, an acute isosceles triangle seen
    from above, with a gold guard and pommel, 1.3 times the size of the one
    in the chimera's jaws. Unlike the own sword it is held low, pointing to
    screen lower left. Its parts start hidden; the sprite renderer shows the
    sword the player holds."""
    prefix = 'Cursed sword' if cursed else 'Chimera sword'
    if cursed:
        steel = material('Cursed sword black steel', (.04, .03, .04), .6, .15,
                         emission=(.9, .05, .02), strength=.6, rim=(1.0, .15, .05),
                         rim_strength=4.0, transmission=0)
        hilt = material('Cursed sword iron hilt', (.25, .22, .24), 1.0, .3)
    else:
        steel = material('Chimera sword steel', (.85, .92, 1.0), .5, .08,
                         emission=(.7, .85, 1.0), strength=.8, rim=(.9, .95, 1.0),
                         rim_strength=1.5, transmission=.3)
        hilt = material('Chimera sword hilt', (1.0, .68, .18), 1.0, .25)
    u, size = SWORD_UNIT, 1.3
    head, tail = (Vector(p) for p in BONES['hand.R'][:2])
    hand = head + (tail - head) * .6
    ahead = Vector((-.34, -.30, -.10)).normalized()
    across = ahead.cross(Vector((0, 0, 1))).normalized()
    thick = across.cross(ahead)
    base, tip = hand + ahead * .05 * size * u, hand + ahead * .58 * size * u
    width = .075 * size * u
    vertices = [tuple(base + across * width), tuple(base + thick * width * .2),
                tuple(base - across * width), tuple(base - thick * width * .2), tuple(tip)]
    faces = [(3, 2, 1, 0)] + [(k, (k + 1) % 4, 4) for k in range(4)]
    mesh = bpy.data.meshes.new(f'{prefix} blade')
    mesh.from_pydata(vertices, [], faces)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    blade = bpy.data.objects.new(f'{prefix} blade', mesh)
    bpy.context.collection.objects.link(blade)
    attach(blade, rig, 'hand.R', steel).modifiers['Forged edge'].width = .003
    guard = hand_bar(rig, f'{prefix} guard', hand + across * .09 * size * u,
                     hand - across * .09 * size * u, .025 * size * u, hilt)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=.035 * size * u,
                                         location=hand - ahead * .10 * size * u)
    pommel = bpy.context.object
    pommel.name = f'{prefix} pommel'
    attach(pommel, rig, 'hand.R', hilt)
    for obj in (blade, guard, pommel):
        obj.hide_render = obj.hide_viewport = True


# Jet helmet shell: a hemisphere of JET_RADIUS on its equator at
# JET_EQUATOR_Z, centered JET_CENTER_Y behind the head axis, over sides that
# run down through JET_SIDE_RINGS (z, radius, back offset, back drop) past
# the ears. At the back each ring moves in or out by its offset and down by
# its drop (fading out toward the sides), so the back of the helmet follows
# the head into the neck: it pinches in under the skull and flares out over
# the nape at the rim. The deepest pinch sits at z 1.5956 (5% of the helmet's
# height above 1.58); the rings between the equator and the rim are spaced
# around it. The rings below the pinch are squeezed toward it so the rim
# sits 5% of the helmet's height (1.56cm) higher, keeping the flare.
JET_RADIUS, JET_EQUATOR_Z, JET_CENTER_Y = .135, 1.68, .005
JET_SIDE_RINGS = [(1.6462, .136, -.005, 0), (1.6209, .137, -.018, .002),
                  (1.5956, .138, -.03, .006), (1.5706, .139, -.027, .012),
                  (1.5506, .140, -.008, .014), (1.5406, .141, .02, .022)]
JET_THICKNESS = .012
# The face opening: half width, top edge height and corner radius, seen from
# the front; it is open down through the rim.
JET_OPENING_HALF, JET_OPENING_TOP, JET_OPENING_CORNER = .1277, 1.712, .028
# The face plate, a steel plate in front of the opening, like a visor lowered
# over the face: it lies on a cylinder of JET_PLATE_RADIUS just outside the
# shell (a sphere above the shell's equator) with a forward ridge down its
# middle (JET_PLATE_RIDGE deep, JET_PLATE_RIDGE_HALF wide). Half width around
# the curve; its top edge rises over the opening's top, and its bottom edge
# runs down to a rounded point at the chin.
JET_PLATE_RADIUS, JET_PLATE_HALF = .149, .175
JET_PLATE_RIDGE, JET_PLATE_RIDGE_HALF = .022, .08
# The top edge runs straight from the side corners (JET_PLATE_TOP) up to a
# point JET_PLATE_PEAK higher over the ridge, the upper half of a hexagon.
JET_PLATE_TOP, JET_PLATE_PEAK = 1.7365, .0585
# The plate is cut back at both sides by this fraction of JET_PLATE_HALF; the
# top and bottom edges keep the slopes of the full width.
JET_PLATE_TRIM = .08
# How much the brow above the shell's equator follows the dome back
# (1 follows a sphere, 0 rises straight).
JET_PLATE_BROW_CURVE = .7
JET_PLATE_CHIN, JET_PLATE_BOTTOM_SIDE = 1.51, 1.545
# The eye slit through the face plate: height range and half width (around
# the curve); a glowing window sits just behind it.
JET_SLIT_LOW, JET_SLIT_HIGH, JET_SLIT_HALF = 1.6185, 1.6635, .10
# The whole helmet (shell, face plate, crest and horns) is scaled by
# HELMET_SCALE about HELMET_SCALE_CENTER, near the bottom of the head, so
# it stays seated on the neck. The constants above are before scaling.
HELMET_SCALE, HELMET_SCALE_CENTER = .90, (0, .005, 1.56)
HELMET_PARTS = ('Helmet', 'Helmet face opening cutter', 'Helmet face plate', 'Eye window', 'Eye housing',
                'Helmet crest', 'Helmet horn L', 'Helmet horn R')


def scale_about(obj, factor, center):
    """Scale an object's mesh by factor about a world point (at rest)."""
    bpy.context.view_layer.update()
    world = obj.matrix_world.copy()
    scale = (Matrix.Translation(center) @ Matrix.Scale(factor, 4)
             @ Matrix.Translation(-Vector(center)))
    obj.data.transform(world.inverted() @ scale @ world)
    obj.data.update()


def outward_mesh(name, vertices, faces):
    """Mesh with its face normals recalculated to point outward."""
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    if hasattr(mesh, 'use_auto_smooth'):
        mesh.use_auto_smooth = True
    return mesh


def jet_helmet(rig, shell_mat, glow_mat, lining_mat):
    """An open-face jet helmet: a round shell over the top, sides and nape,
    with a large face opening covered by a ridged steel face plate whose eye
    slit shows a glowing window."""
    count = 48
    rings = [(JET_EQUATOR_Z + JET_RADIUS * math.sin(math.radians(a)),
              JET_RADIUS * math.cos(math.radians(a)), 0, 0) for a in range(80, -1, -10)]
    rings += JET_SIDE_RINGS
    vertices = [(0, JET_CENTER_Y, JET_EQUATOR_Z + JET_RADIUS)]
    for z, radius, offset, drop in rings:
        for i in range(count):
            angle = i * 2 * math.pi / count
            # 1 at the back, 0 from the sides forward.
            back = max(0, math.cos(angle)) ** 1.5
            r = radius + offset * back
            vertices.append((r * math.sin(angle), JET_CENTER_Y + r * math.cos(angle),
                             z - drop * back))
    faces = [(0, 1 + (i + 1) % count, 1 + i) for i in range(count)]
    for row in range(len(rings) - 1):
        a, b = 1 + row * count, 1 + (row + 1) * count
        faces += [(a + i, a + (i + 1) % count, b + (i + 1) % count, b + i)
                  for i in range(count)]
    shell = bpy.data.objects.new('Helmet', outward_mesh('Helmet', vertices, faces))
    bpy.context.collection.objects.link(shell)
    for face in shell.data.polygons:
        face.use_smooth = True
    attach(shell, rig, 'head', shell_mat).modifiers['Forged edge'].width = .004

    # Face opening cutter: the opening's outline seen from the front,
    # extruded from in front of the helmet back to just short of its middle.
    half, top, corner = JET_OPENING_HALF, JET_OPENING_TOP, JET_OPENING_CORNER
    outline = [(-half, 1.4), (half, 1.4)]
    for side, start, end in ((1, 0, 90), (-1, 90, 180)):
        cx = side * (half - corner)
        for k in range(9):
            angle = math.radians(start + (end - start) * k / 8)
            outline.append((cx + corner * math.cos(angle), top - corner + corner * math.sin(angle)))
    n = len(outline)
    vertices = [(x, y, z) for y in (-.4, -.03) for x, z in outline]
    faces = [tuple(range(n)), tuple(range(n, 2 * n))]
    faces += [(i, (i + 1) % n, (i + 1) % n + n, i + n) for i in range(n)]
    cutter = bpy.data.objects.new('Helmet face opening cutter',
                                  outward_mesh('Helmet face opening cutter', vertices, faces))
    bpy.context.collection.objects.link(cutter)
    attach(cutter, rig, 'head', shell_mat).modifiers['Forged edge'].width = .001
    cutter.hide_render = True
    cutter.display_type = 'WIRE'
    wall = shell.modifiers.new('Shell thickness', 'SOLIDIFY')
    wall.thickness, wall.offset = JET_THICKNESS, 0
    opening = shell.modifiers.new('Face opening', 'BOOLEAN')
    opening.operation, opening.solver, opening.object = 'DIFFERENCE', 'EXACT', cutter
    bpy.context.view_layer.objects.active = shell
    bpy.ops.object.modifier_move_to_index(modifier=wall.name, index=0)
    bpy.ops.object.modifier_move_to_index(modifier=opening.name, index=1)

    # Face plate: a grid over (around, height). Its middle band holds the eye
    # slit at fixed heights; the bands above and below follow the straight top
    # edges, peaked over the ridge, and the pointed chin. Faces inside the
    # slit are left out.
    half, slit = JET_PLATE_HALF, JET_SLIT_HALF
    edge = half * (1 - JET_PLATE_TRIM)
    columns = sorted(set([round(edge * (2 * c / 24 - 1), 6) for c in range(25)]
                         + [-slit, slit]))

    def top(u):
        return JET_PLATE_TOP + JET_PLATE_PEAK * (1 - abs(u) / half)

    def bottom(u):
        return JET_PLATE_CHIN + (JET_PLATE_BOTTOM_SIDE - JET_PLATE_CHIN) * (abs(u) / half) ** 1.5

    low, high = JET_SLIT_LOW - .03, JET_SLIT_HIGH + .02
    rows = ([lambda u, t=t: bottom(u) + (low - bottom(u)) * t for t in (0, .2, .4, .6, .8)]
            + [lambda u, z=z: z for z in (low, JET_SLIT_LOW, JET_SLIT_HIGH, high)]
            + [lambda u, t=t: high + (top(u) - high) * t for t in (.5, 1)])

    def plate_point(u, z, inset=0):
        # Out from the shell's axis, plus the ridge; above the shell's
        # equator the plate curves back, less than the dome
        # (JET_PLATE_BROW_CURVE).
        radius = (JET_PLATE_RADIUS - inset
                  + JET_PLATE_RIDGE * max(0, 1 - abs(u) / JET_PLATE_RIDGE_HALF))
        lift = JET_PLATE_BROW_CURVE * max(0, z - JET_EQUATOR_Z)
        ring = math.sqrt(max(0, radius ** 2 - lift ** 2))
        angle = u / JET_PLATE_RADIUS
        return (ring * math.sin(angle), JET_CENTER_Y - ring * math.cos(angle), z)

    vertices = [plate_point(u, row(u)) for row in rows for u in columns]
    width = len(columns)
    faces = []
    for r in range(len(rows) - 1):
        for c in range(width - 1):
            middle = (columns[c] + columns[c + 1]) / 2
            if r == 6 and abs(middle) < slit:
                continue
            faces.append((r * width + c, r * width + c + 1,
                          (r + 1) * width + c + 1, (r + 1) * width + c))
    face_plate = bpy.data.objects.new('Helmet face plate',
                                      outward_mesh('Helmet face plate', vertices, faces))
    bpy.context.collection.objects.link(face_plate)
    for face in face_plate.data.polygons:
        face.use_smooth = True
    attach(face_plate, rig, 'head', shell_mat).modifiers['Forged edge'].width = .002
    wall = face_plate.modifiers.new('Plate thickness', 'SOLIDIFY')
    wall.thickness, wall.offset = .005, 0
    bpy.context.view_layer.objects.active = face_plate
    bpy.ops.object.modifier_move_to_index(modifier=wall.name, index=0)

    # Eye window: a glowing strip just behind the slit, a little larger.
    us = [slit * 1.15 * (2 * c / 16 - 1) for c in range(17)]
    zs = (JET_SLIT_LOW - .006, JET_SLIT_HIGH + .006)
    vertices = [plate_point(u, z, inset=.007) for z in zs for u in us]
    faces = [(c, c + 1, 17 + c + 1, 17 + c) for c in range(16)]
    window = bpy.data.objects.new('Eye window', outward_mesh('Eye window', vertices, faces))
    bpy.context.collection.objects.link(window)
    for face in window.data.polygons:
        face.use_smooth = True
    attach(window, rig, 'head', glow_mat).modifiers['Forged edge'].width = .001

    # Eye housing: a dark closed channel behind the window, from the face
    # plate's inner surface back past the window, so the glow only leaves
    # through the slit and does not light the helmet's inside or the chest.
    end = slit * 1.15 + .005
    us = [end * (2 * c / 16 - 1) for c in range(17)]
    low, high = zs[0] - .003, zs[1] + .003
    # Cross section: top lid, back wall, bottom lid.
    profile = [(high, .002), (high, .011), (low, .011), (low, .002)]
    vertices = [plate_point(u, z, inset=inset) for z, inset in profile for u in us]
    faces = [(k * 17 + c, k * 17 + c + 1, (k + 1) * 17 + c + 1, (k + 1) * 17 + c)
             for k in range(3) for c in range(16)]
    faces += [tuple(k * 17 + c for k in range(4)) for c in (0, 16)]
    housing = bpy.data.objects.new('Eye housing', outward_mesh('Eye housing', vertices, faces))
    bpy.context.collection.objects.link(housing)
    attach(housing, rig, 'head', lining_mat).modifiers['Forged edge'].width = .001
    return shell


def helmet_crest_and_horns(rig, mat):
    """Crest and horns of the heroic player's helm (../build-heroic.py),
    scaled 0.8 about its head center (0, -.04, .83) onto this helmet's center."""
    def heroic(x, y, z):
        return Vector((x * .8, (y + .04) * .8, 1.67 + (z - .83) * .8))

    # A thin plate, a horn-like triangle from the side: its base runs along
    # the top of the helm and it sweeps forward and up past the visor.
    profile = [heroic(0, -.02, .985), heroic(0, -.17, .955), heroic(0, -.23, 1.063)]
    # Shrunk about the middle of its base, so it stays seated on the helmet.
    crest_scale = .8
    base = (profile[0] + profile[1]) / 2
    profile = [base + (point - base) * crest_scale for point in profile]
    vertices = [(side * .02 * crest_scale, p.y, p.z) for side in (-1, 1) for p in profile]
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
    # Four-sided horns from the sides of the helm, out, back and up: 1.08 times
    # the heroic size, moved in to 90% and up 1 cm. The rounded helmet
    # corners fall away under their square roots, so each horn is extended
    # 6 cm back along its own axis into the helmet; the visible part keeps
    # its tip and taper.
    horn_scale, horn_spread, horn_lift, horn_sink = 1.2 * .9, .9, .01, .06
    radius = .055 * .8 * horn_scale
    for side, sign in (('L', 1), ('R', -1)):
        lift = Vector((0, 0, horn_lift))
        start = heroic(sign * .15 * horn_spread, 0, .90) + lift
        delta = (heroic(sign * .27 * horn_spread, .11, 1.06) + lift - start) * horn_scale
        end = start + delta
        start = start - delta.normalized() * horn_sink
        depth = (end - start).length
        bpy.ops.mesh.primitive_cone_add(vertices=4, radius1=radius * depth / delta.length,
                                        radius2=0, depth=depth, location=(start + end) / 2)
        delta = end - start
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
    box(rig, 'pelvis', 'Belt buckle', (0, -front, BELT_Z), (.03, .004, .028), buckle_mat, .003)


def side_tassets(rig, mat, trim):
    """Curved steel tassets over the flanks, two overlapping lames a side.

    The upper lame hangs from inside the belt and is fixed to the pelvis. The
    lower lame tucks under its hem and swings on tasset.L/R (hinged at the
    side, level with the plate's middle) so a raised thigh does not pass
    through it. A dark iron bar rolls each lame's hem. Rows are (z, half-width, half-depth, width around the hips)
    on an ellipse around the hips, centered TASSET_ANGLE from the front.
    """
    upper_w, upper_d = hip_radius(.94)
    parts = [('Tasset upper', 'pelvis', .012,
              # Top edge on the belt's centerline, hidden inside it.
              [(BELT_Z, BELT_RX, BELT_RY, .19), (.99, upper_w + .012, upper_d + .012, .205),
               (.935, upper_w + .024, upper_d + .022, .225)]),
             ('Tasset lower', 'tasset', .03,
              # Top edge tucked 2 cm up under the upper lame's hem.
              [(.955, upper_w + .012, upper_d + .01, .215), (.87, .235, .175, .24),
               (.79, .25, .185, .245)])]

    def arc_row(radius_x, radius_y, width):
        """13 angles (radians) on the ellipse spanning `width` around it,
        centered TASSET_ANGLE from the front, with arc lengths from the center."""
        center = math.radians(TASSET_ANGLE)

        def point(angle):
            return Vector((radius_x * math.sin(angle), -radius_y * math.cos(angle)))

        def length(half):
            steps = [center + half * (2 * k / 200 - 1) for k in range(201)]
            return sum((point(b) - point(a)).length for a, b in zip(steps, steps[1:]))
        low, high = 0, math.pi / 2
        for _ in range(40):
            half = (low + high) / 2
            low, high = (half, high) if length(half) < width else (low, half)
        return [center + half * (2 * i / 12 - 1) for i in range(13)]
    for side, sign in (('L', 1), ('R', -1)):
        for name, bone_name, hem_round, rows in parts:
            vertices = []
            for r, (z, radius_x, radius_y, width) in enumerate(rows):
                for i, angle in enumerate(arc_row(radius_x, radius_y, width)):
                    # The hem rises toward both edges, rounding the lame's
                    # lower corners.
                    lift = hem_round * ((i - 6) / 6) ** 2 if r == len(rows) - 1 else 0
                    vertices.append((sign * radius_x * math.sin(angle),
                                     -radius_y * math.cos(angle), z + lift))
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
            obj.modifiers['Forged edge'].width = .003
            for face in mesh.polygons:
                face.use_smooth = True
            shell = obj.modifiers.new('Plate thickness', 'SOLIDIFY')
            shell.thickness = .006
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.modifier_move_up(modifier=shell.name)
            bpy.ops.object.modifier_move_up(modifier=shell.name)
            hem = [Vector(v) for v in vertices[-13:]]
            # Sit the bar on the plate's outer face, just above the hem.
            hem = [v + Vector((v.x, v.y, 0)).normalized() * .002 + Vector((0, 0, .004))
                   for v in hem]
            ring_bar(rig, bone_name if bone_name == 'pelvis' else f'{bone_name}.{side}',
                     f'{name} rim {side}', hem, .005, trim, cyclic=False)


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
    mail = chainmail_material('Blackened chainmail')
    hip = plate(rig, 'pelvis', 'Hip armor', HIP_RINGS, steel, segments=32)
    # Brief-like hem: the front and back centers drop 6 cm to the crotch and
    # narrow between the thighs, while the sides stay at the hip joints, so
    # the leg openings arch up over the thighs. The 32-sided section keeps
    # the crotch a rounded U instead of a point.
    for i in range(32):
        c2 = math.cos(i * 2 * math.pi / 32) ** 2
        vertex = hip.data.vertices[i]
        vertex.co.z -= .06 * c2
        vertex.co.x *= 1 - .5 * c2
    hip.data.update()
    plate(rig, 'waist', 'Flexible waist lining', [(0,.135,.10),(.16,.145,.11)], dark)
    belt(rig, trim, trim)
    side_tassets(rig, steel, trim)
    breastplate = plate(rig, 'chest', 'Breast and back plate', CHEST_RINGS, steel)
    # Extend the front center of the lower rim into a shallow V over the abdomen.
    for i in range(12):
        angle = i * 2 * math.pi / 12
        breastplate.data.vertices[i].co.z -= .025 * max(0, math.cos(angle)) * (1 - abs(math.sin(angle)))
    for vertex in breastplate.data.vertices:
        vertex.co.x *= CHEST_WIDEN
    breastplate.data.update()
    chest_seams(rig, trim)
    gorget(rig, mail, trim)
    # Same midnight blue as the heroic player's cloak.
    cloak = material('Player midnight cloak', (.025, .05, .16), roughness=.4, transmission=.15,
                     rim=(.25, .45, 1.0), rim_strength=.6)
    cape(rig, cloak)
    blade = material('Player iron blade', (.62, .63, .66), .55, .4,
                     rim=(.85, .9, 1.0), rim_strength=.8)
    own_sword(rig, blade, trim)
    # The K blessing's sword: the own sword glowing blue (heroic 'Player
    # blessed blade').
    blessed = material('Player blessed blade', (.10, .35, 1.0), .3, .3, emission=(.03, .30, 1.0),
                       strength=1.5, rim=(.2, .6, 1.0), rim_strength=2.0)
    own_sword(rig, blessed, trim, 'Blessed sword', hidden=True)
    chimera_sword(rig)
    chimera_sword(rig, cursed=True)
    joint(rig, 'neck', .075, dark)
    glow = material('Player visor glow', (.3, .9, 1.0), roughness=.35,
                    emission=(.1, .75, 1.0), strength=2.5)
    jet_helmet(rig, helm, glow, dark)
    helmet_crest_and_horns(rig, trim)
    for name in HELMET_PARTS:
        scale_about(bpy.data.objects[name], HELMET_SCALE, HELMET_SCALE_CENTER)
    for side in ('L','R'):
        for part, radius in [('upper_arm',.085),('forearm',.062),('hand',.05),
                             ('thigh',.085),('shin',.075),('foot',.055)]:
            joint(rig, f'{part}.{side}', radius, dark)
        for part, width, depth in [('upper_arm',.072,.075),('forearm',.066,.07),
                                    ('thigh',.092,.095),('shin',.072,.078)]:
            bone_name = f'{part}.{side}'
            length = rig.data.bones[bone_name].length
            plate(rig, bone_name, f'{part} plate {side}',
                  [(.045,width*.85,depth*.85),(length*.4,width,depth),
                   (length-.025,width*.75,depth*.8)],
                  greaves if part in ('thigh', 'shin') else steel)
        # A round dark iron gauntlet for the fist, as on the heroic sprite
        # (its 'Player gauntlet'), a little larger than the wrist's ball
        # joint; the swords' grips sit inside it.
        head, tail = (Vector(p) for p in BONES[f'hand.{side}'][:2])
        bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=.068,
                                             location=head + (tail - head) * .55)
        gauntlet = bpy.context.object
        gauntlet.name = f'Gauntlet {side}'
        attach(gauntlet, rig, f'hand.{side}', trim)
        for face in gauntlet.data.polygons:
            face.use_smooth = True
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
        # Squarish dark iron sabatons, matching the helmet's rounded box.
        sabaton_rings = [(-.025,.065,.055),(.075,.08,.06),(.20,.065,.04)]
        squarish(plate(rig, f'foot.{side}', f'Sabaton {side}', sabaton_rings, trim),
                 rig, f'foot.{side}', sabaton_rings)
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
         'thigh.L': (12, 0, 0), 'shin.L': (-18, 0, 0),
         'cape.L.2': (-4, 0, 0), 'cape.C.2': (-6, 0, 0), 'cape.R.2': (-8, 0, 0)}),
    80: ('STEP', {'waist': (0, 0, -10), 'neck': (0, 0, 10),
         'upper_arm.L': (-22, 0, 0), 'forearm.L': (20, 0, 0),
         'upper_arm.R': (25, 0, 0), 'forearm.R': (40, 0, 0),
         'thigh.L': (32, 0, 0), 'shin.L': (-40, 0, 0),
         'thigh.R': (-15, 0, 0), 'shin.R': (-12, 0, 0),
         **{f'cape.{s}.{k}': (a, 0, 0) for s in 'LCR'
            for k, a in ((1, -6), (2, -8), (3, -8), (4, -6))}}),
    # Collapsed from hunger, as on the heroic sprite: fallen face down, the
    # head toward screen lower right (so the figure's right side faces the
    # camera), the head turned a little toward the camera, the right arm
    # flung past the head, the cape slid off the back toward the far side.
    # The root is lifted onto the floor and the visor dimmed in animate().
    # Below the shoulders the cape chains tip toward the body, laying the
    # billowing cape on the back (the closest fit found that passes through
    # the armor in neither this nor the chibi build).
    # The head and neck tip back and the right arm reaches past the head
    # along the floor, so neither props up the chest.
    120: ('COLLAPSED', {'root': (90, 45, 0), 'neck': (-20, 0, -55), 'head': (-35, 0, 0),
          'upper_arm.R': (170, 0, 40), 'forearm.R': (60, 0, 0),
          'shin.L': (-25, 0, 0), 'shin.R': (-10, 0, 0),
          **{f'cape.{s}.{k}': (a, 0, 0) for s in 'LCR'
             for k, a in ((1, 0), (2, 20), (3, 5), (4, 5))}}),
}
COLLAPSED_FRAME = 120
# Names of the sword parts in the right hand.
SWORD_PREFIXES = ('Sword ', 'Chimera sword ', 'Cursed sword ', 'Blessed sword ')
# Voxel size of the smooth envelope the collapsed cape is draped onto, and
# how far (0 to 1) the cape drops from where its bones hold it onto it.
DRAPE_VOXEL, DRAPE_AMOUNT, DRAPE_AMOUNT_BETWEEN_LEGS = .02, .3, .2


def animate(rig, scene):
    for frame, (label, rotations) in POSES.items():
        scene.timeline_markers.new(label, frame=frame)
        for bone in rig.pose.bones:
            if bone.name.startswith(('hip_plate.', 'tasset.')):
                continue
            angles = rotations.get(bone.name, (0,0,0))
            # Waist/neck twist around bone-local Y, which is upright.
            if bone.name in ('waist','neck'):
                angles = (angles[0], angles[2], angles[1])
            bone.rotation_euler = tuple(math.radians(v) for v in angles)
            bone.keyframe_insert('rotation_euler', frame=frame, group=bone.name)
    rig.animation_data.action.name = 'Rest - guard - step - collapsed (FK studies)'
    # Rest the collapsed figure on the floor, centred where it stood: lift
    # the root by the lowest point's drop below the standing figure's lowest
    # point, and move it so the laid figure's footprint is centred. The
    # collapsed figure holds no sword, so swords are left out; the cape is
    # cloth that the body presses flat, so it is left out too.
    soft = SWORD_PREFIXES + ('Cape',)

    def points():
        depsgraph = bpy.context.evaluated_depsgraph_get()
        result = []
        for obj in scene.objects:
            if (obj.type == 'MESH' and obj.parent == rig and not obj.hide_render
                    and not obj.name.startswith(soft)):
                evaluated = obj.evaluated_get(depsgraph)
                mesh = evaluated.to_mesh()
                result += [evaluated.matrix_world @ v.co for v in mesh.vertices]
                evaluated.to_mesh_clear()
        return result
    root = rig.pose.bones['root']
    scene.frame_set(1)
    standing = min(p.z for p in points())
    scene.frame_set(COLLAPSED_FRAME)
    laid = points()
    lift = standing - min(p.z for p in laid)
    center_x = (min(p.x for p in laid) + max(p.x for p in laid)) / 2
    center_y = (min(p.y for p in laid) + max(p.y for p in laid)) / 2
    for frame in POSES:
        # Root location is in its rest frame: local X is world X, local Y
        # world up and local Z world -Y.
        root.location = ((-center_x, lift, center_y) if frame == COLLAPSED_FRAME else (0, 0, 0))
        root.keyframe_insert('location', frame=frame, group='root')
    drape_cape(rig, scene, standing)
    # Dim the visor while collapsed (heroic 'Player dimmed visor').
    visor = bpy.data.materials['Player visor glow'].node_tree.nodes['Principled BSDF']
    for frame in POSES:
        collapsed = frame == COLLAPSED_FRAME
        visor.inputs['Base Color'].default_value = ((.05, .14, .18, 1) if collapsed
                                                    else (.3, .9, 1.0, 1))
        visor.inputs['Emission Strength'].default_value = .3 if collapsed else 2.5
        for name in ('Base Color', 'Emission Strength'):
            visor.inputs[name].keyframe_insert('default_value', frame=frame)
    scene.frame_end = max(POSES)
    scene.frame_set(1)


def drape_cape(rig, scene, floor_z):
    """Let the cape fall onto the collapsed body: a Shrinkwrap modifier,
    on only at the collapsed frame, projects it straight down onto a hidden,
    smooth envelope of the laid body and the floor, so it lies along the back
    and drops to the floor past the sides. The envelope is a voxel remesh of
    the armor (which wraps its seams, belt and plate edges) and a thin floor
    slab around it."""
    scene.frame_set(COLLAPSED_FRAME)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    bm = bmesh.new()
    xs, ys = [], []
    for obj in scene.objects:
        if (obj.type == 'MESH' and obj.parent == rig and not obj.hide_render
                and not obj.name.startswith(SWORD_PREFIXES + ('Cape',))):
            evaluated = obj.evaluated_get(depsgraph)
            mesh = evaluated.to_mesh()
            mesh.transform(evaluated.matrix_world)
            xs += [v.co.x for v in mesh.vertices]
            ys += [v.co.y for v in mesh.vertices]
            bm.from_mesh(mesh)
            evaluated.to_mesh_clear()
    margin = .3
    slab = bmesh.ops.create_cube(bm, size=1)['verts']
    low, high = Vector((min(xs) - margin, min(ys) - margin, floor_z - .03)), Vector((max(xs) + margin, max(ys) + margin, floor_z))
    for vertex in slab:
        vertex.co = Vector(low[i] if vertex.co[i] < 0 else high[i] for i in range(3))
    target_mesh = bpy.data.meshes.new('Cape drape target')
    bm.to_mesh(target_mesh)
    bm.free()
    target = bpy.data.objects.new('Cape drape target', target_mesh)
    scene.collection.objects.link(target)
    remesh = target.modifiers.new('Envelope', 'REMESH')
    remesh.mode, remesh.voxel_size = 'VOXEL', DRAPE_VOXEL
    bpy.context.view_layer.update()
    evaluated = target.evaluated_get(bpy.context.evaluated_depsgraph_get())
    envelope = bpy.data.meshes.new_from_object(evaluated)
    target.modifiers.remove(remesh)
    target.data = envelope
    bpy.data.meshes.remove(target_mesh)
    target.hide_render = True
    target.display_type = 'WIRE'
    target.hide_set(True)
    cape_obj = bpy.data.objects['Cape']
    # Finer cloth first, so the part past the sides drops steeply instead of
    # cutting across the body's edge between coarse vertices.
    finer = cape_obj.modifiers.new('Drape detail', 'SUBSURF')
    finer.subdivision_type, finer.levels, finer.render_levels = 'SIMPLE', 2, 2
    drape = cape_obj.modifiers.new('Drape when collapsed', 'SHRINKWRAP')
    drape.target, drape.wrap_method, drape.offset = target, 'PROJECT', .008
    drape.use_project_z, drape.use_negative_direction, drape.use_positive_direction = True, True, False
    # Only part of the way down (DRAPE_AMOUNT), through a vertex group: fully
    # dropped, the cloth looked like rubber pulled over the body.
    # Over the gap between the legs (the middle of the cape below the hips)
    # it drops less, blending in across and down, so it does not sag in.
    amount = cape_obj.vertex_groups.new(name='Drape amount')
    for index in range(len(cape_obj.data.vertices)):
        row, column = divmod(index, CAPE_COLUMNS + 1)
        across = max(0, 1 - abs(column - CAPE_COLUMNS / 2) / (CAPE_COLUMNS / 6))
        down = min(1, max(0, (row / CAPE_ROWS - .55) / .15))
        between_legs = across * down * down * (3 - 2 * down)
        amount.add([index], DRAPE_AMOUNT + (DRAPE_AMOUNT_BETWEEN_LEGS - DRAPE_AMOUNT) * between_legs,
                   'REPLACE')
    drape.vertex_group = amount.name
    soften = cape_obj.modifiers.new('Soften drape', 'SMOOTH')
    soften.factor, soften.iterations = .5, 4
    bpy.context.view_layer.objects.active = cape_obj
    for index, modifier in enumerate((finer, drape, soften), start=1):
        bpy.ops.object.modifier_move_to_index(modifier=modifier.name, index=index)
    for frame in POSES:
        for modifier in (finer, drape, soften):
            modifier.show_viewport = modifier.show_render = frame == COLLAPSED_FRAME
            modifier.keyframe_insert('show_viewport', frame=frame)
            modifier.keyframe_insert('show_render', frame=frame)


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
    # The floor sits under the standing figure's visible parts (not the
    # hidden cutters or the collapsed cape's drape envelope).
    ground_z = min((obj.matrix_world @ v.co).z for obj in scene.objects
                   if obj.type == 'MESH' and obj.parent and not obj.hide_render
                   for v in obj.data.vertices)
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
    meshes = [o for o in scene.objects if o.parent == rig and o.name != 'Cape']
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
    # The cape bends: bending its middle chain moves the middle of the hem but
    # not the middle of the top edge (checked with the Armature modifier only).
    cape_obj = bpy.data.objects['Cape']
    others = [m for m in cape_obj.modifiers if m.type != 'ARMATURE']
    for m in others:
        m.show_viewport = False
    rest = [v.co for v in cape_obj.data.vertices]
    top = max(range(len(rest)), key=lambda i: rest[i].z - abs(rest[i].x))
    hem = min(range(len(rest)), key=lambda i: rest[i].z + abs(rest[i].x))

    def cape_points():
        mesh = cape_obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
        return mesh.vertices[hem].co.copy(), mesh.vertices[top].co.copy()
    hem0, top0 = cape_points()
    rig.pose.bones['cape.C.2'].rotation_euler.x = math.radians(-30)
    bpy.context.view_layer.update()
    hem1, top1 = cape_points()
    assert (hem1 - hem0).length > .05 and (top1 - top0).length < 1e-4, 'cape'
    rig.pose.bones['cape.C.2'].rotation_euler = (0, 0, 0)
    for m in others:
        m.show_viewport = True
    bpy.context.view_layer.update()
    scene.frame_set(1)
    print(f'Validated {len(required)} required joints, {len(BONES)} bones, {len(meshes)} rigid parts, bending cape')


def save_and_render(rig, scene, blend_name, image_prefix='', view_center=(0, 0, .95),
                    view_distance=3.3, only=None):
    """Leave the rig selected in Pose Mode, save the .blend and render each
    sample pose to <image_prefix><pose>.png next to this script."""
    bpy.ops.object.select_all(action='DESELECT')
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='POSE')
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                space = area.spaces.active
                space.region_3d.view_distance = view_distance
                space.region_3d.view_location = view_center
                space.region_3d.view_rotation = scene.camera.rotation_euler.to_quaternion()
                space.region_3d.view_perspective = 'ORTHO'
                space.shading.color_type = 'MATERIAL'
    bpy.ops.wm.save_as_mainfile(filepath=str(HERE / blend_name))
    swords = [o for o in scene.objects if o.name.startswith(SWORD_PREFIXES) and not o.hide_render]
    for frame, (label, _) in POSES.items():
        if only and label.lower() not in only:
            continue
        scene.frame_set(frame)
        # The collapsed figure is drawn without its sword.
        for obj in swords:
            obj.hide_render = frame == COLLAPSED_FRAME
        scene.render.filepath = str(HERE / f'{image_prefix}{label.lower()}.png')
        bpy.ops.render.render(write_still=True)
    for obj in swords:
        obj.hide_render = False


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    rig = create_rig()
    build_armor(rig)
    animate(rig, scene)
    setup_scene(scene)
    validate(rig, scene)
    save_and_render(rig, scene, 'hero-rig.blend')


if __name__ == '__main__':
    main()
