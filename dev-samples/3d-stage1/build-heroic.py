"""Refined, more dramatic versions of the five accepted characters.

Run with: blender --background --threads 4 --python dev-samples/3d-stage1/build-heroic.py

Keeps the accepted silhouettes (attached obtuse cones, angular bison and
dragon, two-head-tall legless player with a cloak) and adds glowing cores,
rim light, sharper features and stronger poses.
"""
from pathlib import Path
import math
import sys

import bpy
from mathutils import Vector

OUT = Path(__file__).resolve().parent / 'heroic'
OUT.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 96
scene.cycles.use_denoising = False
scene.cycles.sample_clamp_indirect = 2.0
scene.cycles.blur_glossy = 1.0
scene.cycles.caustics_reflective = False
scene.cycles.caustics_refractive = False
scene.render.resolution_x = 1500
scene.render.resolution_y = 700
scene.view_settings.view_transform = 'Standard'
scene.view_settings.look = 'Medium High Contrast'
world = bpy.data.worlds.new('Night studio')
world.use_nodes = True
world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.012, 0.018, 0.03, 1)
scene.world = world

ROW = [('@', 'PLAYER', -4.0), ('a', 'AMOEBA', -2.0), ('A', 'RARE AMOEBA', 0.0),
       ('b', 'BISON', 2.0), ('d', 'COMODO DRAGON', 4.0)]
# Sprite export reads the character centres from here.
CENTERS = {char: (x, 0.0) for char, _, x in ROW}


def material(name, color, transmission=0.0, roughness=0.35, emission=None,
             strength=0.0, rim=None, rim_strength=0.0, metallic=0.0, coat=0.0):
    """Principled material, optionally mixed with a Fresnel-driven glowing rim."""
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (*color, 1)
    bsdf.inputs['Transmission Weight'].default_value = transmission
    bsdf.inputs['Roughness'].default_value = roughness
    bsdf.inputs['Metallic'].default_value = metallic
    bsdf.inputs['Coat Weight'].default_value = coat
    bsdf.inputs['IOR'].default_value = 1.45
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


def finish(obj, mat, smooth=True, name=None):
    if name:
        obj.name = name
    obj.data.materials.append(mat)
    for face in obj.data.polygons:
        face.use_smooth = smooth
    return obj


def recalc_normals(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')


def mesh_object(name, vertices, faces, mat, smooth):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    recalc_normals(obj)
    return finish(obj, mat, smooth)


def sphere(name, pos, scale, mat, segments=40, smooth=True):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=segments // 2,
                                         location=pos)
    obj = bpy.context.object
    obj.scale = scale
    return finish(obj, mat, smooth, name)


def block(name, pos, size, mat, radius, rotation=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=pos, rotation=rotation)
    obj = bpy.context.object
    obj.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    finish(obj, mat, True, name)
    bevel = obj.modifiers.new('Rounded edges', 'BEVEL')
    bevel.width = radius
    bevel.segments = 5
    obj.data.use_auto_smooth = True
    obj.modifiers.new('Weighted normals', 'WEIGHTED_NORMAL')
    return obj


def tube(name, points, radii, mat, sides=8, smooth=False, flat=1.0, twist=0.0):
    """Loft rings along a polyline; radius 0 closes the end to a point.

    `flat` squashes the vertical axis of every ring, giving reptile bodies.
    """
    points = [Vector(p) for p in points]
    vertices, rings = [], []
    for i, (center, radius) in enumerate(zip(points, radii)):
        ahead = points[min(i + 1, len(points) - 1)] - points[max(i - 1, 0)]
        ahead.normalize()
        up = Vector((0, 0, 1)) if abs(ahead.z) < 0.9 else Vector((0, 1, 0))
        side = ahead.cross(up).normalized()
        up = side.cross(ahead).normalized()
        if radius == 0:
            rings.append([len(vertices)])
            vertices.append(tuple(center))
            continue
        ring = []
        for k in range(sides):
            a = 2 * math.pi * k / sides + twist
            rx, rz = (radius, radius * flat) if isinstance(radius, (int, float)) else radius
            ring.append(len(vertices))
            vertices.append(tuple(center + side * (rx * math.cos(a)) + up * (rz * math.sin(a))))
        rings.append(ring)
    faces = []
    if len(rings[0]) > 1:
        faces.append(tuple(reversed(rings[0])))
    for a, b in zip(rings, rings[1:]):
        if len(a) == 1:
            faces += [(a[0], b[(k + 1) % sides], b[k]) for k in range(sides)]
        elif len(b) == 1:
            faces += [(a[k], a[(k + 1) % sides], b[0]) for k in range(sides)]
        else:
            faces += [(a[k], a[(k + 1) % sides], b[(k + 1) % sides], b[k])
                      for k in range(sides)]
    if len(rings[-1]) > 1:
        faces.append(tuple(rings[-1]))
    return mesh_object(name, vertices, faces, mat, smooth)


