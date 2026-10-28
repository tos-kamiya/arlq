"""Refined, more dramatic versions of the Stage 1-2 characters, companions and marks.

Run with: blender --background --threads 4 --python dev-samples/3d-stage1/build-heroic.py

This builds the three scenes (monsters, Stage 5 members and the others; see
heroic_groups.py) in parallel child processes and renders the group shot from
them; `-- --save-only` skips the group shot, and `-- --group monsters` (or
`members`, `others`) rebuilds just that one scene.

Keeps the accepted silhouettes (attached obtuse cones, angular bison and
dragon, two-head-tall legless player with a cloak) and adds glowing cores,
rim light, sharper features and stronger poses.
"""
from pathlib import Path
import math
import subprocess
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from heroic_groups import GROUPS, blend_path, group_of

OUT = Path(__file__).resolve().parent / 'heroic'
GROUP = sys.argv[sys.argv.index('--group') + 1] if '--group' in sys.argv else None
assert GROUP in (None, *GROUPS)
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

# The group shot lays the characters out on the game's own grid. Sprites are
# exported at 256 px per 2.6 units and drawn so that 186 px span 1.8 times
# 11 px (the 13 px sprite unit less 1 px padding each side), so one screen
# pixel is 186 / 1.8 / 11 * 2.6 / 256 units. Sprite-mode cells are 15 px wide
# (SPRITE_CELL_SIZE_X), 1.43 units, and 20 px tall; the 60-degree view
# shortens floor depth by sin 60, so a cell is 20 px / sin 60 = 2.20 units
# deep. The models are built at their in-game size, so on these cells they
# look as large as in the game.
SCREEN_PIXEL = 186 / 1.8 / 11 * 2.6 / 256
CELL_W = SCREEN_PIXEL * 15
CELL_D = SCREEN_PIXEL * 20 / math.sin(math.radians(60))
GRID_COLS, GRID_ROWS = 14, 8
# Back to front: the player and its sword variants, Stage 1 monsters and chest;
# the companions and elves; monsters in stage order, then Stage 5 members.
ORDER = [('@', 'PLAYER'), ('@c', 'PLAYER + SWORD'), ('@C', 'PLAYER + CURSED SWORD'),
         ('@K', 'PLAYER + K BLESSING'), ('a', 'AMOEBA'), ('A', 'RARE AMOEBA'), ('b', 'BISON'),
         ('c', 'CHIMERA'), ('d', 'COMODO DRAGON'), ('T', 'TREASURE CHEST'), ('M', 'MIMIC'), ('D', 'DRAGON'),
         ('l', 'LOOP'), ('n', 'NOMICON'), ('o', 'OCULAR'), ('p', 'PEGASUS'),
         ('H', 'HIGH ELF'), ('I', 'ISOLATED ELF'), ('J', 'JAVELIN ELF'), ('K', 'COLLECTOR ELF'),
         ('L', 'LIFEBRINGER ELF'), ('S', 'SYLVAN ELF'),
         ('C', 'RARE CHIMERA'), ('F', 'FIRE DRAKE'), ('g', 'GOLEM'), ('rock', 'GOLEM ROCK'),
         ('X', 'CALTROP PLANT'), ('e', 'EREBUS'), ('w', 'WYRM'), ('W', 'DREAD WYRM'),
         ('E', 'RARE EREBUS'), ('m', 'SPORE'), ('k', 'MARKSMAN'), ('V', 'VORTEX'),
         ('f', 'FLAME COBRA'), ('B', 'BUFFALO'),
         ('jester-light', 'JESTER LIGHT'), ('jester-medium', 'JESTER MEDIUM'),
         ('jester-dark', 'JESTER DARK'), ('healer-light', 'HEALER LIGHT'),
         ('healer-medium', 'HEALER MEDIUM'), ('healer-dark', 'HEALER DARK'),
         ('rogue-light', 'ROGUE LIGHT'), ('rogue-medium', 'ROGUE MEDIUM'),
         ('rogue-dark', 'ROGUE DARK'), ('knight-light', 'KNIGHT LIGHT'),
         ('knight-medium', 'KNIGHT MEDIUM'), ('knight-dark', 'KNIGHT DARK'),
         ('explorer-light', 'DUNGEON EXPLORER LIGHT'),
         ('explorer-medium', 'DUNGEON EXPLORER MEDIUM'),
         ('explorer-dark', 'DUNGEON EXPLORER DARK'),
         ('guardian-light', 'GUARDIAN LIGHT'), ('guardian-medium', 'GUARDIAN MEDIUM'),
         ('guardian-dark', 'GUARDIAN DARK')]
# Characters stand on every other cell, like the light squares of a
# chessboard, so neighbours in a row are two cells apart.
SLOTS = [(col, row) for row in range(GRID_ROWS) for col in range(GRID_COLS)
         if (col + row) % 2 == 0]
assert len(ORDER) <= len(SLOTS)


def cell_centre(col, row):
    return ((col - (GRID_COLS - 1) / 2) * CELL_W, -row * CELL_D)


ROW = [(char, name, *cell_centre(*slot)) for (char, name), slot in zip(ORDER, SLOTS)]
# Rank marks remain available for sprite export, outside the preview grid.
ROW += [("'", 'RANK 2', 50, 0), ('"', 'RANK 3', 55, 0)]
# Sprite export reads the character centres from here.
CENTERS = {char: (x, y) for char, _, x, y in ROW}
# Model sizes relative to the amoeba's first size, baked into the meshes.
# Sprites are exported and drawn at one common scale, so these decide how
# large each character appears; the boss dragon is built large, its wings
# spreading past its cell. The amoebas, comodo dragon and Erebuses were
# later shrunk to 0.9 of their first sizes.
SIZES = {'@': 1.42, '@c': 1.42, '@C': 1.42, '@K': 1.42, 'a': 0.9, 'A': 0.9, 'b': 1.09, 'B': 1.13, 'c': 1.2, 'd': 1.04, 'T': 1.66, 'M': 1.66, 'D': 1.44,
         'l': 1.4, 'n': 1.15, 'o': 1.25, 'C': 1.28, 'F': 1.52, "'": 1.7, '"': 1.7,
         'w': 1.52, 'W': 2.2, 'V': 1.4, 'k': 1.4, 'm': 1.35, 'f': 1.25, 'g': 1.3, 'e': 1.71, 'E': 1.98, 'X': 1.35, 'p': 1.3, 'H': 1.8, 'I': 1.6, 'J': 1.6, 'K': 1.6, 'L': 1.7, 'S': 1.6,
         'rock': 2.5, 'jester-light': 1.2, 'jester-medium': 1.2, 'jester-dark': 1.2,
         'healer-light': 1.2, 'healer-medium': 1.2, 'healer-dark': 1.2,
         'rogue-light': 1.35, 'rogue-medium': 1.35, 'rogue-dark': 1.35,
         'explorer-light': 1.42, 'explorer-medium': 1.42, 'explorer-dark': 1.42,
         'knight-light': 1.70, 'knight-medium': 1.70, 'knight-dark': 1.70,
         'guardian-light': 1.42, 'guardian-medium': 1.42, 'guardian-dark': 1.42}
# The pegasus companion turns further left, so its horse profile shows.
PEGASUS_YAW = math.radians(-45)
# Monsters and the chest turn slightly toward screen left; the player and companions face front.
MONSTER_YAW = math.radians(-30)
# Wyrms turn less, so both of their tall folded wings show.
WYRM_YAW = math.radians(-12)


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

def companion_green(name, strength=0.3, trim=False):
    """Translucent, softly glowing green resin that every companion (n, o, l,
    p) is made of; `trim` is a deeper green for details set on that body."""
    if trim:
        return material(name, (0.01, 0.25, 0.08), 0.3, 0.15, emission=(0.02, 0.35, 0.1),
                        strength=strength, rim=(0.3, 1.0, 0.5), rim_strength=0.8, coat=0.8)
    return material(name, (0.22, 0.85, 0.42), 0.6, 0.15, emission=(0.2, 0.9, 0.4),
                    strength=strength, rim=(0.6, 1.0, 0.7), rim_strength=1.2, coat=0.8)


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
    # The plain amoeba's body is a size smaller than the rare one's; its
    # nucleus and pupil keep the same size and only move with the body.
    k = 1.0 if rare else 0.87
    body = sphere('Membrane', (x, y, 0.40 * k), (0.72 * k, 0.65 * k, 0.36 * k), shell, 64)
    wobble = body.modifiers.new('Organic wobble', 'DISPLACE')
    texture = bpy.data.textures.new('Membrane wobble', 'CLOUDS')
    texture.noise_scale = 0.55
    wobble.texture = texture
    wobble.strength = 0.05 * k
    wobble.mid_level = 0.5
    # Accepted obtuse cones (r 0.34, depth 0.25), pulled 0.06 into the body.
    for angle in range(0, 360, 60):
        r = math.radians(angle)
        cone('Radial cone', (x + 0.64 * k * math.cos(r), y + 0.58 * k * math.sin(r), 0.32 * k),
             (x + 0.89 * k * math.cos(r), y + 0.83 * k * math.sin(r), 0.32 * k), 0.34 * k, 0,
             cone_mat)
    # A glowing eye-like nucleus visible through the shell.
    glow = material('Nucleus glow', core, emission=core, strength=5.0)
    sphere('Nucleus', (x, y - 0.12 * k, 0.47 * k), (0.24, 0.22, 0.18), glow)
    sphere('Nucleus slit pupil', (x, y - 0.25 * k, 0.56 * k), (0.045, 0.05, 0.13), obsidian)
    vacuole = material('Vacuole', (1, 1, 1), 0.3, 0.1,
                       emission=core, strength=1.5)
    for dx, dy, s in ((-0.36, 0.18, 0.08), (0.33, 0.24, 0.065), (0.12, 0.34, 0.05)):
        sphere('Vacuole', (x + dx * k, y + dy * k, 0.52 * k), (s * k, s * k, s * 0.8 * k),
               vacuole, 24)
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
    # Shoulder hump, tapering rump; head lowered for a charge. The body is
    # built 0.78 as wide as at first (`slim`), lean beside the heavier
    # Buffalo `B`.
    slim = 0.78
    soften(loft('Bison torso', x, y,
                [(along, w * slim, z, h) for along, w, z, h in
                 [(-0.42, 0.50, 0.50, 0.32), (-0.18, 0.60, 0.62, 0.42),
                  (0.10, 0.55, 0.58, 0.36), (0.45, 0.42, 0.47, 0.27),
                  (0.70, 0.30, 0.42, 0.20)]], hide), 0.09)
    # A modest shaggy hump: a few low-poly clumps over the shoulders and brow,
    # kept small so the bison does not look too strong.
    clumps = [(0, -0.28, 0.90, 0.25), (-0.22, -0.22, 0.84, 0.19), (0.22, -0.22, 0.84, 0.19),
              (0, -0.04, 0.86, 0.21), (0, -0.52, 0.76, 0.19)]
    for i, (dx, dy, z, r) in enumerate(clumps):
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=r * 0.85,
                                              location=(x + dx * slim, y + dy, z * 0.95),
                                              rotation=(i * 0.7, i * 1.3, i * 0.4))
        clump = finish(bpy.context.object, mane, False, 'Bison mane clump')
        clump.scale = (1.0, 1.1, 0.8)
    soften(loft('Bison lowered head', x, y,
                [(-0.92, 0.25, 0.34, 0.17), (-0.72, 0.34, 0.44, 0.24),
                 (-0.52, 0.34, 0.52, 0.25)], hide), 0.04)
    soften(loft('Bison muzzle', x, y,
                [(-0.98, 0.18, 0.30, 0.10), (-0.86, 0.22, 0.32, 0.13)], obsidian), 0.03)
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
            block('Bison hoof', (x + side * 0.40 * slim, y + dy, 0.13), (0.17, 0.24, 0.24),
                  obsidian, 0.04)
    tube('Bison tail', [(x, y + 0.66, 0.55), (x + 0.06, y + 0.80, 0.48), (x + 0.10, y + 0.86, 0.30)],
         [0.05, 0.04, 0.07], mane, sides=6)


def buffalo(x, y):
    # A darker, browner resin than the Bison's amber, with near-black horns.
    hide = material('Buffalo dark chestnut resin', (0.34, 0.13, 0.07), 0.45, 0.22,
                    rim=(1.0, 0.6, 0.4), rim_strength=1.3, coat=0.6)
    # Matte horn: a glossy coat mirrored the key light as a white band on
    # the boss's top.
    horn = material('Buffalo black horn', (0.035, 0.03, 0.028), 0.0, 0.6, coat=0.1,
                    rim=(0.85, 0.8, 0.75), rim_strength=0.9)
    eye = material('Buffalo pale gold eyes', (1.0, 0.75, 0.2), emission=(1.0, 0.75, 0.2),
                   strength=12.0)
    # Broad, level back without a hump; the head is held out ahead on a
    # thick neck, unlike the Bison's lowered charge.
    soften(loft('Buffalo torso', x, y,
                [(-0.45, 0.46, 0.50, 0.28), (-0.20, 0.56, 0.52, 0.32),
                 (0.10, 0.56, 0.52, 0.32), (0.42, 0.52, 0.50, 0.29),
                 (0.66, 0.38, 0.47, 0.22)], hide), 0.09)
    soften(loft('Buffalo head', x, y,
                [(-1.00, 0.24, 0.46, 0.15), (-0.86, 0.32, 0.52, 0.20),
                 (-0.66, 0.36, 0.58, 0.24), (-0.46, 0.40, 0.60, 0.26)], hide), 0.04)
    soften(loft('Buffalo muzzle', x, y,
                [(-1.12, 0.20, 0.42, 0.09), (-1.00, 0.25, 0.45, 0.12)], obsidian), 0.03)
    # The horns' bases meet over the brow in a helmet-like boss: two
    # mounded halves with a shallow dip between them.
    for side in (-1, 1):
        sphere('Buffalo boss', (x + side * 0.17, y - 0.78, 0.80), (0.24, 0.16, 0.13), horn, 24)
    for side in (-1, 1):
        # Thick horns droop outward from the boss, then hook up and forward.
        horn_path = [(0.28, -0.78, 0.80), (0.48, -0.78, 0.74), (0.64, -0.77, 0.58),
                     (0.72, -0.84, 0.44), (0.74, -0.96, 0.50), (0.70, -1.05, 0.64)]
        tube('Buffalo horn', [(x + side * px, y + py, pz) for px, py, pz in horn_path],
             [0.15, 0.13, 0.105, 0.08, 0.055, 0], horn, sides=10, smooth=True)
        sphere('Buffalo eye', (x + side * 0.26, y - 0.92, 0.58), (0.055, 0.04, 0.035), eye, 16)
        for dy in (-0.32, 0.46):
            block('Buffalo hoof', (x + side * 0.40, y + dy, 0.13), (0.24, 0.30, 0.26),
                  obsidian, 0.04)
    tube('Buffalo tail', [(x, y + 0.66, 0.60), (x + 0.04, y + 0.82, 0.50), (x + 0.07, y + 0.88, 0.32)],
         [0.04, 0.03, 0.06], hide, sides=6)

def dragon(x, y):
    # Deep cobalt like the wyrm's sapphire. The low body is seen mostly at a
    # grazing angle, so a weak rim and coat keep the facets' shading, and
    # rougher scales keep its flat back from mirroring the lights in white.
    scales = material('Dragon cobalt scales', (0.015, 0.07, 0.32), 0.25, 0.4,
                      rim=(0.4, 0.8, 1.0), rim_strength=0.6, coat=0.2)
    belly = material('Dragon pale crest', (0.45, 0.65, 0.90), 0.3, 0.2,
                     rim=(0.7, 0.9, 1.0), rim_strength=0.8)
    eye = material('Dragon gold eyes', (1.0, 0.8, 0.1), emission=(1.0, 0.75, 0.1),
                   strength=25.0)
    # One continuous body, snout to a sinuous tail, with softly rounded facets.
    spine = [(0.00, -1.00, 0.26), (0.00, -0.86, 0.30), (0.00, -0.68, 0.34), (0.02, -0.50, 0.33),
             (0.03, -0.28, 0.36), (0.01, 0.02, 0.37), (-0.05, 0.30, 0.33), (-0.15, 0.55, 0.27),
             (-0.14, 0.78, 0.21), (0.04, 0.96, 0.16), (0.26, 1.04, 0.12), (0.40, 1.04, 0.10)]
    radii = [(0.08, 0.05), (0.17, 0.10), (0.22, 0.14), (0.17, 0.12), (0.31, 0.19), (0.34, 0.21),
             (0.27, 0.17), (0.17, 0.12), (0.11, 0.08), (0.07, 0.05), (0.035, 0.03), 0]
    soften(tube('Dragon body', [(x + px, y + py, pz) for px, py, pz in spine], radii, scales,
                sides=8, twist=math.pi / 8), 0.025)
    for side in (-1, 1):
        # Brow ridge over each glowing eye gives a scowl.
        cone('Dragon brow', (x + side * 0.08, y - 0.78, 0.45),
             (x + side * 0.24, y - 0.62, 0.50), 0.05, 0, belly, 5, False)
        sphere('Dragon eye', (x + side * 0.15, y - 0.76, 0.42), (0.05, 0.045, 0.035), eye, 16)
        for dy, back in ((-0.24, -0.16), (0.24, 0.12)):
            hip = (x + side * 0.22, y + dy, 0.34)
            knee = (x + side * 0.55, y + dy + back * 0.3, 0.36)
            foot = (x + side * 0.66, y + dy + back, 0.08)
            soften(tube('Dragon splayed leg', [hip, knee, foot], [0.12, 0.09, 0.07],
                        scales, sides=6), 0.018)
            sphere('Dragon foot', foot, (0.10, 0.12, 0.05), scales, 12, False)
    # A low crest along the spine, kept as a single smooth fin.
    crest = [(x + px, y + py, pz + rz) for (px, py, pz), r in zip(spine[3:9], radii[3:9])
             for rz in [r[1] + 0.02]]
    tube('Dragon dorsal crest', crest, [(0.025, 0.05)] * len(crest), belly, sides=4)


