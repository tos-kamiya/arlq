"""The Stage 6 bridgehead for the sprite GUI: a small fortified outpost.

Run with: blender --background --threads 4 --python dev-samples/3d-stage1/build-bridgehead.py

It takes two cells side by side on the floor and is drawn with the stairs'
60-degree orthographic camera, turned toward screen right (YAW) and fitted
to the cells' width. The outpost is a low curtain of grey stone blocks
with battlements around a packed-earth yard,
a gatehouse in the front wall with a barred plank gate, a round watchtower
at the back west corner flying a plain blue banner, and only a campfire
in the yard; the whole raised on a low earth mound. Like the characters, it is drawn
simplified and exaggerated: big stones, merlons, gate and banner.

Writes to OUT (BRIDGEHEAD_OUT in the environment, else
src/arlq/assets/bridgehead):
  bridgehead.png
  bridgehead.json  {"cells": 2, "under": UNDER, "overhang": OVERHANG}
"""
from pathlib import Path
import json
import math
import os

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parent
OUT = Path(os.environ.get('BRIDGEHEAD_OUT',
                          ROOT.parents[1] / 'src' / 'arlq' / 'assets' / 'bridgehead'))
OUT.mkdir(parents=True, exist_ok=True)
CELL_PIXELS = (300, 400)
UNIT_PIXELS = 300
CELL_W = CELL_PIXELS[0] / UNIT_PIXELS
CELLS = 2
WIDTH = CELL_PIXELS[0] * CELLS
ELEVATION = math.radians(60)
CELL_UP = CELL_PIXELS[1] / UNIT_PIXELS
YAW = math.radians(35)

# The outpost before it is fitted to the cells: its walls' half width, south
# and north faces, height and thickness, and the merlons along their tops.
HALF_W, SOUTH, NORTH = 0.52, 0.0, 0.90
MID = (SOUTH + NORTH) / 2
WALL_H, T = 0.42, 0.11
MERLON_W, MERLON_H, MERLON_STEP = 0.13, 0.11, 0.24
# The gatehouse: the gate's half width and height, and the gatehouse's.
GATE_HALF, GATE_H, GATEHOUSE_H, PIER = 0.20, 0.48, 0.68, 0.14
# The watchtower at the back west corner.
TOWER_X, TOWER_Y, TOWER_R, TOWER_H = -HALF_W + 0.06, NORTH - 0.06, 0.30, 1.15
MOUND = 0.08


def material(name, color, roughness=0.65, metallic=0.0, rim_strength=0.0,
             emission=None, strength=0.0):
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


def stone(name, across, around=None):
    """Grey stone blocks in running bond with dark mortar, laid on the wall
    plane spanned by the part's own `across` axis ('X' or 'Y') and its
    vertical; or, with `around` (circumference, height), wrapped round a
    cylinder by its UV map."""
    mat = material(name, (0.40, 0.40, 0.42), roughness=0.9, rim_strength=0.15)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    coords = nodes.new('ShaderNodeTexCoord')
    split = nodes.new('ShaderNodeSeparateXYZ')
    plane = nodes.new('ShaderNodeCombineXYZ')
    texture = nodes.new('ShaderNodeTexBrick')
    texture.offset = 0.5
    texture.inputs['Color1'].default_value = (0.42, 0.42, 0.44, 1)
    texture.inputs['Color2'].default_value = (0.30, 0.30, 0.33, 1)
    texture.inputs['Mortar'].default_value = (0.12, 0.12, 0.14, 1)
    texture.inputs['Scale'].default_value = 1.0
    texture.inputs['Mortar Size'].default_value = 0.012
    texture.inputs['Brick Width'].default_value = 0.30
    texture.inputs['Row Height'].default_value = 0.14
    texture.inputs['Bias'].default_value = 0.0
    if around:
        links.new(coords.outputs['UV'], split.inputs[0])
        sx, sz = nodes.new('ShaderNodeMath'), nodes.new('ShaderNodeMath')
        sx.operation = sz.operation = 'MULTIPLY'
        sx.inputs[1].default_value = around[0]
        sz.inputs[1].default_value = around[1] * 2  # the sides take half the UV map
        links.new(split.outputs['X'], sx.inputs[0])
        links.new(split.outputs['Y'], sz.inputs[0])
        links.new(sx.outputs[0], plane.inputs['X'])
        links.new(sz.outputs[0], plane.inputs['Y'])
    else:
        links.new(coords.outputs['Object'], split.inputs[0])
        links.new(split.outputs[across], plane.inputs['X'])
        links.new(split.outputs['Z'], plane.inputs['Y'])
    links.new(plane.outputs[0], texture.inputs['Vector'])
    links.new(texture.outputs['Color'], nodes['Principled BSDF'].inputs['Base Color'])
    return mat


