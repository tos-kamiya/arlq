"""Trial sprite of a sword slash: a crescent of light cutting across a monster.

Picture an upright cylinder around the monster cut by a slanted plane. The
crescent lies flat in that plane: its outer edge is the far half of the
cut's ellipse, from the monster's left shoulder (screen upper right) around
its back to its right hip (screen lower left), bulging upward on the screen.
Seen from above with the far side at 12 o'clock, the crescent's ends are at
2:30 and 8:30, the plane rising toward 2:30;
its inner edge is the same curve drawn in toward the ellipse's centre, so
the crescent is pointed at both ends and widest in the middle. Its light is
the blue of a beatable monster's ground disc (CI_BLUE), palest along the
outer edge and fading out toward the inner one.

Rendered with the character sprites' camera (60 degrees down, 256 px per
2.6 units, crop symmetric about 0.35 above the ground origin), so the GUI
can place it on the monster's cell like a character sprite, drawn
additively. The colors are baked into the image.

    blender --background --threads 4 --python dev-samples/3d-stage1/build-slash.py

Writes heroic/effect-slash.png.
"""
from pathlib import Path
import math

import bpy
from mathutils import Vector

OUT = Path(__file__).resolve().parent / 'heroic' / 'effect-slash.png'
# The cylinder's radius; the cut's height at the centre, and how far it
# rises toward 2:30 (seen from above, the far side at 12) and falls
# toward 8:30, where the crescent ends.
# The cut spans about 1.5 times a monster's width and slants gently.
RADIUS = 1.0
# The cylinder's axis stands this far in front of the monster, toward the
# player, so the far half of the cut does not reach far behind the monster.
NEAR = 0.6
MIDDLE = 0.8
RISE = 0.4
END_ANGLE = math.radians(15)  # 2:30, counterclockwise from screen right
# The crescent's widest part as a fraction of the radius, and the mesh
# resolution along and across it.
WIDTH = 0.35
STEPS, ACROSS = 128, 12
# CI_BLUE (92, 154, 224) in linear RGB, and the pale blue of the outer edge, kept dim so that added over a bright monster the blue is not
# washed out toward white.
BLUE = tuple((c / 255) ** 2.2 for c in (92, 154, 224))
CORE = (0.3, 0.55, 1.0)
STRENGTH = 0.85

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 64
scene.cycles.use_denoising = False
scene.view_settings.view_transform = 'Standard'
world = bpy.data.worlds.new('Black')
world.color = (0, 0, 0)
scene.world = world


def path(t):
    """The cut's far half: t = 0 at 2:30 (high), 1 at 8:30 (low)."""
    angle = END_ANGLE + math.pi * t
    return Vector((RADIUS * math.cos(angle), RADIUS * math.sin(angle) - NEAR,
                   MIDDLE + RISE * math.cos(angle - END_ANGLE)))


vertices, uvs, faces = [], [], []
centre = Vector((0, -NEAR, MIDDLE))
for i in range(STEPS + 1):
    t = i / STEPS
    outer = path(t)
    # Drawing in toward the centre keeps the inner edge in the cut's plane.
    width = WIDTH * math.sin(math.pi * t) ** 0.8
    for j in range(ACROSS + 1):
        v = j / ACROSS  # 0 on the inner edge, 1 on the outer edge
        vertices.append(centre + (outer - centre) * (1 - width * (1 - v)))
        uvs.append((t, v))
for i in range(STEPS):
    for j in range(ACROSS):
        a = i * (ACROSS + 1) + j
        b = a + ACROSS + 1
        faces.append((a, b, b + 1, a + 1))
mesh = bpy.data.meshes.new('Slash')
mesh.from_pydata([tuple(v) for v in vertices], [], faces)
layer = mesh.uv_layers.new(name='UV')
for poly in mesh.polygons:
    for loop in poly.loop_indices:
        layer.data[loop].uv = uvs[mesh.loops[loop].vertex_index]
obj = bpy.data.objects.new('Slash', mesh)
scene.collection.objects.link(obj)

# Light only: pale blue along the outer edge, turning blue and fading out
# toward the inner edge.
mat = bpy.data.materials.new('Slash light')
mat.use_nodes = True
nodes, links = mat.node_tree.nodes, mat.node_tree.links
nodes.remove(nodes['Principled BSDF'])
uv = nodes.new('ShaderNodeUVMap')
split = nodes.new('ShaderNodeSeparateXYZ')
links.new(uv.outputs['UV'], split.inputs[0])
tint = nodes.new('ShaderNodeValToRGB')
tint.color_ramp.elements[0].position = 0.4
tint.color_ramp.elements[0].color = (*BLUE, 1)
tint.color_ramp.elements[1].position = 0.95
tint.color_ramp.elements[1].color = (*CORE, 1)
links.new(split.outputs['Y'], tint.inputs['Fac'])
opacity = nodes.new('ShaderNodeValToRGB')
elements = opacity.color_ramp.elements
elements.new(0.5)
for element, (position, value) in zip(elements, [(0.0, 0.15), (0.5, 0.65), (1.0, 1.0)]):
    element.position = position
    element.color = (value, value, value, 1)
opacity.color_ramp.interpolation = 'EASE'
links.new(split.outputs['Y'], opacity.inputs['Fac'])
emission = nodes.new('ShaderNodeEmission')
emission.inputs['Strength'].default_value = STRENGTH
links.new(tint.outputs['Color'], emission.inputs['Color'])
transparent = nodes.new('ShaderNodeBsdfTransparent')
mix = nodes.new('ShaderNodeMixShader')
links.new(opacity.outputs['Color'], mix.inputs['Fac'])
links.new(transparent.outputs[0], mix.inputs[1])
links.new(emission.outputs[0], mix.inputs[2])
links.new(mix.outputs[0], nodes['Material Output'].inputs['Surface'])
obj.data.materials.append(mat)

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
right = min(width, max(p[0] for p in occupied) + 3)
bottom = max(0, min(p[1] for p in occupied) - 2)
top = min(height, max(p[1] for p in occupied) + 3)
left = min(left, width - right)
right = width - left
bottom = min(bottom, height - top)
top = height - bottom
trimmed = bpy.data.images.new('slash', right - left, top - bottom, alpha=True)
trimmed.pixels = [value for row in range(bottom, top)
                  for value in pixels[(row * width + left) * 4:(row * width + right) * 4]]
trimmed.filepath_raw = str(OUT)
trimmed.file_format = 'PNG'
trimmed.save()