def chimera_sword_materials(cursed):
    """Blade and hilt of the chimeras' swords: pale glowing steel and gold
    for the chimera's, black steel glowing red and iron for the cursed one."""
    if cursed:
        steel = material('Cursed sword black steel', (0.04, 0.03, 0.04), 0.0, 0.15,
                         emission=(0.9, 0.05, 0.02), strength=0.6, metallic=0.6,
                         rim=(1.0, 0.15, 0.05), rim_strength=4.0)
        hilt = material('Cursed sword iron hilt', (0.25, 0.22, 0.24), roughness=0.3,
                        metallic=1.0)
    else:
        steel = material('Chimera sword steel', (0.85, 0.92, 1.0), 0.3, 0.08,
                         emission=(0.7, 0.85, 1.0), strength=0.8, metallic=0.5,
                         rim=(0.9, 0.95, 1.0), rim_strength=1.5)
        hilt = material('Chimera sword hilt', (1.0, 0.68, 0.18), roughness=0.25, metallic=1.0)
    return steel, hilt


def chimera_blade(name, base, tip, width, steel):
    """A flat blade narrowing steadily from `base` to a sharp point at `tip`,
    an acute isosceles triangle seen from above."""
    return tube(name, [base, tip], [(width, width * 0.2), 0], steel, sides=4)


def player(x, y, sword=None):
    """The player. `sword` picks the blade in the right hand: None for the
    player's own broad short sword, 'blessed' for the same sword glowing blue
    after the Collector Elf's blessing, 'c' or 'C' for the chimera's or the
    cursed chimera's sword taken from them."""
    # Plate armour in bluish steel rather than the first frosted crystal,
    # which looked more like a spacesuit.
    tunic = material('Player steel plate', (0.55, 0.63, 0.74), roughness=0.32, metallic=0.8,
                     rim=(0.6, 0.85, 1.0), rim_strength=0.8)
    helm = material('Player steel helm', (0.62, 0.70, 0.80), roughness=0.28, metallic=0.85,
                    rim=(0.7, 0.9, 1.0), rim_strength=0.9)
    # Midnight blue so the yellow and red low-LP ground discs stand out.
    cape = material('Player midnight cloak', (0.025, 0.05, 0.16), 0.15, 0.4,
                    rim=(0.25, 0.45, 1.0), rim_strength=0.6)
    # Trim and sword are plain dark iron rather than precious metal.
    iron = material('Player dark iron trim', (0.16, 0.16, 0.18), roughness=0.35, metallic=1.0)
    visor = material('Player visor glow', (0.3, 0.9, 1.0), emission=(0.1, 0.75, 1.0),
                     strength=2.5)
    if sword == 'blessed':
        blade = material('Player blessed blade', (0.10, 0.35, 1.0), roughness=0.3,
                         metallic=0.3, emission=(0.03, 0.30, 1.0), strength=1.5,
                         rim=(0.2, 0.6, 1.0), rim_strength=2.0)
    else:
        blade = material('Player iron blade', (0.62, 0.63, 0.66), roughness=0.4, metallic=0.55,
                         rim=(0.85, 0.9, 1.0), rim_strength=0.8)
    # About three heads tall: a 0.34-tall head, a cylinder body about as
    # tall, and two legs below it ending in small boots.
    body_start = set(bpy.data.objects)
    legs = material('Player steel greaves', (0.45, 0.52, 0.62), roughness=0.35, metallic=0.8,
                    rim=(0.6, 0.8, 1.0), rim_strength=0.6)
    for side in (-1, 1):
        tube('Player leg', [(x + side * 0.10, y, 0.36), (x + side * 0.10, y - 0.01, 0.18),
                            (x + side * 0.10, y - 0.01, 0.06)], [0.085, 0.075, 0.065], legs,
             sides=16, smooth=True)
        sphere('Player boot', (x + side * 0.10, y - 0.03, 0.04), (0.075, 0.09, 0.045), iron, 20)
    # The body is an oval, wider than deep (`flat`), so it does not look like
    # a drum from above; the belt and seams follow it.
    flat = 0.72
    bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=0.24, depth=0.36,
                                        location=(x, y, 0.48))
    torso = finish(bpy.context.object, tunic, True, 'Player cylinder torso')
    torso.scale.y = flat
    for face in torso.data.polygons:
        face.use_smooth = len(face.vertices) == 4
    torso.data.use_auto_smooth = True
    bevel = torso.modifiers.new('Rounded rims', 'BEVEL')
    bevel.width = 0.06
    bevel.segments = 5
    bpy.ops.mesh.primitive_torus_add(major_radius=0.245, minor_radius=0.03,
                                     location=(x, y, 0.36))
    finish(bpy.context.object, iron, True, 'Player belt').scale.y = flat
    block('Player buckle', (x, y - 0.245 * flat - 0.02, 0.36), (0.09, 0.03, 0.07), iron, 0.012)
    # Seams between the breastplate's lames.
    for z in (0.48, 0.57):
        bpy.ops.mesh.primitive_torus_add(major_radius=0.243, minor_radius=0.011,
                                         location=(x, y, z))
        finish(bpy.context.object, iron, True, 'Player plate seam').scale.y = flat
    for side in (-1, 1):
        arm = block('Player arm', (x + side * 0.255, y - 0.06, 0.48),
                    (0.14, 0.16, 0.30), tunic, 0.06)
        arm.rotation_euler.y = -side * 0.10
        # Broad pauldrons over the shoulders, and couters on the elbows.
        sphere('Player pauldron', (x + side * 0.27, y - 0.05, 0.63), (0.14, 0.14, 0.07), iron, 24)
        sphere('Player couter', (x + side * 0.275, y - 0.10, 0.46), (0.075, 0.07, 0.06), iron, 20)
    # Short sword in the right hand (screen left), held low and outward.
    hand = Vector((x - 0.30, y - 0.13, 0.34))
    if sword in ('c', 'C'):
        # The chimera's longer, tapering sword, with its own hilt. Held by
        # the player it also shows the sword status, so it is drawn 1.3
        # times as large as in the chimeras' jaws.
        steel, hilt = chimera_sword_materials(sword == 'C')
        size = 1.3
        ahead = Vector((-0.34, -0.30, -0.10)).normalized() * size
        across = ahead.cross(Vector((0, 0, 1))).normalized() * size
        chimera_blade('Player chimera sword blade', hand + ahead * 0.05, hand + ahead * 0.58,
                      0.075 * size, steel)
        tube('Player chimera sword guard', [hand + across * 0.09, hand - across * 0.09],
             [0.025 * size, 0.025 * size], hilt, sides=6)
        sphere('Player chimera sword pommel', tuple(hand - ahead * 0.10),
               (0.035 * size,) * 3, hilt, 12)
    else:
        tip = hand + Vector((-0.34, -0.30, -0.10)) * 0.8
        tube('Player sword blade', [hand + (tip - hand) * 0.12, tip * 0.94 + hand * 0.06, tip],
             [(0.075, 0.016), (0.06, 0.014), 0], blade, sides=4)
        tube('Player sword guard', [hand + Vector((0.07, -0.08, 0)),
                                    hand + Vector((-0.08, 0.06, 0))],
             [0.025, 0.025], iron, sides=6)
    # Cloak: hugs the shoulders, drifts back and sideways toward the hem.
    columns, rows = 25, 8
    vertices = []
    for row in range(rows):
        t = row / (rows - 1)
        for col in range(columns):
            u = col / (columns - 1) * 2 - 1
            angle = u * math.radians(95)
            radius = 0.26 + 0.10 * t
            depth = flat + (1 - flat) * t
            vertices.append((x + radius * math.sin(angle) + 0.05 * t * t,
                             y + radius * depth * math.cos(angle) + 0.21 * t * t,
                             0.64 - 0.50 * t + 0.045 * t * math.cos(u * math.pi * 3)))
    faces = [(r * columns + c, r * columns + c + 1, (r + 1) * columns + c + 1, (r + 1) * columns + c)
             for r in range(rows - 1) for c in range(columns - 1)]
    cloak = mesh_object('Player cloak', vertices, faces, cape, True)
    cloak.modifiers.new('Smooth drape', 'SUBSURF').levels = 2
    solid = cloak.modifiers.new('Fabric thickness', 'SOLIDIFY')
    solid.thickness = 0.03
    solid.offset = 0
    hem = [vertices[(rows - 1) * columns + c] for c in range(columns)]
    tube('Player cloak hem trim', hem, [0.018] * columns, iron, sides=6, smooth=True)
    # Like the elves (`elf_figure()`), the body is stretched upward, as
    # heights shrink to half in the 60-degree view, and the helmeted head is
    # tilted back at the neck so the visor faces the camera.
    start = set(bpy.data.objects)
    bpy.context.view_layer.update()
    for obj in start - body_start:
        obj.matrix_world = (Matrix.Translation((x, y, 0)) @ Matrix.Diagonal((1, 1, ELF_STRETCH, 1))
                            @ Matrix.Translation((-x, -y, 0)) @ obj.matrix_world)
    block('Player head', (x, y - 0.04, 0.83), (0.34, 0.32, 0.34), helm, 0.10)
    # A dark iron faceplate with a glowing eye window, wider than a real
    # helm's slit so the face reads at sprite size, and a crest running front
    # to back over the top.
    block('Player faceplate', (x, y - 0.195, 0.80), (0.28, 0.04, 0.14), iron, 0.015)
    block('Player eye window', (x, y - 0.218, 0.81), (0.22, 0.012, 0.05), visor, 0.008)
    block('Player helm crest', (x, y - 0.02, 1.005), (0.05, 0.30, 0.05), iron, 0.015)
    for side in (-1, 1):
        cone('Player helm fin', (x + side * 0.15, y, 0.90),
             (x + side * 0.27, y + 0.11, 1.06), 0.055, 0, iron, 4, False)
    neck = Vector((x, y, 0.66))
    transform_new(start, Matrix.Translation((0, 0, neck.z * (ELF_STRETCH - 1)))
                  @ Matrix.Translation(neck) @ Matrix.Rotation(-0.6, 4, 'X')
                  @ Matrix.Translation(-neck))

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
    steel, hilt = chimera_sword_materials(cursed)
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
    # Flat blade so its broad face shows from above, tapering to a point.
    chimera_blade('Chimera sword blade', (x - 0.20, y - 0.88, 0.50), (x - 0.80, y - 0.88, 0.50),
                  0.085, steel)
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


def treasure(x, y, mimic=False):
    """Treasure chest (T), or with `mimic` the revealed Mimic (M), a kind of
    golem: the chest's own shape in the golem's dark basalt and slate, its
    lid only slightly open on a black inside where two round amber lights
    glow, and an amber rune for the lock.
    """
    if mimic:
        # Rougher and with a weaker rim than the golem's own stone, as the
        # chest's broad smooth faces would otherwise shine pale grey.
        wood = material('Mimic basalt', (0.08, 0.08, 0.10), 0.05, 0.75,
                        rim=(0.55, 0.65, 0.85), rim_strength=0.5)
        gold = material('Mimic slate bands', (0.20, 0.19, 0.22), 0.05, 0.65,
                        rim=(0.65, 0.70, 0.90), rim_strength=0.5)
        gem = material('Mimic amber rune', (1.0, 0.6, 0.1), emission=(1.0, 0.55, 0.08),
                       strength=6.0)
        dark = material('Mimic black inside', (0.0, 0.0, 0.005), roughness=0.9)
        block('Mimic black inside', (x, y, 0.47), (0.86, 0.54, 0.06), dark, 0.02)
        # Two round amber lights peering out from the dark, set toward the
        # front so they show under the lid's raised edge.
        for side in (-1, 1):
            sphere('Mimic glowing eye', (x + side * 0.15, y - 0.16, 0.53), (0.05, 0.035, 0.035),
                   gem, 16)
    else:
        wood = material('Chest mahogany resin', (0.40, 0.09, 0.03), 0.12, 0.28,
                        rim=(1.0, 0.55, 0.25), rim_strength=0.8, coat=0.8)
        gold = material('Chest gold bands', (1.0, 0.68, 0.18), roughness=0.22, metallic=1.0)
        light = material('Chest treasure glow', (1.0, 0.8, 0.3), emission=(1.0, 0.72, 0.2),
                         strength=3.0)
        gem = material('Chest ruby', (1.0, 0.08, 0.12), 0.8, 0.02,
                       emission=(1.0, 0.1, 0.1), strength=1.5, coat=1.0)
        # Gold glow inside the unlocked chest, with a few coins on the pile.
        block('Chest treasure glow', (x, y, 0.47), (0.86, 0.54, 0.06), light, 0.02)
        for i, (dx, dy) in enumerate(((-0.22, -0.08), (0.05, 0.10), (0.24, -0.04),
                                      (-0.04, -0.14))):
            bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=0.07, depth=0.02,
                                                location=(x + dx, y + dy, 0.515),
                                                rotation=(0.3 * (i - 1.5), 0.2 * i, 0))
            finish(bpy.context.object, gold, True, 'Chest gold coin')
    block('Chest box', (x, y, 0.27), (1.0, 0.66, 0.46), wood, 0.05)
    # Rounded lid: a half cylinder along the box, flat underneath, so it
    # stays a half circle seen from the side when tilted open.
    def half_cylinder(name, dx, radius, length, mat):
        segments, verts = 24, []
        for end in (-0.5, 0.5):
            for k in range(segments + 1):
                a = math.pi * k / segments
                verts.append((x + dx + end * length, y + radius * math.cos(a),
                              0.50 + 0.75 * radius * math.sin(a)))
        n = segments + 1
        faces = [(k, k + 1, n + k + 1, n + k) for k in range(segments)]
        faces += [tuple(reversed(range(n))), tuple(range(n, 2 * n)), (0, n, 2 * n - 1, n - 1)]
        return mesh_object(name, verts, faces, mat, True)

    lid = half_cylinder('Chest rounded lid', 0, 0.33, 0.98, wood)
    bevel = lid.modifiers.new('Soft lid rims', 'BEVEL')
    bevel.width = 0.03
    bevel.segments = 3
    # Bands wrap only the outside: a hollow half ring over the lid, and a
    # plate on the box's front and back, so none crosses the opening.
    def band_arc(name, dx, inner, outer, width, mat):
        segments, verts = 24, []
        for k in range(segments + 1):
            a = math.pi * k / segments
            for r in (outer, inner):
                for end in (-0.5, 0.5):
                    verts.append((x + dx + end * width, y + r * math.cos(a),
                                  0.50 + 0.75 * r * math.sin(a)))
        faces = []
        for k in range(segments):
            o0, i0, o1, i1 = 4 * k, 4 * k + 2, 4 * k + 4, 4 * k + 6
            faces += [(o0, o0 + 1, o1 + 1, o1), (i0, i1, i1 + 1, i0 + 1),
                      (o0, o1, i1, i0), (o0 + 1, i0 + 1, i1 + 1, o1 + 1)]
        last = 4 * segments
        faces += [(0, 2, 3, 1), (last, last + 1, last + 3, last + 2)]
        return mesh_object(name, verts, faces, mat, True)

    lid_parts = [lid]
    for dx in (-0.36, 0.36):
        lid_parts.append(band_arc('Chest lid band', dx, 0.325, 0.35, 0.09, gold))
        for side in (-1, 1):
            block('Chest box band', (x + dx, y + side * 0.335, 0.27), (0.09, 0.03, 0.47), gold,
                  0.012)
    bpy.context.view_layer.update()
    hinge = Matrix.Translation((x, y + 0.33, 0.50))
    # Both lids are open only a little, on the treasure's glow or the
    # mimic's black inside.
    opening = hinge @ Matrix.Rotation(-0.50, 4, 'X') @ hinge.inverted()
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
        # Komodo-dragon olive-bronze hide, apart from the companions' green.
        scales = material('Dragon olive-bronze scales', (0.15, 0.14, 0.07), 0.25, 0.3,
                          rim=(0.65, 0.60, 0.40), rim_strength=1.0, coat=0.8)
        belly = material('Dragon dusky ochre belly', (0.46, 0.38, 0.22), 0.25, 0.3,
                         rim=(0.85, 0.75, 0.5), rim_strength=0.6)
        wing = material('Dragon wing membrane', (0.30, 0.22, 0.09), 0.6, 0.3,
                        emission=(0.35, 0.18, 0.04), strength=0.15,
                        rim=(0.80, 0.65, 0.35), rim_strength=0.9)
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