def loft(name, x, y, sections, mat, profile=None):
    """Octagonal sections (along, half width, z, half height) along +Y."""
    profile = profile or [(-0.65, 1), (0.65, 1), (1, 0.55), (1, -0.55),
                          (0.65, -1), (-0.65, -1), (-1, -0.55), (-1, 0.55)]
    n = len(profile)
    vertices = [(x + px * w, y + along, z + pz * h)
                for along, w, z, h in sections for px, pz in profile]
    faces = [tuple(reversed(range(n)))]
    for ring in range(len(sections) - 1):
        faces += [(ring * n + i, ring * n + (i + 1) % n, ring * n + (i + 1) % n + n,
                   ring * n + i + n) for i in range(n)]
    faces.append(tuple((len(sections) - 1) * n + i for i in range(n)))
    return mesh_object(name, vertices, faces, mat, False)


def soften(obj, width, segments=3):
    bevel = obj.modifiers.new('Soft facets', 'BEVEL')
    bevel.width = width
    bevel.segments = segments
    bevel.use_clamp_overlap = True
    bevel.harden_normals = True
    obj.data.use_auto_smooth = True
    return obj


def cone(name, start, end, r1, r2, mat, vertices=32, smooth=True):
    delta = Vector(end) - Vector(start)
    bpy.ops.mesh.primitive_cone_add(vertices=vertices, radius1=r1, radius2=r2,
                                    depth=delta.length,
                                    location=(Vector(start) + Vector(end)) / 2)
    obj = bpy.context.object
    obj.rotation_euler = delta.to_track_quat('Z', 'Y').to_euler()
    finish(obj, mat, False, name)
    if smooth:
        for face in obj.data.polygons:
            face.use_smooth = len(face.vertices) in (3, 4)
    return obj


ink = material('Ivory lettering', (0.85, 0.92, 1.0))
dark = material('Night floor', (0.006, 0.008, 0.014), roughness=0.8)
tile = material('Smoked glass tile', (0.06, 0.10, 0.15), 0.5, 0.22,
                rim=(0.25, 0.55, 0.9), rim_strength=0.6)
obsidian = material('Obsidian', (0.01, 0.012, 0.018), roughness=0.18, coat=1.0)


