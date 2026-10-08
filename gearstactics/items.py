from typing import Dict, NamedTuple

from BaseClasses import Item, ItemClassification

from .data import ITEMS, ITEM_BASE_ID


class GearsTacticsItem(Item):
    game: str = "Gears Tactics"


class ItemData(NamedTuple):
    code: int
    classification: ItemClassification
    count: int                    # copies in the pool, from the design YAML


_CLS = {
    "progression": ItemClassification.progression,
    "useful": ItemClassification.useful,
    "trap": ItemClassification.trap,
    "filler": ItemClassification.filler,
}

# Built from data.py, generated from the design YAML. Edit the YAML.
ITEM_TABLE: Dict[str, ItemData] = {
    name: ItemData(code, _CLS[cls], count) for name, code, cls, count in ITEMS
}

FILLER_NAMES = [n for n, d in ITEM_TABLE.items() if d.classification == ItemClassification.filler]
TRAP_NAMES = [n for n, d in ITEM_TABLE.items() if d.classification == ItemClassification.trap]
