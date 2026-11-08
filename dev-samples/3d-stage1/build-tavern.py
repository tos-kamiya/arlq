"""The Stage 6 tavern for the sprite GUI: a small brick cottage.

Run with: blender --background --threads 4 --python dev-samples/3d-stage1/build-tavern.py

The tavern takes two cells side by side on the floor. This draws it as a
small, old-fashioned cottage seen with the walls' and stairs' 60-degree
orthographic camera: red-brown brick walls, a lopsided gable roof of dark
tiles in overlapping courses under half-round ridge tiles (its ridge
east-west, along the two cells; both slopes at the same pitch, the back one
running on down over the cottage stretched back under it to a low back
wall, like a catslide roof, so the gables read like the kana へ), a low brick chimney at the west gable, set back behind the
ridge, a plank door in a timber frame of posts and a beam standing out
from the wall, and
tall, unglazed windows with diagonal lattice bars, lit softly from inside;
no sign. Like the characters, it is drawn simplified and exaggerated:
a large door, windows and chimney for the cottage, big bricks and tiles, a
thick roof and ridge, and the chimney leaning a little. The finished cottage is then shrunk to
fit the two cells' width, whatever that makes its scale beside the
characters. The canvas is the two cells wide; it covers OVERHANG cells
north of them, where the roof and chimney rise, and UNDER cells south of
them, where the turned cottage's front corner and eaves reach, both found
from the shrunk model, printed and written beside the image:
  tavern.png
  tavern.json  {"cells": 2, "under": UNDER, "overhang": OVERHANG}
"""
from pathlib import Path
import json
import math

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parents[1] / 'src' / 'arlq' / 'assets' / 'tavern'
OUT.mkdir(parents=True, exist_ok=True)
# The same cell and scale as build-stairs.py: a 16 x 20 px cell at 20 px per
# screen pixel, one world unit being 15 screen px.
CELL_PIXELS = (320, 400)
UNIT_PIXELS = 300
CELL_W = CELL_PIXELS[0] / UNIT_PIXELS
CELLS = 2
WIDTH = CELL_PIXELS[0] * CELLS
ELEVATION = math.radians(60)
CELL_UP = CELL_PIXELS[1] / UNIT_PIXELS
DEPTH = CELL_UP / math.sin(ELEVATION)
# The cottage: its walls' half width and their south and north faces, the
# eaves' height, the ridge's height above the eaves, and how far the roof
# reaches past the walls at the eaves and at the gables.
# The cottage is SCALE times its first size, about the cells' middle.
SCALE = 2.0
MID = 0.775
HALF_W, SOUTH, RIDGE_Y = 0.50 * SCALE, MID - 0.325 * SCALE, MID
# Both roof slopes are pitched PITCH; the ridge rises that much over the
# front wall.
PITCH = math.radians(31)
EAVES = 0.60 * SCALE
RIDGE_RISE = (RIDGE_Y - SOUTH) * math.tan(PITCH)
EAVE_OUT, GABLE_OUT = 0.10 * SCALE, 0.06 * SCALE
# The cottage reaches this far back from the ridge, under the back slope,
# which comes down at the same pitch to the lower back wall.
BACK_DEPTH = 0.635 * SCALE
NORTH = RIDGE_Y + BACK_DEPTH
BACK_EAVES = EAVES + RIDGE_RISE - BACK_DEPTH * math.tan(PITCH)
# A thick roof, so its edges read as a chunky slab, like a toy's.
ROOF_THICK = 0.07
# Turned toward screen right, a little further than the monsters (MONSTER_YAW
# in build-heroic.py turns them 30 degrees the other way); 10 degrees less
# than at first, so the cottage is a little narrower on screen and is
# shrunk less to fit the cells.
YAW = math.radians(35)
# The roof tiles: width, the step between courses down the slope, each
# tile's length (so the courses overlap) and thickness; large and few, so
# they still read at sprite size.
TILE_W, TILE_STEP, TILE_LEN, TILE_THICK = 0.20, 0.13, 0.19, 0.03


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


