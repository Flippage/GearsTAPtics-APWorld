# Gears Tactics AP: checks & items status

Baseline: `design/MercyTactics.yaml` (a Taskipelago YAML). The APWorld tables in
`gearstactics/data.py` are generated from it by `tools/gen_apworld_data.py`.
To change the design, edit the YAML and re-run the generator. Don't hand-edit `data.py`.

APWorld version 2.0.0: **516 checks** (143 priority) and **68 item types / 462 copies**.
The pool is padded to the location count with filler/traps (`trap_percentage`).
Location and item IDs from 1.x were kept wherever the check or item still exists.

## How the Taskipelago YAML maps onto the APWorld

| Taskipelago key | Meaning | APWorld use |
|---|---|---|
| `tasks` | one check per row | location name |
| `task_priority` | `true` → AP priority location | added to `priority_locations` |
| `task_prereqs` | task indices (1-based) that must be done first | `after` chain, flattened into rules |
| `item_prereqs` | item indices required; `N*k` = k copies | location access rule (`state.has`) |
| `items` / `item_types` / `item_count` | pool entries, class, copies | ITEM_TABLE |
| `goal_tasks` | victory check | goal option 2 (Complete Act 3) |

Rules are item-only. A check needs its own items, plus every item needed by any
check up its prerequisite chain (max count per item).

Notes for the YAML:
- In Taskipelago, `8, 8, 8` means "item 8 AND item 8 AND item 8", which is only **1 copy**.
  The APWorld treats repeats as copies, which is what the list was going for. For
  Taskipelago to behave the same way it should be written as `8*3`.
- "Complete Act 4, Mission 7" was a typo and is imported as "Complete Act 3, Mission 7".
- The list has **no max-AP item**, but the APProbe mod already supports awarding max AP.
  Decide whether to add one.

## Checks: what we have built

| Category | Checks | Status |
|---|---|---|
| Collect Loot Crate 1–120 | 120 | **Built.** ChecksProbe LOOT hook + crate toast takeover |
| Total Enemies Killed 25–1000 | 40 | **Built.** Kill counter |
| Bayonet 20 / Lancer Chainsaw 20 / Execute 30 | 70 | **Built.** Counter; Execute 21–30 are new but only extend the same counter |
| Close E-Hole 1–15 | 15 | **Built.** 11–15 are new, same counter |
| Revive Any Gear 1–10 | 10 | **Built** |
| Start The Game | 1 | Trivial. Send on first connect (client side) |
| **Subtotal built** | **256** | |
| Story / Side / Boss / Act clear | 48 | Source found (mission-complete state), **not wired**. Side A2 SM5–6, A3 SM10–12 are new |
| Complete Optional Objective 1–40 | 40 | Source found, **not wired** |
| Class Level 1–10 × 5 | 50 | Source found, **not wired** |
| Convoy Size 1–18 | 18 | Source found, **not wired** |
| Heroes join (5) | 5 | Source found, **not wired** |
| Enemy Encounter (19) | 19 | Partial. Reveal detection is unreliable |
| Acquire Legendary × 10 types × 3 | 30 | Needs the earned-loot log. Snub Pistol 1–3 are new |
| Collect Supreme Loot 1–20 | 20 | Needs the earned-loot log |
| Complete Veteran Mission 1–20 | 20 | **No source found yet** |
| Jack Level Up 1–10 | 10 | **No source found yet.** Jack levels differently from class gears; all 10 are new |

## Items: what we have built

| Item group | Copies | Status |
|---|---|---|
| Received-item toast (any item) | — | **Built** (APNotify, colour by class) |
| Max AP award | — | **Built** (APProbe) but not in the item list |
| Unlock Act 2 / Unlock Act 3 | 2 | **Not built.** Must block the player from starting Act 2/3 missions until received |
| Class Level Up Unlock × 5, Jack Level Up Unlock | 60 | **Not built.** Must cap each class/Jack level to the number received |
| Gear Recruit (5 classes × 3) | 15 | Not built. Add a recruit to the barracks |
| Weapon/armour/grenade mods (Common/Rare/Epic) | 205 | Route exists (APCrates reward-row injection); per-item mapping not done |
| In-mission buffs (Crit, Evasion, Accuracy, CTH+, Clip +1, cooldowns−, fog reveal) | 70 | Not built. Needs a mission-scoped modifier |
| Filler actions (reload, skill cooldown, auto revive, supplies, reinforcements, stim, empty crate/pod) | 80 | Not built |
| Traps (E-Hole, reinforcements, destroy supplies, down gear, cooldowns+, Nemacyst, CTH−) | 70 | Not built |

The class-level and act unlocks are progression. Until they're enforced in game,
logic will say a check is out of reach while the player can still do it.
They matter more than the other item work.

## Removed vs 1.x
- Checks: Convoy Size 19–26 (IDs +66..+73) and "Complete The Game" (+42; the goal is now "Complete Act 3").
- Items: "Common Weapon Attachment", "Restart Mission".
- Renamed to Mercy's wording (IDs unchanged), e.g. "Acquire Loot Case N" → "Collect Loot Crate N",
  "Kill N Enemies" → "Total Enemies Killed: N", "Support Level N" → "Support Class Level N".

## Stale
- `client/location_tracker.py` still uses the 1.x names and sends IDs +42 and +66..+73,
  which no longer exist. Update it when the client is wired to the mod.
