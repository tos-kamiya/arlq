"""Marble column wall parts for the sprite GUI.

Run with: blender --factory-startup --background --threads 4 --python dev-samples/3d-stage1/build-walls.py

Every wall cell gets one column. Each part is rendered with the same
60-degree orthographic camera on the same canvas, which covers one cell plus
the band it rises into the cell to its north, so the GUI can stack them:
  wall-column.png      plinth, shaft and capital
  wall-link-west.png   architrave and plinth reaching the west edge
  wall-link-east.png   the same toward the east edge
The parts are near-white; the GUI tints them for visible/explored walls.

With `-- --training` the same columns are written as training-*.png for the
Stage 5 training room: brighter, and darkening far less toward its bright
floor.

With `-- --torch` only the wall torches of the dungeon's west and east edge
walls are written, each mounted on the column's side facing the floor
(east for the west edge wall, west for the east edge wall):
  wall-torch-east.png        the torch alone (iron bracket and stick, no
                             flame), hidden where the column stands in front
  wall-torch-east-light.png  its light: the flame, a faint halo and the warm
                             light it casts on the column, in their own
                             colour (light_layer.py with own_colour=True)
  wall-torch-west*.png       the same on the west side
The GUI draws the torch over the column and adds the light layer.
The output directory can be changed with WALLS_OUT.
"""
from pathlib import Path
import math
import os
import sys

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from light_layer import write_light_layer

OUT = Path(os.environ.get('WALLS_OUT', ROOT.parents[1] / 'src' / 'arlq' / 'assets' / 'walls'))
OUT.mkdir(parents=True, exist_ok=True)
# Canvas aspect: one sprite-mode cell (15 x 20 px at scale 1) plus a
# 0.25-cell rise.
WIDTH, HEIGHT = 300, 500
ELEVATION = math.radians(60)
DEPTH = 0.30  # half depth (north-south) of the plinth and abacus
TOP = 2.81  # height of the abacus top, chosen so the column fills the canvas
# The canvas, framed from the plinth's near bottom edge to the abacus's far
# top edge on the image plane (up = z cos(60) + y sin(60)), and its width.
# The column keeps the size it had on the former 13 px cells (1 unit wide);
# the links reach the wider canvas's edges.
CANVAS_UP = (TOP * math.cos(ELEVATION) + DEPTH * math.sin(ELEVATION)) + DEPTH * math.sin(ELEVATION)
CANVAS_W = CANVAS_UP * WIDTH / HEIGHT
# The marble darkens toward the floor to stress the walls' height
# (darken_toward_floor): FOOT_SHADE of its brightness at the floor, rising
# as height ** HEIGHT_CURVE to full brightness at the abacus top.
ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
TRAINING = '--training' in ARGS
TORCH = '--torch' in ARGS
# The wall torch: mounted on the shaft at this height and angle from the
# east toward the viewer, its stick leaning out by TORCH_LEAN, and the
# flame's point light (energy in W).
TORCH_MOUNT_Z = 1.30
TORCH_MOUNT_ANGLE = math.radians(-25)
TORCH_LEAN = math.radians(15)
TORCH_LIGHT_ENERGY = 25.0
# The torch's light is a small difference between two renders; more samples
# keep its render noise from showing as specks on the column.
TORCH_SAMPLES = 1024
# A faint halo of light around the flame, within the canvas.
TORCH_HALO_RADIUS = 0.20
TORCH_HALO_STRENGTH = 1.5
FOOT_SHADE = 0.45 if TRAINING else 0.12
HEIGHT_CURVE = 1.0


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


def darken_toward_floor(mat, foot_shade, curve):
    """Blend the whole surface (color, highlights and rim) toward black near
    the floor: by foot_shade at z = 0, rising as height ** curve to full
    brightness at TOP."""
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    surface = nodes['Material Output'].inputs['Surface']
    shader = surface.links[0].from_socket
    position = nodes.new('ShaderNodeNewGeometry')
    xyz = nodes.new('ShaderNodeSeparateXYZ')
    height = nodes.new('ShaderNodeMapRange')
    height.inputs['From Min'].default_value = 0
    height.inputs['From Max'].default_value = TOP
    power = nodes.new('ShaderNodeMath')
    power.operation = 'POWER'
    power.inputs[1].default_value = curve
    shade = nodes.new('ShaderNodeMapRange')
    shade.inputs['To Min'].default_value = foot_shade
    black = nodes.new('ShaderNodeEmission')
    black.inputs['Strength'].default_value = 0
    mix = nodes.new('ShaderNodeMixShader')
    links.new(position.outputs['Position'], xyz.inputs[0])
    links.new(xyz.outputs['Z'], height.inputs['Value'])
    links.new(height.outputs['Result'], power.inputs[0])
    links.new(power.outputs[0], shade.inputs['Value'])
    links.new(shade.outputs['Result'], mix.inputs['Fac'])
    links.new(black.outputs[0], mix.inputs[1])
    links.new(shader, mix.inputs[2])
    links.new(mix.outputs[0], surface)
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
if TRAINING:
    scene.view_settings.exposure = 0.5  # brighter, whiter marble
