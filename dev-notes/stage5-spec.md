# Stage 5 implementation notes

This file records implementation details for maintenance. `src/arlq/defs.py` is the source of truth for roster counts, party weights, and gameplay constants.

## Stage layout and objective

- Stage 5 starts at level 1 and has five seeded floors. Each floor has a detached terminal room containing one additional monster chosen from `b`, `c`, and `A`. Floors 3–5 can also have short wall spurs.
- Two ordinary stair pairs connect each adjacent floor pair. Dangeon Scholar reveals one additional hidden pair per connection. Stairs avoid the detached room where possible.
- Floors 2–5 receive two barriers each; the final floor also has barriers on 5% of eligible open cells. It contains one ordinary `W`, up to two random empowered escorts, a dormant Mimic that imitates `W`, and a treasure chest in another room section. A Knight or a sword from `c`/`C` is required to defeat `W`.
- Defeating `W` repositions the remaining monsters on floor 5 and clears explored floor and barrier cells. Wall and stair knowledge remains. Taking the unlocked chest wins the stage.
- Stage 5 has no elves. Caltrop Plants (`X`) are in the floor 2–4 roster and can also appear as boss escorts; defeating one scatters caltrops around the player using the shared spread pattern. Pits drop the player to the next floor.

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
| Dangeon Scholar | Reveals and enables hidden stairs and walks through walls created by Golems. Those walls still block Marksman arrows. |
| Guardian | Reduces barrier extra LP damage by half and caltrop damage to one third; movement LP cost is unchanged. |

## Monster parties and placement

- Vertically adjacent monsters form a party, up to five members. Horizontal and diagonal adjacency do not connect parties. A party fights as one encounter; strength and experience are summed, and LP reward uses the highest individual value.
- Party size uses `STAGE5_PARTY_SIZE_WEIGHTS` (weights for parties of one through five monsters):

| Floor | 1 | 2 | 3 | 4 | 5 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 70 | 22 | 7 | 1 | 0 |
| 2 | 50 | 30 | 15 | 4 | 1 |
| 3 | 40 | 30 | 20 | 8 | 2 |
| 4 | 34 | 30 | 24 | 10 | 2 |
| 5 | 33 | 30 | 22 | 12 | 3 |

- Stage 5 roster leaders and counts live in `STAGE5_ROSTER`. The deep-floor roster is spread over floors 2–5. Every floor also receives its detached-room `b`, `c`, or `A`.
- Fixed Bison (`b`) leader counts by floor are 10, 9, 9, 9, and 9.
- Floor 2 has no Wyrms (`w`), including as party additions. Its support pool excludes `w` and Marksmen (`k`); floors 3–5 use `a`, `f`, `b`, and `e` at twice the weight of `w` and `k`. Floor 1 party additions are `a` only.
- Golems (`g`) spawn alone. Marksmen (`k`) spawn alone on floors 2–5. Golems and Marksmen may be placed near walls or in narrow passages.
- Wyrms (`w`, `W`) raise barriers in their eight neighboring cells when unoccupied. The final floor boss party has one `W` and zero to two rank-2 escorts; neither `W'` nor `V'` is used there.

## Main implementation modules

- `src/arlq/stage5.py`: floor generation, member placement, monster party placement, and party rearrangement.
- `src/arlq/defs.py`: Stage 5 rosters, counts, party weights, and member/gameplay constants.
- `src/arlq/game_engine.py`: combat, member recruitment, movement warnings, Marksman cooldown, and floor transitions.
- `src/arlq/display.py` and the GUI/terminal frontends: member progress and field presentation.
