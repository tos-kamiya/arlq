"""Refined, more dramatic versions of the Stage 1-2 characters, companions and marks.

Run with: blender --background --threads 4 --python dev-samples/3d-stage1/build-heroic.py

Keeps the accepted silhouettes (attached obtuse cones, angular bison and
dragon, two-head-tall legless player with a cloak) and adds glowing cores,
rim light, sharper features and stronger poses.
"""
from pathlib import Path
import math
import sys

import bpy
from mathutils import Matrix, Vector

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
scene.render.resolution_x = 2900
scene.render.resolution_y = 1250
scene.view_settings.view_transform = 'Standard'
scene.view_settings.look = 'Medium High Contrast'
world = bpy.data.worlds.new('Night studio')
world.use_nodes = True
world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.012, 0.018, 0.03, 1)
scene.world = world

# Stage 1 characters and companions in the back row, Stage 2 additions in front.
STAGE2_ROW_Y = -4.4
ROW = [('@', 'PLAYER', -8.0, 0.0), ('a', 'AMOEBA', -6.0, 0.0), ('A', 'RARE AMOEBA', -4.0, 0.0),
       ('b', 'BISON', -2.0, 0.0), ('c', 'CHIMERA', 0.0, 0.0), ('d', 'COMODO DRAGON', 2.0, 0.0),
       ('T', 'TREASURE CHEST', 4.0, 0.0), ('D', 'DRAGON', 6.7, 0.0), ('n', 'NOMICON', 9.2, 0.0),
       ('o', 'OCULAR', 11.2, 0.0),
       ('C', 'RARE CHIMERA', -6.0, STAGE2_ROW_Y), ('F', 'FIRE DRAKE', -3.2, STAGE2_ROW_Y),
       ("'", 'RANK 2 MARK', -0.6, STAGE2_ROW_Y), ('"', 'RANK 3 MARK', 1.2, STAGE2_ROW_Y)]
# Sprite export reads the character centres from here.
CENTERS = {char: (x, y) for char, _, x, y in ROW}
# Model sizes relative to the amoeba, baked into the meshes. Sprites are exported
# and drawn at one common scale, so these decide how large each character
# appears; the boss dragon is built large, its wings spreading past its cell.
SIZES = {'@': 1.42, 'a': 1.0, 'A': 1.0, 'b': 1.09, 'c': 1.2, 'd': 1.16, 'T': 1.66, 'D': 1.44,
         'n': 1.15, 'o': 1.25, 'C': 1.28, 'F': 1.52, "'": 1.7, '"': 1.7}
# Monsters turn slightly toward screen left; the player, chest and companions face front.
MONSTER_YAW = math.radians(-30)


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


