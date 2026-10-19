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
scene.render.resolution_x = 1600
scene.render.resolution_y = 990
scene.view_settings.view_transform = 'Standard'
scene.view_settings.look = 'Medium High Contrast'
world = bpy.data.worlds.new('Night studio')
world.use_nodes = True
world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.012, 0.018, 0.03, 1)
scene.world = world

# Three rows, back to front: the player, Stage 1 monsters and chest; the
# companions and elves; the monsters added from Stage 2 on and the rank marks.
ROW_Y = (0.0, -3.8, -7.6)
ROW = [('@', 'PLAYER', -7.0, ROW_Y[0]), ('a', 'AMOEBA', -5.0, ROW_Y[0]),
       ('A', 'RARE AMOEBA', -3.0, ROW_Y[0]), ('b', 'BISON', -1.0, ROW_Y[0]),
       ('c', 'CHIMERA', 1.0, ROW_Y[0]), ('d', 'COMODO DRAGON', 3.0, ROW_Y[0]),
       ('T', 'TREASURE CHEST', 5.0, ROW_Y[0]), ('D', 'DRAGON', 7.7, ROW_Y[0]),
       ('l', 'LOOP', -9.4, ROW_Y[1]), ('n', 'NOMICON', -7.4, ROW_Y[1]), ('o', 'OCULAR', -5.4, ROW_Y[1]),
       ('p', 'PEGASUS', -3.4, ROW_Y[1]), ('H', 'HIGH ELF', -1.4, ROW_Y[1]),
       ('I', 'ISOLATED ELF', 0.6, ROW_Y[1]), ('J', 'JAVELIN ELF', 2.6, ROW_Y[1]),
       ('K', 'COLLECTOR ELF', 4.6, ROW_Y[1]),
       ('L', 'LIFEBRINGER ELF', 6.6, ROW_Y[1]),
       ('S', 'SYLVAN ELF', 8.6, ROW_Y[1]),
       ('C', 'RARE CHIMERA', -7.4, ROW_Y[2]), ('F', 'FIRE DRAKE', -4.775, ROW_Y[2]),
       ('g', 'GOLEM', -2.15, ROW_Y[2]), ('rock', 'GOLEM ROCK', -0.15, ROW_Y[2]),
       ('e', 'EREBUS', 1.85, ROW_Y[2]), ('E', 'RARE EREBUS', 3.85, ROW_Y[2]),
       ('X', 'CALTROP PLANT', 5.85, ROW_Y[2]), ("'", 'RANK 2', 7.525, ROW_Y[2]),
       ('"', 'RANK 3', 8.875, ROW_Y[2])]
# Sprite export reads the character centres from here.
CENTERS = {char: (x, y) for char, _, x, y in ROW}
# Model sizes relative to the amoeba, baked into the meshes. Sprites are exported
# and drawn at one common scale, so these decide how large each character
# appears; the boss dragon is built large, its wings spreading past its cell.
SIZES = {'@': 1.42, 'a': 1.0, 'A': 1.0, 'b': 1.09, 'c': 1.2, 'd': 1.16, 'T': 1.66, 'D': 1.44,
         'l': 1.4, 'n': 1.15, 'o': 1.25, 'C': 1.28, 'F': 1.52, "'": 1.7, '"': 1.7,
         'g': 1.3, 'e': 1.9, 'E': 2.2, 'X': 1.35, 'p': 1.3, 'H': 1.8, 'I': 1.6, 'J': 1.6, 'K': 1.6, 'L': 1.7, 'S': 1.6,
         'rock': 2.5}
# The pegasus companion turns further left, so its horse profile shows.
PEGASUS_YAW = math.radians(-45)
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
    # A modest shaggy hump: a few low-poly clumps over the shoulders and brow,
    # kept small so the bison does not look too strong.
    clumps = [(0, -0.28, 0.90, 0.25), (-0.22, -0.22, 0.84, 0.19), (0.22, -0.22, 0.84, 0.19),
              (0, -0.04, 0.86, 0.21), (0, -0.52, 0.76, 0.19)]
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
        # Half-size horns, so they are not mistaken for the chimeras' swords.
        root = Vector((x + side * 0.30, y - 0.66, 0.66))
        horn_path = [(0.30, -0.66, 0.66), (0.56, -0.66, 0.68), (0.74, -0.70, 0.82),
                     (0.76, -0.80, 1.00), (0.66, -0.92, 1.12)]
        tube('Bison horn', [root + (Vector((x + side * px, y + py, pz)) - root) * 0.5
                            for px, py, pz in horn_path],
             [0.065, 0.055, 0.04, 0.025, 0], horn, sides=10, smooth=True)
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
    # Midnight blue so the yellow and red low-LP ground discs stand out.
    cape = material('Player midnight cloak', (0.025, 0.05, 0.16), 0.15, 0.4,
                    rim=(0.25, 0.45, 1.0), rim_strength=0.6)
    # Trim and sword are plain dark iron rather than precious metal.
    iron = material('Player dark iron trim', (0.16, 0.16, 0.18), roughness=0.35, metallic=1.0)
    visor = material('Player visor glow', (0.3, 0.9, 1.0), emission=(0.1, 0.75, 1.0),
                     strength=2.5)
    blade = material('Player iron blade', (0.62, 0.63, 0.66), roughness=0.4, metallic=0.55,
                     rim=(0.85, 0.9, 1.0), rim_strength=0.8)
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
    finish(bpy.context.object, iron, True, 'Player belt')
    block('Player buckle', (x, y - 0.29, 0.24), (0.09, 0.03, 0.07), iron, 0.012)
    block('Player head', (x, y - 0.07, 0.67), (0.38, 0.36, 0.36), helm, 0.11)
    block('Player visor', (x, y - 0.25, 0.63), (0.30, 0.05, 0.08), visor, 0.015)
    for side in (-1, 1):
        cone('Player helm fin', (x + side * 0.17, y - 0.02, 0.74),
             (x + side * 0.30, y + 0.10, 0.92), 0.06, 0, iron, 4, False)
        arm = block('Player short arm', (x + side * 0.285, y - 0.075, 0.32),
                    (0.16, 0.18, 0.28), tunic, 0.065)
        arm.rotation_euler.y = -side * 0.12
        sphere('Player pauldron', (x + side * 0.27, y - 0.06, 0.46), (0.09, 0.10, 0.045), iron, 24)
    # Short sword in the right hand (screen left), held low and outward.
    hand = Vector((x - 0.33, y - 0.16, 0.20))
    tip = hand + Vector((-0.34, -0.30, -0.10)) * 0.8
    tube('Player sword blade', [hand + (tip - hand) * 0.12, tip * 0.94 + hand * 0.06, tip],
         [(0.075, 0.016), (0.06, 0.014), 0], blade, sides=4)
    tube('Player sword guard', [hand + Vector((0.07, -0.08, 0)), hand + Vector((-0.08, 0.06, 0))],
         [0.025, 0.025], iron, sides=6)
    # Cloak: hugs the shoulders, drifts back and sideways toward the hem.
    columns, rows = 25, 8
    vertices = []
    for row in range(rows):
        t = row / (rows - 1)
        for col in range(columns):
            u = col / (columns - 1) * 2 - 1
            angle = u * math.radians(95)
            radius = 0.29 + 0.10 * t
            vertices.append((x + radius * math.sin(angle) + 0.05 * t * t,
                             y + radius * math.cos(angle) + 0.21 * t * t,
                             0.50 - 0.36 * t + 0.045 * t * math.cos(u * math.pi * 3)))
    faces = [(r * columns + c, r * columns + c + 1, (r + 1) * columns + c + 1, (r + 1) * columns + c)
             for r in range(rows - 1) for c in range(columns - 1)]
    cloak = mesh_object('Player cloak', vertices, faces, cape, True)
    cloak.modifiers.new('Smooth drape', 'SUBSURF').levels = 2
    solid = cloak.modifiers.new('Fabric thickness', 'SOLIDIFY')
    solid.thickness = 0.03
    solid.offset = 0
    hem = [vertices[(rows - 1) * columns + c] for c in range(columns)]
    tube('Player cloak hem trim', hem, [0.018] * columns, iron, sides=6, smooth=True)


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
    page = material('Nomicon parchment pages', (0.58, 0.43, 0.22), 0.1, 0.55,
                    emission=(1.0, 0.7, 0.35), strength=0.05)
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
    iris = material('Ocular amber iris', (0.95, 0.32, 0.02), 0.2, 0.15,
                    emission=(1.0, 0.35, 0.02), strength=0.35, coat=0.6)
    gold = material('Ocular gold rings', (1.0, 0.70, 0.22), roughness=0.22, metallic=1.0)
    pupil = material('Ocular matte pupil', (0.0, 0.0, 0.0), roughness=0.9)
    center = Vector((x, y, 0.62))
    # The eye looks straight at the camera, i.e. at the player.
    look = Vector((0, -math.cos(math.radians(60)), math.sin(math.radians(60))))
    sphere('Ocular eyeball', tuple(center), (0.36, 0.36, 0.36), sclera, 48)
    cone('Ocular iris', center + look * 0.30, center + look * 0.355, 0.20, 0.17, iris, 40)
    cone('Ocular pupil', center + look * 0.35, center + look * 0.37, 0.085, 0.07, pupil, 32)
    # A gyroscope-like gold frame: a ring around the eye and one tilted across it.
    for name, rotation in (('Ocular equator ring', (0.0, 0.0, 0.0)),
                           ('Ocular orbit ring', (math.radians(60), math.radians(25), 0.0))):
        bpy.ops.mesh.primitive_torus_add(major_radius=0.46, minor_radius=0.03,
                                         location=tuple(center), rotation=rotation)
        finish(bpy.context.object, gold, True, name)
    for side in (-1, 1):
        cone('Ocular ring fin', center + Vector((side * 0.46, 0, 0)),
             center + Vector((side * 0.62, 0, 0.10)), 0.06, 0, gold, 4, False)



