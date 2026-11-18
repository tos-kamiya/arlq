"""Render the chibi samurai with the armor sprite camera and pose adjustments.

Run after build-chibi.py. Pass -- --facings --chimera --cursed --collapsed
to write the complete preview-player-facings.jpg. The two sword variants
come from rigged-armor/hero-rig-chibi.blend.
"""

import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'rigged-armor'))

from sprite_pose import apply_walk_pose, bake, figure_parts, standing_extent


def load_armor_sword(rig, prefix):
    source = HERE.parent / 'rigged-armor' / 'hero-rig-chibi.blend'
    with bpy.data.libraries.load(str(source)) as (available, loaded):
        loaded.objects = [name for name in available.objects if name.startswith(prefix)]
    if not loaded.objects:
        raise ValueError(f'{prefix.strip()} missing from {source}')
    for part in loaded.objects:
        inverse = part.matrix_parent_inverse.copy()
        basis = part.matrix_basis.copy()
        bpy.context.collection.objects.link(part)
        part.parent = rig
        part.parent_type = 'BONE'
        part.parent_bone = 'hand.R'
        part.matrix_parent_inverse = inverse
        part.matrix_basis = basis
        part.hide_render = False
        part.hide_viewport = False
    return loaded.objects


def render_facings(scene, rig, katana, armor, floor, with_chimera, with_cursed, collapsed):
    katana_parts = [obj for obj in katana.children if not obj.hide_render]
    rows = [('KATANA', 0, katana_parts)]
    if with_chimera:
        rows.append(('CHIMERA SWORD (c)', -1.6, load_armor_sword(rig, 'Chimera sword ')))
    if with_cursed:
        rows.append(('CURSED SWORD (C)', -1.6 * len(rows), load_armor_sword(rig, 'Cursed sword ')))
    bpy.data.objects['Studio floor'].location.z = floor - .002
    for light in (obj for obj in scene.objects if obj.type == 'LIGHT'):
        distance = light.location.length
        sun = bpy.data.lights.new(light.name + ' sun', 'SUN')
        sun.energy = light.data.energy / (math.pi * distance ** 2)
        sun.angle = 2 * math.atan(light.data.size / (2 * distance))
        sun.color = light.data.color
        light.data = sun

    camera = scene.camera
    last_y = -1.6 * (len(rows) - 1 + collapsed)
    expanded = last_y < 0
    target = Vector((-.45, .04 + last_y / 2, .54) if expanded else (0, .04, .54))
    camera.location = target + Vector((0, -5, 5 * math.sqrt(3)))
    camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera.data.ortho_scale = 8.35 if expanded else 7.4
    scene.render.resolution_x = 1600 if expanded else 1500
    scene.render.resolution_y = 400 - round(last_y * 158)
    scene.render.image_settings.file_format = 'JPEG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.image_settings.quality = 90

    ink = bpy.data.materials.new('Facing labels')
    ink.use_nodes = True
    nodes = ink.node_tree.nodes
    emission = nodes.new('ShaderNodeEmission')
    emission.inputs['Color'].default_value = (.75, .8, .9, 1)
    ink.node_tree.links.new(emission.outputs[0], nodes['Material Output'].inputs['Surface'])
    screen_rotation = camera.rotation_euler.to_quaternion()
    def label_on_screen(label, x, y, size=.095):
        font = bpy.data.curves.new(label, 'FONT')
        font.body = label
        font.align_x = 'CENTER'
        font.size = size
        font.materials.append(ink)
        text = bpy.data.objects.new(label, font)
        scene.collection.objects.link(text)
        text.location = camera.location + screen_rotation @ Vector((x, y, -8.4))
        text.rotation_euler = camera.rotation_euler

    columns = (
        ('down', 'rest', 'DOWN', -2.81),
        ('left', 'rest', 'LEFT', -1.55),
        ('right', 'rest', 'RIGHT', -.29),
        ('up', 'rest', 'UP', .97),
        ('down', 'walk-right', 'DOWN / RIGHT FOOT', 2.65),
    )
    for _, _, label, x in columns:
        label_on_screen(label, x - target.x, .70 - last_y * math.sqrt(3) / 4)

    for row_label, y, sword in rows:
        if expanded:
            label_on_screen(row_label, -3.55, (.8 * -last_y / 2 + y) * math.sqrt(3) / 2, .083)
        for facing, pose, _, x in columns:
            if pose == 'walk-right' and sword is katana_parts:
                # Recompute the blade roll for the gait, which uses the rest frame.
                rig.rotation_euler.z = 0
                scene.frame_set(1)
                apply_walk_pose(rig, 'R')
                bpy.context.view_layer.update()
                undo_roll = Matrix.Rotation(-katana.rotation_euler.x, 3, 'X')
                unrolled = katana.matrix_world.to_3x3() @ undo_roll
                forward = unrolled.inverted() @ Vector((0, -1, 0))
                katana.rotation_euler.x = math.atan2(forward.z, forward.y)
                katana.keyframe_insert(data_path='rotation_euler', index=0, frame=1)
            bake(scene, rig, armor + sword, pose, facing, floor,
                 place=Matrix.Translation((x, y, 0)))

    if collapsed:
        bake(scene, rig, armor, 'collapsed', 'down', floor,
             place=Matrix.Translation((columns[0][3], last_y, 0)))
        label_on_screen('COLLAPSED (HUNGER)', -3.55,
                        (.8 * -last_y / 2 + last_y) * math.sqrt(3) / 2, .083)

    for part in armor:
        part.hide_render = True
    for _, _, sword in rows:
        for part in sword:
            part.hide_render = True
    name = 'preview-player-facings-with-chimera.jpg' if with_chimera else 'preview-player-facings-katana.jpg'
    if collapsed:
        name = 'preview-player-facings-with-collapsed.jpg'
    if with_cursed:
        name = 'preview-player-facings.jpg'
    scene.render.filepath = str(HERE / name)
    bpy.ops.render.render(write_still=True)


def main():
    source = HERE / 'hero-rig-chibi.blend'
    bpy.ops.wm.open_mainfile(filepath=str(source))
    scene = bpy.context.scene
    rig = bpy.data.objects['Hero rig']
    katana = bpy.data.objects['Katana hand mount']
    armor = figure_parts(scene, rig)
    parts = armor + [obj for obj in katana.children if not obj.hide_render]
    floor, _ = standing_extent(scene, rig, armor)
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    if '--facings' in args:
        render_facings(scene, rig, katana, armor, floor, '--chimera' in args,
                       '--cursed' in args, '--collapsed' in args)
        return

    target = Vector((0, .05, .5))
    angle = math.radians(60)
    camera = scene.camera
    camera.location = target + Vector((0, -10 * math.cos(angle), 10 * math.sin(angle)))
    camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera.data.ortho_scale = 1.75
    scene.render.resolution_x = scene.render.resolution_y = 400
    scene.render.film_transparent = True
    scene.render.image_settings.color_mode = 'RGBA'
    bpy.data.objects['Studio floor'].hide_render = True

    scene.render.filepath = str(HERE / 'sprite-upright-down.png')
    bpy.ops.render.render(write_still=True)
    for pose in ('rest', 'step'):
        copies = bake(scene, rig, parts, pose, 'down', floor)
        for part in parts:
            part.hide_render = True
        scene.render.filepath = str(HERE / f'sprite-{pose}-down.png')
        bpy.ops.render.render(write_still=True)
        for obj in copies:
            mesh = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            bpy.data.meshes.remove(mesh)
        for part in parts:
            part.hide_render = False


if __name__ == '__main__':
    main()
