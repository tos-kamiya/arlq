"""Iris, the talkative Stage 6 robot (dev-notes/handoff-stage6-robot-iris-design-20261121.md).

The model, shared by build-heroic.py (the members' scene the game sprites
are exported from) and build-robot-iris.py (standalone close-ups and every
expression). `build(x, y)` adds a small tea-canister robot of white glazed
ceramic (brass bands, antenna, splayed manipulators, a tall curved locker
door) hovering at the player's shoulder height over a thin ring of cyan
light, with floating eye panels in every expression of EXPRESSIONS; only the
neutral eyes render until `show_expression()` picks another.

The parts are built at the first prototype's size (below), then shrunk to
SCALE, lifted to HOVER_Z and leaned back by FACE_TILT, with the transforms
applied to the meshes; only the faint pool of light stays on the floor.
The glowing parts (eyes, ring, floor glow) carry Freestyle face marks, so the
sprite export draws no ink outline round them.
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

# The finished model is this fraction of the size below, and its bottom
# hovers this high, centring the canister on the player's shoulders (the
# player's pauldrons span 1.18-1.44; the player is about 2 tall).
SCALE = 0.5
HOVER_Z = 1.10
# The whole robot leans back by this much about its middle, so its face
# looks up toward the 60-degree camera: half the player's face tilt (its
# body leans 0.1 and its head 0.3 more; rigged-armor/sprite_pose.py
# BODY_LEAN, HEAD_TILT), as the full tilt looked too obvious.
FACE_TILT = (0.1 + 0.3) / 2
# Proportions before shrinking, in the heroic scenes' units.
FLOAT = 0.26            # gap between the floor and the canister's bottom
BODY_R = 0.225          # the lower two thirds
BODY_H = 0.70
SEAM = 0.025            # where the head begins above the body
LID_R = BODY_R          # the head: the body's tube continued up
HEAD_H = 0.36
BODY_TOP = FLOAT + BODY_H
LID_BOTTOM = BODY_TOP + SEAM
LID_TOP = LID_BOTTOM + HEAD_H
HEAD_Z = LID_BOTTOM + HEAD_H / 2
# The hover ring: a thin glowing torus this far below the bottom, far
# enough that the 60-degree camera sees its front in front of the body.
RING_R = 0.264
RING_THICKNESS = 0.014
RING_GAP = 0.2
# The manipulators are this much larger than first built, about the shoulder.
ARM_SIZE = 2.2
# The eyes float this far in front of the head as vertical planes facing
# straight ahead, centred on the head's height.
EYE_GAP = 0.05
EYE_Z = HEAD_Z
EYE_SPACING = 0.16      # half the distance between the eye centres
EYE_RIM = 0.029         # width of the bright edge of each eye
# Player visor glow (rigged-armor/build.py).
CYAN_BASE = (.3, .9, 1.0)
CYAN_EMIT = (.1, .75, 1.0)
# The height of the eyes' centre once built, for close-ups of the face.
FACE_HEIGHT = HOVER_Z + (EYE_Z - FLOAT) * SCALE


def material(name, color, roughness=0.35, metallic=0.0, emission=None, strength=0.0,
             rim=None, rim_strength=0.0, coat=0.0):
    """Principled material with the heroic sprites' optional Fresnel rim glow
    (see build-heroic.py material())."""
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (*color, 1)
    bsdf.inputs['Roughness'].default_value = roughness
    bsdf.inputs['Metallic'].default_value = metallic
    bsdf.inputs['IOR'].default_value = 1.45
    bsdf.inputs['Coat Weight'].default_value = coat
    if emission:
        bsdf.inputs['Emission Color'].default_value = (*emission, 1)
        bsdf.inputs['Emission Strength'].default_value = strength
    if rim:
        out = nodes['Material Output']
        weight = nodes.new('ShaderNodeLayerWeight')
        weight.inputs['Blend'].default_value = 0.3
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
        links.new(bsdf.outputs[0], add.inputs[0])
        links.new(glow.outputs[0], add.inputs[1])
        links.new(bsdf.outputs[0], mix.inputs[1])
        links.new(add.outputs[0], mix.inputs[2])
        links.new(mix.outputs[0], out.inputs['Surface'])
    return mat


def see_through(mat, opacity):
    """Let part of the light through: mix the surface with a transparent one."""
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    out = nodes['Material Output']
    surface = out.inputs['Surface'].links[0].from_socket
    clear = nodes.new('ShaderNodeBsdfTransparent')
    mix = nodes.new('ShaderNodeMixShader')
    mix.inputs['Fac'].default_value = opacity
    links.new(clear.outputs[0], mix.inputs[1])
    links.new(surface, mix.inputs[2])
    links.new(mix.outputs[0], out.inputs['Surface'])
    return mat


def light_glow(name, strength, opacity, softness):
    """Pure light with no surface reflection: emission mixed with
    transparency, most opaque where the surface faces the viewer and fading
    toward the silhouette, so a tube of it reads as a soft blur of light."""
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*CYAN_BASE, 1)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.remove(nodes['Principled BSDF'])
    out = nodes['Material Output']
    facing = nodes.new('ShaderNodeLayerWeight')
    facing.inputs['Blend'].default_value = 0.5
    invert = nodes.new('ShaderNodeMath')
    invert.operation = 'SUBTRACT'
    invert.inputs[0].default_value = 1.0
    links.new(facing.outputs['Facing'], invert.inputs[1])
    curve = nodes.new('ShaderNodeMath')
    curve.operation = 'POWER'
    curve.inputs[1].default_value = softness
    links.new(invert.outputs[0], curve.inputs[0])
    scale = nodes.new('ShaderNodeMath')
    scale.operation = 'MULTIPLY'
    scale.inputs[1].default_value = opacity
    links.new(curve.outputs[0], scale.inputs[0])
    emit = nodes.new('ShaderNodeEmission')
    emit.inputs['Color'].default_value = (*CYAN_EMIT, 1)
    emit.inputs['Strength'].default_value = strength
    clear = nodes.new('ShaderNodeBsdfTransparent')
    mix = nodes.new('ShaderNodeMixShader')
    links.new(scale.outputs[0], mix.inputs['Fac'])
    links.new(clear.outputs[0], mix.inputs[1])
    links.new(emit.outputs[0], mix.inputs[2])
    links.new(mix.outputs[0], out.inputs['Surface'])
    return mat


def floor_pool(name):
    """A faint pool of cyan light: opacity (1 - distance)^2 * 0.7, the
    distance measured from the disc's centre in units of its radius (from
    its generated coordinates, so applying its scale changes nothing), so it
    fades out before its edge."""
    pool = material(name, CYAN_BASE, 1.0, emission=CYAN_EMIT, strength=1.0)
    nodes, links = pool.node_tree.nodes, pool.node_tree.links
    out = nodes['Material Output']
    coords = nodes.new('ShaderNodeTexCoord')
    grad = nodes.new('ShaderNodeTexGradient')
    grad.gradient_type = 'SPHERICAL'
    centred = nodes.new('ShaderNodeVectorMath')
    centred.operation = 'MULTIPLY_ADD'
    centred.inputs[1].default_value = (2, 2, 0)
    centred.inputs[2].default_value = (-1, -1, 0)
    links.new(coords.outputs['Generated'], centred.inputs[0])
    links.new(centred.outputs[0], grad.inputs['Vector'])
    square = nodes.new('ShaderNodeMath')
    square.operation = 'POWER'
    square.inputs[1].default_value = 2.0
    links.new(grad.outputs['Fac'], square.inputs[0])
    fade = nodes.new('ShaderNodeMath')
    fade.operation = 'MULTIPLY'
    fade.inputs[1].default_value = 0.7
    links.new(square.outputs[0], fade.inputs[0])
    emit = nodes.new('ShaderNodeEmission')
    emit.inputs['Color'].default_value = (*CYAN_EMIT, 1)
    emit.inputs['Strength'].default_value = 1.0
    clear = nodes.new('ShaderNodeBsdfTransparent')
    mix = nodes.new('ShaderNodeMixShader')
    links.new(fade.outputs[0], mix.inputs['Fac'])
    links.new(clear.outputs[0], mix.inputs[1])
    links.new(emit.outputs[0], mix.inputs[2])
    links.new(mix.outputs[0], out.inputs['Surface'])
    return pool


class Parts:
    """The materials and the collections of one robot being built."""

    def __init__(self, body_col, glow_col):
        self.body_col, self.glow_col = body_col, glow_col
        # White glazed ceramic: a soft, non-metallic base under a glossy
        # coat, darker than pure white so the studio key light does not burn
        # it out.
        self.ceramic = material('Iris white ceramic', (.58, .57, .55), .5, rim=(.8, .9, 1.0),
                                rim_strength=.25, coat=.5)
        self.brass = material('Iris brass band', (.80, .58, .26), .3, 1.0, rim=(1.0, .85, .6),
                              rim_strength=.3)
        # Joint housings (shoulder hubs, gripper palms): plain gray, not brass.
        self.gray = material('Iris gray joint housing', (.36, .38, .41), .4, .6, rim=(.7, .8, .9),
                             rim_strength=.2)
        self.dark = material('Iris dark seam', (.025, .034, .045), .5, .2)
        self.joint = material('Iris dark iron joint', (.16, .16, .18), .4, 1.0)
        self.eye_edge = material('Iris eye edge', CYAN_BASE, .35, emission=CYAN_EMIT, strength=6.0)
        # The fill lets a little of what is behind show through; much more
        # and the sprite's plain alpha blending turns the overhanging parts a
        # dull teal.
        self.eye_fill = see_through(material('Iris eye fill', CYAN_BASE, .35, emission=CYAN_EMIT,
                                             strength=1.2), 0.85)
        # The hover ring: a thin core of light inside a wider, fainter halo.
        self.ring_core = light_glow('Iris hover ring core', 3.0, 0.9, 0.6)
        self.ring_halo = light_glow('Iris hover ring halo', 1.5, 0.45, 2.5)
        self.pool = floor_pool('Iris floor glow')


P = None    # the Parts of the robot being built


def auto_smooth(mesh, angle=math.radians(30)):
    if hasattr(mesh, 'use_auto_smooth'):
        mesh.use_auto_smooth = True
        mesh.auto_smooth_angle = angle
    else:
        mesh.set_sharp_from_angle(angle=angle)


def no_ink(mesh):
    """Mark every face for Freestyle, so linesets excluding face marks draw
    no ink round them (the 'freestyle_face' attribute in Blender 4.1+)."""
    if hasattr(mesh.polygons[0], 'use_freestyle_mark'):
        for face in mesh.polygons:
            face.use_freestyle_mark = True
        return
    marks = mesh.attributes.get('freestyle_face') or mesh.attributes.new(
        'freestyle_face', 'BOOLEAN', 'FACE')
    marks.data.foreach_set('value', [True] * len(mesh.polygons))


def place(obj, mat, glow=False, smooth=True, name=None):
    """Give obj its material and move it to the body or glow collection;
    glowing parts get Freestyle face marks, so no ink is drawn round them."""
    if name:
        obj.name = name
    if mat is not None:
        obj.data.materials.append(mat)
    for face in obj.data.polygons:
        face.use_smooth = smooth
    if glow:
        no_ink(obj.data)
    if smooth:
        auto_smooth(obj.data)
    for old in list(obj.users_collection):
        old.objects.unlink(obj)
    (P.glow_col if glow else P.body_col).objects.link(obj)
    return obj


def bevel(obj, width, segments=3):
    mod = obj.modifiers.new('Rounded edges', 'BEVEL')
    mod.width = width
    mod.segments = segments
    mod.limit_method = 'ANGLE'
    obj.modifiers.new('Weighted normals', 'WEIGHTED_NORMAL')
    return obj


def cylinder(name, radius, z0, z1, mat, vertices=64, x=0.0, y=0.0, edge=0.0):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=z1 - z0,
                                        location=(x, y, (z0 + z1) / 2))
    obj = place(bpy.context.object, mat, name=name)
    if edge:
        bevel(obj, edge)
    return obj


def sphere(name, pos, radius, mat, segments=16):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=segments // 2,
                                         radius=radius, location=pos)
    return place(bpy.context.object, mat, name=name)


def block(name, pos, size, mat, radius=0.005, rotation=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=pos, rotation=rotation)
    obj = bpy.context.object
    obj.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    place(obj, mat, name=name)
    return bevel(obj, radius)


def rod(name, a, b, radius, mat, vertices=16):
    """A round bar from a to b."""
    a, b = Vector(a), Vector(b)
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius,
                                        depth=(b - a).length, location=(a + b) / 2)
    obj = bpy.context.object
    obj.rotation_euler = (b - a).to_track_quat('Z', 'Y').to_euler()
    return place(obj, mat, name=name)


def on_surface(radius, angle, z, out=0.0):
    """A point on a vertical cylinder; angle 0 faces the camera (-y)."""
    r = radius + out
    return (r * math.sin(angle), -r * math.cos(angle), z)


def build_canister():
    # Body and head: one tube of ceramic, no seam at the neck, its top edge
    # rounded; a brass band round its bottom edge, another where the head
    # begins, and a dark underside.
    cylinder('Iris body', BODY_R, FLOAT + 0.01, LID_TOP, P.ceramic, edge=0.035)
    cylinder('Iris bottom band', BODY_R + 0.012, FLOAT, FLOAT + 0.06, P.brass, edge=0.008)
    cylinder('Iris underside', BODY_R - 0.03, FLOAT - 0.02, FLOAT + 0.01, P.dark)
    cylinder('Iris head band', LID_R + 0.01, LID_BOTTOM, LID_BOTTOM + 0.05, P.brass, edge=0.008)
    # A raised vertical seam strip on the body (glazed ceramic: no rivets
    # or screws anywhere).
    strip = math.radians(52)
    block('Iris seam strip', on_surface(BODY_R, strip, FLOAT + 0.38, 0.004),
          (0.045, 0.016, 0.56), P.ceramic, 0.004, rotation=(0, 0, strip))


def build_antenna():
    # Short antenna, doubling as the microphone: a collar, a thin rod and a
    # small dark mesh ball held in a brass cup. Off-centre toward the back
    # right so the eyes stay clear.
    x, y = 0.06, 0.05
    cylinder('Iris antenna collar', 0.032, LID_TOP - 0.035, LID_TOP + 0.02, P.brass, 24, x, y,
             edge=0.006)
    rod('Iris antenna rod', (x, y, LID_TOP + 0.01), (x + 0.02, y + 0.03, LID_TOP + 0.26),
        0.011, P.ceramic)
    tip = Vector((x + 0.02, y + 0.03, LID_TOP + 0.28))
    cylinder('Iris mic cup', 0.026, tip.z - 0.03, tip.z - 0.005, P.brass, 24, tip.x, tip.y,
             edge=0.004)
    mic = sphere('Iris mic grille', tip, 0.032, P.joint, 24)
    mic.scale = (1, 1, 0.85)


def curved_panel(name, half_width, z0, z1, corner, d0, d1, mat):
    """A rounded rectangle bent round the body: built flat with u (arc
    length across the front) and d (height off the body surface), cut into
    narrow strips, then wrapped so u follows the body's curve."""
    bm = bmesh.new()
    outline = []
    for cu, cz, start in ((half_width - corner, z1 - corner, 0), (-half_width + corner, z1 - corner, 90),
                          (-half_width + corner, z0 + corner, 180), (half_width - corner, z0 + corner, 270)):
        for k in range(7):
            angle = math.radians(start + k * 15)
            outline.append((cu + corner * math.cos(angle), cz + corner * math.sin(angle)))
    face = bm.faces.new([bm.verts.new((u, d0, z)) for u, z in outline])
    bmesh.ops.extrude_face_region(bm, geom=[face])
    # The extruded copy of the face stays in place; lift it to d1.
    for v in bm.verts:
        if v.co.y == d0 and v not in face.verts:
            v.co.y = d1
    steps = 16
    for k in range(1, steps):
        u = -half_width + 2 * half_width * k / steps
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(u, 0, 0), plane_no=(1, 0, 0))
    for v in bm.verts:
        u, d, z = v.co
        r = BODY_R + d
        v.co = (r * math.sin(u / BODY_R), -r * math.cos(u / BODY_R), z)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    place(obj, mat, name=name)
    return bevel(obj, 0.003, 2)


