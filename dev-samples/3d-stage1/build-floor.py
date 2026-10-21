"""Flagstone floor tiles for the sprite GUI.

Run with: blender --background --threads 4 --python dev-samples/3d-stage1/build-floor.py

Two near-white flagstones with different surface patterns, each filling one
sprite-mode cell (15 x 20 px at scale 1). The GUI lays them out as a checkerboard and
tints them per visible/explored floor, slightly darker on alternate cells.
"""
from pathlib import Path
import math

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parents[1] / 'src' / 'arlq' / 'assets' / 'floor'
OUT.mkdir(parents=True, exist_ok=True)
WIDTH, HEIGHT = 150, 200
SLAB_X, SLAB_Y = 1.0, HEIGHT / WIDTH  # the canvas in world units


def stone(name, seed):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = nodes['Principled BSDF']
    bsdf.inputs['Roughness'].default_value = 0.8
    coords = nodes.new('ShaderNodeTexCoord')
    shift = nodes.new('ShaderNodeVectorMath')
    shift.operation = 'ADD'
    shift.inputs[1].default_value = (seed * 7.3, seed * 3.1, seed * 5.7)
    noise = nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 4.0
    noise.inputs['Detail'].default_value = 6.0
    ramp = nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (0.80, 0.80, 0.80, 1)
    ramp.color_ramp.elements[1].color = (0.95, 0.95, 0.95, 1)
    bump = nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.1
    links.new(coords.outputs['Object'], shift.inputs[0])
    links.new(shift.outputs[0], noise.inputs['Vector'])
    links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
    links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
    links.new(noise.outputs['Fac'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    return mat


bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 64
scene.cycles.use_denoising = False
scene.view_settings.view_transform = 'Standard'
scene.render.resolution_x, scene.render.resolution_y = WIDTH, HEIGHT
scene.render.film_transparent = True
world = bpy.data.worlds.new('Night studio')
world.use_nodes = True
world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.25, 0.25, 0.25, 1)
scene.world = world

# A slab slightly smaller than the cell, with bevelled edges; the gap and the
# bevel read as the joint between neighbouring stones.
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, -0.04))
slab = bpy.context.object
slab.scale = (SLAB_X * 0.94, SLAB_Y * 0.95, 0.08)
bpy.ops.object.transform_apply(scale=True)
bevel = slab.modifiers.new('Worn edges', 'BEVEL')
bevel.width = 0.05
bevel.segments = 3
# Joint below the slab: a dark bed of mortar filling the whole cell.
bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, -0.07))
mortar = bpy.context.object
mortar.scale = (SLAB_X, SLAB_Y, 1)
mortar_mat = bpy.data.materials.new('Mortar')
mortar_mat.use_nodes = True
mortar_mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.45, 0.45, 0.45, 1)
mortar.data.materials.append(mortar_mat)

# Key light from the front left, as for the characters and walls.
bpy.ops.object.light_add(type='SUN', location=(0, 0, 5))
sun = bpy.context.object
sun.data.energy = 3.0
sun.rotation_euler = (Vector((0, 0, 0)) - Vector((-4, -6, 8))).to_track_quat('-Z', 'Y').to_euler()

bpy.ops.object.camera_add(location=(0, 0, 5))
camera = bpy.context.object
camera.data.type = 'ORTHO'
camera.data.ortho_scale = SLAB_Y  # the canvas is taller than wide
scene.camera = camera
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'
for name, seed in (('a', 1), ('b', 2)):
    slab.data.materials.clear()
    slab.data.materials.append(stone('Flagstone ' + name, seed))
    scene.render.filepath = str(OUT / ('floor-' + name + '.png'))
    bpy.ops.render.render(write_still=True)
