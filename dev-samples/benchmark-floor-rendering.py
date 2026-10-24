"""Compare the current floor renderer with pre-sized checkerboard copies.

Run with the project's Python environment. Only benchmark artifacts are written;
the game's renderer is not modified. Default sizes exercise the reduced-resolution
path (UI scale >= 2, pixel ratio 1). No display or extra dependencies are required.
"""

import argparse
import ctypes
import json
import math
import os
import platform
import random
import statistics
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pyglet

pyglet.options['headless'] = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from pyglet import gl
from pyglet.math import Mat4

from arlq import defs as d
from arlq.pyglet_funcs import CELL_SIZE_X, CELL_SIZE_Y, VISIBLE_FLOOR
from arlq.sprite_funcs import (
    FLOOR_CHECKER_SHADE,
    FLOOR_TINTS,
    SpriteUI,
    mipmapped,
)


def target(width, height):
    texture = pyglet.image.Texture.create(
        width, height, min_filter=gl.GL_NEAREST, mag_filter=gl.GL_NEAREST,
    )
    framebuffer = pyglet.image.Framebuffer()
    framebuffer.attach_texture(texture)
    framebuffer.bind()
    if not framebuffer.is_complete:
        raise RuntimeError('Incomplete benchmark framebuffer')
    return texture, framebuffer


def bind(window, texture, framebuffer, logical_size):
    framebuffer.bind()
    gl.glViewport(0, 0, texture.width, texture.height)
    window.projection = Mat4.orthogonal_projection(
        0, logical_size[0], 0, logical_size[1], -255, 255,
    )


def new_ui(scale, height, images):
    # Reuse the real floor method and drawable-cache lifecycle without creating
    # a complete game window or loading unrelated character textures.
    ui = SpriteUI.__new__(SpriteUI)
    ui.scale = scale
    ui.cell_size_x, ui.cell_size_y = CELL_SIZE_X * scale, CELL_SIZE_Y * scale
    ui.window_height = height
    ui._horizontal_scroll_px = 0
    ui._floor_images = images
    ui._floor_group = pyglet.graphics.Group(order=-1)
    ui.batch = pyglet.graphics.Batch()
    ui._display_color = lambda color: color
    ui._menu_active = False
    ui._sprite_cells = {}
    ui._drawable_cache = {}
    ui._frame_drawable_cache = None
    ui._drawables = []
    return ui


def bake(window, images, cell_width, cell_height):
    """Pre-size and tint both floor variants, then assemble a 2x2 RGBA tile."""
    started = time.perf_counter()
    cell_images = []
    resources = []
    for parity, image in enumerate(images):
        texture, framebuffer = target(cell_width, cell_height)
        resources.append(framebuffer)
        bind(window, texture, framebuffer, (cell_width, cell_height))
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)
        sprite = pyglet.sprite.Sprite(image)
        sprite.scale_x, sprite.scale_y = cell_width / image.width, cell_height / image.height
        shade = FLOOR_CHECKER_SHADE if parity else 1
        sprite.color = tuple(round(c * shade) for c in FLOOR_TINTS[VISIBLE_FLOOR])
        sprite.draw()
        sprite.delete()
        cell_images.append(texture)

    tile, tile_framebuffer = target(cell_width * 2, cell_height * 2)
    resources.append(tile_framebuffer)
    bind(window, tile, tile_framebuffer, (tile.width, tile.height))
    gl.glClear(gl.GL_COLOR_BUFFER_BIT)
    batch = pyglet.graphics.Batch()
    sprites = [
        pyglet.sprite.Sprite(cell_images[(x + y) % 2],
                             x=x * cell_width, y=(1 - y) * cell_height, batch=batch,
                             blend_src=gl.GL_ONE, blend_dest=gl.GL_ZERO)
        for y in range(2) for x in range(2)
    ]
    batch.draw()
    gl.glFinish()
    elapsed_ms = (time.perf_counter() - started) * 1000
    for sprite in sprites:
        sprite.delete()
    return cell_images, tile, tile_framebuffer, resources, elapsed_ms


def cached_prepare(ui, images, step, cell_width, cell_height):
    ui._clear_drawables()
    for y in range(0, d.FIELD_HEIGHT, step):
        for x in range(0, d.FIELD_WIDTH, step):
            image = images[(x + y) % 2] if step == 1 else images[0]
            left, bottom = x * cell_width, (d.FIELD_HEIGHT - y - step) * cell_height
            signature = ('copy', id(image), left, bottom, 1, 1, id(ui._floor_group))
            sprite = ui._draw_object(
                signature,
                lambda image=image, left=left, bottom=bottom: pyglet.sprite.Sprite(
                    image, x=left, y=bottom, batch=ui.batch, group=ui._floor_group,
                    blend_src=gl.GL_ONE, blend_dest=gl.GL_ZERO,
                ),
            )
            ui._set_drawable_attribute(sprite, 'scale', 1)
    ui._finish_drawables()


