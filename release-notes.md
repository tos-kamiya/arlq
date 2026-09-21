# ARLQ Release Notes

## Unreleased

## 4.6.3 - 2026-09-22

- Revise the English and Japanese event messages so both languages
  describe the same outcome. The stage-clear banner now says the
  treasure chest was obtained, and the defeat banner says the player
  collapsed from hunger.
- In English, drop an initial letter when the creature's name already
  shows it, such as in the Dragon's treasure-chest message. Japanese
  messages keep the alphabet letter beside the katakana name.
- Show the "terminal is too small" prompt in Japanese when the UI
  language is Japanese.

## 4.6.2 - 2026-09-22

- Fix the High Elf (`H`) and Stage 3's Collector Elf (`K`) so that, while
  their condition remains unmet, contacting them a first time only shows
  their refusal message, but any contact after that now sends the player
  to a random location on the map (previously Stage 2's High Elf ignored
  the shared "twice in a row" escape mechanic entirely, and Stage 3's
  Collector Elf never escaped at all).

## 4.6.1 - 2026-09-21

- Fix the GUI window title when launching with `LC_ALL=C`.
- Align the `arlq-cli` stage-selection heading with its options.

## 4.6.0 - 2026-09-21

- Fix a soft-lock: losing combat twice in a row to the very same monster
  (with no other monster contact in between) now sends the player to a
  random location instead of back to the checkpoint, so a too-strong
  monster occupying the only corridor into an area can no longer
  permanently block progress.
- Fix a soft-lock in Stage 3: contact with the Isolated Elf (`I`) after
  the first now always sends the player elsewhere, so a player who
  reaches the elf's sealed room (e.g. via a Pegasus jump) can no longer
  get trapped inside.
- Align the English README's Game Description section structure with the
  Japanese version, and document the new escape mechanics above.

## 4.5.1 - 2026-09-21

- Fix Stage 3 monster color coding (red/beatable-blue) to include the
  Javelin Elf and Collector Elf attack bonuses, matching actual combat
  resolution. Previously an empowered monster could be shown as
  unbeatable (red) while still dying on contact.

## 4.5.0 - 2026-09-21

- Add Japanese localization: in-game event/status messages and the
  stage-select screen, in both the GUI and terminal frontends, can now
  display in Japanese. Status-bar abbreviations and item names stay in
  English to avoid breaking fixed-width layouts.
- Add the `--lang {auto,en,ja}` option. `auto` (the default) detects the
  language from the environment: an explicit `LC_ALL`/`LC_MESSAGES`/`LANG`
  environment variable is honored first, then falls back to a native
  per-OS UI-language lookup (Windows, macOS) when none is set.

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
