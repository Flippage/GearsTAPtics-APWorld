from worlds.generic.Rules import set_rule

from .data import GOAL_TASKS
from .locations import LOCATION_TABLE

# Goal option -> the check whose completion wins.
GOAL_LOCATION = {
    0: "Kill The Brumak",
    1: "Kill The Corpser",
    2: GOAL_TASKS[0],                  # the design YAML's goal: "Complete Act 3"
    3: "Complete Veteran Mission 20",
}


def _rule(player, requires):
    items = dict(requires)
    if not items:
        return lambda state: True
    return lambda state: all(state.has(n, player, c) for n, c in items.items())


def set_rules(world) -> None:
    player = world.player
    for loc in world.multiworld.get_locations(player):
        data = LOCATION_TABLE.get(loc.name)
        if data and data.requires:
            set_rule(loc, _rule(player, data.requires))

    goal = GOAL_LOCATION[world.options.goal.value]
    world.multiworld.completion_condition[player] = \
        lambda state: state.can_reach_location(goal, player)