def finish(obj, name, mat, bevel=0.0):
    obj.name = name
    obj.data.materials.append(mat)
    if bevel:
        mod = obj.modifiers.new('Soft edges', 'BEVEL')
        mod.width = bevel
        mod.segments = 2
    return obj


def box(name, x0, x1, y0, y1, z0, z1, mat, bevel=0.008, rotation=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=((x0 + x1) / 2, (y0 + y1) / 2,
                                                      (z0 + z1) / 2), rotation=rotation)
    obj = bpy.context.object
    obj.scale = (x1 - x0, y1 - y0, z1 - z0)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return finish(obj, name, mat, bevel)


def mesh(name, vertices, faces, mat):
    data = bpy.data.meshes.new(name)
    data.from_pydata(vertices, [], faces)
    data.update()
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    return finish(obj, name, mat)


def cylinder(name, x, y, z0, z1, radius, mat, vertices=24, bevel=0.0):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=z1 - z0,
                                        location=(x, y, (z0 + z1) / 2))
    return finish(bpy.context.object, name, mat, bevel)


def merlons(name, a0, a1, at, z, mat):
    """Merlons along a wall top from `a0` to `a1`, one at each end; `at(a0,
    a1)` gives the box's x0, x1, y0, y1 for a merlon spanning a0 to a1."""
    count = max(1, round((a1 - a0 - MERLON_W) / MERLON_STEP))
    step = (a1 - a0 - MERLON_W) / count
    for k in range(count + 1):
        b0 = a0 + k * step
        box(name, *at(b0, b0 + MERLON_W), z, z + MERLON_H, mat, 0.01)


bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 128
scene.cycles.use_denoising = False
scene.cycles.sample_clamp_indirect = 2.0
scene.view_settings.view_transform = 'Standard'
scene.view_settings.look = 'Medium High Contrast'
scene.render.resolution_x = WIDTH
scene.render.film_transparent = True
world = bpy.data.worlds.new('Night studio')
world.use_nodes = True
world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.05, 0.06, 0.08, 1)
scene.world = world

stone_x = stone('Stone (front and back)', 'X')
stone_y = stone('Stone (sides)', 'Y')
stone_tower = stone('Stone (tower)', None, (2 * math.pi * TOWER_R, TOWER_H))
cap = material('Coping stone', (0.48, 0.47, 0.46), roughness=0.85, rim_strength=0.12)
earth = material('Packed earth', (0.20, 0.14, 0.09), roughness=0.95)
yard = material('Trodden yard', (0.26, 0.20, 0.14), roughness=0.95)
wood = material('Weathered oak', (0.22, 0.11, 0.05), roughness=0.75, rim_strength=0.1)
timber = material('Dark timber', (0.12, 0.06, 0.03), roughness=0.8, rim_strength=0.1)
dark_iron = material('Black iron fittings', (0.03, 0.03, 0.035), roughness=0.4, metallic=0.9)
banner_cloth = material('Banner cloth', (0.08, 0.22, 0.60), roughness=0.7, rim_strength=0.2)
gold = material('Brass finial', (0.80, 0.60, 0.18), roughness=0.4, metallic=0.6)
glow = material('Firelight', (0.9, 0.5, 0.15), emission=(1.0, 0.45, 0.10), strength=3.0)
slit_glow = material('Lamplit slit', (0.8, 0.45, 0.18), emission=(1.0, 0.50, 0.16),
                     strength=1.2)

# The yard inside the walls.
box('Yard', -HALF_W + T, HALF_W - T, SOUTH + T, NORTH - T, 0, 0.015, yard, 0)

# The curtain walls with coping and merlons; the front wall is split by the
# gatehouse.
wall_top = WALL_H
segments = [('Front wall', -HALF_W, -GATE_HALF - PIER, SOUTH, SOUTH + T, stone_x, 'X'),
            ('Front wall', GATE_HALF + PIER, HALF_W, SOUTH, SOUTH + T, stone_x, 'X'),
            ('Back wall', -HALF_W, HALF_W, NORTH - T, NORTH, stone_x, 'X'),
            ('West wall', -HALF_W, -HALF_W + T, SOUTH, NORTH, stone_y, 'Y'),
            ('East wall', HALF_W - T, HALF_W, SOUTH, NORTH, stone_y, 'Y')]
for name, x0, x1, y0, y1, mat, axis in segments:
    box(name, x0, x1, y0, y1, 0, wall_top, mat, 0.006)
    box(name + ' coping', x0 - 0.015, x1 + 0.015, y0 - 0.015, y1 + 0.015, wall_top,
        wall_top + 0.03, cap, 0.006)
    if axis == 'X':
        merlons(name + ' merlon', x0, x1, lambda a, b, y0=y0, y1=y1: (a, b, y0, y1),
                wall_top + 0.03, mat)
    else:
        merlons(name + ' merlon', y0 + T, y1 - T,
                lambda a, b, x0=x0, x1=x1: (x0, x1, a, b), wall_top + 0.03, mat)

