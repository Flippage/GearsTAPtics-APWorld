
# Gears Tactics AP: checks & items status

Baseline: `design/MercyTactics.yaml` (a Taskipelago YAML). The APWorld tables in
`gearstactics/data.py` are generated from it by `tools/gen_apworld_data.py`.
To change the design, edit the YAML and re-run the generator. Don't hand-edit `data.py`.

APWorld version 2.0.0 (updated 2026-09-29): **709 checks** (143 priority) and **68 item
types / 462 copies**. The pool is padded to the location count with filler/traps
(`trap_percentage`). Location and item IDs from 1.x were kept wherever the check or item
still exists.

## What "Working" means here (Flip, 2026-09-29)

No AP mod has been built yet, so nothing is actually delivered into a multiworld except
via manual hotkey test bindings — there's nothing to wire real delivery into yet. That is
not the same as "not working." The bar for every row below is:

- **Working** — the delivery method (writing `check <name>` to the mod's outbox file, or
  the equivalent trigger) has been **tested and confirmed**, e.g. via a hotkey-triggered
  test or an observed in-game toast/outbox line. It doesn't need a live AP session to
  qualify.
- **Not working** — either nothing has been built yet, *or* it's been built but not
  actually tested/confirmed.

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
- **Class levels are checks, not items (Flip, 2026-09-27).** The "Class Level Up Unlock × 5"
  and "Jack Level Up Unlock" items (60 copies) are out of the YAML item list; levels give
  nothing but native skill points, and skill points stay items ("+1 `<Class>` Skill Point").
  The level checks stay. Level caps (read from the game): gears **15**, Jackbot **7** -- so
  "Jack Level Up" has only 6 reachable level-ups (levels 2–7), and "Class Level 1–10" leaves
  levels 11–15 unchecked.
- **Level 1 is the default, not a check (Flip, 2026-09-27)**: the "Class Level 1" / "Jack
  Level Up 1" entries are out of the YAML. In their place, **a new "`<Class>` Class Joined"
  check per class**, sent the first time that class has any gear in the roster (the class
  still starts at level 1). **Jackbot gets one too** (Flip: he's his own class, and getting
  him into the roster is a progression point) -- 6 Class Joined checks total, and each
  "Class Level 2" task's prereq now points at its class's "Class Joined" task instead of the
  removed "Class Level 1".
- **Skill-tree purchases are now in the YAML as 196 discrete checks (2026-09-29), not a
  fixed pool count placeholder.** There are always the same 6 classes (5 gears + Jackbot)
  with identical trees per class, not a dynamic/variable set — see below.
- **+1 `<Class>` Skill Point items added to the YAML (2026-09-29)**, one per class (6 total),
  `item_count` currently a **placeholder of 10 copies each** — needs real balancing input
  from Flip against the 196 skill-tree-purchase checks.

## Checks: what we have built

| Category | Checks | Status |
|---|---|---|
| Collect Loot Crate 1–120 | 120 | **Working.** ChecksProbe LOOT hook + crate toast takeover |
| Total Enemies Killed 25–1000 | 40 | **Working.** Kill counter |
| Bayonet 20 / Lancer Chainsaw 20 / Execute 30 | 70 | **Working.** Counter; Execute 21–30 extend the same counter |
| Close E-Hole 1–15 | 15 | **Working.** 11–15 are the same counter, extended |
| Revive Any Gear 1–10 | 10 | **Working** |
| Start The Game | 1 | Trivial. Send on first connect (client side). **Not working** until that client exists |
| **Class Level 2–10 × 5** (Level 1 replaced by Class Joined) | 45 | **Working, APClassLevel v5 (2026-09-27), confirmed live this session (Ctrl+Alt+L toast test)**: a natural (mission-XP) level-up of any gear raises its whole class and appends `check ClassLevel <Class> <n>` to `APClassLevel_outbox.txt`, one per level gained, sent once each (`checkedLevel` in `APClassLevel_state.json`), with the "`{Class}` Level Up `X` - Check Sent" toast confirmed on screen |
| **Jack Level Up 2–7** | 6 | **Working, same mechanism, same toast test** -- class string is `Jackbot`, not `Jack`. Level caps at 7, so 8/9/10 don't exist and are out of the YAML |
| **`<Class>` Class Joined** × 6 (Scout, Sniper, Heavy, Support, Vanguard, Jackbot) | 6 | **Not working — built (APClassLevel v6, 2026-09-27), not yet confirmed tested.** First time a class has any gear in the roster → `check ClassJoined <Class>` in `APClassLevel_outbox.txt`, once (`joinedSent`). Classes already in the roster before v6 send theirs on first load. Jackbot included (decided by Flip). This session's toast test confirmed the Class Level path, not this one specifically -- worth a quick Ctrl+Alt+L-style check to move it to Working |
| Story / Side / Boss / Act clear | 45 | Source found (mission-complete state), **not working -- not wired** |
| Complete Optional Objective 1–40 | 40 | Source found, **not working -- not wired** |
| Convoy Size 1–18 | 18 | Source found, **not working -- not wired** |
| Heroes join (5) | 5 | Source found, **not working -- not wired** |
| Enemy Encounter (19) | 19 | Partial. Reveal detection is unreliable. **Not working** |
| Acquire Legendary × 10 types × 3 | 30 | Needs the earned-loot log. **Not working**. Snub Pistol 1–3 are new |
| Collect Supreme Loot 1–20 | 20 | Needs the earned-loot log. **Not working** |
| Complete Veteran Mission 1–20 | 20 | **No source found yet. Not working** |

