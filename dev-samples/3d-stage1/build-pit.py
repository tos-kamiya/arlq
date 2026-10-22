"""Collapse pit for the sprite GUI.

Run with: blender --background --threads 4 --python dev-samples/3d-stage1/build-pit.py

A Collapse pit (O) is a shapeless hole in the floor with rough rock walls,
with rocks lying around its edge and a few chunks falling into it. It is
rendered with the walls' 60-degree orthographic camera, 1.2 times its
original size, on a canvas that also reaches past each side of the cell, so
the GUI places it like a stair. The rock is a cool grey that the GUI's gold
tint (the pit glyph was yellow) turns to a neutral stone grey.

A second image, fallen-rocks.png, is a few of the same rocks on the same
canvas, which the GUI scatters on the floor below a pit.
"""
from pathlib import Path
import math
import random

import bmesh
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parents[1] / 'src' / 'arlq' / 'assets' / 'pit'
OUT.mkdir(parents=True, exist_ok=True)
# The canvas covers one 15 x 20 px cell, 0.25 cells past each side (drawn by
# the GUI only over explored floor) and the 0.25-cell band north of it
# (sprite_funcs.TERRAIN_SIDE, TERRAIN_OVERHANG).
CELL_PIXELS = (300, 400)  # 15 x 20 at 20 px per screen pixel
SIDE, OVERHANG = 0.25, 0.25
WIDTH = round(CELL_PIXELS[0] * (1 + 2 * SIDE))
HEIGHT = round(CELL_PIXELS[1] * (1 + OVERHANG))
ELEVATION = math.radians(60)
CELL_UP = CELL_PIXELS[1] / CELL_PIXELS[0]  # cell height on the image plane
DEPTH = CELL_UP / math.sin(ELEVATION)  # the cell spans y = 0 (south) to DEPTH
# The hole's radii as fractions of the cell's width and depth (its size on
# the original 13 x 20 cells), enlarged by PIT_SCALE; its centre sits this
# fraction of the depth north of the cell's middle, so the larger slabs stay
# within the canvas.
HOLE_RADII = (0.36 * 13 / 15, 0.36)
PIT_SCALE = 1.2
PIT_NORTH = 0.12
ROCK_COLOR = (0.24, 0.27, 0.44)
SHAFT_COLOR = (0.10, 0.11, 0.16)
EDGE_POINTS = 18
# Rocks around the edge: (angle in degrees from east, counterclockwise;
# distance from the centre as a fraction of the hole's radii; size).
ROCKS = ((-80, 1.12, 0.13), (-55, 1.18, 0.08), (-110, 1.10, 0.09),
         (-150, 1.08, 0.12), (175, 1.15, 0.07), (140, 1.05, 0.10),
         (95, 1.02, 0.08), (40, 1.08, 0.11), (10, 1.20, 0.07),
         (-20, 1.10, 0.10))
RUBBLE = 14
# Rocks fallen onto the floor below a pit: (x as a fraction of the cell's
# width from its centre, y as a fraction of its depth from the south edge,
# size).
FALLEN_ROCKS = ((-0.15, 0.42, 0.12), (0.17, 0.56, 0.09), (0.03, 0.27, 0.07),
                (-0.06, 0.68, 0.06), (0.28, 0.32, 0.05))
SHAFT_RINGS = 5
# The top of the wall, just below the edge, is lighter rock.
LIP_DEPTH = 0.07
SHAFT_Z = -0.8

def material(name, color, roughness=0.8, rough_bump=False):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (*color, 1)
    bsdf.inputs['Roughness'].default_value = roughness
    if rough_bump:
        # A fine pitted surface, like cast concrete or cut stone.
        noise = nodes.new('ShaderNodeTexNoise')
        noise.inputs['Scale'].default_value = 60
        noise.inputs['Detail'].default_value = 6
        bump = nodes.new('ShaderNodeBump')
        bump.inputs['Strength'].default_value = 0.35
        bump.inputs['Distance'].default_value = 0.01
        links.new(noise.outputs['Fac'], bump.inputs['Height'])
        links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    return mat