def brick(name, across):
    """Red-brown brick in running bond with pale mortar, laid on the wall
    plane spanned by the part's own `across` axis ('X' or 'Y') and its
    vertical, so the bricks turn with the cottage."""
    mat = material(name, (0.42, 0.15, 0.08), roughness=0.85, rim_strength=0.15)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    position = nodes.new('ShaderNodeTexCoord')
    split = nodes.new('ShaderNodeSeparateXYZ')
    plane = nodes.new('ShaderNodeCombineXYZ')
    texture = nodes.new('ShaderNodeTexBrick')
    texture.offset = 0.5
    texture.inputs['Color1'].default_value = (0.45, 0.16, 0.08, 1)
    texture.inputs['Color2'].default_value = (0.32, 0.11, 0.06, 1)
    texture.inputs['Mortar'].default_value = (0.55, 0.50, 0.44, 1)
    texture.inputs['Scale'].default_value = 1.0
    texture.inputs['Mortar Size'].default_value = 0.012
    texture.inputs['Brick Width'].default_value = 0.26
    texture.inputs['Row Height'].default_value = 0.11
    texture.inputs['Bias'].default_value = -0.2
    links.new(position.outputs['Object'], split.inputs[0])
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

brick_front = brick('Brick (front and back)', 'X')
brick_side = brick('Brick (gables)', 'Y')
boards = material('Roof boards', (0.03, 0.025, 0.02), roughness=0.9)
tiles = [material('Dark roof tile', color, roughness=0.55, rim_strength=0.15)
         for color in ((0.075, 0.072, 0.08), (0.10, 0.095, 0.10), (0.06, 0.058, 0.065))]
wood = material('Weathered oak', (0.22, 0.11, 0.05), roughness=0.75, rim_strength=0.1)
timber = material('Dark timber', (0.12, 0.06, 0.03), roughness=0.8, rim_strength=0.1)
dark_iron = material('Black iron fittings', (0.03, 0.03, 0.035), roughness=0.4, metallic=0.9)
stone = material('Doorstep stone', (0.45, 0.44, 0.42), roughness=0.85)
glow = material('Warm lamplight', (0.8, 0.45, 0.18), emission=(1.0, 0.50, 0.16), strength=1.2)

# Walls: front and back, and the two gables up to the ridge.
T = 0.06  # wall thickness
box('Front wall', -HALF_W, HALF_W, SOUTH, SOUTH + T, 0, EAVES, brick_front, 0.004)
box('Back wall', -HALF_W, HALF_W, NORTH - T, NORTH, 0, BACK_EAVES, brick_front, 0.004)
mid = RIDGE_Y
top = EAVES + RIDGE_RISE
for side, name in ((-1, 'West gable'), (1, 'East gable')):
    x0, x1 = sorted((side * HALF_W, side * (HALF_W - T)))
    vertices = [(x, y, z) for x in (x0, x1) for y, z in
                ((SOUTH, 0), (NORTH, 0), (NORTH, BACK_EAVES), (mid, top), (SOUTH, EAVES))]
    faces = [(0, 1, 2, 3, 4), (9, 8, 7, 6, 5)]
    faces += [(k, k + 5, (k + 1) % 5 + 5, (k + 1) % 5) for k in range(5)]
    mesh(name, vertices, faces, brick_side)

# Roof: dark boards from the eaves to the ridge, covered in courses of dark
# tiles, each course overlapping the one below it, its lower edge raised by
# a tile's thickness so the courses show as steps; alternate courses are
# offset by half a tile. Half-round tiles cap the ridge.
pitch = math.atan2(RIDGE_RISE, mid - SOUTH)
slopes = {-1: pitch, 1: pitch}
runs = {-1: (mid - SOUTH + EAVE_OUT) / math.cos(pitch),
        1: (NORTH - mid + EAVE_OUT) / math.cos(pitch)}
left, right = -HALF_W - GABLE_OUT, HALF_W + GABLE_OUT


