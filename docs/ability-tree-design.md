## v6 — APClassLevel: class-shared native level/skill-points/tree (2026-09-27)

**This is a new, separate system from everything above.** v1-v5.6 (GearSkillsMenu + APSkills) are
about *AP-granted skills*: `APSkills_state.json`'s `granted[Class]` (a skill usable class-wide) and
`assigned[gear]` (which granted skill is equipped on a specific gear), surfaced as rings/right-click
in the Skill Tree. None of that changed and none of it is described below.

**What v6 is about instead**: the game's own *native* skill tree and native leveling. Clarified by
Flip (2026-09-27) after an initial mix-up on my part: the native tree exists **purely to trigger AP
checks** (APSkills' `scanPurchases`, unchanged, reading `AbilityTreeItemUnlockOrder`) -- spending a
real native point has no gameplay benefit of its own. But every gear of a class must still look
identical to every other gear of that class: same level, same unspent native skill points, same
native tree nodes Obtained, in addition to the same AP-granted/assigned skills above. And an AP
"+1 <Class> Level" item raises the WHOLE class's level (every gear of that class, existing and new);
an AP "+1 <Class> Skill Point" item adds one native point to the whole class, spent by buying any
one node on any one gear of that class (which must then mirror onto every other gear of the class).
Native mission-completion leveling/point-grants are supposed to stop entirely -- only AP items may
move a class's level or points.

### The two native calls this needed (found live, 2026-09-27)

Both found the same way as `CreateSoldierItem` (see `recruit-troops-design.md`'s methodology note):
a WinDbg dump of the decrypted `.text` disassembled offline. Static call-graph analysis alone
couldn't isolate either function (too many candidate instructions touching the relevant fields
across dozens of root functions) -- resolved instead by a live WinDbg hardware watchpoint
(`ba w4 <CurrentAbilityPoints address> "<dump registers/stack>; g"`) while Flip bought two real
tree nodes in-game ("Intimidate Lv1" and "Enraged Bayonet" on Issac "Buster" Cook), reading the
resulting call stack.

- **`void GanderCharacterData::LevelUpTo(GanderCharacterData* this, int32 level)`** -- RVA `0xC1BAD0`.
  Disassembled signature confirmed (`rcx`=this, `edx`=level). Loops `level - this->Level` times
  calling `AddExperience` (RVA `0xC09B90`) with the exact XP delta from the game's own level table,
  so Health/derived stats recompute exactly like natural leveling. **Level-up only**: the loop count
  is `level - this->Level`, so calling it with `level <= this->Level` is a silent no-op -- it can
  never lower a gear's level. Also grants whatever native skill points that table awards per level
  (same as a natural level-up); APClassLevel corrects `CurrentAbilityPoints` back to its own tracked
  total right after every call, since only "+1 Skill Point" items are allowed to move that number.
- **`bool GanderCharacterData::UnlockAbility(GanderCharacterData* this, int32 index, bool bFree)`**
  -- RVA `0xC23570`. Disassembled signature confirmed (`rcx`=this, `edx`=index, `r8b`=bFree). Requires
  `AbilityTree.Abilities[index].AbilityState == 1` (Available) to do anything; on success it
  lazy-inits `CurrentAbilityPoints` from `AbilityPoints` if uninitialized, requires
  `CurrentAbilityPoints > 0`, decrements it, and sets `AbilityState[index] = 0` (Obtained). `bFree`
  does **not** bypass the point cost or an unmet prerequisite -- fully disassembled its only effect:
  when the node ISN'T in state 1, `bFree=true` turns an already-Obtained node into a no-op success
  (used internally for prerequisite bookkeeping) but a still-Locked node still fails regardless.
  APClassLevel always calls this with `bFree=false` -- mirroring a purchase really does spend a real
  point on every other gear too, matching "remove 1 skill point from all `<class>` gears". Because
  the prerequisite must already be Obtained on the target gear, mirroring always replays a class's
  `unlocked` list in original purchase order, never out of order.

Both added as new guarded exports on **`APRoster\dlls\APRosterNative.dll`** (same freestanding-DLL
conventions as `CreateSoldierItem`: 32-byte prologue self-check per RVA, live-instance-of-
`GanderCharacterData` check, `__try/__except` around the call). Request/response travel through
small text files in `APRoster`'s own mod folder (`native_lvlup_*.txt`, `native_unlock_*.txt`) because
that's where the DLL's `DllMain` resolves its root to, regardless of which mod's Lua calls it.
Source: `APRoster\src\aprosternative.c`.

### v1 bug + fix, first live confirmation (2026-09-27)

First live test (migration + a native purchase on one of two Scout gears, Francisca "Shock" Jenkins)
showed a partial result: `CurrentAbilityPoints` deducted correctly on the OTHER Scout (Kim "Slasher"
Buie) -- confirming that field IS plain-Lua-reflected and writable, no raw-memory fallback needed --
but the tree state itself never mirrored. `UE4SS.log` showed why: every `UnlockAbility` call was
refused with `"ERR prologue mismatch (game updated?) -- refusing"`. Root cause was my own
transcription, not the game: manually counting instruction bytes from the disassembly I dropped an
8-byte instruction (`movq %rbx, 0x98(%rsp)` at RVA `0xC2358D`) and substituted 3 bytes from the next
one instead, so the hardcoded 32-byte prologue array never matched. Recomputed directly from the
objdump addresses (not by hand) and re-verified byte-for-byte before rebuilding. `LevelUpTo`'s array
was independently re-checked the same way and was already correct.

Also found in that same first test: a raw `Level`/`CurrentAbilityPoints`/`AbilityState` write has no
native UI notify, so the Barracks roster list kept showing stale numbers until a save/reload (the
migration correctly reset Gabe/Sid to level 1 underneath, but the visible list didn't move). Fixed
with the same trick APRoster v15 already uses for newly-injected gears:
`UIWidget_Meta_RosterList:SetDataContext(vm)` rebuilds the grid rows from the roster VM's current
list, re-reading every bound field fresh. APClassLevel v2 calls this once after any change
(migration, new-gear sync, purchase mirroring, `addLevel`, `addSkillPoint`) -- never on a fixed
timer (see the perf lessons below).

**Confirmed working live by Flip after both fixes**, v2, 2026-09-27: bought 2 skill points on a
Sniper gear -- the purchase mirrored onto Mikayla (the other Sniper) correctly, tree state included.
(In hindsight this test didn't actually exercise the roster-refresh fix below -- see v3 -- it was
observed by opening Mikayla's own Skill Tree screen, a fresh navigation that reads current state
regardless of any refresh trick. The refresh fix's real first test was the v3 bug below.)

### v3 bug + fix: SetDataContext alone doesn't refresh existing rows (2026-09-27)

First live test of the level-up path (`Ctrl+Alt+L`): "scouts levelled up to 3 but roster still
shows them on level 2." `UE4SS.log` confirmed the level change itself worked --
`LEVEL Scout -> 3 ... Marcella "Specter" Trinh: leveled up to 3, replayed 2/2 node(s), points-write
ok` (and likewise for Francisca and Kim) -- but v2's `refreshRosterRows()` call afterward was
silent (no log line at all, an observability gap fixed in the same pass), so there was no way to
tell from the log whether it even ran.

Root cause: `RosterList:SetDataContext(vm)` re-renders rows from `vm.SoldierViewModelList`, but
each entry in that list is a `UGanderSoldierRosterItemViewModel` built **once** by the game's own
native `CreateSoldierItem` (RVA `0xF8F8D0`, the same call APRoster uses for brand-new gears -- see
`recruit-troops-design.md`). Its fields, Level included, are a snapshot copied at construction, not
a live binding back to the `GanderCharacterData`. Re-calling `SetDataContext` with the *same* stale
item VMs just re-renders the same stale numbers, no matter how many times it's called. (The earlier
v2 doc note claiming the level-1 migration reset was "confirmed working live... visible after the
roster-refresh fix" was an assumption on my part, not an actual re-test with the fix in place --
this bug had been present since v2 and simply hadn't been exercised by a test that looked at the
roster LIST screen specifically.)

Fix, v3: rebuild the specific item VM(s) that changed -- call native `CreateSoldierItem` again for
that (already-existing) gear, find its index in the live `GanderCharacterRoster.SoldierRoster`
array (APRoster keeps `SoldierViewModelList` in lockstep with `SoldierRoster`, same index), and
splice the fresh item into `vm.SoldierViewModelList` at that index *before* calling
`SetDataContext`. Also added actual logging of `refreshRosterRows()`'s outcome (screens matched,
items rebuilt, failures) at every call site instead of calling it silently, precisely so a gap like
this can't hide again. **Deployed, not yet re-tested live** -- next step is repeating the
`Ctrl+Alt+L` Scout test and confirming the roster list shows level 3 immediately, no reload.

**v3 confirmed live by Flip (2026-09-27)**: level-ups on every class, and a forced level-DOWN
(Heavy 4 -> 1 via inbox `level Heavy -3`, the raw-write path), all updated the open roster list
immediately with no reload (`LEVEL Heavy refresh: 1 roster screen(s), 2/2 item(s) rebuilt`).

### v7 (+ APRoster v18): the roster list is SORTED -- entries matched by gear, headers kept (2026-09-28)

Flip spotted that after an injection or refresh the roster lost its HEROES / AVAILABLE UNITS
sections and showed every gear in one plain list. Measured live:

- **The game re-sorts `SoldierViewModelList` whenever the roster screen opens**: heroes first
  (Gabe, Sid, Jack, Mikayla), then the rest by level, highest first (Tyrone, level 1, last).
  `SoldierRoster` stays in join order. So **list index != roster index** -- v3-v6's
  `rebuildItemVM` assumption was wrong. It spliced the rebuilt entry at the gear's ROSTER index,
  overwriting a different gear's entry. A partial rebuild could show one gear twice and another
  missing until a menu switch; a full re-sync forced the whole list into roster order (Flip's
  screenshot).
- **Section headers are stored on the list entries:** `GanderSoldierRosterItemViewModel`
  `.GroupHeaderVisibilityBinding.Value` (4 = shown, 1 = collapsed) and
  `.GroupHeaderTextBinding.Value` (e.g. `'Heroes'`, `'Available Units 12/100,001'`), set only on the
  first entry of each section. A fresh `CreateSoldierItem` entry has them blank. Both are plain
  `{Value}` structs, and nested writes (`it.GroupHeaderTextBinding.Value = FText(..)`) work from Lua.
- **Each entry points at its gear:** `GanderSoldierRosterItemViewModel.CharacterData`
  (ObjectProperty -> GanderCharacterData). Other useful reflected fields: `SoldierLevelText` and
  friends (`TextEventBinding {Value}`), `HealthWidgetVM`, `SoldierSubSceneViewModel`.
- **APClassLevel v7:** `rebuildItemVM` finds the gear's entry by `CharacterData`, copies the old
  entry's two header values onto the new one, and replaces it in place. Order and sections survive.
- **APRoster v18** (v17 didn't work live): the ~10 pooled rows copy an entry's header into their
  `Title` only when (re)bound, and a **re-used row is not re-bound** -- neither by our
  `SetDataContext` rebuild nor on a Recruit -> Roster switch. So v17's entry-only write never showed,
  and after a Recruit -> Roster switch the native "Available Units 14/100,001" stayed on screen with
  its cap: the existing strip only runs on row-load events, which don't fire for re-used rows.
  v18's `fixListHeaders(scene, available)` fixes the header ENTRIES and the visible row showing each
  one. Rows are reached via `scene.RosterList.RosterGridPanel.GridPanel` children, each with
  `.DataContext` -> entry, so no FindAllOf. It runs on every roster-screen event (strip `/cap` only)
  and after an injection (Available count = non-hero gears). `GearsCountText` = roster size after an
  injection. An injected gear is still
  appended at the end of the list -- fine in practice, since recruits land in the last (available)
  section -- and the game re-sorts on the next screen open.
- Not yet confirmed live.

### Injection stutter pass (APRoster v19 + APClassLevel v8, 2026-09-28)

Flip saw a ~0.5 s hitch on every gear injection. Measured live: **every `FindAllOf` /
`FindFirstOf` costs ~40 ms** (even `FindFirstOf("PlayerController")`), while the list rebuild
(`RosterList:SetDataContext`) is **6 ms** and the native `CreateSoldierItem` call **8 ms**. One
injection did 6 lookups in APRoster's frame (~240 ms), then APClassLevel's next tick re-synced the
"new gear" and did 3 more (~120 ms), rebuilding its roster entry a second time.

- **New entry caught during our own native call** instead of a `FindAllOf` over every roster
  entry: `NotifyOnNewObject("/Script/GanderGame.GanderSoldierRosterItemViewModel")`, armed only for
  the duration of the DLL call. Verified live: it fires exactly once, synchronously inside the call,
  with the same address the DLL returns. Rule 3-safe: the callback only records the object, and the
  caller checks the address and drops it. The `FindAllOf` stays as a fallback.
- **Squad roster VM reached from the roster screen** (`screen.RosterSubSceneViewModel:GetOuter()
  .SquadRosterViewModel` -- verified to be the same object as the PlayerController path) using the
  single `FindAllOf("UISubScene_Meta_RosterV2_C")` each refresh already needed. The PlayerController
  path is only the fallback when no roster screen is open.
- APRoster passes the roster it already found to the counts (no second `liveRoster()`), and moves
  the portrait-controller lookup two frames later (the render is async anyway).
- Result by count: the injection frame goes from ~6 lookups to ~2 (roster + screens), and
  APClassLevel's follow-up from 3 to 1. Not yet confirmed live.
- **Found alongside, fixed in APClassLevel v8:** native `UnlockAbility` spends a real point and
  refuses at `CurrentAbilityPoints == 0`, so a freshly joined level-1 recruit never received its
  class's purchased nodes (live: `node 16 unlock FAILED (OK 0)` on a new Heavy). The replay now
  gives the gear `#unlocked + 1` points first; the final write restores the class record's points.

### v4: Jack's class name is "Jackbot" (2026-09-27, confirmed live)

`classOf` resolves Jack to `"Jackbot"` (his tree asset is `AttributeTree_Jackbot_*`), but
APClassLevel's keybind cycle list and `CLASS_BY_ENUM[6]` said `"Jack"`, so "+1 Jack Level" logged
`syncing 0 gear(s)` and created a phantom `"Jack"` record no gear ever matched. Renamed both to
`"Jackbot"`; confirmed: `LEVEL Jackbot -> 2, syncing 1 gear(s) ... Jack: leveled up to 2`. The stale
`"Jack"` key is left in `APClassLevel_state.json` as inert data. **The AP client must address Jack
as `Jackbot`** (in both APClassLevel and APSkills, which share the same `classOf`).

### v5: class level-ups are CHECKS, not items (Flip's design change, 2026-09-27)

Because levels give nothing but native skill points (see the next section), Flip changed the
design: a level-up is a check, and skill points stay items. What changed in APClassLevel:

- **Natural mission-XP leveling is the trigger now, not something to block** (this retires the old
  "natural leveling isn't blocked" known gap). On the watch tick, if any KNOWN gear of a class is
  above the class record's level, the record rises to that level (capped: 15 for gears, 7 for
  Jackbot, read from the gear's `ProgressionConfigClass` CDO's `LevelUpExpThresholds` length). Every
  other gear of that class is raised to match via native `LevelUpTo`, and the native +2 skill points
  are taken back (`CurrentAbilityPoints` = class record points).
- **One check per level gained**, appended to `APClassLevel_outbox.txt` as
  `check ClassLevel <Class> <n>` (e.g. `check ClassLevel Heavy 2`). `rec.checkedLevel` records the
  highest one sent; anything between it and `rec.level` goes out on the next tick. That backfills,
  so the test levels already in the state file (Scout 5, Sniper 4 ...) will send their checks once
  on first load of v5. Level 1 is the start level and sends nothing.
- A gear **joining** above the class level (recruit, hero auto-join) is still pulled down and does
  not count as a level-up: detection only looks at already-known gears and runs before the
  newcomer sync.
- Gears keep their own XP. The class level is the highest level any gear reaches.
- `Ctrl+Alt+L` now **simulates a natural level-up** (native `LevelUpTo` +1 on one known gear of the
  cycled class), so it exercises the real detection path. The inbox `level <Class> <n>` command
  stays as a debug/admin override (clamped to the cap; raising it also sends the checks).
- **Deployed, not yet live-tested.**

### What a level-up actually changes (read live from the game's config, 2026-09-27)

Source: `GanderCharacterData.ProgressionConfigClass` -> CDO of
`/Game/Gameplay/Progression/BP_GanderProgressionConfig_Operation` (all 5 gear classes) or
`BP_GanderProgressionConfig_Jackbot` (Jack only). Two parallel arrays: `LevelUpExpThresholds`
(float) and `LevelUpDescriptors` (`/Script/GanderGame.LevelUpDescriptor`: `Health`, `MovementPoints`,
`Accuracy`, `EvasionIncrease`, `ActionPoints` (floats), `AbilityPoints`, `CardSlot` (ints),
`GrubHuntScore` (float), `MinimalVeteranLevel` (int)). No live instance exists; the game uses the CDO.
Read with UEBridge eval (`~/ueb.py` on the device writes `ue4ss\bridge\request.json`); a struct
array's field list comes from `arrayProp:GetInner():GetStruct()`, since the elements themselves
don't expose `GetStruct()`.

- **Health, MovementPoints, Accuracy, EvasionIncrease, ActionPoints and CardSlot are 0 at every
  level, for every class including Jackbot.** Leveling changes no combat stat. Confirmed against
  live gears: base Health 500 / Accuracy 0.60 / Movement 6 at levels 1 through 5 alike. (Sid's 560
  comes from gear or a passive, not level.) **So the "forced level-down doesn't recompute Health"
  gap is moot**: there is nothing level-derived to recompute.
- **AbilityPoints: +2 per level from level 2 on** (level 1 row = 0). Total native points at level N
  = 2*(N-1). Gears max out at 28 (matches the tree's "x / 28" counter).
- **GrubHuntScore**: 3 at L1 rising to 18 at L15 (Jackbot 3 to 9). A hidden score for Grub Hunt
  missions, not a combat stat.
- **Level caps: gears 15, Jackbot 7** (array lengths). The XP-to-next-level table for gears is
  L1->2 800, 2->3 800, 3->4 1700, 4->5 2400, 5->6 3200, then 4800 per level to 15. For Jackbot:
  250, 1000, 1500, 2750, 3500, 4500.
- **Note (2026-09-29): `CardSlot` is 0 at every level too** (same source table as the rest of this
  list) -- native leveling itself never grants extra `AbilityCardSlots`. The slot count comes from
  `GanderCharacterData.MaxAbilitySlots` instead -- see "APSkills v6 -- extra native ability slots"
  below.
- **Design consequences:** (1) the APWorld's 10 "Jack Level Up" checks/items can't all be real,
  because Jackbot has only 6 level-ups (1->7); (2) APClassLevel doesn't clamp `rec.level` to the
  cap yet. `LevelUpTo` indexes this table, so leveling past 15 (or 7 for Jackbot) risks reading
  past the end. Add a clamp before real AP items flow.

### APClassLevel (new mod, `ue4ss\Mods\APClassLevel\Scripts\main.lua`, v4)

- **Class identity**: exact same derivation as APSkills' `classOf` (parse `AbilityTreeType`'s asset
  name, e.g. `AttributeTree_Vanguard_Alpha_01` -> `"Vanguard"`; `CombatClass` enum only as a
  fallback) -- must produce the same strings APSkills uses, since an AP item addresses a class by
  this name in both mods. Full enum fallback table: `0 Scout, 1 Sniper, 2 Heavy, 3 Support,
  5 Vanguard, 6 Jack`.
- **One record per class** in `APClassLevel_state.json`: `{ level, points, unlocked = [node index, ...] }`
  (`unlocked` is ORDERED -- purchase order matters, see `UnlockAbility`'s prerequisite requirement
  above).
- **First-time migration**: the first watch tick that sees gears of a class with no record yet seeds
  `{level=1, points=0, unlocked=[]}` and pulls every current gear of that class to match. This is
  the deliberate, one-way reset for existing native progress (Flip's own decision, 2026-09-27,
  choosing this over leaving heroes on native leveling or freezing them at their current level): a
  hero like Gabe or Sid sitting at native level 3 drops to 1 the first time this mod runs. Since
  `LevelUpTo` can't lower level, this ONE path (only this path) writes `Level`/`CachedLevel`/
  `Experience`/`CachedExperience` directly via plain property assignment rather than the native
  call -- which means it does **not** recompute Health/derived stats the way `LevelUpTo` does. Flagged
  as a known rough edge (see Known gaps) rather than solved. Gabe/Sid's underlying `Level` field IS
  confirmed dropping to 1 on first load (seen in the migration log line); whether the roster LIST
  screen shows that live (rather than needing a reload) was wrongly marked confirmed in the v2 pass
  of this doc -- it wasn't actually re-tested with the refresh fix in place, and the v3 bug above
  shows that fix was incomplete anyway. Re-test alongside the v3 level-up re-test.
- **New-gear sync**: any gear not yet seen (recruit, hero auto-join, an APRoster-injected gear) gets
  leveled up (native `LevelUpTo`) and has the class's `unlocked` list replayed onto it (native
  `UnlockAbility`, in order, skipping any node already Obtained), then `CurrentAbilityPoints` is
  force-written to the class record's `points` as the final step (overrides whatever the native
  calls computed along the way -- simpler and more robust than trying to track running point deltas
  through however many replayed unlocks).
