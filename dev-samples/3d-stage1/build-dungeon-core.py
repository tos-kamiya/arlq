"""The Stage 6 Dungeon Core for the sprite GUI: an eye in a crystal among
four pillars, in four sizes as the core grows toward bursting.

Run with: blender --background --threads 4 --python dev-samples/3d-stage1/build-dungeon-core.py

The core is shown as `[*]` on three cells side by side. A clear violet
octahedron floats in the middle with an eye hanging inside it, looking at
the camera: an almond-shaped lens with a glowing magenta iris and a black
slit pupil in a pale violet-grey white. Four unnatural pillars stand round
it in a cross, the whole cross turned 30 degrees clockwise seen from above
(YAW) so it does not face straight ahead: square in plan, polished
violet-black, flat-topped, with glowing violet grooves down each face and
glowing bands near the top and foot. The crystal gives off a dark glow:
spikes of smoky light, black at heart and violet at their edges, fading
toward their tips, radiating from it in every direction. There is no base.
It uses the bridgehead's 60-degree orthographic camera and ink outline, and
is fitted so the pillars span FRAME_CELLS cells, centred on a canvas CELLS
wide that leaves room for the rays.

The pillars keep their shape and size in every stage (GROWTH); only their
glow changes. The crystal, eye, rays and inner light grow with the core:
- small: a small, deeper-coloured, less clear crystal with the eye half
  closed, a few short rays and a dim glow;
- medium: the original core;
- large: a crystal rising past the pillar tops, the eye wide open with a
  wider iris, more and longer rays and a strong glow;
- huge: about to burst, the crystal swollen wider than it grows tall,
  nearly touching the pillars and floor, its faces split by glowing cracks
  reaching its middle, and the most rays and glow. The eye stares wide in
  pain: opened almost round, the iris ringed by white all round, the slit
  pupil dilated into a wide lemon shape pointed top and bottom, and
  bloodshot veins creeping in from the rim.

All four images share one canvas, sized for the furthest reach, so the
pillars stay put when the game swaps them.

Writes to OUT (DUNGEON_CORE_OUT in the environment, else
src/arlq/assets/dungeon-core):
  dungeon-core-{small,medium,large,huge}.png
  dungeon-core.json  {"cells": 3, "under": UNDER, "overhang": OVERHANG}
"""
from pathlib import Path
import json
import math
import os
import random

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parent
OUT = Path(os.environ.get('DUNGEON_CORE_OUT',
                          ROOT.parents[1] / 'src' / 'arlq' / 'assets' / 'dungeon-core'))
OUT.mkdir(parents=True, exist_ok=True)
CELL_PIXELS = (300, 400)
UNIT_PIXELS = 300
CELL_W = CELL_PIXELS[0] / UNIT_PIXELS
CELLS = 3
FRAME_CELLS = 1.7
WIDTH = CELL_PIXELS[0] * CELLS
ELEVATION = math.radians(60)
CELL_UP = CELL_PIXELS[1] / UNIT_PIXELS

# The model before it is fitted to the cells.
PILLAR_D, PILLAR_HALF, PILLAR_H = 0.95, 0.17, 2.6
YAW = math.radians(-30)
CRYSTAL_R, CRYSTAL_H, CRYSTAL_Z = 0.62, 0.95, 1.45
EYE_W, EYE_DEPTH = 0.34, 0.40

