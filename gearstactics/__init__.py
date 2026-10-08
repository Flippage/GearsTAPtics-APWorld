from typing import Any, Dict, List

from BaseClasses import Item, ItemClassification, Tutorial
from worlds.AutoWorld import WebWorld, World

from .items import FILLER_NAMES, ITEM_TABLE, TRAP_NAMES, GearsTacticsItem
from .locations import LOCATION_GROUPS, LOCATION_TABLE
from .options import GearsTacticsOptions
from .regions import create_regions, included_locations
from .rules import GOAL_LOCATION, set_rules


class GearsTacticsWebWorld(WebWorld):
    theme = "dirt"
    tutorials = [Tutorial(
        "Gears Tactics Setup Guide",
        "A guide to setting up the Gears Tactics Archipelago client.",
        "English",
        "setup_en.md",
        "setup/en",
        ["Flippage", "Mercy"]
    )]


class GearsTacticsWorld(World):
    """
    Gears Tactics is a fast-paced, turn-based strategy game set 12 years before the first Gears of War.
    Upgrade your squad, hunt Locust commanders, and coordinate across the Multiworld!
    """
    game: str = "Gears Tactics"
    topology_present: bool = True
    web = GearsTacticsWebWorld()
    options_dataclass = GearsTacticsOptions
    options: GearsTacticsOptions

    item_name_to_id = {name: data.code for name, data in ITEM_TABLE.items()}
    location_name_to_id = {name: data.code for name, data in LOCATION_TABLE.items()}
    location_name_groups = LOCATION_GROUPS

    def generate_early(self) -> None:
        # a Veteran goal needs the Veteran checks to exist
        if self.options.goal.value == 3:
            self.options.include_veteran_missions.value = 1
        # the design's priority checks -> Archipelago priority_locations, so
        # they are more likely to hold progression than filler
        included = included_locations(self)
        self.options.priority_locations.value |= {
            n for n, d in included.items() if d.priority
        }

    def create_regions(self) -> None:
        for region in create_regions(self).values():
            self.multiworld.regions.append(region)

    def set_rules(self) -> None:
        set_rules(self)

    def create_items(self) -> None:
        n_locations = len(self.multiworld.get_unfilled_locations(self.player))

        # every listed item at its design count
        by_class: Dict[ItemClassification, List[str]] = {}
        for name, data in ITEM_TABLE.items():
            by_class.setdefault(data.classification, []).extend([name] * data.count)
        progression = by_class.get(ItemClassification.progression, [])
        useful = by_class.get(ItemClassification.useful, [])
        traps = by_class.get(ItemClassification.trap, [])
        filler = by_class.get(ItemClassification.filler, [])

        if len(progression) > n_locations:
            raise Exception(f"Gears Tactics: {len(progression)} progression items for "
                            f"{n_locations} locations. Enable more check categories.")

        # too many items (categories switched off): drop filler, then traps,
        # then useful. Progression is never dropped.
        pool_rest = useful + traps + filler
        excess = len(progression) + len(pool_rest) - n_locations
        for bucket in (filler, traps, useful):
            while excess > 0 and bucket:
                bucket.pop(self.random.randrange(len(bucket)))
                excess -= 1

        pool = progression + useful + traps + filler

        # too few: pad; trap_percentage decides how much padding is traps
        pad = n_locations - len(pool)
        if pad > 0:
            n_traps = int(pad * self.options.trap_percentage.value / 100)
            pool += [self.random.choice(TRAP_NAMES) for _ in range(n_traps)]
            pool += [self.random.choice(FILLER_NAMES) for _ in range(pad - n_traps)]

        self.multiworld.itempool += [self.create_item(n) for n in pool]

    def create_item(self, name: str) -> GearsTacticsItem:
        data = ITEM_TABLE[name]
        return GearsTacticsItem(name, data.classification, data.code, self.player)

    def get_filler_item_name(self) -> str:
        return self.random.choice(FILLER_NAMES)

    def fill_slot_data(self) -> Dict[str, Any]:
        return {
            "goal": self.options.goal.value,
            "goal_location": GOAL_LOCATION[self.options.goal.value],
            "death_link": self.options.death_link.value,
            "trap_percentage": self.options.trap_percentage.value,
            "include_starting_skills": bool(self.options.include_starting_skills.value),
        }