def build_door():
    # The ration locker door on the front of the body, always closed: tall
    # enough to take rations out of, curved with the body, set in a dark
    # gap, with two hinges on its left edge and a latch on its right.
    z0, z1, half = FLOAT + 0.10, FLOAT + 0.58, 0.12
    curved_panel('Iris locker gap', half + 0.012, z0 - 0.012, z1 + 0.012, 0.05, -0.006, 0.003, P.dark)
    curved_panel('Iris locker door', half, z0, z1, 0.04, 0.0, 0.012, P.ceramic)
    for z in (z0 + 0.09, z1 - 0.09):
        u = -half - 0.004
        angle = u / BODY_R
        block('Iris locker hinge', on_surface(BODY_R, angle, z, 0.012), (0.02, 0.02, 0.06),
              P.brass, 0.004, rotation=(0, 0, angle))
    angle = (half - 0.035) / BODY_R
    block('Iris locker latch', on_surface(BODY_R, angle, (z0 + z1) / 2, 0.018), (0.018, 0.014, 0.07),
          P.brass, 0.004, rotation=(0, 0, angle))


def build_arm(side):
    """A jointed manipulator splayed at the side: shoulder hub at mid
    body, upper arm down and out, forearm forward, a three-fingered gripper."""
    s = side
    start = set(bpy.data.objects)
    shoulder = Vector((s * (BODY_R + 0.025), -0.02, FLOAT + 0.52))
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=0.055, depth=0.05,
                                        location=shoulder, rotation=(0, math.pi / 2, 0))
    bevel(place(bpy.context.object, P.gray, name='Iris shoulder hub'), 0.01)
    sphere('Iris shoulder joint', shoulder + Vector((s * 0.03, 0, 0)), 0.046, P.joint)
    # Splayed out from the body so they stand clear of its silhouette.
    elbow = Vector((s * (BODY_R + 0.13), 0.0, FLOAT + 0.30))
    wrist = Vector((s * (BODY_R + 0.15), -0.19, FLOAT + 0.36))
    rod('Iris upper arm', shoulder + Vector((s * 0.03, 0, 0)), elbow, 0.040, P.ceramic)
    sphere('Iris elbow', elbow, 0.044, P.joint)
    rod('Iris forearm', elbow, wrist, 0.036, P.ceramic)
    # Gripper: a short palm with three curled fingers (two below, one above).
    ahead = (wrist - elbow).normalized()
    palm = wrist + ahead * 0.03
    sphere('Iris wrist', wrist, 0.038, P.joint)
    bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=0.038, depth=0.03, location=palm)
    hub = bpy.context.object
    hub.rotation_euler = ahead.to_track_quat('Z', 'Y').to_euler()
    bevel(place(hub, P.gray, name='Iris gripper palm'), 0.006)
    up = Vector((0, 0, 1))
    across = ahead.cross(up).normalized()
    for angle in (90, 210, 330):
        radial = up * math.sin(math.radians(angle)) + across * math.cos(math.radians(angle))
        base = palm + ahead * 0.015 + radial * 0.022
        knuckle = base + ahead * 0.04 + radial * 0.012
        tip = knuckle + ahead * 0.032 - radial * 0.018
        rod('Iris finger', base, knuckle, 0.014, P.ceramic, 10)
        sphere('Iris knuckle', knuckle, 0.015, P.joint, 10)
        rod('Iris finger tip', knuckle, tip, 0.013, P.ceramic, 10)
    # Built at the first prototype's size, then enlarged about the shoulder.
    grow = (Matrix.Translation(shoulder) @ Matrix.Scale(ARM_SIZE, 4)
            @ Matrix.Translation(-shoulder))
    for obj in set(bpy.data.objects) - start:
        obj.matrix_world = grow @ obj.matrix_world
        for mod in obj.modifiers:
            if mod.type == 'BEVEL':
                mod.width *= ARM_SIZE


