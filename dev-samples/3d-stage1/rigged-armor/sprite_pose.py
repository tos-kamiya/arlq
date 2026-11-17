"""Pose the low head-to-body rig as a top-down sprite figure.

Shared by render-chibi-sprites.py (previews of the rig on its own) and
../build-heroic.py (the player in the heroic scenes the game sprites are
exported from). For a sample pose and facing the figure is turned about its
feet, then the whole body leans back a little about the feet and the head
tilts back further at the neck, so the face reads from the 60-degree camera.
Both are rigid turns about the screen's horizontal axis, applied to baked
copies of the evaluated meshes, so the rig itself is left unchanged. The
collapsed pose is laid out by the rig (head toward screen lower right) and
baked unleaned and without a sword.
"""
import math
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
CHIBI_BLEND = HERE / 'hero-rig-chibi.blend'
BODY_LEAN, HEAD_TILT = 0.1, 0.3    # radians, back from the camera
FACINGS = {'down': 0, 'left': -90, 'right': 90, 'up': 180}    # turn in degrees
POSE_FRAMES = {'rest': 1, 'guard': 40, 'step': 80, 'collapsed': 120}
# The sword in the right hand: the parts whose names start with each prefix.
SWORDS = {'own': 'Sword ', 'chimera': 'Chimera sword ', 'cursed': 'Cursed sword ',
          'blessed': 'Blessed sword '}


def show_sword(objects, sword):
    """Show the named sword's parts and hide the others (None hides all)."""
    for obj in objects:
        for name, prefix in SWORDS.items():
            if obj.name.startswith(prefix):
                obj.hide_render = obj.hide_viewport = name != sword


def figure_parts(scene, rig):
    """The rig's mesh parts that render: armor, cape and the shown sword."""
    return [o for o in scene.objects if o.type == 'MESH' and o.parent == rig and not o.hide_render]


def standing_extent(scene, rig, parts):
    """Lowest and highest points of the standing figure (rest pose, no sword)."""
    scene.frame_set(POSE_FRAMES['rest'])
    rig.rotation_euler.z = 0
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    heights = []
    for part in parts:
        if part.name.startswith(tuple(SWORDS.values())):
            continue
        evaluated = part.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        heights += [(evaluated.matrix_world @ v.co).z for v in mesh.vertices]
        evaluated.to_mesh_clear()
    return min(heights), max(heights)


def bake(scene, rig, parts, pose, facing, floor, place=Matrix.Identity(4)):
    """Baked mesh copies of the posed, turned and leaned figure, each with its
    world shape in its mesh, transformed by `place` (applied last)."""
    collapsed = pose == 'collapsed'
    rig.rotation_euler.z = 0 if collapsed else math.radians(FACINGS[facing])
    scene.frame_set(POSE_FRAMES[pose])
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    feet = Vector((0, 0, floor))
    body = (Matrix.Identity(4) if collapsed else
            Matrix.Translation(feet) @ Matrix.Rotation(-BODY_LEAN, 4, 'X') @ Matrix.Translation(-feet))
    neck = body @ (rig.matrix_world @ rig.pose.bones['head'].head)
    head = body if collapsed else (Matrix.Translation(neck) @ Matrix.Rotation(-HEAD_TILT, 4, 'X')
                                   @ Matrix.Translation(-neck) @ body)
    copies, still = [], {}
    for part in parts:
        if collapsed and part.name.startswith(tuple(SWORDS.values())):
            continue
        evaluated = part.evaluated_get(depsgraph)
        mesh = bpy.data.meshes.new_from_object(evaluated, preserve_all_data_layers=True,
                                               depsgraph=depsgraph)
        on_head = part.parent_type == 'BONE' and part.parent_bone == 'head'
        mesh.transform(place @ (head if on_head else body) @ evaluated.matrix_world)
        # Materials keyed per pose (the visor dims while collapsed) are
        # replaced with still copies holding this pose's values, so the
        # copies look the same rendered at any frame.
        for index, material in enumerate(mesh.materials):
            if material and material.node_tree and material.node_tree.animation_data:
                if material.name not in still:
                    still[material.name] = material.copy()
                    still[material.name].node_tree.animation_data_clear()
                mesh.materials[index] = still[material.name]
        copy = bpy.data.objects.new(part.name + ' sprite', mesh)
        scene.collection.objects.link(copy)
        copies.append(copy)
    return copies


# Height of the heroic player before its sprite size (SIZES['@'] in
# ../build-heroic.py) is applied; the chibi figure is scaled to it, so it
# fills a game cell as the previous player model did.
HEROIC_PLAYER_HEIGHT = 1.33
# The heroic scenes' sword states.
HEROIC_SWORDS = {None: 'own', 'c': 'chimera', 'C': 'cursed', 'blessed': 'blessed'}


def heroic_player(x, y, sword=None, facing='down', collapsed=False):
    """Build the player for ../build-heroic.py: bring in the chibi rig, pose
    it, bake the sprite figure standing on the floor at (x, y) at the heroic
    player's height, and remove the rig again."""
    scene = bpy.context.scene
    with bpy.data.libraries.load(str(CHIBI_BLEND)) as (source, loaded):
        loaded.objects = list(source.objects)
    rig = next(o for o in loaded.objects if o.type == 'ARMATURE')
    kept = [o for o in loaded.objects if o is rig or o.parent == rig
            or o.name.startswith('Cape drape target')]
    for obj in kept:
        scene.collection.objects.link(obj)
    show_sword(kept, None if collapsed else HEROIC_SWORDS[sword])
    parts = figure_parts(scene, rig)
    floor, top = standing_extent(scene, rig, parts)
    scale = HEROIC_PLAYER_HEIGHT / (top - floor)
    place = (Matrix.Translation((x, y, 0)) @ Matrix.Scale(scale, 4)
             @ Matrix.Translation((0, 0, -floor)))
    copies = bake(scene, rig, parts, 'collapsed' if collapsed else 'rest', facing, floor, place)
    scene.frame_set(1)
    for obj in loaded.objects:
        if obj is not None:
            bpy.data.objects.remove(obj)
    return copies