# What changes as the core grows. scale: crystal width (height too, unless
# height is given; at most about 1.74 before the crystal meets the pillars,
# and 1.47 tall before it meets the floor); eye: eye size; eye_tall: the
# eye's height for its width; lid: how far the upper lid stays open (1 is
# fully open); iris: iris size; pupil: the slit's half width, or with
# lemon, the half width of a dilated lemon-shaped pupil; sclera: the
# white's colour at the iris and at the rim (optional); veins: bloodshot
# veins in the white (optional); rays:
# (count, shortest, longest, width factor); light: the inner point light;
# glow: the pillars' grooves and bands; rim: the crystal's edge glow; tint
# and clear: the crystal's colour and how much of it lets light through;
# cracks: none, or (per face, shortest and longest reach toward the face
# middle, glow strength).
GROWTH = {
    'small': dict(scale=0.6, eye=0.85, eye_tall=0.58, lid=0.3, iris=1.0, pupil=0.10,
                  rays=(9, 0.45, 0.70, 0.8), light=4.0, glow=1.4, rim=1.6,
                  tint=(0.55, 0.32, 0.82), clear=0.80, cracks=None),
    'medium': dict(scale=1.0, eye=1.0, eye_tall=0.58, lid=1.0, iris=1.0, pupil=0.10,
                   rays=(22, 0.75, 1.30, 1.0), light=8.0, glow=3.0, rim=2.5,
                   tint=(0.82, 0.62, 1.0), clear=0.88, cracks=None),
    'large': dict(scale=1.35, eye=1.35, eye_tall=0.68, lid=1.0, iris=1.25, pupil=0.10,
                  rays=(30, 1.05, 1.70, 1.2), light=14.0, glow=5.0, rim=3.4,
                  tint=(0.85, 0.66, 1.0), clear=0.90, cracks=None),
    'huge': dict(scale=1.65, height=1.45, eye=1.7, eye_tall=0.95, lid=1.0, iris=1.0,
                 pupil=0.16, lemon=True, sclera=((0.36, 0.27, 0.38), (0.24, 0.14, 0.24)), veins=True, rays=(36, 1.20, 1.85, 1.35), light=20.0, glow=7.0, rim=4.2,
                 tint=(0.92, 0.72, 1.0), clear=0.90, cracks=(3, 0.62, 0.85, 7.5)),
}

VIEW = Vector((0, math.cos(ELEVATION), -math.sin(ELEVATION)))
IMAGE_UP = Vector((0, math.sin(ELEVATION), math.cos(ELEVATION)))
TOWARD_CAMERA = -VIEW