def build_hover():
    # The cyan hover ring floating under the bottom (a thin core inside a
    # soft halo) and a faint pool of light on the floor.
    for name, mat, thickness, segments in (('Iris hover ring', P.ring_core, RING_THICKNESS, 12),
                                           ('Iris hover ring halo', P.ring_halo, RING_THICKNESS * 3.5, 16)):
        bpy.ops.mesh.primitive_torus_add(major_radius=RING_R, minor_radius=thickness,
                                         major_segments=64, minor_segments=segments,
                                         location=(0, 0, FLOAT - RING_GAP))
        place(bpy.context.object, mat, glow=True, name=name)
    bpy.ops.mesh.primitive_circle_add(vertices=48, radius=1.0, fill_type='NGON',
                                      location=(0, 0, 0.004))
    disc = place(bpy.context.object, P.pool, glow=True, smooth=False, name='Iris floor glow')
    disc['iris_floor'] = True
    return disc


# --- Eyes -----------------------------------------------------------------
# Outlines are 2D (x to screen right, y up), given for the eye on screen
# left; most right eyes are its mirror image. Sizes are in units of R, the
# radius of the first prototype's hexagon eyes.

R = 0.173


def regular(n, radius, start=90.0, squash=1.0):
    return [(radius * math.cos(math.radians(start + i * 360 / n)),
             squash * radius * math.sin(math.radians(start + i * 360 / n))) for i in range(n)]