scene.render.resolution_x, scene.render.resolution_y = WIDTH, HEIGHT
scene.render.film_transparent = True
world = bpy.data.worlds.new('Night studio')
world.use_nodes = True
world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.05, 0.06, 0.08, 1)
scene.world = world

marble = darken_toward_floor(
    material('Marble', (0.92, 0.91, 0.88), 0.0, 0.65, rim_strength=0.25),
    FOOT_SHADE, HEIGHT_CURVE)
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
        box('Architrave', (side * CANVAS_W / 4, 0, TOP - 0.25), (CANVAS_W / 2, 1.8 * DEPTH, 0.46),
            marble, 0.005),
        box('Stylobate', (side * CANVAS_W / 4, 0, 0.13), (CANVAS_W / 2, 2 * DEPTH, 0.26),
            marble, 0.005),
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
assert abs(height - CANVAS_UP) < 1e-9

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


def torch_parts(side):
    """Bracket, stick, head and flame of a torch on the shaft's `side` (+1
    east, -1 west), and its point light."""
    iron = material('Black iron', (0.03, 0.03, 0.035), 0.0, 0.4)
    wood = material('Torch stick', (0.20, 0.10, 0.04), 0.0, 0.8)
    pitch = material('Pitch-soaked rag', (0.05, 0.03, 0.02), 0.0, 0.9)
    flame = material('Torch flame', (0.9, 0.5, 0.15), 0.0, 0.5)
    core = material('Torch flame core', (1.0, 0.8, 0.4), 0.0, 0.5)
    for mat, color, strength in ((flame, (1.0, 0.28, 0.03), 0.9),
                                 (core, (1.0, 0.60, 0.12), 1.5)):
        bsdf = mat.node_tree.nodes['Principled BSDF']
        bsdf.inputs['Emission Color'].default_value = (*color, 1)
        bsdf.inputs['Emission Strength'].default_value = strength
    angle = TORCH_MOUNT_ANGLE if side > 0 else math.pi - TORCH_MOUNT_ANGLE
    out = Vector((math.cos(angle), math.sin(angle), 0))
    mount = out * 0.31 + Vector((0, 0, TORCH_MOUNT_Z))
    objects = []
    # A plate on the shaft and an arm reaching out to a ring.
    plate = box('Torch plate', mount, (0.10, 0.10, 0.16), iron, 0.01)
    plate.rotation_euler = (0, 0, angle)
    arm_end = mount + out * 0.10
    bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.018, depth=0.10,
                                        location=(mount + arm_end) / 2,
                                        rotation=(0, math.pi / 2, angle))
    arm = bpy.context.object
    arm.name = 'Torch arm'
    arm.data.materials.append(iron)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.04, minor_radius=0.012,
                                     location=arm_end)
    ring = bpy.context.object
    ring.name = 'Torch ring'
    ring.data.materials.append(iron)
    objects += [plate, arm, ring]
    # The stick through the ring, leaning out; the rag and flame at its top.
    lean = out * math.sin(TORCH_LEAN) + Vector((0, 0, math.cos(TORCH_LEAN)))
    rotation = lean.to_track_quat('Z', 'Y').to_euler()
    for name, mat, start, length, r0, r1 in (
            ('Torch stick', wood, -0.14, 0.34, 0.020, 0.030),
            ('Torch head', pitch, 0.17, 0.08, 0.042, 0.048)):
        bpy.ops.mesh.primitive_cone_add(vertices=10, radius1=r0, radius2=r1, depth=length,
                                        location=arm_end + lean * (start + length / 2),
                                        rotation=rotation)
        obj = bpy.context.object
        obj.name = name
        obj.data.materials.append(mat)
        objects.append(obj)
    top = arm_end + lean * 0.25
    for name, mat, radius, depth, lift in (('Torch flame', flame, 0.075, 0.30, 0.13),
                                           ('Torch flame core', core, 0.040, 0.16, 0.08)):
        bpy.ops.mesh.primitive_cone_add(vertices=12, radius1=radius, depth=depth,
                                        location=top + Vector((0, 0, lift)))
        obj = bpy.context.object
        obj.name = name
        obj.data.materials.append(mat)
        objects.append(obj)
    # The halo: a disc facing the camera, glowing most at its centre and
    # fading out to its rim, in front of the flame.
    centre = top + Vector((0, 0, 0.12))
    view = Vector((0, math.cos(ELEVATION), -math.sin(ELEVATION)))
    bpy.ops.mesh.primitive_circle_add(vertices=32, radius=TORCH_HALO_RADIUS, fill_type='NGON',
                                      location=centre - view * 0.3,
                                      rotation=view.to_track_quat('-Z', 'Y').to_euler())
    halo = bpy.context.object
    halo.name = 'Torch halo'
    halo.data.materials.append(halo_material())
    objects.append(halo)
    bpy.ops.object.light_add(type='POINT', location=centre + out * 0.03)
    light = bpy.context.object
    light.data.energy, light.data.color = TORCH_LIGHT_ENERGY, (1.0, 0.50, 0.15)
    light.data.shadow_soft_size = 0.05
    return objects, light, (flame, core), halo