def make_case(window, name, scale, images, cached, tile_framebuffer):
    field_width = d.FIELD_WIDTH * CELL_SIZE_X * scale
    field_height = d.FIELD_HEIGHT * CELL_SIZE_Y * scale
    native_width, native_height = d.FIELD_WIDTH * 26, d.FIELD_HEIGHT * 40
    if name == 'current_mipmap':
        logical_size = (round(field_width), round(field_height + 120))
        model = SpriteUI.__new__(SpriteUI)
        model.scale = scale
        model.window = SimpleNamespace(width=logical_size[0], height=logical_size[1])
        dimensions = SpriteUI._render_target_dimensions(model)
        ui = new_ui(scale, logical_size[1], images)
    elif name == 'aligned_mipmap':
        logical_size = (field_width, field_height)
        dimensions = (native_width, native_height)
        ui = new_ui(scale, field_height, images)
    else:
        logical_size = dimensions = (native_width, native_height)
        ui = new_ui(2, native_height, images)
    texture, framebuffer = target(*dimensions)

    if name in ('current_mipmap', 'aligned_mipmap'):
        def prepare():
            ui._clear_drawables()
            for y in range(d.FIELD_HEIGHT):
                for x in range(d.FIELD_WIDTH):
                    ui._draw_floor(x, y, VISIBLE_FLOOR, None, None)
            ui._finish_drawables()
        draw = ui.batch.draw
        count = d.FIELD_WIDTH * d.FIELD_HEIGHT
    elif name in ('copy_1x1', 'copy_2x2'):
        step = 1 if name == 'copy_1x1' else 2
        selected = cached[:2] if step == 1 else cached[2:]
        prepare = lambda: cached_prepare(ui, selected, step, 26, 40)
        draw = ui.batch.draw
        count = math.ceil(d.FIELD_WIDTH / step) * math.ceil(d.FIELD_HEIGHT / step)
    else:
        # A literal GPU framebuffer copy per 2x2 tile, as a separate control.
        # The sprite variants above use batched nearest-filtered texture reads.
        positions = [(x * 26, (d.FIELD_HEIGHT - y - 2) * 40)
                     for y in range(0, d.FIELD_HEIGHT, 2)
                     for x in range(0, d.FIELD_WIDTH, 2)]
        prepare = lambda: None

        def draw():
            gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, tile_framebuffer.id)
            for left, bottom in positions:
                gl.glBlitFramebuffer(0, 0, 52, 80, left, bottom, left + 52, bottom + 80,
                                     gl.GL_COLOR_BUFFER_BIT, gl.GL_NEAREST)
        count = len(positions)
    prepare()
    bind(window, texture, framebuffer, logical_size)
    for _ in range(5):
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)
        draw()
    gl.glFinish()
    return SimpleNamespace(name=name, ui=ui, texture=texture, framebuffer=framebuffer,
                           logical_size=logical_size, prepare=prepare, draw=draw, count=count)


def measure(window, case, frames, rebuild):
    bind(window, case.texture, case.framebuffer, case.logical_size)
    gl.glFinish()
    query = gl.GLuint()
    gl.glGenQueries(1, ctypes.byref(query))
    started = time.perf_counter_ns()
    gl.glBeginQuery(gl.GL_TIME_ELAPSED, query)
    for _ in range(frames):
        if rebuild:
            case.prepare()
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)
        case.draw()
    gl.glEndQuery(gl.GL_TIME_ELAPSED)
    gl.glFinish()
    wall_ms = (time.perf_counter_ns() - started) / 1e6 / frames
    elapsed = gl.GLuint64()
    gl.glGetQueryObjectui64v(query, gl.GL_QUERY_RESULT, ctypes.byref(elapsed))
    gl.glDeleteQueries(1, ctypes.byref(query))
    return {'wall_ms': wall_ms, 'gl_elapsed_ms': elapsed.value / 1e6 / frames}


