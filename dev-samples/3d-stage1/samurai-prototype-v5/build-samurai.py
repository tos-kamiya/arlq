"""Build the tall Samurai study with Blender in background mode."""

import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
RIG_DIR = HERE.parent / 'rigged-armor'
sys.path.insert(0, str(RIG_DIR))

from build import attach, material, own_sword


def plate(rig, name, bone, vertices, faces, metal):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    attach(obj, rig, bone, metal).modifiers['Forged edge'].width = .004
    return obj


def band(rig, name, bone, rings, metal, start=0, end=360, steps=32, center_x=0):
    """Elliptical shell, optionally open at the front."""
    closed = end - start == 360
    count = steps if closed else steps + 1
    vertices = []
    for z, rx, ry, cy in rings:
        for i in range(count):
            angle = math.radians(start + (end - start) * i / steps)
            vertices.append((center_x + rx * math.sin(angle), cy - ry * math.cos(angle), z))
    faces = []
    for row in range(len(rings) - 1):
        for i in range(steps):
            j = (i + 1) % count
            a, b = row * count, (row + 1) * count
            faces.append((a + i, a + j, b + j, b + i))
    if closed:
        faces.extend((tuple(range(count - 1, -1, -1)),
                      tuple(range(len(vertices) - count, len(vertices)))))
    obj = plate(rig, name, bone, vertices, faces, metal)
    if not closed:
        solidify = obj.modifiers.new('Plate thickness', 'SOLIDIFY')
        solidify.thickness = .012
        obj.modifiers.move(len(obj.modifiers) - 1, 0)
    for face in obj.data.polygons:
        face.use_smooth = len(face.vertices) == 4
    return obj


def panel(rig, name, bone, outline, offset, metal):
    vertices = [Vector(v) for v in outline]
    vertices += [v + Vector(offset) for v in vertices]
    n = len(outline)
    faces = [tuple(range(n)), tuple(range(n, 2 * n))]
    faces += [(i, (i + 1) % n, (i + 1) % n + n, i + n) for i in range(n)]
    return plate(rig, name, bone, vertices, faces, metal)


def cut_armholes(cuirass):
    # Use the same round cut on the steel and its lining.
    for sign in (-1, 1):
        bpy.ops.mesh.primitive_uv_sphere_add(
            segments=32, ring_count=16, radius=1,
            location=(sign * .237, 0, 1.448),
        )
        cutter = bpy.context.object
        cutter.scale = (.122, .115, .155)
        for part in cuirass:
            cut = part.modifiers.new('Rounded arm opening', 'BOOLEAN')
            cut.object = cutter
            part.modifiers.move(len(part.modifiers) - 1, 0)
            bpy.context.view_layer.objects.active = part
            bpy.ops.object.modifier_apply(modifier=cut.name)
        bpy.data.objects.remove(cutter, do_unlink=True)