def chimera(x, y, cursed=False):
    if cursed:
        # Rare chimera with the cursed sword: ash-grey lion, black mane with
        # ember edges, bone-white serpent, and a black blade glowing red.
        hide = material('Rare chimera ash resin', (0.30, 0.32, 0.38), 0.45, 0.24,
                        rim=(0.75, 0.80, 0.95), rim_strength=1.2, coat=0.6)
        mane = material('Rare chimera black mane', (0.03, 0.02, 0.03), 0.1, 0.4,
                        rim=(1.0, 0.18, 0.05), rim_strength=2.2)
        snake = material('Rare chimera bone serpent', (0.92, 0.88, 0.78), 0.35, 0.2,
                         rim=(1.0, 0.95, 0.85), rim_strength=1.2, coat=0.8)
        snake_eye = material('Rare chimera snake eyes', (1.0, 0.1, 0.05),
                             emission=(1.0, 0.1, 0.05), strength=8.0)
        steel = material('Cursed sword black steel', (0.04, 0.03, 0.04), 0.0, 0.15,
                         emission=(0.9, 0.05, 0.02), strength=0.6, metallic=0.6,
                         rim=(1.0, 0.15, 0.05), rim_strength=4.0)
        hilt = material('Cursed sword iron hilt', (0.25, 0.22, 0.24), roughness=0.3,
                        metallic=1.0)
    else:
        hide = material('Chimera golden lion resin', (0.95, 0.66, 0.18), 0.5, 0.22,
                        rim=(1.0, 0.85, 0.45), rim_strength=1.2, coat=0.6)
        mane = material('Chimera crimson mane', (0.62, 0.05, 0.04), 0.15, 0.4,
                        rim=(1.0, 0.25, 0.1), rim_strength=1.5)
        snake = material('Chimera serpent tail', (0.04, 0.80, 0.40), 0.4, 0.16,
                         emission=(0.05, 0.6, 0.3), strength=0.3,
                         rim=(0.6, 1.0, 0.6), rim_strength=1.8, coat=0.8)
        snake_eye = material('Chimera snake eyes', (1.0, 0.9, 0.1), emission=(1.0, 0.85, 0.1),
                             strength=6.0)
        steel = material('Chimera sword steel', (0.85, 0.92, 1.0), 0.3, 0.08,
                         emission=(0.7, 0.85, 1.0), strength=0.8, metallic=0.5,
                         rim=(0.9, 0.95, 1.0), rim_strength=1.5)
        hilt = material('Chimera sword hilt', (1.0, 0.68, 0.18), roughness=0.25, metallic=1.0)
    tongue = material('Chimera snake tongue', (1.0, 0.1, 0.15), emission=(1.0, 0.1, 0.15),
                      strength=2.0)
    eye = material('Chimera ember eyes', (1.0, 0.3, 0.05), emission=(1.0, 0.3, 0.05),
                   strength=6.0)
    # Lion: small body, maned head, sword carried crosswise in the jaws.
    soften(loft('Chimera lion torso', x, y,
                [(-0.40, 0.26, 0.42, 0.17), (-0.16, 0.28, 0.43, 0.18),
                 (0.14, 0.23, 0.40, 0.15), (0.32, 0.17, 0.37, 0.12)], hide), 0.05)
    soften(loft('Chimera lion head', x, y,
                [(-0.92, 0.14, 0.50, 0.09), (-0.80, 0.22, 0.56, 0.14),
                 (-0.56, 0.25, 0.62, 0.18)], hide), 0.04)
    sphere('Chimera nose', (x, y - 0.93, 0.55), (0.06, 0.04, 0.04), obsidian, 12)
    # Full mane: two rings of clumps framing the face.
    for ring, (dy, radius, size) in enumerate(((-0.52, 0.34, 0.15), (-0.40, 0.30, 0.17))):
        for i in range(12):
            a = math.pi * (-0.15 + 1.3 * i / 11)
            bpy.ops.mesh.primitive_ico_sphere_add(
                subdivisions=1, radius=size,
                location=(x + radius * math.cos(a), y + dy, 0.60 + radius * math.sin(a)),
                rotation=(i * 0.9, i * 0.5 + ring, 0))
            finish(bpy.context.object, mane, False, 'Chimera mane clump')
    # Flat blade so its broad face shows from above.
    tube('Chimera sword blade', [(x - 0.20, y - 0.88, 0.50), (x - 0.64, y - 0.88, 0.50),
                                 (x - 0.76, y - 0.88, 0.50)],
         [(0.07, 0.014), (0.06, 0.012), 0], steel, sides=4)
    tube('Chimera sword guard', [(x - 0.18, y - 0.88, 0.40), (x - 0.18, y - 0.88, 0.62)],
         [0.03, 0.03], hilt, sides=6)
    tube('Chimera sword grip', [(x - 0.17, y - 0.88, 0.50), (x + 0.20, y - 0.88, 0.50)],
         [0.025, 0.025], hilt, sides=6)
    sphere('Chimera sword pommel', (x + 0.23, y - 0.88, 0.50), (0.045, 0.045, 0.045), hilt, 12)
    for side in (-1, 1):
        sphere('Chimera lion eye', (x + side * 0.11, y - 0.82, 0.66), (0.04, 0.03, 0.03), eye, 12)
        for dy in (-0.28, 0.22):
            foot = (x + side * 0.23, y + dy - 0.05, 0.06)
            tube('Chimera leg', [(x + side * 0.18, y + dy, 0.36), foot], [0.09, 0.07], hide, sides=6)
            sphere('Chimera paw', foot, (0.08, 0.09, 0.045), hide, 12, False)
    # Thick serpent tail rearing over the back, hooded head facing forward.
    tube('Chimera serpent tail', [(x, y + 0.30, 0.40), (x + 0.06, y + 0.56, 0.40),
                                  (x - 0.06, y + 0.80, 0.52), (x - 0.28, y + 0.84, 0.76),
                                  (x - 0.38, y + 0.66, 0.98), (x - 0.32, y + 0.46, 1.08)],
         [0.09, 0.10, 0.11, 0.11, 0.10, 0.10], snake, sides=8, smooth=True)
    sphere('Chimera snake hood', (x - 0.32, y + 0.46, 1.08), (0.22, 0.06, 0.17), snake, 24)
    tube('Chimera snake head', [(x - 0.32, y + 0.42, 1.10), (x - 0.29, y + 0.24, 1.10),
                                (x - 0.27, y + 0.10, 1.06)],
         [(0.15, 0.08), (0.12, 0.07), 0], snake, sides=8)
    tube('Chimera snake tongue', [(x - 0.27, y + 0.12, 1.05), (x - 0.26, y - 0.02, 1.02)],
         [0.014, 0.01], tongue, sides=4)
    for side in (-1, 1):
        sphere('Chimera snake eye', (x - 0.29 + side * 0.08, y + 0.26, 1.16),
               (0.035, 0.035, 0.03), snake_eye, 12)