def amoeba(x, y, rare):
    if rare:
        shell = material('Rare amoeba tangerine resin', (1.0, 0.42, 0.04), 0.6, 0.14,
                         rim=(1.0, 0.8, 0.4), rim_strength=1.5, coat=0.6)
        cone_mat = material('Rare amoeba deep orange cones', (0.80, 0.24, 0.02), 0.55, 0.16,
                            rim=(1.0, 0.75, 0.35), rim_strength=1.2, coat=0.8)
        core = (1.0, 0.88, 0.25)
    else:
        shell = material('Amoeba sky blue resin', (0.08, 0.55, 0.98), 0.6, 0.14,
                         rim=(0.55, 0.9, 1.0), rim_strength=1.5, coat=0.6)
        cone_mat = material('Amoeba deep blue cones', (0.03, 0.30, 0.80), 0.55, 0.16,
                            rim=(0.5, 0.85, 1.0), rim_strength=1.2, coat=0.8)
        core = (0.55, 1.0, 0.95)
    body = sphere('Membrane', (x, y, 0.40), (0.72, 0.65, 0.36), shell, 64)
    wobble = body.modifiers.new('Organic wobble', 'DISPLACE')
    texture = bpy.data.textures.new('Membrane wobble', 'CLOUDS')
    texture.noise_scale = 0.55
    wobble.texture = texture
    wobble.strength = 0.05
    wobble.mid_level = 0.5
    # Accepted obtuse cones (r 0.34, depth 0.25), pulled 0.06 into the body.
    for angle in range(0, 360, 60):
        r = math.radians(angle)
        cone('Radial cone', (x + 0.64 * math.cos(r), y + 0.58 * math.sin(r), 0.32),
             (x + 0.89 * math.cos(r), y + 0.83 * math.sin(r), 0.32), 0.34, 0, cone_mat)
    # A glowing eye-like nucleus visible through the shell.
    glow = material('Nucleus glow', core, emission=core, strength=5.0)
    sphere('Nucleus', (x, y - 0.12, 0.47), (0.24, 0.22, 0.18), glow)
    sphere('Nucleus slit pupil', (x, y - 0.25, 0.56), (0.045, 0.05, 0.13), obsidian)
    vacuole = material('Vacuole', (1, 1, 1), 0.3, 0.1,
                       emission=core, strength=1.5)
    for dx, dy, s in ((-0.36, 0.18, 0.08), (0.33, 0.24, 0.065), (0.12, 0.34, 0.05)):
        sphere('Vacuole', (x + dx, y + dy, 0.52), (s, s, s * 0.8), vacuole, 24)
    if rare:
        crystal = material('Rare crown crystal', (1.0, 0.92, 0.65), 0.6, 0.05,
                           emission=(1.0, 0.65, 0.1), strength=2.0,
                           rim=(1.0, 0.85, 0.5), rim_strength=4.0)
        for dx, tilt, h in ((-0.30, -0.12, 0.40), (0, 0, 0.52), (0.30, 0.12, 0.40)):
            base = Vector((x + dx, y + 0.24, 0.62))
            cone('Crown crystal', base, base + Vector((tilt, 0.06, h)),
                 0.12, 0, crystal, vertices=6, smooth=False)