def build_armor(rig):
    mats = bpy.data.materials
    steel = mats['Player steel plate']
    silver = mats['Player steel helm']
    iron = mats['Player dark iron trim']
    cloth = mats['Player midnight cloak']
    lining = mats['Dark joint lining']
    sole = material('Zori sole', (.22, .18, .125), roughness=.85)
    hidden = ('Sabaton', 'Helmet', 'Eye ', 'Nape cutter', 'Cape', 'Pauldron', 'Chest seam',
              'Breast and back plate', 'Diagonal waist plate', 'Knee cap', 'thigh plate')
    for obj in list(rig.children):
        if obj.name.startswith(hidden):
            obj.hide_viewport = obj.hide_render = True
        if obj.name.startswith(('upper_arm plate', 'Hip armor', 'Joint shin',
                                'Joint forearm', 'Elbow cap')):
            obj.data.materials.clear()
            obj.data.materials.append(cloth)

    band(rig, 'Kabuto face guard', 'head', [
        (1.50, .103, .095, -.015), (1.524, .116, .110, -.016),
        (1.581, .118, .113, -.011), (1.651, .116, .107, 0),
    ], lining, -75, 75)
    # The equator sits above the old rim while the crown stays near its former height.
    bowl_base, radius = 1.676, .132
    bowl = [
        (bowl_base + radius * math.sin(angle),
         radius * math.cos(angle), radius * math.cos(angle), .007)
        for angle in (math.radians(degrees) for degrees in range(0, 90, 10))
    ]
    bowl.append((bowl_base + radius, .0005, .0005, .007))
    band(rig, 'Kabuto bowl', 'head', bowl, silver)
    band(rig, 'Kabuto brow rim', 'head', [
        (1.654, .132, .130, .007), (1.678, .134, .133, .007),
    ], iron)
    band(rig, 'Kabuto visor', 'head', [
        (1.642, .142, .165, .002), (1.661, .131, .130, .005),
    ], silver, -67, 67)
    for row, (rx, ry, lower_rx, lower_ry) in enumerate((
        (.131, .132, .149, .153),
        (.145, .148, .170, .178),
        (.162, .169, .198, .206),
    )):
        z = 1.654 - row * .047
        band(rig, f'Shikoro {row + 1}', 'head', [
            (z - .045, lower_rx, lower_ry, .012), (z, rx, ry, .012),
        ], steel, 65, 295)
        band(rig, f'Shikoro dark edge {row + 1}', 'head', [
            (z - .048, lower_rx + .001, lower_ry + .001, .012),
            (z - .039, lower_rx - .004, lower_ry - .004, .012),
        ], iron, 65, 295)

    for side, sign in (('L', 1), ('R', -1)):
        panel(rig, f'Kuwagata {side}', 'head', [
            (sign * x, y, z + .021) for x, y, z in (
                (.017, -.149, 1.653), (.060, -.149, 1.645),
                (.120, -.137, 1.717), (.159, -.114, 1.867),
                (.122, -.116, 1.843), (.088, -.133, 1.742),
                (.043, -.149, 1.684),
            )
        ], (0, .015, 0), silver)
        shoulder_angles = (32, 148) if sign == 1 else (212, 328)
        for row in range(4):
            x, z = sign * (.244 + row * .029), 1.498 - row * .059
            bone = f'upper_arm.{side}'
            band(rig, f'Sode {side} {row + 1}', bone, [
                (z - .052, .121, .127, 0), (z, .100, .111, 0),
            ], steel, *shoulder_angles, steps=16, center_x=x)
            band(rig, f'Sode dark edge {side} {row + 1}', bone, [
                (z - .054, .123, .128, 0), (z - .045, .119, .125, 0),
            ], iron, *shoulder_angles, steps=16, center_x=x)

        trousers = band(rig, f'Baggy trousers {side}', f'thigh.{side}', [
            (.523, .053, .064, -.023), (.55, .080, .080, -.022),
            (.595, .105, .103, -.017), (.667, .123, .123, -.008),
            (.746, .126, .123, 0), (.811, .114, .109, 0),
            (.874, .089, .086, 0), (.921, .065, .070, 0),
        ], cloth, center_x=sign * .142)
        # A narrow cuff and fuller fabric above it keep the knee readable.
        trousers.modifiers['Forged edge'].width = .002
        band(rig, f'Zori {side}', f'foot.{side}', [
            (.024, .067, .109, -.062), (.033, .074, .117, -.062),
            (.057, .075, .118, -.062), (.069, .067, .110, -.062),
        ], sole, center_x=sign * .15)
        foot_material = bpy.data.objects[f'Joint foot.{side}'].data.materials[0]
        band(rig, f'Foot {side}', f'foot.{side}', [
            (.061, .048, .087, -.062), (.071, .061, .101, -.061),
            (.092, .059, .094, -.057), (.111, .046, .073, -.045),
            (.126, .029, .042, -.024),
        ], foot_material, center_x=sign * .15)


    for name, bone, side in (
        ('front', 'pelvis', 0),
        ('left', 'hip_plate.L', 1),
        ('right', 'hip_plate.R', -1),
    ):
        slats = []
        for row in range(4):
            z = 1.048 - row * .069
            bottom = z - .062
            if side:
                x = .174 + row * .026
                outline = [
                    (side * (x - .015), -.118, z), (side * x, .105, z),
                    (side * (x + .027), .121, bottom),
                    (side * (x + .012), -.134, bottom),
                ]
                inward = Vector((-side * .012, 0, 0))
            else:
                width, y = .109 + row * .009, -.144 - row * .013
                outline = [
                    (-width, y, z), (width, y, z),
                    (width + .01, y - .014, bottom),
                    (-width - .01, y - .014, bottom),
                ]
                inward = Vector((0, .012, 0))
            slats.append(panel(rig, f'Kusazuri {name} {row + 1}', bone,
                               outline, inward, steel))
            lower_left, lower_right = map(Vector, (outline[3], outline[2]))
            upper_left = lower_left.lerp(Vector(outline[0]), .13)
            upper_right = lower_right.lerp(Vector(outline[1]), .13)
            edge = [v - inward * .2 for v in (upper_left, upper_right, lower_right, lower_left)]
            slats.append(panel(rig, f'Kusazuri {name} dark edge {row + 1}', bone,
                               edge, inward * .5, iron))
        # All slats in each section share the same bone and modifiers.
        bpy.ops.object.select_all(action='DESELECT')
        for slat in slats:
            slat.select_set(True)
        bpy.context.view_layer.objects.active = slats[0]
        bpy.ops.object.join()
        slats[0].name = f'Kusazuri {name}'

    cuirass = [band(rig, 'Dou lining', 'chest', [
        (1.069, .137, .096, 0), (1.33, .198, .123, 0),
        (1.45, .17, .091, 0),
    ], iron)]
    for row, (z, rx, ry, top_rx, top_ry) in enumerate((
        (1.077, .152, .109, .172, .115),
        (1.162, .175, .121, .193, .129),
        (1.247, .197, .134, .204, .134),
        (1.332, .206, .138, .177, .103),
    ), 1):
        cuirass.append(band(rig, f'Dou plate {row}', 'chest', [
            (z, rx, ry, 0), (z + .071, top_rx, top_ry, 0),
        ], steel))
    widen = Matrix.Diagonal((1.05, 1.05, 1.0, 1.0))
    waist = [bpy.data.objects[name] for name in (
        'Belt', 'Belt buckle', 'Flexible waist lining', 'Hip armor',
    )]
    for part in cuirass + waist:
        part.data.transform(widen)
    cut_armholes(cuirass)
    blade = material('Player iron blade', (.62, .63, .66), .55, .4,
                     rim=(.85, .9, 1.0), rim_strength=.8)
    own_sword(rig, blade, iron)