def material(name, color, roughness=0.65, metallic=0.0, rim_strength=0.0,
             rim_color=(1, 1, 1), emission=None, strength=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (*color, 1)
    bsdf.inputs['Roughness'].default_value = roughness
    bsdf.inputs['Metallic'].default_value = metallic
    if emission:
        bsdf.inputs['Emission Color'].default_value = (*emission, 1)
        bsdf.inputs['Emission Strength'].default_value = strength
    if rim_strength:
        weight = nodes.new('ShaderNodeLayerWeight')
        weight.inputs['Blend'].default_value = 0.3
        power = nodes.new('ShaderNodeMath')
        power.operation = 'POWER'
        power.inputs[1].default_value = 3.5
        glow = nodes.new('ShaderNodeEmission')
        glow.inputs['Color'].default_value = (*rim_color, 1)
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


def math_node(nodes, links, operation, a, b=None):
    node = nodes.new('ShaderNodeMath')
    node.operation = operation
    for index, value in enumerate((a, b)):
        if value is None:
            continue
        if isinstance(value, (int, float)):
            node.inputs[index].default_value = value
        else:
            links.new(value, node.inputs[index])
    return node.outputs[0]


def crystal_material(growth):
    """Clear violet crystal: mostly see-through with a violet tint, glossier
    and glowing violet toward its silhouette."""
    mat = bpy.data.materials.new('Core crystal')
    mat.use_nodes = True
    mat.blend_method = 'BLEND'
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    out = nodes['Material Output']
    nodes.remove(nodes['Principled BSDF'])
    weight = nodes.new('ShaderNodeLayerWeight')
    weight.inputs['Blend'].default_value = 0.45
    clear = nodes.new('ShaderNodeBsdfTransparent')
    clear.inputs['Color'].default_value = (*growth['tint'], 1)
    gloss = nodes.new('ShaderNodeBsdfGlossy')
    gloss.inputs['Color'].default_value = (0.85, 0.75, 1.0, 1)
    gloss.inputs['Roughness'].default_value = 0.05
    surface = nodes.new('ShaderNodeMixShader')
    fac = math_node(nodes, links, 'ADD', math_node(nodes, links, 'MULTIPLY',
                                                   weight.outputs['Fresnel'], 0.6),
                    1.0 - growth['clear'])
    links.new(fac, surface.inputs['Fac'])
    links.new(clear.outputs[0], surface.inputs[1])
    links.new(gloss.outputs[0], surface.inputs[2])
    rim = nodes.new('ShaderNodeEmission')
    rim.inputs['Color'].default_value = (0.55, 0.18, 1.0, 1)
    links.new(math_node(nodes, links, 'MULTIPLY',
                        math_node(nodes, links, 'POWER', weight.outputs['Facing'], 2.5),
                        growth['rim']),
              rim.inputs['Strength'])
    add = nodes.new('ShaderNodeAddShader')
    links.new(surface.outputs[0], add.inputs[0])
    links.new(rim.outputs[0], add.inputs[1])
    links.new(add.outputs[0], out.inputs['Surface'])
    return mat


def eye_material(growth):
    """In the eye's own coordinates (width along X, height along Z, at unit
    half width): a pale violet-grey sclera, a glowing magenta iris and a black vertical
    slit pupil, with a wet gloss. With `veins`, red veins wander in from the
    rim of the white toward the iris."""
    mat = bpy.data.materials.new('Core eye')
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (0.0, 0.0, 0.0, 1)
    bsdf.inputs['Roughness'].default_value = 0.12
    bsdf.inputs['Specular IOR Level'].default_value = 0.9
    bsdf.inputs['Emission Strength'].default_value = 2.4
    coords = nodes.new('ShaderNodeTexCoord')
    split = nodes.new('ShaderNodeSeparateXYZ')
    links.new(coords.outputs['Object'], split.inputs[0])
    x2 = math_node(nodes, links, 'MULTIPLY', split.outputs['X'], split.outputs['X'])
    z2 = math_node(nodes, links, 'MULTIPLY', split.outputs['Z'], split.outputs['Z'])
    radius = math_node(nodes, links, 'SQRT', math_node(nodes, links, 'ADD', x2, z2))
    iris = growth['iris']
    if growth.get('lemon'):
        # |x| < w (1 - (z / h)^2): widest across the middle, pointed at
        # the top and bottom.
        tall = 0.34 * iris
        pupil = math_node(nodes, links, 'LESS_THAN', math_node(
            nodes, links, 'ABSOLUTE', split.outputs['X']), math_node(
            nodes, links, 'MULTIPLY', math_node(
                nodes, links, 'SUBTRACT', 1.0, math_node(nodes, links, 'DIVIDE', z2, tall ** 2)),
            growth['pupil']))
        # A pupil this wide would mirror the glare; keep it black.
        links.new(math_node(nodes, links, 'MULTIPLY', math_node(
            nodes, links, 'SUBTRACT', 1.0, pupil), 0.9),
                  bsdf.inputs['Specular IOR Level'])
    else:
        pupil = math_node(nodes, links, 'LESS_THAN', math_node(
            nodes, links, 'ADD', math_node(nodes, links, 'DIVIDE', x2, growth['pupil'] ** 2),
            math_node(nodes, links, 'DIVIDE', z2, (0.38 * iris) ** 2)), 1.0)
    ramp = nodes.new('ShaderNodeValToRGB')
    elements = ramp.color_ramp.elements
    elements[0].position, elements[0].color = 0.0, (1.0, 0.62, 0.85, 1)
    elements[1].position, elements[1].color = 0.30 * iris, (0.85, 0.08, 0.50, 1)
    inner, outer = growth.get('sclera', ((0.30, 0.22, 0.40), (0.18, 0.12, 0.26)))
    for position, color in ((0.35 * iris, (0.15, 0.0, 0.10, 1)),
                            (0.39 * iris, (*inner, 1)),
                            (1.0, (*outer, 1))):
        element = elements.new(position)
        element.color = color
    links.new(radius, ramp.inputs['Fac'])
    colour = ramp.outputs['Color']
    if growth.get('veins'):
        # Thin wavering lines running out from the iris, by angle round
        # the centre bent by noise, strongest toward the rim.
        noise = nodes.new('ShaderNodeTexNoise')
        noise.inputs['Scale'].default_value = 4.0
        noise.inputs['Detail'].default_value = 3.0
        links.new(coords.outputs['Object'], noise.inputs['Vector'])
        angle = math_node(nodes, links, 'ARCTAN2', split.outputs['Z'], split.outputs['X'])
        wave = math_node(nodes, links, 'ABSOLUTE', math_node(
            nodes, links, 'SINE', math_node(nodes, links, 'ADD', math_node(
                nodes, links, 'MULTIPLY', angle, 11.0), math_node(
                nodes, links, 'MULTIPLY', noise.outputs['Fac'], 9.0))))
        line = math_node(nodes, links, 'LESS_THAN', wave, 0.24)
        reach = nodes.new('ShaderNodeMapRange')
        reach.inputs['From Min'].default_value = 0.42 * iris
        reach.inputs['From Max'].default_value = 0.7
        links.new(radius, reach.inputs['Value'])
        vein = math_node(nodes, links, 'MULTIPLY', line, reach.outputs['Result'])
        red = nodes.new('ShaderNodeMix')
        red.data_type = 'RGBA'
        links.new(vein, red.inputs['Factor'])
        links.new(colour, red.inputs['A'])
        red.inputs['B'].default_value = (0.75, 0.0, 0.05, 1)
        colour = red.outputs['Result']
    black = nodes.new('ShaderNodeMix')
    black.data_type = 'RGBA'
    links.new(pupil, black.inputs['Factor'])
    links.new(colour, black.inputs['A'])
    black.inputs['B'].default_value = (0, 0, 0, 1)
    links.new(black.outputs['Result'], bsdf.inputs['Emission Color'])
    return mat


def dark_light_material():
    """Smoky dark light: black where it faces the camera, violet toward its
    edges, faint, fading out toward the tip (UV Y runs from 0 at the base
    to 1) and toward the ridges between its sides (UV X runs 0 to 1 across
    each side), so it reads as a blurred haze rather than a spike."""
    mat = bpy.data.materials.new('Dark light')
    mat.use_nodes = True
    mat.blend_method = 'BLEND'
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    out = nodes['Material Output']
    nodes.remove(nodes['Principled BSDF'])
    coords = nodes.new('ShaderNodeTexCoord')
    split = nodes.new('ShaderNodeSeparateXYZ')
    links.new(coords.outputs['UV'], split.inputs[0])
    along = math_node(nodes, links, 'POWER', math_node(
        nodes, links, 'SUBTRACT', 1.0, split.outputs['Y']), 2.0)
    across = math_node(nodes, links, 'POWER', math_node(
        nodes, links, 'SINE', math_node(nodes, links, 'MULTIPLY', split.outputs['X'], math.pi)),
        1.5)
    opacity = math_node(nodes, links, 'MULTIPLY', math_node(
        nodes, links, 'MULTIPLY', along, across), 0.6)
    weight = nodes.new('ShaderNodeLayerWeight')
    weight.inputs['Blend'].default_value = 0.5
    fringe = nodes.new('ShaderNodeValToRGB')
    fringe.color_ramp.elements[0].position = 0.45
    fringe.color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1)
    fringe.color_ramp.elements[1].position = 0.95
    fringe.color_ramp.elements[1].color = (0.45, 0.10, 0.85, 1)
    links.new(weight.outputs['Facing'], fringe.inputs['Fac'])
    body = nodes.new('ShaderNodeEmission')
    body.inputs['Strength'].default_value = 1.4
    links.new(fringe.outputs['Color'], body.inputs['Color'])
    clear = nodes.new('ShaderNodeBsdfTransparent')
    mix = nodes.new('ShaderNodeMixShader')
    links.new(opacity, mix.inputs['Fac'])
    links.new(clear.outputs[0], mix.inputs[1])
    links.new(body.outputs[0], mix.inputs[2])
    links.new(mix.outputs[0], out.inputs['Surface'])
    return mat


