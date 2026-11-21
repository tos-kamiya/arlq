"""Prototype of Iris, the talkative Stage 6 robot (dev-notes/handoff-stage6-robot-iris-design-20261121.md).

blender --factory-startup --background --threads 4 --python dev-samples/3d-stage1/build-robot-iris.py

Builds a small tea-canister robot (white glazed ceramic, brass bands, antenna,
folded manipulator arms, storage door, a cyan hover ring) and its floating
polygon eyes (the normal expression only), saves robot-iris/robot-iris.blend
and renders it with the sprite camera (export-sprites.py: 60-degree
orthographic view, 256 px per 2.6 units, Freestyle ink) to
robot-iris/iris.png, plus close-ups robot-iris/closeup.png (sprite angle) and
robot-iris/closeup-side.png (three-quarter view from the side) and
robot-iris/closeup-front.png (straight from the front).

The model is built at the first prototype's size (below) and then shrunk to
SCALE and lifted so it hovers at the player's shoulder height (HOVER_Z);
only the faint pool of light stays on the floor.

Not yet part of the heroic scenes or the game: the member letter is undecided.
"""
from pathlib import Path
import math
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

OUT = Path(__file__).resolve().parent / 'robot-iris'
OUT.mkdir(parents=True, exist_ok=True)

# The finished model is this fraction of the size below, and its bottom
# hovers this high, centring the canister on the player's shoulders (the player's pauldrons span 1.18-1.44; the player is
# about 2 tall).
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
SEAM = 0.025            # the thin gap between head and body
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
EYE_SPACING = 0.22      # half the distance between the eye centres
EYE_RIM = 0.029         # width of the bright edge of each eye
# Player visor glow (rigged-armor/build.py).
CYAN_BASE = (.3, .9, 1.0)
CYAN_EMIT = (.1, .75, 1.0)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 128
scene.cycles.use_denoising = False
scene.cycles.sample_clamp_indirect = 2.0
scene.cycles.blur_glossy = 1.0
scene.cycles.caustics_reflective = False
scene.cycles.caustics_refractive = False
scene.view_settings.view_transform = 'Standard'
scene.view_settings.look = 'Medium High Contrast'
world = bpy.data.worlds.new('Night studio')
world.use_nodes = True
world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.012, 0.018, 0.03, 1)
scene.world = world

body_col = bpy.data.collections.new('Iris body')
glow_col = bpy.data.collections.new('Iris glow')
scene.collection.children.link(body_col)
scene.collection.children.link(glow_col)


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


# White glazed ceramic: a soft, non-metallic base under a glossy coat.
# Darker than pure white, so the studio key light does not burn it out.
steel = material('Iris white ceramic', (.58, .57, .55), .5, rim=(.8, .9, 1.0),
                 rim_strength=.25, coat=.5)
lid_steel = material('Iris lid ceramic', (.60, .59, .57), .5, rim=(.8, .9, 1.0),
                     rim_strength=.25, coat=.5)
brass = material('Iris brass band', (.80, .58, .26), .3, 1.0, rim=(1.0, .85, .6), rim_strength=.3)
# Joint housings (shoulder hubs, gripper palms): plain gray, not brass.
gray = material('Iris gray joint housing', (.36, .38, .41), .4, .6, rim=(.7, .8, .9), rim_strength=.2)
dark = material('Iris dark seam', (.025, .034, .045), .5, .2)
joint = material('Iris dark iron joint', (.16, .16, .18), .4, 1.0)
eye_edge = material('Iris eye edge', CYAN_BASE, .35, emission=CYAN_EMIT, strength=6.0)
eye_fill = see_through(material('Iris eye fill', CYAN_BASE, .35, emission=CYAN_EMIT,
                                strength=0.8), 0.5)


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


# The hover ring: a thin core of light inside a wider, fainter halo.
ring_glow = light_glow('Iris hover ring core', 3.0, 0.9, 0.6)
ring_halo = light_glow('Iris hover ring halo', 1.5, 0.45, 2.5)