def preview(scene, name, frame, view):
    scene.frame_set(frame)
    target = Vector((0, 0, .95))
    scene.camera.location = target + Vector(view)
    scene.camera.rotation_euler = (target - scene.camera.location).to_track_quat('-Z', 'Y').to_euler()
    scene.render.filepath = str(HERE / f'{name}.png')
    bpy.ops.render.render(write_still=True)


def main():
    destination = HERE / 'hero-samurai.blend'
    bpy.ops.wm.open_mainfile(filepath=str(RIG_DIR / 'hero-rig.blend'))
    scene = bpy.context.scene
    rig = bpy.data.objects['Hero rig']
    if rig.mode != 'OBJECT':
        bpy.context.view_layer.objects.active = rig
        bpy.ops.object.mode_set(mode='OBJECT')
    scene.frame_set(1)
    build_armor(rig)
    scene.cycles.samples = 48
    scene.cycles.use_denoising = False
    scene.render.resolution_x = 640
    scene.render.resolution_y = 720
    scene.camera.data.ortho_scale = 2.52
    preview_views = (
        ('samurai-front', 1, (2.0, -6, 1.35)),
        ('samurai-back', 1, (2.3, 6, 1.6)),
        ('samurai-step', 80, (-2.3, -6, 1.55)),
    )
    for name, frame, view in preview_views:
        preview(scene, name, frame, view)
    scene.frame_set(1)
    target = Vector((0, 0, .95))
    scene.camera.location = target + Vector(preview_views[0][2])
    scene.camera.rotation_euler = (target - scene.camera.location).to_track_quat('-Z', 'Y').to_euler()
    scene.render.filepath = '//samurai-front.png'
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(destination))


if __name__ == '__main__':
    main()
