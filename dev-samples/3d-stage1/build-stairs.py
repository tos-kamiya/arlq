"""Marble stair cells for the sprite GUI.

Run with: blender --background --threads 4 --python dev-samples/3d-stage1/build-stairs.py

Each stair is a short flight turning back at a landing, seen from the front,
rendered with the
walls' 60-degree orthographic camera. The canvas covers one
15 x 20 px cell, 0.25 cells past each side (drawn by the GUI only over
explored floor) and the 0.5-cell band north of it (sprite_funcs.TERRAIN_SIDE,
TERRAIN_OVERHANG):
  stairs-up.png    steps rising from left to right on the floor, turning back
                   at a landing and rising on to the left behind
  stairs-down.png  the same going down into a dark opening
The stone is near-white; the GUI tints it gold, darker outside the view.
"""
from pathlib import Path
import math

import bmesh
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parents[1] / 'src' / 'arlq' / 'assets' / 'stairs'
OUT.mkdir(parents=True, exist_ok=True)
CELL_PIXELS = (300, 400)  # 15 x 20 at 20 px per screen pixel
SIDE, OVERHANG = 0.25, 0.5
WIDTH = round(CELL_PIXELS[0] * (1 + 2 * SIDE))
HEIGHT = round(CELL_PIXELS[1] * (1 + OVERHANG))
ELEVATION = math.radians(60)
# One cell is 1 unit wide; its north-south depth on the ground follows from
# the cell shape and the view angle. The cell spans y = 0 (south) to DEPTH.
CELL_UP = CELL_PIXELS[1] / CELL_PIXELS[0]  # cell height on the image plane
DEPTH = CELL_UP / math.sin(ELEVATION)
# Both ways turn back at a landing: steps per flight, each step's run
# (east-west), each flight's depth (north-south), and the landing's width.
# The way up climbs from left to right along the front, turns at the landing
# on the right and climbs back to the left behind. The way down,
# inside an opening, goes down from left to right along the back half, turns
# at the landing and goes on down to the left along the front half, with
# shallower steps; the opening reaches DOWN_GAP further toward the viewer, so
# the front flight shows past its near edge. Its stone is darker than the way
# up even at the top (DOWN_BRIGHT) and fades to near black at the bottom
# (DOWN_DARK).
FLIGHT_STEPS, STEP_RUN, FLIGHT_DEPTH, LANDING = 3, 0.24, 0.38, 0.3
UP_RISE = 0.15
DOWN_RISE, DOWN_GAP, DOWN_BRIGHT, DOWN_DARK = 0.1, 0.2, 0.6, 0.06
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


def deepening(name, depth, bright=DOWN_BRIGHT, dark=DOWN_DARK):
    """Marble that darkens from z = 0 down to z = -depth."""
    mat = material(name, (bright,) * 3, roughness=0.8)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    position = nodes.new('ShaderNodeNewGeometry')
    split = nodes.new('ShaderNodeSeparateXYZ')
    ramp = nodes.new('ShaderNodeMapRange')
    ramp.inputs['From Min'].default_value = -depth
    ramp.inputs['From Max'].default_value = 0
    ramp.inputs['To Min'].default_value = dark
    ramp.inputs['To Max'].default_value = bright
    tint = nodes.new('ShaderNodeCombineColor')
    links.new(position.outputs['Position'], split.inputs[0])
    links.new(split.outputs['Z'], ramp.inputs['Value'])
    for channel, scale in (('Red', 1.0), ('Green', 0.99), ('Blue', 0.96)):
        if scale == 1.0:
            links.new(ramp.outputs['Result'], tint.inputs[channel])
        else:
            factor = nodes.new('ShaderNodeMath')
            factor.operation = 'MULTIPLY'
            factor.inputs[1].default_value = scale
            links.new(ramp.outputs['Result'], factor.inputs[0])
            links.new(factor.outputs[0], tint.inputs[channel])
    links.new(tint.outputs['Color'], nodes['Principled BSDF'].inputs['Base Color'])
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


def flight(name, x0, run, heights, y0, y1, mat, base=0):
    """One solid stepped block: the steps' profile above z = base, extruded from y0 to y1."""
    profile = [(x0, base)]
    for i, h in enumerate(heights):
        profile += [(x0 + i * run, h), (x0 + (i + 1) * run, h)]
    profile.append((x0 + len(heights) * run, base))
    bm = bmesh.new()
    front = bm.faces.new([bm.verts.new((x, y0, z)) for x, z in profile])
    extruded = bmesh.ops.extrude_face_region(bm, geom=[front])
    bmesh.ops.translate(bm, vec=(0, y1 - y0, 0),
                        verts=[v for v in extruded['geom'] if isinstance(v, bmesh.types.BMVert)])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.data.materials.append(mat)
    mod = obj.modifiers.new('Soft edges', 'BEVEL')
    mod.width = 0.012
    mod.segments = 2
    return obj