def loop_watch(x, y):
    """Loop companion: a floating gold pocket watch whose glowing ring and
    arrow on the dial suggest turning time back."""
    gold = material('Loop gold case', (1.0, 0.70, 0.22), roughness=0.22, metallic=1.0)
    dial = material('Loop ivory dial', (0.92, 0.88, 0.76), 0.1, 0.3, coat=0.8)
    ink = material('Loop blued steel hands', (0.04, 0.06, 0.16), roughness=0.3, metallic=0.6)
    glow = material('Loop cyan time ring', (0.1, 0.75, 1.0), emission=(0.1, 0.7, 1.0),
                    strength=3.0)
    start = set(bpy.data.objects)
    # Built with the dial facing +Z and 12 o'clock toward +Y, then turned to
    # face the camera and lifted so it floats above its cell.
    bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=0.40, depth=0.12, location=(0, 0, 0))
    case = finish(bpy.context.object, gold, True, 'Loop watch case')
    bevel = case.modifiers.new('Rounded back', 'BEVEL')
    bevel.width = 0.04
    bevel.segments = 4
    case.data.use_auto_smooth = True
    bpy.ops.mesh.primitive_torus_add(major_radius=0.38, minor_radius=0.04, location=(0, 0, 0.06))
    finish(bpy.context.object, gold, True, 'Loop watch bezel')
    bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=0.35, depth=0.02, location=(0, 0, 0.06))
    finish(bpy.context.object, dial, True, 'Loop watch dial')
    for hour in range(12):
        a = math.pi / 2 - hour * math.pi / 6
        long = hour % 3 == 0
        block('Loop hour mark', (0.29 * math.cos(a), 0.29 * math.sin(a), 0.075),
              (0.03, 0.08 if long else 0.05, 0.02), gold if long else ink, 0.006,
              (0, 0, a - math.pi / 2))
    # The time-loop ring inside the hour marks, with an arrowhead running
    # counterclockwise, i.e. backward.
    bpy.ops.mesh.primitive_torus_add(major_radius=0.20, minor_radius=0.022,
                                     location=(0, 0, 0.075))
    finish(bpy.context.object, glow, True, 'Loop time ring')
    a = math.radians(200)
    tip = Vector((0.20 * math.cos(a), 0.20 * math.sin(a), 0.08))
    heading = Vector((-math.sin(a), math.cos(a), 0))
    side = Vector((heading.y, -heading.x, 0))
    arrow = mesh_object('Loop rewind arrow', [tuple(tip + heading * 0.10),
                                              tuple(tip + side * 0.075), tuple(tip - side * 0.075)],
                        [(0, 1, 2)], glow, False)
    arrow.modifiers.new('Arrow thickness', 'SOLIDIFY').thickness = 0.02
    # Warped hands, as if time itself were bending. The hour hand points
    # left: it rises, curls over to point down, then turns up again. The
    # minute hand is its mirror image, a little larger, so the two read as
    # an upturned moustache.
    def hand(name, length, width, headings, steps):
        points, pos = [], Vector((0, 0, 0.11))
        for i in range(steps + 1):
            points.append(pos.copy())
            heading = headings(i / steps)
            pos += Vector((math.cos(heading), math.sin(heading), 0.006)) * (length / steps)
        tube(name, points, [(width * (1 - i / steps) ** 0.6 + 0.005, 0.008)
                            for i in range(steps)] + [0], ink, sides=8, smooth=True)

    def smoothstep(t):
        t = min(1.0, max(0.0, t))
        return t * t * (3 - 2 * t)

    def hour_heading(t):
        return math.radians(145 + 125 * smoothstep((t - 0.2) / 0.3)
                            - 165 * smoothstep((t - 0.55) / 0.35))

    hand('Loop moustache hour hand', 0.42, 0.024, hour_heading, 40)
    hand('Loop moustache minute hand', 0.42 * 1.15, 0.024 * 1.15,
         lambda t: math.pi - hour_heading(t), 40)
    sphere('Loop centre cap', (0, 0, 0.12), (0.035, 0.035, 0.02), gold, 24)
    # Crown and bow at 12 o'clock.
    tube('Loop watch stem', [(0, 0.40, 0), (0, 0.47, 0)], [0.035, 0.035], gold, sides=12,
         smooth=True)
    tube('Loop watch crown', [(0, 0.46, 0), (0, 0.53, 0)], [0.06, 0.06], gold, sides=16)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.09, minor_radius=0.022,
                                     location=(0, 0.62, 0))
    finish(bpy.context.object, gold, True, 'Loop watch bow')
    face = Matrix.Translation((x, y, 0.62)) @ Matrix.Rotation(math.radians(30), 4, 'X')
    transform_new(start, face)

def metaball_mesh(name, elements, mat, resolution=0.01):
    """Melt (position, radius) metaballs into one smooth mesh object.

    The surface lies at roughly 0.6 of each element's radius.
    """
    meta = bpy.data.metaballs.new(name)
    meta.resolution = meta.render_resolution = resolution
    for co, radius in elements:
        element = meta.elements.new()
        element.co = co
        element.radius = radius
    obj = bpy.data.objects.new(name, meta)
    bpy.context.collection.objects.link(obj)
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.convert(target='MESH')
    return finish(bpy.context.object, mat, True, name)


def erebus(x, y, rare):
    """Erebus: a hooded body of dark smoke whose slanted eyes are pure light.

    The rare Erebus (E) is larger and darker, crowned with obsidian horns,
    with longer, larger red eyes that spill past the hood, long clawed arms
    and a cracked gold halo it drains; the Erebus (e) is small and round,
    with short arms. The face looks up at the 60-degree camera.
    """
    if rare:
        smoke = material('Rare Erebus black smoke', (0.015, 0.015, 0.03), 0.25, 0.4,
                         rim=(0.6, 0.8, 1.0), rim_strength=2.2)
        light, strength = (1.0, 0.12, 0.05), 14.0
    else:
        smoke = material('Erebus indigo smoke', (0.04, 0.05, 0.14), 0.5, 0.4,
                         rim=(0.6, 0.8, 1.0), rim_strength=2.0)
        light, strength = (0.2, 0.85, 1.0), 4.0
    shade = material('Erebus hood shadow', (0.0, 0.0, 0.005), roughness=0.9)
    glow = material('Erebus eye light', light, emission=light, strength=strength)
    # Hood and body, flowing back into a smoke tail along the floor.
    body = [((0, 0, 0.62), 0.46), ((0, 0.03, 0.42), 0.50), ((0, 0.07, 0.24), 0.42),
            ((0.04, 0.20, 0.12), 0.28), ((0.10, 0.33, 0.07), 0.18), ((0.18, 0.42, 0.05), 0.11)]
    if rare:
        # Tall pointed hood and a ragged hem with extra tails.
        body += [((0, 0.06, 0.84), 0.28), ((0, 0.10, 0.98), 0.16), ((0, 0.13, 1.07), 0.08),
                 ((-0.20, 0.22, 0.08), 0.20), ((-0.30, 0.34, 0.05), 0.11),
                 ((0.24, 0.14, 0.08), 0.18), ((0.36, 0.20, 0.05), 0.10)]
        arm = [(0.22, -0.10, 0.44, 0.17), (0.28, -0.24, 0.42, 0.13), (0.24, -0.38, 0.40, 0.10)]
    else:
        body += [((0, 0.12, 0.78), 0.26)]
        arm = [(0.22, -0.12, 0.40, 0.15), (0.17, -0.25, 0.38, 0.11)]
    for side in (-1, 1):
        body += [((side * ax, ay, az), r) for ax, ay, az, r in arm]
    shape = metaball_mesh('Erebus E body' if rare else 'Erebus e body',
                          [((x + px, y + py, pz), r) for (px, py, pz), r in body], smoke, 0.015)
    wobble = shape.modifiers.new('Smoke wobble', 'DISPLACE')
    texture = bpy.data.textures.new('Smoke wobble', 'CLOUDS')
    texture.noise_scale = 0.18
    wobble.texture = texture
    wobble.strength = 0.06
    # Dark opening of the hood on its upper front, facing the camera, with
    # the eyes of light set in it; the rare one's eyes spill past the hood.
    facing = Vector((0, -math.cos(math.radians(60)), math.sin(math.radians(60))))
    upward = Vector((0, math.sin(math.radians(60)), math.cos(math.radians(60))))
    face = Vector((x, y, 0.62)) + facing * 0.25
    opening = sphere('Erebus hood opening', tuple(face), (0.19, 0.16, 0.05), shade, 32)
    opening.rotation_euler = (math.radians(30), 0, 0)
    reach, rise, thick = (0.343, 0.10, 0.06) if rare else (0.25, 0.08, 0.05)
    for side in (-1, 1):
        inner = face + facing * 0.035 + Vector((side * 0.035, 0, 0)) - upward * 0.02
        outer = face + facing * 0.035 + Vector((side * reach, 0, 0)) + upward * rise
        mid = inner + (outer - inner) * 0.4
        tube('Erebus slanted eye', [inner, mid, outer], [(0.01, 0.01), (thick, thick * 0.55), 0],
             glow, sides=10, smooth=True)
    if rare:
        horn = material('Rare Erebus obsidian horns', (0.01, 0.01, 0.015), roughness=0.15,
                        coat=1.0, rim=(0.7, 0.85, 1.0), rim_strength=1.5)
        for dx, tilt in ((-0.16, -0.12), (0.0, 0.0), (0.16, 0.12)):
            base = Vector((x + dx, y + 0.06, 0.92 if dx else 1.02))
            cone('Rare Erebus crown horn', base, base + Vector((tilt, 0.04, 0.24 if dx else 0.18)),
                 0.05, 0, horn, 5, False)
        for side in (-1, 1):
            hand = Vector((x + side * 0.24, y - 0.44, 0.40))
            for spread in (-0.05, 0.05):
                cone('Rare Erebus claw', hand, hand + Vector((-side * 0.08, -0.07, spread)),
                     0.025, 0, horn, 4, False)
        # A cracked gold halo held between the hands, with drifting shards.
        gold = material('Stolen halo gold', (1.0, 0.72, 0.22), roughness=0.2, metallic=1.0,
                        emission=(1.0, 0.6, 0.15), strength=0.6)
        center = Vector((x, y - 0.50, 0.42))
        for a0, a1 in ((20, 160), (195, 330)):
            arc = [center + Vector((0.15 * math.cos(math.radians(a)), 0.15 * 0.5 * math.sin(math.radians(a)),
                                    0.15 * 0.85 * math.sin(math.radians(a))))
                   for a in range(a0, a1 + 1, 10)]
            tube('Stolen halo arc', arc, [0.022] * len(arc), gold, sides=8, smooth=True)
        for dx, dz in ((-0.22, 0.62), (0.20, 0.66), (0.05, 0.74)):
            base = Vector((x + dx, y - 0.46, dz))
            cone('Halo shard', base, base + Vector((0.02, 0, 0.06)), 0.03, 0, gold, 4, False)