### Skill tree purchases and Reset Tokens

| Category | Checks | Status |
|---|---|---|
| **Skill tree purchases** | **196** (fixed, not dynamic — 6 classes × their tree's non-starting nodes; see `design/skill_catalog.json`) | **Not working — built (APSkills), not yet confirmed tested.** A native tree purchase writes `check <Class> <Asset>` to `APSkills_outbox.txt`. All 196 are now in the YAML as their own checks (`"<Class> <Asset>"`, matching the outbox key exactly), added 2026-09-29 |
| **Reset Token 1–N** | N (cap 20 for now; **not yet added to the YAML — see below**) | **Not working — built 2026-09-24 (APSkills), the resets-always-zeroed behaviour is verified live, but the `check ResetToken <n>` delivery itself hasn't been confirmed.** Every reset token the game awards → `check ResetToken <n>` (n counts up over the save), and the token is removed at once so a skill tree can never be reset. **Not in the item pool**: AP grants skills directly, so resets aren't needed |

The 196 skill-tree-purchase names were pulled from `design/skill_catalog.json`'s 6 canonical
trees (Heavy_RTF_01, Jackbot_01, Scout_Alpha_01, Sniper_Alpha_01, Support_Alpha_01,
Vanguard_Alpha_01 — the other 3 tree assets are confirmed-identical duplicates), one task per
non-starting node, named `"<Class> <Asset>"` against `APSkills`' `class .. " " .. asset`
outbox format.

Reset tokens, details:
- They're the game's **Supplies** resource: `GanderGameProgression.Supplies` (`GanderResource`)
  `.CurrentValue`. A reset costs `ResetAbilityTreeSupplyCost` = 1. Verified live: Supplies = 2 made
  F2 ask "reset the Skills of the current Gear? YES (1)". The header's "Reset Tokens" counter reads
  the same resource but only refreshes on the game's own changes.
- APSkills' ~0.75 s watch tick zeroes Supplies first, reads it back, and only then sends checks. If
  the write fails it sends nothing and logs once, so a stuck value can't spam checks.
- The GearSkillsMenu mod also hides the "[F2] RESET SKILLS" button and the header counter on the
  Skill Tree. The F2 key itself can't be unbound, but with tokens always 0 it only shows "not enough
  tokens".
- **To decide (still open — not resolved by the 2026-09-29 YAML update):** how many "Reset Token N"
  locations the APWorld gets (= `RESET_TOKEN_MAX_CHECKS`, currently 20 as a working assumption, not
  yet in the YAML), and how the game awards tokens (source not identified; detection doesn't depend
  on it). `GanderProgressionConfig.InitialSupplies` = 1000. If a new campaign starts with that,
  the cap is what keeps it from firing 1000 checks. Reloading an older save that still held tokens
  would count them again as new numbers.
- The AP client needs to map `check ResetToken <n>` to the location, alongside the skill checks.

## Items: what we have built

| Item group | Copies | Status |
|---|---|---|
| Received-item toast (any item) | — | **Working** (APNotify, colour by class) |
| Max AP award | — | **Not working — built (APProbe) but not in the item list**, and not confirmed tested as a delivery |
| +1 `<Class>` Skill Point | 6 items × 10 copies (placeholder) | **Not working — built (APClassLevel `addSkillPoint`, inbox `point <Class> <n>`), not yet confirmed tested.** Added to the YAML 2026-09-29; the 10-copies-per-class count is a placeholder pending Flip's balancing against the 196 skill-tree-purchase checks |
| Unlock Act 2 / Unlock Act 3 | 2 | **Not working. Not built.** Must block the player from starting Act 2/3 missions until received |
| ~~Class Level Up Unlock × 5, Jack Level Up Unlock~~ | ~~60~~ | **Dropped 2026-09-27 (confirmed by Flip), removed from the YAML 2026-09-29**: class levels are checks now (see above) |
| Gear Recruit (5 classes × 3) | 15 | **Working** (APRoster v11–v15) |
| Weapon/armour/grenade mods (Common/Rare/Epic) | 205 | Route exists (APCrates reward-row injection); per-item mapping not done. **Not working** |
| In-mission buffs (Crit, Evasion, Accuracy, CTH+, Clip +1, cooldowns−, fog reveal) | 70 | Not built. **Not working**. Needs a mission-scoped modifier |
| Filler actions (reload, skill cooldown, auto revive, supplies, reinforcements, stim, empty crate/pod) | 80 | Not built. **Not working** |
| Traps (E-Hole, reinforcements, destroy supplies, down gear, cooldowns+, Nemacyst, CTH−) | 70 | Not built. **Not working** |

The act unlocks are progression. Until they're enforced in game, logic will say a check is out of
reach while the player can still do it. They matter more than the other item work.

Note: the "supplies" filler item and "destroy supplies" trap may refer to in-mission supplies. If
they meant the Supplies resource, that's reset tokens, which APSkills now always zeroes.

## 2026-09-29 YAML update

Ran against `design/MercyTactics.yaml` and regenerated `gearstactics/data.py`
(`tools/gen_apworld_data.py`, extended with `Class Joined` and `Skill Tree Purchase`
categories):

- **Dropped 9 tasks**: `<Class> Class Level 1` × 5, `Jack Level Up 1/8/9/10`.
- **Dropped 6 items**: `<Class> Class Level Up Unlock` × 5, `Jack Level Up Unlock`.
- **Added 6 tasks**: `<Class> Class Joined` × 6 (Support, Sniper, Heavy, Scout, Vanguard,
  Jackbot), priority. The five `<Class> Class Level 2` tasks and `Jack Level Up 2` now prereq
  off their class's `Class Joined` task instead of the removed `Class Level 1` / `Jack Level
  Up 1`.
- **Added 196 tasks**: one per non-starting skill-tree node across the 6 canonical trees,
  named `"<Class> <Asset>"`.
- **Added 6 items**: `+1 <Class> Skill Point` × 6, `item_count` **placeholder** `10` each.
- Cleared `item_prereqs` on all 51 surviving Class Level / Jack Level Up tasks (they used to
  require N copies of the now-dropped "Class Level Up Unlock" item).
- Net: **516 → 709 tasks**, **68 → 68 items** (6 dropped, 6 added).
- Because 4 of the 9 dropped tasks (`Jack Level Up 1/8/9/10`) and 1 of the 6 dropped items
  (`Jack Level Up Unlock`) had never been in the 1.x APWorld (no legacy ID), removing them
  shifted the sequential IDs of everything that came after them in the YAML at regen time: 24
  surviving tasks and 22 surviving items got new (lower) IDs. Nothing is live yet, so this is
  harmless, but flagging it since it's the kind of thing that would matter once a real
  multiworld exists.

**Flagged for Flip's review, not decided unilaterally:**
- `+1 <Class> Skill Point` item_count (currently `10` per class, placeholder).
- `"Jackbot Class Joined"` naming — inferred from APClassLevel's literal `classOf()` string
  (`"Jackbot"`, not `"Jack"`), matching the existing `"Jack Level Up"` special-case convention,
  but not explicitly confirmed.
- Reset Token count/cap deliberately left **out** of this YAML update — still an open decision
  (see "To decide" above).

## Removed vs 1.x
- Checks: Convoy Size 19–26 (IDs +66..+73) and "Complete The Game" (+42; the goal is now "Complete Act 3").
- Items: "Common Weapon Attachment", "Restart Mission".
- Renamed to Mercy's wording (IDs unchanged), e.g. "Acquire Loot Case N" → "Collect Loot Crate N",
  "Kill N Enemies" → "Total Enemies Killed: N", "Support Level N" → "Support Class Level N".

## Stale
- `client/location_tracker.py` still uses the 1.x names and sends IDs +42 and +66..+73,
  which no longer exist. Update it when the client is wired to the mod.
- The client will also need to read `APClassLevel_outbox.txt` (`check ClassLevel <Class> <n>` ->
  "<Class> Class Level <n>", `Jackbot` -> "Jack Level Up ...", and `check ClassJoined <Class>` ->
  "<Class> Class Joined") and `APSkills_outbox.txt` (`check <Class> <Asset>` -> "<Class> <Asset>").
