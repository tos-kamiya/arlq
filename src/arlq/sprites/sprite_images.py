"""Image generators for the sprite frontend; they do not depend on SpriteUI."""

import math

import pyglet

from .. import defs as d

# Followers walking with the player (party members, the Javelin Elf and the
# cat) are drawn at this size, never enlarged as neighbors, so they do not
# look larger than the player. Their outer ink outline is faded too: dark
# pixels (luminance below FOLLOWER_INK) within FOLLOWER_OUTLINE_BAND pixels
# of the image's transparent area keep FOLLOWER_OUTLINE_KEEP of their alpha.
FOLLOWER_SCALE = 0.85
FOLLOWER_INK = 70
FOLLOWER_OUTLINE_BAND = 4
FOLLOWER_OUTLINE_KEEP = 0.35
MIPMAP_LOD_BIAS = -1.0
# Ground disc under each sprite (radius: see GROUND_DISC_RADIUS in sprite_funcs):
# vertical squash for the 60-degree view, opacity at the centre, how quickly
# it fades toward the rim, and its texture size.
GROUND_DISC_FLATTEN = math.sin(math.radians(60))
GROUND_DISC_ALPHA = 1.0
GROUND_DISC_FALLOFF = 0.8
GROUND_DISC_TEXELS = 64
# Fairies stand inside a faint green pillar of light: an open cylinder on
# the ground disc's ellipse, seen at the same 60-degree view. Radius and side
# height in cell widths; peak opacity of the far wall (behind the sprite) and
# the near wall (over it); the sides glow brighter, and both fade upward.
PILLAR_RADIUS = 0.8
PILLAR_HEIGHT = 2.0
PILLAR_BACK_ALPHA = 0.9
PILLAR_FRONT_ALPHA = 0.4
PILLAR_EDGE = 0.45
PILLAR_FADE = 1.1
# For the turn after a respawn, the character stands in a taller column of
# light in its ground disc's main color, with helical bands twisting up the
# column. Its near wall (the outside) is brighter than the far wall seen
# through it (the inside). Bands around it, their twist in turns over the full
# height, the angle of one band's foot (0 east, increasing toward the viewer),
# and the brightness between bands. Each band is leaf-shaped: its width (a
# fraction of the band period) peaks halfway up and tapers to a point at both
# ends, the taper exponent shaping its curve.
RESPAWN_COLUMN_RADIUS = 0.7
RESPAWN_COLUMN_HEIGHT = 2.15
RESPAWN_COLUMN_BACK_ALPHA = 0.4
RESPAWN_COLUMN_FRONT_ALPHA = 0.75
RESPAWN_COLUMN_FADE = 0.7
RESPAWN_COLUMN_EDGE = 0.8
RESPAWN_COLUMN_BANDS = 5
RESPAWN_COLUMN_TWIST = 1 / 3
RESPAWN_COLUMN_START = math.radians(360 / 10)
RESPAWN_COLUMN_BAND_WIDTH = 0.6
RESPAWN_COLUMN_BAND_TAPER = 0.7
RESPAWN_COLUMN_GAP_SHADE = 0.15
RESPAWN_COLUMN_TEXELS = 96
# The floor fades darker toward the field's outer walls so the scrolled view's
# left and right ends read as the end of the map: (shade at the wall's inner
# face, cells until full brightness) for the sides and for the top and bottom.
# Corners take the darker of the two. The fade is a smooth, linearly filtered
# multiply layer over the floor, so walls and characters keep their colors.
EDGE_FLOOR_SIDE_FADE = (0.7, 3.5)
EDGE_FLOOR_END_FADE = (0.7, 1.5)
EDGE_FLOOR_TEXELS_PER_CELL = 4
# Barrier image (see the barrier comment in sprite_funcs): texture size,
# height in cell heights, and opacity.
BARRIER_TEXELS = (48, 96)
BARRIER_HEIGHT = 1.5
BARRIER_ALPHA = 0.9
# Gap between the plate and the cell's edges, and height of the light sheets.
BARRIER_INSET = 0.1
BARRIER_SHEET_HEIGHT = 0.55
# Peak strength of the plate's inside and rim, the front and back sheets, and
# the vertical seams where the sheets meet.
BARRIER_PLATE = (0.22, 0.75)
BARRIER_SHEETS = (0.55, 0.45)
BARRIER_SEAM = 0.6
# Per variant: shimmer phase and sparks as (across, height in sheet heights).
BARRIER_SHIMMER = (0.0, 0.5)
BARRIER_SPARKS = (((0.3, 0.45), (0.62, 0.8), (0.78, 0.3)),
                  ((0.22, 0.7), (0.5, 0.35), (0.72, 0.6)))


