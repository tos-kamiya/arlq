# ARLQ, another rogue-like quest game

ARLQ (Another Rogue-Like Quest) is a compact rogue-like game created as an
experiment in developing code and manuals with humans and AIs.

<p align="center">
  <a href="https://pypi.org/project/arlq/">
    <img alt="PyPI version" src="https://img.shields.io/pypi/v/arlq" />
  </a>
  <a href="https://www.python.org/">
    <img alt="Python 3.10-3.14" src="https://img.shields.io/badge/Python-3.10--3.14-3776AB?logo=python&logoColor=white" />
  </a>
</p>

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

ARLQ requires Python 3.10 or later. Install it from PyPI with:

```bash
pip install arlq
```

The required Pyglet and Blessed dependencies are installed automatically.

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

Run `arlq --help` for the complete list of options. The terminal interface
requires a terminal at least 80 columns wide and 24 lines high; the game
pauses while the terminal is smaller and resumes after it is enlarged.

## License

ARLQ is released under the BSD-2-Clause License.
