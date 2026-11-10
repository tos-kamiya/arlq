"""The Stage 6 Dungeon Core for the sprite GUI: an eye in a crystal among
four pillars.

Run with: blender --background --threads 4 --python dev-samples/3d-stage1/build-dungeon-core.py

A trial for the core shown as `[*]` on three cells side by side. A large
clear violet octahedron floats in the middle with an eye hanging inside it,
looking at the camera: an almond-shaped lens with a glowing magenta iris and
a black slit pupil in a pale violet-grey white. Four unnatural pillars stand
round it in a cross, the whole cross turned 30 degrees clockwise seen from
above (YAW) so it does not face straight ahead: square in plan,
polished violet-black, flat-topped, with glowing violet grooves down each
face and glowing bands near the top and foot. The crystal gives off a dark
glow: spikes of smoky light, black at heart and violet at their edges,
fading toward their tips, radiating from it in every direction. There is no
base. It uses the bridgehead's 60-degree orthographic camera and ink
outline, and is fitted so the pillars span FRAME_CELLS cells,
centred on a canvas CELLS wide that leaves room for the rays.

Writes to OUT (DUNGEON_CORE_OUT in the environment, else
src/arlq/assets/dungeon-core):
  dungeon-core.png
  dungeon-core.json  {"cells": 3, "under": UNDER, "overhang": OVERHANG}
"""
from pathlib import Path
import json
import math
import os
import random

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parent
OUT = Path(os.environ.get('DUNGEON_CORE_OUT',
                          ROOT.parents[1] / 'src' / 'arlq' / 'assets' / 'dungeon-core'))
OUT.mkdir(parents=True, exist_ok=True)
CELL_PIXELS = (320, 400)
UNIT_PIXELS = 300
CELL_W = CELL_PIXELS[0] / UNIT_PIXELS
CELLS = 3
FRAME_CELLS = 1.7
WIDTH = CELL_PIXELS[0] * CELLS
ELEVATION = math.radians(60)
CELL_UP = CELL_PIXELS[1] / UNIT_PIXELS

# The model before it is fitted to the cells.
PILLAR_D, PILLAR_HALF, PILLAR_H = 0.95, 0.17, 2.6
YAW = math.radians(-30)
CRYSTAL_R, CRYSTAL_H, CRYSTAL_Z = 0.62, 0.95, 1.45
EYE_W, EYE_TALL, EYE_DEPTH = 0.34, 0.58, 0.40
RAYS, RAY_MIN, RAY_MAX = 22, 0.75, 1.30
rng = random.Random(6)

VIEW = Vector((0, math.cos(ELEVATION), -math.sin(ELEVATION)))
IMAGE_UP = Vector((0, math.sin(ELEVATION), math.cos(ELEVATION)))
TOWARD_CAMERA = -VIEW


