"""Collapse pit for the sprite GUI.

Run with: blender --background --threads 4 --python dev-samples/3d-stage1/build-pit.py

A Collapse pit (O) is a jagged hole broken through the flagstones: cracked
slabs sag toward a dark shaft, with a few chunks falling into it. It is
rendered with the walls' 60-degree orthographic camera, 1.2 times its
original size, on a canvas that also reaches past each side of the cell, so
the GUI places it like a stair. The slabs are a cool grey that the GUI's gold tint (the pit glyph was
yellow) turns close to the floor's warm grey.
"""
from pathlib import Path
import math
import random

import bmesh
import bpy
from mathutils import Euler, Vector

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
SLAB_COLOR = (0.14, 0.15, 0.27)
EDGE_POINTS = 20


def material(name, color, roughness=0.8):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (*color, 1)
    bsdf.inputs['Roughness'].default_value = roughness
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


def solidify(obj, thickness):
    mod = obj.modifiers.new('Thickness', 'SOLIDIFY')
    mod.thickness = thickness
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

slab = material('Cracked slab', SLAB_COLOR)
shaft = material('Shaft wall', (0.05, 0.05, 0.08), roughness=0.95)
void = material('Void', (0.0, 0.0, 0.0), roughness=1.0)
ground = holdout('Ground')

# The hole's jagged edge and the outer edge of the sagging slabs around it,
# both irregular ellipses about the cell centre (the y radius is larger so
# the hole looks round on the cell, which is taller than wide on screen).
rng = random.Random(7)
cy = DEPTH * (0.5 + PIT_NORTH)
rx, ry = PIT_SCALE * HOLE_RADII[0], PIT_SCALE * HOLE_RADII[1] * DEPTH
hole, rim = [], []
for i in range(EDGE_POINTS):
    a = 2 * math.pi * i / EDGE_POINTS
    r = 1 + rng.uniform(-0.16, 0.12)
    hole.append((rx * r * math.cos(a), cy + ry * r * math.sin(a)))
    s = r * rng.uniform(1.18, 1.28)
    rim.append((rx * s * math.cos(a), cy + ry * s * math.sin(a)))
hole_z, rim_z, shaft_z = -0.07, 0.0, -0.6

# Broken slabs: two rim segments each, shrunk toward their centre so the
# gaps between them read as cracks, every one tilted a little differently.
for i in range(0, EDGE_POINTS, 2):
    j, k = (i + 1) % EDGE_POINTS, (i + 2) % EDGE_POINTS
    sag = rng.uniform(0.6, 1.4)
    points = [Vector((*hole[n], hole_z * sag)) for n in (i, j, k)]
    points += [Vector((*rim[n], rim_z)) for n in (k, j, i)]
    centre = sum(points, Vector()) / len(points)
    points = [centre + (p - centre) * 0.93 for p in points]
    piece = mesh_object('Slab %d' % i, [points], slab)
    solidify(piece, 0.05)
    bevel = piece.modifiers.new('Worn edges', 'BEVEL')
    bevel.width = 0.01
    bevel.segments = 2

# The shaft: walls from the hole's edge down to a black bottom, narrowing a
# little, so the far (north) wall shows faintly under the broken edge.
walls = []
for i in range(EDGE_POINTS):
    j = (i + 1) % EDGE_POINTS
    walls.append([Vector((*hole[i], hole_z)), Vector((*hole[j], hole_z)),
                  Vector((hole[j][0] * 0.85, cy + (hole[j][1] - cy) * 0.85, shaft_z)),
                  Vector((hole[i][0] * 0.85, cy + (hole[i][1] - cy) * 0.85, shaft_z))])
mesh_object('Shaft', walls, shaft)
bpy.ops.mesh.primitive_plane_add(size=3, location=(0, cy, shaft_z - 0.01))
bpy.context.object.data.materials.append(void)
bottom = bpy.context.object

# Ground outside the slabs: invisible, but it hides the shaft from outside.
far = [(3 * x, cy + 3 * (y - cy)) for x, y in rim]
mesh_object('Ground', [[Vector((*rim[i], 0.001)), Vector((*rim[(i + 1) % EDGE_POINTS], 0.001)),
                        Vector((*far[(i + 1) % EDGE_POINTS], 0.001)), Vector((*far[i], 0.001))]
                       for i in range(EDGE_POINTS)], ground)

# A few chunks falling into the dark.
for n, (x, y, z, size) in enumerate(((-0.08, 0.10, -0.22, 0.10),
                                     (0.10, -0.12, -0.32, 0.08),
                                     (0.02, 0.28, -0.40, 0.06))):
    bpy.ops.mesh.primitive_cube_add(size=PIT_SCALE * size,
                                    location=(PIT_SCALE * x, cy + PIT_SCALE * y, z))
    chunk = bpy.context.object
    chunk.name = 'Chunk %d' % n
    chunk.scale = (1.3, 1.0, 0.45)
    chunk.rotation_euler = Euler([rng.uniform(-0.8, 0.8) for _ in range(3)])
    chunk.data.materials.append(slab)

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
lines.linestyle.thickness = 4.0
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'
scene.render.filepath = str(OUT / 'pit.png')
bpy.ops.render.render(write_still=True)