def halo_material():
    mat = bpy.data.materials.new('Torch halo')
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.remove(nodes['Principled BSDF'])
    coords = nodes.new('ShaderNodeTexCoord')
    distance = nodes.new('ShaderNodeVectorMath')
    distance.operation = 'LENGTH'
    fade = nodes.new('ShaderNodeMapRange')
    fade.inputs['From Max'].default_value = TORCH_HALO_RADIUS
    fade.inputs['To Min'].default_value = 1.0
    fade.inputs['To Max'].default_value = 0.0
    square = nodes.new('ShaderNodeMath')
    square.operation = 'POWER'
    square.inputs[1].default_value = 2.0
    glow = nodes.new('ShaderNodeEmission')
    glow.inputs['Color'].default_value = (1.0, 0.45, 0.12, 1)
    glow.inputs['Strength'].default_value = TORCH_HALO_STRENGTH
    clear = nodes.new('ShaderNodeBsdfTransparent')
    mix = nodes.new('ShaderNodeMixShader')
    links.new(coords.outputs['Object'], distance.inputs[0])
    links.new(distance.outputs['Value'], fade.inputs['Value'])
    links.new(fade.outputs['Result'], square.inputs[0])
    links.new(square.outputs[0], mix.inputs['Fac'])
    links.new(clear.outputs[0], mix.inputs[1])
    links.new(glow.outputs[0], mix.inputs[2])
    links.new(mix.outputs[0], nodes['Material Output'].inputs['Surface'])
    return mat


def render_torches():
    """Render each side's torch and its light layer (see the docstring)."""
    column = parts['column']
    scene.cycles.samples = TORCH_SAMPLES
    for name, side in (('east', 1), ('west', -1)):
        objects, light, glowing, halo = torch_parts(side)
        others = [obj for obj in scene.objects
                  if obj.type == 'MESH' and obj not in column and obj not in objects]
        for obj in others:
            obj.hide_render = True
        lit_path = OUT / f'wall-torch-{name}-lit.png'
        unlit_path = OUT / f'wall-torch-{name}-unlit.png'
        scene.render.use_freestyle = False
        scene.render.filepath = str(lit_path)
        bpy.ops.render.render(write_still=True)
        # The light layer: the column and torch again, the flame out.
        halo.hide_render = True
        energy = light.data.energy
        light.data.energy = 0.0
        saved = []
        for mat in glowing:
            bsdf = mat.node_tree.nodes['Principled BSDF']
            saved.append((bsdf, bsdf.inputs['Emission Strength'].default_value,
                          tuple(bsdf.inputs['Base Color'].default_value)))
            bsdf.inputs['Emission Strength'].default_value = 0.0
            bsdf.inputs['Base Color'].default_value = (0, 0, 0, 1)
        scene.render.filepath = str(unlit_path)
        bpy.ops.render.render(write_still=True)
        write_light_layer(lit_path, unlit_path, OUT / f'wall-torch-{name}-light.png',
                          own_colour=True)
        light.data.energy = energy
        for bsdf, strength, color in saved:
            bsdf.inputs['Emission Strength'].default_value = strength
            bsdf.inputs['Base Color'].default_value = color
        # The torch alone, hidden behind the column where it stands in front.
        # The flame is left out: the light layer holds it, so it stays as
        # bright when the GUI dims the torch with the wall.
        flames = [obj for obj in objects if obj.name.startswith('Torch flame')]
        for obj in flames:
            obj.hide_render = True
        for obj in column:
            obj.is_holdout = True
        scene.render.filepath = str(OUT / f'wall-torch-{name}.png')
        bpy.ops.render.render(write_still=True)
        for obj in column:
            obj.is_holdout = False
        for path in (lit_path, unlit_path):
            path.unlink()
        for obj in objects + [light]:
            bpy.data.objects.remove(obj)
        for obj in others:
            obj.hide_render = False


if TORCH:
    render_torches()
    sys.exit(0)

for name, objects in parts.items():
    for obj in scene.objects:
        obj.hide_render = obj.type == 'MESH' and obj not in objects
    # Links meet their neighbours at the canvas edge; an outline there would
    # show as a seam, so only the column is outlined.
    scene.render.use_freestyle = name == 'column'
    scene.render.filepath = str(OUT / (('training-' if TRAINING else 'wall-') + name + '.png'))
    bpy.ops.render.render(write_still=True)