def auto_smooth(mesh, angle=math.radians(30)):
    if hasattr(mesh, 'use_auto_smooth'):
        mesh.use_auto_smooth = True
        mesh.auto_smooth_angle = angle
    else:
        mesh.set_sharp_from_angle(angle=angle)


def place(obj, mat, collection=body_col, smooth=True, name=None):
    if name:
        obj.name = name
    if mat is not None:
        obj.data.materials.append(mat)
    for face in obj.data.polygons:
        face.use_smooth = smooth
    if smooth:
        auto_smooth(obj.data)
    for old in list(obj.users_collection):
        old.objects.unlink(obj)
    collection.objects.link(obj)
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


def sphere(name, pos, radius, mat, segments=16, collection=body_col):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=segments // 2,
                                         radius=radius, location=pos)
    return place(bpy.context.object, mat, collection, name=name)


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
    cylinder('Iris body', BODY_R, FLOAT + 0.01, LID_TOP, steel, edge=0.035)
    cylinder('Iris bottom band', BODY_R + 0.012, FLOAT, FLOAT + 0.06, brass, edge=0.008)
    cylinder('Iris underside', BODY_R - 0.03, FLOAT - 0.02, FLOAT + 0.01, dark)
    cylinder('Iris head band', LID_R + 0.01, LID_BOTTOM, LID_BOTTOM + 0.05, brass, edge=0.008)
    # A raised vertical seam strip on the body (glazed ceramic: no rivets
    # or screws anywhere).
    strip = math.radians(52)
    block('Iris seam strip', on_surface(BODY_R, strip, FLOAT + 0.38, 0.004),
          (0.045, 0.016, 0.56), steel, 0.004, rotation=(0, 0, strip))


def build_antenna():
    # Short antenna, doubling as the microphone: a collar, a thin rod and a
    # small dark mesh ball held in a brass cup. Off-centre toward the back
    # right so the eyes stay clear.
    x, y = 0.06, 0.05
    cylinder('Iris antenna collar', 0.032, LID_TOP - 0.035, LID_TOP + 0.02, brass, 24, x, y,
             edge=0.006)
    rod('Iris antenna rod', (x, y, LID_TOP + 0.01), (x + 0.02, y + 0.03, LID_TOP + 0.26),
        0.011, steel)
    tip = Vector((x + 0.02, y + 0.03, LID_TOP + 0.28))
    cylinder('Iris mic cup', 0.026, tip.z - 0.03, tip.z - 0.005, brass, 24, tip.x, tip.y,
             edge=0.004)
    mic = sphere('Iris mic grille', tip, 0.032, joint, 24)
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
    curved_panel('Iris locker gap', half + 0.012, z0 - 0.012, z1 + 0.012, 0.05, -0.006, 0.003, dark)
    curved_panel('Iris locker door', half, z0, z1, 0.04, 0.0, 0.012, steel)
    for z in (z0 + 0.09, z1 - 0.09):
        u = -half - 0.004
        angle = u / BODY_R
        block('Iris locker hinge', on_surface(BODY_R, angle, z, 0.012), (0.02, 0.02, 0.06),
              brass, 0.004, rotation=(0, 0, angle))
    angle = (half - 0.035) / BODY_R
    block('Iris locker latch', on_surface(BODY_R, angle, (z0 + z1) / 2, 0.018), (0.018, 0.014, 0.07),
          brass, 0.004, rotation=(0, 0, angle))


