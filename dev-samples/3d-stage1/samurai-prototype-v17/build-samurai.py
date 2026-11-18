"""Build the tall Samurai and katana using the existing rigged-armor base rig."""

import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
RIG_DIR = HERE.parent / 'rigged-armor'
sys.path.insert(0, str(RIG_DIR))

from build import SWORD_BACK_TILT, attach, material


def new_mesh(name, vertices, faces):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    return mesh


def plate(rig, name, bone, vertices, faces, metal):
    mesh = new_mesh(name, vertices, faces)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    attach(obj, rig, bone, metal).modifiers['Forged edge'].width = .004
    return obj


def band(rig, name, bone, rings, metal, start=0, end=360, steps=32,
         center_x=0, openings=None, ring_x_offsets=None):
    """Elliptical shell, optionally open at the front."""
    closed = end - start == 360
    count = steps if closed else steps + 1
    vertices = []
    for row, (z, rx, ry, cy) in enumerate(rings):
        cx = center_x + (ring_x_offsets[row] if ring_x_offsets else 0)
        for i in range(count):
            angle = math.radians(start + (end - start) * i / steps)
            vertices.append((cx + rx * math.sin(angle), cy - ry * math.cos(angle), z))
    faces = []
    for row in range(len(rings) - 1):
        omitted = openings.get(row, ()) if openings else ()
        for i in range(steps):
            if i in omitted:
                continue
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


def tilt_ornament(obj, pivot, degrees):
    center = Vector(pivot)
    turn = (Matrix.Translation(center)
            @ Matrix.Rotation(math.radians(degrees), 4, 'X')
            @ Matrix.Translation(-center))
    world = obj.matrix_world
    obj.data.transform(world.inverted() @ turn @ world)


def katana_part(grip, name, vertices, faces, surface, bevel_width):
    mesh = new_mesh(name, vertices, faces)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.parent = grip
    mesh.materials.append(surface)
    bevel = obj.modifiers.new('Rounded edges', 'BEVEL')
    bevel.width, bevel.segments = bevel_width, 2


def build_katana_blade(grip, steel):
    # X follows the grip, +Y points toward the cutting edge, and Z is thickness.
    length, sweep = .54, .052
    vertices = []
    for t, width, half_thickness in (
        (0, .054, .008), (.17, .053, .008), (.34, .051, .0075),
        (.51, .049, .007), (.68, .047, .0065), (.83, .044, .006),
        (.90, .040, .0055), (.94, .033, .0045),
        (.97, .023, .0035), (.989, .011, .002),
    ):
        center = Vector((length * t, -sweep * t * t, 0))
        across = Vector((2 * sweep * t, length, 0)).normalized()
        # The spine keeps its sweep while the cutting edge rounds toward it.
        spine = center - across * (.027 - .006 * t)
        edge = spine + across * width
        vertices.extend((spine + Vector((0, 0, half_thickness)),
                         spine - Vector((0, 0, half_thickness)), edge))
    spine_offset = Vector((2 * sweep, length, 0)).normalized() * .021
    vertices.append(Vector((length, -sweep, 0)) - spine_offset)
    tip = len(vertices) - 1
    faces = [(2, 1, 0)]
    for row in range(0, tip - 3, 3):
        for i in range(3):
            following = (i + 1) % 3
            faces.append((row + i, row + following, row + following + 3, row + i + 3))
    faces.extend((tip - 3 + i, tip - 3 + (i + 1) % 3, tip) for i in range(3))
    katana_part(grip, 'Katana blade', vertices, faces, steel, .0008)


def build_katana_hilt(grip, iron, indigo):
    sides = 32
    for name, start, end, width, depth, surface in (
        ('Katana tsuba', -.020, .004, .066, .048, iron),
        ('Katana grip', -.216, -.018, .031, .025, indigo),
        ('Katana pommel', -.228, -.211, .032, .027, iron),
    ):
        vertices = [
            (x, width * math.cos(angle), depth * math.sin(angle))
            for x in (start, end)
            for angle in (math.tau * i / sides for i in range(sides))
        ]
        faces = [tuple(range(sides)), tuple(range(sides, 2 * sides))]
        for i in range(sides):
            following = (i + 1) % sides
            faces.append((i, following, following + sides, i + sides))
        katana_part(grip, name, vertices, faces, surface, .003)


def build_habaki(grip, brass):
    # A short tapered collar that follows the blade's thick spine and thin edge.
    vertices = [
        (x, y, z)
        for x, spine, edge, spine_half, edge_half in (
            (.002, -.034, .034, .016, .007),
            (.042, -.030, .029, .012, .004),
        )
        for y, z in ((spine, spine_half), (spine, -spine_half),
                     (edge, -edge_half), (edge, edge_half))
    ]
    faces = [(0, 1, 2, 3), (4, 5, 6, 7)]
    faces.extend((i, (i + 1) % 4, (i + 1) % 4 + 4, i + 4) for i in range(4))
    katana_part(grip, 'Katana habaki', vertices, faces, brass, .0016)