def bison(x, y):
    hide = material('Bison amber resin', (0.90, 0.38, 0.08), 0.5, 0.22,
                    rim=(1.0, 0.7, 0.35), rim_strength=1.2, coat=0.5)
    mane = material('Bison smouldering mane', (0.16, 0.05, 0.02), 0.1, 0.5,
                    rim=(1.0, 0.4, 0.1), rim_strength=1.5)
    horn = material('Bison ivory horn', (0.95, 0.92, 0.82), 0.2, 0.15, coat=1.0,
                    rim=(1.0, 0.95, 0.8), rim_strength=1.5)
    eye = material('Bison ember eyes', (1.0, 0.2, 0.05), emission=(1.0, 0.25, 0.05),
                   strength=25.0)
    # Massive shoulder hump, tapering rump; head lowered for a charge.
    soften(loft('Bison torso', x, y,
                [(-0.42, 0.50, 0.50, 0.32), (-0.18, 0.60, 0.62, 0.42),
                 (0.10, 0.55, 0.58, 0.36), (0.45, 0.42, 0.47, 0.27),
                 (0.70, 0.30, 0.42, 0.20)], hide), 0.09)
    # Shaggy hump: overlapping low-poly clumps over the shoulders and brow.
    clumps = [(0, -0.30, 0.98, 0.34), (-0.26, -0.22, 0.92, 0.28), (0.26, -0.22, 0.92, 0.28),
              (0, -0.02, 0.96, 0.30), (-0.30, 0.04, 0.84, 0.24), (0.30, 0.04, 0.84, 0.24),
              (0, -0.55, 0.80, 0.28), (-0.24, -0.50, 0.76, 0.22), (0.24, -0.50, 0.76, 0.22),
              (-0.42, -0.34, 0.70, 0.20), (0.42, -0.34, 0.70, 0.20), (0, 0.20, 0.86, 0.22)]
    for i, (dx, dy, z, r) in enumerate(clumps):
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=r,
                                              location=(x + dx, y + dy, z),
                                              rotation=(i * 0.7, i * 1.3, i * 0.4))
        clump = finish(bpy.context.object, mane, False, 'Bison mane clump')
        clump.scale = (1.0, 1.1, 0.8)
    soften(loft('Bison lowered head', x, y,
                [(-0.92, 0.28, 0.34, 0.17), (-0.72, 0.40, 0.44, 0.25),
                 (-0.52, 0.40, 0.52, 0.26)], hide), 0.04)
    soften(loft('Bison muzzle', x, y,
                [(-0.98, 0.20, 0.30, 0.10), (-0.86, 0.25, 0.32, 0.13)], obsidian), 0.03)
    for side in (-1, 1):
        # Horns sweep outward, then hook up and forward.
        tube('Bison horn', [(x + side * 0.30, y - 0.66, 0.66), (x + side * 0.56, y - 0.66, 0.68),
                            (x + side * 0.74, y - 0.70, 0.82), (x + side * 0.76, y - 0.80, 1.00),
                            (x + side * 0.66, y - 0.92, 1.12)],
             [0.13, 0.11, 0.08, 0.05, 0], horn, sides=10, smooth=True)
        sphere('Bison eye', (x + side * 0.20, y - 0.86, 0.50), (0.055, 0.04, 0.035), eye, 16)
        for dy in (-0.32, 0.50):
            block('Bison hoof', (x + side * 0.40, y + dy, 0.13), (0.22, 0.28, 0.24),
                  obsidian, 0.04)
    tube('Bison tail', [(x, y + 0.66, 0.55), (x + 0.06, y + 0.80, 0.48), (x + 0.10, y + 0.86, 0.30)],
         [0.05, 0.04, 0.07], mane, sides=6)


def dragon(x, y):
    scales = material('Dragon cobalt scales', (0.05, 0.36, 0.92), 0.45, 0.2,
                      rim=(0.4, 0.85, 1.0), rim_strength=1.5, coat=0.7)
    belly = material('Dragon pale crest', (0.70, 0.92, 1.0), 0.4, 0.15,
                     rim=(0.7, 1.0, 1.0), rim_strength=1.0)
    eye = material('Dragon gold eyes', (1.0, 0.8, 0.1), emission=(1.0, 0.75, 0.1),
                   strength=25.0)
    # One continuous faceted body, snout to a sinuous tail.
    spine = [(0.00, -1.00, 0.26), (0.00, -0.86, 0.30), (0.00, -0.68, 0.34), (0.02, -0.50, 0.33),
             (0.03, -0.28, 0.36), (0.01, 0.02, 0.37), (-0.05, 0.30, 0.33), (-0.15, 0.55, 0.27),
             (-0.14, 0.78, 0.21), (0.04, 0.96, 0.16), (0.26, 1.04, 0.12), (0.40, 1.04, 0.10)]
    radii = [(0.08, 0.05), (0.17, 0.10), (0.22, 0.14), (0.17, 0.12), (0.31, 0.19), (0.34, 0.21),
             (0.27, 0.17), (0.17, 0.12), (0.11, 0.08), (0.07, 0.05), (0.035, 0.03), 0]
    tube('Dragon body', [(x + px, y + py, pz) for px, py, pz in spine], radii, scales,
         sides=8, twist=math.pi / 8)
    for side in (-1, 1):
        # Brow ridge over each glowing eye gives a scowl.
        cone('Dragon brow', (x + side * 0.08, y - 0.78, 0.45),
             (x + side * 0.24, y - 0.62, 0.50), 0.05, 0, belly, 5, False)
        sphere('Dragon eye', (x + side * 0.15, y - 0.76, 0.42), (0.05, 0.045, 0.035), eye, 16)
        for dy, back in ((-0.24, -0.16), (0.24, 0.12)):
            hip = (x + side * 0.22, y + dy, 0.34)
            knee = (x + side * 0.55, y + dy + back * 0.3, 0.36)
            foot = (x + side * 0.66, y + dy + back, 0.08)
            tube('Dragon splayed leg', [hip, knee, foot], [0.12, 0.09, 0.07], scales, sides=6)
            sphere('Dragon foot', foot, (0.10, 0.12, 0.05), scales, 12, False)
    # A low crest along the spine, kept as a single smooth fin.
    crest = [(x + px, y + py, pz + rz) for (px, py, pz), r in zip(spine[3:9], radii[3:9])
             for rz in [r[1] + 0.02]]
    tube('Dragon dorsal crest', crest, [(0.025, 0.05)] * len(crest), belly, sides=4)


