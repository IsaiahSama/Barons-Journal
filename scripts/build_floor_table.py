"""Regenerate src/barons_journal/reference/floors.json from an installed copy of Barony.

Usage:
    uv run python scripts/build_floor_table.py /path/to/Barony \\
        --game-dir ~/.steam/steam/steamapps/common/Barony [--commit SHA] [--game-build ID]

Sources:
- maps/levels.txt (game): line N is main floor N (dungeon_lvl N).
- maps/secretlevels.txt (game): line N is secret level N; "warpzone" means none.
  A secret entrance on main floor N leads to secret level N+1 (actladder.cpp).
- src/maps.cpp (source), the "// secret stuff" block: which generated main floors
  get a secret entrance, and on which it's a 50% chance (`map_rng.rand() % 2`).
  Fixed (hand-made) maps place their entrances in the binary map file, so those
  are listed by hand in FIXED_MAP_ENTRANCES, citing the compendium.
- src/maps.cpp (source), `orb_floors[N] = "orb_<colour>"`: main floors that always
  get the room holding a mystic orb.
- lang/compendium_lang/contents_world.json (game): display titles ("HAUNTED CASTLE").
- lang/compendium_lang/lang_world.json (game): "SECRET LEVEL TREASURES" lists.
Artifact item IDs are found by matching treasure names against data.ids.ITEMS.

Not modelled: whether a secret level's exit leads on to the next secret level
instead of back to the main dungeon. That's a per-portal flag in the binary map
files (portalNotSecret), so it can't be read here.
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from barons_journal.data.ids import ITEMS  # noqa: E402

OUT = Path(__file__).parent.parent / "src/barons_journal/reference/floors.json"

# Map file / generator name -> compendium entry key.
MAIN_AREAS = {
    "start": "minehead",
    "mine": "mines",
    "swamp": "swamps",
    "labyrinth": "labyrinth",
    "ruins": "ruins",
    "boss": "herx lair",
    "hell": "hell",
    "hellboss": "molten throne",
    "hamlet": "hamlet",
    "caves": "crystal caves",
    "citadel": "arcane citadel",
    "sanctum": "citadel sanctum",
    "minetoswamp": "transition floor",
    "swamptolabyrinth": "transition floor",
    "labyrinthtoruins": "transition floor",
    "cavestocitadel": "transition floor",
}
SECRET_AREAS = {
    "gnomishmines": "gnomish mines",
    "minetown": "minetown",
    "underworld": "underworld",
    "temple": "temple",
    "greatcastle": "haunted castle",
    "sokoban": "sokoban",
    "minotaur": "minotaur maze",
    "mysticlibrary": "mystic library",
    "caveslair": "cockatrice lair",
    "bramscastle": "brams castle",
}
# Main floors whose secret entrance is built into a fixed map, not placed by maps.cpp.
FIXED_MAP_ENTRANCES = {
    5: "compendium (underworld): accessed via secret entrances on floor 5 and 18",
}
# Lines in secretlevels.txt that aren't secret places.
SKIPPED_SECRET = {
    "warpzone": "no secret level at this depth",
    "boss": "same map as the main Lich's Bastion floor; the compendium doesn't list it as a secret place",
}


def read_level_list(path: Path) -> list[str]:
    """Map names, one per dungeon level ("gen: mine" -> "mine")."""
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [line.split(" ", 1)[1] for line in lines]


def display_titles(game_dir: Path) -> dict[str, str]:
    """Compendium key -> title-cased display name ("brams castle" -> "Bram's Castle")."""
    contents = json.loads((game_dir / "lang/compendium_lang/contents_world.json").read_text(encoding="utf-8"))
    titles = {}
    for entry in contents["contents"]:
        ((title, key),) = entry.items()
        if key != "-":
            titles[key] = " ".join(word.capitalize() for word in title.split())
    return titles


def treasures(game_dir: Path) -> dict[str, list[str]]:
    """Compendium key -> its "SECRET LEVEL TREASURES" lines."""
    world = json.loads((game_dir / "lang/compendium_lang/lang_world.json").read_text(encoding="utf-8"))
    found = {}
    for key, entry in world.items():
        details = entry.get("details", []) if isinstance(entry, dict) else []
        if "SECRET LEVEL TREASURES:" in details:
            start = details.index("SECRET LEVEL TREASURES:") + 1
            items = []
            for line in details[start:]:
                if not line.startswith("- "):
                    break
                items.append(line[2:].strip())
            found[key] = items
    return found


def artifact_ids(game_dir: Path, treasure_lines: list[str]) -> list[int]:
    game_items = json.loads((game_dir / "items/items.json").read_text(encoding="utf-8"))["items"]
    artifact_item_ids = {v["item_id"] for k, v in game_items.items() if k.startswith("artifact_")}
    ids = []
    for line in treasure_lines:
        name = re.sub(r"\s*\(.*\)$", "", line)  # "Khryselakatos (Lvl 7)" -> "Khryselakatos"
        try:
            item_id = ITEMS.index_of(name)
        except ValueError:
            continue
        assert item_id in artifact_item_ids, f"{name} matched item {item_id}, which isn't an artifact"
        ids.append(item_id)
    return ids


def entrance_floors(barony: Path) -> dict[int, float]:
    """Main floor -> chance (0-1) that it has a secret entrance, from maps.cpp."""
    src = (barony / "src/maps.cpp").read_text(encoding="utf-8")
    block = src[src.index("// secret stuff") : src.index("mapList.first = nullptr;")]
    found = {}
    for lvl, coin_flip in re.findall(r"currentlevel == (\d+)(\s*&&\s*map_rng\.rand\(\)\s*%\s*2)?", block):
        found[int(lvl)] = 0.5 if coin_flip else 1.0
    assert found, "no secret entrance floors found in maps.cpp"
    for lvl in FIXED_MAP_ENTRANCES:
        found[lvl] = 1.0
    return found


def orb_floor_items(barony: Path) -> dict[int, int]:
    """Main floor -> mystic orb item ID, from TreasureRoomGenerator's orb_floors in maps.cpp."""
    src = (barony / "src/maps.cpp").read_text(encoding="utf-8")
    found = {int(lvl): ITEMS.index_of(f"{colour} mystic orb")
             for lvl, colour in re.findall(r'orb_floors\[(\d+)\] = "orb_(\w+)";', src)}
    assert found, "no orb_floors found in maps.cpp"
    return found


