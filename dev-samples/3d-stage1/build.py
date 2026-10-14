"""Run with: blender --background --python dev-samples/3d-stage1/build.py"""
from pathlib import Path
import math
import sys

import bpy
from mathutils import Vector

OUT = Path(__file__).resolve().parent
ATTACHED_CONES = '--attached-cones' in sys.argv
OBTUSE_CONES = '--obtuse-cones' in sys.argv or ATTACHED_CONES
BROAD_CONES = '--broad-cones' in sys.argv or OBTUSE_CONES
SOFT_CONES = '--soft-cones' in sys.argv or BROAD_CONES
REFINED = '--refined' in sys.argv or SOFT_CONES
ANGULAR = '--angular' in sys.argv or REFINED
if ATTACHED_CONES:
    OUT = OUT / 'attached-cones'
elif OBTUSE_CONES:
    OUT = OUT / 'obtuse-cones'
elif BROAD_CONES:
    OUT = OUT / 'broad-cones'
elif SOFT_CONES:
    OUT = OUT / 'soft-cones'
elif REFINED:
    OUT = OUT / 'refined'
elif ANGULAR:
    OUT = OUT / 'angular'
OUT.mkdir(parents=True, exist_ok=True)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = 32
scene.cycles.device = 'CPU'
scene.cycles.use_denoising = False
scene.render.resolution_x = 1200
scene.render.resolution_y = 900
scene.render.resolution_percentage = 100
scene.world.color = (0.18, 0.18, 0.18)


def material(name, color, glass=False):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    bs = m.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value = (*color, 1)
    bs.inputs['Roughness'].default_value = 0.19 if glass else 0.4
    bs.inputs['Transmission Weight'].default_value = 0.65 if glass else 0
    bs.inputs['IOR'].default_value = 1.45
    return m


ink = material('Ivory lettering', (0.88, 0.95, 1))
dark = material('Dark display surface', (0.018, 0.027, 0.045))
tile = material('Smoked glass tile', (0.10, 0.17, 0.23), True)
eye = material('Obsidian eyes', (0.008, 0.015, 0.025))


def sphere(name, pos, scale, mat):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, location=pos)
    o = bpy.context.object
    o.name = name
    o.scale = scale
    o.data.materials.append(mat)
    for p in o.data.polygons:
        p.use_smooth = True
    return o


def cube(name, pos, scale, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=pos)
    o = bpy.context.object
    o.name = name
    o.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    o.data.materials.append(mat)
    mod = o.modifiers.new('Soft edges', 'BEVEL')
    mod.width = 0.09
    mod.segments = 4
    o.modifiers.new('Weighted normals', 'WEIGHTED_NORMAL')
    o.data.use_auto_smooth = True
    return o


def text(value, pos, size):
    bpy.ops.object.text_add(location=pos)
    o = bpy.context.object
    o.name = 'Label ' + value
    o.data.body = value
    o.data.align_x = 'CENTER'
    o.data.size = size
    o.data.extrude = 0.002
    o.data.materials.append(ink)


def horn(pos, radius, depth, mat):
    bpy.ops.mesh.primitive_cone_add(vertices=32, radius1=radius,
                                    radius2=0.025, depth=depth, location=pos)
    bpy.context.object.data.materials.append(mat)


def faceted_body(name, x, y, sections, mat):
    """Loft octagonal cross sections along Y, retaining flat faces."""
    profile = [(-0.65, 1), (0.65, 1), (1, 0.55), (1, -0.55),
               (0.65, -1), (-0.65, -1), (-1, -0.55), (-1, 0.55)]
    vertices = [(x + px * width, y + along, z + pz * height)
                for along, width, z, height in sections for px, pz in profile]
    faces = [tuple(reversed(range(8)))]
    for ring in range(len(sections) - 1):
        for i in range(8):
            a = ring * 8 + i
            b = ring * 8 + (i + 1) % 8
            faces.append((a, b, b + 8, a + 8))
    faces.append(tuple((len(sections) - 1) * 8 + i for i in range(8)))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    # Consistent outward normals are needed for glass refraction.
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    return obj


def tapered_segment(name, start, end, r1, r2, mat):
    delta = Vector(end) - Vector(start)
    bpy.ops.mesh.primitive_cone_add(vertices=5, radius1=r1, radius2=r2,
                                    depth=delta.length,
                                    location=(Vector(start) + Vector(end)) / 2)
    obj = bpy.context.object
    obj.name = name
    obj.rotation_euler = delta.to_track_quat('Z', 'Y').to_euler()
    obj.data.materials.append(mat)