CENTRE_Y = DEPTH / 2
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

x0 = -(FLIGHT_STEPS * STEP_RUN + LANDING) / 2
x1 = x0 + FLIGHT_STEPS * STEP_RUN
x2 = x1 + LANDING


def switchback(name, rise, first, second, mat, base=0):
    """A flight from left to right over the y range `first` (treads at rise,
    2 rise, ...), a landing across both ranges, and a flight back to the left
    over `second`, each tread one rise further from the floor; rise < 0 goes
    down. The solids reach down (or up) to z = base."""
    n = FLIGHT_STEPS
    treads = [(i + 1) * rise for i in range(n)], [(2 * n + 1 - i) * rise for i in range(n)]
    ys = sorted(first + second)
    low, high = sorted((base, (n + 1) * rise))
    return [flight(name + ' first flight', x0, STEP_RUN, treads[0], *first, mat, base),
            box(name + ' landing', x1, x2, ys[0], ys[-1], low, high, mat),
            flight(name + ' second flight', x0, STEP_RUN, treads[1], *second, mat, base)]


# Up: solid flights on the floor, so their fronts show the stepped profile
# without lines between steps. The front one rises to the right, to a landing
# as deep as both flights; the back one rises from there to the left, above
# the front one. (The first flight is the front one here.)
y0, y1, y2 = CENTRE_Y - FLIGHT_DEPTH, CENTRE_Y, CENTRE_Y + FLIGHT_DEPTH
parts['up'] += switchback('Up', UP_RISE, (y0, y1), (y1, y2), marble)

# Down: a low kerb rings a rectangular opening; inside, solid flights go down
# from left to right along the back, turn at the landing and go on down to
# the left in front, darker the deeper they go, above a black drop; a gap in
# front of them lets the front flight show. An invisible holdout ground hides the opening's sides from outside.
# The kerb is a cool grey that the GUI's gold tint turns close to the
# floor's warm grey.
kerb = 0.07
y0, y1 = CENTRE_Y - FLIGHT_DEPTH - DOWN_GAP, CENTRE_Y + FLIGHT_DEPTH
kerb_stone = material('Kerb stone', KERB_COLOR, roughness=0.8)
for name, bx0, bx1, by0, by1 in (('Kerb south', x0 - kerb, x2 + kerb, y0 - kerb, y0),
                                 ('Kerb north', x0 - kerb, x2 + kerb, y1, y1 + kerb),
                                 ('Kerb west', x0 - kerb, x0, y0, y1),
                                 ('Kerb east', x2, x2 + kerb, y0, y1)):
    parts['down'].append(box(name, bx0, bx1, by0, by1, 0, 0.06, kerb_stone))
for name, bx0, bx1, by0, by1 in (('Ground south', -3, 3, -3, y0 - kerb),
                                 ('Ground north', -3, 3, y1 + kerb, 6),
                                 ('Ground west', -3, x0 - kerb, -3, 6),
                                 ('Ground east', x2 + kerb, 3, -3, 6)):
    parts['down'].append(box(name, bx0, bx1, by0, by1, -0.02, 0, ground, bevel=0))
parts['down'].append(box('Abyss', -3, 3, -3, 6, -3.1, -3, void, bevel=0))
parts['down'] += switchback('Down', -DOWN_RISE, (CENTRE_Y, y1),
                            (CENTRE_Y - FLIGHT_DEPTH, CENTRE_Y),
                            deepening('Deepening marble', (2 * FLIGHT_STEPS + 1) * DOWN_RISE),
                            base=-3)
parts['down'].append(box('Back wall', x0, x2, y1 - 0.02, y1, -3, 0, shadowed, bevel=0))

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
# up = 0) to OVERHANG cells above its north edge, SIDE cells past each side.
height = CELL_UP * (1 + OVERHANG)
view = Vector((0, math.cos(ELEVATION), -math.sin(ELEVATION)))
image_up = Vector((0, math.sin(ELEVATION), math.cos(ELEVATION)))
centre = image_up * (height / 2)
bpy.ops.object.camera_add(location=centre - view * 20)
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

for name, objects in parts.items():
    for obj in scene.objects:
        obj.hide_render = obj.type == 'MESH' and obj not in objects
    scene.render.filepath = str(OUT / ('stairs-' + name + '.png'))
    bpy.ops.render.render(write_still=True)
