"""Trial sprite of the player's defeat: a splash of blood as a flat symbol.

Like an asterisk, six drops burst out from the centre, one pointing straight
up: each is a teardrop, fine at the centre and swelling to a round head,
with a small droplet beyond it. It is a symbol rather than a realistic
splatter: a flat shape in the plain red of a monster the player cannot beat
(CI_RED), faced to the camera, with no shading and no outline.

Rendered with the character sprites' camera (60 degrees down, 256 px per
2.6 units, crop symmetric about 0.35 above the ground origin), so the GUI
can place it on the player's cell like a character sprite. The colors are
baked into the image.

    blender --background --threads 4 --python dev-samples/3d-stage1/build-splash.py

Writes src/arlq/assets/effects/splash.png, the image the GUI draws.
"""
from pathlib import Path
import math

import bpy
from mathutils import Vector

OUT = Path(__file__).resolve().parents[2] / 'src' / 'arlq' / 'assets' / 'effects' / 'splash.png'
# The splash's centre (about the player's chest), and its drops: where each
# starts and ends from the centre, and its radius at the root and the head; the droplet's
# distance and radius. All in the plane facing the camera, scaled by SIZE.
CENTER = Vector((0, 0, 0.75))
SIZE = 0.6
DROP_START, DROP_END, ROOT, HEAD = 0.1 * SIZE, 0.5 * SIZE, 0.035 * SIZE, 0.13 * SIZE
DROPLET_AT, DROPLET = 0.8 * SIZE, 0.065 * SIZE
# CI_RED (220, 82, 82) in linear RGB.
RED = tuple((c / 255) ** 2.2 for c in (220, 82, 82))

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 32
scene.cycles.use_denoising = False
scene.view_settings.view_transform = 'Standard'
world = bpy.data.worlds.new('Dim')
world.use_nodes = True
world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.05, 0.05, 0.06, 1)
scene.world = world

# Plain emission renders every pixel of the shape in exactly CI_RED.
mat = bpy.data.materials.new('Splash flat red')
mat.use_nodes = True
nodes = mat.node_tree.nodes
nodes.remove(nodes['Principled BSDF'])
flat = nodes.new('ShaderNodeEmission')
flat.inputs['Color'].default_value = (*RED, 1)
flat.inputs['Strength'].default_value = 1.0
mat.node_tree.links.new(flat.outputs[0], nodes['Material Output'].inputs['Surface'])

# The plane facing the 60-degree camera: screen right, and screen up.
right = Vector((1, 0, 0))
up = Vector((0, math.cos(math.radians(30)), math.sin(math.radians(30))))


def metaball_mesh(name, elements):
    """Melt (position, surface radius) metaballs into one smooth mesh."""
    meta = bpy.data.metaballs.new(name)
    meta.resolution = meta.render_resolution = 0.008 * SIZE
    for co, radius in elements:
        element = meta.elements.new()
        element.co = co
        # The surface lies at roughly 0.6 of each element's radius.
        element.radius = radius / 0.6
    obj = bpy.data.objects.new(name, meta)
    scene.collection.objects.link(obj)
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.convert(target='MESH')
    obj = bpy.context.object
    obj.data.materials.append(mat)
    for poly in obj.data.polygons:
        poly.use_smooth = True


drops, droplets = [], []
for k in range(6):
    angle = math.radians(90 + 60 * k)
    direction = math.cos(angle) * right + math.sin(angle) * up
    # A teardrop: balls growing from fine at the centre to the round head.
    for i in range(12):
        u = i / 11
        drops.append((CENTER + direction * (DROP_START + (DROP_END - DROP_START) * u),
                      ROOT + (HEAD - ROOT) * u ** 2))
    droplets.append((CENTER + direction * DROPLET_AT, DROPLET))
# The droplets are a mesh of their own, so they stay apart from the heads.
metaball_mesh('Splash drops', drops)
metaball_mesh('Splash droplets', droplets)

# The character sprites' camera.
bpy.ops.object.camera_add()
camera = bpy.context.object
target = Vector((0, 0, 0.35))
camera.location = target + Vector((0, -7.5, 15 * math.sin(math.radians(60))))
camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
camera.data.type = 'ORTHO'
camera.data.ortho_scale = 4.6
scene.camera = camera
scene.render.film_transparent = True
scene.render.resolution_x = scene.render.resolution_y = round(256 * 4.6 / 2.6)
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'
scene.render.filepath = str(OUT)
bpy.ops.render.render(write_still=True)

# Crop symmetric about the render centre, as export-sprites.py does.
image = bpy.data.images.load(str(OUT), check_existing=False)
width, height = image.size
pixels = list(image.pixels)
occupied = [(i % width, i // width) for i in range(width * height) if pixels[i * 4 + 3] > 0.01]
left = max(0, min(p[0] for p in occupied) - 2)
right_edge = min(width, max(p[0] for p in occupied) + 3)
bottom = max(0, min(p[1] for p in occupied) - 2)
top = min(height, max(p[1] for p in occupied) + 3)
left = min(left, width - right_edge)
right_edge = width - left
bottom = min(bottom, height - top)
top = height - bottom
trimmed = bpy.data.images.new('splash', right_edge - left, top - bottom, alpha=True)
trimmed.pixels = [value for row in range(bottom, top)
                  for value in pixels[(row * width + left) * 4:(row * width + right_edge) * 4]]
trimmed.filepath_raw = str(OUT)
trimmed.file_format = 'PNG'
trimmed.save()