def _luminance(color):
    r, g, b = color
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def pillar_image(side, height=PILLAR_HEIGHT / PILLAR_RADIUS, peaks=None,
                 fade=PILLAR_FADE, band=None, width=GROUND_DISC_TEXELS, edge=PILLAR_EDGE):
    """One wall ('back' or 'front') of an open light cylinder, white with alpha.

    The image spans the cylinder's width and, from the bottom of its ground
    ellipse, the side height (in radii) plus that ellipse; the tint is applied
    when drawn. `band(angle, t)` scales the opacity at an angle around the
    cylinder (0 east, pi/2 nearest the viewer) and height fraction t.
    """
    flatten = GROUND_DISC_FLATTEN
    rows = round(width * (height + 2 * flatten) / 2)
    back, front = peaks or (PILLAR_BACK_ALPHA, PILLAR_FRONT_ALPHA)
    peak = back if side == 'back' else front
    rgba = bytearray()
    for row in range(rows):
        v = (row + 0.5) / rows * (height + 2 * flatten) - flatten
        for col in range(width):
            u = (col + 0.5) / width * 2 - 1
            depth = math.sqrt(max(0.0, 1 - u * u))
            # The far wall rises from the ellipse's upper (northern) arc.
            t = (v - (depth if side == 'back' else -depth) * flatten) / height
            alpha = 0.0
            if 0 <= t <= 1:
                rim = min(1.0, (1 - abs(u)) / 0.06)
                alpha = (peak * rim * min(1.0, edge / math.sqrt(1 - u * u + 0.02))
                         * (1 - t) ** fade)
                if band is not None:
                    angle = math.acos(max(-1.0, min(1.0, u)))
                    alpha *= band(angle if side == 'front' else -angle, t)
            rgba += bytes((255, 255, 255, round(255 * alpha)))
    return pyglet.image.ImageData(width, rows, 'RGBA', bytes(rgba), pitch=width * 4)


def respawn_column_image(side, gaps=False):
    """A respawn column wall: its helical bands, or with `gaps` the space between."""
    def band(angle, t):
        phase = RESPAWN_COLUMN_BANDS * (angle - RESPAWN_COLUMN_START
                                        + 2 * math.pi * RESPAWN_COLUMN_TWIST * t)
        # Distance from the nearest band centre, as a fraction of the period.
        offset = abs((phase / (2 * math.pi) + 0.5) % 1 - 0.5)
        half_width = RESPAWN_COLUMN_BAND_WIDTH / 2 * math.sin(math.pi * t) ** RESPAWN_COLUMN_BAND_TAPER
        value = max(0.0, min(1.0, (half_width - offset) / 0.06 + 0.5))
        return 1 - value if gaps else value
    return pillar_image(
        side, RESPAWN_COLUMN_HEIGHT / RESPAWN_COLUMN_RADIUS,
        (RESPAWN_COLUMN_BACK_ALPHA, RESPAWN_COLUMN_FRONT_ALPHA),
        RESPAWN_COLUMN_FADE, band, RESPAWN_COLUMN_TEXELS, RESPAWN_COLUMN_EDGE,
    )


def smoke_image(barrier):
    """A white copy of `barrier` with the same shape, for the cooled smoke."""
    width, height = barrier.width, barrier.height
    rgba = bytearray(barrier.get_data('RGBA', width * 4))
    for offset in range(0, len(rgba), 4):
        rgba[offset:offset + 3] = b'\xff\xff\xff'
    return pyglet.image.ImageData(width, height, 'RGBA', bytes(rgba), pitch=width * 4)