def wyrm(x, y, dread=False):
    """Wyrm (w) and Dread Wyrm (W): lean two-legged reptiles whose forelimbs
    are huge wings, folded at rest into an M seen from the front: the wrists
    peak high above the shoulders and four finger bones each fall outward
    and down, with see-through membranes.

    The wyrm has sapphire scales, pale blue wings and silver horns, apart
    from the dragon's green and the fire drake's red; the Dread Wyrm, the
    Stage 3 boss, is built larger with black scales, dark red wings and
    glowing eyes.
    """
    if dread:
        scales = material('Dread wyrm black scales', (0.02, 0.02, 0.03), 0.2, 0.2,
                          rim=(1.0, 0.3, 0.2), rim_strength=1.6, coat=0.8)
        belly = material('Dread wyrm ash belly', (0.20, 0.17, 0.17), 0.2, 0.3,
                         rim=(1.0, 0.5, 0.4), rim_strength=0.6)
        wing = material('Dread wyrm blood membrane', (0.45, 0.03, 0.04), 0.7, 0.25,
                        emission=(0.6, 0.04, 0.03), strength=0.3,
                        rim=(1.0, 0.35, 0.25), rim_strength=1.2)
        horn = material('Dread wyrm bone horns', (0.80, 0.76, 0.66), roughness=0.3,
                        rim=(1.0, 0.9, 0.8), rim_strength=0.6)
        eye = material('Dread wyrm burning eyes', (1.0, 0.75, 0.15), emission=(1.0, 0.7, 0.1),
                       strength=8.0)
    else:
        scales = material('Wyrm sapphire scales', (0.02, 0.07, 0.35), 0.35, 0.2,
                          rim=(0.5, 0.75, 1.0), rim_strength=1.5, coat=0.8)
        belly = material('Wyrm pale belly', (0.55, 0.70, 0.90), 0.3, 0.25,
                         rim=(0.8, 0.9, 1.0), rim_strength=0.6)
        wing = material('Wyrm wing membrane', (0.35, 0.60, 0.95), 0.75, 0.2,
                        emission=(0.2, 0.4, 0.9), strength=0.3,
                        rim=(0.7, 0.9, 1.0), rim_strength=1.2)
        horn = material('Wyrm silver horns', (0.80, 0.82, 0.88), roughness=0.25, metallic=0.9)
        eye = material('Wyrm amber eyes', (1.0, 0.6, 0.1), emission=(1.0, 0.55, 0.08),
                       strength=6.0)
    start, LEG = set(bpy.data.objects), 0.8
    # Long raised neck, lean upright body on two legs, tail curling behind;
    # unlike the dragon, no spikes along the back.
    spine = [(0.00, -0.92, 0.92), (0.00, -0.80, 0.98), (0.00, -0.64, 0.98), (0.00, -0.50, 0.86),
             (0.00, -0.36, 0.70), (0.00, -0.18, 0.58), (0.00, 0.06, 0.52), (0.04, 0.30, 0.42),
             (0.16, 0.52, 0.30), (0.30, 0.70, 0.20), (0.26, 0.90, 0.14), (0.06, 1.00, 0.11),
             (-0.14, 0.96, 0.09)]
    radii = [(0.06, 0.045), (0.13, 0.09), (0.14, 0.11), (0.10, 0.10), (0.13, 0.12), (0.24, 0.19),
             (0.22, 0.18), (0.16, 0.13), (0.11, 0.09), (0.08, 0.06), (0.05, 0.04), (0.03, 0.025), 0]

    def rotate_x(v, pivot, degrees):
        a = math.radians(degrees)
        dy, dz = v.y - pivot.y, v.z - pivot.z
        return Vector((v.x, pivot.y + dy * math.cos(a) - dz * math.sin(a),
                       pivot.z + dy * math.sin(a) + dz * math.cos(a)))

    # Stand upright like an old picture of a T. rex: everything in front of
    # the hips swings up by 55 degrees while the tail stays on the floor,
    # and the head tips back down at the neck to look ahead.
    hips, lean, nod = Vector((x, y + 0.06, 0.52)), -55, 45
    neck = rotate_x(Vector((x, y - 0.50, 0.86)), hips, lean)

    def raised(px, py, pz, head=False):
        v = Vector((x + px, y + py, pz))
        if py >= 0.06:
            return v
        v = rotate_x(v, hips, lean)
        return rotate_x(v, neck, nod) if head else v

    tube('Wyrm body', [raised(*p, head=i < 3) for i, p in enumerate(spine)], radii, scales,
         sides=8, twist=math.pi / 8)
    tube('Wyrm jaw', [raised(0, -0.62, 0.88, True), raised(0, -0.78, 0.85, True),
                      raised(0, -0.91, 0.82, True)],
         [(0.11, 0.04), (0.09, 0.035), 0], belly, sides=6)
    for side in (-1, 1):
        sphere('Wyrm eye', tuple(raised(side * 0.10, -0.78, 1.04, True)), (0.04, 0.035, 0.028),
               eye, 16)
        # Nearly straight horns, angled back and up.
        tube('Wyrm horn', [raised(side * 0.08, -0.68, 1.06, True),
                           raised(side * 0.12, -0.56, 1.16, True),
                           raised(side * 0.15, -0.45, 1.25, True)], [0.04, 0.025, 0], horn,
             sides=6, smooth=True)
        # Huge folded wing, an M from the front: the arm bone climbs from the
        # shoulder to the wrist, a peak high above the shoulder, and four
        # finger bones fold from it outward and down like a resting bat's,
        # with the membrane scalloped deeply between them.
        shoulder = raised(side * 0.18, -0.16, 0.66)
        # Folded but still large: a tall peak and long fingers reaching down
        # to the floor, rather than a wide span.
        # The arm bone, from the shoulder to the claw at the wrist, is kept
        # at 0.8 of its first length; the finger tips stay where they were.
        wrist = shoulder + (Vector((x + side * 0.44, y - 0.02, 1.90)) - shoulder) * 0.8
        tips = [Vector((x + side * 0.78, y + 0.06, 0.62)),
                Vector((x + side * 0.76, y + 0.26, 0.24)),
                Vector((x + side * 0.62, y + 0.44, 0.08)),
                Vector((x + side * 0.42, y + 0.54, 0.08))]
        root = Vector((x + side * 0.12, y + 0.36, 0.46))
        tube('Wyrm wing arm', [shoulder, (shoulder + wrist) / 2 + Vector((0, 0, 0.06)), wrist],
             [0.06, 0.05, 0.04], scales, sides=6, smooth=True)
        for tip in tips:
            tube('Wyrm wing finger', [wrist, tip], [0.04, 0.012], scales, sides=6)
        cone('Wyrm wing claw', wrist, wrist + Vector((side * 0.04, -0.12, 0.12)),
             0.035, 0, horn, 5, False)
        outline = [shoulder, wrist, tips[0]]
        for a, b in zip(tips, tips[1:] + [root]):
            sag = wrist + ((a + b) / 2 - wrist) * 0.72
            outline += [sag, b]
        verts = [tuple(v) for v in outline]
        faces = [(1, i, i + 1) for i in range(2, len(verts) - 1)] + [(0, 1, len(verts) - 1)]
        membrane = mesh_object('Wyrm wing membrane', verts, faces, wing, True)
        solid = membrane.modifiers.new('Membrane thickness', 'SOLIDIFY')
        solid.thickness = 0.02
        solid.offset = 0
        # Two hind legs only; the wings are the forelimbs.
        # Legs at 0.8 of their first length; the whole wyrm is lowered at
        # the end to put the talons back on the floor.
        hip = Vector((x + side * 0.15, y + 0.04, 0.46))
        knee = hip + (Vector((x + side * 0.22, y - 0.08, 0.30)) - hip) * LEG
        foot = hip + (Vector((x + side * 0.18, y - 0.04, 0.07)) - hip) * LEG
        tube('Wyrm leg', [hip, knee, foot], [0.11, 0.08, 0.06], scales, sides=6)
        for spread in (-0.05, 0, 0.05):
            cone('Wyrm talon', (foot.x + spread, foot.y - 0.04, foot.z - 0.02),
                 (foot.x + spread * 1.6, foot.y - 0.15, foot.z - 0.05), 0.022, 0, horn, 4,
                 False)
    # A barbed tip on the tail.
    tail = Vector((x - 0.14, y + 0.96, 0.09))
    cone('Wyrm tail barb', tail + Vector((0.04, 0.02, 0)), tail + Vector((-0.12, -0.04, 0.02)),
         0.06, 0, horn, 4, False)
    transform_new(start, Matrix.Translation((0, 0, -0.39 * (1 - LEG))))


def transform_new(start, matrix):
    """Apply `matrix` to every object created since the `start` object set."""
    bpy.context.view_layer.update()
    for obj in set(bpy.data.objects) - start:
        obj.matrix_world = matrix @ obj.matrix_world


def nomicon(x, y):
    leather = companion_green('Nomicon green resin cover')
    green = companion_green('Nomicon deep green corners', 0.5, trim=True)
    # Aged parchment without a glow, and dimmer runes: the open pages face
    # the camera, and white glowing paper made the tome glare beside the
    # other companions.
    page = material('Nomicon paper pages', (0.56, 0.53, 0.44), 0.1, 0.6)
    rune = material('Nomicon cyan runes', (0.1, 0.75, 1.0), emission=(0.1, 0.7, 1.0),
                    strength=1.0)
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
            parts.append(block('Nomicon green corner', (side * 0.66, corner * 0.44, 0.0),
                               (0.12, 0.12, 0.07), green, 0.02))
        # Rune lines written across each page.
        # The lines next to the middle one stand a little apart to clear its eyes.
        for dy, length in zip((0.30, 0.17, 0.0, -0.17, -0.30), (0.42, 0.42, 0.38, 0.42, 0.42)):
            dx = side * (0.10 + length / 2)
            parts.append(block('Nomicon rune line', (dx, dy, 0.095),
                               (length, 0.06, 0.02), rune, 0.008))
        # The third line swells near the spine on both pages: a pair of eyes.
        # Each eye is a puffed, slightly narrow diamond: a domed outline whose
        # corners point up, down and sideways, the outer corner tilted up.
        cx, ring, verts = side * 0.25, 32, []
        tilt = side * math.radians(8)
        for level in range(6):
            shrink = 1 - level / 6
            z = 0.09 + 0.035 * math.sqrt(1 - shrink * shrink)
            for k in range(ring):
                a = 2 * math.pi * k / ring
                c, s_ = math.cos(a), math.sin(a)
                ex = 0.16 * shrink * math.copysign(abs(c) ** 1.35, c)
                ey = 0.10 * shrink * math.copysign(abs(s_) ** 1.35, s_)
                verts.append((cx + ex * math.cos(tilt) - ey * math.sin(tilt),
                              ex * math.sin(tilt) + ey * math.cos(tilt), z))
        verts.append((cx, 0, 0.125))
        faces = [tuple(reversed(range(ring)))]
        faces += [(l * ring + k, l * ring + (k + 1) % ring, (l + 1) * ring + (k + 1) % ring,
                   (l + 1) * ring + k) for l in range(5) for k in range(ring)]
        faces += [(5 * ring + k, 5 * ring + (k + 1) % ring, 6 * ring) for k in range(ring)]
        parts.append(mesh_object('Nomicon rune eye', verts, faces, rune, True))
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
    green = companion_green('Ocular deep green rings', 0.5, trim=True)
    pupil = material('Ocular matte pupil', (0.0, 0.0, 0.0), roughness=0.9)
    glint = material('Ocular cyan pupil light', (0.1, 0.75, 1.0), emission=(0.1, 0.7, 1.0),
                     strength=3.0)
    center = Vector((x, y, 0.62))
    # The eye looks straight at the camera, i.e. at the player.
    look = Vector((0, -math.cos(math.radians(60)), math.sin(math.radians(60))))
    sphere('Ocular eyeball', tuple(center), (0.36, 0.36, 0.36), sclera, 48)
    cone('Ocular iris', center + look * 0.30, center + look * 0.355, 0.20, 0.17, iris, 40)
    cone('Ocular pupil', center + look * 0.35, center + look * 0.37, 0.085, 0.07, pupil, 32)
    # The same cyan glow as the Nomicon's eyes and the Loop's ring, deep in the pupil.
    cone('Ocular pupil light', center + look * 0.365, center + look * 0.38, 0.035, 0.028,
         glint, 24)
    # A gyroscope-like green frame: a ring around the eye and one tilted across it.
    for name, rotation in (('Ocular equator ring', (0.0, 0.0, 0.0)),
                           ('Ocular orbit ring', (math.radians(60), math.radians(25), 0.0))):
        bpy.ops.mesh.primitive_torus_add(major_radius=0.46, minor_radius=0.03,
                                         location=tuple(center), rotation=rotation)
        finish(bpy.context.object, green, True, name)
    for side in (-1, 1):
        cone('Ocular ring fin', center + Vector((side * 0.46, 0, 0)),
             center + Vector((side * 0.62, 0, 0.10)), 0.06, 0, green, 4, False)



def loop_watch(x, y):
    """Loop companion: a floating green resin pocket watch whose glowing ring and
    arrow on the dial suggest turning time back."""
    green = companion_green('Loop green resin case')
    trim = companion_green('Loop deep green bezel', 0.5, trim=True)
    dial = material('Loop ivory dial', (0.92, 0.88, 0.76), 0.1, 0.3, coat=0.8)
    ink = material('Loop blued steel hands', (0.04, 0.06, 0.16), roughness=0.3, metallic=0.6)
    glow = material('Loop cyan time ring', (0.1, 0.75, 1.0), emission=(0.1, 0.7, 1.0),
                    strength=3.0)
    start = set(bpy.data.objects)
    # Built with the dial facing +Z and 12 o'clock toward +Y, then turned to
    # face the camera and lifted so it floats above its cell.
    bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=0.40, depth=0.12, location=(0, 0, 0))
    case = finish(bpy.context.object, green, True, 'Loop watch case')
    bevel = case.modifiers.new('Rounded back', 'BEVEL')
    bevel.width = 0.04
    bevel.segments = 4
    case.data.use_auto_smooth = True
    bpy.ops.mesh.primitive_torus_add(major_radius=0.38, minor_radius=0.04, location=(0, 0, 0.06))
    finish(bpy.context.object, trim, True, 'Loop watch bezel')
    bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=0.35, depth=0.02, location=(0, 0, 0.06))
    finish(bpy.context.object, dial, True, 'Loop watch dial')
    for hour in range(12):
        a = math.pi / 2 - hour * math.pi / 6
        long = hour % 3 == 0
        block('Loop hour mark', (0.29 * math.cos(a), 0.29 * math.sin(a), 0.075),
              (0.03, 0.08 if long else 0.05, 0.02), trim if long else ink, 0.006,
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
    sphere('Loop centre cap', (0, 0, 0.12), (0.035, 0.035, 0.02), green, 24)
    # Crown and bow at 12 o'clock.
    tube('Loop watch stem', [(0, 0.40, 0), (0, 0.47, 0)], [0.035, 0.035], green, sides=12,
         smooth=True)
    tube('Loop watch crown', [(0, 0.46, 0), (0, 0.53, 0)], [0.06, 0.06], trim, sides=16)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.09, minor_radius=0.022,
                                     location=(0, 0.62, 0))
    finish(bpy.context.object, trim, True, 'Loop watch bow')
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
        # It is large so the rare Erebus reads apart from the Erebus (e).
        gold = material('Stolen halo gold', (1.0, 0.72, 0.22), roughness=0.2, metallic=1.0,
                        emission=(1.0, 0.6, 0.15), strength=0.6)
        center = Vector((x, y - 0.52, 0.44))
        radius = 0.24
        for a0, a1 in ((20, 160), (195, 330)):
            arc = [center + Vector((radius * math.cos(math.radians(a)),
                                    radius * 0.5 * math.sin(math.radians(a)),
                                    radius * 0.85 * math.sin(math.radians(a))))
                   for a in range(a0, a1 + 1, 10)]
            tube('Stolen halo arc', arc, [0.032] * len(arc), gold, sides=8, smooth=True)
        for dx, dz in ((-0.30, 0.70), (0.28, 0.74), (0.06, 0.82)):
            base = Vector((x + dx, y - 0.46, dz))
            cone('Halo shard', base, base + Vector((0.02, 0, 0.06)), 0.03, 0, gold, 4, False)



def vortex(x, y):
    """Vortex (V): a whirlwind seen like a typhoon from above. Two strands of
    smoke in slightly different greys spiral up and out into a widening
    funnel, each thin at its foot, swelling midway and tapering to its tip,
    with pebbles caught in it and lightning crackling out from the centre.

    The smoky rim-lit look follows the Erebus; grey rather than its indigo,
    so the two read apart.
    """
    smokes = [material('Vortex grey smoke', (0.07, 0.08, 0.11), 0.5, 0.4,
                       rim=(0.7, 0.9, 1.0), rim_strength=1.5),
              material('Vortex blue-grey smoke', (0.28, 0.34, 0.45), 0.5, 0.4,
                       rim=(0.75, 0.92, 1.0), rim_strength=1.5)]
    stone = material('Vortex caught pebbles', (0.16, 0.15, 0.14), 0.0, 0.6,
                     rim=(0.7, 0.8, 1.0), rim_strength=0.6)
    glow = material('Vortex lightning', (1.0, 0.75, 0.25), emission=(1.0, 0.62, 0.12),
                    strength=4.0)
    steps = 80
    for strand, smoke in zip((0, math.pi), smokes):
        points, radii = [], []
        for i in range(steps + 1):
            t = i / steps
            r, a = 0.06 + 0.40 * t ** 1.3, strand + 2 * 2 * math.pi * t
            points.append((x + r * math.cos(a), y + r * math.sin(a), 0.06 + 1.0 * t))
            radii.append(0.012 + 0.08 * math.sin(math.pi * t) ** 0.8)
        radii[-1] = 0
        strand_obj = tube('Vortex smoke strand', points, radii, smoke, sides=16, smooth=True)
        wobble = strand_obj.modifiers.new('Smoke wobble', 'DISPLACE')
        texture = bpy.data.textures.new('Vortex smoke wobble', 'CLOUDS')
        texture.noise_scale = 0.12
        wobble.texture = texture
        wobble.strength = 0.025
    # Jagged lightning crackling out from the eye of the storm, laid nearly
    # flat so its zigzag shows from above.
    for start_angle, length in ((0.5, 0.30), (2.6, 0.26), (4.4, 0.33)):
        along = Vector((math.cos(start_angle), math.sin(start_angle), 0))
        side = Vector((-along.y, along.x, 0))
        bolt = [Vector((x, y, 0.90))]
        for k, swing in enumerate((0.05, -0.06, 0.05, -0.04)):
            f = (k + 1) / 4
            bolt.append(Vector((x, y, 0.90 - 0.10 * f)) + along * (length * f) + side * swing)
        tube('Vortex lightning', bolt, [0.022, 0.02, 0.017, 0.012, 0], glow, sides=6)
    # Pebbles whirled round the funnel.
    for a, r, z, size in ((0.4, 0.42, 0.35, 0.05), (2.1, 0.50, 0.62, 0.045),
                          (3.6, 0.38, 0.22, 0.04), (4.9, 0.58, 0.85, 0.05),
                          (5.8, 0.52, 0.50, 0.035)):
        block('Vortex pebble', (x + r * math.cos(a), y + r * math.sin(a), z),
              (size * 1.4, size, size), stone, size * 0.4, (a, a * 0.7, a * 1.3))

ELF_STRETCH = 1.3


