# ARLQ, another rogue-like quest game

ARLQ (Another Rogue-Like Quest) is a compact rogue-like game created as an
experiment in developing code and manuals with humans and ChatGPT.

![](https://github.com/tos-kamiya/arlq/blob/main/screenshot.png?raw=True)

Explore a procedurally generated dungeon, manage your LP (Life Points), learn
the identities of monsters, and find the treasure guarded by the dragon. The
game includes three stages:

- Stage 1: Find the Dragon's treasure chest.
- Stage 2: Find the Fire Drake's treasure chest.
- Stage 3: Defeat the Dread Wyrm and claim its treasure chest with help from the elves.

Features include:

- Turn-based combat, level progression, food, and special monster abilities.
- Fog of war and an automap that preserves explored areas.
- Companions with unique abilities.
- A Pyglet graphical interface and a Blessed terminal interface.

## Installation

Install ARLQ from PyPI:

```bash
pip install arlq
```

Start the graphical version with:

```bash
arlq
```

The terminal version is available through `arlq-cli`:

```bash
arlq-cli
```

You can also select the Blessed terminal interface explicitly:

```bash
arlq --terminal
```

Run `arlq --help` for the complete list of options. The old `--curses` option
is retained as a deprecated alias for `--terminal`.

## License

ARLQ is released under the BSD-2-Clause License.