# The gatehouse: two stout piers standing out from the wall and a lintel
# block over the gate, crenellated; a barred double gate of planks.
GY0, GY1 = SOUTH - 0.06, SOUTH + T + 0.06
for x0, x1 in ((-GATE_HALF - PIER, -GATE_HALF), (GATE_HALF, GATE_HALF + PIER)):
    box('Gate pier', x0, x1, GY0, GY1, 0, GATEHOUSE_H, stone_x, 0.008)
box('Gate lintel', -GATE_HALF, GATE_HALF, GY0, GY1, GATE_H, GATEHOUSE_H, stone_x, 0.008)
box('Gatehouse coping', -GATE_HALF - PIER - 0.02, GATE_HALF + PIER + 0.02, GY0 - 0.02,
    GY1 + 0.02, GATEHOUSE_H, GATEHOUSE_H + 0.035, cap, 0.006)
merlons('Gatehouse merlon', -GATE_HALF - PIER - 0.02, GATE_HALF + PIER + 0.02,
        lambda a, b: (a, b, GY0, GY0 + 0.10), GATEHOUSE_H + 0.035, stone_x)
front = SOUTH + 0.02
for x0, x1 in ((-GATE_HALF, -0.006), (0.006, GATE_HALF)):
    box('Gate leaf', x0, x1, front, front + 0.04, 0, GATE_H, wood, 0.005)
    for k in range(1, 3):
        px = x0 + k * (x1 - x0) / 3
        box('Gate plank gap', px - 0.004, px + 0.004, front - 0.004, front, 0.02,
            GATE_H - 0.02, dark_iron, 0)
for z in (0.10, GATE_H - 0.12):
    box('Gate band', -GATE_HALF + 0.01, GATE_HALF - 0.01, front - 0.014, front, z,
        z + 0.035, dark_iron, 0.004)
box('Gate bar', -GATE_HALF - 0.03, GATE_HALF + 0.03, front - 0.05, front - 0.014, 0.24,
    0.30, timber, 0.006)

# The watchtower: a round stone tower at the back west corner, its top
# corbelled out into a crenellated platform, with lamplit arrow slits.
cylinder('Watchtower', TOWER_X, TOWER_Y, 0, TOWER_H, TOWER_R, stone_tower, 32)
cylinder('Tower corbel', TOWER_X, TOWER_Y, TOWER_H - 0.10, TOWER_H, TOWER_R + 0.06, cap, 32,
         0.01)
cylinder('Tower floor', TOWER_X, TOWER_Y, TOWER_H, TOWER_H + 0.01, TOWER_R, timber, 32)
for k in range(8):
    a = 2 * math.pi * (k + 0.5) / 8
    r = TOWER_R + 0.01
    bpy.ops.mesh.primitive_cube_add(size=1, location=(TOWER_X + r * math.cos(a),
                                                      TOWER_Y + r * math.sin(a),
                                                      TOWER_H + MERLON_H * 0.7),
                                    rotation=(0, 0, a))
    obj = bpy.context.object
    obj.scale = (0.10, 0.14, MERLON_H * 1.4)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    finish(obj, 'Tower merlon', cap, 0.01)
for a, z in ((math.radians(-120), 0.55), (math.radians(-170), 0.75)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(TOWER_X + TOWER_R * math.cos(a),
                                                      TOWER_Y + TOWER_R * math.sin(a), z),
                                    rotation=(0, 0, a))
    obj = bpy.context.object
    obj.scale = (0.03, 0.05, 0.18)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    finish(obj, 'Arrow slit', slit_glow)

# A flagpole on the tower flying a plain blue banner, rippling; plain so it
# reads as no real country's flag.
POLE_TOP = TOWER_H + 0.62
cylinder('Flagpole', TOWER_X, TOWER_Y, TOWER_H, POLE_TOP, 0.018, timber, 12)
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.035, location=(TOWER_X, TOWER_Y, POLE_TOP))
finish(bpy.context.object, 'Pole finial', gold)
FLAG_L, FLAG_H, NU, NV = 0.42, 0.24, 12, 4


def flag_point(u, v):
    t = u / NU
    return (TOWER_X + 0.02 + t * FLAG_L,
            TOWER_Y + 0.05 * math.sin(t * math.pi * 1.6) * t,
            POLE_TOP - 0.05 - v / NV * FLAG_H - 0.04 * t * t)


vertices = [flag_point(u, v) for u in range(NU + 1) for v in range(NV + 1)]
faces = [(u * (NV + 1) + v, u * (NV + 1) + v + 1, (u + 1) * (NV + 1) + v + 1,
          (u + 1) * (NV + 1) + v) for u in range(NU) for v in range(NV)]