def treasure(x, y):
    wood = material('Chest mahogany resin', (0.40, 0.09, 0.03), 0.12, 0.28,
                    rim=(1.0, 0.55, 0.25), rim_strength=0.8, coat=0.8)
    gold = material('Chest gold bands', (1.0, 0.68, 0.18), roughness=0.22, metallic=1.0)
    light = material('Chest treasure glow', (1.0, 0.8, 0.3), emission=(1.0, 0.72, 0.2),
                     strength=3.0)
    gem = material('Chest ruby', (1.0, 0.08, 0.12), 0.8, 0.02,
                   emission=(1.0, 0.1, 0.1), strength=1.5, coat=1.0)
    block('Chest box', (x, y, 0.27), (1.0, 0.66, 0.46), wood, 0.05)
    # Gold glow inside the unlocked chest, with a few coins on the pile.
    block('Chest treasure glow', (x, y, 0.47), (0.86, 0.54, 0.06), light, 0.02)
    for i, (dx, dy) in enumerate(((-0.22, -0.08), (0.05, 0.10), (0.24, -0.04), (-0.04, -0.14))):
        bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=0.07, depth=0.02,
                                            location=(x + dx, y + dy, 0.515),
                                            rotation=(0.3 * (i - 1.5), 0.2 * i, 0))
        finish(bpy.context.object, gold, True, 'Chest gold coin')
    # Rounded lid: a cylinder whose lower half sinks into the box, tilted open.
    lid_parts = []
    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=0.33, depth=0.98,
                                        location=(x, y, 0.50), rotation=(0, math.pi / 2, 0))
    lid = finish(bpy.context.object, wood, True, 'Chest rounded lid')
    lid.scale = (1, 1.0, 0.75)
    bevel = lid.modifiers.new('Soft lid rims', 'BEVEL')
    bevel.width = 0.03
    bevel.segments = 3
    lid_parts.append(lid)
    for dx in (-0.36, 0.36):
        bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=0.345, depth=0.09,
                                            location=(x + dx, y, 0.50),
                                            rotation=(0, math.pi / 2, 0))
        band = finish(bpy.context.object, gold, True, 'Chest lid band')
        band.scale = (1, 1.0, 0.75)
        lid_parts.append(band)
        block('Chest box band', (x + dx, y, 0.27), (0.09, 0.68, 0.47), gold, 0.015)
    bpy.context.view_layer.update()
    hinge = Matrix.Translation((x, y + 0.33, 0.50))
    opening = hinge @ Matrix.Rotation(-1.15, 4, 'X') @ hinge.inverted()
    for part in lid_parts:
        part.matrix_world = opening @ part.matrix_world
    block('Chest lock plate', (x, y - 0.34, 0.42), (0.20, 0.03, 0.24), gold, 0.03)
    sphere('Chest ruby', (x, y - 0.365, 0.44), (0.065, 0.035, 0.075), gem, 16, False)
    for dx in (-0.48, 0.48):
        for dy in (-0.31, 0.31):
            block('Chest corner cap', (x + dx, y + dy, 0.27), (0.08, 0.08, 0.48), gold, 0.02)