def tile_courses(name, ridge, along, down, out, u_range, v_range):
    """Courses of tiles on a roof slope: `ridge` is a point on its top
    edge, `along` the unit vector along it, `down` and `out` the unit
    vectors down the slope and out of it; tiles cover `u_range` along and
    `v_range` down from the ridge."""
    u_lo, u_hi = u_range
    v_lo, v_hi = v_range
    courses = math.ceil((v_hi - v_lo - TILE_LEN) / TILE_STEP) + 1
    for row in range(courses):
        v0 = v_lo + min(row * TILE_STEP, v_hi - v_lo - TILE_LEN)
        v1 = v0 + TILE_LEN
        u = u_lo - (TILE_W / 2 if row % 2 else 0.0)
        k = 0
        while u < u_hi:
            u0, u1 = max(u, u_lo), min(u + TILE_W - 0.006, u_hi)
            if u1 > u0:
                vertices = []
                for a in (u0, u1):
                    for v, lift in ((v0, 0.0), (v1, TILE_THICK)):
                        for w in (lift, lift + TILE_THICK):
                            vertices.append(tuple(ridge + along * a + down * v
                                                  + out * (ROOF_THICK / 2 + w)))
                faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6),
                         (0, 2, 6, 4), (1, 5, 7, 3)]
                mesh(name + ' tile', vertices, faces, tiles[(row * 5 + k * 3) % 3])
            u += TILE_W
            k += 1


ridge = Vector((0, mid, top + ROOF_THICK))
x_axis = Vector((1, 0, 0))
for side, name in ((-1, 'South'), (1, 'North')):
    slope, run = slopes[side], runs[side]
    angle = slope if side < 0 else -slope
    down = Vector((0, side * math.cos(slope), -math.sin(slope)))
    out = Vector((0, side * math.sin(slope), math.cos(slope)))
    centre = ridge + down * (run / 2) - Vector((0, 0, ROOF_THICK))
    box(name + ' roof boards', left, right, -run / 2, run / 2,
        -ROOF_THICK / 2, ROOF_THICK / 2, boards, 0.004, rotation=(angle, 0, 0))
    bpy.context.object.location = centre
    tile_courses(name + ' roof', ridge, x_axis, down, out, (left, right), (0, run))
bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.08, depth=right - left,
                                    location=(0, mid, top + ROOF_THICK + 0.02),
                                    rotation=(0, math.pi / 2, 0))
finish(bpy.context.object, 'Ridge tiles', tiles[0])

# A stout brick chimney at the west gable, the one turned toward the camera,
# set back behind the ridge on the north slope, with a thick corbelled brick
# top and a dark flue; drawn large for the cottage, and leaning a little
# toward the west, like a toy's.
cx0, cx1 = -HALF_W + 0.04, -HALF_W + 0.34
cy0 = mid + 0.16
cy1 = cy0 + 0.30
chimney_top = top + 0.28
chimney_start = set(bpy.data.objects)
box('Chimney', cx0, cx1, cy0, cy1, EAVES, chimney_top, brick_front, 0.01)
box('Chimney corbel', cx0 - 0.04, cx1 + 0.04, cy0 - 0.04, cy1 + 0.04, chimney_top,
    chimney_top + 0.08, brick_front, 0.01)
box('Chimney flue', cx0 + 0.06, cx1 - 0.06, cy0 + 0.06, cy1 - 0.06, chimney_top + 0.075,
    chimney_top + 0.085, boards, 0)
base = Vector(((cx0 + cx1) / 2, (cy0 + cy1) / 2, EAVES))
lean = (Matrix.Translation(base) @ Matrix.Rotation(math.radians(-5), 4, 'Y')
        @ Matrix.Translation(-base))
bpy.context.view_layer.update()
for obj in set(bpy.data.objects) - chimney_start:
    obj.matrix_world = lean @ obj.matrix_world

# The front: a plank door with a doorstep, and tall, unglazed windows lit
# softly from inside, framed in thick oak; both drawn large for the cottage,
# so they read at sprite size, the door's top tucked under the eaves.
DOOR_X0, DOOR_X1, DOOR_TOP = -0.67, -0.25, 0.74
front = SOUTH - 0.012
box('Door', DOOR_X0, DOOR_X1, front - 0.01, SOUTH + 0.01, 0.0, DOOR_TOP, wood, 0.006)
for k in range(1, 4):
    px = DOOR_X0 + k * (DOOR_X1 - DOOR_X0) / 4
    box('Door plank gap', px - 0.004, px + 0.004, front - 0.016, front, 0.02, DOOR_TOP - 0.02,
        dark_iron, 0)
box('Door handle', DOOR_X1 - 0.09, DOOR_X1 - 0.05, front - 0.05, front - 0.01, 0.34, 0.38,
    dark_iron, 0.008)