def elf_figure(x, y, prefix, robe, skin, eye, body, head, skirt=(0.25, 0.19, 0.14), torso=None,
               skirt_z=(0.02, 0.30, 0.58), girth=1.0, ears=True, body_radii=None):
    """Shared elf build: about three heads tall, slimmer and taller than the
    player, in a long robe, with pointed ears; `body(x, y)` and `head(x, y)`
    add each elf's own parts, and `torso` can dress the upper body apart
    from the robe. `skirt_z` raises the robe's hem (for a seated elf),
    `girth` widens the upper body, `body_radii` replaces its four (x, y)
    radii from the waist to the neck, and `ears=False` leaves out the pointed
    ears.

    Heights shrink to half in the 60-degree view, so the body is stretched
    upward and the head tilted back for the face to look at the camera.
    """
    body_start = set(bpy.data.objects)
    # Long robe flaring to the floor and the slim body above it. Some
    # characters, such as the trouser-wearing Explorer, omit the robe skirt.
    if skirt is not None:
        tube(prefix + ' robe skirt', [(x, y, z) for z in skirt_z], list(skirt),
             robe, sides=32, smooth=True)
    tube(prefix + ' robe body', [(x, y, 0.56), (x, y, 0.72), (x, y, 0.86), (x, y, 0.90)],
         body_radii or [(rx * girth, ry * girth) for rx, ry in
                        ((0.16, 0.13), (0.19, 0.15), (0.17, 0.13), (0.08, 0.07))],
         torso or robe, sides=32,
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
    """Collector Elf: a plump, round-shouldered connoisseur who never leaves
    a light folding camp chair, in a deep teal robe, balding with side hair,
    with a watchmaker's loupe of stacked black-rimmed lenses over the left
    eye and hands folded on the belly (the rustless blade it gives is magic,
    not held), with a vase and a bundle of blades beside the chair.
    """
    robe = material('Collector elf teal robe', (0.02, 0.30, 0.30), 0.1, 0.45,
                    rim=(0.5, 1.0, 0.9), rim_strength=1.0, coat=0.3)
    dark = material('Collector elf blackened loupe', (0.03, 0.03, 0.035), roughness=0.3,
                    metallic=0.6, rim=(0.7, 0.8, 0.9), rim_strength=0.6)
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
    strap = material('Collector elf leather headband', (0.22, 0.12, 0.06), 0.0, 0.5)

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
            # Arms from low, sloping shoulders round the belly, the hands
            # folded on top of it.
            tube('Collector elf sleeve', [(x + side * 0.14, y, 0.82), (x + side * 0.27, y - 0.10, 0.68),
                                          (x + side * 0.09, y - 0.28, 0.62)], [0.075, 0.08, 0.08], robe,
                 sides=12, smooth=True)
            sphere('Collector elf hand', (x + side * 0.04, y - 0.31, 0.62), (0.055, 0.05, 0.05), skin, 16)
        # A paunch sitting low and pushing forward.
        sphere('Collector elf belly', (x, y - 0.10, 0.60), (0.24, 0.20, 0.19), robe, 32)
        # Collected pieces beside the chair: a vase and a bundle of blades.
        tube('Collector elf vase', [(x + 0.52, y - 0.05, 0.0), (x + 0.52, y - 0.05, 0.12),
                                    (x + 0.52, y - 0.05, 0.26), (x + 0.52, y - 0.05, 0.34)],
             [0.07, 0.11, 0.05, 0.06], vase, sides=20, smooth=True)
        for k, dx in enumerate((-0.04, 0.0, 0.04)):
            tube('Collector elf stored blade', [(x - 0.50 + dx, y - 0.10 + k * 0.03, 0.0),
                                                (x - 0.46 + dx * 2, y - 0.08 + k * 0.03, 0.46)],
                 [(0.025, 0.008), 0], steel, sides=4)

    def head(x, y):
        # Balding top with hair left at the sides and back.
        for side in (-1, 1):
            sphere('Collector elf side hair', (x + side * 0.11, y + 0.04, 1.00), (0.06, 0.09, 0.07), hair, 16)
        sphere('Collector elf back hair', (x, y + 0.11, 1.00), (0.12, 0.05, 0.07), hair, 16)
        sphere('Collector elf double chin', (x, y - 0.06, 0.92), (0.11, 0.09, 0.05), skin, 16)
        # A watchmaker's loupe over the left eye (screen right): a leather
        # headband, three black-rimmed lenses stacked into a short barrel
        # jutting forward, and a spare lens flipped up at the temple.
        bpy.ops.mesh.primitive_torus_add(major_radius=0.145, minor_radius=0.014,
                                         location=(x, y, 1.08), rotation=(0.15, 0, 0))
        finish(bpy.context.object, strap, True, 'Collector elf loupe headband')
        facing = (math.pi / 2, 0, 0)
        for k, r in enumerate((0.042, 0.036, 0.030)):
            centre = (x + 0.05, y - 0.15 - 0.045 * k, 1.04)
            bpy.ops.mesh.primitive_torus_add(major_radius=r, minor_radius=0.009,
                                             location=centre, rotation=facing)
            finish(bpy.context.object, dark, True, 'Collector elf loupe rim')
            bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=r, depth=0.008,
                                                location=centre, rotation=facing)
            finish(bpy.context.object, lens, True, 'Collector elf loupe lens')
        tube('Collector elf loupe barrel', [(x + 0.05, y - 0.15, 1.04), (x + 0.05, y - 0.24, 1.04)],
             [0.040, 0.029], dark, sides=16, smooth=True)
        tube('Collector elf loupe arm', [(x + 0.14, y - 0.04, 1.08), (x + 0.12, y - 0.13, 1.14)],
             [0.007, 0.007], dark, sides=6)
        spare = (x + 0.12, y - 0.15, 1.15)
        bpy.ops.mesh.primitive_torus_add(major_radius=0.026, minor_radius=0.007,
                                         location=spare, rotation=(0.4, 0, 0))
        finish(bpy.context.object, dark, True, 'Collector elf spare loupe rim')
        bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.026, depth=0.006,
                                            location=spare, rotation=(0.4, 0, 0))
        finish(bpy.context.object, lens, True, 'Collector elf spare loupe lens')

    # Fat but round-shouldered: the body widens steadily from narrow, sloping
    # shoulders to a heavy waist and hips, rather than bulging like a barrel.
    elf_figure(x, y, 'Collector elf', robe, skin, eye, body, head, skirt=(0.27, 0.29, 0.28),
               skirt_z=(0.34, 0.45, 0.60),
               body_radii=[(0.27, 0.22), (0.22, 0.18), (0.15, 0.12), (0.08, 0.07)])


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


# Stage 5 party members come in three skin tones on one shared build.
MEMBER_SKINS = {
    'light': (0.96, 0.80, 0.66),
    'medium': (0.66, 0.43, 0.26),
    'dark': (0.33, 0.19, 0.11),
}


def diamond_material(name, first, second, size, diamond=True, **kwargs):
    """`material()` whose base color is a harlequin pattern of `size`-wide
    diamonds in the two colors, set on the front (X-Z) faces; with
    `diamond=False`, a plain checkerboard of `size` squares."""
    mat = material(name, first, **kwargs)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    coords = nodes.new('ShaderNodeTexCoord')
    mapping = nodes.new('ShaderNodeMapping')
    if diamond:
        mapping.inputs['Rotation'].default_value = (0, math.radians(45), 0)
    # Diamonds taller than wide, like a jester's motley.
    mapping.inputs['Scale'].default_value = (1 / size, 1 / size, (0.7 if diamond else 1) / size)
    checker = nodes.new('ShaderNodeTexChecker')
    checker.inputs['Scale'].default_value = 1.0
    checker.inputs['Color1'].default_value = (*first, 1)
    checker.inputs['Color2'].default_value = (*second, 1)
    links.new(coords.outputs['Object'], mapping.inputs['Vector'])
    links.new(mapping.outputs['Vector'], checker.inputs['Vector'])
    links.new(checker.outputs['Color'], nodes['Principled BSDF'].inputs['Base Color'])
    return mat


def jester(x, y, tone):
    """Jester (J), a Stage 5 member: a court jester in wine-red and cream
    motley trimmed with gold, a two-pointed cap with gold bells, a pointed
    collar and an ivory masquerade mask, juggling three glowing gold balls
    (the experience it brings) over the cap while balanced on one leg, the
    other knee drawn up like an acrobat's. The mask
    leaves no mouth or beard, so it reads as neither man nor woman. No
    pointed ears, so it is not taken for an elf. `tone` picks one of
    `MEMBER_SKINS`.
    """
    red, cream = (0.50, 0.03, 0.06), (0.92, 0.84, 0.66)
    motley = diamond_material('Jester motley', red, cream, 0.11, transmission=0.05,
                              roughness=0.55, rim=(1.0, 0.85, 0.7), rim_strength=0.8)
    checks = diamond_material('Jester checkered shoes', (0.60, 0.03, 0.06), (0.95, 0.94, 0.92),
                              0.05, diamond=False, roughness=0.45, coat=0.3,
                              rim=(1.0, 0.9, 0.85), rim_strength=0.8)
    wine = material('Jester wine velvet', red, 0.05, 0.6, rim=(1.0, 0.6, 0.6), rim_strength=0.8)
    linen = material('Jester cream linen', cream, 0.05, 0.6, rim=(1.0, 0.95, 0.85),
                     rim_strength=0.6)
    gold = material('Jester gold', (1.0, 0.72, 0.22), roughness=0.25, metallic=0.9,
                    rim=(1.0, 0.9, 0.6), rim_strength=0.8)
    juggle = material('Jester juggling light', (1.0, 0.62, 0.08), 0.3, 0.15,
                      emission=(1.0, 0.6, 0.08), strength=0.8,
                      rim=(1.0, 0.85, 0.4), rim_strength=1.5)
    skin_color = MEMBER_SKINS[tone]
    skin = material('Jester skin ' + tone, skin_color, 0.2, 0.4,
                    rim=(1.0, 0.9, 0.8), rim_strength=0.6)
    # Ivory like porcelain, apart from the gold cap band above it.
    mask = material('Jester mask', (0.95, 0.93, 0.88), 0.1, 0.3, coat=0.4,
                    rim=(1.0, 1.0, 0.95), rim_strength=0.6)
    eye = material('Jester eyes', (0.03, 0.02, 0.02), roughness=0.2, coat=1.0)

    def body(x, y):
        # Legs in tights, one per color: the right (screen left) stands
        # nearly straight, the shin turned in a little; the left, in wine
        # to stand out, is bent with the knee turned out and the foot just
        # off the floor, toe pointing out, as in a juggler's caper. The shin
        # does not kick back, which the 60-degree view would show as a foot
        # flung upward. Large curled shoes in red and white checks, with bells.
        for leg, color, hip, knee, ankle, ahead in (
                ('right', linen, (-0.06, 0.0, 0.34), (-0.08, -0.01, 0.18), (-0.035, 0.0, 0.05),
                 (-0.6, -0.8)),
                ('left', wine, (0.07, 0.0, 0.36), (0.22, -0.14, 0.28), (0.10, -0.15, 0.11),
                 (0.8, -0.6))):
            points = [(x + px, y + py, pz) for px, py, pz in (hip, knee, ankle)]
            tube('Jester %s leg' % leg, points, [0.078, 0.068, 0.056], color, sides=12, smooth=True)
            ax, ay, az = ankle
            fx, fy = ahead
            toe = [(x + ax - fx * 0.05, y + ay - fy * 0.05, az + 0.01),
                   (x + ax + fx * 0.09, y + ay + fy * 0.09, az - 0.01),
                   (x + ax + fx * 0.21, y + ay + fy * 0.21, az + 0.02),
                   (x + ax + fx * 0.25, y + ay + fy * 0.25, az + 0.10)]
            tube('Jester %s shoe' % leg, toe, [0.075, 0.07, 0.04, 0], checks, sides=12,
                 smooth=True)
            sphere('Jester shoe bell', toe[-1], (0.025, 0.025, 0.025), gold, 12)
        # Pointed collar: alternating wine and cream points round the neck,
        # with gold bells on the front ones.
        for k in range(10):
            a = 2 * math.pi * k / 10 - math.pi / 2
            base = Vector((x + 0.10 * math.cos(a), y + 0.09 * math.sin(a), 0.85))
            tip = Vector((x + 0.22 * math.cos(a), y + 0.20 * math.sin(a), 0.75))
            cone('Jester collar point', base, tip, 0.055, 0, wine if k % 2 else linen, 8, False)
            if math.sin(a) < -0.3:
                sphere('Jester collar bell', tuple(tip), (0.022, 0.022, 0.022), gold, 12)
        bpy.ops.mesh.primitive_torus_add(major_radius=0.165, minor_radius=0.02, location=(x, y, 0.58))
        finish(bpy.context.object, gold, True, 'Jester belt')
        # Sleeves in opposite colors, both arms spread wide with the
        # forearms raised and the palms up.
        for side, sleeve in ((-1, linen), (1, wine)):
            tube('Jester sleeve', [(x + side * 0.17, y, 0.84), (x + side * 0.38, y - 0.02, 0.74),
                                   (x + side * 0.47, y - 0.06, 0.88)], [0.05, 0.05, 0.055], sleeve,
                 sides=12, smooth=True)
            sphere('Jester hand', (x + side * 0.49, y - 0.07, 0.93), (0.05, 0.045, 0.03), skin, 16)
        # Five glowing balls in flight, arching from hand to hand high over
        # the cap, clear of its bells.
        for px, py, pz in ((-0.55, -0.08, 1.12), (-0.48, -0.05, 1.52), (0.0, -0.02, 1.86),
                           (0.48, -0.05, 1.52), (0.55, -0.08, 1.12)):
            sphere('Jester juggling ball', (x + px, y + py, pz), (0.06, 0.06, 0.06), juggle, 20)

    def head(x, y):
        # A masquerade mask: a flat ivory plate held off the face, covering
        # the eyes and the bridge of the nose, its upper corners swept out
        # past the head into pointed wings, edged in gold, with dark
        # almond eyeholes. It curves less than the face, so it does not
        # wrap round the head like a headband.
        half = [(0.0, 0.040), (0.06, 0.045), (0.12, 0.060), (0.215, 0.115), (0.20, 0.060),
                (0.16, 0.005), (0.12, -0.035), (0.07, -0.045), (0.03, -0.030), (0.0, -0.020)]
        outline = half + [(-u, v) for u, v in reversed(half[1:-1])]

        def on_mask(u, v, ahead=0.0):
            return (x + u, y - 0.168 - ahead + 0.30 - math.sqrt(0.30 ** 2 - u * u), 1.035 + v)

        verts = [on_mask(0.0, 0.01)] + [on_mask(u, v) for u, v in outline]
        n = len(outline)
        plate = mesh_object('Jester mask', verts,
                            [(0, 1 + k, 1 + (k + 1) % n) for k in range(n)], mask, True)
        plate.modifiers.new('Mask thickness', 'SOLIDIFY').thickness = 0.014
        tube('Jester mask trim', [on_mask(u, v, 0.004) for u, v in outline + outline[:1]],
             [0.008] * (n + 1), gold, sides=6, smooth=True)
        for side in (-1, 1):
            sphere('Jester mask eyehole', on_mask(side * 0.06, 0.005, 0.006),
                   (0.034, 0.006, 0.018), eye, 12)
        # A two-pointed cap: a crown over the head and two drooping horns of
        # wine and cream, each ending in a gold bell.
        sphere('Jester cap crown', (x, y + 0.03, 1.13), (0.155, 0.15, 0.10), motley, 32)
        bpy.ops.mesh.primitive_torus_add(major_radius=0.15, minor_radius=0.022,
                                         location=(x, y + 0.02, 1.11))
        bpy.context.object.scale.y = 0.95
        finish(bpy.context.object, gold, True, 'Jester cap band')
        for side, color in ((-1, wine), (1, linen)):
            horn = [(x + side * 0.06, y + 0.02, 1.15), (x + side * 0.18, y + 0.04, 1.27),
                    (x + side * 0.31, y + 0.05, 1.27), (x + side * 0.38, y + 0.03, 1.15),
                    (x + side * 0.39, y + 0.0, 1.05)]
            tube('Jester cap horn', horn, [0.09, 0.07, 0.05, 0.03, 0.012], color, sides=14,
                 smooth=True)
            sphere('Jester cap bell', horn[-1], (0.04, 0.04, 0.04), gold, 16)

    elf_figure(x, y, 'Jester', motley, skin, eye, body, head, skirt=(0.21, 0.19, 0.16),
               skirt_z=(0.40, 0.49, 0.58), ears=False)


