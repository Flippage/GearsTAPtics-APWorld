from dataclasses import dataclass
from Options import Choice, Toggle, DefaultOnToggle, Range, PerGameCommonOptions

class Goal(Choice):
    """Select the campaign victory condition."""
    display_name = "Goal"
    option_defeat_brumak = 0      # Defeat Act 1 Boss
    option_defeat_corpser = 1     # Defeat Act 2 Boss
    option_complete_campaign = 2  # Defeat Hydra / Act 3 Boss (Default)
    option_veteran_mastery = 3    # Complete Veteran Missions
    default = 2

class IncludeOptionalObjectives(DefaultOnToggle):
    """Include the 40 optional mission objective checks in the multiworld pool."""
    display_name = "Include Optional Objectives"

class IncludeVeteranMissions(Toggle):
    """Include post-game Veteran missions as location checks. Forced on when the
    goal is Veteran Mastery."""
    display_name = "Include Veteran Missions"
    default = 0

class IncludeHighKillMilestones(DefaultOnToggle):
    """Include high-tier enemy kill milestones (525 to 1000 kills)."""
    display_name = "Include High Kill Milestones"

class IncludeLootCaseMilestones(DefaultOnToggle):
    """Include all 120 Loot Case collection milestones."""
    display_name = "Include Loot Case Milestones"

class TrapPercentage(Range):
    """The design lists every item and trap explicitly. When there are more
    checks than listed items, the pool is padded; this is the percentage of
    that PADDING that becomes traps (the rest is filler)."""
    display_name = "Trap Percentage"
    range_start = 0
    range_end = 100
    default = 15

class DeathLink(Toggle):
    """When you die, everyone dies. Of course the reverse is true too."""
    display_name = "Death Link"

class IncludeStartingSkills(Toggle):
    """When enabled, starting class skills must be found in the item pool before they can be equipped.
    When disabled (default), starting skills are unlocked and equippable from the beginning."""
    display_name = "Include Starting Skills"
    default = 0

@dataclass
class GearsTacticsOptions(PerGameCommonOptions):
    goal: Goal
    include_optional_objectives: IncludeOptionalObjectives
    include_veteran_missions: IncludeVeteranMissions
    include_high_kill_milestones: IncludeHighKillMilestones
    include_loot_case_milestones: IncludeLootCaseMilestones
    trap_percentage: TrapPercentage
    death_link: DeathLink
    include_starting_skills: IncludeStartingSkills