def star(points, outer, inner, start=90.0):
    return [((outer if i % 2 == 0 else inner) * math.cos(math.radians(start + i * 180 / points)),
             (outer if i % 2 == 0 else inner) * math.sin(math.radians(start + i * 180 / points)))
            for i in range(points * 2)]


def arc_band(width, height, thickness, start, end, steps=20):
    """A curved band along an elliptical arc about the origin (width and
    height are the outer ellipse's), from angle start to end in degrees."""
    def arc(rx, ry):
        return [(rx * math.cos(math.radians(start + (end - start) * k / steps)),
                 ry * math.sin(math.radians(start + (end - start) * k / steps)))
                for k in range(steps + 1)]
    return arc(width / 2, height / 2) + arc(width / 2 - thickness, height / 2 - thickness)[::-1]


def shift(points, dx, dy):
    return [(x + dx, y + dy) for x, y in points]


def bent_stroke(points, width):
    """A stroke of even width along a polyline, with mitred corners."""
    def normal(a, b):
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        return -dy / length, dx / length
    left, right = [], []
    for k, (x, y) in enumerate(points):
        normals = [normal(points[j], points[j + 1]) for j in (k - 1, k)
                   if 0 <= j < len(points) - 1]
        nx = sum(n[0] for n in normals) / len(normals)
        ny = sum(n[1] for n in normals) / len(normals)
        length = math.hypot(nx, ny)
        nx, ny = nx / length, ny / length
        miter = width / 2 / (nx * normals[0][0] + ny * normals[0][1])
        left.append((x + nx * miter, y + ny * miter))
        right.append((x - nx * miter, y - ny * miter))
    return left + right[::-1]