def build(barony: Path, game_dir: Path) -> dict:
    main = read_level_list(game_dir / "maps/levels.txt")
    secret = read_level_list(game_dir / "maps/secretlevels.txt")
    titles = display_titles(game_dir)
    compendium_treasures = treasures(game_dir)

    entrances = entrance_floors(barony)

    secret_levels = []
    for lvl, name in enumerate(secret):
        if name in SKIPPED_SECRET:
            continue
        key = SECRET_AREAS[name]  # KeyError = new secret level to map
        prev_name = secret[lvl - 1] if lvl > 0 else "warpzone"
        next_name = secret[lvl + 1] if lvl + 1 < len(secret) else "warpzone"
        # The second floor of a multi-floor area (the underworld) is reached by trapdoor from the first.
        continues = prev_name == name
        entrance = lvl - 1 if (lvl - 1) in entrances else None
        assert continues or entrance is not None, f"no known way into secret level {lvl} ({name})"
        # Multi-floor secret areas (the underworld) list their treasures once. The compendium:
        # "adventurers who find a trapdoor down to a second floor of the underworld will find a
        # deadly reward", so the treasures belong to the last floor of the run.
        found_here = compendium_treasures.get(key, []) if next_name != name else []
        secret_levels.append(
            {
                "dungeon_lvl": lvl,
                "map": name,
                "name": titles[key],
                "entrance_floor": entrance,
                "previous": titles[key] if continues else None,
                "treasures": found_here,
                "artifacts": artifact_ids(game_dir, found_here),
            }
        )

    orbs = orb_floor_items(barony)
    leads_to = {s["entrance_floor"]: s["dungeon_lvl"] for s in secret_levels if s["entrance_floor"] is not None}
    for lvl in sorted(set(entrances) - set(leads_to)):
        print(f"note: floor {lvl}'s secret entrance leads to skipped secret line {secret[lvl + 1]!r}")
    floors = [
        {
            "dungeon_lvl": lvl,
            "map": name,
            "area": titles[MAIN_AREAS[name]],  # KeyError = new area to map
            "secret_entrance": leads_to.get(lvl),
            "secret_entrance_chance": entrances[lvl] if lvl in leads_to else None,
            "orb": orbs.get(lvl),
        }
        for lvl, name in enumerate(main)
    ]
    return {"floors": floors, "secret_levels": secret_levels}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("barony", type=Path, help="path to a TurningWheel/Barony checkout")
    parser.add_argument("--game-dir", type=Path, required=True, help="installed Barony folder (has maps/)")
    parser.add_argument("--commit", default="unknown", help="Barony commit SHA, recorded for provenance")
    parser.add_argument("--game-build", default="unknown", help="Steam build ID of --game-dir, for provenance")
    args = parser.parse_args()

    tables = build(args.barony, args.game_dir)
    out = {
        "_source": (
            f"TurningWheel/Barony@{args.commit} + game data from Steam build {args.game_build}, "
            "generated by scripts/build_floor_table.py"
        ),
        **tables,
    }
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"floors        {len(tables['floors'])}\nsecret levels {len(tables['secret_levels'])}\nwrote {OUT}")


if __name__ == "__main__":
    main()