ELF_STRETCH = 1.3


def elf_figure(x, y, prefix, robe, skin, eye, body, head, skirt=(0.25, 0.19, 0.14), torso=None,
               skirt_z=(0.02, 0.30, 0.58), girth=1.0, ears=True):
    """Shared elf build: about three heads tall, slimmer and taller than the
    player, in a long robe, with pointed ears; `body(x, y)` and `head(x, y)`
    add each elf's own parts, and `torso` can dress the upper body apart
    from the robe. `skirt_z` raises the robe's hem (for a seated elf),
    `girth` widens the upper body, and `ears=False` leaves out the pointed ears.

    Heights shrink to half in the 60-degree view, so the body is stretched
    upward and the head tilted back for the face to look at the camera.
    """
    body_start = set(bpy.data.objects)
    # Long robe flaring to the floor and the slim body above it.
    tube(prefix + ' robe skirt', [(x, y, z) for z in skirt_z], list(skirt),
         robe, sides=32, smooth=True)
    tube(prefix + ' robe body', [(x, y, 0.56), (x, y, 0.72), (x, y, 0.86), (x, y, 0.90)],
         [(rx * girth, ry * girth) for rx, ry in
          ((0.16, 0.13), (0.19, 0.15), (0.17, 0.13), (0.08, 0.07))], torso or robe, sides=32,
         smooth=True)
    body(x, y)
    head_start = set(bpy.data.objects)
    for side in (-1, 1):
        if ears:
            cone(prefix + ' ear', (x + side * 0.12, y + 0.01, 1.04), (x + side * 0.27, y + 0.05, 1.13),
                 0.04, 0, skin, 10, True)
        sphere(prefix + ' eye', (x + side * 0.05, y - 0.135, 1.04), (0.022, 0.012, 0.028), eye, 12)
    sphere(prefix + ' head', (x, y, 1.03), (0.14, 0.14, 0.155), skin, 32)
    head(x, y)
    bpy.context.view_layer.update()
    neck = Vector((x, y, 0.90))
    for obj in head_start - body_start:
        obj.matrix_world = (Matrix.Translation((x, y, 0)) @ Matrix.Diagonal((1, 1, ELF_STRETCH, 1))
                            @ Matrix.Translation((-x, -y, 0)) @ obj.matrix_world)
    lift = Matrix.Translation((0, 0, neck.z * (ELF_STRETCH - 1)))
    tilt = Matrix.Translation(neck) @ Matrix.Rotation(-0.6, 4, 'X') @ Matrix.Translation(-neck)
    for obj in set(bpy.data.objects) - head_start:
        obj.matrix_world = lift @ tilt @ obj.matrix_world


def high_elf(x, y):
    """High Elf: a noble in a long royal blue robe with a gold belt, a white
    mantle trailing behind, a gold crown over long platinum hair, and the
    glowing protective amulet on the chest above clasped hands.
    """
    robe = material('High elf royal blue robe', (0.05, 0.12, 0.55), 0.2, 0.3,
                    rim=(0.5, 0.7, 1.0), rim_strength=1.2, coat=0.5)
    mantle = material('High elf white mantle', (0.90, 0.91, 0.95), 0.2, 0.35,
                      rim=(0.85, 0.9, 1.0), rim_strength=0.8)
    gold = material('High elf gold', (1.0, 0.72, 0.22), roughness=0.25, metallic=0.8,
                    emission=(1.0, 0.62, 0.15), strength=0.4)
    skin = material('High elf skin', (0.95, 0.80, 0.68), 0.2, 0.4,
                    rim=(1.0, 0.9, 0.8), rim_strength=0.6)
    hair = material('High elf platinum hair', (0.95, 0.92, 0.80), 0.3, 0.3,
                    rim=(1.0, 1.0, 0.9), rim_strength=1.0, coat=0.5)
    gem = material('High elf amulet light', (0.35, 0.8, 1.0), emission=(0.3, 0.75, 1.0),
                   strength=6.0)
    eye = material('High elf eyes', (0.05, 0.12, 0.25), roughness=0.2, coat=1.0)

    def body(x, y):
        bpy.ops.mesh.primitive_torus_add(major_radius=0.155, minor_radius=0.025, location=(x, y, 0.58))
        finish(bpy.context.object, gold, True, 'High elf belt')
        # Mantle hanging from the shoulders and trailing back along the floor.
        columns, rows = 21, 8
        vertices = []
        for row in range(rows):
            t = row / (rows - 1)
            for col in range(columns):
                u = col / (columns - 1) * 2 - 1
                angle = u * math.radians(105)
                radius = 0.20 + 0.22 * t
                vertices.append((x + radius * math.sin(angle),
                                 y + radius * math.cos(angle) + 0.22 * t * t,
                                 0.88 - 0.85 * t))
        faces = [(r * columns + c, r * columns + c + 1, (r + 1) * columns + c + 1, (r + 1) * columns + c)
                 for r in range(rows - 1) for c in range(columns - 1)]
        cloak = mesh_object('High elf mantle', vertices, faces, mantle, True)
        cloak.modifiers.new('Smooth drape', 'SUBSURF').levels = 2
        solid = cloak.modifiers.new('Fabric thickness', 'SOLIDIFY')
        solid.thickness = 0.03
        solid.offset = 0
        hem = [vertices[(rows - 1) * columns + c] for c in range(columns)]
        tube('High elf mantle hem', hem, [0.018] * columns, gold, sides=6, smooth=True)
        for side in (-1, 1):
            sphere('High elf mantle clasp', (x + side * 0.15, y - 0.10, 0.86), (0.04, 0.03, 0.04), gold, 16)
            # Sleeves from the shoulders to hands clasped in front of the waist.
            tube('High elf sleeve', [(x + side * 0.19, y, 0.84), (x + side * 0.22, y - 0.06, 0.70),
                                     (x + side * 0.10, y - 0.18, 0.64)], [0.06, 0.06, 0.07], robe,
                 sides=12, smooth=True)
            sphere('High elf hand', (x + side * 0.05, y - 0.21, 0.64), (0.05, 0.045, 0.045), skin, 16)
        # The protective amulet, glowing on the chest.
        sphere('High elf amulet', (x, y - 0.185, 0.76), (0.05, 0.03, 0.06), gem, 16)
        bpy.ops.mesh.primitive_torus_add(major_radius=0.055, minor_radius=0.012, location=(x, y - 0.19, 0.76),
                                         rotation=(math.pi / 2, 0, 0))
        finish(bpy.context.object, gold, True, 'High elf amulet frame')

    def head(x, y):
        # Long hair: a cap over the back of the head, leaving the face clear, and
        # locks down the back.
        sphere('High elf hair cap', (x, y + 0.06, 1.08), (0.15, 0.13, 0.14), hair, 32)
        for dx in (-0.09, -0.03, 0.03, 0.09):
            tube('High elf hair lock', [(x + dx, y + 0.08, 1.04), (x + dx * 1.3, y + 0.16, 0.86),
                                        (x + dx * 1.4, y + 0.19, 0.66)], [0.05, 0.045, 0], hair,
                 sides=8, smooth=True)
        # Crown: a gold band with five points, the middle one tallest with a gem.
        bpy.ops.mesh.primitive_torus_add(major_radius=0.14, minor_radius=0.022, location=(x, y + 0.01, 1.16))
        finish(bpy.context.object, gold, True, 'High elf crown band')
        for angle in (-60, -30, 0, 30, 60):
            a = math.radians(angle - 90)
            base = Vector((x + 0.14 * math.cos(a), y + 0.01 + 0.14 * math.sin(a), 1.16))
            cone('High elf crown point', base, base + Vector((0, 0, 0.16 if angle == 0 else 0.10)),
                 0.03, 0, gold, 6, False)
        sphere('High elf crown gem', (x, y - 0.13, 1.20), (0.03, 0.02, 0.035), gem, 12)

    elf_figure(x, y, 'High elf', robe, skin, eye, body, head)


