"""Export samurai player sprites. Pass -- --part INDEX COUNT to split jobs."""
import math
import sys
from pathlib import Path
import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'rigged-armor'))
from sprite_pose import HEROIC_PLAYER_HEIGHT, HEROIC_PLAYER_SIZE, bake, figure_parts, standing_extent

OUT = ROOT.parents[1] / 'src' / 'arlq' / 'assets' / 'characters'
RATION_OUT = OUT
SAMURAI = ROOT / 'rigged-samurai' / 'hero-rig-chibi.blend'
ARMOR = ROOT / 'rigged-armor' / 'hero-rig-chibi.blend'
SCENE = ROOT / 'heroic' / 'characters-others-angle60.blend'
states = [('player', 'katana'), ('player-sword', 'chimera'),
          ('player-cursed-sword', 'cursed'), ('player-blessed', 'blessed')]
jobs = [(name + ('' if facing == 'down' else '-' + facing), state, facing, 'rest')
        for name, state in states for facing in ('down', 'up', 'left', 'right')]
jobs += [(name + '-' + facing + '-' + pose, state, facing, pose)
         for name, state in states for facing in ('down', 'up', 'left', 'right')
         for pose in ('walk-right', 'walk-left')]
jobs.append(('player-collapsed', 'katana', 'down', 'collapsed'))
args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
if '--part' in args:
    pos = args.index('--part')
    index, count = int(args[pos + 1]), int(args[pos + 2])
    jobs = [job for i, job in enumerate(jobs) if i % count == index]

for name, state, facing, pose in jobs:
    if '--missing' in args and (OUT / ('samurai-' + name + '.png')).is_file():
        continue
    bpy.ops.wm.open_mainfile(filepath=str(SCENE))
    scene = bpy.context.scene
    with bpy.data.libraries.load(str(SAMURAI)) as (available, loaded):
        loaded.objects = list(available.objects)
    rig = next(obj for obj in loaded.objects if obj and obj.type == 'ARMATURE')
    mount = next(obj for obj in loaded.objects if obj and obj.name.startswith('Katana hand mount'))
    kept = [obj for obj in loaded.objects if obj and (obj == rig or obj.parent in (rig, mount))]
    for obj in kept:
        scene.collection.objects.link(obj)
    armor = figure_parts(scene, rig)
    floor, top = standing_extent(scene, rig, armor)
    swords = []
    if state in ('katana', 'blessed') and pose != 'collapsed':
        swords = list(mount.children)
        if state == 'blessed':
            blade = next(obj for obj in swords if obj.name == 'Katana blade')
            glow = blade.data.materials[0].copy()
            shader = glow.node_tree.nodes['Principled BSDF']
            shader.inputs['Base Color'].default_value = (.1, .35, 1, 1)
            shader.inputs['Emission Color'].default_value = (.03, .3, 1, 1)
            shader.inputs['Emission Strength'].default_value = 1.5
            blade.data.materials.clear()
            blade.data.materials.append(glow)
    elif state in ('chimera', 'cursed'):
        prefix = 'Chimera sword ' if state == 'chimera' else 'Cursed sword '
        with bpy.data.libraries.load(str(ARMOR)) as (available, loaded_sword):
            loaded_sword.objects = [n for n in available.objects if n.startswith(prefix)]
        for obj in loaded_sword.objects:
            inverse, basis = obj.matrix_parent_inverse.copy(), obj.matrix_basis.copy()
            scene.collection.objects.link(obj)
            obj.parent, obj.parent_type, obj.parent_bone = rig, 'BONE', 'hand.R'
            obj.matrix_parent_inverse, obj.matrix_basis = inverse, basis
            obj.hide_render = obj.hide_viewport = False
        swords = loaded_sword.objects
    scale = HEROIC_PLAYER_SIZE * HEROIC_PLAYER_HEIGHT / (top - floor)
    place = Matrix.Scale(scale, 4) @ Matrix.Translation((0, 0, -floor))
    selected = set(bake(scene, rig, armor + swords, pose, facing, floor, place))
    x = y = 0
    name = 'samurai-' + name
    char = '@'
    for obj in scene.objects:
        obj.hide_render = obj not in selected and obj.type not in ('LIGHT', 'CAMERA')
    camera = scene.camera
    # The lights are aimed at the scene origin; move them with the
    # character so every sprite is lit the same way wherever it stands.
    for light in (obj for obj in scene.objects if obj.type == 'LIGHT'):
        light.location += Vector((x, y, 0))
    target = Vector((x, y, 0.35))
    camera.location = target + Vector((0, -7.5, 15 * math.sin(math.radians(60))))
    camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
    # Same 256 px per 2.6 units for every sprite, on a canvas large enough for
    # the biggest model; the model's size alone decides the trimmed image size.
    camera.data.ortho_scale = 4.6
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
    # Bold outer contour; thinner, softer lines between overlapping parts.
    lines.select_silhouette = lines.select_border = False
    inner = settings.linesets.new('Inner parts')
    inner.select_silhouette = inner.select_border = True
    inner.select_external_contour = inner.select_crease = False
    inner.linestyle = bpy.data.linestyles.new('Thin ink')
    inner.linestyle.color = (0.04, 0.05, 0.07)
    inner.linestyle.thickness = 1.5
    inner.linestyle.alpha = 0.7
    scene.cycles.samples = 64
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    # The Stage 6 emergency rations go in their own directory.
    path = (RATION_OUT if char.startswith('ration-') else OUT) / (name + '.png')
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
