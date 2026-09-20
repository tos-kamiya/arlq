"""Minimal translation support for player-visible messages.

Only the event/status message line and the GUI (Pyglet) stage-select
screen are translated. Status-bar abbreviations and item names (LVL,
HRS, Sword, Poisoned, ...) are intentionally left in English: they sit
in fixed-width layouts (especially in the Blessed terminal frontend)
that a longer or double-width Japanese string could break.

Messages are keyed by their English source text (or, for messages with
a number, by a `str.format` template). Translating happens at display
time rather than at `defs.py` definition time, since the language is
only known after argument parsing.
"""

import os
from typing import Optional

_JA = {
    "-- Exp. Boost!": "-- 経験値ボーナス!",
    "-- Stuffed!": "-- 満腹になった!",
    "-- Got a sword!": "-- 剣を手に入れた!",
    "-- Got cursed sword!": "-- 呪われた剣を手に入れた!",
    "-- Unlocked Dragon's treasure chest!": "-- 竜の宝箱の封印を解いた!",
    "-- Energy Drained!": "-- 気力を吸い取られた!",
    "-- Unlocked Fire Drake's treasure chest!": "-- 火竜の宝箱の封印を解いた!",
    "-- Caltrops Scattered!": "-- まきびしが散らばった!",
    "-- The Isolated Elf told you about the history of the elves.": "-- 隠者エルフがエルフたちの歴史を語ってくれた。",
    "-- The Javelin Elf joins your hunt for the Dread Wyrm!": "-- ジャベリンエルフがドレッドウィルム討伐に同行してくれる!",
    "-- The Collector Elf gave you a rustless blade for your Cursed Sword!": (
        "-- コレクターエルフが呪われた剣と引き換えに、錆びない刃を授けてくれた!"
    ),
    "-- The High Elf bestowed the talisman upon you!": "-- ハイエルフがタリスマンを授けてくれた!",
    "-- Spores cloud your vision!": "-- 胞子で視界がかすんだ!",
    "-- Dread Wyrm defeated!": "-- ドレッドウィルムを討伐した!",
    "-- Something went terribly wrong...": "-- 何か恐ろしいことが起きた……",
    "-- Nomicon joined!": "-- ノミコンが仲間になった!",
    "-- Ocular joined!": "-- オキュラーが仲間になった!",
    "-- Pegasus joined!": "-- ペガサスが仲間になった!",
    ">> Treasures collected! <<": ">> 宝箱を手に入れた! <<",
    "-- The High Elf does not recognize you.": "-- ハイエルフはまだあなたを認めていない。",
    "-- Respawned!": "-- 復活した!",
    "-- The companion vanishes.": "-- 同行者が姿を消した。",
    ">> Starved to Death. <<": ">> 飢えて死んだ。 <<",
    "SEED: {seed_str}": "シード: {seed_str}",
    "-- The elf watches you in silence.": "-- エルフは黙ってあなたを見つめている。",
    "-- The cursed sword has served its purpose.": "-- 呪われた剣はもう役目を終えた。",
    "-- Keep the talisman close to your skin.": "-- タリスマンを肌身離さず持っていよう。",
    "-- The barrier burns you.": "-- バリアに焼かれた。",
    "-- Time folds back to the beginning of the recorded past.": "-- 時が記録された過去の始まりまで巻き戻った。",
    "-- You took the treasure, but the King's request remains.": "-- 宝物を手に入れたが、国王の依頼はまだ残っている。",
    "-- Bring the cursed sword.": "-- 呪われた剣を持ってこよう。",
    "-- Descended to floor {n}/3.": "-- {n}/3階に降りた。",
    "-- Ascended to floor {n}/3.": "-- {n}/3階に上った。",
    "-- The King has ordered the Dread Wyrm slain.": "-- 国王がドレッドウィルムの討伐を命じた。",
    "Stage Selection": "ステージ選択",
    "[q]uit": "[q] 終了",
    "stage [{n}]": "ステージ [{n}]",
}

_CATALOGS = {"ja": _JA}

_lang = "en"


def set_language(lang: str) -> None:
    global _lang
    _lang = lang if lang in _CATALOGS else "en"


def detect_language() -> str:
    """Guess a language from the environment's locale variables."""
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(var, "")
        if value.lower().startswith("ja"):
            return "ja"
    return "en"


def t(text: Optional[str]) -> Optional[str]:
    """Translate a fixed message string (or `str.format` template) for the
    current language. Falls back to `text` unchanged if untranslated."""
    if text is None:
        return None
    return _CATALOGS.get(_lang, {}).get(text, text)