flag = mesh('Banner', vertices, faces, banner_cloth)
solid = flag.modifiers.new('Cloth thickness', 'SOLIDIFY')
solid.thickness = 0.012
# In the yard, alone: a campfire ringed with stones.
FX, FY = 0.04, 0.50
for k in range(7):
    a = 2 * math.pi * k / 7
    bpy.ops.mesh.primitive_uv_sphere_add(segments=8, ring_count=6, radius=0.045,
                                         location=(FX + 0.12 * math.cos(a),
                                                   FY + 0.12 * math.sin(a), 0.03))
    obj = bpy.context.object
    obj.scale = (1, 1, 0.7)
    finish(obj, 'Hearth stone', cap)
for a in (0.3, 1.9, 3.6):
    bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.018, depth=0.18,
                                        location=(FX, FY, 0.05),
                                        rotation=(math.radians(70), 0, a))
    finish(bpy.context.object, 'Firewood', timber)
bpy.ops.mesh.primitive_cone_add(vertices=10, radius1=0.07, depth=0.20,
                                location=(FX, FY, 0.12))
finish(bpy.context.object, 'Flame', glow)
bpy.ops.mesh.primitive_cone_add(vertices=8, radius1=0.04, depth=0.14,
                                location=(FX + 0.03, FY - 0.02, 0.17), rotation=(0, 0.25, 0))
finish(bpy.context.object, 'Flame', glow)
bpy.ops.object.light_add(type='POINT', location=(FX, FY, 0.25))
fire_light = bpy.context.object
fire_light.data.energy, fire_light.data.color = 1.2, (1.0, 0.55, 0.2)
fire_light.data.shadow_soft_size = 0.05

# Everything stands on a low earth mound, a little wider than the walls,
# reaching out in front just past the gatehouse.
lift = Matrix.Translation((0, 0, MOUND))
bpy.context.view_layer.update()
for obj in scene.objects:
    if obj.type == 'MESH':
        obj.matrix_world = lift @ obj.matrix_world
fire_light.location.z += MOUND
box('Earth mound', -HALF_W - 0.10, HALF_W + 0.10, SOUTH - 0.12, NORTH + 0.10, 0, MOUND,
    earth, 0.03)

# Turn the outpost toward screen right.
pivot = Vector((0, MID, 0))
turn = (Matrix.Translation(pivot) @ Matrix.Rotation(YAW, 4, 'Z')
        @ Matrix.Translation(-pivot))
bpy.context.view_layer.update()
for obj in scene.objects:
    obj.matrix_world = turn @ obj.matrix_world

# Fit to the cells' width and find the overhangs.
bpy.context.view_layer.update()
points = [obj.matrix_world @ v.co for obj in scene.objects if obj.type == 'MESH'
          for v in obj.data.vertices]
x_lo, x_hi = min(p.x for p in points), max(p.x for p in points)
fit = CELLS * CELL_W / (x_hi - x_lo)
shrink = (Matrix.Translation(pivot) @ Matrix.Scale(fit, 4)
          @ Matrix.Translation(-pivot - Vector(((x_lo + x_hi) / 2, 0, 0))))
for obj in scene.objects:
    obj.matrix_world = shrink @ obj.matrix_world
fire_light.data.energy *= fit * fit
ups = [(shrink @ p).y * math.sin(ELEVATION) + (shrink @ p).z * math.cos(ELEVATION)
       for p in points]
# A little room past the model for the ink outline and the banner's
# thickness, so neither is cut at the canvas edge.
MARGIN = 0.03
UNDER = math.ceil(max(0.0, -min(ups) / CELL_UP + MARGIN) * 20) / 20
OVERHANG = math.ceil(max(0.0, max(ups) / CELL_UP - 1 + MARGIN) * 20) / 20
print(f'bridgehead: scale {fit:.3f}, UNDER {UNDER}, OVERHANG {OVERHANG}')
(OUT / 'bridgehead.json').write_text(json.dumps({'cells': CELLS, 'under': UNDER,
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
view = Vector((0, math.cos(ELEVATION), -math.sin(ELEVATION)))
image_up = Vector((0, math.sin(ELEVATION), math.cos(ELEVATION)))
centre = image_up * (height / 2 - UNDER * CELL_UP)
bpy.ops.object.camera_add(location=centre - view * 20)
camera = bpy.context.object
camera.rotation_euler = view.to_track_quat('-Z', 'Y').to_euler()
camera.data.type = 'ORTHO'
camera.data.ortho_scale = max(height, CELL_W * CELLS)
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
scene.render.filepath = str(OUT / 'bridgehead.png')
bpy.ops.render.render(write_still=True)