def build_arm(side):
    """A thin jointed manipulator folded at the side: shoulder hub at mid
    body, upper arm down, forearm forward, a three-fingered gripper."""
    s = side
    start = set(bpy.data.objects)
    shoulder = Vector((s * (BODY_R + 0.025), -0.02, FLOAT + 0.52))
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=0.055, depth=0.05,
                                        location=shoulder, rotation=(0, math.pi / 2, 0))
    bevel(place(bpy.context.object, gray, name='Iris shoulder hub'), 0.01)
    sphere('Iris shoulder joint', shoulder + Vector((s * 0.03, 0, 0)), 0.035, joint)
    # Splayed out from the body so they stand clear of its silhouette.
    elbow = Vector((s * (BODY_R + 0.13), 0.0, FLOAT + 0.30))
    wrist = Vector((s * (BODY_R + 0.15), -0.19, FLOAT + 0.36))
    rod('Iris upper arm', shoulder + Vector((s * 0.03, 0, 0)), elbow, 0.022, steel)
    sphere('Iris elbow', elbow, 0.032, joint)
    rod('Iris forearm', elbow, wrist, 0.019, steel)
    # Gripper: a short palm with three curled fingers (two below, one above).
    ahead = (wrist - elbow).normalized()
    palm = wrist + ahead * 0.03
    sphere('Iris wrist', wrist, 0.026, joint)
    bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=0.03, depth=0.03, location=palm)
    hub = bpy.context.object
    hub.rotation_euler = ahead.to_track_quat('Z', 'Y').to_euler()
    bevel(place(hub, gray, name='Iris gripper palm'), 0.006)
    up = Vector((0, 0, 1))
    across = ahead.cross(up).normalized()
    for angle in (90, 210, 330):
        radial = up * math.sin(math.radians(angle)) + across * math.cos(math.radians(angle))
        base = palm + ahead * 0.015 + radial * 0.022
        knuckle = base + ahead * 0.04 + radial * 0.012
        tip = knuckle + ahead * 0.032 - radial * 0.018
        rod('Iris finger', base, knuckle, 0.008, steel, 10)
        sphere('Iris knuckle', knuckle, 0.009, joint, 10)
        rod('Iris finger tip', knuckle, tip, 0.007, steel, 10)
    # Built at the first prototype's size, then enlarged about the shoulder.
    grow = (Matrix.Translation(shoulder) @ Matrix.Scale(ARM_SIZE, 4)
            @ Matrix.Translation(-shoulder))
    for obj in set(bpy.data.objects) - start:
        obj.matrix_world = grow @ obj.matrix_world
        for mod in obj.modifiers:
            if mod.type == 'BEVEL':
                mod.width *= ARM_SIZE


def build_hover():
    # The cyan hover ring floating under the bottom, a faint pool of light on
    # the floor and a small light that lights the underside.
    bpy.ops.mesh.primitive_torus_add(major_radius=RING_R, minor_radius=RING_THICKNESS,
                                     major_segments=64, minor_segments=12,
                                     location=(0, 0, FLOAT - RING_GAP))
    place(bpy.context.object, ring_glow, glow_col, name='Iris hover ring')
    bpy.ops.mesh.primitive_torus_add(major_radius=RING_R, minor_radius=RING_THICKNESS * 3.5,
                                     major_segments=64, minor_segments=16,
                                     location=(0, 0, FLOAT - RING_GAP))
    place(bpy.context.object, ring_halo, glow_col, name='Iris hover ring halo')
    pool = material('Iris floor glow', CYAN_BASE, 1.0, emission=CYAN_EMIT, strength=1.0)
    nodes, links = pool.node_tree.nodes, pool.node_tree.links
    out = nodes['Material Output']
    # Radial falloff from the centre: opacity = (1 - 2 * distance)^2 on a
    # unit-size disc, so the pool fades out before its edge.
    coords = nodes.new('ShaderNodeTexCoord')
    grad = nodes.new('ShaderNodeTexGradient')
    grad.gradient_type = 'SPHERICAL'
    links.new(coords.outputs['Object'], grad.inputs['Vector'])
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
    bpy.ops.mesh.primitive_circle_add(vertices=48, radius=1.0, fill_type='NGON',
                                      location=(0, 0, 0.004))
    disc = bpy.context.object
    disc.scale = (0.42, 0.42, 1)
    place(disc, pool, glow_col, smooth=False, name='Iris floor glow')
    bpy.ops.object.light_add(type='POINT', location=(0, 0, FLOAT - RING_GAP))
    light = bpy.context.object
    light.name = 'Iris hover light'
    light.data.energy = 6
    light.data.shadow_soft_size = 0.15
    light.data.color = CYAN_EMIT
    glow_col.objects.link(light)
    scene.collection.objects.unlink(light)


