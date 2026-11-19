"""Effect image of a defeated Vortex: its storm whirled flat over the floor.

The Vortex's two smoke strands (see vortex() in build-heroic.py), in
darker grey and violet-grey smoke, opened out into a wide funnel like the
Vortex's own: each strand spirals TURNS turns up and out from the eye on
the ground to REACH at HEIGHT, thin at the eye, swelling into a band midway
and tapering to its tip. Two smaller arms swirl in the gaps between them
(ARMS), and the Vortex's lightning, three bolts and three smaller ones
(BOLTS), crackles faintly (LIGHTNING_OPACITY) out of the funnel. The smoke is a volume (DENSITY, broken up by noise), so it has no
hard outline: it thins out toward the edges of each band.

Rendered orthographically (ORTHO units across SIZE px) looking ELEVATION
degrees down, steeper than the character sprites' 60, aimed at the middle
of the funnel's height. The eye on the ground is then FOOT of the image's
height below its centre, so the GUI can stand it on the Vortex's cell and
scale it to the area it swirls over (see draw_vortex_effect in
sprite_effects.py, whose VORTEX_STORM_REACH is REACH / ORTHO and
VORTEX_STORM_FOOT is FOOT).

    blender --factory-startup --background --threads 4 --python dev-samples/3d-stage1/build-vortex-storm.py

Writes src/arlq/assets/effects/vortex-storm.png.
"""
from pathlib import Path
import math

import bmesh
import bpy
from mathutils import Vector

OUT = (Path(__file__).resolve().parents[2] / 'src' / 'arlq' / 'assets' / 'effects'
       / 'vortex-storm.png')
REACH, ORTHO, SIZE = 1.0, 2.6, 384
HEIGHT, ELEVATION = 1.4, 75
FOOT = HEIGHT / 2 * math.cos(math.radians(ELEVATION)) / ORTHO
TURNS = 1.3
# A band's half width at its thickest, and how much flatter it is than wide.
BAND, FLAT = 0.085, 0.5
DENSITY = 40
# The arms all follow the same spiral: (start angle, the stretch of it they
# cover from the eye (0) to the tip (1), band, smoke). Two run the whole
# way; two smaller ones swirl in the gaps between them, turned a quarter
# turn or so and covering only part of the way.
ARMS = ((0.0, 0.0, 1.0, BAND, 0), (math.pi, 0.0, 1.0, BAND, 1),
        (math.pi / 2 + 0.3, 0.3, 0.75, 0.55 * BAND, 1),
        (3 * math.pi / 2 - 0.2, 0.45, 0.92, 0.5 * BAND, 0))
# The lightning bolts: (angle, length, height as a fraction of HEIGHT, how
# far out from the eye it starts, thickness). Three full size and three
# smaller ones scattered among them. LIGHTNING_OPACITY lets the smoke show
# through them.
BOLTS = ((0.5, 0.42, 0.75, 0.0, 1.0), (2.6, 0.36, 0.75, 0.0, 1.0),
         (4.4, 0.46, 0.75, 0.0, 1.0), (1.4, 0.22, 0.45, 0.42, 0.7),
         (3.4, 0.2, 0.55, 0.5, 0.7), (5.7, 0.24, 0.4, 0.36, 0.7))
LIGHTNING_OPACITY = 0.4

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 128
scene.cycles.use_denoising = False
scene.view_settings.view_transform = 'Standard'
world = bpy.data.worlds.new('Night studio')
world.use_nodes = True
world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.03, 0.04, 0.06, 1)
scene.world = world