def material(name, color, roughness=0.65, metallic=0.0, rim_strength=0.0,
             rim_color=(1, 1, 1), emission=None, strength=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (*color, 1)
    bsdf.inputs['Roughness'].default_value = roughness
    bsdf.inputs['Metallic'].default_value = metallic
    if emission:
        bsdf.inputs['Emission Color'].default_value = (*emission, 1)
        bsdf.inputs['Emission Strength'].default_value = strength
    if rim_strength:
        weight = nodes.new('ShaderNodeLayerWeight')
        weight.inputs['Blend'].default_value = 0.3
        power = nodes.new('ShaderNodeMath')
        power.operation = 'POWER'
        power.inputs[1].default_value = 3.5
        glow = nodes.new('ShaderNodeEmission')
        glow.inputs['Color'].default_value = (*rim_color, 1)
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


def math_node(nodes, links, operation, a, b=None):
    node = nodes.new('ShaderNodeMath')
    node.operation = operation
    for index, value in enumerate((a, b)):
        if value is None:
            continue
        if isinstance(value, (int, float)):
            node.inputs[index].default_value = value
        else:
            links.new(value, node.inputs[index])
    return node.outputs[0]


def crystal_material():
    """Clear violet crystal: mostly see-through with a violet tint, glossier
    and glowing violet toward its silhouette."""
    mat = bpy.data.materials.new('Core crystal')
    mat.use_nodes = True
    mat.blend_method = 'BLEND'
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    out = nodes['Material Output']
    nodes.remove(nodes['Principled BSDF'])
    weight = nodes.new('ShaderNodeLayerWeight')
    weight.inputs['Blend'].default_value = 0.45
    clear = nodes.new('ShaderNodeBsdfTransparent')
    clear.inputs['Color'].default_value = (0.82, 0.62, 1.0, 1)
    gloss = nodes.new('ShaderNodeBsdfGlossy')
    gloss.inputs['Color'].default_value = (0.85, 0.75, 1.0, 1)
    gloss.inputs['Roughness'].default_value = 0.05
    surface = nodes.new('ShaderNodeMixShader')
    fac = math_node(nodes, links, 'ADD', math_node(nodes, links, 'MULTIPLY',
                                                   weight.outputs['Fresnel'], 0.6), 0.12)
    links.new(fac, surface.inputs['Fac'])
    links.new(clear.outputs[0], surface.inputs[1])
    links.new(gloss.outputs[0], surface.inputs[2])
    rim = nodes.new('ShaderNodeEmission')
    rim.inputs['Color'].default_value = (0.55, 0.18, 1.0, 1)
    links.new(math_node(nodes, links, 'MULTIPLY',
                        math_node(nodes, links, 'POWER', weight.outputs['Facing'], 2.5), 2.5),
              rim.inputs['Strength'])
    add = nodes.new('ShaderNodeAddShader')
    links.new(surface.outputs[0], add.inputs[0])
    links.new(rim.outputs[0], add.inputs[1])
    links.new(add.outputs[0], out.inputs['Surface'])
    return mat


def eye_material():
    """In the eye's own coordinates (width along X, height along Z, at unit
    half width): a pale violet-grey sclera, a glowing magenta iris and a black vertical
    slit pupil, with a wet gloss."""
    mat = bpy.data.materials.new('Core eye')
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (0.0, 0.0, 0.0, 1)
    bsdf.inputs['Roughness'].default_value = 0.12
    bsdf.inputs['Specular IOR Level'].default_value = 0.9
    bsdf.inputs['Emission Strength'].default_value = 2.4
    coords = nodes.new('ShaderNodeTexCoord')
    split = nodes.new('ShaderNodeSeparateXYZ')
    links.new(coords.outputs['Object'], split.inputs[0])
    x2 = math_node(nodes, links, 'MULTIPLY', split.outputs['X'], split.outputs['X'])
    z2 = math_node(nodes, links, 'MULTIPLY', split.outputs['Z'], split.outputs['Z'])
    radius = math_node(nodes, links, 'SQRT', math_node(nodes, links, 'ADD', x2, z2))
    pupil = math_node(nodes, links, 'LESS_THAN', math_node(
        nodes, links, 'ADD', math_node(nodes, links, 'DIVIDE', x2, 0.10 ** 2),
        math_node(nodes, links, 'DIVIDE', z2, 0.38 ** 2)), 1.0)
    ramp = nodes.new('ShaderNodeValToRGB')
    elements = ramp.color_ramp.elements
    elements[0].position, elements[0].color = 0.0, (1.0, 0.62, 0.85, 1)
    elements[1].position, elements[1].color = 0.30, (0.85, 0.08, 0.50, 1)
    for position, color in ((0.35, (0.15, 0.0, 0.10, 1)), (0.39, (0.30, 0.22, 0.40, 1)),
                            (1.0, (0.18, 0.12, 0.26, 1))):
        element = elements.new(position)
        element.color = color
    links.new(radius, ramp.inputs['Fac'])
    black = nodes.new('ShaderNodeMix')
    black.data_type = 'RGBA'
    links.new(pupil, black.inputs['Factor'])
    links.new(ramp.outputs['Color'], black.inputs['A'])
    black.inputs['B'].default_value = (0, 0, 0, 1)
    links.new(black.outputs['Result'], bsdf.inputs['Emission Color'])
    return mat


def dark_light_material():
    """Smoky dark light: black where it faces the camera, violet toward its
    edges, fading out toward the tip (UV Y runs from 0 at the base to 1)."""
    mat = bpy.data.materials.new('Dark light')
    mat.use_nodes = True
    mat.blend_method = 'BLEND'
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    out = nodes['Material Output']
    nodes.remove(nodes['Principled BSDF'])
    coords = nodes.new('ShaderNodeTexCoord')
    split = nodes.new('ShaderNodeSeparateXYZ')
    links.new(coords.outputs['UV'], split.inputs[0])
    opacity = math_node(nodes, links, 'MULTIPLY', math_node(
        nodes, links, 'POWER', math_node(nodes, links, 'SUBTRACT', 1.0, split.outputs['Y']),
        1.3), 0.92)
    weight = nodes.new('ShaderNodeLayerWeight')
    weight.inputs['Blend'].default_value = 0.5
    fringe = nodes.new('ShaderNodeValToRGB')
    fringe.color_ramp.elements[0].position = 0.45
    fringe.color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1)
    fringe.color_ramp.elements[1].position = 0.95
    fringe.color_ramp.elements[1].color = (0.45, 0.10, 0.85, 1)
    links.new(weight.outputs['Facing'], fringe.inputs['Fac'])
    body = nodes.new('ShaderNodeEmission')
    body.inputs['Strength'].default_value = 1.4
    links.new(fringe.outputs['Color'], body.inputs['Color'])
    clear = nodes.new('ShaderNodeBsdfTransparent')
    mix = nodes.new('ShaderNodeMixShader')
    links.new(opacity, mix.inputs['Fac'])
    links.new(clear.outputs[0], mix.inputs[1])
    links.new(body.outputs[0], mix.inputs[2])
    links.new(mix.outputs[0], out.inputs['Surface'])
    return mat


