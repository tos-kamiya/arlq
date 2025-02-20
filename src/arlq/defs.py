from typing import List, Tuple

TILE_WIDTH = 5
TILE_HEIGHT = 4
TILE_NUM_X = 12
TILE_NUM_Y = 4
FIELD_WIDTH = (TILE_WIDTH + 1) * TILE_NUM_X + 1
FIELD_HEIGHT = (TILE_HEIGHT + 1) * TILE_NUM_Y + 1
CORRIDOR_V_WIDTH = 3
CORRIDOR_H_WIDTH = 2
WALL_CHARS = "###"  # cross, horizontal, vertical

FOOD_MAX = 100
FOOD_INIT = 90
FOOD_STARVATION = 30

MONSTER_RESPAWN_RATE = 150

ITEM_SWORD = "Sword"
ITEM_POISONED = "Poisoned"
ITEM_TREASURE = "Treasure"

EFFECT_SPECIAL_EXP = "Special Exp."
EFFECT_FEED_MUCH = "Bison Meat"
EFFECT_RANDOM_TRANSPORT = "Random Trans."
EFFECT_CLAIRVOYANCE = "Sword & Eye"
EFFECT_TREASURE_POINTER = "Treasure Ptr."

COMPANION_FAIRY = "Fairy"
FAIRY_TORCH_EXTENSION = 3

CHAR_DRAGON = "D"
CHAR_TREASURE = "T"


Point = Tuple[int, int]
Edge = Tuple[Point, Point]


class Entity:
    def __init__(self, x, y):
        self.x = x
        self.y = y


class Treasure(Entity):
    def __init__(self, x, y):
        super().__init__(x, y)


class Player(Entity):
    def __init__(self, x, y, level, food):
        super().__init__(x, y)
        self.level = level
        self.food = food
        self.item = ""
        self.item_taken_from = ""
        self.companion = ""


class Monster(Entity):
    def __init__(self, x, y, tribe):
        super().__init__(x, y)
        self.tribe = tribe


class MonsterTribe:
    def __init__(self, char, level, feed, population, item="", effect="", companion=""):
        self.char = char
        self.level = level
        self.feed = feed
        self.population = population
        self.item = item
        self.effect = effect
        self.companion = companion


MONSTER_TRIBES: List[MonsterTribe] = [
    MonsterTribe("a", 1, 12, 25),  # Amoeba
    MonsterTribe("b", 5, 20, 4, effect=EFFECT_FEED_MUCH),  # Bison
    MonsterTribe("c", 10, 12, 3, item=ITEM_SWORD),  # Chimera
    MonsterTribe("d", 20, 20, 3, item=ITEM_POISONED),  # Comodo Dragon
    MonsterTribe(CHAR_DRAGON, 40, 12, 1, effect=EFFECT_TREASURE_POINTER),  # Dragon
    MonsterTribe("E", 50, 0, 1, effect=EFFECT_RANDOM_TRANSPORT),  # Elemental
    MonsterTribe("f", 0, 0, 1, companion=COMPANION_FAIRY),  # Fairy
    MonsterTribe("A", 2, 12, 2, effect=EFFECT_SPECIAL_EXP),  # Amoeba rare
    MonsterTribe("B", 10, 30, 2, effect=EFFECT_FEED_MUCH),  # Bison rare
    MonsterTribe("C", 20, 12, 0.3, item=ITEM_SWORD, effect=EFFECT_CLAIRVOYANCE),  # Chimera rare
]


def player_attack_by_level(player: Player) -> int:
    if player.item == ITEM_SWORD:
        return player.level * 3
    elif player.item == ITEM_POISONED:
        return (player.level + 2) // 3
    else:
        return player.level
