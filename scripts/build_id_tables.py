"""Regenerate src/barons_journal/data/ids.json from a Barony source checkout.

Usage:
    uv run python scripts/build_id_tables.py /path/to/Barony \
        --game-dir ~/.steam/steam/steamapps/common/Barony [--commit SHA] [--game-build ID]

ID order comes from the C++ enums; display names come from the game's own
language files (lang/en.txt, lang/item_names.json), so they match what the
player sees in-game. A few spells have no language entry; those use the
names from the Barony Save Editor (github.com/Groshie/Barony-Save-Editor).

Status effect names aren't in the source repo. They come from
data/status_effects.json in an installed copy of the game (--game-dir).

When Barony updates: rerun this, check the counts it prints against a new
save's array lengths, update the expected sizes in tests/data/test_ids.py,
and add the new game_version to SUPPORTED_VERSIONS.
"""

import argparse
import json
import re
from pathlib import Path

OUT = Path(__file__).parent.parent / "src/barons_journal/data/ids.json"

# Monster display names live in several ranges of en.txt.
# Monster ID -> en.txt string number.
MONSTER_STRINGS = (
    [90 + i for i in range(21)]  # NOTHING .. SHOPKEEPER
    + [2000 + i for i in range(16)]  # KOBOLD .. DUMMYBOT
    + [6256]  # BUGBEAR
    + [6358, 6359, 6360, 6361]  # DRYAD, MYCONID, SALAMANDER, GREMLIN
    + [6568, 6569]  # REVENANT_SKULL, MINIMIMIC
    + [6580, 6581, 6582, 6583, 6584, 6585]  # ADORCISED_WEAPON .. DUCK_SMALL
    + [6586, 6587, 6588]  # MONSTER_UNUSED_6..8
)

CLASS_STRINGS = list(range(5348, 5369)) + list(range(6789, 6794))

# Rat/Troll/Spider/Imp have no capitalised race string; reuse the monster names.
RACE_STRINGS = list(range(5369, 5378)) + [92, 95, 97, 101] + list(range(6779, 6784))

PROFICIENCY_STRINGS = list(range(236, 250)) + [3204, 3340]  # .. Shield, Unarmed, Alchemy

# Spells with no entry in item_names.json "spell_names".
SPELL_FALLBACK_NAMES = {
    "NONE": None,
    "FOCI_DARK_LIFE": "Icon of Claim Life",
    "FOCI_DARK_RIFT": "Icon of Void Rift",
    "FOCI_DARK_SILENCE": "Icon of Silence",
    "FOCI_DARK_VENGEANCE": "Icon of Vengeance",
    "FOCI_DARK_SUPPRESS": "Icon of Suppress",
    "FOCI_LIGHT_PEACE": "Symbol of Peace",
    "FOCI_LIGHT_JUSTICE": "Symbol of Justice",
    "FOCI_LIGHT_PROVIDENCE": "Symbol of Providence",
    "FOCI_LIGHT_PURITY": "Symbol of Purity",
    "FOCI_LIGHT_SANCTUARY": "Symbol of Sanctuary",
    "SCEPTER_BLAST": "Scepter Blast",
    "DUCK_DIVE": "Duck Dive",
}
# Spell enum name -> language key, where it isn't just "spell_" + lowercase.
SPELL_KEY_ALIASES = {
    "CHARM_MONSTER": "spell_charm",
    "DEMON_ILLUSION": "spell_demon_illu",
    "MYCELIUM_BOMB": "spell_mycelium",
}

# Status effects whose in-game name is a list of variants (tiers, forms) get one generic name.
EFFECT_NAME_OVERRIDES = {
    "EFF_VAMPIRICAURA": "Vampiric Aura",  # or "Vampiric Curse"
    "EFF_SHAPESHIFT": "Shapeshifted",  # "Rat Form", "Troll Form", ...
    "EFF_SALAMANDER_HEART": "Radiant Heart",  # or "Stone Heart"
}
# stat.hpp name -> internal_name in status_effects.json, where they differ.
EFFECT_INTERNAL_ALIASES = {"EFF_SALAMANDER_HEART": "EFF_RADIANT_HEART"}

# items.hpp `Status` enum. Not in en.txt as standalone words.
ITEM_STATUS = ["broken", "decrepit", "worn", "serviceable", "excellent"]


def read_lang(path: Path) -> dict[int, str]:
    strings = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^(\d+) (.*)#\s*$", line)
        if m:
            strings[int(m.group(1))] = m.group(2)
    return strings


def enum_members(source: str, start: str, end: str) -> list[str]:
    body = source[source.index(start) :]
    body = body[body.index("{") + 1 : body.index(end)]
    body = re.sub(r"//.*", "", body)
    return [m.split("=")[0].strip() for m in body.split(",") if m.strip()]


def derived_name(enum_name: str) -> str:
    """EFF_SHADOW_TAGGED -> "Shadow tagged"."""
    return enum_name.removeprefix("EFF_").replace("_", " ").capitalize()


