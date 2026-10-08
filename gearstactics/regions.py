from typing import Dict

from BaseClasses import Region

from .locations import GearsTacticsLocation, LOCATION_TABLE

# Category -> the option that switches it off. Every rule is a flattened item
# rule (see data.py), so dropping a category never strands anything else.
OPTIONAL_CATEGORIES = {
    "Optional Objective": "include_optional_objectives",
    "Veteran Mission": "include_veteran_missions",
    "High Kills": "include_high_kill_milestones",
    "Loot Case": "include_loot_case_milestones",
}


def included_locations(world) -> Dict[str, object]:
    out = {}
    for name, data in LOCATION_TABLE.items():
        opt = OPTIONAL_CATEGORIES.get(data.category)
        if opt and not getattr(world.options, opt).value:
            continue
        out[name] = data
    return out


def create_regions(world) -> Dict[str, Region]:
    player, mw = world.player, world.multiworld
    menu = Region("Menu", player, mw)
    game = Region("Gears Tactics", player, mw)
    for name, data in included_locations(world).items():
        game.locations.append(GearsTacticsLocation(player, name, data.code, game))
    menu.connect(game, "Start Game")
    return {"Menu": menu, "Gears Tactics": game}
