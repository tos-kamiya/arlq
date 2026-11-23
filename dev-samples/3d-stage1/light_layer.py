"""The light layer of a rendered sprite, for Blender build scripts.

A sprite with light sources of its own (a fire, a glowing crystal) is
rendered twice: as usual, and with its point lights out and its glowing
surfaces black. What the first adds to the second is the light those
sources give, their own glow and what they cast around them. The light
layer is the first image scaled by the share of that light in each pixel
(by luminance), so the glowing surfaces keep almost all of it and the
surroundings as much as the light reaches them. The game dims the sprite
for an explored cell out of view and adds this layer back by the amount it
dimmed, so the light keeps its brightness and colour.
"""
from array import array

import bpy

# Light differences below this (0..1) are taken as render noise.
LIGHT_FLOOR = 0.02


def _rgba_pixels(path):
    image = bpy.data.images.load(str(path))
    pixels = array('f', bytes(4 * len(image.pixels)))
    image.pixels.foreach_get(pixels)
    size = tuple(image.size)
    bpy.data.images.remove(image)
    return pixels, size


def _luminance(r, g, b):
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def write_light_layer(lit_path, unlit_path, out_path, floor=LIGHT_FLOOR):
    """Write to `out_path` the light layer of `lit_path` against `unlit_path`
    (premultiplied), clear where the light adds less than `floor`."""
    lit, size = _rgba_pixels(lit_path)
    unlit, _ = _rgba_pixels(unlit_path)
    light_pixels = array('f', bytes(4 * len(lit)))
    for i in range(0, len(lit), 4):
        a, b = lit[i + 3], unlit[i + 3]
        full = [lit[i + k] * a for k in range(3)]
        added = [max(0.0, full[k] - unlit[i + k] * b) for k in range(3)]
        brightness = _luminance(*full)
        if max(added) < floor or brightness <= 0.0:
            continue
        share = min(1.0, _luminance(*added) / brightness)
        light_pixels[i:i + 4] = array('f', (*(c * share for c in full), 1.0))
    light_image = bpy.data.images.new('Light layer', *size, alpha=True)
    light_image.pixels.foreach_set(light_pixels)
    light_image.filepath_raw = str(out_path)
    light_image.file_format = 'PNG'
    light_image.save()
    bpy.data.images.remove(light_image)