- **Purchase mirroring**: a 750 ms watch tick (same cadence and roster-caching pattern as APSkills'
  v5.6 perf pass -- `NotifyOnNewObject`-fed roster cache, `IsValid()`-first, no `StaticFindObject`-by-
  path in the hot loop) reads each gear's `AbilityTreeItemUnlockOrder` growth (per-gear last-seen
  length, same idea as APSkills' `LAST_ORDER`). A newly-appeared index not yet in the class's
  `unlocked` list is a genuine new purchase: appended to the record, `points -= 1`, and mirrored via
  native `UnlockAbility(otherGear, index, false)` onto every OTHER gear of the class. APSkills' own
  check-sending is untouched by any of this -- it already dedupes by `Class + Asset` globally, so it
  doesn't matter which specific gear's purchase it happens to see first. **Confirmed working live**
  twice (Scout, then Sniper) after the v2 fixes.
- **Roster-list live refresh (v3)**: any change (migration, new-gear sync, purchase mirroring,
  `addLevel`, `addSkillPoint`) rebuilds each changed gear's `GanderSoldierRosterItemViewModel` via
  native `CreateSoldierItem` (splicing it into `vm.SoldierViewModelList` at that gear's index in the
  live roster) before calling `RosterList:SetDataContext(vm)` -- see the v3 bug/fix above for why
  `SetDataContext` alone wasn't enough. Every call site now logs the outcome (screens matched, items
  rebuilt, failures) rather than refreshing silently.
- **AP-facing surface**: `_G.APClassLevel.addLevel(class, n)` / `.addSkillPoint(class, n)`, an inbox
  file (`APClassLevel_inbox.txt`: `level <Class> <n>` / `point <Class> <n>`) for future AP-client
  wiring, and test keybinds (`Ctrl+Alt+L` = +1 level, `Ctrl+Alt+P` = +1 skill point, both cycling
  through the 6 classes) for testing before real items exist. Skill-point path (and the mirroring it
  drives) is confirmed live for the underlying data (`CurrentAbilityPoints`, tree state); the
  level-up path (`Ctrl+Alt+L` / `LevelUpTo` actually raising a gear above its current level) is also
  confirmed live for the underlying `Level` field -- both exposed the v3 roster-list refresh bug
  above rather than a problem with the native calls themselves. Live re-test of the v3 fix (roster
  list showing the new level with no reload) is the immediate next step.

### Known gaps (deliberately shipped unsolved, not silently missing)

- **Natural mission-completion leveling is not blocked.** Confirmed still happening (Gabe/Sid 1->2
  after the tutorial mission with native skill-point grants shown as "PROMOTED!"; Jack leveling
  from mission completions per the Missions-screen screenshot). No reflected hook found for
  whatever triggers post-mission XP -- `AddExperience` (RVA `0xC09B90`, called by `LevelUpTo`) has no
  reflected caller either, same story as `UnlockAbility`/`LevelUpTo` before this session's WinDbg
  work found those. The real fix needs either (a) a live WinDbg watch across an actual mission
  completion (the same watchpoint-on-a-field-plus-call-stack technique that found `UnlockAbility`,
  just watching `Level`/`Experience` instead and triggered by finishing a mission rather than buying
  a node), or (b) fully mapping the level-data table (`GetLevelDataTable`-style helper at RVA
  `0xaca3e0` returns it; 40-byte-stride entries; XP-needed at struct offset `0x24` confirmed from the
  `LevelUpTo` disassembly; the Health-per-level field's offset in that same struct is NOT yet
  identified) so a forced level-down could recompute Health correctly instead of leaving it stale.
  Until one of those happens, APClassLevel logs loudly (but does not correct) when it sees a gear
  natively above its class's record level.
- **XP-bar visual freeze** (Experience/CachedExperience never visibly moving) isn't wired to any
  specific UI moment yet -- only forced alongside a level-up call. The after-mission summary
  panel's own XP-gain animation (mentioned as a design goal earlier this session) isn't addressed.
- **APRoster's own new-gear `levelFor` guess and APClassLevel's class-record level are two
  independent sources of truth** that should usually agree but aren't unified yet (see
  `recruit-troops-design.md`'s follow-up note).
- **The migration doesn't capture pre-existing native tree purchases.** If a gear (e.g. a hero)
  already had a node or two Obtained natively before this mod's first run, the migration resets its
  Level/Experience but leaves that node's `AbilityState` untouched and doesn't add it to the class
  record's `unlocked` list -- so another gear of the same class won't have it until it happens to get
  bought again through the mirrored system. Not yet hit in practice; would need the migration to read
  each gear's existing `AbilityTreeItemUnlockOrder`/`AbilityState` into the fresh record instead of
  assuming everyone starts clean.
- **No level cap clamp yet** (gears 15, Jackbot 7) -- see "What a level-up actually changes" above.
- (Resolved) the forced level-down Health gap: levels carry no Health, so nothing needs recomputing.

## v5.15 / APSkills v3 — free nodes get rings + right-click equip (2026-09-28)

Flip's request: Jackbot's start node is an ACTIVE. Keep it auto-unlocked (never an AP item), but
allow equipping/unequipping it like an AP active. Rule for free nodes (the start node, or an
`IsAlwaysUnlocked` one): **passive = always green ring; active = green (equipped) / purple
(unequipped), right-click toggles.** Free nodes stay out of the AP Skills panel and the item pool.

- **Free nodes, measured live across all 9 trees (all 6 classes):** start passives for Heavy
  (Anchor_v3), Sniper (Sharpshooter), Support (Aura_v2) and Vanguard (Regeneration). **Two classes
  start with an ACTIVE:** Scout (`GanderAbilityCard_Cloak`, start) and Jackbot
  (`GanderAbilityCard_StackingBuff`, start, plus `GanderAbilityCard_JackCloak`, `IsAlwaysUnlocked`,
  not start). (An earlier version of this note said Jackbot was the only one, which was wrong: the
  Scout tree wasn't in that save.) Before this change, GearSkillsMenu counted "free" as
  start OR always-unlocked but APSkills only counted start, so APSkills would have stripped
  JackCloak as not AP-granted. Both now use the same rule. **JackCloak must not be in the AP item
  pool** (it appeared in the earlier grantable-actives dump because that list only excluded
  `IsStartNode`).
- **APSkills v3:** `assigned[gear].startOff` = free actives the player switched off. Free actives
  are equipped by default: `applyActives` now also equips any free card not in `startOff` into a
  free slot, before the AP-assigned cards. `enforceActives` unequips a free card that is in
  `startOff` and otherwise never strips free cards (unchanged). `assign`/`unassign` of a free card
  toggles `startOff` and needs no grant ("START CARD ON/OFF" log lines). Side effect: a gear whose
  free card was natively unequipped gets it equipped at the next load, matching "default on".
- **GearSkillsMenu v5.15:** `nodeStatus` rings free nodes (no longer returns nil for them);
  `refreshFromState` reads `startOff`; `toggleStart(e)` sends assign/unassign for free actives on
  right-click. Right-clicking a free passive just logs "always on".
- Not yet confirmed live.

### v5.16 / APSkills v4 — starting skills as an option + always in the AP panel (2026-09-28)

Flip, same day: starting skills (start node, or `IsAlwaysUnlocked`) should be **optional AP
items**, and should always appear in the AP SKILLS panel as usable skills.

- **Option `include_starting_skills`** (APSkills state `options.include_starting_skills`, default
  **off**). Set it via the inbox with `option include_starting_skills on|off`; the AP client will set
  it from the YAML later.
  - **Off:** starting skills are FREE (the v5.15 rules: passive always on / green; active default
    equipped, green/purple, right-click or panel click toggles `startOff`).
  - **On:** starting skills are ordinary AP skills: red until granted, a start passive is stripped
    in missions until granted, a start active is stripped from slots unless granted + assigned.
  - The vanilla tree shows them unlocked either way. Both mods share the rule
    `isFree = start and not include_starting_skills`.
- **AP SKILLS panel = everything this gear can use:** AP-granted skills **plus** free starting
  skills (option off). Free actives show EQUIPPED/UNEQUIPPED like AP actives, and a left-click on
  their row toggles them the same way as a right-click on the node. With the option on, starting
  skills are listed once granted, like any other skill. An option change rebuilds the panel.
- **Marker for the YAML option:** `design/skill_catalog.json`, generated from the live game by
  `tools/dump_skill_catalog.py` via UEBridge (merges across saves, keyed by tree). Every node has
  `starting: true|false`, plus a `starting_skills_by_class` summary. The APWorld has **no skill items
  yet**, so the generator will read this file when they're added, and the option just filters
  `starting`. Coverage: **all 6 classes, 9 trees** -- Heavy_RTF_01, Jackbot_01, Scout_Alpha_01,
  Sniper_Alpha_01, Sniper_Mikayla, Support_Alpha_01, Support_Gabe, Vanguard_Alpha_01, Vanguard_Sid.
- **Hero trees are separate assets with identical contents** (checked node by node 2026-09-28):
  Support_Gabe vs Support_Alpha_01, Vanguard_Sid vs Vanguard_Alpha_01 and Sniper_Mikayla vs
  Sniper_Alpha_01 (Kristina "Dodger" Lawrence) have the same 35 skills,
  positions, start flags and node order -- only the asset name differs. So skill items can be
  defined per class, and node indices line up across a class's trees. (An earlier note here claimed
  they "may differ" based only on the names; Flip challenged it and the comparison disproved it.)