def mirror(points):
    return [(-x, y) for x, y in reversed(points)]


def rectangle(width, height):
    w, h = width / 2, height / 2
    return [(-w, -h), (w, -h), (w, h), (-w, h)]


EYE = rectangle(1.0 * R, 1.25 * R)  # the normal eye: a filled rectangle, a little tall
DOT = regular(16, 0.32 * R)         # a small round dot
# name: (left eye outlines, right eye outlines, (outward shift, upward shift)
# of each eye in units of R, bright edge width). The scenes follow
# dev-notes/handoff-stage6-robot-iris-design-20261121.md.
EXPRESSIONS = {
    # Normal: filled rectangles.
    'neutral': ([EYE], [EYE], (0, 0), EYE_RIM),
    # Joy (a won battle, the core destroyed): rainbow arcs, the smiling eyes
    # of Japanese comics, on a tall ellipse.
    'joy': ([arc_band(1.5 * R, 2.2 * R, 0.35 * R, 12, 168)],
            [arc_band(1.5 * R, 2.2 * R, 0.35 * R, 12, 168)], (0, -0.35), 0.45 * EYE_RIM),
    # Worry (the hunger warning): arcs bowing downward on the same kind of
    # ellipse, spread like the kanji 八 (eight): their inner ends a little
    # higher, sweeping down and out.
    'worry': ([arc_band(1.5 * R, 2.0 * R, 0.3 * R, 245, 360)],
              [mirror(arc_band(1.5 * R, 2.0 * R, 0.3 * R, 245, 360))], (0.15, 0.55),
              0.45 * EYE_RIM),
    # Panic (the emergency rations): blank, tiny round dots, all expression
    # gone.
    'panic': ([regular(16, 0.16 * R)], [regular(16, 0.16 * R)], (-0.2, 0), 0.6 * EYE_RIM),
    # Surprise (falling into a pit): plump five-pointed stars, past the
    # canister.
    'surprise': ([star(5, 1.33 * R, 0.79 * R)], [star(5, 1.33 * R, 0.79 * R)], (0.3, 0.1),
                 0.8 * EYE_RIM),
    # Curiosity (an unknown monster, a treasure chest): the normal eye,
    # and a small dot under a brow bent like the kana he: rising steeply
    # from the inner end over the dot, then dropping a little to the outer
    # end, like a famous science-fiction officer's raised eyebrow.
    'curious': ([EYE], [DOT, shift(bent_stroke([(-0.6 * R, 0), (0.3 * R, 0.42 * R),
                                                 (0.7 * R, 0.2 * R)], 0.18 * R), 0, 0.14 * R)],
                (0, 0), 0.4 * EYE_RIM),
    # Waiting: thin horizontal bars, small (slowly breathing in the game).
    'idle': ([rectangle(1.36 * R, 0.3 * R)], [rectangle(1.36 * R, 0.3 * R)], (0, -0.15),
             0.35 * EYE_RIM),
}


