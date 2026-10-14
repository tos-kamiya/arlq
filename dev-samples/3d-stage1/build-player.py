"""Create a fixed-facing player using the accepted creatures' display setup."""
from pathlib import Path
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'player'
OUT.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(ROOT / 'attached-cones' / 'stage1-characters.blend'))
scene = bpy.context.scene
for obj in list(scene.objects):
    if obj.type not in ('LIGHT', 'CAMERA') and obj.name != 'Backdrop':
        bpy.data.objects.remove(obj, do_unlink=True)


def resin(name, color):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (*color, 1)
    shader.inputs['Transmission Weight'].default_value = 0.65
    shader.inputs['Roughness'].default_value = 0.19
    shader.inputs['IOR'].default_value = 1.45
    return mat


def soften(obj, width):
    bevel = obj.modifiers.new('Soft bevels', 'BEVEL')
    bevel.width = width
    bevel.segments = 4
    obj.data.use_auto_smooth = True
    obj.modifiers.new('Weighted normals', 'WEIGHTED_NORMAL')


def cube(name, pos, size, material, bevel):
    bpy.ops.mesh.primitive_cube_add(size=1, location=pos)
    obj = bpy.context.object
    obj.name = name
    obj.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(material)
    soften(obj, bevel)
    return obj


def label(value, pos, size, material):
    bpy.ops.object.text_add(location=pos)
    obj = bpy.context.object
    obj.name = 'Overlay ' + value
    obj.data.body = value
    obj.data.align_x = 'CENTER'
    obj.data.align_y = 'CENTER'
    obj.data.size = size
    obj.data.extrude = 0.002
    obj.data.materials.append(material)


head_mat = resin('Player frost crystal', (0.72, 0.88, 0.97))
cape_mat = resin('Player pale blue cloak', (0.36, 0.69, 0.85))
ink = bpy.data.materials['Ivory lettering']
mark = bpy.data.materials['Obsidian eyes']
cube('Display tile', (0, 0, 0), (2.65, 2.15, 0.15),
     bpy.data.materials['Smoked glass tile'], 0.09)

# A single broad cloak with a small V opening on the screen-bottom side.
outline = [(-0.28, -0.42), (-0.47, -0.12), (-0.57, 0.60),
           (0.57, 0.60), (0.47, -0.12), (0.28, -0.42), (0, -0.26)]
verts = [(x, y, 0.14) for x, y in outline]
verts += [(x, y, 0.48 if y < 0 else 0.28) for x, y in outline]
count = len(outline)
faces = [tuple(reversed(range(count))), tuple(range(count, 2 * count))]
faces += [(i, (i + 1) % count, (i + 1) % count + count, i + count)
          for i in range(count)]
mesh = bpy.data.meshes.new('Cloak silhouette mesh')
mesh.from_pydata(verts, [], faces)
mesh.update()
cloak = bpy.data.objects.new('Player simple cloak', mesh)
scene.collection.objects.link(cloak)
cloak.data.materials.append(cape_mat)
bpy.context.view_layer.objects.active = cloak
cloak.select_set(True)
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.normals_make_consistent(inside=False)
bpy.ops.object.mode_set(mode='OBJECT')
soften(cloak, 0.035)
cube('Player square head', (0, -0.24, 0.68), (0.47, 0.47, 0.36), head_mat, 0.055)
# The face is intentionally omitted; @ remains a separate top-facing overlay.
label('@', (0, -0.24, 0.865), 0.30, mark)
label('PLAYER / FIXED FRONT', (0, -1.30, 0.03), 0.16, ink)
label('ARLQ / PLAYER STUDY', (0, 1.40, 0.03), 0.16, ink)

collection = bpy.data.collections.new('Player prototype')
scene.collection.children.link(collection)
for obj in list(scene.objects):
    if obj.name.startswith('Player') or obj.name == 'Overlay @':
        for old in list(obj.users_collection):
            old.objects.unlink(obj)
        collection.objects.link(obj)
camera = scene.camera
camera.location = (0, -5.5, 14)
camera.rotation_euler = (Vector((0, 0, 0)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
camera.data.ortho_scale = 3.6
scene.render.resolution_x = 800
scene.render.resolution_y = 800
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'player.blend'))
scene.render.filepath = str(OUT / 'preview-overhead.png')
bpy.ops.render.render(write_still=True)
camera.location = (0, 0, 15)
camera.rotation_euler = (0, 0, 0)
scene.render.filepath = str(OUT / 'preview-top.png')
bpy.ops.render.render(write_still=True)