def mount_katana(rig):
    bone = rig.data.bones['hand.R']
    fist = bone.head_local.lerp(bone.tail_local, .6)
    ahead = Vector((-.75, .3, .32)).normalized()
    ahead = Matrix.Rotation(SWORD_BACK_TILT, 3, ahead.cross(Vector((0, 1, 0)))) @ ahead

    # Keep the edge toward the front, so the blade sweeps back toward the spine.
    forward = Vector((0, -1, 0))
    edgeward = (forward - ahead * forward.dot(ahead)).normalized()
    thickness_axis = ahead.cross(edgeward)
    mount = Matrix((ahead, edgeward, thickness_axis)).transposed().to_4x4()
    mount.translation = fist + ahead * .106
    bone_tip = Matrix.Translation((0, bone.length, 0))
    rest_parent = rig.matrix_world @ bone.matrix_local @ bone_tip

    grip = bpy.data.objects.new('Katana hand mount', None)
    bpy.context.collection.objects.link(grip)
    grip.parent = rig
    grip.parent_type = 'BONE'
    grip.parent_bone = bone.name
    grip.matrix_parent_inverse = rest_parent.inverted() @ mount
    grip.empty_display_size = .035

    steel = material('Katana steel', (.65, .70, .77), .78, .27)
    iron = material('Katana dark iron', (.12, .13, .16), .75, .38)
    indigo = material('Katana indigo grip', (.033, .055, .13), roughness=.62)
    brass = material('Katana muted brass', (.47, .32, .12), .72, .39)
    build_katana_blade(grip, steel)
    build_katana_hilt(grip, iron, indigo)
    build_habaki(grip, brass)

    # Roll around the grip axis as the wrist turns, preserving the grip and blade heading.
    scene = bpy.context.scene
    original_frame = scene.frame_current
    for frame in (1, 40, 80):
        scene.frame_set(frame)
        wrist = rig.matrix_world @ rig.pose.bones[bone.name].matrix @ bone_tip
        unrolled = wrist @ grip.matrix_parent_inverse
        local_forward = unrolled.to_3x3().inverted() @ forward
        grip.rotation_euler.x = math.atan2(local_forward.z, local_forward.y)
        grip.keyframe_insert(data_path='rotation_euler', index=0, frame=frame)
    scene.frame_set(original_frame)


def build_armor(rig):
    mats = bpy.data.materials
    steel = mats['Player steel plate']
    silver = mats['Player steel helm']
    iron = mats['Player dark iron trim']
    cloth = mats['Player midnight cloak']
    sole = material('Zori sole', (.22, .18, .125), roughness=.85)
    hidden = ('Sabaton', 'Eye ', 'Nape cutter', 'Cape', 'Pauldron', 'Chest seam',
              'Breast and back plate', 'Diagonal waist plate', 'Knee cap', 'thigh plate')
    for obj in list(rig.children):
        if obj.name.startswith(hidden) or obj.name in ('Helmet', 'Helmet cavity cutter'):
            obj.hide_viewport = obj.hide_render = True
        if obj.name.startswith(('upper_arm plate', 'Hip armor', 'Joint shin',
                                'Joint forearm', 'Elbow cap')):
            obj.data.materials.clear()
            obj.data.materials.append(cloth)

    mask_steel = material('Mask blackened steel', (.047, .054, .065), .65, .46)
    mask = band(rig, 'Kabuto mask', 'head', [
        (1.50, .103, .095, -.015), (1.524, .116, .110, -.016),
        (1.581, .118, .113, -.011), (1.588, .118, .112, -.009),
        (1.613, .117, .111, -.007), (1.651, .116, .107, 0),
    ], mask_steel, -75, 75, steps=40, openings={3: range(4, 36)})
    # Keep the slit edges crisp at sprite size.
    mask.modifiers['Plate thickness'].thickness = .008
    mask.modifiers['Forged edge'].width = .002
    glow = mats['Player visor glow'].copy()
    glow.name = 'Mask visor glow'
    glow.node_tree.animation_data_clear()
    glow.node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value = .8
    band(rig, 'Mask recessed eye light', 'head', [
        (1.586, .117, .112, .006), (1.615, .117, .111, .008),
    ], glow, -65, 65)
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

    # Rotate around points inside the bowl so the bases stay seated.
    crest = bpy.data.objects['Helmet crest']
    crest.data.transform(Matrix.Translation((0, .014, -.004)))
    tilt_ornament(crest, (0, -.030, 1.778), -10)
    crest.data.transform(Matrix.Translation((0, -.018, -.012)))

    for side, sign in (('L', 1), ('R', -1)):
        tilt_ornament(bpy.data.objects[f'Helmet horn {side}'],
                      (sign * .078, .002, 1.693), 14)
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

        trouser_profile = (
            (.523, .053, .064, -.023, 0), (.532, .055, .065, -.023, 0),
            (.548, .093, .099, -.021, .005), (.567, .1176, .1176, -.019, .009),
            (.595, .12705, .12495, -.016, .011), (.667, .128, .126, -.008, .012),
            (.746, .126, .123, 0, .011), (.811, .114, .109, 0, .009),
            (.874, .089, .086, 0, .005), (.921, .065, .070, 0, 0),
        )
        # Shift each widened ring inward so its outside edge stays in place.
        trouser_rings = [(z, rx + inward / 2, ry, cy)
                         for z, rx, ry, cy, inward in trouser_profile]
        trouser_offsets = [-sign * ring[4] / 2 for ring in trouser_profile]
        trousers = band(rig, f'Baggy trousers {side}', f'thigh.{side}',
                        trouser_rings, cloth, center_x=sign * .142,
                        ring_x_offsets=trouser_offsets)
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
    mount_katana(rig)


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
        ('samurai-side', 1, (6.2, 0, .7)),
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