def finish(obj, name, mat, bevel=0.0):
    obj.name = name
    obj.data.materials.append(mat)
    if bevel:
        mod = obj.modifiers.new('Soft edges', 'BEVEL')
        mod.width = bevel
        mod.segments = 2
    return obj


def mesh(name, vertices, faces, mat, uvs=None):
    data = bpy.data.meshes.new(name)
    data.from_pydata(vertices, [], faces)
    if uvs:
        layer = data.uv_layers.new()
        for loop in data.loops:
            layer.data[loop.index].uv = uvs[loop.vertex_index]
    data.update()
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    return finish(obj, name, mat)


def box(name, x0, x1, y0, y1, z0, z1, mat, bevel=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=((x0 + x1) / 2, (y0 + y1) / 2,
                                                      (z0 + z1) / 2))
    obj = bpy.context.object
    obj.scale = (x1 - x0, y1 - y0, z1 - z0)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return finish(obj, name, mat, bevel)


def pillars(stone, glow):
    """Four square, flat-topped pillars in a cross round the crystal, with
    glowing grooves down each face and glowing bands near the top and foot."""
    h, groove, proud = PILLAR_HALF, 0.022, 0.006
    z0, z1 = 0.42, PILLAR_H - 0.42
    for x, y in ((0, -PILLAR_D), (PILLAR_D, 0), (0, PILLAR_D), (-PILLAR_D, 0)):
        box('Pillar', x - h, x + h, y - h, y + h, 0, PILLAR_H, stone, 0.012)
        for x0, x1, y0, y1 in ((-groove, groove, -h - proud, -h + 0.01),
                               (-groove, groove, h - 0.01, h + proud),
                               (-h - proud, -h + 0.01, -groove, groove),
                               (h - 0.01, h + proud, -groove, groove)):
            box('Pillar groove', x + x0, x + x1, y + y0, y + y1, z0, z1, glow)
        for z in (0.20, PILLAR_H - 0.24):
            box('Pillar band', x - h - proud, x + h + proud, y - h - proud,
                y + h + proud, z, z + 0.035, glow)