def eye_polygon_mesh(name, polygons, rim):
    """Flat eye: each outline becomes a translucent fill inside a bright edge."""
    bm = bmesh.new()
    for outline in polygons:
        verts = [bm.verts.new((x, 0, y)) for x, y in outline]
        face = bm.faces.new(verts)
        face.normal_update()
        if face.normal.y > 0:
            face.normal_flip()
        edge = bmesh.ops.inset_region(bm, faces=[face], thickness=rim, depth=0,
                                      use_even_offset=True)['faces']
        face.material_index = 1
        for f in edge:
            f.material_index = 0
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(P.eye_edge)
    place(obj, P.eye_fill, glow=True, smooth=False)
    return obj


def build_eyes():
    """Both eyes in every expression, each tagged with its expression."""
    for expr, (left, right, (out, up), rim) in EXPRESSIONS.items():
        for side, polygons in ((-1, left), (1, right)):
            obj = eye_polygon_mesh(f'Iris eye {expr} {"L" if side < 0 else "R"}', polygons, rim)
            obj.location = (side * (EYE_SPACING + out * R), -(LID_R + EYE_GAP), EYE_Z + up * R)
            obj['iris_expression'] = expr


def show_expression(objects, name):
    """Render only the eyes of the named expression among objects."""
    for obj in objects:
        if 'iris_expression' in obj:
            obj.hide_render = obj['iris_expression'] != name


