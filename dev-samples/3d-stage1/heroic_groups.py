"""Which of the three heroic scenes holds each character.

Monsters (with the treasure chest beside the mimic, the golem's rock and the
rank marks) go in one scene, the Stage 5 party members in another, and
everyone else (the player, companions and elves) in the third, so one group
can be rebuilt without the others.
"""
from pathlib import Path

HEROIC = Path(__file__).resolve().parent / 'heroic'
GROUPS = ('monsters', 'members', 'others')
MONSTERS = {'a', 'A', 'b', 'B', 'c', 'C', 'd', 'D', 'F', 'f', 'g', 'rock', 'X', 'e', 'E',
            'w', 'W', 'm', 'k', 'V', 'T', 'T-toy', 'M', "'", '"'}
# Members are named like 'jester-light', one model per skin tone.
MEMBERS = ('jester', 'healer', 'rogue', 'knight', 'guardian', 'explorer')


def group_of(char):
    if char in MONSTERS:
        return 'monsters'
    return 'members' if char.split('-')[0] in MEMBERS else 'others'


def blend_path(group):
    return HEROIC / f'characters-{group}-angle60.blend'