- Not yet confirmed live.

## v5.21 / APSkills v5 — progressive-skill (Lv1/Lv2/Lv3) double-slot bug fixed (2026-09-29)

Flip's live report: Jack's AP Skills panel listed "Shock Capsule [Lv1]" EQUIPPED and "Shock Capsule
[Lv2]" UNEQUIPPED as two separate rows, and right-clicking the tree node turned it green without
the panel row agreeing. Same pattern independently visible on Sonic Capsule. Traced to a real gap,
not a display glitch: **the whole AP-granted-skills model never had a concept of "progressive sets"
outside GearSkillsMenu's tree-ring colouring.**

- **Root cause.** A progressive active (Lv1/Lv2/Lv3 of the same skill, e.g. Shock Capsule) shares
  ONE native equip slot in the actual game -- buying the Lv2 node is meant to upgrade the same
  equipped card in place, not add a second equippable thing. `nodeStatus()`/`grantedCardFor()`
  (GearSkillsMenu, added in v5.1) already resolve this correctly for the tree's ring colours: any
  unlocked level of a set follows the set's highest-granted card. But:
  - **APSkills' own state never collapsed levels.** `M.assign(key, cardName)` just appended
    `cardName` to `S.assigned[key].cards` if not already present -- so a gear assigned "Shock
    Capsule" (Lv1) before Lv2 was ever granted, then later (re-)assigned once Lv2 became available
    (which GearSkillsMenu's right-click already resolves to `grantedCardFor`, i.e. "Shock Capsule
    Lv2"), ended up with **both** names stuck in `.cards` forever. `applyActives()` then tried to
    equip both into separate native slots -- two slots spent on what should be one skill, and (see
    below) part of why Jack's "23/25 EQUIPPED" ran out of room for 2 other skills.
  - **GearSkillsMenu's `buildPanel()` (the AP Skills side panel) built one row per tree node**, not
    one row per progressive-skill SET, and read each row's equipped status straight off
    `cur.assigned[e.name]` -- the raw per-level name -- instead of through `grantedCardFor()` the
    way the ring colouring does. So a set with more than one level granted always showed one row
    per granted level, each with its own (often stale) status.
- **Fix (APSkills v5, `main.lua`):**
  - Added `levelOf(cardName)` (same `_Lv%d` suffix regex GearSkillsMenu already uses) and
    `dedupeCardsByBase(cards)`, which collapses a gear's `.cards` list to one entry per base skill,
    keeping whichever level is LATER in the list (assign always appends, so the last one is the most
    recently (re-)equipped level).
  - `M.assign()` now dedupes `.cards` by base immediately after adding the new card, so assigning a
    higher level correctly replaces a lower one going forward instead of piling up.
  - **One-time startup repair** (`cleanupDuplicateProgressiveAssignments()`, run once right after
    `loadState()`, not on a tick -- at most one file write, not per-tick I/O): scans every gear's
    already-saved `.cards` for this exact duplicate pattern and collapses it, so saves that already
    accumulated a stale lower-level entry (like Flip's Shock Capsule / Sonic Capsule) get fixed
    automatically on the next load, without needing to manually re-click every affected skill.
- **Fix (GearSkillsMenu v5.21, `buildPanel()`):** the active-row loop now tracks `shownBase` per
  base skill; the first node of a given base encountered (tree order) gets ONE row, built from
  `grantedCardFor(e)`'s resolved top-granted-level entry rather than whichever level was hit first.
  Passive rows and free (starting) active rows are untouched -- this collapsing only applies to
  granted, non-free actives, which is the only case that can actually have Lv1/Lv2/Lv3 siblings.
  The row's own `assigned`/description/click-target fields then naturally read from the resolved
  top-level entry, so they already agree with `cur.assigned` and with the ring colour -- no other
  change needed there. (`stackedDescription`'s existing Lv1..LvN text-stacking on that one row is
  unaffected and correct as-is: showing both levels' non-restated description text together, on the
  single row, is the intended behaviour, not the bug.)
- **Status: fixed, not yet live-tested.** Next test: reopen Jack's Skill Tree and confirm Shock
  Capsule / Sonic Capsule each show as a single row with a status matching the tree ring, and check
  the startup log for a `startup cleanup: ... collapsed N -> M card(s)` line confirming the existing
  save got repaired.
- **Jack's active-skill slot cap:** resolved 2026-09-30 -- see "APSkills v6 -- extra native ability
  slots" directly below. (The v5.21 fix did NOT free any real slots: the Lv1/Lv2 problem was only in
  the panel and the assigned list. Flip unassigned everything and re-assigned one by one: still 2
  short.)

## APSkills v6 — extra native ability slots for Jack (2026-09-30)

Flip's request: let Jack equip all of his actives. Before: 21 fit, TeamActions and one start card
("no free slot") did not.

### What sizes the slot array (measured live via UEBridge)

- `GanderCharacterData.AbilityCardSlots` is a real `ArrayProperty` (TArray) of **`ObjectProperty`**:
  each element is a small `GanderCharacterCardSlot` UObject (outer = the gear's character data) with
  three reflected fields: `AbilityCard` (object), `SlotStatus` (byte), `SlotNum` (int, 0-based). Its
  owner link is NOT a reflected field: set it with `SetCharacterData(cd)`, read it with
  `GetOwningCharacter()`. Other UFunctions: `EquipAbilityCard`, `UnequipAbilityCard`,
  `CanEquipAbilityCard`, `CanUnequipCurrentAbilityCard`, `SetSlotNum`, `GetSlotNum`, `SetData`,
  `SetUnavailable`, `IsEmpty`, `IsLocked`, `IsUnavailable`, `IsEquipped`, `GetSlotStatus`.
- **`SlotStatus` values (mapped live): 0 Unavailable, 1 Empty, 2 Equipped, 3 Locked.** A freshly
  constructed slot defaults to 0 (Unavailable).
- The count comes from **`GanderCharacterData.MaxAbilitySlots`** (UInt32; native getter
  `GetMaxAbilitySlots()`): **10 for every gear, 21 for Jackbot**, from the premade asset
  `/Game/Gameplay/Meta/PremadeCharacters/GanderCharacter_Jackbot` (class CDO = 5). The live roster
  Jack had exactly 21 slots, 21/21 capacity (`ArrayNum == ArrayMax`), none locked or unavailable.
- **`MaxAbilitySlots` is not saved.** Writing 23 to both the asset and the live Jack worked
  (`GetMaxAbilitySlots()` returned 23), but a main-menu reload brought both back to 21 and the array
  stayed 21. Changing the number alone does nothing.
- **The slot objects themselves ARE saved.** After appending 2 slots: main-menu reload and then a
  full game relaunch both came back with 23 slots (the two new ones still named `..._AP1`/`_AP2`),
  owner links restored by the game, `MaxAbilitySlots` back to 21. The load empties AP cards from
  slots as usual and APSkills re-equips them.
- **The "25" in the panel was never a game number.** GearSkillsMenu's counter is `equipped / total
  AP-panel active rows` (line ~711). Before the v5.21 fix merged Lv1/Lv2 rows it read "/25"; Jack has
  23 actives including his 2 start cards (StackingBuff, JackCloak).

### How a slot is added (all live-tested)

`StaticConstructObject(GanderCharacterCardSlot class, cd)` with **no name** (the engine picks a
unique one, e.g. `GanderCharacterCardSlot_20`, so it can't collide with a saved slot), then
`SetCharacterData(cd)`, `SetSlotNum(n)`, `SlotStatus = 1`, then `arr[n + 1] = slot`. **UE4SS's TArray
`__newindex` at `Num + 1` grows the array properly**: the data pointer moved and capacity went
21 -> 46 (Unreal's normal growth), so this is a real reallocation, not a write past the end. The array
holds the new object by a strong reference, so GC won't collect it. APSkills' normal
`EquipAbilityCard` then fills the new slots.

**Mission test:** 23 abilities on Jack's action bar, all equipped (Flip, 2026-09-30, with
`MaxAbilitySlots` = 23 in memory). Not yet tested: a mission after a fresh load where
`MaxAbilitySlots` is back to 21 with 23 slots -- v6 raises it to match anyway (below).

### APSkills v6 (`main.lua`, `VERSION = 6`)

- `SLOT_GROW_CLASSES = { Jackbot = true }` (only Jack grows; add a class here to extend it),
  `SLOT_GROW_CAP = 30`.
- In `applyActives`, for those classes: count cards waiting (free start cards not switched off + granted
  assigned cards in the tree) that aren't in a slot, versus free slots. If short, `growSlots` appends
  exactly the shortfall, then equipping proceeds as usual. `syncMaxSlots` raises `MaxAbilitySlots` to
  the array length on every call (it resets from the asset every load).
- **On load it is deferred:** `applyActives("load:...")` runs inside the `GanderPawn_Customizable`
  `NotifyOnNewObject` callback, i.e. mid-construction of another object, so it doesn't create objects
  there. It queues `growSlots` + `applyActives(cd, "grow")` with `ExecuteInGameThread` (once per gear,
  via `growQueued`). In practice growth happens once per save (the Barracks assign path grows inline),
  since the save keeps the slots.
- No polling, no `FindAllOf`: the check only runs where `applyActives` already ran.
- Log lines: `added N ability slot(s): A -> B`, `N card(s) waiting, M free slot(s): adding slots after
  this load step`, `wants N more slot(s) but the cap is 30`.
- Syntax-checked with a real Lua 5.4 compiler (`loadfile`), built in the cloud container from
  github.com/lua/lua tag v5.4.6 (`gcc -DLUA_USE_LINUX lua.c l*.c`; the repo has no `luac.c`). Use the
  same for future edits instead of paren counting. Backup: `main.lua.pre-2026-09-30-slotgrow.bak`.
- **Status: code deployed, not yet loaded in-game.** Flip's current save already has 23 slots, so it
  won't grow anything there; the grow path needs a save with 21 slots (an older one) to exercise it.

### APSkills v6.1 — mission-start hitch fixed (2026-09-30)

Flip: the cutscene at mission start hung while APSkills added Noelle's 17 passives to the Passive
Skills panel (log `10:32:56.83` to `10:32:58.79`, one entry every ~111 ms, ~2.7 s for the whole squad).

- **Cause (timed live in the mission via UEBridge):** per entry, `iconFor` did a `StaticFindObject`
  for the per-skill icon (**~55 ms**, texture not resident in a mission), then `LoadAsset` (**~54 ms**,
  and it always throws `Did not load assets because asset_registry was nullptr` -- the log's "Was
  unable to locate AssetRegistryHelpers"), then found the generic fallback (**~12 ms**). ~120 ms per
  entry, and the per-skill lookup missed for all 20 distinct passives seen that session. Building the
  entry (`StaticConstructObject` from a template + `FText`s) is ~0.5 ms: Sid's and Moises's cached
  rows logged 3 entries within 0.5 ms.
- **Fix:** every panel entry uses the generic `PassiveIcon` texture, looked up once and cached
  (`FALLBACK_TEX`, re-found if it dies). No per-skill lookup and no `LoadAsset` at all. If per-skill
  icons are ever wanted, they'd have to be captured while the Skill Tree screen is open (the textures
  only exist then).
- **Also:** each pawn's first passive job (~100-200 ms: `componentOf` does `FindAllOf`, plus the mods
  and the panel) is now delayed `2500 + 300 ms x (jobs already waiting)`, so a mission's pawns no
  longer run back to back (`passivePending` counter; retries unchanged).
- Not touched: `applyAllActives` still runs a `FindAllOf("GanderCharacterRoster")` (~45 ms) inside each
  pawn's construction callback (audit item 6); `componentOf` still scans with `FindAllOf`.
- Backup: `main.lua.pre-2026-09-30-iconhitch.bak`. Syntax-checked with Lua 5.4.
- **Status: fixed, not yet re-tested in a mission.** Expect Noelle's 17 entries to log within a few
  milliseconds of each other, no `Was unable to locate AssetRegistryHelpers` lines, and no hang at the
  start cutscene. The panel rows will all show the generic icon.

### Crash 2026-09-30 10:42:25 — APClassLevel's tick indexing a TArray (fixed as APClassLevel v12)

Flip was idle on the mission's Passive Skills panel; the game died with `Fatal Error! Crashdump written`
and **nothing in the UE4SS log for the 2 minutes before it** (last line `10:40:26`).

- **Analysis (dump `crash_2026_09_30_10_42_25.1701561.dmp`):** access violation (read of `0xD`) in
  `UE4SS.dll+0xC5F4CD` = `lua_getiuservalue` (lapi.c:808), called from the generic `__index` metamethod
  wrapper in `LuaMadeSimple::Lua::add_metamethods` (LuaMadeSimple.cpp:545), from `process_lua_function`,
  from `luaV_execute` via a metamethod call. Symbolized with the old-build PDB (method in "Reading a
  crash dump" in `ue4ss-threading-rules.md`). `0xD` = a userdata pointer of `3` + `nuvalue` offset `0xA`:
  the wrapper called `lua_getiuservalue` on a stack slot holding the integer `3` (release Lua has no
  `api_check`) — i.e. an integer key reaching `__index` with `-2` not pointing at the userdata.
- **Which Lua code:** the dump's `lua_State` (memory is in the dump) gives the Lua call stack. Innermost
  Lua frame = a 5-instruction closure with 2 upvalues and no constants (`GETUPVAL, GETUPVAL, GETTABLE,
  RETURN1`), defined at line 727, executing the `GETTABLE` = `function() return order[i] end` inside
  **APClassLevel's `unlockOrderOf`** (`order` = `cd.AbilityTreeItemUnlockOrder`, a TArray userdata).
  Tools: `~/scratch/dmpmem.py` (read dump memory by address), `~/scratch/luastack.py <dump> <L>` (walk
  `L->ci`). `L` is in the crash context's registers (`rcx`/`rdi`).
- **Why it ran with nothing logged:** `watchTick` (every 750 ms, all roster gears, in and out of missions)
  called `mirrorPurchases` -> `unlockOrderOf(cd)` for every gear, which rebuilt the whole list element by
  element just to compare its LENGTH with `LAST_ORDER`. Thousands of integer `__index` calls per minute,
  silently. (APSkills' tick does the same class of thing: `enforceActives` -> `slotList` indexes every
  gear's `AbilityCardSlots` each tick — not changed yet.)
- **Root cause inside UE4SS: not identified.** Something (a stale/odd wrapper or a stack-slot mix-up in
  that `__index` path) very rarely goes wrong. What we can control is exposure.
- **Fix (APClassLevel v12, `main.lua`):** new `unlockOrderCount(cd)` (`#` on the array); `mirrorPurchases`
  and the two `LAST_ORDER` seeds use the count, and `unlockOrderOf` (element reads) only runs when the count
  grew, i.e. a node was actually bought. Backup `main.lua.pre-2026-09-30-orderpoll.bak`. Lua 5.4 syntax OK.
- **Status: fixed, not yet re-tested.** Signs it's working: no crash during a long idle in a mission.
  Note the crash was intermittent (this build ran fine for other missions), so "no crash for one session"
  is weak evidence — compare crash-dump frequency over several sessions.

### APSkills v6.2 — passive panel icons from the passive's own data (2026-09-30)

Flip: vanilla passives show their proper icons in the mission panel, so v6.1's generic icon is wrong.
`CharacterModificationUIData` (the struct behind each passive class's `UIData`, which APSkills already reads
for Name/Tooltip) has `Icon` (hard `ObjectProperty` @0x30) and `IconAsset` (`AssetObjectProperty`, soft,
@0x38). The panel item VM `GanderPassiveAbilityItemViewModel` has `AbilityIconAsset` (soft) and `AbilityIcon`
(`.Value`), and no UFunctions. v6.2 sets `AbilityIcon.Value` from `ui.Icon` when it is live, else the cached
generic icon. **Unverified:** whether `Icon` is populated for these passives, or only `IconAsset` (then the
next step is resolving the soft pointer the way the item VM does — check the VM of a vanilla entry first).
Backup `main.lua.pre-2026-09-30-uiicon.bak`.

### Event-driven sync — no more tick timers (APSkills v6.3, APClassLevel v12, GearSkillsMenu v5.22; 2026-09-30, Flip's design)

Flip's rule: classes cannot level up and skills cannot be bought or equipped during a mission (gear XP is paid out at mission end), so nothing needs to be applied *to gears* in a mission. AP items that arrive in a mission are only **recorded** (state file) and applied when the convoy loads. This removes the 750 ms `watchTick` (APClassLevel) and the 1 s `WATCH_MS` scan (APSkills), which were both a stutter source (per-tick object lookups) and the crash exposure from the 10:42:25 dump (TArray indexing on a timer).

**Scene tracking** (both mods, from the `GanderPawn_Customizable` `NotifyOnNewObject` hook, which already existed): pawn name `bp_ganderpawn_customizable_c_N` = mission; a name containing `convoycustomizable` (`BP_GanderPawn_ConvoyCustomizable[_Jackbot]_C_N`) = convoy. `ConvoyPortraitCreator` is deliberately not used. A *convoy load* = the first convoy pawn after another scene, or a fresh burst of convoy pawns more than 8 s after the last one (main menu -> reload save straight back into the convoy keeps the scene at "convoy"). The hook only **queues** a debounced pass (1.5 s later) and never works inside pawn construction.

**`syncPass(why)`** (APSkills: `scanPurchases` + `enforceActives` per gear + reset-token conversion; APClassLevel: the old `watchTick`, i.e. mirror purchases, level-ups to all gears of the class, deferred levels) runs on:
- convoy load (debounced), 
- roster screen open (APClassLevel's existing `onRosterSceneEvent`, plus the roster panel's own active refresh already covers items arriving while you sit in the convoy),
- inbox command `scan` (new; GearSkillsMenu sends it — see below),
- the level-up debug keybind,
- once ~3 s after the mod loads (covers UE4SS injected mid-game; scene is worked out from the live pawns).
It returns immediately while `SCENE == "mission"`.

**GearSkillsMenu v5.22**: `notifyScan(why)` appends `scan` to `APSkills_inbox.txt` and `APClassLevel_inbox.txt` (a) when the open tree's `AbilityTreeItemUnlockOrder` count grows (checked in the existing ~1 s state-poll block, only while the tree is open) and (b) on tree teardown. So a purchase is mirrored/checked within about a second, and closing the tree always syncs.

**Still polling** (cheap, no game-object work): the 1 s inbox file poll in APSkills and APClassLevel, and GearSkillsMenu's 200 ms tick (`findOpenAbilityTree` while idle). Inbox polling could be replaced by a keybind/console command later. APSkills' pawn hook still runs `applyAllActives` (with a `FindAllOf("GanderCharacterRoster")`) inside pawn construction — audit item 6.

**Test plan**: relaunch; expect `scene: unknown -> convoy` / `scene at startup: ...` in the logs; buy a skill -> `scan requested (purchase)` then the check/mirror; close the tree -> `scan requested (tree closed...)`; send `grant`/`level`/`point` while in a mission -> logged as recorded, applied at the next `scene: mission -> convoy` pass; idle in a mission and on the passive panel with no crash and no per-second log traffic.

Backups: `main.lua.pre-2026-09-30-eventsync.bak` (APSkills, APClassLevel), `main.lua.pre-2026-09-30-scannotify.bak` (GearSkillsMenu). Lua 5.4 syntax + global/forward-declaration checks pass on all three. Unverified in game at time of writing.

### Native purchase hook — APPurchaseHook.dll (2026-09-30, verified working by Flip)

Found with WinDbg: write-watch (`ba w4`) on `GanderCharacterData.AbilityTreeItemUnlockOrder.Num` (cd + 0x7D0 + 8) while buying a node. The hit is the AddUnique inside `bool GanderCharacterData::UnlockAbility(this, int32 index, bool bFree)` (RVA 0xC23570, 0x570 bytes; same function APRosterNative already calls to mirror purchases), called from the Skill Tree UI's confirm-YES handler at RVA 0xFFFD10 (return address RVA 0xFFFD4A; args rcx=character, edx=node, r8b=0). There is no reflected UFunction for it, so a Lua hook is impossible.

`ue4ss/Mods/APSkills/dlls/APPurchaseHook.dll` (source `src/APPurchaseHook.c`; freestanding clang + lld-link like the other native DLLs, kernel32 import lib made with llvm-dlltool) detours it from DllMain: 14-byte absolute jump over the 16-byte prologue (`48 89 4c 24 08 55 56 57 41 54 41 55 41 56 41 57`, verified before patching), RWX trampoline back to +16. In the detour: call the original; if it returned true AND the return address is base+0xFFFD4A (player purchase; APClassLevel's mirror calls and internal calls are ignored) append `scan` to `APSkills_inbox.txt` and `APClassLevel_inbox.txt` and log to `ue4ss/APPurchaseHook.log`. APSkills `package.loadlib`s it at startup. GearSkillsMenu no longer polls the unlock-order count (v5.22b); it still sends `scan` when the tree closes. Remaining polls: inbox files 1 s, APToast outbox tail 750 ms, GearSkillsMenu 200 ms tick.

**Toasts**: "already checked" lines: APSkills writes `already <Class> <Asset>` to `APSkills_notice.txt` when a bought node's check was sent earlier; APToast (v13) shows it as ALREADY CHECKED. Toasts now use player-facing names via `APToast/Scripts/skill_names.lua` (asset -> Skill Tree display name, generated from `SkillProbe_trees.tsv` + `design/skill_catalog.json`, copy in `design/skill_names.json`); ClassJoined/ClassLevel/Recruit/ResetToken checks get plain wording too.

**Icons**: texture name = passive class stem (Epiphany = `BP_Passive_Combo_C` -> `Textures/Attributes/Combo`), so paths are derivable, but the textures are mostly not resident (`StaticFindObject` ~30 ms each, miss) and LoadAsset fails; next WinDbg target = the game's own icon load (write-watch on a native passive item VM's `AbilityIconAsset` at +0x1C0).

### Passive icons, take 2 — cache them from the Skill Tree screen (GearSkillsMenu v5.22; 2026-09-30)

**v6.2 result (Flip's test): icons still generic.** Measured why: `BP_Passive_*` CDO `UIData.Icon` (the hard ObjectProperty) is **null** for every passive (checked Streak, Payback). The real reference is the soft `IconAsset` (`AssetObjectProperty`, old-style TAssetPtr = pre-4.18 engine), which the game resolves asynchronously; Lua cannot read it ("Property type 'AssetObjectProperty' not supported"), `LoadAsset` fails, and `KismetSystemLibrary:LoadAsset_Blocking` / `AssetRegistryHelpers` do not exist in this build. Texture names don't follow display names (Weak Spot -> `ZeroingIn`, Epiphany -> `Combo`), so guessing paths is out.

**What does work:** while the Skill Tree screen is open the game has already loaded each node's icon, and the tree item VM exposes it (`itemVM.AbilityIcon`, a Texture2D at `/Game/Interface/GanderMeta/Textures/Attributes/<X>.<X>`). GearSkillsMenu now copies that texture into the passive class CDO's `UIData.Icon` (`cachePassiveIcons`, run at tree build and +30/+120/+300 frames, logs `passive icon cache (...)`). CDOs are never garbage collected, so the texture stays resident for the session and APSkills' existing v6.2 `ui.Icon` read finds it in a mission with zero lookups. Limitation: only classes whose Skill Tree has been opened this session are cached; others still get the generic icon. Next idea if that is not enough: warm the cache by opening each class's tree once, or find how the game's item VM resolves `AbilityIconAsset` (Lua cannot read/copy soft refs today; a UE4SS handler for AssetObjectProperty would let us read the path).

Facts: `GanderPassiveAbilityItemViewModel` (panel item) icon = `AbilityIcon.Value`; tree item VM icon = `AbilityIcon`. No 1-line test yet: open Heavy's tree, expect `passive icon cache (...): N newly cached`, start a mission, panel shows real icons.

### Passive icon loader corrupted icon paths -> Skill Tree hang (fixed as APSkills v6.6 + APTexLoad_v5.dll, 2026-09-30)

**What happened:** after a mission that used v6.5, opening Bianh's Skill Tree froze the game (no crash, no log). WinDbg `~*kn` showed the main thread in a runaway recursive directory walk (`../../../GearGame/Content/../Content/../Content/...`), reached from the Skill Tree item builder (RVA `0x1000a50` -> `0xaca850`), which builds a `FStringAssetReference` straight from a passive CDO's `UIData.IconAsset` FString (`UIData+0x48`) and requests an async load. The class's path string was garbage. A relaunch fixed it and, with the loader off, the tree opened fine (Flip's A test): the damage was in memory only, nothing on disk or in the save.

**Cause:** DLL v3/v4 `@` mode copied the CDO's 0x20-byte TAssetPtr (including its FString heap pointer) into the ProcessEvent param block. Disassembly of ProcessEvent (RVA `0x2376640`) shows it memcpy's the params into an alloca frame (`0x23767a3`) and, after the call, memcpy's every non-out param back to the caller's block (loop at `0x2376910`); the caller owns and must destroy the params. So the engine worked on, and handed back, the game's own string buffer, which left the CDO's path dangling/garbage. (The earlier WinDbg `lock xadd [rcx+8]` crash after the 92-icon bridge test is consistent with the same corruption.) The plain-path mode had a milder version of the same mistake: our static buffer in the param block, which the engine may free.

**Fix (APTexLoad_v5.dll, `#<addr>` mode):** read the class's path read-only; allocate the param FString with the game's `FMemory::Realloc` (RVA `0x220f6f0`, 16-byte prologue checked) and destroy it after the call with `FMemory::Free` (RVA `0x220ebd0`, prologue checked), exactly like the engine's own callers; then re-read the class's TAssetPtr and string and report `CHANGED` if a single byte moved. APSkills v6.6 turns the loader off for the session if anything reports `CHANGED`. The `@` and plain-path modes are gone; `?<addr>` is a read-only path report (`scratch/p_paths.lua`). The loader is always on (an on/off file gate was tried and removed: Flip called it overkill while testing), with the CHANGED self-disable. DLL v1-v4 deleted. GearSkillsMenu's tree-open icon cache only writes the hard `UIData.Icon` (never IconAsset) and was active during the A test; kept. Not yet tested: turn the loader on, run a mission, check `p_paths.lua` shows no BAD paths, and open Skill Trees several times.

### Passive icons via the game's own sync loader (APSkills v6.5; 2026-09-30; icons confirmed by Flip, but see the corruption fix above)

Supersedes "take 2" above (the tree-open cache is still in GearSkillsMenu but is no longer needed). Every passive in Noelle's mission panel now shows its real icon.

- **How the game does it:** the object dump lists `GanderGameplayBlueprintLibrary:LoadAssetFromAssetIDSync(Asset: TAssetPtr) -> UObject*` — a synchronous UFunction (exec thunk in the GanderGame module) that loads a soft asset. UE4SS Lua cannot call it: `Type 'AssetObjectProperty' not supported`. (Also in the dump: `GearUserWidget:StartLoadingAction/OnObjectAsyncLoaded`, `KismetSystemLibrary:LoadAsset/LoadAssetClass` (latent, needs a delegate + latent info), `GanderGameplayBlueprintLibrary:LoadClassAssetSync`. `UImage:SetBrushFromLazyTexture/SoftTexture` do not exist in this engine version.)
- **`APSkills\dlls\APTexLoad_v3.dll`** (source `APSkills\src\APTexLoad.c`, freestanding clang like the other DLLs; imports kernel32 + ntdll `__C_specific_handler`): export `APTexLoad` reads `native_tex_req.txt` in the mod folder. Line 1 = `<libraryCDO hex> <UFunction hex> <FString offset hex, 10>`; then one line per asset: a plain path, or `@<addr>` = copy the game's own 0x20-byte TAssetPtr from that address. It checks the CDO/UFunction are live GUObjectArray entries, takes `ProcessEvent` from the CDO's vtable slot `0x1C0` (this build's slot, see UE4SS log `UObject::ProcessEvent = 0x1C0`), builds the param block (Asset at +0, return at +0x20), calls under `__try`, and writes `native_tex_res.txt`: `OK <obj hex> <proper-case /Pkg/Path.Name> <original path>` / `NULL <path>` / `EMPTY` / `ERR ...`. Must run on the game thread.
- **TAssetPtr layout (engine < 4.18):** `FWeakObjectPtr(8) + int32 Tag(4) + pad(4) + FStringAssetReference{FString}(16)` = 0x20. The FString is at +0x10 (Data ptr, Num, Max).
- **Where the pointer is:** `CharacterModification.UIData` at CDO+0x80 (struct `CharacterModificationUIData`), its `IconAsset` at +0x38, so `@(cdo + 0x80 + 0x38)`. The game's own path is used — no guessing from class names (Streak's texture is `LuckyNumber`, some passives use `/Game/Interface/GanderGameplay/Textures/HUD/AbilityIcons/...`).
- **The returned path is lower-case** (`/game/interface/...`) and `StaticFindObject` on it misses. The DLL therefore reads the returned object's Outer and own FName from GNames and returns the proper-case path, which `StaticFindObject` resolves.
- **GC:** an unreferenced loaded texture is garbage collected within seconds (verified: 4 textures found right after loading, gone a minute later). So `preloadIcons` (APSkills) immediately writes the texture into the class's hard `UIData.Icon` (`cdo.UIData.Icon = tex`), which pins it for the session; later builds are a plain property read.
- **APSkills wiring:** `applyPassivesToPawn` collects the granted, not-natively-bought passive classes, `preloadIcons` loads the ones whose `UIData.Icon` is null, then the existing v6.2 code reads `ui.Icon`. Classes that fail are remembered (`TEX.bad`) and keep the generic star. Log: `icon loader: N/M passive icon(s) loaded+pinned in X ms`. **Cost: ~60 ms per icon on first load** (0.2 s for 3, 0.66 s for 11 at mission start); once per class per session. If it hitches, spread it over frames.
- **Crash lesson:** an earlier bridge test loaded all 92 passives at once and let them be collected; WinDbg then sat in a loop on `lock xadd [rcx+8]` with `rcx=0x80` (a refcount increment on a near-null pointer, thread 72c0). Not root-caused; the production path loads only what a panel needs and pins immediately. Detach WinDbg for these tests (its break loop freezes the bridge).
- Backup `APSkills main.lua.pre-2026-09-30-texload.bak`. Syntax-checked in-game with `load()` through the bridge.

### Class reset, record-is-truth on load, early-start thread check (APClassLevel v14b/c; 2026-09-30, confirmed by Flip)

- **`reset <Class>|all`** (APClassLevel inbox): record -> level 1 / 0 points / no purchases, and every gear of the class: raw level-down to 1, 0 points, each `AbilityTree.Abilities[i].AbilityState` copied from the tree ASSET (`cd.AbilityTreeType.Abilities[i]`, the pristine start state: 0 Obtained start/always-unlocked, 1 Available neighbours, 2 Locked), `AbilityTreeItemUnlockOrder` emptied (`TArray:Empty()` works) and refilled with the asset's obtained nodes, start node first. `checkedLevel` is kept (checks aren't re-sent); APSkills slot counts untouched. Tree node struct `AbilityTreeItem`: AbilityCard, Passive, PrimaryWeapon_WeaponEffect, AbilityState, Unlocks (int array: nodes opened when this one is bought), Disables, LocationX/YIndex, IsStartNode, IsAlwaysUnlocked. `GanderAbilityTree` also has StaticAbilities (empty), PredefinedPaths, no UFunctions. Confirmed live on 40 gears.
- **Record is the truth on load (v14c):** a reset only lives in memory until the game saves; after a relaunch the save still had old purchases (levels/points were corrected on load, nodes were not). `syncNewGear` now finds Obtained nodes that are neither asset-obtained nor in the class record, resets that gear's tree to the asset state and replays the record. Confirmed by Flip.
- **`IsInGameThread()` throws before the engine's first tick** ("GetGameThreadId called too early"): APClassLevel's 1 s inbox loop logged LUA_ERRRUN at every cold start. Every call site (APClassLevel, APRoster, APCrates, ChecksProbe, GearSkillsMenu, shared/APGrantLib) now treats an error as "not on the game thread" and queues the work (`select(2, pcall(IsInGameThread)) ~= true`).

### Crash on a Skill Tree purchase after Ctrl+R -> APPurchaseHook_v3.dll pins itself (2026-09-30)

Crash 15:22:36 buying a node on Jack right after a `reset all` + several Ctrl+Alt+P: access violation **executing** an address inside no loaded module. Not Jack-specific. Cause: Lua's `package.loadlib` keeps its library handles in a table whose `__gc` calls `FreeLibrary` when the Lua state closes, i.e. on every UE4SS hot reload (Ctrl+R). APPurchaseHook_v2.dll was unloaded then, but its detour at `UnlockAbility` (RVA 0xC23570) still jumped into the freed code. The reload's fresh copy found the stale detour and refused to patch (`NOT INSTALLED: prologue mismatch` in APPurchaseHook.log; that line was the clue). Any purchase after any Ctrl+R would have crashed.

Fix: **APPurchaseHook_v3.dll** calls `GetModuleHandleExA(FROM_ADDRESS | PIN, DllMain)` in DllMain before patching (refuses to patch if pinning fails), so the module stays loaded for the life of the process and a later `loadlib` gets the same copy (DllMain not re-run, no double install). APSkills v8 loads `_v3`. Rule: **any DLL that patches game code must pin itself.** The other DLLs (APRosterNative, APTexLoad) only export functions and are safe to unload. Needs a full game restart (the running process still has the dangling v2 detour).

### Purchase hook v2 / roster DLL v2 / sync robustness (2026-09-30)

- **APPurchaseHook_v2.dll** writes `purchased <charAddrHex> <nodeIdx>` to `APSkills_inbox.txt` and `scan` to `APClassLevel_inbox.txt` (v1 wrote `scan` to both). APSkills sets `PLAYER_BUY = {addr, idx}` and the "already checked" notice is emitted only for that node of that character when the check was sent earlier (`already <Class> <Asset>` in `APSkills_notice.txt`, shown by APToast as ALREADY CHECKED). Mirrored/replayed unlocks (APClassLevel via `UnlockAbility` with a different return address) never fire it, and a load emits nothing. `syncPass` clears `PLAYER_BUY`. APToast no longer coalesces: one toast per purchase.
- **APRosterNative_v2.dll**: `unlock_prologue_ok` accepts either the original 16 prologue bytes or the hook's detour (`FF 25 00000000 <abs> 90 90`) and still checks bytes 16..31. v1 refused to mirror once the hook was installed, so gear sync silently broke. APClassLevel loads `_v2`; APRoster still uses the original DLL for `CreateSoldierItem`. After a full game restart these can be renamed back to single names.
- **APClassLevel:** `RETRY` table + retry-mirror pass (a gear whose replay failed is retried on the next sync pass), `syncGearToRecord` returns `(report, changed)`, `LOAD SYNC repaired ...` only logs when something changed, and `sync pass (<why>): X ms, N gear(s) already in sync` gives the timing. The NEW GEAR lines at load are the once-per-session first sight of each gear (`rosterData` walk after the debounced convoy-load pass); 0 replays on a second load is the expected steady state.
- **Toast names:** `APToast/Scripts/skill_names.lua` (asset -> display name) so toasts show player-facing skill names.

### Active skill slots as AP items (APSkills v7, GearSkillsMenu v5.23, APToast; 2026-09-30, Flip's design)

New AP item per class: **"+1 Active Skill Slot - <Class>"**. Every class starts a campaign with 0 active slots; each item adds one, up to the class's number of distinct actives (levels of one skill share a slot, start cards included). Counted from `design/skill_catalog.json`:

| Class | Distinct actives | Notes |
|---|---|---|
| Heavy | 7 | Redeploy, Explosive Shot, Dig In, Reckless Shot, Heat Up, Suppressing Fire, Ultra Shot |
| Scout | 9 | incl. start card Cloak |
| Sniper | 7 | |
| Support | 8 | Group Therapy + `_lv2` = one skill |
| Vanguard | 8 | Rally + `_lv2` + `_lv3` = one skill |
| Jackbot | 23 | incl. start cards Wingman (StackingBuff) and Cloak (JackCloak) |

Regular gears already have 10 native slots, so only Jack's array needs growing (21 -> 23, the v6 mechanism, now allowed for any class).

- **State:** `APSkills_state.json` `slots.<Class>` = slots received. Inbox `slot <Class> [n]` (n defaults to 1; `Jack` accepted for `Jackbot`), clamped to the table above. Option `option locked_active_slots on|off` (default on; off = v6 behaviour, our locks removed). Test key **Ctrl+Alt+M** = +1 slot (v7 used Ctrl+Alt+K, which APCrates already binds to its reward-suppression toggle: each press also ran ~165 ms of APCrates work and flipped that toggle), cycling Scout, Sniper, Heavy, Support, Vanguard, Jackbot. Received in a mission: recorded, applied at the next convoy pass (same rule as everything else).
- **Native side (`fitSlots`):** slots 1..limit of `AbilityCardSlots` are usable (grown if short; deferred out of the pawn-construction callback like v6), every slot past the limit is emptied and set `SlotStatus = 3` (Locked). Measured live: writing 3 makes `IsLocked()` true and `IsEmpty()` false, so the existing "free slot" test refuses it; writing 1 restores it. Whether the save keeps SlotStatus is unknown, so it is re-applied on every load/sync pass.
- **Record side (`trimToSlots`):** the gear's equipped cards, in priority order = start cards that are on (tree order) then assigned granted cards (assign order). Over the limit, the lowest-priority ones are unassigned / switched off, so the AP Skills panel (which reads the record) always matches what is equipped. Runs at the start of `enforceActives` (sync passes and every pawn load).
- **Nothing is equipped automatically (APSkills v8, Flip):** with AP slots on, a starting skill is on only if the player switched it on (`assigned[gear].startOn`); a new slot just becomes free. (v7 turned start cards on by default and re-enabled them when a slot arrived; Flip: let the player decide, starting skills included.) With AP slots off the old rule applies (on unless in `startOff`).
- **Equip refused when full:** `assign` (and switching a start card on) is refused when every slot is in use (another level of the same skill doesn't count: it replaces). GearSkillsMenu refuses locally first, the panel counter reads `n / limit` with the label `SLOTS USED`, and a `noslot <Class> <n>` line in `APSkills_notice.txt` makes APToast show **NO FREE ACTIVE SLOT**.
- **Existing save:** the first load with v7 trims every gear to 0 slots (all actives unequipped, assignments dropped). Backup of the state before v7: `ue4ss/APSkills_state.json.pre-2026-09-30-slots.bak`.
- **APWorld:** the six items are not in the design YAML / `gearstactics/data.py` yet (62 copies in total if every slot is to be obtainable).
- Backups: `main.lua.pre-2026-09-30-slots.bak` in APSkills, GearSkillsMenu, APToast. Lua 5.4 syntax OK on all. **Not yet tested in game.**

### Stutter pass: no FindAllOf, native calls without files (APRoster v21, APClassLevel v14, APSkills v8, APRosterNative_v3.dll; 2026-09-30)

Flip: a hitch every time a slot / skill point / level arrived. Measured live:

| Cost | Where |
|---|---|
| **45-67 ms per `FindAllOf` / `FindFirstOf`** | roster, player controller, roster screens, Missions screen, portrait creator, game progression; several per action |
| ~4.5 ms per native call through request/response files | every `LevelUpTo` / `UnlockAbility` / `CreateSoldierItem` |
| ~16 ms per roster entry rebuild, all in one frame | APClassLevel refresh |
| **~430 ms** on the first roster open after every convoy load | APClassLevel queued all 27 gears for a rebuild after merely verifying them (bug) |
| ~165 ms per Ctrl+Alt+K | APCrates' own binding on the same key |

**Object access without searching.** Everything is reachable through properties from the game instance, which lives for the whole session (created at startup, never freed; `StaticFindObject("/Engine/Transient.GanderEngine_0:GanderGameInstance_0")` ~11 ms, once), so it is the one object kept and the rest is read fresh on each use (well under 1 ms):
- `GameInstance.GanderMetaInfo` (`GanderMetaInfo_Operation`): `.Roster`, `.GameProgression`, `.MetaInventory`, `.SquadInfo`, `.CharacterPortraitCreator`.
- `GameInstance.LocalPlayers[1].PlayerController.UISceneInterface` (`GanderMetaUISceneInterface_C`): `.BarracksViewModelManager`, `:GetBarracksSceneManagerV2().SceneStack` (the Barracks sub-scenes currently stacked, e.g. `UISubScene_Meta_RosterV2_C_0`, `..._CharacterDetails_C`, `..._AbilityTreeV2_C_0`), `.RootScene` (`GanderMainMenuSceneManager_C`).
- The Missions screen has no such property found yet (a broad property dump of `RootScene` crashed the game, 14:42:20: keep probes narrow). It is remembered from its own intro event and used only while `APFastAlive` confirms it.

**APRosterNative_v3.dll** (`APRoster\src\aprosternative.c`): the v2 file exports unchanged, plus fast exports that take arguments from and return results on the Lua stack. UE4SS.dll exports no `lua_*` API, so the DLL reads Lua 5.4's structures itself (the layout `scratch/luastack.py` walked in the crash-dump analysis): `lua_State` +0x10 `top`, +0x20 `ci`; `CallInfo` +0 `func`; `TValue` 16 bytes, tag at +8 (0x03 int, 0x13 float, 0x01/0x11 false/true, 0x16 light C function). **Self-check on every call:** `ci->func` must hold a light C function whose pointer is that very export, with 0-16 arguments; otherwise the export touches nothing and returns no results, and the Lua side falls back to the file exports. Only integers/booleans/nil are pushed (never GC objects).
- `APFastAbi()` -> 20260930 (Lua checks this once).
- `APFastAlive(addr [, classAddr])` -> true if `GUObjectArray[addr->InternalIndex].Object == addr`, not Unreachable/PendingKill, and (optionally) exactly that class. All reads SEH-guarded, so it is safe on a freed address: this is what makes remembering a screen across events safe.
- `APFastCreate(vm, cd)` -> item address; `APFastLevelUp(cd, level)`; `APFastUnlock(cd, index, bFree)` -> native bool. Same prologue and live-instance checks as the file exports; reasons for a refusal go to `APRosterNative.log` (nothing is logged on success).

**APClassLevel v14:** the chain above everywhere; fast native calls; a gear verified at load is queued for a roster rebuild only if something changed; the rebuild is spread over frames (about 6 ms per frame, lists re-bound once at the end; log `roster refresh (...): N list(s) re-bound, M entries rebuilt over F frame(s), T ms`). **APRoster v21:** chain + fast `CreateSoldierItem` + remembered Missions screen. **APSkills v8:** roster and game progression through the chain.

**Confirmed by Flip (2026-09-30):** fast path ON, Ctrl+Alt+L / Ctrl+Alt+P / injections with no noticeable stutter (40-entry refresh: 237 ms spread over 17 frames). A deliberate garbage-address test of v3's APFastAlive froze the game (the access violation went to the game's crash handler, not our __except): v4 reads GUObjectArray only (`APFastIndex` taken while alive, `APFastAlive(addr, index, class)`). Never rely on SEH in this process. If it says `off (file fallback)`, everything still works the old way.

### Missions tab roster (APRoster v20, APClassLevel v13; 2026-09-30)

The Missions tab (`UIScene_MetaMissionSelect_C`) has its own compact roster: `SimpleRosterList` (`UIWidget_SimpleSoldierRosterList_C`, native `UIWidget_Meta_SimpleRosterList`), `GearsText` "22/100,000", and 10 pooled `UIWidget_SimpleSoldierRosterItem_C` rows (native `UIWidget_Meta_SimpleSoldierRosterItem`) whose `Title` shows the section header ("AVAILABLE UNITS 18/99,996"). Its `DataContext` is the **same** squad roster VM as the Barracks list (verified live), so the entries are shared. The rows are not reachable by property: walk `SimpleRosterList.WidgetTree.RootWidget` children; the nested `UIWidget_VirtualGridPanel_C` has no `GetChildrenCount` (TrivialObject) but exposes `.GridPanel`, which holds the rows.

- **APRoster v20:** strips the caps on the screen's `OnIntroTransitionComplete` and on a row/list `OnEndAsyncLoad` (event + one frame, class IDs recorded at construction). After an injection (Ctrl+Alt+,) `refreshRosterRows` also re-binds the Missions list (`SetDataContext(vm)`) and writes the real count and the Available header (row `Title` + entry `GroupHeaderTextBinding`). One `FindAllOf` per injection, only while a Missions screen has been shown (`MS_OPEN`). Confirmed working by Flip.
- **APClassLevel v13:** its `refreshRosterRows` treats the Missions list as an open screen (rebuilds dirty entries, re-binds it, strips caps after the re-bind), and the Missions screen's intro flushes entries that changed while no list was open. Not yet tested.

### Probing notes from this investigation

- **Crashed once (2026-09-30 09:47:54):** one eval running `ForEachFunction` up the whole super chain of
  Jack's `GanderCharacterData` (up to 8 hops, to `Object`), with a `pcall` + `GetFName():ToString()`
  per function. No response was written; the dump appeared at that moment. Not symbolized. Single-class
  `ForEachFunction` on `GanderCharacterData` and on `GanderCharacterCardSlot` was fine afterwards.
  Keep function listings to one class.
- The bridge works from the device VM with `python3 scratch/bcall.py <lua file> [timeout]` (run from
  the GearsTAPtics root). It uses the mounted relative paths; `scratch/bridge_call.py` and `~/ueb.py`
  hardcode `c:/Users/...` and fail on the Linux VM. Probe scripts from this investigation:
  `scratch/p_*.lua`.

## v5 — AP status rings + focus-based right-click (2026-09-24, confirmed working by Flip)

v4.1's fixes were guesses and failed live (right-click still dead, flicker still there, hover
flash still there). v5 is based on direct measurement through the bridge, including the game's
own `shot showui` screenshots (copied out via Lua `io` from
`%LOCALAPPDATA%\GearsTactics\Saved\Screenshots\WindowsNoEditor\`). That's a useful way to *see*
the game with no computer-use access.

### What was actually going on (measured)

1. **Hover = keyboard focus, not Slate hover.** Gears' `GearUserWidget` (`bIsHoverable=true`,
   `bIsHoverableWithoutFocus=false`) turns mouse-over into keyboard focus. `IsHovered()` is false
   on the node and all its parts even while hovered, which is why v4/v4.1 right-click matched
   nothing. `HasKeyboardFocus()` is true on the hovered node. Focus **stays** after the mouse
   leaves (the node goes back to its rest colour but keeps focus), so focus alone isn't "under the
   mouse". `w:SetKeyboardFocus()` from Lua reproduces a hover exactly (amber + glow).
2. **The game ignores the widget's colour tables at runtime.** On focus it wrote native amber even
   with that node's `BorderColourData.HoverColour` set to a blue marker. On focus loss it wrote
   native Unavailable `(0.01,0.07,0.07)` (near-black: the "border disappears" flash). The cache
   is private: editing the widget table, editing the class CDO
   (`Default__UIWidget_AbilityTreePassiveItem_C`), or calling `ForceSetDataContext(vm)` all left
   it unchanged. `UIWidget_Meta_AbilityTreeItem` exposes **zero** UFunctions (hover is native
   `NativeOnMouseEnter/Leave`), so there's nothing to hook either.
3. **On hover the game changes only** `vm.BorderColour` → amber and `vm.GlowVisibility` 1 → 4.
   Background and icon colours are untouched.
4. **Flicker wasn't a rebuild.** Gabe's screen ran 4 minutes with no teardown/setup in the log.
   The v4.1 "sticky screen" theory was wrong. Cause: the empty-state TextBlock sat inside the
   ScaleBox (Stretch = ScaleToFitX). Free-width text inside scale-to-fit is a layout feedback loop.
   Rows never flickered because they're fixed width (RootSizeBox 585).

### v5 design

- **Rings:** per non-start node, one plain `Image` (StaticConstructObject, outer = screen
  WidgetTree) added to the node's `Overlay_0` (parent of the visible native border image). It gets
  `SetBrush(nativeBorder.Brush)` (`skill_border` 128×128 for cards; passives have their own
  shape), same OverlaySlot alignment/padding, `SetColorAndOpacity(status colour)`, visibility
  `HitTestInvisible` (must not steal the mouse). Colours: red `(0.85,0.10,0.08)`, purple
  `(0.62,0.22,1.00)`, green `(0.15,0.95,0.30)`. Verified on screen: exact shape overlay, and a
  hovered node still shows the game's amber glow around the ring.
- **Native border is never written any more** (no table writes, no VM writes). Rings are coloured
  on build and on status change only (`applyNodeColour` no-ops when the status is unchanged).
  There is **no per-tick colour work**.
- **Right-click:** on the click only, scan nodes for `vm.BorderColour ≈ amber (1.00,0.64,0.07)`,
  preferring one with keyboard focus. Since we never write the native border, amber ⇔ mouse on it.
- **Ring cleanup:** our rings are the only unnamed `Image_<n>` children of a node overlay (native
  parts have designer names). `buildTreeModel` removes them on setup, which covers soldier switch
  on the same node widgets and mod hot-reload.
- **Tick** (200 ms): while active, it re-validates the same screen + soldier with a few property
  reads (no FindAllOf). It reads the state file about once a second and re-sets up if the node
  widgets were rebuilt. `FindAllOf` only runs while no Skill Tree is active.
- **Empty panel message** is added straight to the ScrollBox (outside the ScaleBox) with
  `AutoWrapText`.
- **Progressive sets (v5.1, verified on screen):** `grantedCardFor(e)` = the set's highest granted
  level ≥ the node's level (nil → red). Every level up to the top grant mirrors that card's
  equipped state; levels above it stay red (e.g. only Lv2 granted → Lv1+Lv2 follow Lv2, Lv3 red).
  Right-clicking *any* unlocked level toggles the set's granted card, and `toggleActive` calls
  `recolourAll()` (no-op on unchanged nodes) so the whole set changes at once. v5 only recoloured
  the clicked card's own node, so the lower levels waited ~3–4 s for the post-toggle state re-read.

Dry-run of the tree code through the bridge before deploy: 35/35 nodes, 35 native borders,
leftover test rings removed, hover detection picked exactly the focused amber node. Preview
screenshot of the full tree with rings looked right.

Confirmed live by Flip: right-click equip/unequip on nodes. v5.1 progressive-set colouring
verified via computer use (unequip Lv3 → Lv1–3 purple, right-click Lv1 → Lv1–3 green, both
instant; stable after the 3 s state hold).

## v5.2 — native reset-skills UI hidden (2026-09-24)

Skills come from Archipelago, so while a Skill Tree is showing the mod collapses:
- the **"[F2] RESET SKILLS (COST: 1)"** button: a `UIWidget_Gander_ButtonBarItem` (e.g.
  `Gander_ButtonBarItem_C_25`) in the scene's shared bottom `UIWidget_Gander_ButtonBar`, found by
  `ButtonSlot.Action == 84`;
- the header's **"Reset Tokens"** counter: `SuppliesResource` (`UIWidget_CurrencyItem_C`) under
  `UIWidget_SceneHeader_C → … → HeaderResourcesGlitchRetainerBox → ResourcesDisplay` (a HorizontalBox,
  not a property; found by name).

Both are shared widgets the game re-shows and re-uses per screen. Verified live: after leaving the tree,
the same bar item became "[X] SWITCH TO CYCLE BY CLASS" (visible), and the game collapsed the counter
itself on the soldier screen. So the mod only hides them, only while a tree is showing, and never
restores. The tick re-checks the two cached refs (one property read each) and rescans only about once
a second or when a ref is lost.

**v5.5: no flash, and no polling scans (verified live 2026-09-25).**
- *Button source:* the bar builds "RESET SKILLS" from the **new Skill Tree screen's own**
  `ResetSkillsButtonBarSlot` / `HoldResetSkillsButtonBarSlot`. The game fills these in while building
  the screen, so editing the class defaults does nothing. `NotifyOnNewObject("/Script/GanderGame.UISubScene_Meta_AbilityTreeV2")`
  fires at creation, early enough that setting both slots to `Action = 110` (the bar's "none") with
  empty `HintText` makes the bar leave that item collapsed. The button is never drawn. Verified: the
  item came up as action 110 hidden and the fallback never fired.
  Things that did NOT work: the Barracks scene manager's `ResetAbilityTreeButtonData` (same text, and
  it has `HideForKeyboard`/`HideForGamepad` flags, but the bar doesn't read it), and
  `UIWidget_SoldierAbilityTreeV2_C.ResetButtonData`. The bar's native `SetButtonBarAtSlot` etc. are
  called from C++, so RegisterHook never fires on them.
- *Counter:* the scene manager's `HeaderConfig.bShowSupplies` is flipped natively on tree entry, which
  we can't intercept. Instead, collapsing the INNER root (`Border_0`) of the header's `SuppliesResource`
  once makes it measure 0x0 even when the game shows it (174x25 → 0x0 measured), so it never draws
  and leaves no gap. The header is `UIScene_Meta_BarracksSceneManagerV2.SceneHeaderWidget` and the bar
  is `.ButtonBar`: direct references, no scans.
- **Performance: `FindAllOf` costs ~45 ms per call** (it walks every object in the game). v5.4 and
  earlier called it every 200 ms outside the tree, a hitch 5×/s. v5.5 learns new screens and the scene
  manager via `NotifyOnNewObject` plus one seeding scan at load. Screen lookup now takes ~0 ms.
  APSkills' 0.75 s watch also did `FindAllOf("GanderCharacterRoster")` every tick (43 ms). It now
  uses a cached roster (0 ms). Full scans remain only for events (pawn load, commands, status), and
  rescans back off 5 s when the roster or progression object is missing.
- **Follow-up:** other mods call FindAllOf too (APCrates ×61, ChecksProbe ×27, MissionFlowProbe ×24,
  EventWatcher ×9, APToast ×5, APNotify ×4, …). Any of them in a timer loop is a stutter source. Not
  audited yet.

**F2 is hard-wired natively.** Collapsing the item, `SetIsEnabled(false)`, changing the item's
`ButtonSlot.Action` to 110, and changing the screen's `ResetSkillsButtonBarSlot` /
`HoldResetSkillsButtonBarSlot` `.Action` all still let F2 open the "RESET SKILLS" modal.
`CheckUIInputAction` is a native C++ call (not via ProcessEvent), so a Lua hook won't see it. With 0
reset tokens the modal only says "not enough tokens". Blocking it outright would mean detecting and
dismissing the modal.

## v5.6 — crash fix + measured perf pass across every mod (2026-09-25)

**Crash fix.** v5.5 crashed live (`00:23:35`) calling `GetFullName` on a Skill Tree screen the game
had just destroyed — a straightforward missing-`IsValid`-before-read bug, not a stale-pointer/reuse
issue. v5.6 added `isLiveInstance` (IsValid **first**, before any name/property read) plus a
path-tracking scheme (`track`/`resolve`, re-finding objects with `StaticFindObject` every tick) as a
belt-and-braces measure against pointer reuse. Deployed and confirmed crash-free by Flip after
relaunching and switching between Gabe's and Sid's trees repeatedly.

**The path-tracking scheme itself turned out to be the next perf problem.** A live measurement
(`~/counts.lua`, 2026-09-25) re-finding 586 already-known objects by `StaticFindObject(path)` took
15,521 ms total — **~26 ms per call**, on top of the ~45 ms `FindAllOf` already flagged above. GSM
v5.6's 200 ms tick and APSkills' 750 ms watch were each doing this on every single tick (screen,
barracks manager, header root; game progression), which would have reintroduced exactly the kind of
per-tick hitch v5.5→v5.6 was meant to fix — just from a different call.

**Fix, applied everywhere the pattern existed (GearSkillsMenu, APSkills, APProbe, `~/perf/helpers.lua`):**
`resolve()`/`resolveObj()` no longer call `StaticFindObject` at all. They are now pure
`isLive(t.obj) and t.obj or nil` — an O(1) check against the live-object array. This is exactly as
safe as what actually fixed the v5.5 crash (IsValid before any read); a truly-destroyed object is
picked back up by each mod's own `NotifyOnNewObject` registry or `FindAllOf` retry/back-off, not by
re-resolving a stale path. `track()`/`trackObj()` (which capture `.path`) are left in place but their
path is now unused in the hot path — harmless, and kept in case a future need for it comes up.

**Perf pass on the other mods (same session), all additive/fallback-preserving — nothing here can
regress below what each mod already did:**
- **APCrates:**
  - A pre-existing bug found and fixed first: a comment on line ~7738 was missing its `--` prefix
    (`only this manual test hotkey is disabled.` parsed as bare Lua), which meant **APCrates failed
    to load at all** (`syntax error near 'this'`) — the whole mod, including crate injection and the
    AP delivery queue, was dead until this was fixed.
  - `liveInstance(classNames)` (called from ~17 sites, including the 2 s `apPollOnce`/`drainPending`
    polls via `missionMode()`) now checks a `NotifyOnNewObject`-fed registry first for
    `GanderGame_Mission`, `GanderMetaInfo`, `GanderGameProgression` (all effectively singletons per
    session) before falling back to the original per-class `FindAllOf` loop for any class not
    registered (inventory view models etc. are untouched).
  - `apOwnedItems()`'s 586-view-model `FindAllOf` scan (used for the Convoy baseline) was left as-is:
    it's already bounded to "while not in a mission and no baseline taken yet", and its retry/backoff
    logic is load-bearing (see the comments around `AP_OWNED_PREV`) — not touched without a live
    re-test.
- **ChecksProbe:** `refreshCaches` (previously 5–7 `FindAllOf` calls back to back, run every 10 s
  while no mission was found — a real ~300 ms hitch on a timer while sat in the convoy/barracks) now
  builds `COMPS`/`MISSION_OBJ`/`CACHED_EHOLES`/`CACHED_FACTORIES`/`CACHED_ENCOUNTER_TRIGGERS` from
  `NotifyOnNewObject` registries first (`GanderUnitStatsComponent`, `GanderGame_Mission`,
  `GanderSpawner_EmergenceHole`, `GanderAIFactory`, `GanderEncounterTrigger_Base/_EHole` — all
  registered under `/Script/GanderGame`, inferred from the package every other confirmed
  `NotifyOnNewObject` call in this codebase uses). `GearSpawner_EmergenceHoleBase`'s package isn't
  confirmed, so it's left on the original `FindAllOf` fallback only. Each category still falls back to
  its original `FindAllOf` call if its registry is empty, so a wrong package guess just means "no
  regression", not "broken".
- **APTextureLib** (`shared/APTextureLib.lua`): `getTexture()` used to pay up to 4 `StaticFindObject`
  calls (~26 ms each) plus a full `FindAllOf("Texture2D")` scan on **every** call whenever the cache
  was empty (e.g. before APTexture's native injection completes, or after a level change destroys the
  `Engine/Transient` copy), with no backoff. Added a 3 s negative-cache cooldown (`lastMissAt`) so a
  miss is retried at most once every 3 s instead of on every call.

**Not yet done:** none of the above has been reloaded/re-verified live yet (the game wasn't running
when this pass finished). Next session: relaunch (needed anyway to pick up the APCrates fix, since the
mod was dead), watch `UE4SS.log` for load errors across all 5 touched mods, and re-run the
`~/counts.lua`-style timing check once more to confirm `resolve()` is now cheap.

**Lessons for future mod work on this project:**
- `FindAllOf` (~45 ms) and `StaticFindObject`-by-path (~26 ms) must **never** run on a fixed timer,
  regardless of how safe or well-intentioned the reason (path tracking was added specifically to fix a
  crash and still turned into a perf bug). Learn objects via `NotifyOnNewObject` and re-validate with
  `IsValid()` on the raw pointer — that's both the cheap path and the crash-safe one.
- When adding "safety" indirection (like path-based re-resolution) after a crash, measure its cost
  live before shipping it as the default hot path, the same way the crash itself was root-caused by
  measurement rather than guessing.

## v4 background (tree mode, still the basis of v5)

Idea from Flip + friend: instead of a separate GEAR SKILLS menu, take over the Skill Tree itself.
Whenever a soldier's Skill Tree is open: node AP status in colour, right-click a purple/green
active to equip/unequip (`assign`/`unassign` → `APSkills_inbox.txt`), left-click untouched (native
purchasing), right panel always "AP Skills" (AP actives EQUIPPED / red UNEQUIPPED, left-click a row
also toggles, then AP passives). Re-reads `APSkills_state.json` ~1 s. State re-reads are held 3 s
after our own toggle. GEAR SKILLS header button removed; native DLL no longer used.

**Passive mapping:** the tree VM's `AbilityTreeItems` line up 1:1 by index with the character's
`AbilityTree.Abilities` (35/35 for Sid), so a passive node's class is `Abilities[i].Passive`
(e.g. `BP_Passive_Leech_C`, matching APSkills' names). Node widget ↔ item via `widget.ViewModel`
address. `DescriptionVM` + `AbilityIcon` on every item VM. The builder retries while counts differ or
cards mismatch (tree still updating).

**Node widget anatomy:** `UIWidget_AbilityTreeSkillCardItem_C` / `UIWidget_AbilityTreePassiveItem_C`
(native base `UIWidget_Meta_AbilityTreeItem`, no UFunctions). Overlay_0 children: `BackgroundImage`,
`GlowImage`, `BorderImageLevel`/`BorderImageNoLevel` (cards; one collapsed) or `BorderImage`
(passives), `SizeBox_1`→`Icon`, `PowerLevelIconSizeBox` (cards). The node itself is `Visible`; its
parts are `SelfHitTestInvisible`. Colour comes from the VM (`BorderColour`, `BackgroundColour`,
`ItemColour`). The widget's `BorderColourData`/etc. tables (`AttributeItemColourData` { Hover,
Available, Obtained, Unavailable }) look authoritative but are **not read at runtime** (see v5 #2).
Native border: Hover `(1.00,0.64,0.07)`, Available `(0.05,0.29,0.33)`, Obtained
`(0.43,0.71,0.89)`, Unavailable `(0.01,0.07,0.07)`.

## Screen & widget knowledge

`UISubScene_Meta_AbilityTreeV2_C` → `WidgetTree.RootWidget` (`Overlay_0`) → `HorizontalBox_0`
(3 columns). Right column:

```
SizeBox_2 (WidthOverride 500)
  Border_0
    VerticalBox_1
      [0] Border_1 → SkillsText "Skills", SkillPointsSpent "2 / 28", UnlockedText "UNLOCKED"
      [1] AbilitySlotListWidget [UIWidget_Meta_AbilitySlotListV2_C]  (slot pad T10 B10, Fill)
            → AbilityListPanel [UIWidget_VirtualGridPanel_C]
                ScrollBox [GearScrollBox] → ScaleBox (Stretch=3) → GridPanel → 10 pooled rows
```

- Bound props: `sub.AbilitySlotListWidget`, `sub.SkillsText`, `sub.SkillPointsSpent`,
  `sub.UnlockedText`, `sub.SoldierAbilityTreeV2` (→ `.CurrentCharacter`, `.TreeWidget`
  → `.AbilityItems` = node widgets in tree order). `sub.LastFocusedWidget` (weak ptr) = the
  last hovered node. `WidgetTree:FindWidget(FName)` doesn't resolve.
- Native row `UIWidget_Meta_AbilitySlotListItemV2_C`: `RootSizeBox` (W 585), `BorderActive`/
  `BorderPassive`, `AbilityIcon`, `AbilityTitle`, `AbilityActive`/`AbilityPassive`,
  `AbilityDuration` (spare line, now our status line), `AbilityDescription`.
- **Stale screens:** re-entering the Skill Tree creates a new subscene; the old one stays alive
  (detached) until GC. Only use a subscene with a live `GetParent()`.
- Upgrade card descriptions: stack Lv1..LvN, drop a level whose unique words are ≥75% present in a
  higher level. Verified against all 17 Vanguard actives.

### Widget construction rules (hard-won)

| Widget kind | How to create | Status |
|---|---|---|
| Blueprint `UserWidget` (`*_C`) | `WidgetBlueprintLibrary:Create(worldCtx, class, owner)` | proven |
| Plain UMG widget (ScrollBox, ScaleBox, VerticalBox, TextBlock, Image, …) | `StaticConstructObject(class, <screen>.WidgetTree)` | proven |
| Plain UMG widget via `WidgetBlueprintLibrary:Create` | **never** | corrupt object; using it **crashed the game** (`crash_2026_09_24_14_18_28`) |
| `UWidgetTree::ConstructWidget` | unavailable | `Default__WidgetTree` is a `TrivialObject` |
| Child into a ContentWidget (ScaleBox, Border, SizeBox…) | `parent:AddChild(child)` | proven. `SetContent` is a `TrivialObject` and fails silently; verify with `child:GetParent()` |
| Image copying another's look | `img:SetBrush(other.Brush)` then `SetColorAndOpacity` | proven (v5). `SetBrushTintColor` is a `TrivialObject` |

Always `IsValid()`-check a created object before touching it; if false, touch nothing.
`attempt()` swallows "not callable" errors, so verify results explicitly.
Don't put free-width text inside a ScaleToFit ScaleBox (it flickers).

### Input

- UE4SS 3.0.1 `RegisterKeyBind(Key.LEFT_MOUSE_BUTTON / Key.RIGHT_MOUSE_BUTTON, fn)` works for
  mouse buttons; run handlers via `ExecuteInGameThread`.
- **Two different hover models on the same screen:** native panel rows use Slate hover (the leaf
  child under the cursor reports `IsHovered()`, not the row UserWidget; check its visible parts).
  Skill Tree nodes use **focus-as-hover** (`HasKeyboardFocus()`, sticky after mouse-out) with the
  native border painted amber while the mouse is actually on it.
- `PlayerController:GetMousePosition(outTbl, {})` works (UE4SS puts both outs into the first table
  as `LocationX`/`LocationY`). `WidgetLayoutLibrary` mouse functions and `GetCachedGeometry` are not
  usable from Lua (TrivialObject / empty struct), so geometry hit-testing isn't an option.

### Data flow

GearSkillsMenu owns no state. Reads `APSkills_state.json` read-only (`granted.<Class>.actives`/
`.passives`, `assigned.<gearKey>.cards`) with the same `classOf`/`gearKey` derivation as APSkills;
writes only `assign`/`unassign` lines to `APSkills_inbox.txt`.

## History (short)

- v1: GEAR SKILLS header button (native DLL). Worked.
- v2: floating overlay menu of button clones. Looked bad; `WidgetBlueprintLibrary.Create` on plain
  widgets → crash.
- v3.x: GEAR SKILLS toggled the native right panel into an AP list. **Confirmed working by Flip.**
- v4: tree mode via rewriting the native border tables + VM colour. Right-click used `IsHovered()`.
  Live: right-click dead, hover flashed the border blank, empty-state text flickered.
- v4.1: guesses (hitParts hover check, "sticky" screen pick, repaint every tick). All three bugs
  persisted. The every-tick repaint also risked stutter. The progressive-skill colouring from v4.1
  worked and is kept.
- v5: measured the real mechanisms; rings + focus/amber right-click + ScaleBox fix (above).
- v5.5: no button/counter flash, no polling scans for screen lookup (NotifyOnNewObject registries).
- v5.6: fixed the v5.5 destroyed-screen crash (IsValid-first), then found and fixed the path-tracking
  perf regression it introduced; perf pass extended to APSkills, APProbe, ChecksProbe, APCrates,
  APTextureLib (see the v5.6 section above). Also fixed an unrelated pre-existing syntax error that
  had APCrates completely failing to load.
- v6: APClassLevel -- class-shared NATIVE level/skill-points/tree-unlocks, a separate system from
  APSkills' AP-granted-skills model (see above). Native `LevelUpTo`/`UnlockAbility` found and wired.
  v1 shipped with a self-inflicted prologue-check bug (refused every `UnlockAbility` call); v2 fixed
  it and added a roster-list refresh (`SetDataContext`), confirmed for tree-state mirroring (Scout
  pair, then Sniper pair/Mikayla). v3 found that refresh was itself incomplete -- existing rows'
  item VMs are a one-time snapshot, not live-bound -- surfaced when `Ctrl+Alt+L` raised Scouts to
  level 3 but the roster list kept showing 2; fixed by rebuilding the changed gear's item VM via
  native `CreateSoldierItem` and splicing it back in before `SetDataContext`. Native
  mission-completion leveling still not blocked. v3's fix is deployed, not yet re-tested live.
- v5.21 / APSkills v5: progressive-skill (Lv1/Lv2/Lv3) double-slot/double-row bug fixed (see the
  v5.21 section above) -- a gear could get a stale lower level stuck in a slot alongside a newly
  granted higher one, and the AP Skills panel showed one row per level instead of one per skill.
- APSkills v6: extra native ability slots for Jack (21 -> 23+, see "APSkills v6" above). The slots
  are real `GanderCharacterCardSlot` objects appended to `AbilityCardSlots` and are kept by the save.

## Debugging practice notes

- **Ctrl+R hot-reload crash (fixed 2026-09-24).** `crash_2026_09_24_23_06_09` symbolized to
  `Input::Handler::process_event → LuaMadeSimple Registry::get_function_ref → lua_rawgeti` (null+0x40)
  on UE4SS's input thread. ChecksProbe bound **Ctrl+R** (manual cache refresh), the same combo as
  UE4SS's `HotReloadKey = R`. The reload destroys every mod's Lua state from inside the key loop,
  which could then still call ChecksProbe's callback into its dead state. Intermittent because it
  depends on how the callback list got reshuffled. Fix: ChecksProbe's refresh moved to
  **Ctrl+Home** (no mod binds Home). **Rule: no mod may bind Ctrl+R.** APCrates Ctrl+Alt+R and
  APNotify Ctrl+Shift+R still share the R key but need other modifiers, so they shouldn't match a
  Ctrl+R press. Move them too if a reload ever crashes again. APClassLevel binds Ctrl+Alt+L /
  Ctrl+Alt+P (plain letters, not R) -- no conflict.
- **Symbolizing UE4SS crash dumps:** `UE4SS.pdb` is age 11 = the Sep 3 build (`UE4SS - Copy.dll`);
  the live `UE4SS.dll` is age 14 (same GUID). Find each crash RVA's surrounding bytes in the old
  DLL, then `llvm-symbolizer --obj="UE4SS - Copy.dll" --relative-address <rva>` with the PDB beside
  it. Minidumps parse with a ~60-line Python script (exception stream 6, module list 4, memory
  lists 5/9, stack scan from the context's Rsp).
- **A 5 ms `LoopAsync` monitor crashed the game (2026-09-25, `00:34:39`).** The async thread and the
  game thread share one Lua state; a high-frequency `LoopAsync` doing `ExecuteInGameThread` work
  corrupted it. **Never run a high-frequency loop for monitoring/timing** — use one-shot bridge calls
  instead, and if a repeating check is really needed, keep it at ≥100 ms with pre-built closures.
  (APClassLevel's watch tick is 750 ms, same as APSkills' proven-safe cadence.)
- **`FindAllOf` costs ~45 ms per call; `StaticFindObject`-by-path costs ~26 ms per call** (both
  measured live via wall-clock timing through the bridge, 2026-09-25). Neither may run on a fixed
  timer. See the v5.6 section above for the full perf pass this drove.
- **Manually transcribing disassembly bytes is error-prone -- always recompute from the tool's own
  addresses, never by hand-counting instruction lengths.** The `UnlockAbility` prologue bug above
  (2026-09-27) came from doing exactly that. Now: get the raw hex for the exact address window
  directly from `llvm-objdump` (or a byte-count script), not by adding up instruction lengths from
  memory/notes.
- **A refresh call that "should" fix a UI staleness bug still needs a live re-test, not just a
  plausible mechanism.** The v2→v3 gap above (`SetDataContext` alone looked like the fix, and one
  doc pass even marked it "confirmed" without an actual matching re-test) shows why: log what a
  refresh call actually did (screens matched, items rebuilt) at every call site, not just whether it
  was *called*, so a doc claim of "confirmed working" can be checked back against real log lines.

- UEBridge `eval` is fine for small targeted probes; avoid `FindAllOf` on very common classes.
- **Never dereference `Image.Brush.ResourceObject` (or other raw objects inside struct values) from a
  bridge probe** -- crashed the game 2026-09-28 00:22:25. A first probe printed it as a bare
  `UObject: <addr>` (GetFullName failed on it -- the warning sign); the next probe called
  `:GetClass()` on it after the Skill Tree screen had closed (the 10 pooled rows were still alive
  but torn down) and the game died mid-eval. If an object prints as a bare `UObject: <addr>`, stop
  there. Copy brushes wholesale with `SetBrush(other.Brush)` instead of inspecting them.
- **AP Skills panel icons (GearSkillsMenu v5.9, 2026-09-28):** rows were blank because
  `SetBrushFromTexture(itemVM.AbilityIcon)` didn't take effect from Lua (the texture itself is fine:
  every tree item VM's `AbilityIcon` is a valid `Texture2D` under
  `/Game/Interface/GanderMeta/Textures/Attributes/`). v5.9 copies the whole brush from the matching
  tree node's `Icon` Image (`e.widget.Icon`) with `SetBrush` + its `ColorAndOpacity`, with
  `SetBrushFromTexture` as a fallback. **v5.9 still showed blank rows**: measured live, the row
  brush was `0x0 / DrawAs 0` (NoDraw) even though the copy "succeeded" -- the node's own Icon brush
  isn't populated yet at build time (~250 ms after the screen opens). A live `SetBrush` of a node's
  *filled* brush gave `128x128 / DrawAs 3` and stuck, so SetBrush itself is fine. v5.10 retried
  the copy from the tick; Flip rightly flagged per-tick retries as a stutter risk, and the real root
  cause turned out to be simpler. **Root cause (measured live):** the native row's default
  `AbilityIcon` brush is `ImageSize 0x0 / DrawAs 0 (NoDraw)`, and `SetBrushFromTexture` only swaps
  the resource (and the size with `bMatchSize`) -- it never touches `DrawAs`.
  `SetBrushFromTexture(tex, true)` -> `128x128` but still `DrawAs 0` (nothing drawn). **Fix, v5.11:**
  v5.11 passed a whole brush table including `ResourceObject = tex` to `SetBrush`: size and DrawAs
  applied but **the texture did not carry across the Lua table -> struct conversion (white squares
  on screen)**. **Fix, v5.12 (verified live on 4 rows):** two calls per row at build --
  `SetBrush({ ImageSize = {X=128,Y=128}, DrawAs = 3, TintColor = white })` (no resource), then
  `SetBrushFromTexture(tex, true)`, which sets the texture and leaves DrawAs alone. Texture = the tree
  item VM's `AbilityIcon`, which already exists at build time. No retries and no tick work; the v5.10
  loop is removed. Build logs `AP row icons: N set, M missing`. **General rule for Image widgets from
  Lua:** an object reference inside a struct table passed to a UFunction doesn't survive the
  conversion, so set struct fields with a table and objects with a dedicated setter
  (`SetBrushFromTexture`). And if the target's default brush may be NoDraw, set `DrawAs` first.
- **v5.12 still showed WHITE squares for most rows -- async-loaded icon textures (v5.13 fix).**
  Measured live on Sid's, Mikayla's and Jack's trees: rows whose texture was already in memory drew
  correctly (the gear's *equipped* card -- Sid's Distraction, Jack's Shield -- presumably because
  the loadout already loaded it). Every other row was white: the build-time `SetBrushFromTexture`
  got a texture whose image data wasn't ready (with `bMatchSize=true` it even reported 32x32).
  Slate draws a not-yet-ready texture as plain white and **does not redraw when the load finishes**.
  Re-applying the same texture later fixed it live (Movement Boost). No event marks the moment:
  hooked and measured `GearUserWidget:OnStartAsyncLoad / OnObjectAsyncLoaded / OnEndAsyncLoad /
  OnDataContextChanged` (only `OnEndAsyncLoad` fires on tree nodes, while their icons are still 64x64
  placeholders) and `GearViewModel:OnUIAsyncStateChanged` (never fires for
  `GanderAbilityTreeItemViewModel`). Tree-item VMs expose no UFunctions. Skill cards hold only a soft
  `UIIconTextureAsset` link and passive CDOs have no icon field, so pre-loading ourselves isn't
  possible either. **Fix, v5.13:** `setRowIcon(row)` re-reads the VM's `AbilityIcon` each call and
  uses `SetBrushFromTexture(tex, false)` (keeps 128x128). It runs at build plus two one-shot
  `ExecuteInGameThreadAfterFrames` re-applies at 30 and 120 frames, guarded by `cur.rows` identity so
  a rebuilt or closed panel is skipped. No loop and no scans (Flip asked for no per-tick retries: a
  stutter concern). Logs `AP row icons re-applied: N/M drawing`. **Confirmed live** (Tyrone: 0 set at
  build -> `re-applied: 4/4 drawing`, icons shown).
- **AP panel scrolled forever past its ends (v5.17 -> v5.18, 2026-09-28).** v5.17 swapped the
  native `GearScrollBox` for a plain `/Script/UMG.ScrollBox` (copying `WidgetStyle`,
  `WidgetBarStyle` and `ScrollbarThickness` pre-build). It **did not help**: this game's engine
  ScrollBox itself never clamps. It's engine-modified, with physics scrolling (`SetMaxScrollVelocity`,
  `GetPhysicalScrollOffset`, `ClearScrollVelocity`, `CenterElements`). Measured live:
  `SetScrollOffset(-100)` and `(5000)` were both accepted, the wheel ran to -608, and the engine's own
  `ScrollToEnd()` settles at the full content height (past the real end). The game's lists clamp in
  their virtualised grid. `GetScrollOffsetOfEnd` is a TrivialObject. **Useful:**
  `GetScrollPanelSize(bInView)` returns a float -- `true` = visible height, `false` = content height
  -- so the valid range is `0 .. content - visible`. **v5.18** clamps to that range in the existing
  200 ms tick (only while a Skill Tree is open): one offset read per tick, plus `ClearScrollVelocity`
  + `SetScrollOffset` only when past an end. There's no wheel keybind in UE4SS and `OnUserScrolled`
  can't be bound from Lua, so there's no event to hook. The plain ScrollBox is kept. Not yet
  confirmed live.
- **ROOT CAUSE of the AP panel overscroll, found by disassembly (v5.20, 2026-09-28).** Supersedes the
  v5.17-v5.19 notes above and an earlier version of this bullet, which guessed (wrongly) that
  `SetClampingEnabled` "most likely gates wheel input". Chain, read from the decrypted `.text`
  (`C:\temp\gt_text1.bin` = first `.text` at RVA 0x1000; exec thunks found via the
  `FNameNativePtrPair` name table; vtables via `.pdata` + data refs, since there is no RTTI):
  - Wheel: `SScrollBox::OnMouseWheel` (RVA `0x253fe80`, shared by `SGearScrollBox`) -> if the
    scrollbar is needed and `ConsumeMouseWheel != Never`: `ScrollBy(delta * multiplier, ...)`.
  - `SScrollBox::ScrollBy` (RVA `0x2543c40`): `new = DesiredScrollOffset + amount`, and **if the
    Slate byte `+0x815` (clamping) is set, clamps `new` to `[0, content - view]`**. `Tick` (RVA
    `0x25464e0`) also clamps the drawn offset when that byte is set.
  - `SScrollBox::Construct` sets `+0x815 = 1`, but `UScrollBox::SynchronizeProperties` (RVA
    `0x4326a30`, engine-modified) then calls `SetClampingEnabled(AlwaysCenterSelected == 0)`.
    **`AlwaysCenterSelected` (UScrollBox `+0x8b5`) defaults to TRUE in this build** (both
    `Default__ScrollBox` and `Default__GearScrollBox`). Every designer-built native list sets it false
    (clamped); a box made from Lua with `StaticConstructObject` inherits true, so clamping was OFF
    and the wheel ran unbounded. That, not the ScrollBox class, was the whole bug.
  - `UGearScrollBox::SetClampingEnabled` (vtable `+0x280`, RVA `0x1cd3900`) stores nothing on the
    UMG object -- it only forwards to the Slate widget if one exists (`SGearScrollBox` setter RVA
    `0x25445e0`, `mov [rcx+0x815], dl`). So v5.19's call before `AddChild` was a no-op, and any call
    is overwritten on the next property sync anyway.
  - `SetScrollOffset` and `ScrollAmountManually` never clamp (both measured live, even on the roster's
    own box with clamping on); only `ScrollBy` (the wheel path) and the drawn offset in `Tick` do.
  - The native roster additionally uses `ConsumeMouseWheel = Never` + an external `ScrollBar`
    sibling; that's list-specific layout, not what prevents overscroll.
  - Dead ends ruled out on the way: hooking `/Script/UMG.UserWidget:OnMouseWheel` never fires (an
    unimplemented Blueprint event is skipped before any hook runs), and `GearScrollBox.OnScrolled`
    (MulticastDelegateProperty @ `0x8e0`) is readable but not bindable from UE4SS Lua.
  - **Fix, GearSkillsMenu v5.20:** write `scroll.AlwaysCenterSelected = false` right after
    `constructPlain`, before the box is added to the panel (same UPROPERTY-before-build rule as
    `AlwaysShowScrollbar`). The v5.18 tick clamp and the v5.19 `SetClampingEnabled` call are removed.
    Build logs `scroll box GearScrollBox: AlwaysCenterSelected=false (false = native clamping on)`.
    **Confirmed working live by Flip (2026-09-28)**: scrolls to exactly the top/bottom of the
    content and stops -- no overscroll, no correction glide-back needed. Replaces the v5.18 tick
    clamp (which worked but had a visible overshoot-then-correct) with true native clamping,
    identical to every native list.
  - **General rule:** any UMG ScrollBox built from Lua in this game needs
    `AlwaysCenterSelected = false` before it's first built, or it won't clamp.
- **Panel text flicker = scrollbar layout loop (v5.14, 2026-09-28).** With Tyrone's 4 rows the panel
  flipped every few frames between two measured layouts: ScaleBox `480x709` (no scrollbar) and
  `467x653` (scrollbar, -13 px). The scrollbar appears -> ScaleToFitX scale drops -> text re-wraps
  shorter -> scrollbar no longer needed -> width returns -> re-wraps taller -> repeat. It's
  content-dependent (total height right at the visible height), not caused by the icons. Same family
  as the v5 ScaleBox flicker. `SetAlwaysShowScrollbar` and `SetScrollBarVisibility` are **TrivialObjects**
  (not callable) on this build -- the old `SetScrollBarVisibility(VISIBLE)` line had silently done
  nothing all along. Fix: write the UPROPERTYs `scroll.AlwaysShowScrollbar = true` /
  `ScrollBarVisibility = Visible` right after `constructPlain`, **before** the scroll box is added to
  the panel, so UMG copies them into Slate on first build. The scrollbar then always reserves its
  width and the scale can't flip. **Confirmed live by Flip** (Tyrone's panel steady; icons show immediately). The
  scrollbar track is now always visible and becomes a usable scroller once rows overflow. **General rule:** when a UMG setter is a
  TrivialObject, write the UPROPERTY on a freshly constructed widget before it's first added to a
  parent. Writing it on an already-built widget has no visible effect.
- **See the game without computer use:** `KismetSystemLibrary:ExecuteConsoleCommand(sub, "shot showui", pc)`,
  then find the newest PNG with Lua `io.popen('dir /b /o-d "%LOCALAPPDATA%\\GearsTactics\\Saved\\Screenshots\\WindowsNoEditor\\*.png"')`
  and copy it with `io.open` into `C:\temp` to stage and view. The screenshot lands a frame after
  the request, so a widget added in the same call isn't painted yet (take a second shot).
- **Simulate hover without the mouse:** `node:SetKeyboardFocus()` reproduces the game's hover
  state exactly (amber border + glow); focusing another node reproduces unhover.
- Before shipping a fix, reproduce the bug from the bridge first. v4.1 shipped three untested
  theories and all three were wrong.
- Dry-run new logic through the bridge against live data before deploying (description stacking,
  v4 tree model, v5 tree/ring code).
- Many unrelated historical `ue4ss/crash_*.dmp` files exist; match timestamps before blaming our code.
- **Prologue self-check pattern for native calls (established this session, v6):** before calling
  ANY hardcoded RVA natively, read that address's first 32 bytes and compare against a byte array
  captured from this exact build's disassembly -- refuse the call if it doesn't match (protects
  against a future game update silently changing the offset). Every export on `APRosterNative.dll`
  follows this now (`CreateSoldierItem`, `LevelUpTo`, `UnlockAbility`). Get the byte array from the
  tool's own output for the exact address window, not by hand-counting (see the note above).
</content>
