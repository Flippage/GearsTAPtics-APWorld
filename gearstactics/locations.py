from typing import Dict, List, NamedTuple

from BaseClasses import Location

from .data import TASKS, LOCATION_BASE_ID


class GearsTacticsLocation(Location):
    game: str = "Gears Tactics"


class LocationData(NamedTuple):
    code: int
    category: str
    priority: bool
    requires: Dict[str, int]      # flattened item rule: item name -> copies
    after: List[str]              # design's direct task prereq (for the client)


# Built from data.py, which is generated from the design YAML
# (tools/gen_apworld_data.py). Edit the YAML, not this table.
LOCATION_TABLE: Dict[str, LocationData] = {
    name: LocationData(code, category, priority, requires, after)
    for name, code, category, priority, requires, after in TASKS
}

LOCATION_GROUPS: Dict[str, set] = {}
for _name, _data in LOCATION_TABLE.items():
    LOCATION_GROUPS.setdefault(_data.category, set()).add(_name)
