"""Marble column wall parts for the sprite GUI.

Run with: blender --background --threads 4 --python dev-samples/3d-stage1/build-walls.py

Every wall cell gets one column. Each part is rendered with the same
60-degree orthographic camera on the same canvas, which covers one cell plus
the band it rises into the cell to its north, so the GUI can stack them:
  wall-column.png      plinth, shaft and capital
  wall-link-west.png   architrave and plinth reaching the west edge
  wall-link-east.png   the same toward the east edge
The parts are near-white; the GUI tints them for visible/explored walls.
"""
from pathlib import Path
import math
import sys

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parents[1] / 'src' / 'arlq' / 'assets' / 'walls'
OUT.mkdir(parents=True, exist_ok=True)
# Canvas aspect: one cell (13 x 20 px at scale 1) plus a 0.25-cell rise.
WIDTH, HEIGHT = 260, 500
ELEVATION = math.radians(60)
DEPTH = 0.30  # half depth (north-south) of the plinth and abacus
TOP = 2.81  # height of the abacus top, chosen so the column fills the canvas


def material(name, color, transmission, roughness, rim_strength=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (*color, 1)
    bsdf.inputs['Transmission Weight'].default_value = transmission
    bsdf.inputs['Roughness'].default_value = roughness
    if rim_strength:
        weight = nodes.new('ShaderNodeLayerWeight')
        weight.inputs['Blend'].default_value = 0.3
        power = nodes.new('ShaderNodeMath')
        power.operation = 'POWER'
        power.inputs[1].default_value = 3.5
        glow = nodes.new('ShaderNodeEmission')
        glow.inputs['Color'].default_value = (1, 1, 1, 1)
        glow.inputs['Strength'].default_value = rim_strength
        add = nodes.new('ShaderNodeAddShader')
        mix = nodes.new('ShaderNodeMixShader')
        links.new(weight.outputs['Facing'], power.inputs[0])
        links.new(power.outputs[0], mix.inputs['Fac'])
        links.new(bsdf.outputs[0], add.inputs[0])
        links.new(glow.outputs[0], add.inputs[1])
        links.new(bsdf.outputs[0], mix.inputs[1])
        links.new(add.outputs[0], mix.inputs[2])
        links.new(mix.outputs[0], nodes['Material Output'].inputs['Surface'])
    return mat


def box(name, center, size, mat, bevel=0.015):
    bpy.ops.mesh.primitive_cube_add(size=1, location=center)
    obj = bpy.context.object
    obj.name = name
    obj.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    mod = obj.modifiers.new('Soft edges', 'BEVEL')
    mod.width = bevel
    mod.segments = 2
    return obj


def cylinder(name, z0, z1, r0, r1, mat, vertices=48):
    bpy.ops.mesh.primitive_cone_add(vertices=vertices, radius1=r0, radius2=r1,
                                    depth=z1 - z0, location=(0, 0, (z0 + z1) / 2))
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    for face in obj.data.polygons:
        face.use_smooth = len(face.vertices) == 4
    return obj


def fluted_shaft(mat, z0, z1, r0, r1, flutes=12):
    """Shaft with shallow flutes; entasis via the two radii."""
    shaft = cylinder('Column shaft', z0, z1, r0, r1, mat, vertices=flutes * 4)
    mesh = shaft.data
    for v in mesh.vertices:
        a = math.atan2(v.co.y, v.co.x)
        dent = 1 - 0.06 * max(0.0, math.cos(a * flutes)) ** 2
        v.co.x *= dent
        v.co.y *= dent
    return shaft


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

marble = material('Marble', (0.92, 0.91, 0.88), 0.0, 0.65, rim_strength=0.25)
parts = {'column': [], 'link-west': [], 'link-east': []}
# Column: square plinth, torus base, fluted shaft, flared echinus, abacus.
parts['column'] += [
    # A short, thick shaft between a tall plinth and a heavy abacus; their
    # front faces read as bands, while their top faces stay shallow.
    box('Plinth', (0, 0, 0.15), (0.86, 2 * DEPTH, 0.30), marble),
    cylinder('Base torus', 0.30, 0.40, 0.37, 0.35, marble),
    fluted_shaft(marble, 0.40, TOP - 0.68, 0.33, 0.31),
    cylinder('Echinus', TOP - 0.68, TOP - 0.52, 0.32, 0.40, marble),
    box('Abacus', (0, 0, TOP - 0.26), (0.90, 2 * DEPTH, 0.52), marble),
]
# Links: half an architrave on top and half a stylobate step at the bottom.
for name, side in (('link-west', -1), ('link-east', 1)):
    parts[name] += [
        box('Architrave', (side * 0.25, 0, TOP - 0.25), (0.5, 1.8 * DEPTH, 0.46), marble, 0.005),
        box('Stylobate', (side * 0.25, 0, 0.13), (0.5, 2 * DEPTH, 0.26), marble, 0.005),
    ]

# Softer than the character lights so the near-white marble keeps its face
# shading (top, front, shaft) after the GUI tints it.
for pos, power, size, color in [((-4, -6, 8), 380, 5, (1.0, 0.93, 0.85)),
                                 ((6, -3, 4), 120, 6, (0.6, 0.75, 1.0)),
                                 ((-6, 6, 4), 300, 3, (0.55, 0.8, 1.0)),
                                 ((6, 6, 4), 300, 3, (1.0, 0.7, 0.9))]:
    bpy.ops.object.light_add(type='AREA', location=pos)
    light = bpy.context.object
    light.data.energy, light.data.size, light.data.color = power, size, color
    light.rotation_euler = (Vector((0, 0, 0)) - light.location).to_track_quat('-Z', 'Y').to_euler()

# Frame the canvas: from the plinth's near bottom edge to the abacus's far top
# edge, measured on the image plane (up = z cos(60) + y sin(60)).
up = lambda y, z: z * math.cos(ELEVATION) + y * math.sin(ELEVATION)
bottom, top = up(-DEPTH, 0), up(DEPTH, TOP)
height = top - bottom
centre = Vector((0, 0, (top + bottom) / 2 / math.cos(ELEVATION)))
view = Vector((0, math.cos(ELEVATION), -math.sin(ELEVATION)))
bpy.ops.object.camera_add(location=centre - view * 20)
camera = bpy.context.object
camera.rotation_euler = view.to_track_quat('-Z', 'Y').to_euler()
camera.data.type = 'ORTHO'
camera.data.ortho_scale = height  # the canvas is taller than wide
scene.camera = camera
print('canvas width in world units', height * WIDTH / HEIGHT)

scene.render.use_freestyle = True
settings = scene.view_layers[0].freestyle_settings
lines = settings.linesets[0] if settings.linesets else settings.linesets.new('Outline')
lines.select_silhouette = lines.select_border = False
lines.select_external_contour = True
lines.select_crease = False
lines.linestyle = bpy.data.linestyles.new('Ink outline')
lines.linestyle.color = (0.04, 0.05, 0.07)
lines.linestyle.thickness = 5.0
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'
for name, objects in parts.items():
    for obj in scene.objects:
        obj.hide_render = obj.type == 'MESH' and obj not in objects
    # Links meet their neighbours at the canvas edge; an outline there would
    # show as a seam, so only the column is outlined.
    scene.render.use_freestyle = name == 'column'
    scene.render.filepath = str(OUT / ('wall-' + name + '.png'))
    bpy.ops.render.render(write_still=True)
if '--save' in sys.argv:
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / 'heroic' / 'walls.blend'))
