"""Export accepted characters as cropped transparent 60-degree PNGs."""
from pathlib import Path
import math
import shutil
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parents[1] / 'src' / 'arlq' / 'assets' / 'characters'
OUT.mkdir(parents=True, exist_ok=True)
models = [('a', 'amoeba', (-2, 1.5)), ('A', 'rare-amoeba', (2, 1.5)),
          ('b', 'bison', (-2, -1.5)), ('d', 'comodo-dragon', (2, -1.5)),
          ('@', 'player', (0, 0))]
for char, name, (x, y) in models:
    player = char == '@'
    source = ROOT / ('player-arms/player-angle60.blend' if player else
                     'attached-cones/stage1-characters-angle60.blend')
    bpy.ops.wm.open_mainfile(filepath=str(source))
    scene = bpy.context.scene
    if player:
        selected = {obj for obj in scene.objects if obj.name.startswith('Player')}
    else:
        selected = set(next(c for c in bpy.data.collections
                            if c.name.startswith('Prototype ' + char + ' ')).objects)
        selected = {obj for obj in selected if 'tile' not in obj.name and
                    not obj.name.startswith('Label ')}
    for obj in scene.objects:
        obj.hide_render = obj not in selected and obj.type not in ('LIGHT', 'CAMERA')
    camera = scene.camera
    target = Vector((x, y, 0.35))
    camera.location = target + Vector((0, -7.5, 15 * math.sin(math.radians(60))))
    camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera.data.ortho_scale = 2.6
    scene.render.film_transparent = True
    scene.render.resolution_x = scene.render.resolution_y = 256
    scene.cycles.samples = 64
    # Add ink contours over the existing Cycles shading; leave materials intact.
    scene.render.use_freestyle = True
    settings = scene.view_layers[0].freestyle_settings
    lines = settings.linesets[0]
    lines.select_silhouette = True
    lines.select_border = True
    lines.select_external_contour = True
    lines.select_crease = False
    lines.linestyle.color = (0.015, 0.02, 0.03)
    lines.linestyle.thickness = 4.0
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    path = OUT / (name + '.png')
    comparison = ROOT / 'sprites-before-outline'
    comparison.mkdir(exist_ok=True)
    before = comparison / path.name
    if path.exists() and not before.exists():
        shutil.copy2(path, before)
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    # Trim empty space using Blender itself; no extra imaging dependency.
    image = bpy.data.images.load(str(path), check_existing=False)
    width, height = image.size
    pixels = list(image.pixels)
    occupied = [(i % width, i // width) for i in range(width * height)
                if pixels[i * 4 + 3] > 0.01]
    left = max(0, min(p[0] for p in occupied) - 2)
    right = min(width, max(p[0] for p in occupied) + 3)
    bottom = max(0, min(p[1] for p in occupied) - 2)
    top = min(height, max(p[1] for p in occupied) + 3)
    trimmed = bpy.data.images.new(name, right - left, top - bottom, alpha=True)
    trimmed.pixels = [value for row in range(bottom, top)
                      for value in pixels[(row * width + left) * 4:(row * width + right) * 4]]
    trimmed.filepath_raw = str(path)
    trimmed.file_format = 'PNG'
    trimmed.save()