def save_image(window, case, path):
    bind(window, case.texture, case.framebuffer, case.logical_size)
    gl.glClear(gl.GL_COLOR_BUFFER_BIT)
    case.draw()
    gl.glFinish()
    case.framebuffer.bind()
    pixels = (gl.GLubyte * (case.texture.width * case.texture.height * 4))()
    gl.glReadPixels(0, 0, case.texture.width, case.texture.height,
                    gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, pixels)
    data = bytes(pixels)
    pyglet.image.ImageData(case.texture.width, case.texture.height, 'RGBA', data).save(path)
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--frames', type=int, default=30)
    parser.add_argument('--rounds', type=int, default=9)
    parser.add_argument('--scales', type=float, nargs='+', default=[2.0, 3.37, 4.0])
    args = parser.parse_args()
    if args.frames < 1 or args.rounds < 1 or any(scale < 2 for scale in args.scales):
        parser.error('frames/rounds must be positive and scales must be >= 2')
    args.output.mkdir(parents=True, exist_ok=True)
    window = pyglet.window.Window(width=64, height=64, visible=False, vsync=False)
    gl.glDisable(gl.GL_DITHER)
    gl.glClearColor(0, 0, 0, 0)
    info = {key: ctypes.string_at(gl.glGetString(enum)).decode()
            for key, enum in [('vendor', gl.GL_VENDOR), ('renderer', gl.GL_RENDERER),
                              ('version', gl.GL_VERSION)]}
    info.update(pyglet=pyglet.version, python=sys.version, field=[d.FIELD_WIDTH, d.FIELD_HEIGHT],
                frames_per_sample=args.frames, rounds=args.rounds, pixel_ratio=1,
                hud_logical_height=120, reference_cell_pixels=[26, 40])
    info['platform'] = platform.platform()
    info['cpu_count'] = os.cpu_count()
    cpu_info = Path('/proc/cpuinfo')
    info['cpu_model'] = next(
        (line.split(':', 1)[1].strip() for line in cpu_info.read_text().splitlines()
         if line.startswith('model name')), platform.processor(),
    ) if cpu_info.exists() else platform.processor()
    assets = Path(__file__).resolve().parents[1] / 'src/arlq/assets/floor'
    images = [mipmapped(pyglet.image.load(str(assets / f'floor-{part}.png')))
              for part in ('a', 'b')]
    cell_images, tile, tile_framebuffer, bake_resources, bake_ms = bake(window, images, 26, 40)
    info['prebake_ms'] = bake_ms
    results = {'environment': info, 'samples': [], 'summary': [], 'validation': []}
    names = ['current_mipmap', 'aligned_mipmap', 'copy_1x1', 'copy_2x2', 'blit_2x2']
    rng = random.Random(20261021)
    print(json.dumps(info), flush=True)
    for scale in args.scales:
        cases = [make_case(window, name, scale, images, cell_images + [tile], tile_framebuffer)
                 for name in names]
        pixels = {case.name: save_image(
            window, case, str(args.output / f'scale-{scale}-{case.name}.png'),
        ) for case in cases}
        for name in ('copy_2x2', 'blit_2x2'):
            if pixels[name] != pixels['copy_1x1']:
                raise RuntimeError(f'{name} output differs from the 1x1 copy reference')
        if not any(pixels['current_mipmap']):
            raise RuntimeError('Current floor renderer produced an empty image')
        results['validation'].append({
            'scale': scale, 'copies_pixel_identical': True, 'current_nonempty': True,
        })
        for mode in ('retained_draw', 'rebuild_and_draw'):
            for round_index in range(args.rounds):
                order = cases.copy()
                rng.shuffle(order)
                for case in order:
                    timing = measure(window, case, args.frames, mode == 'rebuild_and_draw')
                    if timing['gl_elapsed_ms'] > timing['wall_ms'] * 10:
                        raise RuntimeError(f'Invalid GL timer result: {timing}')
                    results['samples'].append(dict(scale=scale, name=case.name, mode=mode,
                                                   round=round_index, **timing))
            for case in cases:
                samples = [s for s in results['samples']
                           if (s['scale'], s['name'], s['mode']) == (scale, case.name, mode)]
                row = {
                    'scale': scale, 'name': case.name, 'mode': mode, 'objects': case.count,
                    'target_pixels': [case.texture.width, case.texture.height],
                }
                for key in ('wall_ms', 'gl_elapsed_ms'):
                    values = [s[key] for s in samples]
                    row[key] = {
                        'median': statistics.median(values), 'min': min(values), 'max': max(values),
                    }
                results['summary'].append(row)
                print(json.dumps(row), flush=True)
        for case in cases:
            for drawable in case.ui._drawables:
                drawable.delete()
            case.framebuffer.delete()
            case.texture.delete()
        (args.output / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
    if gl.glGetError() != gl.GL_NO_ERROR:
        raise RuntimeError('OpenGL error during benchmark')
    # Keep framebuffer resources alive until all sampling/copies have completed.
    for framebuffer in bake_resources:
        framebuffer.delete()
    window.close()


if __name__ == '__main__':
    main()