def build(x=0.0, y=0.0, body_col=None, glow_col=None):
    """Build Iris standing at (x, y) and return its objects. Its parts go
    into body_col and its glowing parts into glow_col (the scene's own
    collection by default); only the neutral eyes render."""
    global P
    scene_col = bpy.context.scene.collection
    P = Parts(body_col or scene_col, glow_col or scene_col)
    start = set(bpy.data.objects)
    build_canister()
    build_antenna()
    build_door()
    build_arm(-1)
    build_arm(1)
    floor = build_hover()
    build_eyes()
    objects = set(bpy.data.objects) - start
    # Shrink everything to SCALE, lift it to HOVER_Z, lean it back by
    # FACE_TILT and move it to (x, y); the floor glow stays on the floor.
    bpy.context.view_layer.update()
    lift = Matrix.Translation((0, 0, HOVER_Z - FLOAT * SCALE)) @ Matrix.Scale(SCALE, 4)
    middle = Vector((0, 0, HOVER_Z + (LID_TOP - FLOAT) * SCALE / 2))
    lift = (Matrix.Translation((x, y, 0)) @ Matrix.Translation(middle)
            @ Matrix.Rotation(-FACE_TILT, 4, 'X') @ Matrix.Translation(-middle) @ lift)
    for obj in objects:
        if obj is floor:
            obj.location = (x, y, 0.004)
            obj.scale = (0.42 * SCALE * 1.5, 0.42 * SCALE * 1.5, 1)
        else:
            obj.matrix_world = lift @ obj.matrix_world
    # Apply the transforms to the meshes, scaling each bevel by its object's
    # scale so the rounding stays as large as it looked before.
    bpy.context.view_layer.update()
    for obj in objects:
        size = sum(obj.matrix_world.to_scale()) / 3
        for mod in obj.modifiers:
            if mod.type == 'BEVEL':
                mod.width *= size
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = next(iter(objects))
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    show_expression(objects, 'neutral')
    return objects