def great_dragon(x, y, fire=False):
    if fire:
        # Fire drake: crimson scales, molten belly, glowing orange wings,
        # obsidian horns and talons, and embers in the open jaw.
        scales = material('Drake crimson scales', (0.80, 0.08, 0.03), 0.45, 0.2,
                          rim=(1.0, 0.55, 0.2), rim_strength=1.6, coat=0.8)
        belly = material('Drake molten belly', (1.0, 0.55, 0.08), 0.3, 0.2,
                         emission=(1.0, 0.4, 0.05), strength=0.4,
                         rim=(1.0, 0.8, 0.4), rim_strength=0.8)
        wing = material('Drake wing membrane', (0.95, 0.22, 0.03), 0.7, 0.2,
                        emission=(1.0, 0.25, 0.02), strength=0.3,
                        rim=(1.0, 0.75, 0.3), rim_strength=1.2)
        gold = material('Drake obsidian horns', (0.02, 0.02, 0.025), roughness=0.15,
                        coat=1.0, rim=(1.0, 0.45, 0.1), rim_strength=1.5)
        eye = material('Drake yellow eyes', (1.0, 0.9, 0.2), emission=(1.0, 0.85, 0.2),
                       strength=6.0)
        ember = material('Drake jaw embers', (1.0, 0.6, 0.1), emission=(1.0, 0.5, 0.05),
                         strength=4.0)
        sphere('Drake jaw ember', (x, y - 0.86, 0.73), (0.04, 0.06, 0.025), ember, 16)
    else:
        scales = material('Dragon emerald scales', (0.03, 0.62, 0.30), 0.5, 0.18,
                          rim=(0.5, 1.0, 0.6), rim_strength=1.5, coat=0.8)
        belly = material('Dragon jade belly', (0.55, 0.95, 0.55), 0.4, 0.2,
                         rim=(0.8, 1.0, 0.7), rim_strength=0.8)
        wing = material('Dragon wing membrane', (0.10, 0.85, 0.45), 0.75, 0.2,
                        emission=(0.1, 0.6, 0.3), strength=0.4,
                        rim=(0.7, 1.0, 0.6), rim_strength=1.2)
        gold = material('Dragon gold horns', (1.0, 0.72, 0.22), roughness=0.2, metallic=1.0)
        eye = material('Dragon fire eyes', (1.0, 0.35, 0.05), emission=(1.0, 0.35, 0.05),
                       strength=6.0)
    # Raised neck and head, heavy chest, tail curling behind.
    spine = [(0.00, -0.98, 0.78), (0.00, -0.86, 0.84), (0.00, -0.70, 0.86), (0.00, -0.55, 0.74),
             (0.00, -0.38, 0.58), (0.00, -0.15, 0.52), (0.00, 0.12, 0.50), (0.04, 0.36, 0.42),
             (0.16, 0.56, 0.32), (0.30, 0.72, 0.24), (0.26, 0.92, 0.18), (0.06, 1.00, 0.14),
             (-0.12, 0.96, 0.12)]
    radii = [(0.07, 0.05), (0.15, 0.10), (0.18, 0.13), (0.13, 0.12), (0.18, 0.16), (0.32, 0.24),
             (0.30, 0.22), (0.22, 0.17), (0.15, 0.12), (0.10, 0.08), (0.07, 0.05), (0.04, 0.03), 0]
    tube('Dragon body', [(x + px, y + py, pz) for px, py, pz in spine], radii, scales,
         sides=8, twist=math.pi / 8)
    # Lower jaw, slightly open.
    tube('Dragon jaw', [(x, y - 0.66, 0.74), (x, y - 0.84, 0.70), (x, y - 0.97, 0.66)],
         [(0.13, 0.05), (0.11, 0.04), 0], belly, sides=6)
    for side in (-1, 1):
        sphere('Dragon eye', (x + side * 0.12, y - 0.82, 0.92), (0.045, 0.04, 0.03), eye, 16)
        tube('Dragon swept horn', [(x + side * 0.10, y - 0.72, 0.96), (x + side * 0.18, y - 0.58, 1.06),
                                   (x + side * 0.24, y - 0.42, 1.10), (x + side * 0.27, y - 0.30, 1.06)],
             [0.05, 0.04, 0.025, 0], gold, sides=6, smooth=True)
        # Wing: arm bone, three finger bones, scalloped membrane between them.
        shoulder = Vector((x + side * 0.22, y - 0.18, 0.66))
        # Raised wings keep the sprite narrow enough for the tall game cells.
        wrist = Vector((x + side * 0.56, y - 0.04, 1.12))
        tips = [Vector((x + side * 0.92, y + 0.12, 1.40)),
                Vector((x + side * 0.98, y + 0.44, 1.02)),
                Vector((x + side * 0.74, y + 0.64, 0.62))]
        root = Vector((x + side * 0.12, y + 0.40, 0.50))
        tube('Dragon wing arm', [shoulder, wrist], [0.06, 0.04], scales, sides=6)
        for tip in tips:
            tube('Dragon wing finger', [wrist, tip], [0.03, 0], scales, sides=5)
        cone('Dragon wing claw', wrist, wrist + Vector((side * 0.05, -0.10, 0.10)),
             0.03, 0, gold, 5, False)
        outline = [shoulder, wrist, tips[0]]
        for a, b in zip(tips, tips[1:] + [root]):
            sag = (a + b) / 2
            sag = wrist + (sag - wrist) * 0.78
            outline += [sag, b]
        verts = [tuple(v) for v in outline]
        faces = [(1, i, i + 1) for i in range(2, len(verts) - 1)] + [(0, 1, len(verts) - 1)]
        membrane = mesh_object('Dragon wing membrane', verts, faces, wing, True)
        solid = membrane.modifiers.new('Membrane thickness', 'SOLIDIFY')
        solid.thickness = 0.02
        solid.offset = 0
        for dy, back in ((-0.22, -0.12), (0.30, 0.10)):
            hip = (x + side * 0.24, y + dy, 0.48)
            knee = (x + side * 0.46, y + dy + back * 0.3, 0.36)
            foot = (x + side * 0.48, y + dy + back - 0.04, 0.08)
            tube('Dragon leg', [hip, knee, foot], [0.13, 0.10, 0.08], scales, sides=6)
            for spread in (-0.05, 0, 0.05):
                cone('Dragon talon', (foot[0] + spread, foot[1] - 0.04, 0.06),
                     (foot[0] + spread * 1.6, foot[1] - 0.16, 0.03), 0.025, 0, gold, 4, False)
    # Dorsal spikes from the neck to the tail.
    for i in range(3, 10):
        (px, py, pz), (_, rz) = spine[i], radii[i]
        h = 0.16 if 4 <= i <= 7 else 0.10
        base = Vector((x + px, y + py, pz + rz * 0.8))
        cone('Dragon dorsal spike', base, base + Vector((0, 0.07, h)), 0.05, 0, gold, 4, False)