def material(name, color, roughness=0.4, emission=None, strength=0.0,
             rim=None, rim_strength=0.0):
    """Principled material, optionally with a Fresnel-driven glowing rim
    (as in build-heroic.py)."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (*color, 1)
    bsdf.inputs['Roughness'].default_value = roughness
    if emission:
        bsdf.inputs['Emission Color'].default_value = (*emission, 1)
        bsdf.inputs['Emission Strength'].default_value = strength
    if rim:
        weight = nodes.new('ShaderNodeLayerWeight')
        weight.inputs['Blend'].default_value = 0.3
        power = nodes.new('ShaderNodeMath')
        power.operation = 'POWER'
        power.inputs[1].default_value = 3.5
        glow = nodes.new('ShaderNodeEmission')
        glow.inputs['Color'].default_value = (*rim, 1)
        glow.inputs['Strength'].default_value = rim_strength
        add = nodes.new('ShaderNodeAddShader')
        mix = nodes.new('ShaderNodeMixShader')
        links.new(weight.outputs['Facing'], power.inputs[0])
        links.new(power.outputs[0], mix.inputs['Fac'])
        links.new(bsdf.outputs[0], add.inputs[0])
        links.new(glow.outputs[0], add.inputs[1])
        links.new(bsdf.outputs[0], mix.inputs[1])
        links.new(add.outputs[0], mix.inputs[2])
        links.new(mix.outputs[0], nodes['Material Output'].inputs['Surface'])
    return mat


def tube(name, points, radii, mat, sides=16, flat=1.0):
    """Loft flattened rings along a polyline; radius 0 closes the end."""
    points = [Vector(p) for p in points]
    vertices, rings = [], []
    for i, (center, radius) in enumerate(zip(points, radii)):
        ahead = (points[min(i + 1, len(points) - 1)] - points[max(i - 1, 0)]).normalized()
        side = ahead.cross(Vector((0, 0, 1))).normalized()
        up = side.cross(ahead).normalized()
        if radius == 0:
            rings.append([len(vertices)])
            vertices.append(tuple(center))
            continue
        rings.append(list(range(len(vertices), len(vertices) + sides)))
        for k in range(sides):
            a = 2 * math.pi * k / sides
            vertices.append(tuple(center + side * (radius * math.cos(a))
                                  + up * (radius * flat * math.sin(a))))
    faces = []
    if len(rings[0]) > 1:
        faces.append(tuple(reversed(rings[0])))
    for a, b in zip(rings, rings[1:]):
        if len(a) == 1:
            faces += [(a[0], b[(k + 1) % sides], b[k]) for k in range(sides)]
        elif len(b) == 1:
            faces += [(a[k], a[(k + 1) % sides], b[0]) for k in range(sides)]
        else:
            faces += [(a[k], a[(k + 1) % sides], b[(k + 1) % sides], b[k])
                      for k in range(sides)]
    if len(rings[-1]) > 1:
        faces.append(tuple(rings[-1]))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    # Outward normals, so the volume smoke is filled inside the tube.
    shell = bmesh.new()
    shell.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(shell, faces=shell.faces)
    shell.to_mesh(mesh)
    shell.free()
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    scene.collection.objects.link(obj)
    obj.data.materials.append(mat)
    for face in obj.data.polygons:
        face.use_smooth = True
    return obj


def smoke(name, color):
    """Volume smoke whose density a noise texture breaks into wisps."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.remove(nodes['Principled BSDF'])
    volume = nodes.new('ShaderNodeVolumePrincipled')
    volume.inputs['Color'].default_value = (*color, 1)
    noise = nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 6.0
    noise.inputs['Detail'].default_value = 6.0
    ramp = nodes.new('ShaderNodeMapRange')
    ramp.inputs['From Min'].default_value = 0.35
    ramp.inputs['From Max'].default_value = 0.65
    ramp.inputs['To Min'].default_value = 0.2 * DENSITY
    ramp.inputs['To Max'].default_value = DENSITY
    links.new(noise.outputs['Fac'], ramp.inputs['Value'])
    links.new(ramp.outputs['Result'], volume.inputs['Density'])
    links.new(volume.outputs[0], nodes['Material Output'].inputs['Volume'])
    return mat


smokes = [smoke('Storm grey smoke', (0.06, 0.06, 0.09)),
          smoke('Storm blue-grey smoke', (0.16, 0.16, 0.24))]
glow = material('Storm lightning', (1.0, 0.75, 0.25), emission=(1.0, 0.62, 0.12),
                strength=1.2)