# A timber frame stands out from the wall around the door: a post either
# side and a beam across above the door.
POST, STAND_OUT, BEAM_Z0, BEAM_Z1 = 0.09, 0.10, DOOR_TOP + 0.04, DOOR_TOP + 0.13
x_lo, x_hi = DOOR_X0 - 0.02 - POST, DOOR_X1 + 0.02 + POST
for px in (x_lo, x_hi - POST):
    box('Door post', px, px + POST, SOUTH - STAND_OUT, SOUTH, 0.0, BEAM_Z0, timber, 0.006)
box('Door beam', x_lo - 0.04, x_hi + 0.04, SOUTH - STAND_OUT, SOUTH, BEAM_Z0, BEAM_Z1, timber,
    0.006)
WIN_W, WIN_Z0, WIN_Z1, F = 0.26, 0.24, 0.66, 0.055
# The windows' bars cross diagonally in a lattice of tall diamonds: bars
# this thick, rising this steeply, LATTICE diamonds across.
BAR, BAR_RISE, LATTICE = 0.026, 1.8, 2


def window(a0, wall, at):
    """A tall window `a0` to `a0 + WIN_W` along a wall whose outer face is at
    `wall` across it; `at(a, d, z)` turns a point `a` along the wall, `d`
    across it (growing inward) and `z` up into world coordinates."""
    a1 = a0 + WIN_W
    face = wall - 0.012

    def slab(name, b0, b1, d0, d1, z0, z1, mat, bevel):
        p, q = at(b0, d0, z0), at(b1, d1, z1)
        box(name, min(p[0], q[0]), max(p[0], q[0]), min(p[1], q[1]), max(p[1], q[1]),
            z0, z1, mat, bevel)

    slab('Window light', a0, a1, face - 0.002, wall + 0.02, WIN_Z0, WIN_Z1, glow, 0)
    for name, b0, b1, z0, z1 in (('Window sill', a0 - F, a1 + F, WIN_Z0 - F, WIN_Z0),
                                 ('Window lintel', a0 - F, a1 + F, WIN_Z1, WIN_Z1 + F),
                                 ('Window jamb', a0 - F, a0, WIN_Z0, WIN_Z1),
                                 ('Window jamb', a1, a1 + F, WIN_Z0, WIN_Z1)):
        slab(name, b0, b1, face - 0.03, wall + 0.01, z0, z1, wood, 0.004)
    # Each bar is the line z = WIN_Z0 + sign * BAR_RISE * (a - a0) + c, cut
    # to the window.
    step = BAR_RISE * WIN_W / LATTICE
    for sign in (1, -1):
        offsets = [k * step for k in range(-2 * LATTICE - 6, 2 * LATTICE + 7)]
        for c in offsets:
            lo = (WIN_Z0 - WIN_Z0 - c) / (sign * BAR_RISE) + a0
            hi = (WIN_Z1 - WIN_Z0 - c) / (sign * BAR_RISE) + a0
            s0, s1 = max(a0, min(lo, hi)), min(a1, max(lo, hi))
            if s1 - s0 < 1e-3:
                continue
            ends = [(s, WIN_Z0 + sign * BAR_RISE * (s - a0) + c) for s in (s0, s1)]
            length = math.hypot(ends[1][0] - ends[0][0], ends[1][1] - ends[0][1])
            na = -(ends[1][1] - ends[0][1]) / length * BAR / 2
            nz = (ends[1][0] - ends[0][0]) / length * BAR / 2
            vertices = [at(s + ka * na, d, z + ka * nz) for (s, z) in ends
                        for ka in (-1, 1) for d in (face - 0.02, wall + 0.01)]
            faces = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3),
                     (0, 4, 6, 2), (1, 3, 7, 5)]
            mesh('Window lattice bar', vertices, faces, wood)


# Two in the front wall beside the door, either side of where the one
# window first stood (centred WIN_FRONT along it, WIN_GAP apart), and two in
# the west gable, the one turned toward the camera: one in its middle and
# one nearer the front.
WIN_FRONT, WIN_GAP = 0.44, 0.50
for centre in (WIN_FRONT - WIN_GAP / 2, WIN_FRONT + WIN_GAP / 2):
    window(centre - WIN_W / 2, SOUTH, lambda a, d, z: (a, d, z))
for centre in ((SOUTH + NORTH) / 2, SOUTH + 0.42):
    window(centre - WIN_W / 2, -HALF_W, lambda a, d, z: (d, a, z))
