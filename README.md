# ARLQ, another rogue-like quest game

ARLQ (Another Rogue-Like Quest) is an experimental rogue-like game created through a collaboration between humans and ChatGPT, who worked together on both the code and the manual.

* The code was generated by ChatGPT based on a rough description of the game, and humans then adjusted and improved the details.
  * ChatGPT also handled tasks beyond code generation, such as creating the maze generation algorithm and explaining how to use the curses library.
  * Type hints and comments were generated by ChatGPT.
  * ChatGPT even helped come up with ideas for new monsters.
* The manual was drafted by humans and later edited and proofread with ChatGPT.

![](screenshot.png)

## Installation Instructions

Run the following command to install:

```bash
pipx install git+https://github.com/tos-kamiya/arlq
```

Once installed, the `arlq` command becomes available.

- Without any options, the game will run in a Pygame window.
- To make the game easier, use the `-T` option (expands the visible area).
- To make the game more challenging, use the `-F` option (enlarges the field) or the `-t` option (reduces the visible area).
- With the `--curses` option, the game will run in the terminal using curses.

To use the `--curses` option, you need to install the `curses` package separately:

For Ubuntu 24.04:

```bash
sudo apt install python3-curses
```

For Windows:

```bash
pip install windows-curses
```

## Game Description

* **Objective**  
  The goal of the game is to explore a dungeon with uniquely generated corridors every time and locate the treasure chest hidden by the dragon.

* **Player**  
  You control the character represented by “@” using the arrow keys to move up, down, left, and right.

* **Monsters and Companions**  
  The dungeon is populated with various monsters and companions. Initially, monsters are displayed as “?” while companions appear as “!”. When you come into contact with them, their true type (such as `a`, `b`, `c`, etc.) is revealed.

* **Fog System**  
  The game uses a fog system where only the areas you have walked on are visible. Combined with auto-mapping, areas once visited remain visible on the map.

* **Encounters**  
  - **Monsters:** Contacting a monster initiates combat. If the monster is at or below your level, you can defeat it, level up, and obtain any items it may be carrying. However, if you lose to a higher-level monster, you will respawn at a random location within the dungeon.
  - **Companions:** When you come into contact with a companion, it will join you and provide its unique benefit. For example, a fairy will slightly increase your field of view, a goblin will help identify nearby monsters when you move adjacent to them, and a hippogriff will assist you in overcoming walls. After a short time, the companion will part ways with you.
  
  Note: Neither monsters nor companions move on their own; they wait for you to approach.

* **Rare Types**  
  Some monsters have rare variants with special features that differ from the normal ones.  
  For example:  
  - `A` (Rare Amoeba): Significantly boosts your level upon defeat.  
  - `B` (Rare Bison): Provides even more food than a normal bison.

* **Food System**  
  Every move you make decreases your food supply. If your food reaches zero, you lose the game from hunger. Defeating monsters replenishes your food, so manage your supplies carefully.

* **Game End**  
  The game is cleared when you come into contact with the treasure chest (represented by `T`). Your objective is to obtain the treasure chest guarded by the dragon.

## Monster List

| Display & Name   | Description                                                                                                                                                             |
| ---------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **a** Amoeba         | Weak enough to be defeated from the start. Useful for leveling up.                                                                                                      |
| **A** Rare Amoeba    | A rare amoeba that significantly boosts your level upon defeat.                                                                                                        |
| **b** Bison          | The second weakest. Defeating it provides plenty of food. Hunt it when you're hungry.                                                                                   |
| **B** Rare Bison     | Tastier than a normal bison and provides even more food.                                                                                                                |
| **c** Chimera        | Moderately strong. It wields a sword, which can be obtained upon defeat. Holding the sword doubles your combat power in the next battle and lets you break walls.    |
| **C** Rare Chimera   | Stronger than a normal chimera, wielding a sword that triples your combat power.                                                                                         |
| **d** Komodo Dragon  | Powerful but dangerous. Defeating it provides a large amount of food, but you'll be poisoned—reducing your combat power to one-third in the next battle.               |
| **D** Dragon         | Extremely strong. Defeating it reveals the location of the treasure chest. Even without defeating it, you gain the ability to distinguish treasure chests.           |
| **e** Erebus         | Battling it drains your vitality.                                                                                                                                       |

## Companion List

| Display & Name  | Description                                                                                                                     |
| --------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| **f** Fairy         | The fairy slightly increases your field of view.                                                 |
| **g** Goblin        | When you move adjacent to a monster, the goblin will identify that monster’s type for you.                                        |
| **h** Hippogriff    | When you bump into a wall, the hippogriff helps you overcome it, allowing you to pass over obstacles.                            |

## License

This project is licensed under the BSD-2 license.
