"""Which of the three heroic scenes holds each character.

Monsters (with the treasure chest beside the mimic, the golem's rock and the
rank marks) go in one scene, the Stage 5 party members in another, and
everyone else (the player, fairies and elves) in the third, so one group
can be rebuilt without the others.
"""
from pathlib import Path

HEROIC = Path(__file__).resolve().parent / 'heroic'
GROUPS = ('monsters', 'members', 'others')
MONSTERS = {'a', 'A', 'b', 'B', 'c', 'C', 'd', 'D', 'F', 'f', 'g', 'rock', 'X', 'e', 'E',
            'w', 'W', 'm', 'k', 'V', 'i', 'T', 'T-toy', 'M', "'", '"'}
# Party member models are named '<job>-<gender>-<tone>', like their sprite
# files: gender f(emale), m(ale), or n for a job with one build for both;
# tone l(ight), m(edium) or d(ark) skin.
MEMBER_VARIANTS = (('jester', 'n'), ('healer', 'f'), ('healer', 'm'), ('rogue', 'n'),
                   ('knight', 'n'), ('guardian', 'n'), ('explorer', 'n'),
                   ('seer', 'f'), ('seer', 'm'))
MEMBER_TONES = ('l', 'm', 'd')
MEMBER_MODELS = tuple(f'{job}-{gender}-{tone}' for job, gender in MEMBER_VARIANTS
                      for tone in MEMBER_TONES)
MEMBERS = (*dict.fromkeys(job for job, _ in MEMBER_VARIANTS), 'cat')


def group_of(char):
    if char in MONSTERS:
        return 'monsters'
    return 'members' if char.split('-')[0] in MEMBERS else 'others'


def blend_path(group):
    return HEROIC / f'characters-{group}-angle60.blend'