def transform_new(start, matrix):
    """Apply `matrix` to every object created since the `start` object set."""
    bpy.context.view_layer.update()
    for obj in set(bpy.data.objects) - start:
        obj.matrix_world = matrix @ obj.matrix_world


def nomicon(x, y):
    leather = material('Nomicon indigo leather', (0.10, 0.06, 0.32), 0.15, 0.35,
                       rim=(0.55, 0.45, 1.0), rim_strength=1.2, coat=0.6)
    gold = material('Nomicon gold corners', (1.0, 0.70, 0.22), roughness=0.22, metallic=1.0)
    page = material('Nomicon parchment pages', (0.86, 0.72, 0.46), 0.1, 0.5,
                    emission=(1.0, 0.75, 0.4), strength=0.15)
    rune = material('Nomicon cyan runes', (0.1, 0.75, 1.0), emission=(0.1, 0.7, 1.0),
                    strength=3.0)
    ribbon = material('Nomicon crimson ribbon', (0.75, 0.04, 0.08), 0.1, 0.4)
    start = set(bpy.data.objects)
    # An open tome built lying flat (spine along Y), then tilted toward the
    # camera and lifted so it floats above its cell.
    for side in (-1, 1):
        half = Matrix.Translation((x, y, 0)) @ Matrix.Rotation(side * -0.20, 4, 'Y')
        parts = [block('Nomicon cover', (side * 0.36, 0, 0.0), (0.70, 0.98, 0.05), leather, 0.02),
                 block('Nomicon page stack', (side * 0.33, 0, 0.055), (0.60, 0.88, 0.07),
                       page, 0.015)]
        for corner in (-1, 1):
            parts.append(block('Nomicon gold corner', (side * 0.66, corner * 0.44, 0.0),
                               (0.12, 0.12, 0.07), gold, 0.02))
        # Rune lines written across each page.
        for i, length in enumerate((0.42, 0.34, 0.46, 0.28, 0.40)):
            dx = side * (0.10 + length / 2)
            parts.append(block('Nomicon rune line', (dx, 0.30 - i * 0.15, 0.095),
                               (length, 0.06, 0.02), rune, 0.008))
        bpy.context.view_layer.update()
        for obj in parts:
            obj.matrix_world = half @ obj.matrix_world
    tube('Nomicon spine', [(x, y - 0.49, -0.01), (x, y + 0.49, -0.01)], [0.06, 0.06], leather,
         sides=8, smooth=True)
    tube('Nomicon ribbon', [(x, y + 0.40, 0.11), (x + 0.03, y + 0.58, 0.02),
                            (x + 0.06, y + 0.66, -0.20)], [(0.035, 0.008)] * 3, ribbon, sides=4)
    tilt = Matrix.Translation((x, y, 0.62)) @ Matrix.Rotation(math.radians(12), 4, 'X') \
        @ Matrix.Translation((-x, -y, 0))
    transform_new(start, tilt)