def isolated_elf(x, y):
    """Isolated Elf: an old hermit, stooped with a rounded back, in a moss
    robe tied with a rope, with long white hair, the only beard among the
    elves, bushy brows, a gnarled staff and an old scroll of elf history.
    """
    robe = material('Isolated elf moss robe', (0.17, 0.24, 0.12), 0.2, 0.45,
                    rim=(0.7, 0.85, 0.6), rim_strength=1.0, coat=0.3)
    rope = material('Isolated elf rope', (0.45, 0.32, 0.16), 0.0, 0.7)
    wood = material('Isolated elf staff wood', (0.28, 0.16, 0.07), 0.0, 0.6,
                    rim=(0.9, 0.7, 0.5), rim_strength=0.6)
    parchment = material('Isolated elf scroll', (0.85, 0.74, 0.50), 0.1, 0.5,
                         rim=(1.0, 0.9, 0.7), rim_strength=0.6)
    skin = material('Isolated elf aged skin', (0.88, 0.74, 0.62), 0.2, 0.45,
                    rim=(1.0, 0.9, 0.8), rim_strength=0.6)
    white = material('Isolated elf white hair', (0.93, 0.93, 0.92), 0.25, 0.4,
                     rim=(1.0, 1.0, 1.0), rim_strength=1.0, coat=0.3)
    eye = material('Isolated elf eyes', (0.10, 0.08, 0.05), roughness=0.3, coat=1.0)

    def body(x, y):
        bpy.ops.mesh.primitive_torus_add(major_radius=0.155, minor_radius=0.02, location=(x, y, 0.58))
        finish(bpy.context.object, rope, True, 'Isolated elf rope belt')
        tube('Isolated elf rope end', [(x + 0.06, y - 0.15, 0.58), (x + 0.08, y - 0.17, 0.46),
                                       (x + 0.07, y - 0.18, 0.38)], [0.018, 0.016, 0.014], rope,
             sides=6, smooth=True)
        # A rounded, stooped back.
        sphere('Isolated elf hunched back', (x, y + 0.10, 0.84), (0.19, 0.15, 0.13), robe, 32)
        # Right hand (screen left) on a gnarled staff taller than the elf.
        tube('Isolated elf staff', [(x - 0.30, y - 0.10, 0.0), (x - 0.31, y - 0.11, 0.45),
                                    (x - 0.29, y - 0.12, 0.85), (x - 0.31, y - 0.12, 1.05)],
             [0.028, 0.026, 0.024, 0.03], wood, sides=8, smooth=True)
        sphere('Isolated elf staff knot', (x - 0.32, y - 0.12, 1.08), (0.055, 0.055, 0.05), wood, 12,
               False)
        tube('Isolated elf right sleeve', [(x - 0.17, y, 0.84), (x - 0.24, y - 0.06, 0.74),
                                           (x - 0.29, y - 0.11, 0.70)], [0.06, 0.06, 0.07], robe,
             sides=12, smooth=True)
        sphere('Isolated elf right hand', (x - 0.30, y - 0.12, 0.70), (0.05, 0.05, 0.05), skin, 16)
        # Left hand (screen right) holding an old scroll before the body.
        tube('Isolated elf left sleeve', [(x + 0.17, y, 0.84), (x + 0.22, y - 0.08, 0.70),
                                          (x + 0.14, y - 0.20, 0.62)], [0.06, 0.06, 0.07], robe,
             sides=12, smooth=True)
        sphere('Isolated elf left hand', (x + 0.12, y - 0.22, 0.62), (0.05, 0.045, 0.045), skin, 16)
        bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=0.045, depth=0.26,
                                            location=(x + 0.10, y - 0.25, 0.64),
                                            rotation=(0, math.pi / 2, 0.3))
        finish(bpy.context.object, parchment, True, 'Isolated elf scroll')

    def head(x, y):
        # Long white hair down the back, bushy brows and a long beard.
        sphere('Isolated elf hair cap', (x, y + 0.06, 1.08), (0.15, 0.13, 0.14), white, 32)
        for dx in (-0.09, -0.03, 0.03, 0.09):
            tube('Isolated elf hair lock', [(x + dx, y + 0.08, 1.04), (x + dx * 1.3, y + 0.15, 0.88),
                                            (x + dx * 1.4, y + 0.17, 0.74)], [0.05, 0.045, 0],
                 white, sides=8, smooth=True)
        for side in (-1, 1):
            sphere('Isolated elf brow', (x + side * 0.055, y - 0.13, 1.085), (0.05, 0.025, 0.022),
                   white, 12)
        tube('Isolated elf beard', [(x, y - 0.11, 0.98), (x, y - 0.17, 0.90), (x, y - 0.19, 0.78),
                                    (x, y - 0.18, 0.66)], [(0.11, 0.06), (0.10, 0.06), (0.07, 0.04), 0],
             white, sides=12, smooth=True)

    elf_figure(x, y, 'Isolated elf', robe, skin, eye, body, head)


def javelin_elf(x, y):
    """Javelin Elf: a youth eager to become a warrior, lightly clad: a
    sleeveless leather jerkin with bare arms and leather bracers over a long
    mustard tunic, with a leather belt, a strap across the chest and a pouch,
    short chestnut hair tied back, one hand on the hip and the other holding
    a slightly oversized javelin upright, its leaf-shaped iron head well above.
    """
    robe = material('Javelin elf mustard tunic', (0.60, 0.38, 0.07), 0.05, 0.6,
                    rim=(1.0, 0.85, 0.5), rim_strength=0.8)
    leather = material('Javelin elf leather', (0.22, 0.11, 0.05), 0.0, 0.5,
                       rim=(0.9, 0.6, 0.4), rim_strength=0.6)
    wood = material('Javelin elf ash shaft', (0.60, 0.44, 0.26), 0.0, 0.5,
                    rim=(1.0, 0.85, 0.6), rim_strength=0.6)
    iron = material('Javelin elf iron head', (0.62, 0.63, 0.66), roughness=0.35, metallic=0.55,
                    rim=(0.85, 0.9, 1.0), rim_strength=1.0)
    skin = material('Javelin elf skin', (0.96, 0.80, 0.66), 0.2, 0.4,
                    rim=(1.0, 0.9, 0.8), rim_strength=0.6)
    hair = material('Javelin elf chestnut hair', (0.35, 0.14, 0.05), 0.15, 0.4,
                    rim=(1.0, 0.7, 0.5), rim_strength=0.8, coat=0.3)
    eye = material('Javelin elf eyes', (0.05, 0.15, 0.10), roughness=0.2, coat=1.0)

    def body(x, y):
        bpy.ops.mesh.primitive_torus_add(major_radius=0.155, minor_radius=0.025, location=(x, y, 0.58))
        finish(bpy.context.object, leather, True, 'Javelin elf belt')
        block('Javelin elf pouch', (x + 0.12, y - 0.13, 0.52), (0.09, 0.05, 0.09), leather, 0.02)
        # A strap across the chest from the left shoulder to the right hip.
        tube('Javelin elf chest strap', [(x + 0.15, y - 0.06, 0.86), (x + 0.02, y - 0.17, 0.74),
                                         (x - 0.13, y - 0.13, 0.60)], [0.022] * 3, leather,
             sides=6, smooth=True)
        # Right hand (screen left) holding the javelin upright.
        shaft = (x - 0.30, y - 0.12)
        tube('Javelin elf shaft', [(shaft[0], shaft[1], 0.0), (shaft[0], shaft[1], 0.70),
                                   (shaft[0], shaft[1], 1.36)], [0.022, 0.022, 0.02], wood,
             sides=8, smooth=True)
        tube('Javelin elf head', [(shaft[0], shaft[1], 1.34), (shaft[0], shaft[1], 1.44),
                                  (shaft[0], shaft[1], 1.58)], [(0.06, 0.015), (0.055, 0.014), 0],
             iron, sides=4)
        # Bare arms with leather bracers on the forearms.
        tube('Javelin elf right arm', [(x - 0.17, y, 0.84), (x - 0.25, y - 0.06, 0.74),
                                       (x - 0.29, y - 0.11, 0.70)], [0.045, 0.04, 0.04], skin,
             sides=12, smooth=True)
        tube('Javelin elf right bracer', [(x - 0.25, y - 0.06, 0.745), (x - 0.285, y - 0.105, 0.705)],
             [0.05, 0.05], leather, sides=12, smooth=True)
        sphere('Javelin elf shoulder guard', (x - 0.17, y, 0.85), (0.07, 0.07, 0.04), leather, 16)
        sphere('Javelin elf right hand', (x - 0.30, y - 0.12, 0.70), (0.05, 0.05, 0.05), skin, 16)
        # Left hand on the hip, elbow out.
        tube('Javelin elf left arm', [(x + 0.17, y, 0.84), (x + 0.28, y + 0.02, 0.70),
                                      (x + 0.18, y - 0.06, 0.60)], [0.045, 0.04, 0.04], skin,
             sides=12, smooth=True)
        tube('Javelin elf left bracer', [(x + 0.265, y + 0.01, 0.68), (x + 0.20, y - 0.05, 0.61)],
             [0.05, 0.05], leather, sides=12, smooth=True)
        sphere('Javelin elf left hand', (x + 0.16, y - 0.07, 0.59), (0.05, 0.045, 0.045), skin, 16)

    def head(x, y):
        # Short hair with a few spiky tufts, tied back in a small tail.
        sphere('Javelin elf hair cap', (x, y + 0.05, 1.09), (0.15, 0.13, 0.13), hair, 32)
        for dx, dy in ((-0.08, -0.04), (0.0, -0.07), (0.08, -0.04), (-0.04, 0.04), (0.05, 0.05)):
            base = Vector((x + dx, y + dy, 1.16))
            cone('Javelin elf hair tuft', base, base + Vector((dx * 0.6, dy * 0.6 - 0.02, 0.08)),
                 0.05, 0, hair, 6, False)
        tube('Javelin elf ponytail', [(x, y + 0.14, 1.08), (x, y + 0.22, 1.00), (x, y + 0.25, 0.90)],
             [0.035, 0.045, 0], hair, sides=8, smooth=True)

    jerkin = material('Javelin elf leather jerkin', (0.36, 0.20, 0.09), 0.0, 0.55,
                      rim=(1.0, 0.75, 0.5), rim_strength=0.8)
    elf_figure(x, y, 'Javelin elf', robe, skin, eye, body, head, skirt=(0.21, 0.17, 0.14),
               torso=jerkin)