def soft_cone(name, start, end, mat):
    """Short radial cone with a broad, rounded tip rather than a point."""
    delta = Vector(end) - Vector(start)
    bpy.ops.mesh.primitive_cone_add(vertices=32,
                                    radius1=0.34 if BROAD_CONES else 0.25,
                                    radius2=0 if OBTUSE_CONES else 0.19 if BROAD_CONES else 0.075,
                                    depth=delta.length,
                                    location=(Vector(start) + Vector(end)) / 2)
    obj = bpy.context.object
    obj.name = name
    obj.rotation_euler = delta.to_track_quat('Z', 'Y').to_euler()
    if not OBTUSE_CONES:
        bevel = obj.modifiers.new('Rounded cone rim and tip', 'BEVEL')
        bevel.width = 0.085 if BROAD_CONES else 0.055
        bevel.segments = 4
    obj.data.materials.append(mat)
    for face in obj.data.polygons:
        face.use_smooth = len(face.vertices) in (3, 4)
    obj.data.use_auto_smooth = True
    obj.modifiers.new('Cone weighted normals', 'WEIGHTED_NORMAL')


models = [('a', 'AMOEBA', (-2.0, 1.5), (0.20, 0.85, 0.68)),
          ('A', 'RARE AMOEBA', (2.0, 1.5), (0.52, 0.32, 0.92)),
          ('b', 'BISON', (-2.0, -1.5), (0.95, 0.55, 0.20)),
          ('d', 'COMODO DRAGON', (2.0, -1.5), (0.20, 0.63, 0.92))]