def holdout(name):
    """Invisible ground that still hides what lies below the floor."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.remove(nodes['Principled BSDF'])
    shader = nodes.new('ShaderNodeHoldout')
    mat.node_tree.links.new(shader.outputs[0], nodes['Material Output'].inputs['Surface'])
    return mat

def mesh_object(name, faces, mat):
    """An object from faces given as lists of world-space points."""
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    for points in faces:
        bm.faces.new([bm.verts.new(p) for p in points])
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    return obj

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 128
scene.cycles.use_denoising = False
scene.cycles.sample_clamp_indirect = 2.0
scene.view_settings.view_transform = 'Standard'
scene.view_settings.look = 'Medium High Contrast'
scene.render.resolution_x, scene.render.resolution_y = WIDTH, HEIGHT
scene.render.film_transparent = True
world = bpy.data.worlds.new('Night studio')
world.use_nodes = True
world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.05, 0.06, 0.08, 1)
scene.world = world

rock = material('Rock', ROCK_COLOR, rough_bump=True)
shaft = material('Shaft wall', SHAFT_COLOR, roughness=0.95, rough_bump=True)
void = material('Void', (0.0, 0.0, 0.0), roughness=1.0)
ground = holdout('Ground')

# The hole's edge, a shapeless loop about the cell centre (the y radius is
# larger so the hole looks round on the cell, which is taller than wide on
# screen): smooth random bulges plus a little jitter.
rng = random.Random(7)
cy = DEPTH * (0.5 + PIT_NORTH)
rx, ry = PIT_SCALE * HOLE_RADII[0], PIT_SCALE * HOLE_RADII[1] * DEPTH
phases = [rng.uniform(0, 2 * math.pi) for _ in range(3)]

def edge_radius(a):
    return (0.95 + 0.08 * math.sin(2 * a + phases[0]) + 0.06 * math.sin(3 * a + phases[1])
            + 0.04 * math.sin(5 * a + phases[2]))

def edge_point(a, r, z):
    return Vector((rx * r * math.cos(a), cy + ry * r * math.sin(a), z))

angles = [2 * math.pi * i / EDGE_POINTS for i in range(EDGE_POINTS)]
hole = [edge_point(a, edge_radius(a) * rng.uniform(0.94, 1.04), 0.0) for a in angles]

# Rough rock walls from the edge down to a black bottom, narrowing and
# jittered ring by ring so they look broken rather than dug.
lip = [edge_point(a, edge_radius(a) * rng.uniform(0.92, 0.98), -LIP_DEPTH) for a in angles]
rings = [lip]
for k in range(1, SHAFT_RINGS + 1):
    t = k / SHAFT_RINGS
    rings.append([edge_point(a, edge_radius(a) * (0.95 - 0.18 * t) * rng.uniform(0.9, 1.06),
                             SHAFT_Z * t + rng.uniform(-0.03, 0.03))
                  for a in angles])


def wall(name, upper_lower, mat):
    mesh_object(name, [[upper[i], upper[(i + 1) % EDGE_POINTS],
                        lower[(i + 1) % EDGE_POINTS], lower[i]]
                       for upper, lower in upper_lower for i in range(EDGE_POINTS)], mat)


wall('Lip', [(hole, lip)], rock)
wall('Shaft', zip(rings, rings[1:]), shaft)
bpy.ops.mesh.primitive_plane_add(size=3, location=(0, cy, SHAFT_Z - 0.05))
bpy.context.object.data.materials.append(void)

# Ground around the hole: invisible, but it hides the shaft from outside.
far = [Vector((3 * p.x, cy + 3 * (p.y - cy), 0)) for p in hole]
mesh_object('Ground', [[hole[i], hole[(i + 1) % EDGE_POINTS],
                        far[(i + 1) % EDGE_POINTS], far[i]] for i in range(EDGE_POINTS)],
            ground)

def boulder(name, location, size, flat=0.6):
    """An irregular, angular rock: a coarse sphere with its corners pushed
    about and its bottom cut flat so it sits on the ground."""
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=size, location=location)
    obj = bpy.context.object
    obj.name = name
    for v in obj.data.vertices:
        v.co = v.co * rng.uniform(0.7, 1.2) + Vector([rng.uniform(-0.2, 0.2) * size
                                                      for _ in range(3)])
        v.co.z = max(v.co.z, -0.35 * size)
    obj.scale = (rng.uniform(1.0, 1.5), rng.uniform(0.7, 1.1), flat * rng.uniform(0.8, 1.2))
    obj.rotation_euler = (rng.uniform(-0.15, 0.15), rng.uniform(-0.15, 0.15),
                          rng.uniform(0, 2 * math.pi))
    obj.data.materials.append(rock)
    return obj


# Rocks lying around the edge, some leaning over it.
for n, (deg, dist, size) in enumerate(ROCKS):
    a = math.radians(deg)
    p = edge_point(a, edge_radius(a) * dist, 0.0)
    boulder('Rock %d' % n, (p.x, p.y, 0.2 * size), PIT_SCALE * size)
# Rubble between them.
for n in range(RUBBLE):
    a = rng.uniform(0, 2 * math.pi)
    size = rng.uniform(0.03, 0.05)
    p = edge_point(a, edge_radius(a) * rng.uniform(1.04, 1.3), 0.0)
    boulder('Rubble %d' % n, (p.x, p.y, 0.2 * size), PIT_SCALE * size)

# A few chunks falling into the dark.
for n, (x, y, z, size) in enumerate(((-0.08, 0.10, -0.25, 0.07),
                                     (0.10, -0.10, -0.40, 0.06),
                                     (0.02, 0.24, -0.55, 0.045))):
    boulder('Chunk %d' % n, (PIT_SCALE * x, cy + PIT_SCALE * y, z), PIT_SCALE * size, flat=0.8)

# The key light is above and slightly behind the cell, as for the stairs, so
# the slab tops are lit and the shaft stays dark.
for pos, power, size, color in [((-3, 3, 9), 420, 5, (1.0, 0.93, 0.85)),
                                 ((6, -3, 4), 120, 6, (0.6, 0.75, 1.0)),
                                 ((-6, 6, 4), 300, 3, (0.55, 0.8, 1.0)),
                                 ((6, 6, 4), 300, 3, (1.0, 0.7, 0.9))]:
    bpy.ops.object.light_add(type='AREA', location=pos)
    light = bpy.context.object
    light.data.energy, light.data.size, light.data.color = power, size, color
    light.rotation_euler = (Vector((0, 0, 0)) - light.location).to_track_quat('-Z', 'Y').to_euler()

# Frame the canvas from the cell's south edge on the ground (image-plane
# up = 0) to OVERHANG cells above its north edge, SIDE cells past each side.
height = CELL_UP * (1 + OVERHANG)
view = Vector((0, math.cos(ELEVATION), -math.sin(ELEVATION)))
image_up = Vector((0, math.sin(ELEVATION), math.cos(ELEVATION)))
bpy.ops.object.camera_add(location=image_up * (height / 2) - view * 20)
camera = bpy.context.object
camera.rotation_euler = view.to_track_quat('-Z', 'Y').to_euler()
camera.data.type = 'ORTHO'
camera.data.ortho_scale = max(height, 1 + 2 * SIDE)
scene.camera = camera

scene.render.use_freestyle = True
settings = scene.view_layers[0].freestyle_settings
lines = settings.linesets[0] if settings.linesets else settings.linesets.new('Outline')
lines.select_silhouette = lines.select_border = False
lines.select_external_contour = True
lines.select_crease = False
lines.linestyle = bpy.data.linestyles.new('Ink outline')
lines.linestyle.color = (0.04, 0.05, 0.07)
lines.linestyle.thickness = 3.0
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'
scene.render.filepath = str(OUT / 'pit.png')
bpy.ops.render.render(write_still=True)

# Rocks fallen through a pit onto the floor below: a small cluster on the
# same canvas, without the hole.
for obj in [obj for obj in scene.objects if obj.type == 'MESH']:
    bpy.data.objects.remove(obj)
for n, (x, y, size) in enumerate(FALLEN_ROCKS):
    boulder('Fallen rock %d' % n, (x, DEPTH * y, 0.2 * size), PIT_SCALE * size)
# No outline, like the rocks around the pit (their outline is lost to the
# holdout ground).
scene.render.use_freestyle = False
scene.render.filepath = str(OUT / 'fallen-rocks.png')
bpy.ops.render.render(write_still=True)