def collector_elf(x, y):
    """Collector Elf: a stout connoisseur who never leaves a light folding
    camp chair, in a deep teal robe, balding with side hair and a gold
    monocle, peering through a magnifying glass held in both hands (the
    rustless blade it gives is magic, not held), with a vase and a bundle of
    blades beside the chair.
    """
    robe = material('Collector elf teal robe', (0.02, 0.30, 0.30), 0.1, 0.45,
                    rim=(0.5, 1.0, 0.9), rim_strength=1.0, coat=0.3)
    gold = material('Collector elf gold', (1.0, 0.72, 0.22), roughness=0.25, metallic=0.8,
                    emission=(1.0, 0.62, 0.15), strength=0.4)
    wood = material('Collector elf pale chair wood', (0.70, 0.52, 0.30), 0.0, 0.5,
                    rim=(1.0, 0.85, 0.6), rim_strength=0.6)
    canvas = material('Collector elf canvas', (0.85, 0.80, 0.66), 0.05, 0.8,
                      rim=(1.0, 0.95, 0.85), rim_strength=0.5)
    lens = material('Collector elf lens', (0.85, 0.95, 1.0), 0.9, 0.05, coat=1.0,
                    rim=(0.8, 0.95, 1.0), rim_strength=1.5)
    skin = material('Collector elf skin', (0.96, 0.78, 0.64), 0.2, 0.4,
                    rim=(1.0, 0.9, 0.8), rim_strength=0.6)
    hair = material('Collector elf brown hair', (0.30, 0.20, 0.12), 0.1, 0.5)
    shoe = material('Collector elf shoes', (0.12, 0.06, 0.03), roughness=0.3, coat=0.8)
    steel = material('Collector elf stored blades', (0.80, 0.85, 0.92), roughness=0.2, metallic=0.6,
                     emission=(0.7, 0.85, 1.0), strength=0.4)
    vase = material('Collector elf vase', (0.15, 0.30, 0.65), 0.1, 0.2, coat=1.0,
                    rim=(0.7, 0.85, 1.0), rim_strength=0.8)
    eye = material('Collector elf eyes', (0.10, 0.08, 0.05), roughness=0.3, coat=1.0)

    def body(x, y):
        # Light folding camp chair: crossed thin legs, a canvas seat and back.
        for side in (-1, 1):
            sx = x + side * 0.30
            for a, b in (((sx, y - 0.24, 0.0), (sx, y + 0.22, 0.32)),
                         ((sx, y + 0.22, 0.0), (sx, y - 0.24, 0.32))):
                tube('Collector elf chair leg', [a, b], [0.022, 0.022], wood, sides=8, smooth=True)
            tube('Collector elf back post', [(sx, y + 0.22, 0.32), (sx, y + 0.30, 0.95)],
                 [0.022, 0.02], wood, sides=8, smooth=True)
            tube('Collector elf armrest', [(sx + side * 0.04, y + 0.24, 0.50),
                                           (sx + side * 0.04, y - 0.22, 0.48)], [0.02, 0.02], wood,
                 sides=8, smooth=True)
            tube('Collector elf armrest post', [(sx + side * 0.04, y - 0.22, 0.48),
                                                (sx, y - 0.22, 0.30)], [0.018, 0.018], wood, sides=8,
                 smooth=True)
        for dy in (-0.22, 0.22):
            tube('Collector elf seat rail', [(x - 0.30, y + dy, 0.32), (x + 0.30, y + dy, 0.32)],
                 [0.022, 0.022], wood, sides=8, smooth=True)
        block('Collector elf canvas seat', (x, y, 0.31), (0.58, 0.46, 0.025), canvas, 0.01)
        block('Collector elf canvas back', (x, y + 0.27, 0.72), (0.58, 0.025, 0.36), canvas, 0.01,
              (-0.12, 0, 0))
        for side in (-1, 1):
            # Robed thighs forward over the seat, shins down, shoes in front.
            tube('Collector elf thigh', [(x + side * 0.12, y, 0.42), (x + side * 0.13, y - 0.26, 0.42)],
                 [0.11, 0.10], robe, sides=16, smooth=True)
            tube('Collector elf shin', [(x + side * 0.13, y - 0.28, 0.40), (x + side * 0.13, y - 0.30, 0.08)],
                 [0.08, 0.06], robe, sides=16, smooth=True)
            sphere('Collector elf shoe', (x + side * 0.13, y - 0.35, 0.05), (0.06, 0.09, 0.05), shoe, 16)
            # Arms resting on the belly, both hands on the magnifier's handle.
            tube('Collector elf sleeve', [(x + side * 0.24, y, 0.84), (x + side * 0.30, y - 0.10, 0.70),
                                          (x + side * 0.10, y - 0.27, 0.64)], [0.08, 0.08, 0.08], robe,
                 sides=12, smooth=True)
            sphere('Collector elf hand', (x + side * 0.04, y - 0.30, 0.64), (0.055, 0.05, 0.05), skin, 16)
        sphere('Collector elf belly', (x, y - 0.08, 0.66), (0.24, 0.20, 0.20), robe, 32)
        # Magnifying glass raised before the chest, its lens facing the camera.
        tube('Collector elf magnifier handle', [(x, y - 0.31, 0.60), (x, y - 0.33, 0.74)],
             [0.022, 0.025], wood, sides=8, smooth=True)
        face_camera = (math.radians(30), 0, 0)
        bpy.ops.mesh.primitive_torus_add(major_radius=0.08, minor_radius=0.016,
                                         location=(x, y - 0.35, 0.83), rotation=face_camera)
        finish(bpy.context.object, gold, True, 'Collector elf magnifier rim')
        bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.075, depth=0.012,
                                            location=(x, y - 0.35, 0.83), rotation=face_camera)
        finish(bpy.context.object, lens, True, 'Collector elf magnifier lens')
        # Collected pieces beside the chair: a vase and a bundle of blades.
        tube('Collector elf vase', [(x + 0.52, y - 0.05, 0.0), (x + 0.52, y - 0.05, 0.12),
                                    (x + 0.52, y - 0.05, 0.26), (x + 0.52, y - 0.05, 0.34)],
             [0.07, 0.11, 0.05, 0.06], vase, sides=20, smooth=True)
        for k, dx in enumerate((-0.04, 0.0, 0.04)):
            tube('Collector elf stored blade', [(x - 0.50 + dx, y - 0.10 + k * 0.03, 0.0),
                                                (x - 0.46 + dx * 2, y - 0.08 + k * 0.03, 0.46)],
                 [(0.025, 0.008), 0], steel, sides=4)

    def head(x, y):
        # Balding top with hair left at the sides and back, and a gold monocle.
        for side in (-1, 1):
            sphere('Collector elf side hair', (x + side * 0.11, y + 0.04, 1.00), (0.06, 0.09, 0.07), hair, 16)
        sphere('Collector elf back hair', (x, y + 0.11, 1.00), (0.12, 0.05, 0.07), hair, 16)
        sphere('Collector elf double chin', (x, y - 0.06, 0.92), (0.11, 0.09, 0.05), skin, 16)
        bpy.ops.mesh.primitive_torus_add(major_radius=0.04, minor_radius=0.008,
                                         location=(x + 0.05, y - 0.15, 1.04),
                                         rotation=(math.pi / 2, 0, 0))
        finish(bpy.context.object, gold, True, 'Collector elf monocle')
        tube('Collector elf monocle chain', [(x + 0.09, y - 0.15, 1.02), (x + 0.12, y - 0.12, 0.92),
                                             (x + 0.13, y - 0.10, 0.86)], [0.006] * 3, gold, sides=4)

    elf_figure(x, y, 'Collector elf', robe, skin, eye, body, head, skirt=(0.27, 0.30, 0.24),
               skirt_z=(0.34, 0.45, 0.60), girth=1.35)