def ocular(x, y):
    sclera = material('Ocular pearl sclera', (0.95, 0.96, 1.0), 0.35, 0.12,
                      rim=(0.7, 0.9, 1.0), rim_strength=1.0, coat=1.0)
    iris = material('Ocular amber iris', (1.0, 0.45, 0.03), 0.3, 0.1,
                    emission=(1.0, 0.4, 0.03), strength=1.0, coat=1.0)
    gold = material('Ocular gold rings', (1.0, 0.70, 0.22), roughness=0.22, metallic=1.0)
    lens = material('Ocular crystal cornea', (0.9, 0.97, 1.0), 0.95, 0.03, coat=1.0)
    center = Vector((x, y, 0.62))
    # The eye looks straight at the camera, i.e. at the player.
    look = Vector((0, -math.cos(math.radians(60)), math.sin(math.radians(60))))
    sphere('Ocular eyeball', tuple(center), (0.36, 0.36, 0.36), sclera, 48)
    cone('Ocular iris', center + look * 0.30, center + look * 0.355, 0.20, 0.17, iris, 40)
    cone('Ocular pupil', center + look * 0.35, center + look * 0.37, 0.085, 0.07, obsidian, 32)
    sphere('Ocular cornea', tuple(center + look * 0.20), (0.20, 0.20, 0.20), lens, 32)
    # A gyroscope-like gold frame: a ring around the eye and one tilted across it.
    for name, rotation in (('Ocular equator ring', (0.0, 0.0, 0.0)),
                           ('Ocular orbit ring', (math.radians(60), math.radians(25), 0.0))):
        bpy.ops.mesh.primitive_torus_add(major_radius=0.46, minor_radius=0.03,
                                         location=tuple(center), rotation=rotation)
        finish(bpy.context.object, gold, True, name)
    for side in (-1, 1):
        cone('Ocular ring fin', center + Vector((side * 0.46, 0, 0)),
             center + Vector((side * 0.62, 0, 0.10)), 0.06, 0, gold, 4, False)


