"""Effect frames of the Stage 6 Dungeon Core running wild at the time limit:
arms of calamitous smoke reaching out from the core and scattering away.

Built on build-vortex-storm.py: the same volume smoke lofted along spiral
bands and seen from the same steep orthographic camera, but ARMS thin
tentacle-like arms creep low over the floor (HEIGHT) instead of a tall
funnel. Each arm is black smoke over a violet glowing sheath that shows
round its edges, and white-violet lightning crackles between them.

FRAMES frames are written, FPS a second, each as two layers
(frame-NN-smoke.png, frame-NN-light.png): over GROW_FRAMES the arms reach
out from the core; then, over the rest, they let go of it and drift on
outwards, breaking up and thinning away to nothing.

The smoke layer is drawn with normal alpha blending (the black has to
darken the floor); the light layer (the arms' violet glow and the lightning, opaque on
black) with additive blending. The core's eye on the ground is FOOT of the image's
height below its centre, and REACH / ORTHO of its width from the eye is
where the longest arm ends (as VORTEX_STORM_FOOT and VORTEX_STORM_REACH).

    blender --factory-startup --background --threads 12 \\
        --python dev-samples/3d-stage1/build-core-calamity.py -- OUT_DIR [FRAME ...]

FRAME is e.g. frame-07; without any, every frame is written.
OUT_DIR defaults to src/arlq/assets/effects/core-calamity.
"""
from pathlib import Path
import math
import random
import sys

import bmesh
import bpy
from mathutils import Vector

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
OUT_DIR = (Path(ARGS[0]) if ARGS else
           Path(__file__).resolve().parents[2] / 'src' / 'arlq' / 'assets' / 'effects'
           / 'core-calamity')
ONLY = set(ARGS[1:])

REACH, ORTHO, SIZE = 1.0, 3.0, 384
ELEVATION = 75
# The arms creep low and lift their tips a little.
HEIGHT = 0.28
TARGET_Z = 0.12
FOOT = TARGET_Z * math.cos(math.radians(ELEVATION)) / ORTHO
FRAMES, GROW_FRAMES, FPS = 20, 8, 10
# How far the arms drift on as they scatter, as a fraction of their length:
# their tips to SCATTER_HEAD, their roots to SCATTER_TAIL.
SCATTER_HEAD, SCATTER_TAIL = 1.35, 1.0
# How far an arm curls (radians) from the eye to its tip, and how much it
# writhes.
CURL, WRITHE = 2.4, 0.18
BAND, FLAT = 0.055, 0.5
SHEATH, SHEATH_PAD = 1.5, 0.012
SHEATH_FLAT, SHEATH_DROP = 0.25, 0.02
HOLDOUT = 0.8
DENSITY = 45
SAMPLES = 64

rand = random.Random(6)
# (start angle, length as a fraction of REACH, band, writhe phase)
ARMS = []
for k in range(7):
    ARMS.append((2 * math.pi * k / 7 + rand.uniform(-0.25, 0.25),
                 rand.uniform(0.7, 1.0), BAND * rand.uniform(0.7, 1.2),
                 rand.uniform(0, 1)))

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = SAMPLES
scene.cycles.use_denoising = False
scene.view_settings.view_transform = 'Standard'
world = bpy.data.worlds.new('Night studio')
world.use_nodes = True
world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.03, 0.03, 0.05, 1)
scene.world = world


def tube(name, points, radii, mat, sides=14, flat=1.0):
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
    shell = bmesh.new()
    shell.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(shell, faces=shell.faces)
    shell.to_mesh(mesh)
    shell.free()
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    scene.collection.objects.link(obj)
    obj.data.materials.append(mat)
    return obj