def lifebringer_elf(x, y):
    """Lifebringer Elf: drawn as a spirit or god rather than an elf. It floats
    on a bumpy white cloud that its slim robe sinks into, in softly glowing translucent
    ivory, with long white-gold hair (no beard and no pointed ears), a gold
    halo behind the head, offering in both hands an orb of soft green light.
    """
    robe = material('Lifebringer champagne robe', (0.85, 0.70, 0.40), 0.3, 0.3,
                    emission=(1.0, 0.85, 0.5), strength=0.04,
                    rim=(1.0, 0.9, 0.6), rim_strength=1.2, coat=0.5)
    cloud = material('Lifebringer cloud', (0.70, 0.76, 0.90), 0.2, 0.6,
                     rim=(1.0, 1.0, 1.0), rim_strength=1.0)
    gold = material('Lifebringer halo gold', (1.0, 0.75, 0.25), roughness=0.25, metallic=0.6,
                    emission=(1.0, 0.7, 0.2), strength=1.5)
    skin = material('Lifebringer skin', (0.96, 0.84, 0.72), 0.2, 0.4,
                    rim=(1.0, 0.95, 0.85), rim_strength=0.6)
    hair = material('Lifebringer white-gold hair', (0.95, 0.88, 0.62), 0.2, 0.3,
                    emission=(1.0, 0.9, 0.6), strength=0.03,
                    rim=(1.0, 0.95, 0.7), rim_strength=1.0)
    life = material('Lifebringer life light', (0.25, 0.9, 0.2), 0.3, 0.2,
                    emission=(0.3, 1.0, 0.25), strength=1.0)
    eye = material('Lifebringer eyes', (0.10, 0.20, 0.15), roughness=0.3, coat=1.0)

    def body(x, y):
        # A bumpy cumulus of separate puffs, so it reads as a cloud rather
        # than a flared skirt, with small wisps drifting beside it.
        for k, (px, py, pz, r) in enumerate((
                (0.0, 0.02, 0.22, 0.20), (-0.22, 0.06, 0.18, 0.16), (0.23, 0.04, 0.17, 0.17),
                (-0.12, -0.18, 0.15, 0.15), (0.13, -0.19, 0.16, 0.14), (0.0, 0.22, 0.17, 0.15),
                (-0.36, -0.04, 0.11, 0.11), (0.37, -0.06, 0.10, 0.12), (-0.02, -0.26, 0.10, 0.11),
                (0.30, 0.20, 0.11, 0.10), (-0.30, 0.20, 0.10, 0.10))):
            bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=r,
                                                  location=(x + px, y + py, pz))
            puff = finish(bpy.context.object, cloud, True, 'Lifebringer cloud puff')
            puff.scale = (1.0, 1.0, 0.8)
        for px, py, pz, r in ((-0.52, 0.06, 0.30, 0.06), (0.50, -0.10, 0.36, 0.05),
                              (0.46, 0.12, 0.20, 0.045)):
            sphere('Lifebringer cloud wisp', (x + px, y + py, pz), (r * 1.4, r, r * 0.8), cloud, 16)
        # Wide sleeves meeting before the chest, hands offering the orb.
        for side in (-1, 1):
            tube('Lifebringer sleeve', [(x + side * 0.18, y, 0.84), (x + side * 0.27, y - 0.10, 0.72),
                                        (x + side * 0.12, y - 0.24, 0.70)], [0.06, 0.08, 0.10], robe,
                 sides=14, smooth=True)
            sphere('Lifebringer hand', (x + side * 0.07, y - 0.27, 0.70), (0.05, 0.045, 0.04), skin, 16)
        sphere('Lifebringer life orb', (x, y - 0.34, 0.79), (0.095, 0.095, 0.095), life, 24)

    def head(x, y):
        # Long hair over the back of the head and down the back.
        sphere('Lifebringer hair cap', (x, y + 0.06, 1.08), (0.15, 0.13, 0.14), hair, 32)
        for dx in (-0.10, -0.035, 0.035, 0.10):
            tube('Lifebringer hair lock', [(x + dx, y + 0.08, 1.04), (x + dx * 1.4, y + 0.17, 0.84),
                                           (x + dx * 1.6, y + 0.20, 0.62)], [0.05, 0.05, 0], hair,
                 sides=8, smooth=True)
        # A halo standing behind the head.
        bpy.ops.mesh.primitive_torus_add(major_radius=0.22, minor_radius=0.018,
                                         location=(x, y + 0.14, 1.10))
        halo = finish(bpy.context.object, gold, True, 'Lifebringer halo')
        halo.rotation_euler = (math.pi / 2, 0, 0)

    elf_figure(x, y, 'Lifebringer', robe, skin, eye, body, head, skirt=(0.14, 0.16, 0.15),
               skirt_z=(0.26, 0.42, 0.58), ears=False)


def sylvan_elf(x, y):
    """Sylvan Elf: a farmer one step on the way to a harvest god, still an
    elf. A straw hat with a flower band, a spring green dress and a cream
    apron, sprouts at the feet; for the spirit, friend of the fairy
    companions: small translucent butterfly wings, a softly glowing veil over
    the hem, and a glowing pot of fairy nectar offered in both hands.
    """
    robe = material('Sylvan elf spring green dress', (0.20, 0.55, 0.12), 0.15, 0.45,
                    rim=(0.8, 1.0, 0.6), rim_strength=1.0, coat=0.3)
    apron = material('Sylvan elf cream apron', (0.88, 0.84, 0.70), 0.05, 0.7,
                     rim=(1.0, 1.0, 0.9), rim_strength=0.5)
    veil = material('Sylvan elf glowing veil', (0.55, 0.85, 0.50), 0.5, 0.25,
                    emission=(0.6, 1.0, 0.5), strength=0.12,
                    rim=(0.9, 1.0, 0.8), rim_strength=0.8)
    straw = material('Sylvan elf straw hat', (0.88, 0.70, 0.30), 0.0, 0.7,
                     rim=(1.0, 0.9, 0.6), rim_strength=0.6)
    flower = material('Sylvan elf flowers', (1.0, 0.55, 0.65), 0.1, 0.4)
    wing = material('Sylvan elf butterfly wings', (1.0, 0.70, 0.88), 0.0, 0.25,
                    emission=(1.0, 0.75, 0.9), strength=0.35,
                    rim=(1.0, 0.95, 1.0), rim_strength=1.6)
    nectar = material('Sylvan elf fairy nectar', (1.0, 0.65, 0.1), 0.3, 0.2,
                      emission=(1.0, 0.6, 0.1), strength=2.0)
    pot = material('Sylvan elf clay pot', (0.55, 0.30, 0.15), 0.0, 0.5, coat=0.5)
    leaf = material('Sylvan elf sprouts', (0.25, 0.70, 0.15), 0.2, 0.4)
    skin = material('Sylvan elf skin', (0.95, 0.78, 0.62), 0.2, 0.4,
                    rim=(1.0, 0.9, 0.8), rim_strength=0.6)
    hair = material('Sylvan elf honey hair', (0.70, 0.45, 0.15), 0.15, 0.4,
                    rim=(1.0, 0.85, 0.5), rim_strength=0.8)
    eye = material('Sylvan elf eyes', (0.10, 0.25, 0.08), roughness=0.2, coat=1.0)

    def body(x, y):
        # A softly glowing veil over the hem of the dress.
        tube('Sylvan elf veil', [(x, y, 0.01), (x, y, 0.10), (x, y, 0.20)], [0.27, 0.25, 0.22],
             veil, sides=32, smooth=True)
        block('Sylvan elf apron', (x, y - 0.17, 0.42), (0.26, 0.04, 0.40), apron, 0.03,
              (-0.12, 0, 0))
        tube('Sylvan elf apron string', [(x - 0.15, y - 0.10, 0.62), (x, y - 0.17, 0.62),
                                         (x + 0.15, y - 0.10, 0.62)], [0.018] * 3, apron, sides=6,
             smooth=True)
        # Hands offering a clay pot of glowing fairy nectar.
        for side in (-1, 1):
            tube('Sylvan elf sleeve', [(x + side * 0.18, y, 0.84), (x + side * 0.25, y - 0.08, 0.70),
                                       (x + side * 0.11, y - 0.24, 0.66)], [0.06, 0.06, 0.06], robe,
                 sides=12, smooth=True)
            sphere('Sylvan elf hand', (x + side * 0.08, y - 0.27, 0.66), (0.05, 0.045, 0.045), skin, 16)
        tube('Sylvan elf nectar pot', [(x, y - 0.31, 0.60), (x, y - 0.31, 0.66), (x, y - 0.31, 0.73)],
             [0.07, 0.085, 0.065], pot, sides=20, smooth=True)
        sphere('Sylvan elf nectar', (x, y - 0.31, 0.74), (0.06, 0.06, 0.035), nectar, 20)
        # Small translucent butterfly wings on the back, upper and lower pairs.
        for side in (-1, 1):
            for lower, (length, width, angle) in enumerate(((0.52, 0.30, 55), (0.36, 0.22, 15))):
                a = math.radians(angle)
                root = Vector((x + side * 0.05, y + 0.14, 0.78 - lower * 0.08))
                # The wing's face turns toward the 60-degree camera.
                along = Vector((side * math.cos(a), 0.15, math.sin(a))).normalized()
                across = Vector((0, -0.5, 0.866)).cross(along).normalized()
                n, verts = 20, []
                for t in range(n):
                    u = 2 * math.pi * t / n
                    verts.append(tuple(root + along * (length * (0.5 - 0.5 * math.cos(u)))
                                       + across * (width * 0.5 * math.sin(u))))
                faces = [tuple(range(n))]
                vane = mesh_object('Sylvan elf butterfly wing', verts, faces, wing, True)
                vane.modifiers.new('Wing thickness', 'SOLIDIFY').thickness = 0.01
        # Sprouts at the feet.
        for k in range(6):
            a = 2 * math.pi * k / 6 + 0.3
            base = Vector((x + 0.30 * math.cos(a), y + 0.30 * math.sin(a), 0.0))
            cone('Sylvan elf sprout', base, base + Vector((0.03 * math.cos(a), 0.03 * math.sin(a), 0.10)),
                 0.035, 0, leaf, 5, False)

    def head(x, y):
        # Honey hair in a braid down the back, under a wide straw hat with
        # a band of small flowers.
        sphere('Sylvan elf hair cap', (x, y + 0.06, 1.07), (0.15, 0.13, 0.13), hair, 32)
        tube('Sylvan elf braid', [(x, y + 0.12, 1.02), (x + 0.02, y + 0.18, 0.86), (x, y + 0.19, 0.70)],
             [0.045, 0.04, 0], hair, sides=8, smooth=True)
        bpy.ops.mesh.primitive_cylinder_add(vertices=40, radius=0.24, depth=0.02,
                                            location=(x, y + 0.02, 1.17))
        finish(bpy.context.object, straw, True, 'Sylvan elf hat brim')
        tube('Sylvan elf hat crown', [(x, y + 0.02, 1.17), (x, y + 0.02, 1.25), (x, y + 0.02, 1.28)],
             [0.14, 0.13, 0.11], straw, sides=24, smooth=True)
        for k in range(5):
            a = math.radians(-150 + k * 30)
            sphere('Sylvan elf hat flower', (x + 0.145 * math.cos(a), y + 0.02 + 0.145 * math.sin(a), 1.20),
                   (0.035, 0.035, 0.03), flower, 12)

    elf_figure(x, y, 'Sylvan elf', robe, skin, eye, body, head)