def eye():
    """An almond-shaped lens: a sphere flattened front to back and pinched
    to points at its corners, turned to look at the camera."""
    bpy.ops.mesh.primitive_uv_sphere_add(segments=40, ring_count=20, radius=1.0)
    obj = bpy.context.object
    for v in obj.data.vertices:
        x, y, z = v.co
        v.co = (x, y * EYE_DEPTH, z * EYE_TALL * math.sqrt(max(0.0, 1 - x * x)))
    bpy.ops.object.shade_smooth()
    obj.scale = (EYE_W,) * 3
    obj.location = (0, 0, CRYSTAL_Z)
    # Its front (-Y) turned toward the camera, its height (Z) up the image.
    obj.rotation_euler = (-ELEVATION, 0, 0)
    return finish(obj, 'Core eye', eye_material())


def ray(direction, length, width, mat):
    """A four-sided spike of dark light from inside the crystal outward."""
    direction = direction.normalized()
    side = direction.cross(Vector((0, 0, 1)))
    if side.length < 0.1:
        side = direction.cross(Vector((1, 0, 0)))
    side.normalize()
    other = direction.cross(side).normalized()
    centre = Vector((0, 0, CRYSTAL_Z))
    base = centre + direction * CRYSTAL_R * 0.45
    tip = centre + direction * length
    corners = [base + (side * sx + other * sy) * width
               for sx, sy in ((1, 0), (0, 1), (-1, 0), (0, -1))]
    obj = mesh('Dark ray', [*corners, tip], [(0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4)],
               mat, uvs=[(0, 0)] * 4 + [(0, 1)])
    obj.visible_shadow = False
    return obj


bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 128
scene.cycles.use_denoising = False
scene.cycles.sample_clamp_indirect = 2.0
scene.cycles.transparent_max_bounces = 32
scene.view_settings.view_transform = 'Standard'
scene.view_settings.look = 'Medium High Contrast'
scene.render.resolution_x = WIDTH
scene.render.film_transparent = True
world = bpy.data.worlds.new('Night studio')
world.use_nodes = True
world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.05, 0.06, 0.08, 1)
scene.world = world

stone = material('Polished black-violet stone', (0.035, 0.025, 0.05), roughness=0.28,
                 rim_strength=0.35, rim_color=(0.6, 0.45, 0.9))
groove = material('Violet glow', (0.4, 0.15, 0.7), emission=(0.60, 0.20, 1.0), strength=3.0)
dark_light = dark_light_material()

pillars(stone, groove)

# The octahedron, taller than wide, floating and turned a little.
top, bottom = CRYSTAL_Z + CRYSTAL_H, CRYSTAL_Z - CRYSTAL_H
ring = [(CRYSTAL_R * math.cos(a), CRYSTAL_R * math.sin(a), CRYSTAL_Z)
        for a in (math.radians(20 + 90 * k) for k in range(4))]
octa = mesh('Core crystal', ring + [(0, 0, top), (0, 0, bottom)],
            [(0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4),
             (1, 0, 5), (2, 1, 5), (3, 2, 5), (0, 3, 5)], crystal_material())
octa.visible_shadow = False
core_eye = eye()
core_eye.visible_shadow = False

# Turn the cross of pillars about the crystal.
bpy.context.view_layer.update()
pillar_parts = [obj for obj in scene.objects if obj.name.startswith('Pillar')]
turn = Matrix.Rotation(YAW, 4, 'Z')
for obj in pillar_parts:
    obj.matrix_world = turn @ obj.matrix_world

# Spikes of dark light in every direction, spread evenly over a sphere,
# leaving out those coming straight at the camera so the eye stays clear.
golden = math.pi * (3 - math.sqrt(5))
for k in range(RAYS):
    z = 1 - 2 * (k + 0.5) / RAYS
    r = math.sqrt(1 - z * z)
    a = golden * k + rng.uniform(-0.25, 0.25)
    direction = Vector((r * math.cos(a), r * math.sin(a), z))
    if direction.dot(TOWARD_CAMERA) > 0.7:
        continue
    ray(direction, rng.uniform(RAY_MIN, RAY_MAX), rng.uniform(0.07, 0.11), dark_light)

# A soft violet light inside so the pillars' inner faces catch the glow.
bpy.ops.object.light_add(type='POINT', location=(0, 0, CRYSTAL_Z))
core_light = bpy.context.object
core_light.data.energy, core_light.data.color = 8.0, (0.6, 0.25, 1.0)
core_light.data.shadow_soft_size = 0.2