def finish(obj, name, mat, bevel=0.0):
    obj.name = name
    obj.data.materials.append(mat)
    if bevel:
        mod = obj.modifiers.new('Soft edges', 'BEVEL')
        mod.width = bevel
        mod.segments = 2
    return obj


def mesh(name, vertices, faces, mat, uvs=None):
    data = bpy.data.meshes.new(name)
    data.from_pydata(vertices, [], faces)
    if uvs:
        layer = data.uv_layers.new()
        for loop in data.loops:
            layer.data[loop.index].uv = uvs[loop.vertex_index]
    data.update()
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    return finish(obj, name, mat)


def box(name, x0, x1, y0, y1, z0, z1, mat, bevel=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=((x0 + x1) / 2, (y0 + y1) / 2,
                                                      (z0 + z1) / 2))
    obj = bpy.context.object
    obj.scale = (x1 - x0, y1 - y0, z1 - z0)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return finish(obj, name, mat, bevel)


def pillars(stone, glow):
    """Four square, flat-topped pillars in a cross round the crystal, with
    glowing grooves down each face and glowing bands near the top and foot."""
    h, groove, proud = PILLAR_HALF, 0.022, 0.006
    z0, z1 = 0.42, PILLAR_H - 0.42
    for x, y in ((0, -PILLAR_D), (PILLAR_D, 0), (0, PILLAR_D), (-PILLAR_D, 0)):
        box('Pillar', x - h, x + h, y - h, y + h, 0, PILLAR_H, stone, 0.012)
        for x0, x1, y0, y1 in ((-groove, groove, -h - proud, -h + 0.01),
                               (-groove, groove, h - 0.01, h + proud),
                               (-h - proud, -h + 0.01, -groove, groove),
                               (h - 0.01, h + proud, -groove, groove)):
            box('Pillar groove', x + x0, x + x1, y + y0, y + y1, z0, z1, glow)
        for z in (0.20, PILLAR_H - 0.24):
            box('Pillar band', x - h - proud, x + h + proud, y - h - proud,
                y + h + proud, z, z + 0.035, glow)