def pegasus(x, y):
    """Pegasus companion: a small, slender fairy horse of glowing pearl,
    hovering with legs tucked under, on wide feathered wings large for its
    body, with a full mane and gold hooves.
    """
    pearl = material('Pegasus fairy pearl', (0.78, 0.84, 0.95), 0.3, 0.22,
                     emission=(0.75, 0.9, 1.0), strength=0.04,
                     rim=(0.6, 0.95, 1.0), rim_strength=1.4, coat=0.8)
    wisp = material('Pegasus glowing mane', (0.15, 0.65, 1.0), 0.5, 0.2,
                    emission=(0.15, 0.6, 1.0), strength=0.7,
                    rim=(0.7, 0.95, 1.0), rim_strength=1.2)
    feather = material('Pegasus feathers', (0.58, 0.82, 1.0), 0.5, 0.25,
                       emission=(0.5, 0.8, 1.0), strength=0.1,
                       rim=(0.8, 0.97, 1.0), rim_strength=1.4)
    eye = material('Pegasus eyes', (0.02, 0.03, 0.06), roughness=0.2, coat=1.0)
    gold = material('Pegasus gold hooves', (1.0, 0.70, 0.22), roughness=0.3, metallic=0.7,
                    emission=(1.0, 0.62, 0.15), strength=0.8)
    # Slender body, neck and head melted into one shape; head toward -Y with
    # a short muzzle.
    body = [((0, -0.12, 0.58), 0.25), ((0, 0.02, 0.56), 0.26), ((0, 0.16, 0.55), 0.25),
            ((0, 0.30, 0.56), 0.23), ((0, -0.22, 0.70), 0.17), ((0, -0.28, 0.84), 0.16),
            ((0, -0.35, 0.95), 0.21), ((0, -0.47, 0.92), 0.15)]
    hooves = []
    for side in (-1, 1):
        # Slim legs stretched fore and aft as if galloping through the air, so
        # the gold hooves show past the body from above.
        for hip, knee, foot in (((0.07, -0.13, 0.50), (0.08, -0.25, 0.37), (0.08, -0.34, 0.25)),
                                ((0.09, 0.30, 0.45), (0.09, 0.44, 0.37), (0.09, 0.56, 0.31))):
            # The hip sits inside the chest and a joint fills each bend, so the
            # leg flows out of the body without a gap.
            mid = tuple((a + b) / 2 for a, b in zip(hip, knee))
            body += [((side * hip[0], hip[1], hip[2]), 0.15), ((side * mid[0], mid[1], mid[2]), 0.13),
                     ((side * knee[0], knee[1], knee[2]), 0.12), ((side * foot[0], foot[1], foot[2]), 0.10)]
            hooves.append((side * foot[0], foot[1] + (-0.03 if foot[1] < 0 else 0.03), foot[2] - 0.03))
    metaball_mesh('Pegasus body', [((x + px, y + py, pz), r) for (px, py, pz), r in body],
                  pearl, 0.012)
    for hx, hy, hz in hooves:
        bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.055, depth=0.06,
                                            location=(x + hx, y + hy, hz),
                                            rotation=(0.8 if hy < 0 else -0.8, 0, 0))
        finish(bpy.context.object, gold, True, 'Pegasus gold hoof')
    for side in (-1, 1):
        sphere('Pegasus eye', (x + side * 0.08, y - 0.40, 0.98), (0.03, 0.03, 0.035), eye, 12)
        cone('Pegasus ear', (x + side * 0.055, y - 0.31, 1.04), (x + side * 0.075, y - 0.27, 1.15),
             0.035, 0, pearl, 6, False)
    # A full mane of glowing wisps from the forelock down the neck, lifted as
    # it flows back, and a long tail.
    for k, dx in enumerate((-0.06, -0.03, 0.0, 0.03, 0.06)):
        tube('Pegasus mane', [(x + dx * 0.5, y - 0.36, 1.10), (x + dx, y - 0.24, 1.06 - abs(dx)),
                              (x + dx * 1.5, y - 0.10, 0.92 - abs(dx)), (x + dx * 2, y + 0.04, 0.80)],
             [0.05, 0.075, 0.06, 0], wisp, sides=8, smooth=True)
    tube('Pegasus forelock', [(x, y - 0.36, 1.10), (x, y - 0.45, 1.06), (x, y - 0.50, 0.99)],
         [0.05, 0.04, 0], wisp, sides=8, smooth=True)
    tube('Pegasus tail', [(x, y + 0.42, 0.60), (x + 0.04, y + 0.58, 0.56), (x + 0.02, y + 0.72, 0.44),
                          (x - 0.04, y + 0.82, 0.28)], [0.07, 0.09, 0.07, 0], wisp, sides=10,
         smooth=True)
    # Feathered wings, large for the body, raised up and swept back: a fan of
    # long flight feathers with a shorter layer of coverts over their roots.
    for side in (-1, 1):
        shoulder = Vector((x + side * 0.14, y + 0.04, 0.76))
        out, up = Vector((side, 0, 0)), Vector((0, 0.6, 0.8)).normalized()
        normal = out.cross(up)
        layers = [(range(6), lambda k: 20 + k * 16, lambda k: 0.62 + 0.06 * min(k, 5 - k) + 0.04 * k,
                   0.10, 0.0),
                  (range(5), lambda k: 28 + k * 17, lambda k: 0.34, 0.09, 0.012)]
        for keys, angle, length, width, lift in layers:
            for k in keys:
                a = math.radians(angle(k))
                along = out * math.cos(a) + up * math.sin(a)
                across = -out * math.sin(a) + up * math.cos(a)
                root = shoulder + normal * (lift + 0.003 * k)
                # Vane widening from the root, then closing in a round tip.
                def vane_width(f, cap=0.72):
                    if f <= cap:
                        return math.sin(math.pi / 2 * f / cap) ** 0.6
                    return math.sqrt(max(0.0, 1 - ((f - cap) / (1 - cap)) ** 2))
                n, verts = 18, [tuple(root)]
                for t in range(1, n + 1):
                    f = t / n
                    verts.append(tuple(root + along * (length(k) * f) + across * (width * vane_width(f))))
                for t in range(n - 1, 0, -1):
                    f = t / n
                    verts.append(tuple(root + along * (length(k) * f)
                                       - across * (width * 0.5 * vane_width(f))))
                faces = [(0, i, i + 1) for i in range(1, len(verts) - 1)]
                vane = mesh_object('Pegasus feather', verts, faces, feather, True)
                vane.modifiers.new('Feather thickness', 'SOLIDIFY').thickness = 0.012


def caltrop_plant(x, y):
    """Caltrop plant: a dandelion-like rosette and stem carrying a large
    round head, with spikes jutting from it here and there.

    The head and its spikes are close to the brick red the GUI fills
    scattered caltrop (x) cells with; the leaves and stem are a reddish olive.
    """
    leaf = material('Caltrop plant olive-red leaves', (0.21, 0.22, 0.05), 0.3, 0.3,
                    rim=(0.75, 0.9, 0.4), rim_strength=1.0, coat=0.4)
    stem = material('Caltrop plant olive-red stem', (0.25, 0.23, 0.06), 0.25, 0.3,
                    rim=(0.8, 0.9, 0.45), rim_strength=0.8)
    head = material('Caltrop plant bright brick red', (0.75, 0.18, 0.13), 0.1, 0.35,
                    rim=(1.0, 0.7, 0.6), rim_strength=1.2, coat=0.5)
    iron = head
    # A rosette of serrated dandelion leaves on the floor. Uneven angles,
    # lengths, lift and roll keep it from reading as a symmetric badge.
    angles = (0.2, 1.02, 1.98, 2.82, 3.62, 4.58, 5.40)
    lengths = (0.60, 0.50, 0.64, 0.46, 0.58, 0.52, 0.62)
    lifts = (0.05, 0.20, 0.10, 0.26, 0.04, 0.16, 0.12)
    rolls = (0.06, -0.08, 0.10, -0.04, 0.10, -0.07, -0.06)
    for a, length, lift, roll in zip(angles, lengths, lifts, rolls):
        along, side = Vector((math.cos(a), math.sin(a), 0)), Vector((-math.sin(a), math.cos(a), 0))
        outline = [Vector((x, y, 0.03))]
        teeth = 4
        for t in range(1, 2 * teeth + 1):
            f = t / (2 * teeth)
            width = 0.09 * math.sin(math.pi * f) * (1.6 if t % 2 else 0.8)
            outline.append(Vector((x, y, 0.03)) + along * (length * f) + side * width
                           + Vector((0, 0, lift * f * f + roll * f)))
        outline.append(Vector((x, y, 0.03)) + along * (length * 1.05)
                       + Vector((0, 0, lift * 1.1 + 0.01)))
        for t in range(2 * teeth, 0, -1):
            f = t / (2 * teeth)
            width = 0.09 * math.sin(math.pi * f) * (1.6 if t % 2 else 0.8)
            outline.append(Vector((x, y, 0.03)) + along * (length * f) - side * width
                           + Vector((0, 0, lift * f * f - roll * f)))
        verts = [tuple(v) for v in outline]
        faces = [(0, i, i + 1) for i in range(1, len(verts) - 1)]
        blade = mesh_object('Caltrop plant leaf', verts, faces, leaf, True)
        solid = blade.modifiers.new('Leaf thickness', 'SOLIDIFY')
        solid.thickness = 0.025
    # A slightly bowed stem up to the head.
    centre = Vector((x - 0.04, y + 0.02, 0.80))
    tube('Caltrop plant stem', [(x, y, 0.02), (x + 0.03, y, 0.30), (x - 0.01, y + 0.01, 0.52),
                                tuple(centre)], [0.05, 0.04, 0.04, 0.05], stem, sides=10,
         smooth=True)
    for k in range(6):
        a = 2 * math.pi * k / 6
        base = centre + Vector((0.10 * math.cos(a), 0.10 * math.sin(a), -0.26))
        cone('Caltrop plant sepal', base - Vector((0.06 * math.cos(a), 0.06 * math.sin(a), 0.06)),
             base + Vector((0.04 * math.cos(a), 0.04 * math.sin(a), 0.06)), 0.05, 0, leaf, 5, False)
    radius = 0.32
    sphere('Caltrop plant head', tuple(centre), (radius, radius, radius), head, 48)
    # Iron spikes here and there: spread evenly, then every other one kept
    # with varied lengths so the head looks irregular rather than a mace.
    count = 22
    for k in range(count):
        z = 1 - 2 * (k + 0.5) / count
        r = math.sqrt(1 - z * z)
        a = k * math.pi * (3 - math.sqrt(5))
        out = Vector((r * math.cos(a), r * math.sin(a), z))
        if k % 2 or out.z < -0.6:
            continue
        length = (0.20, 0.28, 0.24)[k % 3]
        cone('Caltrop spike', centre + out * (radius - 0.03), centre + out * (radius + length),
             0.065, 0, iron, 6, False)