def volume(name, color, density, emission=None, strength=0.0, noise_scale=6.0):
    """Volume smoke whose density a noise texture breaks into wisps."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.remove(nodes['Principled BSDF'])
    vol = nodes.new('ShaderNodeVolumePrincipled')
    vol.inputs['Color'].default_value = (*color, 1)
    if emission:
        vol.inputs['Emission Color'].default_value = (*emission, 1)
        vol.inputs['Emission Strength'].default_value = strength
    vol.name = 'Volume'
    noise = nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = noise_scale
    noise.inputs['Detail'].default_value = 6.0
    ramp = nodes.new('ShaderNodeMapRange')
    ramp.name = 'Ramp'
    ramp.inputs['From Min'].default_value = 0.35
    ramp.inputs['From Max'].default_value = 0.65
    ramp.inputs['To Min'].default_value = 0.15 * density
    ramp.inputs['To Max'].default_value = density
    links.new(noise.outputs['Fac'], ramp.inputs['Value'])
    links.new(ramp.outputs['Result'], vol.inputs['Density'])
    links.new(vol.outputs[0], nodes['Material Output'].inputs['Volume'])
    mat['density'], mat['strength'] = density, strength
    return mat


def fade(mat, scatter):
    """Thin `mat`'s smoke out as it scatters (0..1): its noise breaks it into
    ever smaller wisps and its density and glow die away."""
    nodes = mat.node_tree.nodes
    ramp = nodes['Ramp']
    left = (1 - scatter) ** 1.4
    ramp.inputs['From Min'].default_value = 0.35 + 0.3 * scatter
    ramp.inputs['From Max'].default_value = 0.65 + 0.2 * scatter
    ramp.inputs['To Min'].default_value = 0.15 * mat['density'] * (1 - scatter)
    ramp.inputs['To Max'].default_value = mat['density'] * left
    nodes['Volume'].inputs['Emission Strength'].default_value = mat['strength'] * left


def emission(name, color, strength):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.remove(nodes['Principled BSDF'])
    glow = nodes.new('ShaderNodeEmission')
    glow.inputs['Color'].default_value = (*color, 1)
    glow.inputs['Strength'].default_value = strength
    links.new(glow.outputs[0], nodes['Material Output'].inputs['Surface'])
    return mat


black_smoke = volume('Calamity black smoke', (0.02, 0.01, 0.035), DENSITY)
# Barely there as smoke: it is the glow around the black.
violet_sheath = volume('Calamity violet sheath', (0.3, 0.08, 0.5), 0.6,
                       emission=(0.55, 0.15, 1.0), strength=3.0, noise_scale=9.0)
bolt_core = emission('Calamity lightning', (0.95, 0.9, 1.0), 6.0)
bolt_glow = volume('Calamity lightning glow', (0.7, 0.5, 1.0), 4.0,
                   emission=(0.75, 0.5, 1.0), strength=3.0, noise_scale=14.0)
holdout = bpy.data.materials.new('Calamity holdout')
holdout.use_nodes = True
_nodes = holdout.node_tree.nodes
_nodes.remove(_nodes['Principled BSDF'])
holdout.node_tree.links.new(_nodes.new('ShaderNodeHoldout').outputs[0],
                            _nodes['Material Output'].inputs['Surface'])

sun = bpy.data.lights.new('Calamity sun', 'SUN')
sun.energy = 4.0
sun_obj = bpy.data.objects.new('Calamity sun', sun)
sun_obj.rotation_euler = (math.radians(35), 0, math.radians(-30))
scene.collection.objects.link(sun_obj)

camera_data = bpy.data.cameras.new('Top')
camera_data.type = 'ORTHO'
camera_data.ortho_scale = ORTHO
camera = bpy.data.objects.new('Top', camera_data)
target = Vector((0, 0, TARGET_Z))
camera.location = target + 10 * Vector((0, -math.cos(math.radians(ELEVATION)),
                                         math.sin(math.radians(ELEVATION))))
camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
scene.collection.objects.link(camera)
scene.camera = camera
scene.render.film_transparent = True
scene.render.resolution_x = scene.render.resolution_y = SIZE
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'


def arm_point(angle, length, writhe_phase, phase, t):
    r = 0.05 + (REACH * length - 0.05) * t
    wave = WRITHE * t * math.sin(2 * math.pi * (phase + writhe_phase) - 4.0 * t)
    a = angle + CURL * t + wave
    return (r * math.cos(a), r * math.sin(a), 0.04 + HEIGHT * t ** 1.6)


def build(tail, head, scatter, phase):
    """The arms stretched from `tail` to `head` along their length (0 the
    core, 1 a full arm's tip), `scatter` (0..1) of the way to gone, writhing
    at `phase`. Returns (smoke objects, light objects)."""
    smoke, light = [], []
    steps = 90
    grow = min(head, 1.0)
    for mat in (black_smoke, violet_sheath, bolt_glow):
        fade(mat, scatter)
    for angle, length, band, writhe_phase in ARMS:
        points, radii = [], []
        # Short while reaching out; spreading wider as they scatter.
        thick = band * (0.45 + 0.55 * grow) * (1 + 0.8 * scatter)
        for i in range(steps + 1):
            u = i / steps
            points.append(arm_point(angle, length, writhe_phase, phase,
                                    tail + (head - tail) * u))
            profile = u ** 0.5 * (1 - u) ** 0.6 / 0.468
            radii.append(0.01 + thick * profile)
        radii[-1] = 0
        if tail > 0:
            radii[0] = 0
        sheath = [0 if r == 0 else r * SHEATH + SHEATH_PAD for r in radii]
        # Laid flat just under the black arm: seen from above, the glow
        # shows only round its edges.
        under = [(x, y, z - SHEATH_DROP) for x, y, z in points]
        for obj, layer in ((tube('Calamity arm', points, radii, black_smoke, flat=FLAT), smoke),
                           (tube('Calamity sheath', under, sheath, violet_sheath, flat=SHEATH_FLAT), light)):
            wobble = obj.modifiers.new('Smoke wobble', 'DISPLACE')
            texture = bpy.data.textures.new('Calamity wobble', 'CLOUDS')
            texture.noise_scale = 0.08
            wobble.texture = texture
            wobble.strength = 0.03
            layer.append(obj)
        # In the glow layer the arm hides the glow under it outright: the
        # smoke's own wisps would let it through.
        light.append(tube('Calamity arm holdout', points,
                          [r * HOLDOUT for r in radii], holdout, flat=FLAT))
    # Lightning crackling out between the arms, a different few each frame.
    bolt_rand = random.Random(round(head * 1000) * 31 + round(phase * 1000))
    for k in range(round(5 * (1 - scatter) ** 1.5)):
        angle = bolt_rand.uniform(0, 2 * math.pi)
        length = bolt_rand.uniform(0.25, 0.55) * (0.3 + 0.7 * grow)
        out = bolt_rand.uniform(0.0, 0.25) * grow
        along = Vector((math.cos(angle), math.sin(angle), 0))
        side = Vector((-along.y, along.x, 0))
        eye = Vector((0, 0, 0.22)) + along * out
        bolt = [eye]
        for j in range(1, 6):
            f = j / 5
            bolt.append(eye + along * (length * f) + Vector((0, 0, -0.1 * f))
                        + side * bolt_rand.uniform(-0.05, 0.05))
        size = bolt_rand.uniform(0.6, 1.0)
        widths = [w * size for w in (0.012, 0.011, 0.009, 0.007, 0.005, 0)]
        light.append(tube('Calamity bolt', bolt, widths, bolt_core, sides=6))
        light.append(tube('Calamity bolt glow', bolt,
                          [w * 4 + 0.01 if w else 0 for w in widths],
                          bolt_glow, sides=8))
    return smoke, light


def clear(objs):
    for obj in objs:
        mesh = obj.data
        bpy.data.objects.remove(obj)
        bpy.data.meshes.remove(mesh)


def render(shown, hidden, path, glow=False):
    """The smoke layer on a transparent film; the glow layer on black, as
    the light it adds (a glow has next to no alpha to carry it)."""
    scene.render.film_transparent = not glow
    background = world.node_tree.nodes['Background'].inputs['Color']
    background.default_value = (0, 0, 0, 1) if glow else (0.03, 0.03, 0.05, 1)
    for obj in shown:
        obj.hide_render = False
    for obj in hidden:
        obj.hide_render = True
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


def flatten(path):
    """Bake the glow layer's alpha into its colour, opaque: the held-out
    arms leave alpha 0 over stray colour."""
    image = bpy.data.images.load(str(path), check_existing=False)
    pixels = list(image.pixels)
    for i in range(0, len(pixels), 4):
        alpha = pixels[i + 3]
        pixels[i:i + 4] = [pixels[i] * alpha, pixels[i + 1] * alpha,
                           pixels[i + 2] * alpha, 1.0]
    image.pixels = pixels
    image.filepath_raw = str(path)
    image.file_format = 'PNG'
    image.save()
    bpy.data.images.remove(image)


def ease_out(x):
    return 1 - (1 - x) ** 2.2


OUT_DIR.mkdir(parents=True, exist_ok=True)
frames = []
for i in range(FRAMES):
    if i < GROW_FRAMES:
        tail, head, scatter = 0.0, ease_out((i + 1) / GROW_FRAMES), 0.0
    else:
        scatter = (i + 1 - GROW_FRAMES) / (FRAMES - GROW_FRAMES)
        tail = SCATTER_TAIL * ease_out(scatter)
        head = 1.0 + (SCATTER_HEAD - 1.0) * ease_out(scatter)
    # Writhing a full turn of the wave over the whole effect.
    frames.append((f'frame-{i:02d}', tail, head, scatter, i / FRAMES))
for name, tail, head, scatter, phase in frames:
    if ONLY and name not in ONLY:
        continue
    smoke, light = build(tail, head, scatter, phase)
    render(smoke, light, OUT_DIR / f'{name}-smoke.png')
    render(light, smoke, OUT_DIR / f'{name}-light.png', glow=True)
    flatten(OUT_DIR / f'{name}-light.png')
    clear(smoke + light)
print('FOOT', FOOT, 'REACH/ORTHO', REACH / ORTHO)