# Counterclockwise outward, seen from above, like the Vortex's own strands.
steps = 120
bands, bolts = [], []
for strand, start, end, band, shade in ARMS:
    points, radii = [], []
    for i in range(steps + 1):
        u = i / steps
        t = start + (end - start) * u
        r = 0.06 + (REACH - BAND * 0.3 - 0.06) * t ** 1.1
        a = strand + TURNS * 2 * math.pi * t
        points.append((r * math.cos(a), r * math.sin(a), 0.05 + HEIGHT * t))
        # A whole arm swells from the eye; a partial one from both its ends.
        swell = math.sin(math.pi * u ** 0.8) if start == 0 else math.sin(math.pi * u)
        radii.append(0.015 + band * swell ** 0.8)
    radii[-1] = 0
    obj = tube('Storm band', points, radii, smokes[shade], flat=FLAT)
    bands.append(obj)
    wobble = obj.modifiers.new('Smoke wobble', 'DISPLACE')
    texture = bpy.data.textures.new('Storm smoke wobble', 'CLOUDS')
    texture.noise_scale = 0.08
    wobble.texture = texture
    wobble.strength = 0.04

# Jagged lightning crackling out of the eye.
for start_angle, length, height, out, size in BOLTS:
    along = Vector((math.cos(start_angle), math.sin(start_angle), 0))
    side = Vector((-along.y, along.x, 0))
    eye = Vector((0, 0, HEIGHT * height)) + along * out
    bolt = [eye]
    for k, swing in enumerate((0.06, -0.07, 0.06, -0.05)):
        f = (k + 1) / 4
        bolt.append(eye + Vector((0, 0, -0.12 * f)) + along * (length * f)
                    + side * (swing * size))
    bolts.append(tube('Storm lightning', bolt, [w * size for w in (0.03, 0.027, 0.023, 0.016, 0)],
         glow, sides=6))

sun = bpy.data.lights.new('Storm sun', 'SUN')
sun.energy = 5.0
sun_obj = bpy.data.objects.new('Storm sun', sun)
sun_obj.rotation_euler = (math.radians(35), 0, math.radians(-30))
scene.collection.objects.link(sun_obj)

camera_data = bpy.data.cameras.new('Top')
camera_data.type = 'ORTHO'
camera_data.ortho_scale = ORTHO
camera = bpy.data.objects.new('Top', camera_data)
target = Vector((0, 0, HEIGHT / 2))
camera.location = target + 10 * Vector((0, -math.cos(math.radians(ELEVATION)),
                                         math.sin(math.radians(ELEVATION))))
camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
scene.collection.objects.link(camera)
scene.camera = camera
scene.render.film_transparent = True
scene.render.resolution_x = scene.render.resolution_y = SIZE
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'



def render(shown, hidden, path):
    for obj in shown:
        obj.hide_render = False
    for obj in hidden:
        obj.hide_render = True
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    image = bpy.data.images.load(str(path), check_existing=False)
    return list(image.pixels)


# The smoke and the lightning are rendered apart and the lightning laid
# over the smoke at LIGHTNING_OPACITY: inside the smoke, a see-through
# material would still be hidden by the smoke behind it.
smoke_pixels = render(bands, bolts, OUT)
bolt_path = OUT.with_name('vortex-storm-lightning.png')
bolt_pixels = render(bolts, bands, bolt_path)
bolt_path.unlink()
pixels = []
for i in range(0, len(smoke_pixels), 4):
    smoke_alpha = smoke_pixels[i + 3]
    bolt_alpha = bolt_pixels[i + 3] * LIGHTNING_OPACITY
    alpha = bolt_alpha + smoke_alpha * (1 - bolt_alpha)
    pixels += [(bolt_pixels[i + c] * bolt_alpha
                + smoke_pixels[i + c] * smoke_alpha * (1 - bolt_alpha)) / alpha
               if alpha > 0 else 0.0 for c in range(3)]
    pixels.append(alpha)
storm = bpy.data.images.new('vortex-storm', SIZE, SIZE, alpha=True)
storm.pixels = pixels
storm.filepath_raw = str(OUT)
storm.file_format = 'PNG'
storm.save()
