"""Build a low head-to-body version of the armor rig for the overall preview.

blender --background --threads 4 --python dev-samples/3d-stage1/rigged-armor/build-chibi.py

It builds the same model as build.py, then shrinks the body region by region
while keeping the head at full size: each part is scaled about the head of
the bone it is attached to, by the region's factor along the bone and 1.2
times that across it (thicker limbs and torso), and the joints still meet.
The result is about four heads tall. Writes
hero-rig-chibi.blend and chibi-rest/guard/step.png next to this script.
"""
import importlib.util
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('hero_rig_build', HERE / 'build.py')
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)

# Scale per region along each bone; the head keeps its size.
TORSO, ARMS, LEGS, HEAD = .6, .55, .46, 1.0
# Arms, legs and torso are then made this much thicker across their bones.
# The clavicles widen along their length too, so the shoulders keep up with
# the thicker chest. The round dark parts (ball joints, knee and elbow caps,
# pauldrons, gauntlets) and the swords are not thickened, so they keep their
# shapes.
THICKEN = 1.2
ROUND_PARTS = ('Joint ', 'Knee cap ', 'Elbow cap ', 'Pauldron ', 'Sword ', 'Chimera sword ',
               'Cursed sword ', 'Blessed sword ', 'Gauntlet ')


def region_scale(name):
    if name in ('root', 'head'):
        return HEAD
    if name.startswith(('upper_arm.', 'forearm.', 'hand.')):
        return ARMS
    if name.startswith(('thigh.', 'shin.', 'foot.')):
        return LEGS
    return TORSO    # pelvis, waist, chest, neck, clavicles, cape, hip plates


def chibify(rig, scene):
    """Rescale the rest skeleton and every part, region by region."""
    bpy.context.view_layer.update()
    bones = rig.data.bones
    old = {name: (bones[name].head_local.copy(), bones[name].tail_local.copy())
           for name in build.BONES}
    # Per bone, a scale in its own frame: `along` its length (local Y) and
    # `across` it (local X and Z).
    scale = {}
    for name in build.BONES:
        along = region_scale(name)
        across = along if name in ('root', 'head') else along * THICKEN
        if name.startswith('clavicle.'):
            along = across
        # The cape and its bones scale like the chest (thicker horizontally),
        # not across their own slanting bones, so the cape keeps its gap from
        # the thickened chest.
        frame = bones['chest' if name.startswith('cape.') else name].matrix_local.to_3x3().normalized()
        scale[name] = frame @ Matrix.Diagonal((across, along, across)) @ frame.transposed()
    head = {}
    # BONES lists parents before children. A child's head keeps its offset
    # from its parent's head, scaled like the parent, so joints still meet.
    for name, (_, _, parent) in build.BONES.items():
        head[name] = old[name][0] if parent is None else (
            head[parent] + scale[parent] @ (old[name][0] - old[parent][0]))
    tail = {name: head[name] + scale[name] @ (old[name][1] - old[name][0]) for name in head}

    def bone_map(name, uniform=False):
        # Round parts keep their shape: they shrink with the region but are
        # not thickened.
        matrix = (Matrix.Scale(region_scale(name), 4) if uniform else scale[name].to_4x4())
        return Matrix.Translation(head[name]) @ matrix @ Matrix.Translation(-old[name][0])

    rigid = [o for o in scene.objects if o.parent == rig and o.parent_type == 'BONE']
    worlds = {o.name: bone_map(o.parent_bone, o.name.startswith(ROUND_PARTS)) @ o.matrix_world
              for o in rigid}
    cape = bpy.data.objects['Cape']
    # Only the bone groups move the cape; others (the saved tall rig's
    # 'Drape amount') are skipped.
    groups = {g.index: g.name for g in cape.vertex_groups if g.name in head}
    cape_points = []
    for vertex in cape.data.vertices:
        weights = [g for g in vertex.groups if g.group in groups]
        total = sum(g.weight for g in weights)
        cape_points.append(sum((bone_map(groups[g.group]) @ vertex.co * (g.weight / total)
                                for g in weights), Vector()))
    # Drop everything so the lowest point stays on the floor.
    def lowest(objects_worlds):
        return min((world @ v.co).z for obj, world in objects_worlds for v in obj.data.vertices)
    old_low = min(lowest((o, o.matrix_world) for o in rigid), min(v.co.z for v in cape.data.vertices))
    new_low = min(lowest((o, worlds[o.name]) for o in rigid), min(p.z for p in cape_points))
    drop = Matrix.Translation((0, 0, old_low - new_low))

    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')
    for name, edit_bone in rig.data.edit_bones.items():
        if name != 'root':
            edit_bone.head, edit_bone.tail = drop @ head[name], drop @ tail[name]
            edit_bone.align_roll(Vector((0, -1, 0)))
    bpy.ops.object.mode_set(mode='OBJECT')
    for obj in rigid:
        bone = rig.data.bones[obj.parent_bone]
        obj.matrix_parent_inverse = (rig.matrix_world @ bone.matrix_local
                                     @ Matrix.Translation((0, bone.length, 0))).inverted()
        # Thickening a slanted bone shears its parts, which an object
        # transform (location, rotation, scale) cannot hold, so the whole map
        # is baked into the mesh and the object keeps an identity transform.
        obj.data.transform(drop @ worlds[obj.name])
        obj.data.update()
        obj.matrix_basis = Matrix.Identity(4)
        # Bevels and thicknesses are in object space; shrink them with the part.
        factor = region_scale(obj.parent_bone)
        for modifier in obj.modifiers:
            if modifier.type == 'BEVEL':
                modifier.width *= factor
            elif modifier.type == 'SOLIDIFY':
                modifier.thickness *= factor
    for vertex, point in zip(cape.data.vertices, cape_points):
        vertex.co = drop @ point
    cape.data.update()
    bpy.context.view_layer.update()


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    rig = build.create_rig()
    build.build_armor(rig)
    chibify(rig, scene)
    build.animate(rig, scene)
    build.setup_scene(scene)
    # Frame the shorter figure.
    camera = scene.camera
    target = Vector((0, 0, .55))
    camera.location = target + Vector((2.7, -6, 1.75))
    camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera.data.ortho_scale = 1.45
    build.validate(rig, scene)
    # `-- --only rest,step` renders just those poses.
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    only = args[args.index('--only') + 1].split(',') if '--only' in args else None
    build.save_and_render(rig, scene, 'hero-rig-chibi.blend', 'chibi-', (0, 0, .55), 2.0, only)


if __name__ == '__main__':
    main()