# --- Eyes -----------------------------------------------------------------
# The normal expression only: a regular hexagon per eye, within the
# canister's width. Outlines are 2D (x to screen right, y up).

def regular(n, radius, start=90.0):
    return [(radius * math.cos(math.radians(start + i * 360 / n)),
             radius * math.sin(math.radians(start + i * 360 / n))) for i in range(n)]


# Large enough to overhang the canister's sides.
HEX = regular(6, 0.173)


def eye_polygon_mesh(name, polygons):
    """Flat eye: each outline becomes a translucent fill inside a bright edge."""
    bm = bmesh.new()
    for outline in polygons:
        verts = [bm.verts.new((x, 0, y)) for x, y in outline]
        face = bm.faces.new(verts)
        face.normal_update()
        if face.normal.y > 0:
            face.normal_flip()
        edge = bmesh.ops.inset_region(bm, faces=[face], thickness=EYE_RIM, depth=0,
                                      use_even_offset=True)['faces']
        face.material_index = 1
        for f in edge:
            f.material_index = 0
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    obj.data.materials.append(eye_edge)
    obj.data.materials.append(eye_fill)
    return obj


def build_eyes():
    for side in (-1, 1):
        obj = eye_polygon_mesh(f'Iris eye {"L" if side < 0 else "R"}', [HEX])
        glow_col.objects.link(obj)
        obj.location = (side * EYE_SPACING, -(LID_R + EYE_GAP), EYE_Z)


build_canister()
build_antenna()
build_door()
build_arm(-1)
build_arm(1)
build_hover()
build_eyes()

# Shrink everything to SCALE, lift it to HOVER_Z and lean it back by
# FACE_TILT; the floor glow stays
# on the floor, and lights lose power with the square of the shrink.
# Bring matrix_world up to date with the locations set above.
bpy.context.view_layer.update()
lift = Matrix.Translation((0, 0, HOVER_Z - FLOAT * SCALE)) @ Matrix.Scale(SCALE, 4)
middle = Vector((0, 0, HOVER_Z + (LID_TOP - FLOAT) * SCALE / 2))
lift = (Matrix.Translation(middle) @ Matrix.Rotation(-FACE_TILT, 4, 'X')
        @ Matrix.Translation(-middle) @ lift)
for obj in [*body_col.all_objects, *glow_col.all_objects]:
    if obj.name == 'Iris floor glow':
        obj.scale = (0.42 * SCALE * 1.5, 0.42 * SCALE * 1.5, 1)
        continue
    obj.matrix_world = lift @ obj.matrix_world
    if obj.type == 'LIGHT':
        obj.data.energy *= SCALE * SCALE
        if obj.data.type == 'AREA':
            obj.data.size *= SCALE
            obj.data.size_y *= SCALE
        else:
            obj.data.shadow_soft_size *= SCALE
    else:
        for mod in obj.modifiers:
            if mod.type == 'BEVEL':
                mod.width *= SCALE

# Lights and camera as in the heroic scenes and export-sprites.py.
for name, pos, power, size, color in [
        ('Key', (-4, -6, 8), 1000, 5, (1.0, 0.93, 0.85)),
        ('Fill', (6, -3, 4), 250, 6, (0.6, 0.75, 1.0)),
        ('Rim left', (-7, 6, 4), 1300, 3, (0.55, 0.8, 1.0)),
        ('Rim right', (7, 6, 4), 1300, 3, (1.0, 0.7, 0.9))]:
    bpy.ops.object.light_add(type='AREA', location=pos)
    light = bpy.context.object
    light.name = name
    light.data.energy = power
    light.data.size = size
    light.data.color = color
    light.data.shape = 'DISK'
    light.rotation_euler = (Vector((0, 0, 0)) - light.location).to_track_quat('-Z', 'Y').to_euler()