# Fit so the pillars span FRAME_CELLS cells and find the overhangs.
bpy.context.view_layer.update()
pillar_points = [obj.matrix_world @ v.co for obj in pillar_parts for v in obj.data.vertices]
all_points = [obj.matrix_world @ v.co for obj in scene.objects if obj.type == 'MESH'
              for v in obj.data.vertices]
x_lo, x_hi = min(p.x for p in pillar_points), max(p.x for p in pillar_points)
fit = FRAME_CELLS * CELL_W / (x_hi - x_lo)
shrink = Matrix.Scale(fit, 4) @ Matrix.Translation(-Vector(((x_lo + x_hi) / 2, 0, 0)))
for obj in scene.objects:
    obj.matrix_world = shrink @ obj.matrix_world
core_light.data.energy *= fit * fit
ups = [(shrink @ p).y * math.sin(ELEVATION) + (shrink @ p).z * math.cos(ELEVATION)
       for p in all_points]
rights = [(shrink @ p).x for p in all_points]
MARGIN = 0.03
UNDER = math.ceil(max(0.0, -min(ups) / CELL_UP + MARGIN) * 20) / 20
OVERHANG = math.ceil(max(0.0, max(ups) / CELL_UP - 1 + MARGIN) * 20) / 20
SPILL = math.ceil(max(0.0, max(abs(x) for x in rights) / CELL_W - CELLS / 2 + MARGIN)
                  * 20) / 20
print(f'dungeon core: scale {fit:.3f}, UNDER {UNDER}, OVERHANG {OVERHANG}, '
      f'rays past the cells {SPILL}')
(OUT / 'dungeon-core.json').write_text(json.dumps({'cells': CELLS, 'under': UNDER,
                                                   'overhang': OVERHANG}) + '\n')
scene.render.resolution_y = round(CELL_PIXELS[1] * (UNDER + 1 + OVERHANG))

for pos, power, size, color in [((-3, 3, 9), 420, 1.5, (1.0, 0.93, 0.85)),
                                 ((6, -3, 4), 120, 6, (0.6, 0.75, 1.0)),
                                 ((-6, 6, 4), 300, 3, (0.55, 0.8, 1.0)),
                                 ((6, 6, 4), 300, 3, (1.0, 0.7, 0.9))]:
    bpy.ops.object.light_add(type='AREA', location=pos)
    light = bpy.context.object
    light.data.energy, light.data.size, light.data.color = power, size, color
    light.data.cycles.cast_shadow = pos == (-3, 3, 9)
    light.rotation_euler = (Vector((0, 0, 0)) - light.location).to_track_quat('-Z', 'Y').to_euler()

height = CELL_UP * (UNDER + 1 + OVERHANG)
frame_centre = IMAGE_UP * (height / 2 - UNDER * CELL_UP)
bpy.ops.object.camera_add(location=frame_centre - VIEW * 20)
camera = bpy.context.object
camera.rotation_euler = VIEW.to_track_quat('-Z', 'Y').to_euler()
camera.data.type = 'ORTHO'
camera.data.ortho_scale = max(height, CELL_W * CELLS)
scene.camera = camera

# Ink outline on the pillars and crystal only; the rays stay soft.
scene.render.use_freestyle = True
settings = scene.view_layers[0].freestyle_settings
lines = settings.linesets[0] if settings.linesets else settings.linesets.new('Outline')
lines.select_silhouette = lines.select_border = False
lines.select_external_contour = True
lines.select_crease = False
lines.select_by_collection = True
outlined = bpy.data.collections.new('Outlined')
scene.collection.children.link(outlined)
for obj in list(scene.objects):
    if obj.type == 'MESH' and obj.name.startswith(('Pillar', 'Core crystal')):
        for owner in obj.users_collection:
            owner.objects.unlink(obj)
        outlined.objects.link(obj)
lines.collection = outlined
lines.linestyle = bpy.data.linestyles.new('Ink outline')
lines.linestyle.color = (0.04, 0.05, 0.07)
lines.linestyle.thickness = 4.0
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'
scene.render.filepath = str(OUT / 'dungeon-core.png')
bpy.ops.render.render(write_still=True)