def healer(x, y, tone):
    """Healer (H), a Stage 5 member: a temple healer of no real-world faith,
    in a long cream robe with a turquoise stole and silver fittings (not the
    Lifebringer's white and gold), a lowered hood and a thin silver circlet,
    shoulder-length hair. One hand holds a staff topped by a silver ring
    with a floating pale aqua drop crystal; the other is raised before the
    chest, palm out, with a small healing light. The game's own emblem, a
    drop inside a ring, is on the chest. The face reads as neither man nor
    woman. `tone` picks one of `MEMBER_SKINS`.
    """
    robe = material('Healer cream robe', (0.86, 0.82, 0.72), 0.05, 0.6,
                    rim=(1.0, 0.97, 0.9), rim_strength=0.7)
    stole = material('Healer turquoise stole', (0.05, 0.40, 0.45), 0.05, 0.5,
                     rim=(0.6, 0.95, 1.0), rim_strength=0.8)
    silver = material('Healer silver', (0.80, 0.83, 0.88), roughness=0.25, metallic=0.9,
                      rim=(0.85, 0.95, 1.0), rim_strength=0.8)
    wood = material('Healer pale wood', (0.62, 0.48, 0.32), 0.0, 0.5,
                    rim=(1.0, 0.9, 0.7), rim_strength=0.6)
    glow = material('Healer aqua light', (0.30, 0.85, 1.0), 0.4, 0.1,
                    emission=(0.20, 0.75, 1.0), strength=0.7,
                    rim=(0.8, 1.0, 1.0), rim_strength=1.5)
    skin = material('Healer skin ' + tone, MEMBER_SKINS[tone], 0.2, 0.4,
                    rim=(1.0, 0.9, 0.8), rim_strength=0.6)
    hair = material('Healer dark hair', (0.10, 0.06, 0.04), 0.1, 0.45,
                    rim=(0.8, 0.7, 0.6), rim_strength=0.6, coat=0.3)
    eye = material('Healer eyes', (0.03, 0.02, 0.02), roughness=0.2, coat=1.0)

    def emblem(name, center, radius, drop_mat):
        """The drop-in-a-ring emblem, facing the front (-Y)."""
        bpy.ops.mesh.primitive_torus_add(major_radius=radius, minor_radius=radius * 0.16,
                                         location=center, rotation=(math.pi / 2, 0, 0))
        finish(bpy.context.object, silver, True, name + ' ring')
        cx, cy, cz = center
        sphere(name + ' drop', (cx, cy, cz - radius * 0.2), (radius * 0.42,) * 3, drop_mat, 20)
        cone(name + ' drop tip', (cx, cy, cz - radius * 0.05), (cx, cy, cz + radius * 0.62),
             radius * 0.36, 0, drop_mat, 20, True)

    def body(x, y):
        # The lowered hood lies behind the neck; the stole hangs from a band
        # round the neck down the front in two broad strips.
        sphere('Healer lowered hood', (x, y + 0.11, 0.86), (0.18, 0.10, 0.08), robe, 24)
        bpy.ops.mesh.primitive_torus_add(major_radius=0.12, minor_radius=0.03, location=(x, y, 0.87))
        finish(bpy.context.object, stole, True, 'Healer stole collar')
        for side in (-1, 1):
            tube('Healer stole strip', [(x + side * 0.08, y - 0.11, 0.86),
                                        (x + side * 0.08, y - 0.17, 0.60),
                                        (x + side * 0.08, y - 0.24, 0.12)],
                 [(0.045, 0.012)] * 3, stole, sides=8, smooth=True)
        emblem('Healer chest emblem', (x, y - 0.175, 0.72), 0.05, silver)
        # Staff in the right hand (screen left), its silver ring holding a
        # floating drop crystal above the head.
        shaft = (x - 0.30, y - 0.10)
        tube('Healer staff', [(shaft[0], shaft[1], 0.0), (shaft[0], shaft[1], 0.70),
                              (shaft[0], shaft[1], 1.40)], [0.024, 0.024, 0.022], wood,
             sides=8, smooth=True)
        emblem('Healer staff head', (shaft[0], shaft[1], 1.52), 0.12, glow)
        tube('Healer right sleeve', [(x - 0.17, y, 0.84), (x - 0.27, y - 0.04, 0.74),
                                     (x - 0.29, y - 0.09, 0.76)], [0.05, 0.065, 0.075], robe,
             sides=12, smooth=True)
        sphere('Healer right hand', (shaft[0], shaft[1], 0.77), (0.045, 0.045, 0.045), skin, 16)
        # Left hand raised before the chest, palm out, with a soft light.
        tube('Healer left sleeve', [(x + 0.17, y, 0.84), (x + 0.28, y - 0.04, 0.70),
                                    (x + 0.22, y - 0.18, 0.82)], [0.05, 0.065, 0.075], robe,
             sides=12, smooth=True)
        sphere('Healer left hand', (x + 0.21, y - 0.23, 0.86), (0.045, 0.02, 0.055), skin, 16)
        sphere('Healer healing light', (x + 0.21, y - 0.31, 0.90), (0.05, 0.05, 0.05), glow, 20)

    def head(x, y):
        # Shoulder-length hair under a thin silver circlet.
        sphere('Healer hair cap', (x, y + 0.03, 1.08), (0.155, 0.145, 0.13), hair, 32)
        for side in (-1, 1):
            tube('Healer hair side', [(x + side * 0.12, y - 0.02, 1.06), (x + side * 0.14, y + 0.02, 0.96),
                                      (x + side * 0.13, y + 0.04, 0.90)], [0.05, 0.05, 0.035], hair,
                 sides=10, smooth=True)
        tube('Healer hair back', [(x, y + 0.10, 1.06), (x, y + 0.14, 0.96), (x, y + 0.13, 0.90)],
             [0.11, 0.10, 0.07], hair, sides=12, smooth=True)
        bpy.ops.mesh.primitive_torus_add(major_radius=0.152, minor_radius=0.012,
                                         location=(x, y + 0.01, 1.10))
        finish(bpy.context.object, silver, True, 'Healer circlet')
        sphere('Healer circlet stone', (x, y - 0.143, 1.10), (0.022, 0.012, 0.03), glow, 12)

    elf_figure(x, y, 'Healer', robe, skin, eye, body, head, ears=False)


def sphere_shell(name, center, scale, mat, keep, thickness=0.02, reshape=None):
    """A thin shell of a sphere keeping only the faces whose unit-sphere
    center passes `keep(center)`: hoods and cloths over the head.
    `reshape(co)` can then move each unit-sphere vertex, returning a Vector."""
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, location=center)
    obj = bpy.context.object
    mesh = bmesh.new()
    mesh.from_mesh(obj.data)
    bmesh.ops.delete(mesh, geom=[face for face in mesh.faces
                                 if not keep(face.calc_center_median())], context='FACES')
    if reshape:
        for vert in mesh.verts:
            vert.co = reshape(vert.co.copy())
    mesh.to_mesh(obj.data)
    mesh.free()
    obj.scale = scale
    finish(obj, mat, True, name)
    obj.modifiers.new('Shell thickness', 'SOLIDIFY').thickness = thickness
    return obj


def rogue(x, y, tone):
    """Rogue (R), a Stage 5 member: a thief who gets by on sharp eyes and
    tricks rather than force, so it carries no weapon. An assassin-like
    charcoal robe in one piece: a hood of one cloth over the head hanging
    down both sides over the ears, open in front, its dark lining shading
    the uncovered face, folding into a cowl round the neck; wide sleeves
    and a rope belt.
    Crouched with the knees bent out and leaning a little forward, one hand
    dangles a ring of keys and picks at face height, the other is held out
    to say "wait" (it stops the party before danger). A small coil of rope
    hangs at the hip. Reads as neither man nor woman. `tone` picks one of
    `MEMBER_SKINS`.
    """
    charcoal = material('Rogue charcoal cloth', (0.045, 0.05, 0.065), 0.05, 0.7,
                        rim=(0.55, 0.65, 0.85), rim_strength=0.8)
    leather = material('Rogue brown leather', (0.22, 0.12, 0.05), 0.0, 0.5,
                       rim=(1.0, 0.75, 0.5), rim_strength=0.8)
    trousers = material('Rogue dark trousers', (0.07, 0.065, 0.075), 0.0, 0.7,
                        rim=(0.55, 0.6, 0.75), rim_strength=0.7)
    lining = material('Rogue hood lining', (0.02, 0.02, 0.025), roughness=0.8)
    rope = material('Rogue hemp rope', (0.72, 0.56, 0.32), 0.0, 0.6,
                    rim=(1.0, 0.9, 0.7), rim_strength=0.6)
    brass = material('Rogue brass keys', (1.0, 0.78, 0.35), roughness=0.18, metallic=0.8,
                     emission=(1.0, 0.65, 0.25), strength=0.16,
                     rim=(1.0, 0.9, 0.6), rim_strength=1.6)
    skin = material('Rogue skin ' + tone, MEMBER_SKINS[tone], 0.2, 0.4,
                    rim=(1.0, 0.9, 0.8), rim_strength=0.6)
    eye = material('Rogue eyes', (0.02, 0.02, 0.02), roughness=0.15, coat=1.0)
    legs, head_start = set(), set()

    def body(x, y):
        # A low crouch, knees bent out to the sides (bent forward, toward
        # the camera, they looked thin and twisted), the left foot a little
        # ahead; these stay upright while the rest of the figure leans.
        start = set(bpy.data.objects)
        for side, step in ((-1, 0.02), (1, -0.06)):
            hip, knee = (x + side * 0.08, y, 0.42), (x + side * 0.16, y - 0.05 + step, 0.25)
            ankle = (x + side * 0.11, y + step, 0.07)
            tube('Rogue leg', [hip, knee, ankle], [0.085, 0.078, 0.068], trousers, sides=12,
                 smooth=True)
            tube('Rogue boot', [(ankle[0], ankle[1] + 0.03, 0.08), (ankle[0], ankle[1] - 0.06, 0.04),
                                (ankle[0], ankle[1] - 0.11, 0.03)], [0.07, 0.065, 0.045], charcoal,
                 sides=10, smooth=True)
        legs.update(set(bpy.data.objects) - start)
        bpy.ops.mesh.primitive_torus_add(major_radius=0.175, minor_radius=0.018, location=(x, y, 0.58))
        finish(bpy.context.object, rope, True, 'Rogue rope belt')
        for dx in (-0.02, 0.02):
            tube('Rogue belt end', [(x + dx, y - 0.17, 0.57), (x + dx * 2, y - 0.19, 0.46),
                                    (x + dx * 2.5, y - 0.20, 0.38)], [0.016, 0.015, 0.012], rope,
                 sides=6, smooth=True)
        # The hood folds into a cowl round the neck.
        bpy.ops.mesh.primitive_torus_add(major_radius=0.14, minor_radius=0.055, location=(x, y + 0.01, 0.88))
        finish(bpy.context.object, charcoal, True, 'Rogue cowl')
        sphere('Rogue pouch', (x + 0.14, y - 0.10, 0.52), (0.06, 0.05, 0.06), leather, 16)
        sphere('Rogue pouch clasp', (x + 0.14, y - 0.151, 0.53), (0.018, 0.009, 0.018), brass, 12)
        # A small coil of rope against the side of the left hip, hanging in
        # tall ovals with its axis turned 75 degrees from the front, nearly
        # sideways (the rings stand up, so their local Y is the height).
        coil = Vector((x + 0.21, y - 0.03, 0.46))
        for k in range(3):
            bpy.ops.mesh.primitive_torus_add(major_radius=0.07 - 0.01 * k, minor_radius=0.018,
                                             location=coil + Vector((0.012 * k, -0.006 * k, 0)),
                                             rotation=(math.pi / 2, 0, math.radians(75)))
            ring = finish(bpy.context.object, rope, True, 'Rogue rope coil')
            ring.scale = (1.0, 1.6, 1.0)
        bpy.ops.mesh.primitive_torus_add(major_radius=0.035, minor_radius=0.009,
                                         location=(x + 0.21, y - 0.07, 0.56),
                                         rotation=(math.pi / 2, 0, 0))
        finish(bpy.context.object, brass, True, 'Rogue rope clip')
        # Right hand (screen left) raised beside the face, dangling the keys.
        tube('Rogue right sleeve', [(x - 0.17, y, 0.84), (x - 0.34, y - 0.02, 0.86),
                                    (x - 0.36, y - 0.10, 1.06)], [0.055, 0.065, 0.08], charcoal,
             sides=12, smooth=True)
        sphere('Rogue right hand', (x - 0.36, y - 0.12, 1.10), (0.045, 0.045, 0.045), skin, 16)
        ring = Vector((x - 0.36, y - 0.13, 1.00))
        bpy.ops.mesh.primitive_torus_add(major_radius=0.07, minor_radius=0.014, location=ring,
                                         rotation=(math.pi / 2, 0, 0))
        finish(bpy.context.object, brass, True, 'Rogue key ring')
        for k, dx in enumerate((-0.05, 0.0, 0.05)):
            top = ring + Vector((dx, -0.01, -0.06))
            bottom = top + Vector((dx * 0.8, -0.01, -0.17 - 0.04 * (k % 2)))
            tube('Rogue key', [top, bottom], [0.018, 0.018], brass, sides=6)
            block('Rogue key bit', tuple(bottom + Vector((0.022, 0, 0.025))), (0.045, 0.012, 0.04),
                  brass, 0.005)
        # Left hand held out to the side at shoulder height, palm out: "wait".
        tube('Rogue left sleeve', [(x + 0.17, y, 0.84), (x + 0.34, y - 0.04, 0.80),
                                   (x + 0.42, y - 0.10, 0.92)], [0.055, 0.065, 0.08], charcoal,
             sides=12, smooth=True)
        sphere('Rogue left hand', (x + 0.44, y - 0.12, 0.96), (0.035, 0.05, 0.065), skin, 16)
        head_start.update(bpy.data.objects)

    def head(x, y):
        # The hood is one cloth joined over the head and hanging straight
        # down on both sides over the ears to the shoulders, open all down
        # the front below a point on the brow; the crown comes to only a
        # slight point at the back.
        # A near-black lining shows at its edges and shades the face.
        # (A round shell read as a helmet, a hem flared to the shoulders as
        # long hair, and a tall point as a costume cone.)
        def drape(co):
            t = max(0.0, co.z - 0.2) / 0.8
            co.y += 0.12 * t * t
            co.z += 0.08 * t * t
            # Draw the cloth at the brow point a little forward.
            brow = max(0.0, 1 - abs(co.x) / 0.3) * max(0.0, 1 - abs(co.z - 0.45) / 0.35)
            if co.y < 0:
                co.y -= 0.12 * brow
            if co.z < 0:
                co.x *= 1 - 0.15 * co.z
                co.z *= 2.3
            return co

        def front_open(c):
            # The opening is a triangle pointing up to the middle of the
            # brow, so the hood's edge slants down from there to each side.
            return not (c.y < -0.3 and c.z < 0.48 - 0.7 * abs(c.x)) and c.z > -0.9

        sphere_shell('Rogue hood', (x, y + 0.03, 1.06), (0.205, 0.20, 0.20), charcoal,
                     front_open, reshape=drape)
        sphere_shell('Rogue hood lining', (x, y + 0.03, 1.06), (0.19, 0.185, 0.19), lining,
                     front_open, 0.005, reshape=drape)

    upper = set(bpy.data.objects)
    elf_figure(x, y, 'Rogue', charcoal, skin, eye, body, head, skirt=(0.23, 0.19, 0.16),
               skirt_z=(0.32, 0.46, 0.58), ears=False)
    # Lean the body forward over the bent knees, tilting the head back as
    # much so the eyes still face the camera. (Turning the figure to show
    # the lean in profile made it look like it was diving.)
    bpy.context.view_layer.update()
    figure = set(bpy.data.objects) - upper
    hip = Vector((x, y, 0.42 * ELF_STRETCH))
    lean = Matrix.Translation(hip) @ Matrix.Rotation(0.18, 4, 'X') @ Matrix.Translation(-hip)
    neck = lean @ Vector((x, y, 0.90 * ELF_STRETCH))
    unlean = Matrix.Translation(neck) @ Matrix.Rotation(-0.18, 4, 'X') @ Matrix.Translation(-neck)
    for obj in figure:
        if obj not in legs:
            obj.matrix_world = lean @ obj.matrix_world
        if obj not in head_start:
            obj.matrix_world = unlean @ obj.matrix_world