bpy.ops.object.camera_add()
camera = bpy.context.object
scene.camera = camera
camera.data.type = 'ORTHO'
scene.render.film_transparent = True
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'

# Ink contours as in export-sprites.py, on the body only: the glowing eyes
# and ring stay unoutlined light.
scene.render.use_freestyle = True
settings = scene.view_layers[0].freestyle_settings
outline = settings.linesets[0] if settings.linesets else settings.linesets.new('Outline')
outline.linestyle = outline.linestyle or bpy.data.linestyles.new('Ink outline')
outline.select_silhouette = outline.select_border = False
outline.select_external_contour = True
outline.select_crease = False
outline.linestyle.color = (0.015, 0.02, 0.03)
outline.linestyle.thickness = 4.0
inner = settings.linesets.new('Inner parts')
inner.select_silhouette = inner.select_border = True
inner.select_external_contour = inner.select_crease = False
inner.linestyle = bpy.data.linestyles.new('Thin ink')
inner.linestyle.color = (0.04, 0.05, 0.07)
inner.linestyle.thickness = 1.5
inner.linestyle.alpha = 0.7
for lines in (outline, inner):
    lines.select_by_collection = True
    lines.collection = body_col


def frame(target_z, ortho, pixels):
    target = Vector((0, 0, target_z))
    camera.location = target + Vector((0, -7.5, 15 * math.sin(math.radians(60))))
    camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera.data.ortho_scale = ortho
    scene.render.resolution_x = scene.render.resolution_y = pixels


def trim(path):
    """Crop transparent margins symmetrically, as export-sprites.py does."""
    image = bpy.data.images.load(str(path), check_existing=False)
    width, height = image.size
    pixels = list(image.pixels)
    occupied = [(i % width, i // width) for i in range(width * height)
                if pixels[i * 4 + 3] > 0.01]
    left = max(0, min(p[0] for p in occupied) - 2)
    right = min(width, max(p[0] for p in occupied) + 3)
    bottom = max(0, min(p[1] for p in occupied) - 2)
    top = min(height, max(p[1] for p in occupied) + 3)
    left = min(left, width - right)
    right = width - left
    bottom = min(bottom, height - top)
    top = height - bottom
    trimmed = bpy.data.images.new(path.stem, right - left, top - bottom, alpha=True)
    trimmed.pixels = [value for row in range(bottom, top)
                      for value in pixels[(row * width + left) * 4:(row * width + right) * 4]]
    trimmed.filepath_raw = str(path)
    trimmed.file_format = 'PNG'
    trimmed.save()


bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'robot-iris.blend'))
frame(0.35, 4.6, round(256 * 4.6 / 2.6))
path = OUT / 'iris.png'
scene.render.filepath = str(path)
bpy.ops.render.render(write_still=True)
trim(path)
frame(HOVER_Z + 0.25, 1.1, 900)
scene.render.filepath = str(OUT / 'closeup.png')
bpy.ops.render.render(write_still=True)
# A three-quarter close-up from lower and to the side (screen right), to
# check the eyes' float, the arms and the hover ring in depth.
target = Vector((0, 0, HOVER_Z + 0.25))
yaw, pitch = math.radians(40), math.radians(20)
camera.location = target + 10 * Vector((math.sin(yaw) * math.cos(pitch),
                                        -math.cos(yaw) * math.cos(pitch), math.sin(pitch)))
camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
camera.data.ortho_scale = 1.1
scene.render.filepath = str(OUT / 'closeup-side.png')
bpy.ops.render.render(write_still=True)
# Straight from the front, nearly level, to check the face (the eyes).
yaw, pitch = 0.0, math.radians(8)
camera.location = target + 10 * Vector((math.sin(yaw) * math.cos(pitch),
                                        -math.cos(yaw) * math.cos(pitch), math.sin(pitch)))
camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
scene.render.filepath = str(OUT / 'closeup-front.png')
bpy.ops.render.render(write_still=True)