def eye(growth):
    """An almond-shaped lens: a sphere flattened front to back and pinched
    to points at its corners, turned to look at the camera. Its upper half
    is pressed down to `lid` of its height, as an eye half closed."""
    bpy.ops.mesh.primitive_uv_sphere_add(segments=40, ring_count=20, radius=1.0)
    obj = bpy.context.object
    for v in obj.data.vertices:
        x, y, z = v.co
        z *= growth['eye_tall'] * math.sqrt(max(0.0, 1 - x * x))
        if z > 0:
            z *= growth['lid']
        v.co = (x, y * EYE_DEPTH, z)
    bpy.ops.object.shade_smooth()
    obj.scale = (EYE_W * growth['eye'],) * 3
    obj.location = (0, 0, CRYSTAL_Z)
    # Its front (-Y) turned toward the camera, its height (Z) up the image.
    obj.rotation_euler = (-ELEVATION, 0, 0)
    return finish(obj, 'Core eye', eye_material(growth))


def ray(direction, length, width, base_r, mat):
    """A four-sided spike of dark light from inside the crystal outward."""
    direction = direction.normalized()
    side = direction.cross(Vector((0, 0, 1)))
    if side.length < 0.1:
        side = direction.cross(Vector((1, 0, 0)))
    side.normalize()
    other = direction.cross(side).normalized()
    centre = Vector((0, 0, CRYSTAL_Z))
    base = centre + direction * base_r * 0.45
    tip = centre + direction * length
    corners = [base + (side * sx + other * sy) * width
               for sx, sy in ((1, 0), (0, 1), (-1, 0), (0, -1))]
    obj = mesh('Dark ray', [*corners, tip], [(0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4)],
               mat, uvs=[(0, 0), (1, 0), (0, 0), (1, 0), (0.5, 1)])
    obj.visible_shadow = False
    return obj


def cracks(vertices, faces, mat, rng, per_face, shortest, longest):
    """Glowing cracks over the crystal's faces: jagged lines starting at the
    face corners and running in toward the middle, some forking, laid just
    above the surface. They stop short of the face centre so the eye behind
    stays clear."""
    strips = []
    for face in faces:
        corners = [Vector(vertices[i]) for i in face]
        normal = (corners[1] - corners[0]).cross(corners[2] - corners[0]).normalized()
        centre = sum(corners, Vector()) / 3
        if normal.dot(centre - Vector((0, 0, CRYSTAL_Z))) < 0:
            normal = -normal

        def at(weights):
            return sum((c * w for c, w in zip(corners, weights)), Vector()) + normal * 0.006

        for start in rng.sample(range(3), per_face):
            point = [1.0 if k == start else 0.0 for k in range(3)]
            reach = rng.uniform(shortest, longest)
            path = [list(point)]
            for step in range(1, 5):
                t = reach * step / 4
                aim = [(1 - t) * (1.0 if k == start else 0.0) + t / 3 for k in range(3)]
                jitter = [rng.uniform(-0.07, 0.07) for _ in range(3)]
                mean = sum(jitter) / 3
                point = [max(0.02, a + j - mean) for a, j in zip(aim, jitter)]
                total = sum(point)
                path.append([p / total for p in point])
            lines = [path]
            if rng.random() < 0.6:
                fork = path[2]
                other = [k for k in range(3) if k != start][rng.randrange(2)]
                end = [0.75 * f + (0.25 if k == other else 0.0) for k, f in enumerate(fork)]
                lines.append([fork, end])
            for line in lines:
                for a, b in zip(line, line[1:]):
                    strips.append((at(a), at(b), normal))
    verts, quads = [], []
    for k, (a, b, normal) in enumerate(strips):
        across = (b - a).cross(normal).normalized() * 0.011
        verts += [a - across, a + across, b + across, b - across]
        quads.append((4 * k, 4 * k + 1, 4 * k + 2, 4 * k + 3))
    obj = mesh('Core cracks', verts, quads, mat)
    obj.visible_shadow = False
    return obj


