"""Mint concrete floor tiles for the Stage 5 training room.

Run with: blender --background --threads 4 --python dev-samples/3d-stage1/build-floor-training.py

Two muted mint concrete slabs with different surface patterns, each filling
one sprite-mode cell (15 x 20 px at scale 1), laid like the flagstones as a
checkerboard. Unlike the flagstones the colors are baked in; the GUI only
darkens them for explored cells outside the current view.
"""
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parents[1] / 'src' / 'arlq' / 'assets' / 'floor'
OUT.mkdir(parents=True, exist_ok=True)
WIDTH, HEIGHT = 150, 200
SLAB_X, SLAB_Y = 1.0, HEIGHT / WIDTH  # the canvas in world units
# sRGB colors of the two slabs; parity 1 ('b') is slightly darker.
MINT = {'a': (100, 126, 116), 'b': (90, 114, 105)}
JOINT = (40, 48, 45)


def linear(srgb):
    def channel(c):
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return tuple(channel(c) for c in srgb)


def concrete(name, srgb, seed):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = nodes['Principled BSDF']
    bsdf.inputs['Roughness'].default_value = 0.9
    bsdf.inputs['Specular IOR Level'].default_value = 0.3
    coords = nodes.new('ShaderNodeTexCoord')
    shift = nodes.new('ShaderNodeVectorMath')
    shift.operation = 'ADD'
    shift.inputs[1].default_value = (seed * 7.3, seed * 3.1, seed * 5.7)
    # Broad, soft mottling of the cast surface.
    mottle = nodes.new('ShaderNodeTexNoise')
    mottle.inputs['Scale'].default_value = 3.0
    mottle.inputs['Detail'].default_value = 8.0
    ramp = nodes.new('ShaderNodeValToRGB')
    base = linear(srgb)
    ramp.color_ramp.elements[0].color = (*(c * 0.88 for c in base), 1)
    ramp.color_ramp.elements[1].color = (*(c * 1.08 for c in base), 1)
    # Small dark pores (air holes) scattered over it.
    pores = nodes.new('ShaderNodeTexVoronoi')
    pores.inputs['Scale'].default_value = 40.0
    pore_mask = nodes.new('ShaderNodeMapRange')
    pore_mask.inputs['From Min'].default_value = 0.04
    pore_mask.inputs['From Max'].default_value = 0.09
    darken = nodes.new('ShaderNodeMix')
    darken.data_type = 'RGBA'
    darken.blend_type = 'MULTIPLY'
    darken.inputs['B'].default_value = (0.55, 0.55, 0.55, 1)
    invert = nodes.new('ShaderNodeMath')
    invert.operation = 'SUBTRACT'
    invert.inputs[0].default_value = 1.0
    grain = nodes.new('ShaderNodeTexNoise')
    grain.inputs['Scale'].default_value = 60.0
    bump = nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.08
    links.new(coords.outputs['Object'], shift.inputs[0])
    links.new(shift.outputs[0], mottle.inputs['Vector'])
    links.new(shift.outputs[0], pores.inputs['Vector'])
    links.new(shift.outputs[0], grain.inputs['Vector'])
    links.new(mottle.outputs['Fac'], ramp.inputs['Fac'])
    links.new(pores.outputs['Distance'], pore_mask.inputs['Value'])
    links.new(pore_mask.outputs['Result'], invert.inputs[1])
    links.new(invert.outputs[0], darken.inputs['Factor'])
    links.new(ramp.outputs['Color'], darken.inputs['A'])
    links.new(darken.outputs['Result'], bsdf.inputs['Base Color'])
    links.new(grain.outputs['Fac'], bump.inputs['Height'])
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
world = bpy.data.worlds.new('Training room')
world.use_nodes = True
world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.5, 0.5, 0.5, 1)
scene.world = world

# A slab slightly smaller than the cell, with lightly rounded edges; the gap
# reads as the joint between neighbouring slabs.
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, -0.04))
slab = bpy.context.object
slab.scale = (SLAB_X * 0.96, SLAB_Y * 0.97, 0.08)
bpy.ops.object.transform_apply(scale=True)
bevel = slab.modifiers.new('Cast edges', 'BEVEL')
bevel.width = 0.02
bevel.segments = 2
bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, -0.07))
joint = bpy.context.object
joint.scale = (SLAB_X, SLAB_Y, 1)
joint_mat = bpy.data.materials.new('Joint')
joint_mat.use_nodes = True
joint_mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (
    *linear(JOINT), 1)
joint.data.materials.append(joint_mat)

# Key light from the front left, as for the characters and walls.
bpy.ops.object.light_add(type='SUN', location=(0, 0, 5))
sun = bpy.context.object
sun.data.energy = 2.0
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
    slab.data.materials.append(concrete('Concrete ' + name, MINT[name], seed))
    scene.render.filepath = str(OUT / ('training-' + name + '.png'))
    bpy.ops.render.render(write_still=True)
