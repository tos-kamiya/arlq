"""Marble stair cells for the sprite GUI.

Run with: blender --background --threads 4 --python dev-samples/3d-stage1/build-stairs.py

Each stair is rendered with the walls' 60-degree orthographic camera on the
walls' canvas (one cell plus the 0.25-cell band north of it), so the GUI
places it exactly like a wall part:
  stairs-up.png    a short flight of steps rising toward the north
  stairs-down.png  steps descending southward into a dark opening
The stone is near-white; the GUI tints it gold, darker outside the view.
"""
from pathlib import Path
import math
import sys

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parents[1] / 'src' / 'arlq' / 'assets' / 'stairs'
OUT.mkdir(parents=True, exist_ok=True)
WIDTH, HEIGHT = 260, 500
ELEVATION = math.radians(60)
OVERHANG = 0.25
# One cell is 1 unit wide; its north-south depth on the ground follows from
# the canvas shape and the view angle. The cell spans y = 0 (south) to DEPTH.
CELL_UP = (HEIGHT / WIDTH) / (1 + OVERHANG)  # cell height on the image plane
DEPTH = CELL_UP / math.sin(ELEVATION)
STEPS = 4
KERB_COLOR = (0.12, 0.13, 0.24)


def material(name, color, roughness=0.65, rim_strength=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (*color, 1)
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


def holdout(name):
    """Invisible ground that still hides what lies below the floor."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.remove(nodes['Principled BSDF'])
    shader = nodes.new('ShaderNodeHoldout')
    mat.node_tree.links.new(shader.outputs[0], nodes['Material Output'].inputs['Surface'])
    return mat


def box(name, x0, x1, y0, y1, z0, z1, mat, bevel=0.012):
    bpy.ops.mesh.primitive_cube_add(size=1, location=((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))
    obj = bpy.context.object
    obj.name = name
    obj.scale = (x1 - x0, y1 - y0, z1 - z0)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    if bevel:
        mod = obj.modifiers.new('Soft edges', 'BEVEL')
        mod.width = bevel
        mod.segments = 2
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

marble = material('Marble', (0.92, 0.91, 0.88), rim_strength=0.25)
shadowed = material('Shadowed marble', (0.30, 0.30, 0.30), roughness=0.9)
void = material('Void', (0.0, 0.0, 0.0), roughness=1.0)
ground = holdout('Ground')
parts = {'up': [], 'down': []}

# Up: solid steps between two low side walls, the lowest step near the cell's
# south edge and the top landing at its north edge.
half, y0, y1, rise = 0.32, 0.16, DEPTH - 0.16, 0.22
run = (y1 - y0) / STEPS
for i in range(STEPS):
    parts['up'].append(box('Step %d' % i, -half, half, y0 + i * run, y1,
                           0, (i + 1) * rise, marble))
for side in (-1, 1):
    for i in range(STEPS):
        parts['up'].append(box('Side wall %d' % i, side * half, side * (half + 0.08),
                               y0 + i * run, y0 + (i + 1) * run,
                               0, (i + 1) * rise + 0.08, marble))

# Down: a low kerb around an opening; inside, steps descend southward, toward
# the camera, so their risers show as dark bands like the up flight's. An
# invisible holdout ground hides the pit walls from outside. The kerb is a
# cool grey that the GUI's gold tint turns close to the floor's warm grey.
hx, py0, py1, kerb, sink = 0.36, 0.22, DEPTH - 0.12, 0.08, 0.16
kerb_stone = material('Kerb stone', KERB_COLOR, roughness=0.8)
for name, bx0, bx1, by0, by1 in (('Kerb south', -hx - kerb, hx + kerb, py0 - kerb, py0),
                                 ('Kerb north', -hx - kerb, hx + kerb, py1, py1 + kerb),
                                 ('Kerb west', -hx - kerb, -hx, py0, py1),
                                 ('Kerb east', hx, hx + kerb, py0, py1)):
    parts['down'].append(box(name, bx0, bx1, by0, by1, 0, 0.07, kerb_stone))
for name, bx0, bx1, by0, by1 in (('Ground south', -2, 2, -2, py0 - kerb),
                                 ('Ground north', -2, 2, py1 + kerb, 4),
                                 ('Ground west', -2, -hx - kerb, -2, 4),
                                 ('Ground east', hx + kerb, 2, -2, 4)):
    parts['down'].append(box(name, bx0, bx1, by0, by1, -0.02, 0, ground, bevel=0))
run = (py1 - py0) / (STEPS + 1)
for i in range(STEPS):
    # The top step is at the north kerb; deeper treads fade into the dark.
    shade = 0.92 * 0.72 ** i
    mat = material('Step %d marble' % i, (shade, shade * 0.99, shade * 0.96), roughness=0.8)
    parts['down'].append(box('Step %d' % i, -hx, hx, py1 - (i + 1) * run, py1 - i * run,
                             -2.5, -(i + 1) * sink, mat))
parts['down'].append(box('Pit', -hx, hx, py0, py1 - STEPS * run, -2.5, -(STEPS + 1) * sink,
                         void, bevel=0))
parts['down'].append(box('Pit back', -hx, hx, py1 - 0.02, py1, -2.5, 0, shadowed, bevel=0))
for side in (-1, 1):
    parts['down'].append(box('Pit wall', side * hx, side * (hx + 0.05), py0, py1, -2.5, 0,
                             shadowed, bevel=0))

# The key light is above and slightly behind the cell, unlike the walls', so
# the treads are bright and the risers facing the camera read darker.
for pos, power, size, color in [((-3, 3, 9), 420, 5, (1.0, 0.93, 0.85)),
                                 ((6, -3, 4), 120, 6, (0.6, 0.75, 1.0)),
                                 ((-6, 6, 4), 300, 3, (0.55, 0.8, 1.0)),
                                 ((6, 6, 4), 300, 3, (1.0, 0.7, 0.9))]:
    bpy.ops.object.light_add(type='AREA', location=pos)
    light = bpy.context.object
    light.data.energy, light.data.size, light.data.color = power, size, color
    light.rotation_euler = (Vector((0, 0, 0)) - light.location).to_track_quat('-Z', 'Y').to_euler()

# Frame the canvas from the cell's south edge on the ground (image-plane
# up = 0) to OVERHANG cells above its north edge.
height = CELL_UP * (1 + OVERHANG)
view = Vector((0, math.cos(ELEVATION), -math.sin(ELEVATION)))
image_up = Vector((0, math.sin(ELEVATION), math.cos(ELEVATION)))
centre = image_up * (height / 2)
bpy.ops.object.camera_add(location=centre - view * 20)
camera = bpy.context.object
camera.rotation_euler = view.to_track_quat('-Z', 'Y').to_euler()
camera.data.type = 'ORTHO'
camera.data.ortho_scale = height  # the canvas is taller than wide
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
for name, objects in parts.items():
    for obj in scene.objects:
        obj.hide_render = obj.type == 'MESH' and obj not in objects
    scene.render.filepath = str(OUT / ('stairs-' + name + '.png'))
    bpy.ops.render.render(write_still=True)
if '--save' in sys.argv:
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / 'heroic' / 'stairs.blend'))
