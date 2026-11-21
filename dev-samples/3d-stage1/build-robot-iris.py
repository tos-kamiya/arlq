"""Standalone renders of Iris, the talkative Stage 6 robot (robot_iris.py).

blender --factory-startup --background --threads 4 --python dev-samples/3d-stage1/build-robot-iris.py

Builds the model alone in a studio lit like the heroic scenes, saves
robot-iris/robot-iris.blend, and renders every expression with the sprite
camera (export-sprites.py: 60-degree orthographic view, 256 px per 2.6
units, Freestyle ink) to robot-iris/expr/iris-<expression>.png and straight
from the front to robot-iris/expr/face-<expression>.png, then the neutral
robot-iris/iris.png and close-ups robot-iris/closeup.png (sprite angle),
robot-iris/closeup-side.png (three-quarter view from the side) and
robot-iris/closeup-front.png (straight from the front).
The game sprites come from the members' heroic scene instead (build-heroic.py,
export-sprites.py).
"""
from pathlib import Path
import math
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import robot_iris
from robot_iris import EXPRESSIONS, FACE_HEIGHT, HOVER_Z, show_expression

OUT = Path(__file__).resolve().parent / 'robot-iris'
OUT.mkdir(parents=True, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 128
scene.cycles.use_denoising = False
scene.cycles.sample_clamp_indirect = 2.0
scene.cycles.blur_glossy = 1.0
scene.cycles.caustics_reflective = False
scene.cycles.caustics_refractive = False
scene.view_settings.view_transform = 'Standard'
scene.view_settings.look = 'Medium High Contrast'
world = bpy.data.worlds.new('Night studio')
world.use_nodes = True
world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.012, 0.018, 0.03, 1)
scene.world = world

body_col = bpy.data.collections.new('Iris body')
glow_col = bpy.data.collections.new('Iris glow')
scene.collection.children.link(body_col)
scene.collection.children.link(glow_col)
iris = robot_iris.build(0, 0, body_col, glow_col)

# Lights and camera as in the heroic scenes and export-sprites.py.
for name, pos, power, size, color in [
        ('Key', (-4, -6, 8), 1000, 5, (1.0, 0.93, 0.85)),
        ('Fill', (6, -3, 4), 250, 6, (0.6, 0.75, 1.0)),
        ('Rim left', (-7, 6, 4), 1300, 3, (0.55, 0.8, 1.0)),
        ('Rim right', (7, 6, 4), 1300, 3, (1.0, 0.7, 0.9))]:
    bpy.ops.object.light_add(type='AREA', location=pos)
    light = bpy.context.object
    light.name = name
    light.data.energy = power
    light.data.size = size
    light.data.color = color
    light.data.shape = 'DISK'
    light.rotation_euler = (Vector((0, 0, 0)) - light.location).to_track_quat('-Z', 'Y').to_euler()
bpy.ops.object.camera_add()
camera = bpy.context.object
scene.camera = camera
camera.data.type = 'ORTHO'
scene.render.film_transparent = True
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'

# Ink contours as in export-sprites.py, on the body only: the glowing eyes
# and ring stay unoutlined light.
scene.render.use_freestyle = True
settings = scene.view_layers[0].freestyle_settings
outline = settings.linesets[0] if settings.linesets else settings.linesets.new('Outline')
outline.linestyle = outline.linestyle or bpy.data.linestyles.new('Ink outline')
outline.select_silhouette = outline.select_border = False
outline.select_external_contour = True
outline.select_crease = False
outline.linestyle.color = (0.015, 0.02, 0.03)
outline.linestyle.thickness = 4.0
inner = settings.linesets.new('Inner parts')
inner.select_silhouette = inner.select_border = True
inner.select_external_contour = inner.select_crease = False
inner.linestyle = bpy.data.linestyles.new('Thin ink')
inner.linestyle.color = (0.04, 0.05, 0.07)
inner.linestyle.thickness = 1.5
inner.linestyle.alpha = 0.7
for lines in (outline, inner):
    lines.select_by_collection = True
    lines.collection = body_col