def player(x, y):
    tunic = material('Player frost tunic', (0.72, 0.88, 0.98), 0.45, 0.2,
                     rim=(0.6, 0.9, 1.0), rim_strength=1.0, coat=0.6)
    helm = material('Player crystal helm', (0.88, 0.95, 1.0), 0.35, 0.12,
                    rim=(0.7, 0.95, 1.0), rim_strength=1.2, coat=1.0)
    cape = material('Player crimson cloak', (0.65, 0.04, 0.08), 0.15, 0.4,
                    rim=(1.0, 0.2, 0.1), rim_strength=0.6)
    gold = material('Player gold trim', (0.85, 0.55, 0.18), roughness=0.3, metallic=1.0)
    visor = material('Player visor glow', (0.3, 0.9, 1.0), emission=(0.1, 0.75, 1.0),
                     strength=2.5)
    blade = material('Player rune blade', (0.75, 0.95, 1.0), 0.3, 0.05,
                     emission=(0.15, 0.7, 1.0), strength=1.2, metallic=0.4)
    bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=0.27, depth=0.40,
                                        location=(x, y, 0.30))
    torso = finish(bpy.context.object, tunic, True, 'Player cylinder torso')
    for face in torso.data.polygons:
        face.use_smooth = len(face.vertices) == 4
    torso.data.use_auto_smooth = True
    bevel = torso.modifiers.new('Rounded rims', 'BEVEL')
    bevel.width = 0.065
    bevel.segments = 5
    bpy.ops.mesh.primitive_torus_add(major_radius=0.275, minor_radius=0.03,
                                     location=(x, y, 0.24))
    finish(bpy.context.object, gold, True, 'Player belt')
    block('Player buckle', (x, y - 0.29, 0.24), (0.09, 0.03, 0.07), gold, 0.012)
    block('Player head', (x, y - 0.07, 0.67), (0.38, 0.36, 0.36), helm, 0.11)
    block('Player visor', (x, y - 0.25, 0.63), (0.30, 0.05, 0.08), visor, 0.015)
    for side in (-1, 1):
        cone('Player helm fin', (x + side * 0.17, y - 0.02, 0.74),
             (x + side * 0.30, y + 0.10, 0.92), 0.06, 0, gold, 4, False)
        arm = block('Player short arm', (x + side * 0.285, y - 0.075, 0.32),
                    (0.16, 0.18, 0.28), tunic, 0.065)
        arm.rotation_euler.y = -side * 0.12
        sphere('Player pauldron', (x + side * 0.27, y - 0.06, 0.46), (0.09, 0.10, 0.045), gold, 24)
    # Short sword in the right hand (screen left), held low and outward.
    hand = Vector((x - 0.33, y - 0.16, 0.20))
    tip = hand + Vector((-0.34, -0.30, -0.10))
    tube('Player sword blade', [hand + (tip - hand) * 0.12, tip * 0.94 + hand * 0.06, tip],
         [(0.075, 0.016), (0.06, 0.014), 0], blade, sides=4)
    tube('Player sword guard', [hand + Vector((0.07, -0.08, 0)), hand + Vector((-0.08, 0.06, 0))],
         [0.025, 0.025], gold, sides=6)
    # Cloak: hugs the shoulders, drifts back and sideways toward the hem.
    columns, rows = 25, 8
    vertices = []
    for row in range(rows):
        t = row / (rows - 1)
        for col in range(columns):
            u = col / (columns - 1) * 2 - 1
            angle = u * math.radians(95)
            radius = 0.29 + 0.16 * t
            vertices.append((x + radius * math.sin(angle) + 0.07 * t * t,
                             y + radius * math.cos(angle) + 0.30 * t * t,
                             0.50 - 0.36 * t + 0.045 * t * math.cos(u * math.pi * 3)))
    faces = [(r * columns + c, r * columns + c + 1, (r + 1) * columns + c + 1, (r + 1) * columns + c)
             for r in range(rows - 1) for c in range(columns - 1)]
    cloak = mesh_object('Player cloak', vertices, faces, cape, True)
    cloak.modifiers.new('Smooth drape', 'SUBSURF').levels = 2
    solid = cloak.modifiers.new('Fabric thickness', 'SOLIDIFY')
    solid.thickness = 0.03
    solid.offset = 0
    hem = [vertices[(rows - 1) * columns + c] for c in range(columns)]
    tube('Player cloak hem trim', hem, [0.018] * columns, gold, sides=6, smooth=True)
    bpy.ops.object.text_add(location=(x, y - 0.07, 0.855))
    mark = bpy.context.object
    mark.name = 'Overlay @'
    mark.data.body = '@'
    mark.data.align_x = mark.data.align_y = 'CENTER'
    mark.data.size = 0.23
    mark.data.extrude = 0.002
    mark.data.materials.append(obsidian)


