"""Marble stair cells for the sprite GUI.

Run with: blender --background --threads 4 --python dev-samples/3d-stage1/build-stairs.py

Each stair is a spiral staircase inside a round tower, rendered with an
orthographic camera looking 45 degrees down (steeper than the walls' 60
degrees, so more of the spiral shows) on the walls' canvas (one 15 x 20 px
cell plus the 0.25-cell band north of it), so the GUI places it exactly like
a wall part:
  stairs-up.png    a few steps spiralling up around a newel
  stairs-down.png  steps spiralling down a round well into the dark
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
WIDTH, HEIGHT = 300, 500
ELEVATION = math.radians(45)
OVERHANG = 0.25
# One cell is 1 unit wide; its north-south depth on the ground follows from
# the canvas shape and the view angle. The cell spans y = 0 (south) to DEPTH.
CELL_UP = (HEIGHT / WIDTH) / (1 + OVERHANG)  # cell height on the image plane
DEPTH = CELL_UP / math.sin(ELEVATION)
# The tower stands at the cell's centre: well radius (to the wall's inner
# face), wall thickness, newel radius, and each step's turn, rise and slab
# thickness. The up flight takes two thirds of a turn centred on the back,
# from the front right to the front left, so the wall ribbon stands mostly
# behind it; the down
# flight takes half a turn on the right (east) side, from the back to the
# front. The wall is only a spiral ribbon along the steps' outer ends
# (reaching this far below and above each tread).
TOWER_R, TOWER_WALL, NEWEL_R = 0.38, 0.05, 0.06
STEP_TURN, STEP_RISE, STEP_SLAB = math.radians(30), 0.075, 0.05
UP_STEPS, UP_START = 8, math.radians(-30)
DOWN_STEPS, DOWN_START = 6, math.radians(90)
RIBBON = (0.15, 0.2)
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


def ribbon(name, start, end, tread, mat, ceiling=None):
    """Spiral wall strip from angle start to end along treads at height tread(angle)."""
    cap = (lambda z: min(z, ceiling)) if ceiling is not None else (lambda z: z)
    return ring(name, TOWER_R, TOWER_R + TOWER_WALL, min(start, end), max(start, end),
                lambda angle: tread(angle) - RIBBON[0],
                lambda angle: cap(tread(angle) + RIBBON[1]),
                mat, segments=8 * round(abs(end - start) / STEP_TURN))


def ring(name, r0, r1, a0, a1, z0, z1, mat, segments=None):
    """Solid annular sector around the tower's axis; z0 and z1 may vary with the angle."""
    full = abs(a1 - a0) >= 2 * math.pi - 1e-6
    segments = segments or max(2, round(abs(a1 - a0) / math.radians(6)))
    top = z1 if callable(z1) else (lambda angle: z1)
    bottom = z0 if callable(z0) else (lambda angle: z0)
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    sections = []
    for k in range(segments + 1):
        angle = a0 + (a1 - a0) * k / segments
        c, s = math.cos(angle), math.sin(angle)
        sections.append([bm.verts.new((r * c, CENTRE_Y + r * s, z))
                         for r, z in ((r0, bottom(angle)), (r1, bottom(angle)),
                                      (r1, top(angle)), (r0, top(angle)))])
    for a, b in zip(sections, sections[1:]):
        for i in range(4):
            j = (i + 1) % 4
            bm.faces.new((a[i], a[j], b[j], b[i]))
    if not full:
        bm.faces.new(sections[0])
        bm.faces.new(reversed(sections[-1]))
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.data.materials.append(mat)
    for poly in mesh.polygons:
        poly.use_smooth = False
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

# Up: slab steps wind counterclockwise (seen from above) around a newel,
# starting low on the front right and rising across the back to the front
# left. The wall ribbon is
# a darker stone, so the steps stand out.
tower_stone = material('Tower stone', (0.55, 0.55, 0.53), roughness=0.8)
for i in range(UP_STEPS):
    a0 = UP_START + i * STEP_TURN
    z = (i + 1) * STEP_RISE
    parts['up'].append(ring('Step %d' % i, NEWEL_R, TOWER_R, a0, a0 + STEP_TURN,
                            z - STEP_SLAB, z, marble))
parts['up'].append(ring('Newel', 0, NEWEL_R, 0, 2 * math.pi, 0,
                        (UP_STEPS + 1) * STEP_RISE, marble))
parts['up'].append(ribbon('Wall ribbon', UP_START, UP_START + UP_STEPS * STEP_TURN,
                          lambda angle: STEP_RISE * (1 + (angle - UP_START) / STEP_TURN),
                          tower_stone))

# Down: a low kerb rings a round well; slab steps wind clockwise down its
# right side from the back to the front around a newel, darker the deeper
# they go, with the wall ribbon kept below the floor. Everything under the
# floor beyond them is black, so the open left half reads as a dark drop. An
# invisible holdout ground hides the well from outside. The kerb is a cool
# grey that the GUI's gold tint turns close to the floor's warm grey.
kerb_stone = material('Kerb stone', KERB_COLOR, roughness=0.8)
parts['down'].append(ring('Kerb', TOWER_R, TOWER_R + TOWER_WALL + 0.03, 0, 2 * math.pi,
                          0, 0.06, kerb_stone))
parts['down'].append(ring('Ground', TOWER_R + TOWER_WALL + 0.03, 3, 0, 2 * math.pi,
                          -0.02, 0, ground))
parts['down'].append(ring('Abyss', 0, 3, 0, 2 * math.pi, -2.6, -2.5, void))
parts['down'].append(ring('Newel', 0, NEWEL_R, 0, 2 * math.pi, -2.5, 0, shadowed))
for i in range(DOWN_STEPS):
    a0 = DOWN_START - (i + 1) * STEP_TURN
    z = -(i + 1) * STEP_RISE
    shade = 0.92 * 0.78 ** i
    mat = material('Step %d marble' % i, (shade, shade * 0.99, shade * 0.96), roughness=0.8)
    parts['down'].append(ring('Step %d' % i, NEWEL_R, TOWER_R, a0, a0 + STEP_TURN,
                              z - STEP_SLAB, z, mat))
parts['down'].append(ribbon('Wall ribbon', DOWN_START, DOWN_START - DOWN_STEPS * STEP_TURN,
                            lambda angle: -STEP_RISE * (1 + (DOWN_START - angle) / STEP_TURN),
                            shadowed, ceiling=0))

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
