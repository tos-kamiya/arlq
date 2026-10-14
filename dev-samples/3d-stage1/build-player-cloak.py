"""A player with a separate torso and thin draped cloak."""
from pathlib import Path
import math
import sys
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parent
ARMS = '--arms' in sys.argv
FLOWING = '--flowing' in sys.argv or ARMS
CYLINDER = '--cylinder' in sys.argv or FLOWING
OUT = ROOT / ('player-arms' if ARMS else 'player-flowing' if FLOWING else 'player-cylinder' if CYLINDER else 'player-cloak')
OUT.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(ROOT / 'player' / 'player.blend'))
scene = bpy.context.scene
for obj in list(scene.objects):
    if obj.name.startswith('Player') or obj.name == 'Overlay @':
        bpy.data.objects.remove(obj, do_unlink=True)


def material(name, color, transmission, roughness):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (*color, 1)
    shader.inputs['Transmission Weight'].default_value = transmission
    shader.inputs['Roughness'].default_value = roughness
    shader.inputs['IOR'].default_value = 1.45
    return mat


def block(name, pos, size, mat, radius):
    bpy.ops.mesh.primitive_cube_add(size=1, location=pos)
    obj = bpy.context.object
    obj.name = name
    obj.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    bevel = obj.modifiers.new('Rounded edges', 'BEVEL')
    bevel.width = radius
    bevel.segments = 5
    obj.data.use_auto_smooth = True
    obj.modifiers.new('Weighted normals', 'WEIGHTED_NORMAL')
    return obj


body_mat = material('Player translucent tunic', (0.50, 0.76, 0.88), 0.55, 0.24)
head_mat = bpy.data.materials['Player frost crystal']
cape_mat = material('Player thin frosted fabric', (0.23, 0.55, 0.72), 0.25, 0.38)
boot_mat = material('Player smoky boots', (0.11, 0.23, 0.31), 0.25, 0.30)

if CYLINDER:
    bpy.ops.mesh.primitive_cylinder_add(vertices=64,
                                       radius=0.27 if FLOWING else 0.38,
                                       depth=0.40 if FLOWING else 0.62,
                                       location=(0, 0, 0.30 if FLOWING else 0.40))
    torso = bpy.context.object
    torso.name = 'Player rounded cylinder torso'
    torso.data.materials.append(body_mat)
    for face in torso.data.polygons:
        face.use_smooth = len(face.vertices) == 4
    torso.data.use_auto_smooth = True
    bevel = torso.modifiers.new('Rounded cylinder rims', 'BEVEL')
    bevel.width = 0.065 if FLOWING else 0.075
    bevel.segments = 5
    torso.modifiers.new('Weighted normals', 'WEIGHTED_NORMAL')
    block('Player head', (0, -0.07, 0.67 if FLOWING else 0.86),
          (0.38, 0.36, 0.36 if FLOWING else 0.34), head_mat, 0.11)
    if ARMS:
        for side in (-1, 1):
            arm = block('Player short arm', (side * 0.285, -0.075, 0.32),
                        (0.16, 0.18, 0.28), body_mat, 0.065)
            arm.rotation_euler.y = -side * 0.12
else:
    block('Player torso', (0, 0.025, 0.49), (0.48, 0.37, 0.52), body_mat, 0.09)
    block('Player neck', (0, -0.07, 0.76), (0.18, 0.18, 0.12), head_mat, 0.035)
    block('Player head', (0, -0.20, 0.92), (0.36, 0.34, 0.30), head_mat, 0.07)
    for side in (-1, 1):
        arm = block('Player arm', (side * 0.31, -0.015, 0.47),
                    (0.16, 0.23, 0.38), body_mat, 0.065)
        arm.rotation_euler.y = -side * 0.12
        block('Player leg', (side * 0.13, -0.005, 0.23),
              (0.17, 0.22, 0.27), body_mat, 0.045)
        block('Player boot', (side * 0.13, -0.17, 0.15),
              (0.20, 0.34, 0.13), boot_mat, 0.045)

# A curved open sheet with subtle folds, hanging from the shoulders behind the body.
columns, rows = (25, 8) if CYLINDER else (9, 6)
vertices = []
for row in range(rows):
    t = row / (rows - 1)
    width = 0.34 + 0.20 * t
    for col in range(columns):
        u = col / (columns - 1) * 2 - 1
        if CYLINDER:
            angle = u * math.radians(90 if FLOWING else 110)
            if FLOWING:
                radius = 0.285 + 0.07 * t
                # Shoulders follow the body; the lower cloth drifts backward.
                vertices.append((radius * math.sin(angle) + 0.035 * t * t,
                                 radius * math.cos(angle) + 0.23 * t * t,
                                 0.48 - 0.31 * t + 0.035 * t * math.cos(u * math.pi)))
            else:
                radius = 0.405 + 0.04 * t
                vertices.append((radius * math.sin(angle), radius * math.cos(angle),
                                 0.68 - 0.56 * t))
        else:
            fold = math.cos(u * math.pi * 3) * 0.018 * t
            vertices.append((u * width, 0.13 + 0.52 * t + 0.035 * u * u,
                             0.70 - 0.55 * t + 0.06 * (1 - u * u) + fold))
faces = []
for row in range(rows - 1):
    for col in range(columns - 1):
        i = row * columns + col
        faces.append((i, i + 1, i + 1 + columns, i + columns))
mesh = bpy.data.meshes.new('Thin draped cloak surface')
mesh.from_pydata(vertices, [], faces)
mesh.update()
cloak = bpy.data.objects.new('Player thin cloak', mesh)
scene.collection.objects.link(cloak)
cloak.data.materials.append(cape_mat)
for face in mesh.polygons:
    face.use_smooth = True
subdivision = cloak.modifiers.new('Smooth fabric drape', 'SUBSURF')
subdivision.levels = 2
solidify = cloak.modifiers.new('Fabric thickness', 'SOLIDIFY')
solidify.thickness = 0.025
solidify.offset = 0
bevel = cloak.modifiers.new('Soft fabric edge', 'BEVEL')
bevel.width = 0.008
bevel.segments = 2

bpy.ops.object.text_add(location=(0, -0.07, 0.855 if FLOWING else 1.035)
                        if CYLINDER else (0, -0.20, 1.075))
mark = bpy.context.object
mark.name = 'Overlay @'
mark.data.body = '@'
mark.data.align_x = 'CENTER'
mark.data.align_y = 'CENTER'
mark.data.size = 0.23
mark.data.extrude = 0.002
mark.data.materials.append(bpy.data.materials['Obsidian eyes'])

collection = bpy.data.collections.new('Player with thin cloak')
scene.collection.children.link(collection)
for obj in list(scene.objects):
    if obj.name.startswith('Player') or obj.name == 'Overlay @':
        for old in list(obj.users_collection):
            old.objects.unlink(obj)
        collection.objects.link(obj)
camera = scene.camera
camera.location = (0, -5.5, 14)
camera.rotation_euler = (Vector((0, 0, 0)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'player.blend'))
scene.render.filepath = str(OUT / 'preview-overhead.png')
bpy.ops.render.render(write_still=True)
camera.location = (0, 0, 15)
camera.rotation_euler = (0, 0, 0)
scene.render.filepath = str(OUT / 'preview-top.png')
bpy.ops.render.render(write_still=True)