def dungeon_explorer(x, y, tone):
    """Dungeon Explorer (D), a Stage 5 member: a caver who finds hidden
    routes. Lightly dressed like a modern caving team: a yellow helmet with a
    headlamp, a fitted light grey shirt, navy trousers, knee pads and a bare
    sit harness with a few carabiners. A coil of twisted hemp rope is slung
    over the right shoulder and across the chest, and the right hand holds a
    short ice axe beside the body, its head at shoulder height. The left hand
    rests on the hip. No weapon besides the tool, no cape. `tone` picks one of
    `MEMBER_SKINS`.
    """
    shirt = material('Dungeon Explorer light grey shirt', (0.36, 0.37, 0.39), 0.0, 0.55,
                     rim=(0.85, 0.87, 0.92), rim_strength=0.45)
    trousers = material('Dungeon Explorer navy trousers', (0.06, 0.08, 0.20), 0.0, 0.6,
                        rim=(0.6, 0.65, 0.8), rim_strength=0.5)
    pads = material('Dungeon Explorer knee pads', (0.42, 0.42, 0.44), 0.0, 0.45,
                    rim=(0.8, 0.8, 0.85), rim_strength=0.5)
    leather = material('Dungeon Explorer brown boots', (0.30, 0.20, 0.11), 0.0, 0.55,
                       rim=(0.9, 0.72, 0.5), rim_strength=0.5)
    webbing = material('Dungeon Explorer harness webbing', (0.06, 0.06, 0.07), 0.0, 0.5,
                       rim=(0.6, 0.6, 0.65), rim_strength=0.4)
    helmet = material('Dungeon Explorer yellow helmet', (0.92, 0.70, 0.02), 0.0, 0.25,
                      rim=(1.0, 0.92, 0.6), rim_strength=0.7, coat=0.6)
    # Matte hemp; a bright yellow, smooth rope read as nylon.
    rope = material('Dungeon Explorer hemp rope', (0.50, 0.37, 0.19), 0.0, 0.85,
                    rim=(0.95, 0.85, 0.65), rim_strength=0.3)
    steel = material('Dungeon Explorer steel', (0.62, 0.63, 0.66), roughness=0.3,
                     metallic=0.8, rim=(0.95, 0.95, 1.0), rim_strength=0.6)
    shaft = material('Dungeon Explorer ice axe shaft', (0.36, 0.20, 0.08), 0.0, 0.5,
                     rim=(0.95, 0.75, 0.5), rim_strength=0.5)
    lamp = material('Dungeon Explorer headlamp lens', (1.0, 0.92, 0.70), 0.15, 0.2,
                    emission=(1.0, 0.86, 0.55), strength=2.0,
                    rim=(1.0, 0.95, 0.8), rim_strength=0.8, coat=0.4)
    skin = material('Dungeon Explorer skin ' + tone, MEMBER_SKINS[tone], 0.2, 0.4,
                    rim=(1.0, 0.9, 0.8), rim_strength=0.6)
    eye = material('Dungeon Explorer eyes', (0.025, 0.02, 0.015), roughness=0.2, coat=1.0)

    def body(x, y):
        # Straight legs a little apart, with knee pads over the trousers.
        tube('Dungeon Explorer hips', [(x, y, 0.36), (x, y, 0.47), (x, y, 0.58)],
             [(0.15, 0.12), (0.16, 0.125), (0.155, 0.125)], trousers, sides=24, smooth=True)
        for side in (-1, 1):
            hip, knee = (x + side * 0.08, y, 0.42), (x + side * 0.10, y - 0.01, 0.24)
            ankle = (x + side * 0.11, y, 0.07)
            tube('Dungeon Explorer leg', [hip, knee, ankle], [0.08, 0.07, 0.062], trousers,
                 sides=12, smooth=True)
            sphere('Dungeon Explorer knee pad', (knee[0], knee[1] - 0.055, knee[2]),
                   (0.06, 0.035, 0.065), pads, 16)
            tube('Dungeon Explorer boot', [(ankle[0], ankle[1] + 0.03, 0.09),
                                           (ankle[0], ankle[1] - 0.05, 0.05),
                                           (ankle[0], ankle[1] - 0.11, 0.035)],
                 [0.075, 0.07, 0.05], leather, sides=12, smooth=True)
            # Leg loops of the harness.
            bpy.ops.mesh.primitive_torus_add(major_radius=0.085, minor_radius=0.014,
                                             location=(x + side * 0.085, y, 0.37),
                                             rotation=(0, side * math.radians(-12), 0))
            finish(bpy.context.object, webbing, True, 'Dungeon Explorer leg loop')
        # The waist belt of the harness, with carabiners on the left hip.
        bpy.ops.mesh.primitive_torus_add(major_radius=0.165, minor_radius=0.022,
                                         location=(x, y, 0.52))
        belt = finish(bpy.context.object, webbing, True, 'Dungeon Explorer harness belt')
        belt.scale.y = 0.82
        for k in range(3):
            bpy.ops.mesh.primitive_torus_add(major_radius=0.03, minor_radius=0.007,
                                             location=(x + 0.05 + 0.045 * k, y - 0.14 + 0.02 * k,
                                                       0.46),
                                             rotation=(math.pi / 2, 0, math.radians(15 * k)))
            ring = finish(bpy.context.object, steel, True, 'Dungeon Explorer carabiner')
            ring.scale = (0.75, 1.3, 1.0)

        # A coil of rope over the right shoulder (screen left), crossing the
        # chest to the left hip. Three strands make it read as a coil rather
        # than a sash. Each strand is three plies twisted round each other,
        # so it reads as a laid rope.
        center = Vector((x + 0.01, y, 0.69))
        along = Vector((0.165, 0, -0.19))
        across = along.cross(Vector((0, 1, 0))).normalized()
        steps, pitch = 240, 0.06
        for k in (-1, 0, 1):
            points = []
            for step in range(steps + 1):
                t = 2 * math.pi * step / steps
                points.append(center + along * math.cos(t)
                              + Vector((0, -(0.195 + 0.006 * k) * math.sin(t), 0))
                              + across * (0.026 * k))
            length = 0.0
            frames = []
            for i, point in enumerate(points):
                if i:
                    length += (point - points[i - 1]).length
                ahead = (points[min(i + 1, steps)] - points[max(i - 1, 0)]).normalized()
                side = ahead.cross(Vector((0, 0, 1))).normalized()
                frames.append((length, side, side.cross(ahead)))
            for ply in range(3):
                strands = []
                for point, (s, side, up) in zip(points, frames):
                    a = 2 * math.pi * (s / pitch + ply / 3)
                    strands.append(point + (side * math.cos(a) + up * math.sin(a)) * 0.008)
                tube('Dungeon Explorer rope ply', strands, [0.012] * len(strands), rope,
                     sides=6, smooth=True)

        def sleeve(side, shoulder, elbow, wrist):
            # Two straight tubes and a round elbow: one tube bent at the
            # elbow turns its rings there and looks twisted.
            tube('Dungeon Explorer ' + side + ' upper sleeve', [shoulder, elbow], [0.062, 0.055],
                 shirt, sides=16, smooth=True)
            sphere('Dungeon Explorer ' + side + ' elbow', elbow, (0.055, 0.055, 0.055), shirt, 16)
            tube('Dungeon Explorer ' + side + ' lower sleeve', [elbow, wrist], [0.055, 0.045],
                 shirt, sides=16, smooth=True)

        # Left hand (screen right) on the hip, elbow out.
        sleeve('left', (x + 0.16, y - 0.01, 0.83), (x + 0.32, y, 0.67), (x + 0.22, y - 0.07, 0.55))
        sphere('Dungeon Explorer left hand', (x + 0.19, y - 0.09, 0.53),
               (0.045, 0.04, 0.05), skin, 16)
        # Right hand holds the ice axe upright beside the body, the spike
        # toward the floor and the head at shoulder height.
        spike, top = Vector((x - 0.29, y - 0.14, 0.38)), Vector((x - 0.39, y - 0.10, 0.92))
        hand = spike.lerp(top, 0.31)
        sleeve('right', (x - 0.16, y - 0.01, 0.83), (x - 0.31, y - 0.03, 0.70),
               hand + Vector((0.01, 0.02, 0.05)))
        sphere('Dungeon Explorer right hand', tuple(hand + Vector((0, -0.01, 0))),
               (0.045, 0.045, 0.05), skin, 16)
        tube('Dungeon Explorer ice axe shaft', [spike, top], [0.02, 0.018], shaft,
             sides=10, smooth=True)
        cone('Dungeon Explorer ice axe spike', tuple(spike), tuple(spike + (spike - top) * 0.09),
             0.02, 0.0, steel, 12)
        # The pick curves down outward (screen left), the flat adze points
        # in toward the body.
        tube('Dungeon Explorer ice axe pick', [top + Vector((0.03, 0, 0)), top + Vector((-0.08, 0, -0.005)),
                                               top + Vector((-0.17, 0, -0.06))],
             [(0.024, 0.03), (0.016, 0.022), 0.0], steel, sides=8, smooth=True)
        block('Dungeon Explorer ice axe adze', tuple(top + Vector((0.09, 0, 0.0))),
              (0.10, 0.03, 0.05), steel, 0.01, (0, math.radians(8), 0))

    def head(x, y):
        # A hard-hat-like caving helmet: a dome cut by one plane, its rim
        # just above the eyes in front and a little lower at the back, then
        # a narrow brim all round that widens in front into a short peak
        # bent slightly down. A headlamp sits on the front of the dome.
        # Longer front to back than across, like a real helmet seen from above.
        center, radii = Vector((x, y + 0.005, 1.05)), Vector((0.152, 0.185, 0.17))
        # The rim plane on the unit sphere: z = rim_z - rim_tilt * y.
        rim_z, rim_tilt = 0.13, 0.15
        shell = sphere_shell('Dungeon Explorer helmet', tuple(center), tuple(radii), helmet,
                             lambda c: c.z > -0.4, 0.03)
        shell.modifiers['Shell thickness'].offset = 1.0
        mesh = bmesh.new()
        mesh.from_mesh(shell.data)
        bmesh.ops.bisect_plane(mesh, geom=mesh.verts[:] + mesh.edges[:] + mesh.faces[:],
                               plane_co=(0, 0, rim_z), plane_no=(0, rim_tilt, 1),
                               clear_inner=True)
        mesh.to_mesh(shell.data)
        mesh.free()
        inner, outer, count = [], [], 64
        for k in range(count):
            a = 2 * math.pi * k / count
            # a = 0 faces front (-y).
            unit_y = -math.cos(a)
            unit_z = rim_z - rim_tilt * unit_y
            ring = math.sqrt(1 - unit_z * unit_z)
            rim = center + Vector((radii.x * ring * math.sin(a), radii.y * ring * unit_y,
                                   radii.z * unit_z))
            outward = Vector((math.sin(a), unit_y, 0))
            # The peak spans about 70 degrees either side of the front.
            turn = a if a <= math.pi else a - 2 * math.pi
            width = 0.014 + 0.035 * max(0.0, math.cos(turn * 1.25)) ** 1.5
            inner.append(tuple(rim + outward * 0.02))
            outer.append(tuple(rim + outward * (0.02 + width) - Vector((0, 0, 0.15 * width))))
        brim = mesh_object('Dungeon Explorer helmet brim', inner + outer,
                           [(k, (k + 1) % count, count + (k + 1) % count, count + k)
                            for k in range(count)], helmet, True)
        brim.modifiers.new('Brim thickness', 'SOLIDIFY').thickness = 0.014
        block('Dungeon Explorer headlamp housing', (x, y - 0.179, 1.15),
              (0.10, 0.045, 0.07), webbing, 0.015, (math.radians(-10), 0, 0))
        bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=0.03, depth=0.012,
                                            location=(x, y - 0.205, 1.15),
                                            rotation=(math.pi / 2, 0, 0))
        finish(bpy.context.object, lamp, True, 'Dungeon Explorer headlamp lens')

    elf_figure(x, y, 'Dungeon Explorer', shirt, skin, eye, body, head, skirt=None, ears=False)


def heavy_armor_materials(tone):
    """Materials shared by the Knight and the Guardian, so the two read as
    one order: plate and shield in a plain iron grey, lighter than the
    player's bluish steel, darker steel trim and boots, and red accents in
    place of any emblem. Nothing glows, so neither blade nor shield is
    mistaken for the player's blessed sword."""
    # Only partly metallic: fully metallic plate mirrored the dark studio and
    # the pink rim light; a near-white plate looked too white for iron.
    plate = material('Heavy armor iron plate', (0.62, 0.61, 0.59), roughness=0.32,
                     metallic=0.6, rim=(0.95, 0.95, 0.92), rim_strength=0.7)
    trim = material('Heavy armor steel trim', (0.20, 0.20, 0.22), roughness=0.3, metallic=0.9,
                    rim=(0.85, 0.85, 0.9), rim_strength=0.5)
    red = material('Heavy armor red accent', (0.48, 0.02, 0.03), 0.0, 0.45,
                   rim=(1.0, 0.5, 0.45), rim_strength=0.7, coat=0.3)
    skin = material('Heavy armor skin ' + tone, MEMBER_SKINS[tone], 0.2, 0.4,
                    rim=(1.0, 0.9, 0.8), rim_strength=0.6)
    eye = material('Heavy armor eyes', (0.03, 0.02, 0.02), roughness=0.2, coat=1.0)
    return plate, trim, red, skin, eye


def limb(name, start, end, width, depth, mat, radius=0.05):
    """A rounded block from `start` to `end`, `width` across and `depth` deep."""
    start, end = Vector(start), Vector(end)
    ahead = end - start
    return block(name, tuple((start + end) / 2), (width, depth, ahead.length), mat, radius,
                 ahead.to_track_quat('Z', 'Y').to_euler())


def heavy_armor_figure(x, y, prefix, mats, legs, body, head, girth=1.0, boot=1.0,
                       head_scale=1.0):
    """The armored members' figure, borrowed from the player's (`player()`):
    legs from the given (hip, knee, ankle) per side ending in round boots
    (`boot` scales them), an oval cylinder body with a red belt and plate
    seams, round pauldrons edged in red, and the player's block helm, here
    open in front so the face shows. No cloak and no visor fins, which are
    the player's. `body(x, y, radius)` adds the arms and anything held;
    `head(x, y)` adds to the helm, and `head_scale` scales the helm and
    head about the neck. Returns nothing; like the player, the body is
    stretched upward and the head tilted back.
    """
    plate, trim, red, skin, eye = mats
    body_start = set(bpy.data.objects)
    for hip, knee, ankle in legs:
        tube(prefix + ' leg', [hip, knee, ankle], [0.085, 0.078, 0.07], plate, sides=16,
             smooth=True)
        sphere(prefix + ' boot', (ankle[0], ankle[1] - 0.03, 0.04),
               (0.075 * boot, 0.09 * boot, 0.045 * boot), trim, 20)
    flat = 0.72
    radius = 0.24 * girth
    bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=radius, depth=0.36,
                                        location=(x, y, 0.48))
    torso = finish(bpy.context.object, plate, True, prefix + ' cylinder torso')
    torso.scale.y = flat
    for face in torso.data.polygons:
        face.use_smooth = len(face.vertices) == 4
    torso.data.use_auto_smooth = True
    bevel = torso.modifiers.new('Rounded rims', 'BEVEL')
    bevel.width = 0.06
    bevel.segments = 5
    bpy.ops.mesh.primitive_torus_add(major_radius=radius + 0.005, minor_radius=0.035,
                                     location=(x, y, 0.36))
    finish(bpy.context.object, red, True, prefix + ' red belt').scale.y = flat
    for z in (0.48, 0.57):
        bpy.ops.mesh.primitive_torus_add(major_radius=radius + 0.003, minor_radius=0.011,
                                         location=(x, y, z))
        finish(bpy.context.object, trim, True, prefix + ' plate seam').scale.y = flat
    for side in (-1, 1):
        shoulder = (x + side * (radius + 0.03), y - 0.05, 0.63)
        # Darker than the plate, like the player's iron pauldrons.
        sphere(prefix + ' pauldron', shoulder, (0.14, 0.14, 0.07), trim, 24)
        bpy.ops.mesh.primitive_torus_add(major_radius=0.13, minor_radius=0.016,
                                         location=(shoulder[0], shoulder[1], 0.605))
        finish(bpy.context.object, red, True, prefix + ' pauldron red edge')
    body(x, y, radius)
    bpy.context.view_layer.update()
    start = set(bpy.data.objects)
    for obj in start - body_start:
        obj.matrix_world = (Matrix.Translation((x, y, 0)) @ Matrix.Diagonal((1, 1, ELF_STRETCH, 1))
                            @ Matrix.Translation((-x, -y, 0)) @ obj.matrix_world)
    # The player's helm with the faceplate left out and an opening cut into
    # its front, its inner walls dark steel; a round head, like the other
    # characters', sits inside with its face just behind the helm's front,
    # so the opening's edges shade it. (A face pressed onto the helm's flat
    # front looked flat.)
    helm = block(prefix + ' helm', (x, y - 0.04, 0.83), (0.34, 0.32, 0.34), plate, 0.10)
    # Round the helm's edges first; beveled after the cut, the narrow frame
    # beside the opening clamped the rounding away.
    bpy.context.view_layer.objects.active = helm
    bpy.ops.object.modifier_apply(modifier='Rounded edges')
    # The opening stops just above the eyes, so the helm covers the brow.
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y - 0.14, 0.765))
    cutter = bpy.context.object
    cutter.scale = (0.29, 0.16, 0.18)
    cutter.data.materials.append(trim)
    cut = helm.modifiers.new('Face opening', 'BOOLEAN')
    cut.object = cutter
    cut.solver = 'EXACT'
    cut.material_mode = 'TRANSFER'
    bpy.context.view_layer.objects.active = helm
    bpy.ops.object.modifier_move_to_index(modifier=cut.name, index=0)
    bpy.ops.object.modifier_apply(modifier=cut.name)
    bpy.data.objects.remove(cutter)
    sphere(prefix + ' head', (x, y - 0.04, 0.80), (0.15, 0.15, 0.15), skin, 32)
    for side in (-1, 1):
        sphere(prefix + ' eye', (x + side * 0.06, y - 0.175, 0.815), (0.025, 0.012, 0.032), eye,
               12)
    head(x, y)
    neck = Vector((x, y, 0.66))
    transform_new(start, Matrix.Translation((0, 0, neck.z * (ELF_STRETCH - 1)))
                  @ Matrix.Translation(neck) @ Matrix.Rotation(-0.6, 4, 'X')
                  @ Matrix.Scale(head_scale, 4) @ Matrix.Translation(-neck))


# The Knight is built larger than the player and the Guardian; its helm is
# brought back to their size so only the body reads as larger.
KNIGHT_HEAD_SCALE = 1.42 / 1.70


def knight(x, y, tone):
    """Knight (K), a Stage 5 member who adds its level, from 50 up, to the
    player's attack. A tall, proud veteran in heavy iron plate, built like
    the player but with no cloak and no shield: one great sword held
    straight up in the right hand (screen left), the left fist on the hip. The
    helm is open in front and carries a short red plume. Red accents (plume,
    belt, pauldron edges, grip) are shared with the Guardian instead of an
    emblem. `tone` picks one of `MEMBER_SKINS`.
    """
    mats = heavy_armor_materials(tone)
    plate, trim, red = mats[:3]
    blade = material('Knight great sword blade', (0.70, 0.71, 0.73), roughness=0.25,
                     metallic=0.6, rim=(0.95, 0.97, 1.0), rim_strength=1.0)

    def body(x, y, radius):
        # Right arm (screen left) out to the side, the forearm up, holding
        # the great sword straight up.
        hand = Vector((x - 0.44, y - 0.12, 0.84))
        elbow = (x - 0.44, y - 0.08, 0.62)
        limb('Knight right upper arm', (x - radius - 0.03, y - 0.05, 0.60), elbow, 0.17, 0.18,
             plate)
        limb('Knight right forearm', elbow, hand, 0.16, 0.17, plate)
        sphere('Knight right gauntlet', tuple(hand), (0.08, 0.08, 0.08), trim, 16)
        ahead = Vector((0, 0, 1))
        across = Vector((1, 0, 0))
        guard = hand + ahead * 0.07
        tube('Knight sword grip', [hand - ahead * 0.09, guard], [0.022, 0.022], red, sides=8)
        sphere('Knight sword pommel', tuple(hand - ahead * 0.12), (0.035,) * 3, trim, 12)
        tube('Knight sword guard', [guard + across * 0.13, guard - across * 0.13],
             [0.025, 0.025], trim, sides=6)
        # Thin across the view, broad facing the camera.
        tube('Knight sword blade', [guard + ahead * 0.02, guard + ahead * 0.72,
                                    guard + ahead * 0.85],
             [(0.06, 0.014), (0.052, 0.014), 0], blade, sides=4)
        # Left fist on the hip, the elbow out.
        elbow = (x + 0.42, y - 0.02, 0.48)
        limb('Knight left upper arm', (x + radius + 0.03, y - 0.05, 0.60), elbow, 0.17, 0.18,
             plate)
        limb('Knight left forearm', elbow, (x + radius + 0.01, y - 0.10, 0.40), 0.16, 0.17, plate)
        sphere('Knight left gauntlet', (x + radius, y - 0.11, 0.39), (0.08, 0.075, 0.08), trim, 16)

    def head(x, y):
        # A short red plume from a steel socket on the crown, arcing back
        # and falling toward screen right.
        block('Knight plume socket', (x, y - 0.06, 1.005), (0.06, 0.10, 0.04), trim, 0.012)
        root = Vector((x, y - 0.08, 1.02))
        tube('Knight red plume', [root + Vector(offset) for offset in (
            (0, 0, 0), (0.01, 0.07, 0.06), (0.05, 0.15, 0.05), (0.11, 0.20, -0.03),
            (0.15, 0.21, -0.13), (0.165, 0.20, -0.22))],
             [0.035, 0.06, 0.07, 0.065, 0.05, 0], red, sides=12, smooth=True, flat=0.8)

    heavy_armor_figure(x, y, 'Knight', mats, [
        ((x + side * 0.10, y, 0.36), (x + side * 0.11, y - 0.01, 0.18),
         (x + side * 0.12, y - 0.01, 0.06)) for side in (-1, 1)], body, head, girth=1.05,
        head_scale=KNIGHT_HEAD_SCALE)


