# Gears Tactics APWorld

Archipelago world for **Gears Tactics** (v2.0.0): 726 checks, 74 item types / 660 item copies.
Goal: Complete Act 3.

## Contents
- `gearstactics/` - the world source (`data.py` is generated, do not hand-edit).
- `gearstactics.apworld` - the packaged world (a zip of `gearstactics/`); drop it in Archipelago's `custom_worlds` folder.
- `design/MercyTactics.yaml` - the design source of truth for checks and items (Taskipelago format).
  `design/CHECK_STATUS.md`, `design/skill_catalog.json` (skill trees per class) and `design/skill_names.json`.
- `tools/gen_apworld_data.py` - regenerates `gearstactics/data.py` from the YAML.
- `tools/dump_skill_catalog.py` - dumps the skill trees from the running game (dev-only, needs the UE4SS mods).
- `docs/check-status.md` - which checks and items are built in the game mods; `docs/ability-tree-design.md` - skill/class-level design.

## Regenerate and package
```
python tools/gen_apworld_data.py design/MercyTactics.yaml gearstactics/data.py
```
Then zip the `gearstactics/` folder (without `__pycache__`) as `gearstactics.apworld`.

## Notes
- Item counts, classifications and the Reset Token cap are set in the YAML. Active Skill Slot items are progression.
- Not in the world yet: trap items (enemy Heal/Revive exists in-game only) and the weapon-mod / armour item lists.
- The in-game mods live in a separate repo (GTArchipelago).