def frame(target_z, ortho, pixels):
    target = Vector((0, 0, target_z))
    camera.location = target + Vector((0, -7.5, 15 * math.sin(math.radians(60))))
    camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera.data.ortho_scale = ortho
    scene.render.resolution_x = scene.render.resolution_y = pixels


def trim(path):
    """Crop transparent margins symmetrically, as export-sprites.py does."""
    image = bpy.data.images.load(str(path), check_existing=False)
    width, height = image.size
    pixels = list(image.pixels)
    occupied = [(i % width, i // width) for i in range(width * height)
                if pixels[i * 4 + 3] > 0.01]
    left = max(0, min(p[0] for p in occupied) - 2)
    right = min(width, max(p[0] for p in occupied) + 3)
    bottom = max(0, min(p[1] for p in occupied) - 2)
    top = min(height, max(p[1] for p in occupied) + 3)
    left = min(left, width - right)
    right = width - left
    bottom = min(bottom, height - top)
    top = height - bottom
    trimmed = bpy.data.images.new(path.stem, right - left, top - bottom, alpha=True)
    trimmed.pixels = [value for row in range(bottom, top)
                      for value in pixels[(row * width + left) * 4:(row * width + right) * 4]]
    trimmed.filepath_raw = str(path)
    trimmed.file_format = 'PNG'
    trimmed.save()


def front_camera(target, ortho):
    """Straight from the front, nearly level, to check the face."""
    pitch = math.radians(8)
    camera.location = target + 10 * Vector((0, -math.cos(pitch), math.sin(pitch)))
    camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera.data.ortho_scale = ortho


# Every expression with the sprite camera (expr/iris-<name>.png, trimmed like
# the game sprites) and its face straight from the front
# (expr/face-<name>.png).
EXPR_OUT = OUT / 'expr'
EXPR_OUT.mkdir(exist_ok=True)
face = Vector((0, 0, FACE_HEIGHT - 0.02))
for name in EXPRESSIONS:
    show_expression(iris, name)
    frame(0.35, 4.6, round(256 * 4.6 / 2.6))
    path = EXPR_OUT / f'iris-{name}.png'
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    trim(path)
    front_camera(face, 0.8)
    scene.render.resolution_x = scene.render.resolution_y = 480
    scene.render.filepath = str(EXPR_OUT / f'face-{name}.png')
    bpy.ops.render.render(write_still=True)
show_expression(iris, 'neutral')

bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'robot-iris.blend'))
frame(0.35, 4.6, round(256 * 4.6 / 2.6))
path = OUT / 'iris.png'
scene.render.filepath = str(path)
bpy.ops.render.render(write_still=True)
trim(path)
frame(HOVER_Z + 0.25, 1.1, 900)
scene.render.filepath = str(OUT / 'closeup.png')
bpy.ops.render.render(write_still=True)
# A three-quarter close-up from lower and to the side (screen right), to
# check the eyes' float, the arms and the hover ring in depth.
target = Vector((0, 0, HOVER_Z + 0.25))
yaw, pitch = math.radians(40), math.radians(20)
camera.location = target + 10 * Vector((math.sin(yaw) * math.cos(pitch),
                                        -math.cos(yaw) * math.cos(pitch), math.sin(pitch)))
camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
camera.data.ortho_scale = 1.1
scene.render.filepath = str(OUT / 'closeup-side.png')
bpy.ops.render.render(write_still=True)
# Straight from the front, nearly level, to check the face (the eyes).
yaw, pitch = 0.0, math.radians(8)
camera.location = target + 10 * Vector((math.sin(yaw) * math.cos(pitch),
                                        -math.cos(yaw) * math.cos(pitch), math.sin(pitch)))
camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
scene.render.filepath = str(OUT / 'closeup-front.png')
bpy.ops.render.render(write_still=True)
