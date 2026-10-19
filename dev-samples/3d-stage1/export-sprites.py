"""Export accepted characters as cropped transparent 60-degree PNGs.

With `-- --heroic`, export the refined models built by build-heroic.py.
`-- --heroic --only n o` re-exports just the listed characters.
"""
from pathlib import Path
import math
import shutil
import sys
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parents[1] / 'src' / 'arlq' / 'assets' / 'characters'
OUT.mkdir(parents=True, exist_ok=True)
models = [('a', 'amoeba', (-2, 1.5)), ('A', 'rare-amoeba', (2, 1.5)),
          ('b', 'bison', (-2, -1.5)), ('d', 'comodo-dragon', (2, -1.5)),
          ('@', 'player', (0, 0))]
HEROIC = '--heroic' in sys.argv
if HEROIC:
    models += [('c', 'chimera', (0, 0)), ('T', 'treasure', (0, 0)),
               ('D', 'dragon', (0, 0)), ('l', 'loop-watch', (0, 0)), ('n', 'nomicon', (0, 0)), ('o', 'ocular', (0, 0)),
               ('C', 'rare-chimera', (0, 0)), ('F', 'fire-drake', (0, 0)),
               ("'", 'mark-rank2', (0, 0)), ('"', 'mark-rank3', (0, 0)),
               ('g', 'golem', (0, 0)), ('m', 'spore', (0, 0)), ('k', 'marksman', (0, 0)), ('e', 'erebus', (0, 0)), ('E', 'rare-erebus', (0, 0)),
               ('X', 'caltrop-plant', (0, 0)), ('p', 'pegasus', (0, 0)),
               ('H', 'high-elf', (0, 0)), ('I', 'isolated-elf', (0, 0)),
               ('J', 'javelin-elf', (0, 0)), ('K', 'collector-elf', (0, 0)),
               ('L', 'lifebringer-elf', (0, 0)), ('S', 'sylvan-elf', (0, 0)),
               ('rock', 'golem-rock', (0, 0))]
if '--only' in sys.argv:
    only = sys.argv[sys.argv.index('--only') + 1:]
    models = [model for model in models if model[0] in only]
for char, name, (x, y) in models:
    player = char == '@'
    source = ROOT / ('heroic/characters-angle60.blend' if HEROIC else
                     'player-arms/player-angle60.blend' if player else
                     'attached-cones/stage1-characters-angle60.blend')
    bpy.ops.wm.open_mainfile(filepath=str(source))
    scene = bpy.context.scene
    if HEROIC:
        x, y = scene['sprite_centers'][char]
        selected = {obj for obj in scene.objects if obj.get('sprite')}
        selected = {obj for obj in selected if obj.users_collection[0].name.startswith(
            'Character ' + char + ' ')}
    elif player:
        selected = {obj for obj in scene.objects if obj.name.startswith('Player')}
    else:
        selected = set(next(c for c in bpy.data.collections
                            if c.name.startswith('Prototype ' + char + ' ')).objects)
        selected = {obj for obj in selected if 'tile' not in obj.name and
                    not obj.name.startswith('Label ')}
    for obj in scene.objects:
        obj.hide_render = obj not in selected and obj.type not in ('LIGHT', 'CAMERA')
    camera = scene.camera
    if HEROIC:
        # The lights are aimed at the scene origin; move them with the
        # character so every sprite is lit the same way wherever it stands.
        for light in (obj for obj in scene.objects if obj.type == 'LIGHT'):
            light.location += Vector((x, y, 0))
    target = Vector((x, y, 0.35))
    camera.location = target + Vector((0, -7.5, 15 * math.sin(math.radians(60))))
    camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
    # Same 256 px per 2.6 units for every sprite, on a canvas large enough for
    # the biggest model; the model's size alone decides the trimmed image size.
    camera.data.ortho_scale = 4.6 if HEROIC else 2.6
    scene.render.film_transparent = True
    scene.render.resolution_x = scene.render.resolution_y = round(
        256 * camera.data.ortho_scale / 2.6)
    scene.cycles.samples = 64
    # Add ink contours over the existing Cycles shading; leave materials intact.
    scene.render.use_freestyle = True
    settings = scene.view_layers[0].freestyle_settings
    lines = settings.linesets[0] if settings.linesets else settings.linesets.new('Outline')
    lines.select_silhouette = True
    lines.select_border = True
    lines.select_external_contour = True
    lines.select_crease = False
    if lines.linestyle is None:
        lines.linestyle = bpy.data.linestyles.new('Ink outline')
    lines.linestyle.color = (0.015, 0.02, 0.03)
    lines.linestyle.thickness = 4.0
    if HEROIC:
        # Bold outer contour; thinner, softer lines between overlapping parts.
        lines.select_silhouette = lines.select_border = False
        inner = settings.linesets.new('Inner parts')
        inner.select_silhouette = inner.select_border = True
        inner.select_external_contour = inner.select_crease = False
        inner.linestyle = bpy.data.linestyles.new('Thin ink')
        inner.linestyle.color = (0.04, 0.05, 0.07)
        inner.linestyle.thickness = 1.5
        inner.linestyle.alpha = 0.7
        scene.cycles.samples = 256
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    path = OUT / (name + '.png')
    comparison = ROOT / ('sprites-before-heroic' if HEROIC else 'sprites-before-outline')
    comparison.mkdir(exist_ok=True)
    before = comparison / path.name
    # Comparison copies are only for the five characters that had earlier sprites.
    if path.exists() and not before.exists() and char in '@aAbd':
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
    # Keep the crop symmetric about the render centre, so the camera target
    # (0.35 above the model's ground origin) stays at the image centre and the
    # GUI can find each character's feet at one fixed offset.
    left = min(left, width - right)
    right = width - left
    bottom = min(bottom, height - top)
    top = height - bottom
    trimmed = bpy.data.images.new(name, right - left, top - bottom, alpha=True)
    trimmed.pixels = [value for row in range(bottom, top)
                      for value in pixels[(row * width + left) * 4:(row * width + right) * 4]]
    trimmed.filepath_raw = str(path)
    trimmed.file_format = 'PNG'
    trimmed.save()