def guardian(x, y, tone):
    """Guardian (G), a Stage 5 member who halves the barriers' extra damage
    and cuts caltrop damage to a third. Pictured as one shield of a Roman
    testudo: built like the player in the Knight's iron plate and open helm
    (without the plume), broad and low, crouched with the knees out behind a
    great shield held in both hands. The shield is a flat board, wider than
    the body, whose two ends bend back a little toward the body, like the
    bracket "〔" seen from above; straight edges and corners so shields would
    join without gaps. No weapon and no cloak. Heavy steel boots (proof
    against caltrops). `tone` picks one of `MEMBER_SKINS`.
    """
    mats = heavy_armor_materials(tone)
    plate, trim, red = mats[:3]

    def body(x, y, radius):
        # Both arms reach forward to the shield's grips.
        for side in (-1, 1):
            elbow = (x + side * (radius + 0.06), y - 0.18, 0.46)
            limb('Guardian upper arm', (x + side * (radius + 0.03), y - 0.05, 0.60), elbow,
                 0.18, 0.19, plate)
            limb('Guardian forearm', elbow, (x + side * 0.16, y - 0.30, 0.44), 0.17, 0.18, plate)

    heavy_armor_figure(x, y, 'Guardian', mats, [
        ((x + side * 0.11, y, 0.36), (x + side * 0.19, y - 0.04, 0.20),
         (x + side * 0.15, y, 0.06)) for side in (-1, 1)], body, lambda x, y: None,
        girth=1.15, boot=1.4)
    # The shield is built after the stretch, so it stays broad. Seen from
    # above it is a flat board with both ends bent back toward the body;
    # it faces straight ahead, leaned back a little toward the camera. Seen
    # from the front it is a shogi piece upside down, kept squarish: a
    # straight top, upright sides of even width, then two shallow slopes to
    # a blunt point. It is a little wider than the arms' span, so it sticks
    # out on both sides, and sits a little toward the left hand (screen right).
    half_flat, end, bend, height = 0.36 * 0.96, 0.14 * 0.96, math.radians(40), 0.74
    profile = [(-half_flat - end * math.cos(bend), end * math.sin(bend)), (-half_flat, 0.0),
               (half_flat, 0.0), (half_flat + end * math.cos(bend), end * math.sin(bend))]
    lengths = [(Vector(b) - Vector(a)).length for a, b in zip(profile, profile[1:])]
    total = sum(lengths)
    place = Matrix.Translation((x + 0.08, y - 0.40, 0.50)) @ Matrix.Rotation(-0.15, 4, 'X')

    def point(s, z, front=0.0):
        """The point `s` along the profile from the right (screen left) end,
        at height `z`, moved `front` out of the board's front face."""
        for (a, b), length in zip(zip(profile, profile[1:]), lengths):
            if s <= length + 1e-9 or b == profile[-1]:
                a, b = Vector(a), Vector(b)
                along = (b - a).normalized()
                normal = Vector((along.y, -along.x))
                flat_point = a + along * min(s, length) + normal * front
                return place @ Vector((flat_point.x, flat_point.y, z))
            s -= length

    # The outline as (s, z) on the unbent board.
    top, middle = height / 2, total / 2
    point_height = middle * math.tan(0.22)
    outline = [(0.0, top), (total, top), (total, -top + point_height), (middle, -top),
               (0.0, -top + point_height)]
    corners = [sum(lengths[:k]) for k in range(len(profile))]

    def clip(polygon, low, high):
        """The part of a convex (s, z) polygon between s = `low` and `high`."""
        for keep, edge in ((lambda p: p[0] >= low, low), (lambda p: p[0] <= high, high)):
            kept = []
            for p, q in zip(polygon, polygon[1:] + polygon[:1]):
                if keep(p):
                    kept.append(p)
                if keep(p) != keep(q):
                    t = (edge - p[0]) / (q[0] - p[0])
                    kept.append((edge, p[1] + t * (q[1] - p[1])))
            polygon = kept
        return polygon

    def surface(name, polygons, mat, front):
        """Flat faces for convex (s, z) polygons, split at the bends so each
        piece lies on one flat part of the board."""
        vertices, faces, index = [], [], {}
        for polygon in polygons:
            for low, high in zip(corners, corners[1:]):
                face = []
                for s, z in clip(polygon, low, high):
                    key = (round(s, 6), round(z, 6))
                    if key not in index:
                        index[key] = len(vertices)
                        vertices.append(tuple(point(s, z, front)))
                    if index[key] not in face:
                        face.append(index[key])
                if len(face) >= 3:
                    faces.append(tuple(face))
        return mesh_object(name, vertices, faces, mat, False)

    def inset(polygon, distance):
        """A convex (s, z) polygon moved in by `distance` on every side."""
        area = sum(p[0] * q[1] - q[0] * p[1] for p, q in zip(polygon, polygon[1:] + polygon[:1]))
        sign = 1 if area > 0 else -1
        lines = []
        for p, q in zip(polygon, polygon[1:] + polygon[:1]):
            ds, dz = q[0] - p[0], q[1] - p[1]
            length = math.hypot(ds, dz)
            lines.append(((p[0] - dz / length * sign * distance,
                           p[1] + ds / length * sign * distance), (ds, dz)))
        moved = []
        for (p1, d1), (p2, d2) in zip(lines[-1:] + lines[:-1], lines):
            t = (((p2[0] - p1[0]) * d2[1] - (p2[1] - p1[1]) * d2[0])
                 / (d1[0] * d2[1] - d1[1] * d2[0]))
            moved.append((p1[0] + t * d1[0], p1[1] + t * d1[1]))
        return moved

    board = surface('Guardian shield board', [outline], plate, 0.0)
    solid = board.modifiers.new('Shield thickness', 'SOLIDIFY')
    solid.thickness = 0.04
    # Steel rim round the edge, following the bends.
    rim = []
    for p, q in zip(outline, outline[1:] + outline[:1]):
        rim.append(p)
        crossings = sorted((s for s in corners if min(p[0], q[0]) < s < max(p[0], q[0])),
                           reverse=q[0] < p[0])
        rim += [(s, p[1] + (s - p[0]) / (q[0] - p[0]) * (q[1] - p[1])) for s in crossings]
    rim.append(outline[0])
    tube('Guardian shield rim', [point(s, z) for s, z in rim], [0.03] * len(rim), trim, sides=6)
    # A broad flat red band inside the rim, all the way round.
    outer, inner = inset(outline, 0.035), inset(outline, 0.155)
    count = len(outline)
    surface('Guardian shield red band',
            [[outer[k], outer[(k + 1) % count], inner[(k + 1) % count], inner[k]]
             for k in range(count)], red, 0.012)


def pegasus(x, y):
    """Pegasus companion: a small, slender fairy horse of glowing pearl,
    hovering with legs tucked under, on wide feathered wings large for its
    body, with a full mane and green resin hooves.
    """
    pearl = material('Pegasus fairy pearl', (0.78, 0.84, 0.95), 0.3, 0.22,
                     emission=(0.75, 0.9, 1.0), strength=0.04,
                     rim=(0.6, 0.95, 1.0), rim_strength=1.4, coat=0.8)
    wisp = companion_green('Pegasus deep green mane', 0.5, trim=True)
    feather = material('Pegasus feathers', (0.62, 0.95, 0.72), 0.5, 0.25,
                       emission=(0.5, 1.0, 0.65), strength=0.1,
                       rim=(0.8, 1.0, 0.85), rim_strength=1.4)
    eye = material('Pegasus eyes', (0.02, 0.03, 0.06), roughness=0.2, coat=1.0)
    green = companion_green('Pegasus deep green hooves', 0.5, trim=True)
    # Slender body, neck and head melted into one shape; head toward -Y with
    # a short muzzle.
    body = [((0, -0.12, 0.58), 0.25), ((0, 0.02, 0.56), 0.26), ((0, 0.16, 0.55), 0.25),
            ((0, 0.30, 0.56), 0.23), ((0, -0.22, 0.70), 0.17), ((0, -0.28, 0.84), 0.16),
            ((0, -0.35, 0.95), 0.21), ((0, -0.47, 0.92), 0.15)]
    hooves = []
    for side in (-1, 1):
        # Slim legs stretched fore and aft as if galloping through the air, so
        # the green hooves show past the body from above.
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
        finish(bpy.context.object, green, True, 'Pegasus green hoof')
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
    # Feathered wings, large for the body, raised up and swept back, shaped
    # like a raptor's: a bony leading edge runs out from the shoulder to the
    # wrist, broad secondaries hang from it toward the back, long primaries
    # spread like fingers past the wrist, and two rows of short coverts
    # overlap the roots.
    def vane_width(f, cap=0.72):
        if f <= cap:
            return math.sin(math.pi / 2 * f / cap) ** 0.6
        return math.sqrt(max(0.0, 1 - ((f - cap) / (1 - cap)) ** 2))

    for side in (-1, 1):
        shoulder = Vector((x + side * 0.14, y + 0.04, 0.76))
        out, up = Vector((side, 0, 0)), Vector((0, 0.6, 0.8)).normalized()
        # Toward the camera on both wings, so later layers lie on top.
        normal = out.cross(up) * side

        def add_feather(p, q, angle, length, width, lift):
            """A vane from (`p` out, `q` up) of the shoulder in the wing's
            plane, pointing `angle` degrees from `out` toward `up`."""
            a = math.radians(angle)
            along = out * math.cos(a) + up * math.sin(a)
            across = -out * math.sin(a) + up * math.cos(a)
            root = shoulder + out * p + up * q + normal * lift
            n, verts = 18, [tuple(root)]
            for t in range(1, n + 1):
                f = t / n
                verts.append(tuple(root + along * (length * f) + across * (width * vane_width(f))))
            for t in range(n - 1, 0, -1):
                f = t / n
                verts.append(tuple(root + along * (length * f)
                                   - across * (width * 0.5 * vane_width(f))))
            faces = [(0, i, i + 1) for i in range(1, len(verts) - 1)]
            vane = mesh_object('Pegasus feather', verts, faces, feather, True)
            vane.modifiers.new('Feather thickness', 'SOLIDIFY').thickness = 0.012

        # The leading edge: shoulder, elbow, wrist and the end of the hand.
        arm = [(0.0, 0.0), (0.20, 0.08), (0.38, 0.18), (0.50, 0.26)]

        def on_arm(t):
            """The point a fraction `t` along the leading edge."""
            t *= len(arm) - 1
            k = min(int(t), len(arm) - 2)
            (p0, q0), (p1, q1) = arm[k], arm[k + 1]
            return p0 + (p1 - p0) * (t - k), q0 + (q1 - q0) * (t - k)

        # Primaries from the hand, splayed apart at their narrow tips.
        for k in range(5):
            p, q = on_arm(0.68 + 0.08 * k)
            add_feather(p, q, 96 - 16 * k, 0.52 - 0.04 * k, 0.055, 0.003 * k)
        # Secondaries along the arm, broad and overlapping, pointing up and
        # a little back toward the body.
        for k in range(7):
            p, q = on_arm(0.04 + 0.105 * k)
            add_feather(p, q, 106 - 2 * k, 0.32 + 0.02 * k, 0.11, 0.016 + 0.003 * k)
        # Greater and lesser coverts over their roots.
        for row, (count, length, width, lift) in enumerate(((7, 0.20, 0.10, 0.04),
                                                            (6, 0.11, 0.09, 0.06))):
            for k in range(count):
                p, q = on_arm(0.04 + 0.80 * k / (count - 1))
                add_feather(p, q, 106 - 3 * k, length, width, lift + 0.003 * k)

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



def flame_cobra(x, y):
    """A coiled cobra with a fiery hood in the Fire Drake's palette, built
    like the drake from flat-shaded octagonal tubes."""
    scales = material('Cobra crimson scales', (0.80, 0.08, 0.03), 0.45, 0.2,
                      rim=(1.0, 0.55, 0.2), rim_strength=1.6, coat=0.8)
    flame = material('Cobra orange flame', (0.95, 0.22, 0.03), 0.7, 0.2,
                     emission=(1.0, 0.25, 0.02), strength=0.3,
                     rim=(1.0, 0.75, 0.3), rim_strength=1.2)
    belly = material('Cobra molten belly', (1.0, 0.55, 0.08), 0.3, 0.2,
                     emission=(1.0, 0.4, 0.05), strength=0.4,
                     rim=(1.0, 0.8, 0.4), rim_strength=0.8)
    eye = material('Cobra yellow eyes', (1.0, 0.9, 0.2), emission=(1.0, 0.85, 0.2),
                   strength=6.0)
    # A coil of a turn and three quarters, closed in the middle and rising
    # slightly toward it, from the tail tip outside to the neck at the back.
    points = []
    for i in range(15):
        t = i / 14
        angle = math.pi + 3.5 * math.pi * t
        radius = 0.50 - 0.38 * t
        points.append((x + radius * math.cos(angle),
                       y + radius * 0.85 * math.sin(angle), 0.10 + 0.10 * t))
    points += [(x, y + 0.12, 0.34), (x, y + 0.04, 0.58), (x, y, 0.84), (x, y - 0.02, 1.08)]
    radii = [0.01 + 0.14 * min(1, i / 5) for i in range(15)] + [0.15, 0.14, 0.13, 0.12]
    # Sample a curve through the control points, coarse enough that the
    # facets still show along the body.
    curve, widths = [], []
    for i in range(len(points) - 1):
        p0, p1 = Vector(points[max(0, i - 1)]), Vector(points[i])
        p2, p3 = Vector(points[i + 1]), Vector(points[min(len(points) - 1, i + 2)])
        for step in range(2):
            t = step / 2
            curve.append(tuple(0.5 * (2 * p1 + (-p0 + p2) * t
                                      + (2*p0 - 5*p1 + 4*p2 - p3) * t*t
                                      + (-p0 + 3*p1 - 3*p2 + p3) * t*t*t)))
            widths.append(radii[i] * (1 - t) + radii[i + 1] * t)
    curve.append(points[-1])
    widths.append(radii[-1])
    tube('Cobra coiled body', curve, widths, scales, sides=8, flat=0.8, twist=math.pi / 8)
    # A broad hood spreading like fire, with pointed flame tongues rising
    # from its edge, close behind the neck and leaning back a little.
    def hood(bx, bz):
        return Vector((x + bx, y + 0.06 + 0.3 * (bz - 0.6), bz))

    verts = [tuple(hood(bx, bz)) for bx, bz in [
        (0, 0.35), (-0.42, 0.73), (-0.43, 1.12), (-0.31, 1.02), (-0.24, 1.34), (0, 1.08),
        (0.24, 1.34), (0.31, 1.02), (0.43, 1.12), (0.42, 0.73)]]
    membrane = mesh_object('Cobra flame hood', verts, [(0, i, i + 1) for i in range(1, 9)],
                           flame, False)
    solid = membrane.modifiers.new('Hood thickness', 'SOLIDIFY')
    solid.thickness = 0.03
    solid.offset = 0
    tube('Cobra throat', [(x, y - 0.10, 0.56), (x, y - 0.13, 0.80), (x, y - 0.10, 1.02)],
         [(0.09, 0.04), (0.11, 0.05), (0.08, 0.04)], belly, sides=6)
    # Wedge head pointing forward, with a forked tongue.
    tube('Cobra head', [(x, y - 0.02, 1.13), (x, y - 0.18, 1.16), (x, y - 0.32, 1.12),
                        (x, y - 0.42, 1.07)],
         [(0.12, 0.08), (0.16, 0.09), (0.11, 0.07), 0], scales, sides=8, twist=math.pi / 8)
    for side in (-1, 1):
        sphere('Cobra eye', (x + side * 0.10, y - 0.26, 1.20), (0.04, 0.035, 0.028), eye, 16)
        cone('Cobra tongue', (x, y - 0.40, 1.05), (x + side * 0.04, y - 0.56, 1.02),
             0.015, 0, belly, 4, False)
        # Molten flames licking up each side of the hood, just in front of it.
        tube('Cobra hood flame', [hood(side * 0.35, 0.67) - Vector((0, 0.03, 0)),
                                  hood(side * 0.45, 0.95) - Vector((0, 0.03, 0)),
                                  hood(side * 0.48, 1.23) - Vector((0, 0.03, 0))],
             [0.055, 0.065, 0], belly, sides=6)


def spore(x, y):
    """Stage 4 spore monster (m): a stout mushroom with a dusky violet cap
    dotted with softly glowing spots, glowing spores drifting around it, and
    eyes on its stem glaring up at the player.

    Violet keeps it apart from the red caltrop plant and the green used for
    companions.
    """
    cap = material('Spore dusky violet cap', (0.30, 0.12, 0.40), 0.3, 0.35,
                   rim=(0.85, 0.6, 1.0), rim_strength=1.2, coat=0.5)
    gills = material('Spore mauve gills', (0.45, 0.30, 0.42), 0.2, 0.55)
    stem = material('Spore pale stem', (0.78, 0.72, 0.82), 0.35, 0.4,
                    rim=(0.9, 0.85, 1.0), rim_strength=0.6)
    glow = material('Spore pale glow', (0.95, 0.85, 1.0), emission=(0.9, 0.8, 1.0),
                    strength=3.0)
    sclera = material('Spore glaring eyes', (1.0, 0.92, 0.55), emission=(1.0, 0.85, 0.4),
                      strength=0.8)
    pupil = material('Spore matte pupils', (0.0, 0.0, 0.0), roughness=0.9)

    def lathe(name, profile, mat, base, segments=48):
        verts, rings = [], []
        for r, z in profile:
            if r == 0:
                rings.append([len(verts)])
                verts.append((base.x, base.y, base.z + z))
                continue
            rings.append(list(range(len(verts), len(verts) + segments)))
            verts += [(base.x + r * math.cos(2 * math.pi * k / segments),
                       base.y + r * math.sin(2 * math.pi * k / segments), base.z + z)
                      for k in range(segments)]
        faces = []
        for a, b in zip(rings, rings[1:]):
            if len(a) == 1:
                faces += [(a[0], b[k], b[(k + 1) % segments]) for k in range(segments)]
            elif len(b) == 1:
                faces += [(a[(k + 1) % segments], a[k], b[0]) for k in range(segments)]
            else:
                faces += [(a[k], b[k], b[(k + 1) % segments], a[(k + 1) % segments])
                          for k in range(segments)]
        return mesh_object(name, verts, faces, mat, True)

    # A stout stem swelling at the foot, tall enough to show below the cap
    # from the 60-degree camera.
    tube('Spore stem', [(x, y, 0.0), (x, y, 0.15), (x + 0.03, y, 0.50), (x, y + 0.02, 0.97)],
         [0.20, 0.18, 0.14, 0.11], stem, sides=24, smooth=True)
    sphere('Spore stem foot', (x, y, 0.04), (0.22, 0.22, 0.07), stem, 32)
    # Glaring eyes on the stem below the cap. The model is later turned by
    # MONSTER_YAW, so aim at the camera from the unturned frame; the pupils
    # sit high, looking up at the player.
    look = Matrix.Rotation(-MONSTER_YAW, 3, 'Z') @ Vector((0, -0.5, 0.866))
    pupil_dir = (look + Vector((0, 0, 0.45))).normalized()
    for side in (-1, 1):
        eye = Vector((x + side * 0.09, y - 0.145, 0.32))
        sphere('Spore glaring eye', tuple(eye), (0.075, 0.06, 0.075), sclera, 24)
        sphere('Spore pupil', tuple(eye + pupil_dir * 0.064), (0.034, 0.034, 0.034), pupil, 16)
    start = set(bpy.data.objects)
    base = Vector((x, y, 0.95))
    top = [(0, 0.22), (0.13, 0.21), (0.24, 0.17), (0.32, 0.11), (0.38, 0.04), (0.40, -0.01),
           (0.37, -0.05)]
    lathe('Spore cap', top, cap, base)
    lathe('Spore gills', [(0.37, -0.05), (0.24, -0.03), (0.10, 0.0), (0, 0.01)], gills, base)
    # Glowing spots scattered over the cap (profile position, angle in degrees).
    for t, a, size in ((0.4, 250, 0.05), (2.3, 215, 0.055), (2.6, 300, 0.045), (3.5, 255, 0.04),
                       (1.6, 160, 0.045), (1.8, 20, 0.045), (3.2, 120, 0.04), (1.2, 340, 0.04)):
        i = int(t)
        (r0, z0), (r1, z1) = top[i], top[i + 1]
        r, z = r0 + (r1 - r0) * (t - i), z0 + (z1 - z0) * (t - i)
        a = math.radians(a)
        sphere('Spore cap spot', (x + r * math.cos(a), y + r * math.sin(a), base.z + z - 0.01),
               (size, size, size * 0.6), glow, 16)
    # Tip the cap back so its front rim lifts and the gills face the camera,
    # with a slight lean to one side.
    tip = (Matrix.Translation(base) @ Matrix.Rotation(math.radians(-22), 4, 'X')
           @ Matrix.Rotation(math.radians(8), 4, 'Y') @ Matrix.Translation(-base))
    transform_new(start, tip)
    # A few spores drifting around the cap.
    for dx, dy, z, size in ((-0.55, -0.15, 1.05, 0.05), (0.52, -0.10, 1.20, 0.045),
                            (-0.25, -0.35, 1.32, 0.04), (0.50, 0.10, 0.60, 0.04),
                            (-0.50, 0.05, 0.50, 0.035)):
        sphere('Drifting spore', (x + dx, y + dy, z), (size, size, size), glow, 16)


