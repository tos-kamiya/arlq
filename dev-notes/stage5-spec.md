# Stage 5 implementation notes

This file records implementation details for maintenance. `src/arlq/defs.py` is the source of truth for roster counts, party weights, and gameplay constants.

## Stage layout and objective

- Stage 5 starts at level 1 and has five seeded floors. Each floor has a detached terminal room containing one additional monster chosen from `b`, `c`, and `A`. Floors 3–5 can also have short wall spurs.
- Two ordinary stair pairs connect each adjacent floor pair. Dungeon Explorer reveals one additional hidden pair per connection. Stairs avoid the detached room where possible.
- Floors 2–5 receive two barriers each; the final floor also has barriers on 5% of eligible open cells. Its boss party contains one ordinary `W`, one ordinary `V`, and one random empowered escort with no special effect or item. A dormant Mimic imitates `W`, and a treasure chest is in another room section. Combat is decided by comparing player attack with the combined strength of the monster party, including the boss.
- Defeating `W` unlocks the chest. The ordinary `V` in its party applies its local rearrangement effect when defeated. Taking the chest wins the stage.
- Stage 5 has no elves. Caltrop Plants (`X`) are in the floor 2–4 roster; defeating one scatters caltrops around the player using the shared spread pattern. Pits drop the player to the next floor.

## Members

- Four of six member roles are selected and placed across floors 1 and 2. Seeing a candidate reveals their role; touching them recruits them.
- At most two Stage 5 members join, in addition to the temporary companion. A third recruitment replaces the earliest joiner. Departed members do not respawn; their progress marker is dim and has a `-` suffix. Defeat respawns current members with the player.
- Earlier and later joiners follow diagonally behind to the left and right. Member discovery and known candidate floors are shown in the lower HUD.

| Member | Current ability |
| --- | --- |
| Bard | Triples experience after party sharing. |
| Healer | Reduces movement LP cost to one half and defeat LP cost to 2. |
| Rogue | Doubles the interval between Marksman shots. Identifies adjacent Mimics, Golems (`g`), Caltrop Plants (`X`), and Rare Erebus (`E`) in cardinal cells. Stops movement before pits, Marksman firing lanes, and Rare Erebus; a second press proceeds. |
| Knight | Triples player attack and multiplies shared experience by 0.75. |
| Dungeon Explorer | Reveals and enables hidden stairs and walks through walls created by Golems. Those walls still block Marksman arrows. |
| Guardian | Reduces barrier extra LP damage by half and caltrop damage to one third; movement LP cost is unchanged. |

## Monster parties and placement

- Vertically adjacent monsters form a party, up to three members. Horizontal and diagonal adjacency do not connect parties. A party fights as one encounter; strength and experience are summed, and LP reward uses the highest individual value.
- Party size uses `STAGE5_PARTY_SIZE_WEIGHTS` (weights for parties of one through three monsters):

| Floor | 1 | 2 | 3 |
| --- | ---: | ---: | ---: |
| 1 | 78 | 21 | 1 |
| 2 | 60 | 30 | 10 |
| 3 | 50 | 30 | 20 |
| 4 | 46 | 30 | 24 |
| 5 | 45 | 30 | 25 |

- Stage 5 roster leaders and counts live in `STAGE5_ROSTER`. The deep-floor roster is spread over floors 2–5. Every floor also receives its detached-room `b`, `c`, or `A`.
- Fixed Bison (`b`) leader counts by floor are 9, 8, 8, 8, and 8.
- Floor 2 has no Wyrms (`w`), including as party additions. Its support pool excludes `w` and Marksmen (`k`); floors 3–5 use `a`, `f`, `b`, and `e` at twice the weight of `w` and `k`. Floor 1 party additions are `a` only.
- Golems (`g`) spawn alone. Marksmen (`k`) spawn alone on floors 2–5. Golems and Marksmen may be placed near walls or in narrow passages.
- Wyrms (`w`, `W`) raise barriers in their eight neighboring cells when unoccupied. The final floor boss party has one `W`, one rank-1 `V`, and one other rank-2 escort chosen from `a`, `f`, `k`, and `w`; neither `W'` nor `V'` is used there.

## Main implementation modules

- `src/arlq/stage5.py`: floor generation, member placement, monster party placement, and party rearrangement.
- `src/arlq/defs.py`: Stage 5 rosters, counts, party weights, and member/gameplay constants.
- `src/arlq/game_engine.py`: combat, member recruitment, movement warnings, Marksman cooldown, and floor transitions.
- `src/arlq/display.py` and the GUI/terminal frontends: member progress and field presentation.