def barrier_image(variant, scale=1.0):
    """A magic barrier: a glowing plate on the floor with light rising from it.

    Seen at the sprites' 60-degree view, the plate covers the cell inside a
    small inset, bright along its rim. Sheets of light rise from its near
    (front) and far (back) edges, and the side sheets show edge-on as bright
    seams; the sheets fade upward and shimmer in faint vertical bands. Parts
    combine like light so the back sheet shows through the front one. The
    image is drawn additively from the cell's bottom; `variant` (0 or 1)
    shifts the shimmer and sparks so neighbouring cells do not repeat.
    `scale` shrinks the plate about the cell's centre and the sheets' height.
    """
    width, height = BARRIER_TEXELS
    cell = 1 / BARRIER_HEIGHT  # one cell height, in image fractions
    inset = 0.5 - (0.5 - BARRIER_INSET) * scale
    near, far = inset * cell, (1 - inset) * cell
    sheet = BARRIER_SHEET_HEIGHT * scale * cell
    phase = BARRIER_SHIMMER[variant]
    sparks = [(0.5 + (u - 0.5) * scale, t) for u, t in BARRIER_SPARKS[variant]]
    plate_color, low, high = (255, 125, 30), (255, 150, 45), (255, 85, 10)
    rgba = bytearray()
    for row in range(height):
        v = (row + 0.5) / height
        for col in range(width):
            u = (col + 0.5) / width
            parts = []  # (strength, how far up the sheets, 0..1)
            inside_u = inset <= u <= 1 - inset
            # Distance to the plate's rim, in cell widths (v rescaled to cells).
            rim = min(u - inset, 1 - inset - u, (v - near) / cell, (far - v) / cell)
            if rim >= 0:
                inner, edge = BARRIER_PLATE
                parts.append((inner + (edge - inner) * max(0.0, 1 - rim / 0.06), 0.0))
            elif rim > -0.05:
                parts.append((BARRIER_PLATE[1] * (1 + rim / 0.05) ** 2, 0.0))
            wave_u = 0.5 + (u - 0.5) / scale  # across the full-size plate
            shimmer = 0.75 + 0.25 * math.sin(2 * math.pi * (wave_u * 3 + phase))
            for base, peak in ((near, BARRIER_SHEETS[0]), (far, BARRIER_SHEETS[1])):
                t = (v - base) / sheet
                if inside_u and 0 <= t < 1:
                    parts.append((peak * shimmer * (1 - t) ** 1.6, t))
            # Side sheets seen edge-on: thin seams from the front edge to the
            # top of the back sheet.
            t = (v - near) / (far - near + sheet)
            if 0 <= t < 1:
                for side in (inset, 1 - inset):
                    across = abs(u - side) / 0.03
                    if across < 1:
                        top = max(0.0, (v - far) / sheet)
                        parts.append((BARRIER_SEAM * (1 - across ** 2) * (1 - top) ** 1.6,
                                      top))
            for spark_u, spark_t in sparks:
                d2 = ((u - spark_u) / 0.035) ** 2 + ((v - near - spark_t * sheet) / 0.02) ** 2
                if d2 < 1:
                    parts.append((0.8 * (1 - d2), spark_t))
            clear, weight, along = 1.0, 0.0, 0.0
            for value, t in parts:
                clear *= 1 - min(1.0, value)
                weight += value
                along += value * t
            strength = 1 - clear
            if weight > 0 and along == 0:
                color = plate_color
            else:
                mix = min(1.0, along / weight) if weight > 0 else 1.0
                color = [round(a + (b - a) * mix) for a, b in zip(low, high)]
            rgba += bytes((*color, round(255 * min(1.0, BARRIER_ALPHA * strength))))
    return pyglet.image.ImageData(width, height, 'RGBA', bytes(rgba), pitch=width * 4)


def ground_disc_image(half=None):
    """White disc whose opacity fades from the centre to a transparent rim.

    `half` keeps only the 'upper-right' or 'lower-left' side of the diagonal.
    """
    size = GROUND_DISC_TEXELS
    rgba = bytearray()
    for row in range(size):
        for col in range(size):
            u, v = (col + 0.5) / size * 2 - 1, (row + 0.5) / size * 2 - 1
            r = math.hypot(u, v)
            alpha = GROUND_DISC_ALPHA * max(0.0, 1 - r) ** GROUND_DISC_FALLOFF
            # Image rows run bottom to top, so v grows upward.
            if half is not None and (u + v > 0) != (half == 'upper-right'):
                alpha = 0
            rgba += bytes((255, 255, 255, round(255 * alpha)))
    return pyglet.image.ImageData(size, size, 'RGBA', bytes(rgba), pitch=size * 4)


def strength_shaded_image(data):
    """Darken the bottom of a strength-column sprite while preserving alpha."""
    width, height = data.width, data.height
    rgba = bytearray(data.get_data('RGBA', width * 4))
    for y in range(height):
        shade = 0.4 + 0.6 * min(1.0, y / max(1, height * 0.6))
        for x in range(width):
            offset = (y * width + x) * 4
            for channel in range(3):
                rgba[offset + channel] = round(rgba[offset + channel] * shade)
    return pyglet.image.ImageData(width, height, 'RGBA', bytes(rgba), pitch=width * 4)


def gray_image(data):
    """Grayscale copy of image data, keeping its alpha."""
    rgba = bytearray(data.get_data('RGBA', data.width * 4))
    for offset in range(0, len(rgba), 4):
        r, g, b = rgba[offset:offset + 3]
        gray = (299 * r + 587 * g + 114 * b) // 1000
        rgba[offset:offset + 3] = bytes((gray, gray, gray))
    return pyglet.image.ImageData(data.width, data.height, 'RGBA', bytes(rgba),
                                  pitch=data.width * 4)