def label(value, pos, size):
    bpy.ops.object.text_add(location=pos)
    obj = bpy.context.object
    obj.name = 'Label ' + value
    obj.data.body = value
    obj.data.align_x = 'CENTER'
    obj.data.size = size
    obj.data.extrude = 0.002
    obj.data.materials.append(ink)


builders = {'@': player, 'a': lambda x, y: amoeba(x, y, False),
            'A': lambda x, y: amoeba(x, y, True), 'b': bison, 'd': dragon}
for char, name, x in ROW:
    start = set(bpy.data.objects)
    builders[char](x, 0.0)
    character = set(bpy.data.objects) - start
    block(name + ' tile', (x, 0, -0.05), (1.85, 2.45, 0.1), tile, 0.04)
    label(name, (x, -1.55, 0.0), 0.16)
    collection = bpy.data.collections.new('Character ' + char + ' ' + name)
    scene.collection.children.link(collection)
    for obj in set(bpy.data.objects) - start:
        for old in list(obj.users_collection):
            old.objects.unlink(obj)
        collection.objects.link(obj)
        obj['sprite'] = obj in character

bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, -0.1))
finish(bpy.context.object, dark, True, 'Backdrop')
label('ARLQ / STAGE 1 / HEROIC RESIN', (0, 1.75, 0.0), 0.2)
# Warm key, cool fill, strong back rim lights for glossy edges.
for name, pos, power, size, color in [
        ('Key', (-4, -6, 8), 1000, 5, (1.0, 0.93, 0.85)),
        ('Fill', (6, -3, 4), 250, 6, (0.6, 0.75, 1.0)),
        ('Rim left', (-5, 6, 4), 1300, 3, (0.55, 0.8, 1.0)),
        ('Rim right', (5, 6, 4), 1300, 3, (1.0, 0.7, 0.9))]:
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
angle = math.radians(60)
camera.location = (0, -15 * math.cos(angle), 15 * math.sin(angle))
camera.rotation_euler = (Vector((0, 0, 0)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
camera.data.type = 'ORTHO'
camera.data.ortho_scale = 11
scene.camera = camera
scene['sprite_centers'] = {char: list(pos) for char, pos in CENTERS.items()}
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'characters-angle60.blend'))
if '--save-only' not in sys.argv:
    scene.render.filepath = str(OUT / 'preview-angle60.png')
    bpy.ops.render.render(write_still=True)
