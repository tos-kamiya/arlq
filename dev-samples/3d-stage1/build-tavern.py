"""The Stage 6 tavern for the sprite GUI: a small brick cottage.

Run with: blender --background --threads 4 --python dev-samples/3d-stage1/build-tavern.py

The tavern takes two cells side by side on the floor. This draws it as a
small, old-fashioned cottage seen with the walls' and stairs' 60-degree
orthographic camera: red-brown brick walls, a lopsided gable roof of dark
tiles in overlapping courses under half-round ridge tiles (its ridge
east-west, along the two cells; both slopes at the same pitch, the back one
running on down over the cottage stretched back under it to a low back
wall, like a catslide roof, so the gables read like the kana へ), a low brick chimney at the west gable, set back behind the
ridge, a plank door and a tall, unglazed window lit softly from inside;
no sign. The cottage is built twice its first size; the chimney, door,
window and roof tiles keep theirs. The finished cottage is then shrunk to
fit the two cells' width, whatever that makes its scale beside the
characters. The canvas is the two cells wide; it covers OVERHANG cells
north of them, where the roof and chimney rise, and UNDER cells south of
them, where the turned cottage's front corner and eaves reach, both found
from the shrunk model and printed:
  tavern.png
"""
from pathlib import Path
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
ROOF_THICK = 0.03
# Turned toward screen right, further than the monsters (MONSTER_YAW in
# build-heroic.py turns them 30 degrees the other way).
YAW = math.radians(45)
# The roof tiles: width, the step between courses down the slope, each
# tile's length (so the courses overlap) and thickness.
TILE_W, TILE_STEP, TILE_LEN, TILE_THICK = 0.11, 0.075, 0.11, 0.018


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
    texture.inputs['Mortar Size'].default_value = 0.008
    texture.inputs['Brick Width'].default_value = 0.16
    texture.inputs['Row Height'].default_value = 0.07
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
bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.045, depth=right - left,
                                    location=(0, mid, top + ROOF_THICK + 0.01),
                                    rotation=(0, math.pi / 2, 0))
finish(bpy.context.object, 'Ridge tiles', tiles[0])

# A low brick chimney at the west gable, the one turned toward the camera,
# set back behind the ridge on the north slope, with a corbelled brick top
# and a dark flue; it keeps its first size, set back as far for the
# cottage's size.
cx0, cx1 = -HALF_W + 0.02, -HALF_W + 0.20
cy0 = mid + 0.08 * SCALE
cy1 = cy0 + 0.18
chimney_top = top + 0.06
box('Chimney', cx0, cx1, cy0, cy1, EAVES, chimney_top, brick_front, 0.006)
box('Chimney corbel', cx0 - 0.02, cx1 + 0.02, cy0 - 0.02, cy1 + 0.02, chimney_top,
    chimney_top + 0.04, brick_front, 0.006)
box('Chimney flue', cx0 + 0.04, cx1 - 0.04, cy0 + 0.04, cy1 - 0.04, chimney_top + 0.035,
    chimney_top + 0.042, boards, 0)

# The front: a plank door with a doorstep, and a tall, unglazed window lit
# softly from inside, framed in oak; both keep their first sizes, placed
# about as far from the middle for the cottage's size.
DOOR_X0, DOOR_X1, DOOR_TOP = -0.60, -0.32, 0.62
front = SOUTH - 0.012
box('Door', DOOR_X0, DOOR_X1, front - 0.01, SOUTH + 0.01, 0.0, DOOR_TOP, wood, 0.006)
for k in range(1, 4):
    px = DOOR_X0 + k * (DOOR_X1 - DOOR_X0) / 4
    box('Door plank gap', px - 0.004, px + 0.004, front - 0.016, front, 0.02, DOOR_TOP - 0.02,
        dark_iron, 0)
box('Door handle', DOOR_X1 - 0.06, DOOR_X1 - 0.03, front - 0.04, front - 0.01, 0.28, 0.31,
    dark_iron, 0.005)
box('Doorstep', DOOR_X0 - 0.05, DOOR_X1 + 0.05, SOUTH - 0.10, SOUTH, 0, 0.03, stone, 0.006)
WIN_W, WIN_Z0, WIN_Z1, F = 0.18, 0.30, 0.62, 0.035


def window(a0, wall, place):
    """A tall window `a0` to `a0 + WIN_W` along a wall whose outer face is at
    `wall` across it; `place(a0, a1, d0, d1, z0, z1)` turns spans along and
    across the wall (d0 < d1, outward to inward) into a box's six bounds."""
    a1 = a0 + WIN_W
    am = (a0 + a1) / 2
    zm = (WIN_Z0 + WIN_Z1) / 2
    face = wall - 0.012
    box('Window light', *place(a0, a1, face - 0.002, wall + 0.02, WIN_Z0, WIN_Z1), glow, 0)
    for name, b0, b1, z0, z1 in (('Window sill', a0 - F, a1 + F, WIN_Z0 - F, WIN_Z0),
                                 ('Window lintel', a0 - F, a1 + F, WIN_Z1, WIN_Z1 + F),
                                 ('Window jamb', a0 - F, a0, WIN_Z0, WIN_Z1),
                                 ('Window jamb', a1, a1 + F, WIN_Z0, WIN_Z1),
                                 ('Window mullion', am - 0.012, am + 0.012, WIN_Z0, WIN_Z1),
                                 ('Window transom', a0, a1, zm - 0.012, zm + 0.012)):
        box(name, *place(b0, b1, face - 0.03, wall + 0.01, z0, z1), wood, 0.004)


# One in the front wall beside the door, and one in the middle of the west
# gable, the one turned toward the camera.
window(0.35, SOUTH, lambda a0, a1, d0, d1, z0, z1: (a0, a1, d0, d1, z0, z1))
window((SOUTH + NORTH - WIN_W) / 2, -HALF_W,
       lambda a0, a1, d0, d1, z0, z1: (d0, d1, a0, a1, z0, z1))
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
