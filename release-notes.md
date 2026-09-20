# ARLQ Release Notes

## Unreleased

## 4.4.2 - 2026-09-20

- Fix the low-LP and poisoned player indicators so both can be shown at
  once: low LP now always highlights the "@" background red and poisoned
  always tints its text magenta, switching to black text when both apply,
  in both the GUI and terminal renderers.

## 4.4.1 - 2026-09-20

- Replace the ">X" beatable-monster status indicator with a right-edge
  strength column that ranks the stage's monsters and the player by
  strength, in both the GUI and terminal renderers.
- In the GUI, give the strength column a tinted background and padding so
  it reads as distinct from the field, and shrink the field's wall-only
  edge columns to keep the window compact.
- Fix the Stage 3 status line spacing and the message overlapping the
  C/I/J/K/H/W/T progress flags in the GUI.
- Fix the player's low-LP and poisoned indicators so they no longer use the
  same colors as dangerous/beatable monsters.

## 4.4.0 - 2026-09-19

- Shrink Stage 1 to a smaller introductory map.
- Note that the Pegasus companion appears from Stage 2 onward.

## 4.3.1 - 2026-09-19

- Add a CPython compatibility matrix for Python 3.10 through 3.14.
- Update installation documentation with PyPI and GitHub installation paths,
  terminal requirements, and package and Python-version badges.

## 4.3.0 - 2026-09-19

- Replace the curses terminal UI with a Blessed terminal UI and add Blessed as
  a runtime dependency.
- Add the `--terminal` option and retain `--curses` as a deprecated alias.
- Pause the terminal game when the terminal is smaller than 80x24, then resume
  and redraw the game after the terminal is enlarged.
- Remove the separate curses UI implementation.

## 4.2.1 - 2026-09-19

- Adjust monster spawn populations and update the corresponding gameplay
  documentation.
- Clarify the Stage 3 objectives, floor behavior, companions, and progression.

## 4.2.0 - 2026-09-19

- Rebalance empowered monsters in Stages 2 and 3, including their populations
  and combat difficulty.

## 4.1.2 - 2026-09-18

- Fix Stage 3 rewind handling so encountered-elf state is restored together
  with the corresponding Stage 3 flags.

## 4.1.1 - 2026-09-18

- Place the Nomicon companion on every Stage 3 floor.

## 4.1.0 - 2026-09-18

- Replace the Pygame graphical backend with Pyglet.
- Respawn carried Stage 3 companions on their origin floors.
- Refactor Stage 3 state handling and fix Escape-key and related rule issues.

## 4.0.0 - 2026-09-18

- Add Stage 3, including multiple floors, elves, the Dread Wyrm, and its
  related objectives and progression.
- Add `--rematch` support for replaying the most recently started stage with
  the same seed.
- Align Stage 3 status, rewind, and high-elf behavior across game stages.