def render(stage, canvas=None):
    """Builds and renders the core at `stage`. `canvas` gives the (UNDER,
    OVERHANG) to render into; without it they are worked out from this
    stage's own reach. Returns the (UNDER, OVERHANG) used."""
    growth = GROWTH[stage]
    rng = random.Random(6)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 128
    scene.cycles.use_denoising = False
    scene.cycles.sample_clamp_indirect = 2.0
    scene.cycles.transparent_max_bounces = 32
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'Medium High Contrast'
    scene.render.resolution_x = WIDTH
    scene.render.film_transparent = True
    world = bpy.data.worlds.new('Night studio')
    world.use_nodes = True
    world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.05, 0.06, 0.08, 1)
    scene.world = world

    stone = material('Polished black-violet stone', (0.035, 0.025, 0.05), roughness=0.28,
                     rim_strength=0.35, rim_color=(0.6, 0.45, 0.9))
    groove = material('Violet glow', (0.4, 0.15, 0.7), emission=(0.60, 0.20, 1.0),
                      strength=growth['glow'])
    dark_light = dark_light_material()

    pillars(stone, groove)

    # The octahedron, taller than wide, floating and turned a little.
    r = CRYSTAL_R * growth['scale']
    h = CRYSTAL_H * growth.get('height', growth['scale'])
    ring = [(r * math.cos(a), r * math.sin(a), CRYSTAL_Z)
            for a in (math.radians(20 + 90 * k) for k in range(4))]
    octa_vertices = ring + [(0, 0, CRYSTAL_Z + h), (0, 0, CRYSTAL_Z - h)]
    octa_faces = [(0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4),
                  (1, 0, 5), (2, 1, 5), (3, 2, 5), (0, 3, 5)]
    octa = mesh('Core crystal', octa_vertices, octa_faces, crystal_material(growth))
    octa.visible_shadow = False
    core_eye = eye(growth)
    core_eye.visible_shadow = False
    if growth['cracks']:
        per_face, shortest, longest, strength = growth['cracks']
        crack_glow = material('Crack glow', (0.9, 0.5, 1.0), emission=(1.0, 0.55, 0.95),
                              strength=strength)
        cracks(octa_vertices, octa_faces, crack_glow, random.Random(11), per_face,
               shortest, longest)

    # Turn the cross of pillars about the crystal.
    bpy.context.view_layer.update()
    pillar_parts = [obj for obj in scene.objects if obj.name.startswith('Pillar')]
    turn = Matrix.Rotation(YAW, 4, 'Z')
    for obj in pillar_parts:
        obj.matrix_world = turn @ obj.matrix_world

    # Spikes of dark light in every direction, spread evenly over a sphere,
    # leaving out those coming straight at the camera so the eye stays clear.
    count, shortest, longest, width = growth['rays']
    golden = math.pi * (3 - math.sqrt(5))
    for k in range(count):
        z = 1 - 2 * (k + 0.5) / count
        ring_r = math.sqrt(1 - z * z)
        a = golden * k + rng.uniform(-0.25, 0.25)
        direction = Vector((ring_r * math.cos(a), ring_r * math.sin(a), z))
        if direction.dot(TOWARD_CAMERA) > 0.7:
            continue
        ray(direction, rng.uniform(shortest, longest), rng.uniform(0.07, 0.11) * 1.5 * width,
            r, dark_light)

    # A soft violet light inside so the pillars' inner faces catch the glow.
    bpy.ops.object.light_add(type='POINT', location=(0, 0, CRYSTAL_Z))
    core_light = bpy.context.object
    core_light.data.energy, core_light.data.color = growth['light'], (0.6, 0.25, 1.0)
    core_light.data.shadow_soft_size = 0.2

    # Fit so the pillars span FRAME_CELLS cells and find the overhangs.
    bpy.context.view_layer.update()
    pillar_points = [obj.matrix_world @ v.co for obj in pillar_parts for v in obj.data.vertices]
    all_points = [obj.matrix_world @ v.co for obj in scene.objects if obj.type == 'MESH'
                  for v in obj.data.vertices]
    x_lo, x_hi = min(p.x for p in pillar_points), max(p.x for p in pillar_points)
    fit = FRAME_CELLS * CELL_W / (x_hi - x_lo)
    shrink = Matrix.Scale(fit, 4) @ Matrix.Translation(-Vector(((x_lo + x_hi) / 2, 0, 0)))
    for obj in scene.objects:
        obj.matrix_world = shrink @ obj.matrix_world
    core_light.data.energy *= fit * fit
    ups = [(shrink @ p).y * math.sin(ELEVATION) + (shrink @ p).z * math.cos(ELEVATION)
           for p in all_points]
    rights = [(shrink @ p).x for p in all_points]
    margin = 0.03
    under = math.ceil(max(0.0, -min(ups) / CELL_UP + margin) * 20) / 20
    overhang = math.ceil(max(0.0, max(ups) / CELL_UP - 1 + margin) * 20) / 20
    spill = math.ceil(max(0.0, max(abs(x) for x in rights) / CELL_W - CELLS / 2 + margin)
                      * 20) / 20
    print(f'dungeon core {stage}: scale {fit:.3f}, reach under {under}, '
          f'overhang {overhang}, rays past the cells {spill}')
    if canvas is not None:
        under, overhang = canvas
    scene.render.resolution_y = round(CELL_PIXELS[1] * (under + 1 + overhang))

    for pos, power, size, color in [((-3, 3, 9), 420, 1.5, (1.0, 0.93, 0.85)),
                                     ((6, -3, 4), 120, 6, (0.6, 0.75, 1.0)),
                                     ((-6, 6, 4), 300, 3, (0.55, 0.8, 1.0)),
                                     ((6, 6, 4), 300, 3, (1.0, 0.7, 0.9))]:
        bpy.ops.object.light_add(type='AREA', location=pos)
        light = bpy.context.object
        light.data.energy, light.data.size, light.data.color = power, size, color
        light.data.cycles.cast_shadow = pos == (-3, 3, 9)
        light.rotation_euler = (Vector((0, 0, 0)) - light.location).to_track_quat(
            '-Z', 'Y').to_euler()

    height = CELL_UP * (under + 1 + overhang)
    frame_centre = IMAGE_UP * (height / 2 - under * CELL_UP)
    bpy.ops.object.camera_add(location=frame_centre - VIEW * 20)
    camera = bpy.context.object
    camera.rotation_euler = VIEW.to_track_quat('-Z', 'Y').to_euler()
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = max(height, CELL_W * CELLS)
    scene.camera = camera

    # Ink outline on the pillars and crystal only; the rays and cracks stay soft.
    scene.render.use_freestyle = True
    settings = scene.view_layers[0].freestyle_settings
    lines = settings.linesets[0] if settings.linesets else settings.linesets.new('Outline')
    lines.select_silhouette = lines.select_border = False
    lines.select_external_contour = True
    lines.select_crease = False
    lines.select_by_collection = True
    outlined = bpy.data.collections.new('Outlined')
    scene.collection.children.link(outlined)
    for obj in list(scene.objects):
        if obj.type == 'MESH' and obj.name.startswith(('Pillar', 'Core crystal')):
            for owner in obj.users_collection:
                owner.objects.unlink(obj)
            outlined.objects.link(obj)
    lines.collection = outlined
    lines.linestyle = bpy.data.linestyles.new('Ink outline')
    lines.linestyle.color = (0.04, 0.05, 0.07)
    lines.linestyle.thickness = 4.0
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.filepath = str(OUT / f'dungeon-core-{stage}.png')
    bpy.ops.render.render(write_still=True)
    return under, overhang


# The huge core reaches furthest, so it sets the canvas the others share.
UNDER, OVERHANG = render('huge')
for name in ('large', 'medium', 'small'):
    render(name, (UNDER, OVERHANG))
(OUT / 'dungeon-core.json').write_text(json.dumps({'cells': CELLS, 'under': UNDER,
                                                   'overhang': OVERHANG}) + '\n')