def rank_mark(x, y, count):
    """Empowered-rank mark: `count` raised straight apostrophes in near-white resin.

    The GUI tints it with the monster's strength color, like the text mark.
    """
    resin = material('Rank mark white resin', (0.92, 0.92, 0.92), 0.0, 0.18, coat=1.0,
                     rim=(1.0, 1.0, 1.0), rim_strength=0.6)
    start = set(bpy.data.objects)
    for i in range(count):
        dx = (i - (count - 1) / 2) * 0.30
        # A straight wedge, thick and rounded at the top and tapering down,
        # like the game's text apostrophe, standing upright.
        sphere('Rank mark cap', (x + dx, y, 0.55), (0.085, 0.085, 0.085), resin, 32)
        tube('Rank mark stroke', [(x + dx, y, 0.55), (x + dx, y, 0.35), (x + dx, y, 0.18)],
             [0.085, 0.06, 0.035], resin, sides=24, smooth=True)
        sphere('Rank mark tip', (x + dx, y, 0.18), (0.035, 0.035, 0.035), resin, 16)
    # Lean back so the face of the mark looks at the 60-degree camera.
    transform_new(start, Matrix.Translation((x, y, 0.35)) @ Matrix.Rotation(math.radians(-40), 4, 'X')
                  @ Matrix.Translation((-x, -y, -0.35)))


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
            'A': lambda x, y: amoeba(x, y, True), 'b': bison, 'd': dragon,
            'c': chimera, 'T': treasure, 'D': great_dragon, 'n': nomicon, 'o': ocular,
            'C': lambda x, y: chimera(x, y, True), 'F': lambda x, y: great_dragon(x, y, True),
            "'": lambda x, y: rank_mark(x, y, 1), '"': lambda x, y: rank_mark(x, y, 2)}
for char, name, x, y in ROW:
    start = set(bpy.data.objects)
    builders[char](x, y)
    character = set(bpy.data.objects) - start
    bpy.context.view_layer.update()
    pivot = Matrix.Translation((x, y, 0))
    yaw = MONSTER_YAW if char in 'aAbcdDCF' else 0
    resize = (pivot @ Matrix.Rotation(yaw, 4, 'Z') @ Matrix.Scale(SIZES[char], 4)
              @ pivot.inverted())
    for obj in character:
        obj.matrix_world = resize @ obj.matrix_world
    # Apply the size and turn to the mesh data so the model itself is built that way.
    bpy.ops.object.select_all(action='DESELECT')
    meshes = [obj for obj in character if obj.type == 'MESH']
    for obj in meshes:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    block(name + ' tile', (x, y, -0.05), (3.1 if char in 'DF' else 1.85, 2.6, 0.1), tile, 0.04)
    label(name, (x, y - 1.55, 0.0), 0.16)
    collection = bpy.data.collections.new('Character ' + char + ' ' + name)
    scene.collection.children.link(collection)
    for obj in set(bpy.data.objects) - start:
        for old in list(obj.users_collection):
            old.objects.unlink(obj)
        collection.objects.link(obj)
        obj['sprite'] = obj in character

bpy.ops.mesh.primitive_plane_add(size=80, location=(0, 0, -0.1))
finish(bpy.context.object, dark, True, 'Backdrop')
label('ARLQ / STAGE 1-2 / HEROIC RESIN', (1.6, 1.85, 0.0), 0.2)
# Warm key, cool fill, strong back rim lights for glossy edges.
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
angle = math.radians(60)
target = Vector((1.6, STAGE2_ROW_Y / 2, 0))
camera.location = target + Vector((0, -15 * math.cos(angle), 15 * math.sin(angle)))
camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
camera.data.type = 'ORTHO'
camera.data.ortho_scale = 22.6
scene.camera = camera
scene['sprite_centers'] = {char: list(pos) for char, pos in CENTERS.items()}
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'characters-angle60.blend'))
if '--save-only' not in sys.argv:
    scene.render.filepath = str(OUT / 'preview-angle60.png')
    bpy.ops.render.render(write_still=True)