for char, name, (x, y), color in models:
    start = set(bpy.data.objects)
    mat = material(name + ' translucent resin', color, True)
    cube(name + ' tile', (x, y, 0), (2.65, 2.15, 0.15), tile)
    if char in ('a', 'A'):
        sphere(name + ' body', (x, y, 0.40), (0.72, 0.65, 0.34), mat)
        for angle in range(0, 360, 60):
            r = math.radians(angle)
            if SOFT_CONES:
                inward = 0.06 if ATTACHED_CONES else 0
                soft_cone(name + ' rounded radial cone',
                          (x + ((0.70 if OBTUSE_CONES else 0.52) - inward) * math.cos(r),
                           y + ((0.64 if OBTUSE_CONES else 0.46) - inward) * math.sin(r), 0.32),
                          (x + ((0.95 if OBTUSE_CONES else 0.87 if BROAD_CONES else 0.98) - inward) * math.cos(r),
                           y + ((0.89 if OBTUSE_CONES else 0.79 if BROAD_CONES else 0.90) - inward) * math.sin(r), 0.32), mat)
            else:
                sphere(name + ' lobe', (x + 0.56 * math.cos(r), y + 0.48 * math.sin(r), 0.30),
                       (0.30, 0.29, 0.22), mat)
        sphere(name + ' nucleus', (x, y, 0.40), (0.25, 0.25, 0.20), ink)
        if char == 'A':
            for dx in (-0.28, 0, 0.28):
                horn((x + dx, y + 0.27, 0.76), 0.12, 0.32, mat)
    elif char == 'b' and ANGULAR:
        torso = faceted_body('Bison broad shoulders and tapered rump', x, y,
                     [(-0.35, 0.56, 0.58, 0.35), (-0.05, 0.59, 0.63, 0.39),
                      (0.48, 0.40, 0.49, 0.27), (0.70, 0.29, 0.42, 0.21)], mat)
        if REFINED:
            bevel = torso.modifiers.new('Gently rounded body edges', 'BEVEL')
            bevel.width = 0.15
            bevel.segments = 5
            bevel.use_clamp_overlap = True
            torso.modifiers.new('Body weighted normals', 'WEIGHTED_NORMAL')
            torso.data.use_auto_smooth = True
        faceted_body('Bison angular head', x, y,
                     [(-0.83, 0.30, 0.40, 0.18), (-0.55, 0.46, 0.52, 0.29),
                      (-0.31, 0.37, 0.54, 0.23)], mat)
        for side in (-1, 1):
            base = (x + side * 0.37, y - 0.49, 0.63)
            bend = (x + side * 0.70, y - 0.46, 0.70)
            tip = (x + side * 0.75, y - 0.25, 0.89)
            tapered_segment('Bison horn base', base, bend, 0.13, 0.085, ink)
            tapered_segment('Bison horn tip', bend, tip, 0.085, 0.008, ink)
            for dy in (-0.27, 0.48):
                hoof = cube('Bison square hoof', (x + side * 0.39, y + dy, 0.19),
                            (0.22, 0.30, 0.26), mat)
                hoof.modifiers['Soft edges'].width = 0.025
                hoof.modifiers['Soft edges'].segments = 1
    elif char == 'd' and ANGULAR:
        faceted_body('Dragon angular torso', x, y,
                     [(-0.51, 0.20, 0.33, 0.16), (-0.22, 0.35, 0.39, 0.24),
                      (0.35, 0.29, 0.36, 0.20), (0.58, 0.16, 0.29, 0.13)], mat)
        faceted_body('Dragon wedge snout', x, y,
                     [(-0.96, 0.15, 0.25, 0.09), (-0.70, 0.27, 0.32, 0.17),
                      (-0.47, 0.20, 0.33, 0.15)], mat)
        faceted_body('Dragon tapered tail', x, y,
                     [(0.45, 0.17, 0.27, 0.12), (0.82, 0.11, 0.21, 0.08),
                      (1.07, 0.02, 0.15, 0.02)], mat)
        for side in (-1, 1):
            for dy in (-0.28, 0.32):
                hip = (x + side * 0.24, y + dy, 0.30)
                if REFINED:
                    foot = (x + side * 0.65, y + dy - 0.06, 0.17)
                    tapered_segment('Dragon simple leg', hip, foot, 0.16, 0.11, mat)
                    continue
                elbow = (x + side * 0.62, y + dy + 0.14, 0.19)
                foot = (x + side * 0.70, y + dy - 0.12, 0.15)
                tapered_segment('Dragon upper leg', hip, elbow, 0.15, 0.12, mat)
                tapered_segment('Dragon lower leg', elbow, foot, 0.12, 0.08, mat)
                for offset in (-0.07, 0, 0.07):
                    tapered_segment('Dragon claw',
                                    (foot[0] + offset, foot[1], foot[2]),
                                    (foot[0] + offset, foot[1] - 0.17, 0.12),
                                    0.035, 0.004, ink)
        for dy in (() if REFINED else (-0.10, 0.16, 0.40)):
            tapered_segment('Dragon crystal ridge', (x, y + dy, 0.53),
                            (x, y + dy + 0.07, 0.71), 0.09, 0, mat)
    elif char == 'b':
        sphere('Bison torso', (x, y + 0.13, 0.51), (0.56, 0.68, 0.38), mat)
        sphere('Bison head', (x, y - 0.49, 0.50), (0.49, 0.35, 0.29), mat)
        for dx in (-0.52, 0.52):
            horn((x + dx, y - 0.43, 0.61), 0.13, 0.40, ink)
        for dx in (-0.30, 0.30):
            for dy in (-0.30, 0.44):
                sphere('Bison hoof', (x + dx, y + dy, 0.20), (0.16, 0.20, 0.16), mat)
    else:
        sphere('Dragon body', (x, y, 0.38), (0.35, 0.66, 0.23), mat)
        sphere('Dragon head', (x, y - 0.68, 0.36), (0.28, 0.34, 0.19), mat)
        tail = sphere('Dragon tail', (x + 0.14, y + 0.71, 0.26), (0.16, 0.55, 0.12), mat)
        tail.rotation_euler.z = -0.30
        for dx in (-0.45, 0.45):
            for dy in (-0.35, 0.35):
                sphere('Dragon foot', (x + dx, y + dy, 0.21), (0.29, 0.17, 0.12), mat)
        for dy in (-0.1, 0.18, 0.46):
            horn((x, y + dy, 0.60), 0.08, 0.17, mat)
    if char in ('b', 'd'):
        for dx in (-0.15, 0.15):
            sphere(name + ' eye', (x + dx, y - 0.65, 0.64 if char == 'b' else 0.49),
                   (0.065, 0.07, 0.045), eye)
    # Identification is a separate overlay, not baked into a creature mesh.
    text(char, (x + 1.02, y + 0.70, 0.10), 0.32)
    text(name, (x, y - 1.30, 0.03), 0.18)
    collection = bpy.data.collections.new('Prototype ' + char + ' ' + name)
    scene.collection.children.link(collection)
    for obj in set(bpy.data.objects) - start:
        for old in list(obj.users_collection):
            old.objects.unlink(obj)
        collection.objects.link(obj)

cube('Backdrop', (0, 0, -0.18), (200, 200, 0.1), dark)
text('ARLQ / STAGE 1 / TRANSLUCENT RESIN STUDIES', (0, 3.12, 0.03), 0.20)
for pos, power, size in [((-3, -4, 7), 1400, 5), ((4, 2, 5), 1100, 4)]:
    bpy.ops.object.light_add(type='AREA', location=pos)
    light = bpy.context.object
    light.data.energy = power
    light.data.shape = 'DISK'
    light.data.size = size
    light.rotation_euler = (Vector((0, 0, 0)) - light.location).to_track_quat('-Z', 'Y').to_euler()
bpy.ops.object.camera_add(location=(0, -5.5, 14))
camera = bpy.context.object
camera.rotation_euler = (Vector((0, 0, 0)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
camera.data.type = 'ORTHO'
camera.data.ortho_scale = 9.7
scene.camera = camera
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'stage1-characters.blend'))
scene.render.filepath = str(OUT / 'preview-overhead.png')
bpy.ops.render.render(write_still=True)
camera.location = (0, 0, 15)
camera.rotation_euler = (0, 0, 0)
scene.render.filepath = str(OUT / 'preview-top.png')
bpy.ops.render.render(write_still=True)