def build_effects(barony: Path, game_dir: Path) -> tuple[list[str], list[int]]:
    """Return (names, hidden IDs). Hidden = the game shows no HUD entry for it."""
    stat_src = (barony / "src/stat.hpp").read_text(encoding="utf-8")
    enum = {int(n): f"EFF_{k}" for k, n in re.findall(r"static const int EFF_(\w+) = (\d+);", stat_src)}
    assert sorted(enum) == list(range(len(enum))), "gap in EFF_ IDs"

    data = json.loads((game_dir / "data/status_effects.json").read_text(encoding="utf-8"))
    by_id = {e["id"]: e for e in data["effects"].values() if e["id"] >= 0}
    assert sorted(by_id) == sorted(enum), "status_effects.json IDs don't match stat.hpp"

    names, hidden = [], []
    for i in range(len(enum)):
        entry = by_id[i]
        expected = EFFECT_INTERNAL_ALIASES.get(enum[i], enum[i])
        assert entry["internal_name"] == expected, (i, entry["internal_name"], enum[i])
        name = entry["name"]
        if enum[i] in EFFECT_NAME_OVERRIDES:
            name = EFFECT_NAME_OVERRIDES[enum[i]]
        elif isinstance(name, list):
            name = re.sub(r" \(Tier [IV]+\)$", "", name[0])
            assert all(re.sub(r" \(Tier [IV]+\)$", "", n) == name for n in entry["name"]), entry["name"]
        elif name == "":
            hidden.append(i)
            name = derived_name(enum[i])
        elif name.startswith("EFF_"):  # placeholder left in the game data
            name = derived_name(name)
        names.append(name)
    return names, hidden


def build(barony: Path, game_dir: Path) -> dict:
    lang = read_lang(barony / "lang/en.txt")
    lang_json = json.loads((barony / "lang/item_names.json").read_text(encoding="utf-8"))

    items_src = (barony / "src/items.hpp").read_text(encoding="utf-8")
    item_enum = [e for e in enum_members(items_src, "typedef enum ItemType", "} ItemType") if e != "ITEM_ENUM_MAX"]
    item_names = list(lang_json["items"].values())
    assert len(item_names) == len(item_enum), (len(item_names), len(item_enum))

    monster_enum = enum_members(
        (barony / "src/monster.hpp").read_text(encoding="utf-8"), "enum Monster : int", "};"
    )
    monster_enum = [m for m in monster_enum if m != "MAX_MONSTER"]
    assert len(MONSTER_STRINGS) == len(monster_enum), (len(MONSTER_STRINGS), len(monster_enum))

    game_src = (barony / "src/game.hpp").read_text(encoding="utf-8")
    num_classes = int(re.search(r"NUMCLASSES = (\d+)", game_src).group(1))
    num_races = int(re.search(r"#define NUMRACES (\d+)", game_src).group(1))
    assert len(CLASS_STRINGS) == num_classes
    assert len(RACE_STRINGS) == num_races

    magic_src = (barony / "src/magic/magic.hpp").read_text(encoding="utf-8")
    spell_ids = {int(n): k for k, n in re.findall(r"static const int SPELL_(\w+) = (\d+);", magic_src)}
    num_spells = int(re.search(r"NUM_SPELLS = (\d+)", magic_src).group(1))
    assert sorted(spell_ids) == list(range(num_spells)), "gap in spell IDs"
    spell_lang = lang_json["spell_names"]
    spells = []
    for i in range(num_spells):
        enum_name = spell_ids[i]
        key = SPELL_KEY_ALIASES.get(enum_name, f"spell_{enum_name.lower()}")
        if key in spell_lang:
            spells.append(spell_lang[key]["name"])
        else:
            spells.append(SPELL_FALLBACK_NAMES[enum_name])  # KeyError = new unnamed spell

    effects, hidden_effects = build_effects(barony, game_dir)

    return {
        "classes": [lang[n] for n in CLASS_STRINGS],
        "races": [lang[n] for n in RACE_STRINGS[:9]]
        + [lang[n].capitalize() for n in RACE_STRINGS[9:13]]
        + [lang[n] for n in RACE_STRINGS[13:]],
        "monsters": [lang[n] for n in MONSTER_STRINGS],
        "proficiencies": [lang[n] for n in PROFICIENCY_STRINGS],
        "items": [i["name_identified"] for i in item_names],
        "items_unidentified": [i["name_unidentified"] for i in item_names],
        "spells": spells,
        "item_status": ITEM_STATUS,
        "effects": effects,
        "effects_hidden": hidden_effects,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("barony", type=Path, help="path to a TurningWheel/Barony checkout")
    parser.add_argument("--game-dir", type=Path, required=True, help="installed Barony folder (has data/)")
    parser.add_argument("--commit", default="unknown", help="Barony commit SHA, recorded for provenance")
    parser.add_argument("--game-build", default="unknown", help="Steam build ID of --game-dir, for provenance")
    args = parser.parse_args()

    tables = build(args.barony, args.game_dir)
    out = {
        "_source": (
            f"TurningWheel/Barony@{args.commit} + game data from Steam build {args.game_build}, "
            "generated by scripts/build_id_tables.py"
        ),
        **tables,
    }
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    for name, names in tables.items():
        print(f"{name:20} {len(names)}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