def soft_outline_image(data):
    """Copy of image data with its outer ink outline faded (see
    FOLLOWER_SCALE); inner lines and colors are kept."""
    width, height = data.width, data.height
    rgba = data.get_data('RGBA', width * 4)
    clear = rgba[3::4]
    # Dilate the transparent area by the band, along rows and then columns.
    band = FOLLOWER_OUTLINE_BAND
    near_row = bytearray(width * height)
    for y in range(height):
        row = y * width
        for start, stop, step in ((0, width, 1), (width - 1, -1, -1)):
            last = None
            for x in range(start, stop, step):
                if clear[row + x] < 16:
                    last = x
                if last is not None and abs(x - last) <= band:
                    near_row[row + x] = 1
    near = bytearray(width * height)
    for x in range(width):
        for start, stop, step in ((0, height, 1), (height - 1, -1, -1)):
            last = None
            for y in range(start, stop, step):
                if near_row[y * width + x]:
                    last = y
                if last is not None and abs(y - last) <= band:
                    near[y * width + x] = 1
    faded = bytearray(rgba)
    for i in range(width * height):
        offset = i * 4
        alpha = rgba[offset + 3]
        if alpha and near[i] and (299 * rgba[offset] + 587 * rgba[offset + 1]
                                  + 114 * rgba[offset + 2]) // 1000 < FOLLOWER_INK:
            faded[offset + 3] = round(alpha * FOLLOWER_OUTLINE_KEEP)
    return pyglet.image.ImageData(width, height, 'RGBA', bytes(faded), pitch=width * 4)


def brightened_image(data, gain):
    """Copy of image data with its colors scaled by gain (clipped), alpha kept."""
    rgba = data.get_data('RGBA', data.width * 4)
    table = bytes(min(255, round(value * gain)) for value in range(256))
    bright = bytearray(rgba.translate(table))
    bright[3::4] = rgba[3::4]
    return pyglet.image.ImageData(data.width, data.height, 'RGBA', bytes(bright),
                                  pitch=data.width * 4)


def edge_floor_bounds(field):
    """Find the first non-wall column and row from each edge."""
    points = [(x, y) for y, row in enumerate(field)
              for x, cell in enumerate(row)
              if cell not in (*d.WALL_CHARS, d.CHAR_HIDDEN_D_GATE)]
    if not points:
        return (1, 1, len(field[0]) - 1, len(field) - 1)
    return (min(x for x, _ in points), min(y for _, y in points),
            max(x for x, _ in points) + 1, max(y for _, y in points) + 1)

def edge_floor_shade(cx, cy, width, height, bounds=None):
    """Floor shade at continuous field coordinates (in cells, origin top-left)."""
    def fade(distance, fade_spec):
        edge, cells = fade_spec
        t = min(1.0, max(0.0, distance / cells))
        return edge + (1 - edge) * t * t * (3 - 2 * t)
    left, top, right, bottom = bounds or (1, 1, width - 1, height - 1)
    side = fade(min(cx - left, right - cx), EDGE_FLOOR_SIDE_FADE)
    end = fade(min(cy - top, bottom - cy), EDGE_FLOOR_END_FADE)
    return min(side, end)


def edge_floor_shade_data(width, height, texels=EDGE_FLOOR_TEXELS_PER_CELL, bounds=None):
    """Top-down RGBA bytes of the field's edge shade, sampled at texel centers."""
    # The shade is the minimum of a per-column and a per-row fade.
    columns = [edge_floor_shade((col + 0.5) / texels, height / 2, width, height, bounds)
               for col in range(width * texels)]
    data = bytearray()
    for row in range(height * texels):
        row_shade = edge_floor_shade(width / 2, (row + 0.5) / texels, width, height, bounds)
        for column_shade in columns:
            value = round(255 * min(column_shade, row_shade))
            data += bytes((value, value, value, 255))
    return bytes(data)


def mipmapped(image):
    """Texture shrunk through mipmaps, so fine details do not flicker away.

    The PNGs carry their edge colors into transparent pixels (see
    dev-samples/3d-stage1/bleed-alpha.py), so the smaller levels get no dark
    fringe. Pyglet's get_mipmapped_texture() builds the levels before
    uploading the image, so they are generated here instead.
    """
    texture = image.get_texture()
    gl = pyglet.gl
    gl.glBindTexture(texture.target, texture.id)
    gl.glTexParameteri(texture.target, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR_MIPMAP_LINEAR)
    # Sample one level finer than the default; the outlines blur away otherwise.
    gl.glTexParameterf(texture.target, gl.GL_TEXTURE_LOD_BIAS, MIPMAP_LOD_BIAS)
    gl.glGenerateMipmap(texture.target)
    return texture