# The floor is raised a little off the ground: everything built so far is
# lifted FLOOR_RISE onto a stone plinth, a little wider than the walls and
# reaching out in front past the door posts as a narrow porch ledge, with
# STEPS stone steps up to it before the door.
FLOOR_RISE, PLINTH_OUT, LEDGE, STEPS, TREAD = 0.20, 0.04, 0.16, 2, 0.12
lift = Matrix.Translation((0, 0, FLOOR_RISE))
bpy.context.view_layer.update()
for obj in scene.objects:
    obj.matrix_world = lift @ obj.matrix_world
box('Plinth', -HALF_W - PLINTH_OUT, HALF_W + PLINTH_OUT, SOUTH - LEDGE, NORTH + PLINTH_OUT,
    0, FLOOR_RISE, stone, 0.01)
for k in range(STEPS):
    y1 = SOUTH - LEDGE - k * TREAD
    box('Step', x_lo - 0.04, x_hi + 0.04, y1 - TREAD, y1, 0,
        FLOOR_RISE * (STEPS - k) / (STEPS + 1), stone, 0.01)

# Like the monsters, the cottage is turned about its middle, though 45
# degrees and toward screen right, so its west gable and chimney show beside the
# front.
pivot = Vector((0, MID, 0))
turn = (Matrix.Translation(pivot) @ Matrix.Rotation(YAW, 4, 'Z')
        @ Matrix.Translation(-pivot))
bpy.context.view_layer.update()
for obj in scene.objects:
    obj.matrix_world = turn @ obj.matrix_world

# Centre the cottage across the cells and shrink it about the same point to
# fit their width on screen (the camera's image x is the world x), and find
# how far it reaches below and above them on the image (image up is
# y sin 60 + z cos 60 on the ground plane through the cells' south edge),
# to 0.05 cells.
bpy.context.view_layer.update()
points = [obj.matrix_world @ v.co for obj in scene.objects if obj.type == 'MESH'
          for v in obj.data.vertices]
x_lo, x_hi = min(p.x for p in points), max(p.x for p in points)
fit = CELLS * CELL_W / (x_hi - x_lo)
shrink = (Matrix.Translation(pivot) @ Matrix.Scale(fit, 4)
          @ Matrix.Translation(-pivot - Vector(((x_lo + x_hi) / 2, 0, 0))))
for obj in scene.objects:
    obj.matrix_world = shrink @ obj.matrix_world
ups = [(shrink @ p).y * math.sin(ELEVATION) + (shrink @ p).z * math.cos(ELEVATION)
       for p in points]
UNDER = math.ceil(max(0.0, -min(ups)) / CELL_UP * 20) / 20
OVERHANG = math.ceil(max(0.0, max(ups) / CELL_UP - 1) * 20) / 20
print(f'tavern: scale {fit:.3f}, UNDER {UNDER}, OVERHANG {OVERHANG}')
# Where the image sits on the cells, for whatever draws it.
(OUT / 'tavern.json').write_text(json.dumps({'cells': CELLS, 'under': UNDER,
                                             'overhang': OVERHANG}) + '\n')
scene.render.resolution_y = round(CELL_PIXELS[1] * (UNDER + 1 + OVERHANG))

# Lights as for the stairs: a warm key above and behind, cool fill and rims.
for pos, power, size, color in [((-3, 3, 9), 420, 1.5, (1.0, 0.93, 0.85)),
                                 ((6, -3, 4), 120, 6, (0.6, 0.75, 1.0)),
                                 ((-6, 6, 4), 300, 3, (0.55, 0.8, 1.0)),
                                 ((6, 6, 4), 300, 3, (1.0, 0.7, 0.9))]:
    bpy.ops.object.light_add(type='AREA', location=pos)
    light = bpy.context.object
    light.data.energy, light.data.size, light.data.color = power, size, color
    light.data.cycles.cast_shadow = pos == (-3, 3, 9)
    light.rotation_euler = (Vector((0, 0, 0)) - light.location).to_track_quat('-Z', 'Y').to_euler()

# Frame the canvas from UNDER cells below the cells' south edge on the
# ground to OVERHANG cells above their north edge, the cells' width.
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
scene.render.filepath = str(OUT / 'tavern.png')
bpy.ops.render.render(write_still=True)