def marksman(x, y):
    """Stage 4 marksman (k): a stout little gnome in an iron helmet with
    bushy white brows, gripping a longbow taller than himself at his side,
    with a quiver of fletched arrows on his back.

    Heights shrink to half in the 60-degree view, so the head is tilted back
    for the face to look up at the camera.
    """
    tunic = material('Marksman leather tunic', (0.30, 0.16, 0.07), 0.0, 0.55,
                     rim=(1.0, 0.75, 0.5), rim_strength=0.8)
    iron = material('Marksman iron helmet', (0.30, 0.31, 0.34), roughness=0.35, metallic=0.8,
                    rim=(0.8, 0.85, 1.0), rim_strength=0.8)
    bronze = material('Marksman bronze trim', (0.55, 0.30, 0.12), roughness=0.3, metallic=0.9)
    # Ashen blue skin marks him as a monster rather than a person.
    skin = material('Marksman ashen blue skin', (0.36, 0.47, 0.62), 0.2, 0.4,
                    rim=(0.75, 0.85, 1.0), rim_strength=0.6)
    tuft = material('Marksman white tufts', (0.90, 0.90, 0.92), 0.1, 0.5,
                    rim=(0.9, 0.95, 1.0), rim_strength=0.8)
    eye = material('Marksman eyes', (0.02, 0.02, 0.03), roughness=0.2, coat=1.0)
    wood = material('Marksman arrow shafts', (0.62, 0.36, 0.14), 0.0, 0.4,
                    rim=(1.0, 0.8, 0.5), rim_strength=0.8, coat=0.4)
    bow = material('Marksman bone-white bow', (0.88, 0.85, 0.76), 0.1, 0.35,
                   rim=(1.0, 0.97, 0.9), rim_strength=0.8, coat=0.5)
    string = material('Marksman bowstring', (0.85, 0.82, 0.70), roughness=0.6)
    feather = material('Marksman pale fletching', (0.92, 0.90, 0.84), 0.1, 0.5)
    boot = material('Marksman dark boots', (0.08, 0.06, 0.05), roughness=0.5)
    # Squat body in a belted tunic, boots peeking out in front.
    tube('Marksman tunic', [(x, y, 0.02), (x, y, 0.20), (x, y, 0.40), (x, y, 0.50)],
         [0.25, 0.23, 0.20, 0.12], tunic, sides=32, smooth=True)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.225, minor_radius=0.025, location=(x, y, 0.24))
    finish(bpy.context.object, boot, True, 'Marksman belt')
    for side in (-1, 1):
        sphere('Marksman boot', (x + side * 0.10, y - 0.20, 0.05), (0.08, 0.11, 0.06), boot, 16)
    # Quiver on the back, its fletchings above the left shoulder.
    tube('Marksman quiver', [(x + 0.10, y + 0.20, 0.18), (x + 0.16, y + 0.22, 0.58)],
         [0.07, 0.08], tunic, sides=12, smooth=True)
    for dx, dy in ((0.13, 0.20), (0.18, 0.24), (0.19, 0.18)):
        tube('Marksman arrow', [(x + dx, y + dy, 0.55), (x + dx + 0.02, y + dy, 0.72)],
             [0.012, 0.012], wood, sides=6)
        cone('Marksman fletching', (x + dx + 0.02, y + dy, 0.68), (x + dx + 0.03, y + dy, 0.80),
             0.04, 0.012, feather, 4, False)
    # A huge bone-white longbow at his side (screen left), gripped at its
    # leather-wrapped middle at hand height; its upper tip towers far above
    # his head and its lower tip sinks below the floor.
    length = 2.2
    foot = Vector((x - 0.30, y - 0.10, 0.58 - length / 2))
    limb = []
    for i in range(13):
        t = i / 12
        limb.append(foot + Vector((-0.22 * math.sin(math.pi * t),
                                   -0.07 * math.sin(math.pi * t) + 0.06 * t, t * length)))
    tube('Marksman longbow', limb, [0.02, 0.027, 0.032, 0.036, 0.04, 0.043, 0.047, 0.043,
                                    0.04, 0.036, 0.032, 0.027, 0.02], bow, sides=8,
         smooth=True)
    # A thick string, so it still shows at sprite size.
    tube('Marksman bowstring', [limb[0], limb[-1]], [0.015, 0.015], string, sides=8)
    tube('Marksman bow grip', [limb[5], limb[7]], [0.052, 0.052], boot, sides=10, smooth=True)
    # Right arm (screen left) out to the grip; left hand on the belt.
    hold = limb[6]
    # The elbow sits outward past the string, a little back and below the
    # shoulder, so the upper arm passes just behind the string instead of
    # through it and the forearm rises to the grip.
    tube('Marksman right arm', [(x - 0.18, y, 0.44), (x - 0.40, y + 0.06, 0.34), hold],
         [0.06, 0.055, 0.05], tunic, sides=12, smooth=True)
    sphere('Marksman right hand', tuple(hold), (0.055, 0.055, 0.055), skin, 16)
    tube('Marksman left arm', [(x + 0.18, y, 0.44), (x + 0.26, y - 0.06, 0.32),
                               (x + 0.15, y - 0.18, 0.26)], [0.06, 0.055, 0.05], tunic,
         sides=12, smooth=True)
    sphere('Marksman left hand', (x + 0.14, y - 0.19, 0.26), (0.055, 0.05, 0.05), skin, 16)
    # Head with a big nose, bushy white brows and an iron helmet, tilted back.
    start = set(bpy.data.objects)
    head = Vector((x, y, 0.66))
    sphere('Marksman head', tuple(head), (0.17, 0.16, 0.17), skin, 32)
    sphere('Marksman nose', (x, y - 0.17, 0.64), (0.05, 0.05, 0.045), skin, 16)
    for side in (-1, 1):
        sphere('Marksman eye', (x + side * 0.065, y - 0.145, 0.70), (0.024, 0.014, 0.03), eye, 12)
        sphere('Marksman bushy brow', (x + side * 0.07, y - 0.15, 0.745), (0.045, 0.02, 0.018),
               tuft, 12)
    # An iron helmet: a domed bowl sitting above the brows, a bronze band
    # round its rim and a short spike on top.
    rim_z, ring, verts = 0.77, 40, []
    for level in range(9):
        phi = math.pi / 2 * level / 9
        for k in range(ring):
            a = 2 * math.pi * k / ring
            verts.append((x + 0.195 * math.cos(phi) * math.cos(a),
                          y + 0.01 + 0.19 * math.cos(phi) * math.sin(a),
                          rim_z + 0.16 * math.sin(phi)))
    verts.append((x, y + 0.01, rim_z + 0.16))
    faces = [(l * ring + k, l * ring + (k + 1) % ring, (l + 1) * ring + (k + 1) % ring,
              (l + 1) * ring + k) for l in range(8) for k in range(ring)]
    faces += [(8 * ring + k, 8 * ring + (k + 1) % ring, 9 * ring) for k in range(ring)]
    helmet = mesh_object('Marksman iron helmet', verts, faces, iron, True)
    helmet.modifiers.new('Helmet thickness', 'SOLIDIFY').thickness = 0.015
    bpy.ops.mesh.primitive_torus_add(major_radius=0.195, minor_radius=0.026,
                                     location=(x, y + 0.01, rim_z))
    bpy.context.object.scale.y = 0.19 / 0.195
    finish(bpy.context.object, bronze, True, 'Marksman helmet band')
    cone('Marksman helmet spike', (x, y + 0.01, rim_z + 0.15), (x, y + 0.01, rim_z + 0.27),
         0.04, 0, bronze, 12, True)
    neck = Vector((x, y, 0.50))
    transform_new(start, Matrix.Translation(neck) @ Matrix.Rotation(-0.45, 4, 'X')
                  @ Matrix.Translation(-neck))

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

    def stripe(part, side, length):
        """A rune line down the outer side of a limb, like a tracksuit's
        side stripe, so the golem does not read as an ape."""
        bpy.context.view_layer.update()
        offset = Vector((side * (part.dimensions.x / 2 + 0.005), 0, 0))
        block('Golem side stripe', tuple(part.matrix_world @ offset), (0.02, 0.035, length),
              rune, 0.006, part.rotation_euler)

    for side in (-1, 1):
        leg = block('Golem leg', (x + side * 0.20, y + 0.06, 0.17), (0.24, 0.26, 0.34), basalt,
                    0.03, (0, 0, side * 0.08))
        stripe(leg, side, 0.30)
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
    # Two square eyes of different sizes at slightly different heights, like
    # an old robot's. No brow ridge: it made the face read as an ape's.
    for dx, z, size in ((-0.075, 1.165, 0.08), (0.075, 1.125, 0.055)):
        block('Golem eye', (x + dx, y - 0.195, z), (size, 0.02, size), rune, 0.008)
    for side in (-1, 1):
        for i, (dx, dy, z, r) in enumerate(((0.48, 0.0, 1.02, 0.19), (0.36, 0.08, 1.10, 0.12))):
            bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=r,
                                                  location=(x + side * dx, y + dy, z),
                                                  rotation=(i * 0.7 + side, 0.4, i * 0.3))
            finish(bpy.context.object, basalt, False, 'Golem shoulder boulder')
        upper_arm = block('Golem upper arm', (x + side * 0.58, y, 0.80), (0.20, 0.22, 0.34),
                          slate, 0.03, (0, side * 0.15, 0))
        stripe(upper_arm, side, 0.30)
        forearm = block('Golem forearm', (x + side * 0.64, y - 0.04, 0.52), (0.22, 0.24, 0.30),
                        basalt, 0.03, (0, side * 0.05, 0))
        stripe(forearm, side, 0.26)
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


builders = {'@': player, '@c': lambda x, y: player(x, y, 'c'),
            '@C': lambda x, y: player(x, y, 'C'), '@K': lambda x, y: player(x, y, 'blessed'),
            'a': lambda x, y: amoeba(x, y, False),
            'A': lambda x, y: amoeba(x, y, True), 'b': bison, 'B': buffalo, 'd': dragon,
            'c': chimera, 'T': treasure, 'M': lambda x, y: treasure(x, y, True), 'D': great_dragon, 'l': loop_watch, 'n': nomicon, 'o': ocular,
            'C': lambda x, y: chimera(x, y, True), 'F': lambda x, y: great_dragon(x, y, True),
            "'": lambda x, y: rank_mark(x, y, 1), '"': lambda x, y: rank_mark(x, y, 2),
            'g': golem, 'w': wyrm, 'W': lambda x, y: wyrm(x, y, True), 'V': vortex, 'k': marksman, 'm': spore, 'f': flame_cobra, 'e': lambda x, y: erebus(x, y, False),
            'E': lambda x, y: erebus(x, y, True), 'X': caltrop_plant, 'p': pegasus,
            'H': high_elf, 'I': isolated_elf, 'J': javelin_elf, 'K': collector_elf,
            'L': lifebringer_elf, 'S': sylvan_elf, 'rock': golem_rock,
            **{'jester-' + tone: (lambda tone: lambda x, y: jester(x, y, tone))(tone)
               for tone in MEMBER_SKINS},
            **{'healer-' + tone: (lambda tone: lambda x, y: healer(x, y, tone))(tone)
               for tone in MEMBER_SKINS},
            **{'rogue-' + tone: (lambda tone: lambda x, y: rogue(x, y, tone))(tone)
               for tone in MEMBER_SKINS},
            **{'explorer-' + tone: (lambda tone: lambda x, y: dungeon_explorer(x, y, tone))(tone)
               for tone in MEMBER_SKINS},
            **{'knight-' + tone: (lambda tone: lambda x, y: knight(x, y, tone))(tone)
               for tone in MEMBER_SKINS},
            **{'guardian-' + tone: (lambda tone: lambda x, y: guardian(x, y, tone))(tone)
               for tone in MEMBER_SKINS}}
def render_group_shot():
    """Open the others' scene, bring in the other groups, and render them all."""
    bpy.ops.wm.open_mainfile(filepath=str(blend_path('others')))
    scene = bpy.context.scene
    for group in ('monsters', 'members'):
        with bpy.data.libraries.load(str(blend_path(group))) as (source, loaded):
            loaded.collections = [name for name in source.collections
                                  if name.startswith('Character ')]
        for collection in loaded.collections:
            scene.collection.children.link(collection)
    # The preview's time goes mostly to Cycles treating every triangle of the
    # softly glowing meshes as a light; glows still show without that, so turn
    # it off for this group shot only (the saved scene, used for the sprites,
    # keeps it). This about halves the render time.
    for mat in bpy.data.materials:
        mat.cycles.emission_sampling = 'NONE'
    # The area lights sit near the origin and fall off toward the ends of
    # this wide group shot; for the preview only, swap each for a sun from
    # the same direction so every character is lit alike. The sun strength
    # matches the area light's irradiance at the origin (power / (pi d^2)),
    # and its angle matches the area light's apparent size.
    for light in [obj for obj in scene.objects if obj.type == 'LIGHT']:
        distance = light.location.length
        sun = bpy.data.lights.new(light.name + ' sun', 'SUN')
        sun.energy = light.data.energy / (math.pi * distance * distance)
        sun.angle = 2 * math.atan(light.data.size / 2 / distance)
        sun.color = light.data.color
        light.data = sun
    scene.render.filepath = str(OUT / 'preview-angle60.png')
    bpy.ops.render.render(write_still=True)


if GROUP is None:
    # Build all the scenes at once, each in its own Blender.
    children = [subprocess.Popen([bpy.app.binary_path, '--background', '--threads', '4',
                                  '--python-exit-code', '1', '--python', __file__,
                                  '--', '--group', group]) for group in GROUPS]
    if any([child.wait() for child in children]):
        sys.exit('Building a scene failed')
    if '--save-only' not in sys.argv:
        render_group_shot()
    sys.exit(0)
for char, name, x, y in ROW:
    if group_of(char) != GROUP:
        continue
    start = set(bpy.data.objects)
    builders[char](x, y)
    character = set(bpy.data.objects) - start
    bpy.context.view_layer.update()
    pivot = Matrix.Translation((x, y, 0))
    yaw = (MONSTER_YAW if char in 'aAbBcdDCFfgkmeEXTM' else WYRM_YAW if char in 'wW'
           else PEGASUS_YAW if char == 'p' else 0)
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
    if char not in ("'", '"'):
        label(name, (x, y - CELL_D / 2 + 0.12, 0.005), 0.12)
    collection = bpy.data.collections.new('Character ' + char + ' ' + name)
    scene.collection.children.link(collection)
    for obj in set(bpy.data.objects) - start:
        for old in list(obj.users_collection):
            old.objects.unlink(obj)
        collection.objects.link(obj)
        obj['sprite'] = obj in character
        if char in ("'", '"'):
            obj.hide_render = True

bpy.ops.mesh.primitive_plane_add(size=80, location=(0, 0, -0.1))
finish(bpy.context.object, dark, True, 'Backdrop')
# Floor tiles, one per game cell, in two shades like the game's checkered
# flagstones.
tile_dark = material('Darker floor tile', (0.035, 0.045, 0.06), 0.3, 0.4,
                     rim=(0.25, 0.55, 0.9), rim_strength=0.4)
for row in range(GRID_ROWS):
    for col in range(GRID_COLS):
        cx, cy = cell_centre(col, row)
        block('Floor tile', (cx, cy, -0.05), (CELL_W - 0.04, CELL_D - 0.04, 0.1),
              tile if (col + row) % 2 == 0 else tile_dark, 0.02)
label('ARLQ / STAGE 1-5 / HEROIC RESIN', (0, CELL_D / 2 + 0.5, 0.0), 0.2)
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
# Frame the whole grid, with room above the back row for tall characters
# and the title.
grid_width = GRID_COLS * CELL_W + 0.6
grid_height = (GRID_ROWS * CELL_D) * math.sin(angle) + 1.9
target = Vector((0, -(GRID_ROWS - 1) * CELL_D / 2 + 0.6, 0))
camera.location = target + Vector((0, -15 * math.cos(angle), 15 * math.sin(angle)))
camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
camera.data.type = 'ORTHO'
camera.data.ortho_scale = grid_width
scene.render.resolution_x = 1600
scene.render.resolution_y = round(1600 * grid_height / grid_width)
scene.camera = camera
scene['sprite_centers'] = {char: list(pos) for char, pos in CENTERS.items()}
bpy.ops.wm.save_as_mainfile(filepath=str(blend_path(GROUP)))