def golem(x, y):
    """Stage 2 golem: chunky dark basalt blocks with glowing amber rune seams.

    Kept dark and rough so it never reads as the white marble walls. Tall,
    with the upper body leaning back so the chest and face turn up toward
    the 60-degree camera.
    """
    basalt = material('Golem basalt', (0.10, 0.10, 0.12), 0.1, 0.55,
                      rim=(0.55, 0.65, 0.85), rim_strength=1.0, coat=0.2)
    slate = material('Golem slate plates', (0.22, 0.21, 0.24), 0.1, 0.5,
                     rim=(0.65, 0.70, 0.90), rim_strength=0.8)
    rune = material('Golem amber runes', (1.0, 0.6, 0.1), emission=(1.0, 0.55, 0.08),
                    strength=6.0)
    for side in (-1, 1):
        block('Golem leg', (x + side * 0.20, y + 0.06, 0.17), (0.24, 0.26, 0.34), basalt, 0.03,
              (0, 0, side * 0.08))
        block('Golem foot', (x + side * 0.21, y - 0.02, 0.05), (0.28, 0.34, 0.10), slate, 0.02)
    block('Golem pelvis', (x, y + 0.04, 0.40), (0.50, 0.30, 0.16), slate, 0.03)
    upper = set(bpy.data.objects)
    # Upper body, built upright and then leaned back about the waist.
    block('Golem torso', (x, y, 0.75), (0.80, 0.34, 0.60), basalt, 0.05)
    block('Golem chest plate', (x, y - 0.18, 0.78), (0.50, 0.04, 0.40), slate, 0.02)
    for dx, dz, w, h in ((0, 0.90, 0.32, 0.035), (0, 0.66, 0.32, 0.035), (-0.15, 0.78, 0.035, 0.24),
                         (0.15, 0.78, 0.035, 0.24), (0, 0.78, 0.09, 0.09)):
        block('Golem rune', (x + dx, y - 0.205, dz), (w, 0.02, h), rune, 0.006)
    block('Golem head', (x, y - 0.06, 1.16), (0.30, 0.26, 0.24), slate, 0.04)
    block('Golem brow', (x, y - 0.19, 1.22), (0.32, 0.06, 0.06), basalt, 0.015)
    block('Golem eye slit', (x, y - 0.195, 1.15), (0.20, 0.02, 0.05), rune, 0.008)
    for side in (-1, 1):
        for i, (dx, dy, z, r) in enumerate(((0.48, 0.0, 1.02, 0.19), (0.36, 0.08, 1.10, 0.12))):
            bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=r,
                                                  location=(x + side * dx, y + dy, z),
                                                  rotation=(i * 0.7 + side, 0.4, i * 0.3))
            finish(bpy.context.object, basalt, False, 'Golem shoulder boulder')
        block('Golem upper arm', (x + side * 0.58, y, 0.80), (0.20, 0.22, 0.34), slate, 0.03,
              (0, side * 0.15, 0))
        block('Golem forearm', (x + side * 0.64, y - 0.04, 0.52), (0.22, 0.24, 0.30), basalt, 0.03,
              (0, side * 0.05, 0))
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=0.19,
                                              location=(x + side * 0.66, y - 0.08, 0.28),
                                              rotation=(0.5, side * 0.3, 0.2))
        finish(bpy.context.object, basalt, False, 'Golem fist')
        block('Golem knuckle rune', (x + side * 0.66, y - 0.265, 0.30), (0.12, 0.02, 0.03), rune,
              0.005, (0.3, 0, 0))
    bpy.context.view_layer.update()
    lean = (Matrix.Translation((x, y, 0.42)) @ Matrix.Rotation(-0.45, 4, 'X')
            @ Matrix.Translation((-x, -y, -0.42)))
    for obj in set(bpy.data.objects) - upper:
        obj.matrix_world = lean @ obj.matrix_world


def golem_rock(x, y):
    """Rubble a defeated Golem leaves on a floor cell, which becomes a wall:
    a low heap of the Golem's dark basalt and slate pieces, with a rune seam
    whose amber light is fading. About one cell wide.
    """
    basalt = material('Golem rock basalt', (0.10, 0.10, 0.12), 0.1, 0.55,
                      rim=(0.55, 0.65, 0.85), rim_strength=1.0, coat=0.2)
    slate = material('Golem rock slate', (0.22, 0.21, 0.24), 0.1, 0.5,
                     rim=(0.65, 0.70, 0.90), rim_strength=0.8)
    rune = material('Golem rock fading rune', (0.6, 0.35, 0.08), emission=(1.0, 0.55, 0.08),
                    strength=1.2)
    for i, (dx, dy, z, r) in enumerate(((0.0, 0.04, 0.17, 0.19), (-0.17, -0.04, 0.11, 0.13),
                                        (0.17, -0.06, 0.10, 0.12), (0.06, -0.17, 0.09, 0.11),
                                        (-0.10, 0.16, 0.10, 0.11), (0.03, 0.06, 0.34, 0.11))):
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=r, location=(x + dx, y + dy, z),
                                              rotation=(i * 0.9, i * 0.6 + 0.3, i * 1.3))
        chunk = finish(bpy.context.object, basalt, False, 'Golem rock chunk')
        chunk.scale = (1.1, 1.0, 0.8)
    block('Golem rock slate piece', (x - 0.07, y - 0.12, 0.20), (0.22, 0.05, 0.16), slate, 0.02,
          (0.5, 0.2, 0.4))
    block('Golem rock rune seam', (x - 0.07, y - 0.15, 0.20), (0.12, 0.02, 0.025), rune, 0.005,
          (0.5, 0.2, 0.4))


def rank_mark(x, y, count):
    """Empowered-rank mark: `count` raised serif apostrophes in near-white resin.

    The GUI tints it with the monster's strength color, like the text mark.
    """
    resin = material('Rank mark white resin', (0.92, 0.92, 0.92), 0.0, 0.32, coat=0.3,
                     rim=(1.0, 1.0, 1.0), rim_strength=0.6)
    start = set(bpy.data.objects)
    for i in range(count):
        dx = (i - (count - 1) / 2) * 0.30
        # A plump serif apostrophe: metaballs melt a ball and a thick tail,
        # curling down to the left to a round tip, into one smooth body.
        metaball_mesh('Rank mark %d' % i,
                      [((x + dx + px, y, pz), radius) for (px, pz), radius in
                       [((0.0, 0.48), 0.20), ((0.05, 0.42), 0.15), ((0.07, 0.36), 0.13),
                        ((0.06, 0.30), 0.11), ((0.03, 0.25), 0.095),
                        ((-0.01, 0.215), 0.08), ((-0.05, 0.195), 0.07)]], resin)
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
            'c': chimera, 'T': treasure, 'D': great_dragon, 'l': loop_watch, 'n': nomicon, 'o': ocular,
            'C': lambda x, y: chimera(x, y, True), 'F': lambda x, y: great_dragon(x, y, True),
            "'": lambda x, y: rank_mark(x, y, 1), '"': lambda x, y: rank_mark(x, y, 2),
            'g': golem, 'e': lambda x, y: erebus(x, y, False),
            'E': lambda x, y: erebus(x, y, True), 'X': caltrop_plant, 'p': pegasus,
            'H': high_elf, 'I': isolated_elf, 'J': javelin_elf, 'K': collector_elf,
            'L': lifebringer_elf, 'S': sylvan_elf, 'rock': golem_rock}
for char, name, x, y in ROW:
    start = set(bpy.data.objects)
    builders[char](x, y)
    character = set(bpy.data.objects) - start
    bpy.context.view_layer.update()
    pivot = Matrix.Translation((x, y, 0))
    yaw = MONSTER_YAW if char in 'aAbcdDCFgeEX' else PEGASUS_YAW if char == 'p' else 0
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
    width = 3.1 if char in ('D', 'F') else 1.2 if char in ("'", '"') else 1.85
    block(name + ' tile', (x, y, -0.05), (width, 2.6, 0.1), tile, 0.04)
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
label('ARLQ / STAGE 1-2 / HEROIC RESIN', (0.5, 1.85, 0.0), 0.2)
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
target = Vector((-0.5, (1.85 + ROW_Y[2] - 1.55) / 2, 0))
camera.location = target + Vector((0, -15 * math.cos(angle), 15 * math.sin(angle)))
camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
camera.data.type = 'ORTHO'
camera.data.ortho_scale = 20.8
scene.camera = camera
scene['sprite_centers'] = {char: list(pos) for char, pos in CENTERS.items()}
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'characters-angle60.blend'))
if '--save-only' not in sys.argv:
    # The preview's time goes mostly to Cycles treating every triangle of the
    # softly glowing meshes as a light; glows still show without that, so turn
    # it off for this group shot only (the saved scene, used for the sprites,
    # keeps it). This about halves the render time.
    for mat in bpy.data.materials:
        mat.cycles.emission_sampling = 'NONE'
    scene.render.filepath = str(OUT / 'preview-angle60.png')
    bpy.ops.render.render(write_still=True)
