"""
Regenerate gearstactics/data.py from the design YAML (Taskipelago format).

    python tools/gen_apworld_data.py design/MercyTactics.yaml gearstactics/data.py

The Taskipelago YAML is the design baseline: every task is a check, every item
row is an item with a copy count. This turns it into plain tables the APWorld
builds from, so the APWorld never parses YAML at generation time.

TASKIPELAGO SEMANTICS (from its options.py / prereq_parser.py)
  * task_prereqs / item_prereqs are expressions over 1-based task / item
    indices. ',' is AND, same as '&&'.
  * '8, 8, 8' is therefore "item 8" three times = ONE copy. The design intent
    for class levels is N copies for level N (Taskipelago spells that '8*N').
    We implement the intent: an item repeated k times in an AND list means k
    copies.
  * Only AND lists appear in this design, so no OR handling is needed. The
    generator refuses '||' and '(' rather than silently misreading them.

Requirements are FLATTENED: a check's item rule is its own item needs merged
(max count per item) with those of every check up its prereq chain. Chains
are all within one progression track, so after flattening every check's
access is a pure item rule -- no location-reachability rules at generation.

IDs: checks and items that existed in the pre-baseline APWorld keep their old
numeric IDs (the client and the UE4SS mods refer to them). New entries get
IDs from NEW_LOC_START / NEW_ITEM_START upward, in YAML order.
"""
import re
import sys
import yaml

LOCATION_BASE_ID = 8410000
ITEM_BASE_ID = 8400000
NEW_LOC_START = 600
NEW_ITEM_START = 100

# Design typos fixed on import. Each is reported when applied.
TASK_RENAMES = {
    "Complete Act 4, Mission 7": "Complete Act 3, Mission 7",   # Act 3 has Mission 7; there is no Act 4
}

# ---------------------------------------------------------------- categories
def task_category(name):
    rules = [
        (r"^Start The Game$", "Start"),
        (r"^Complete Act \d, Mission \d+$", "Story Mission"),
        (r"^Complete Act \d, Side Mission \d+$", "Side Mission"),
        (r"^Complete Act \d$", "Act Clear"),
        (r"^Kill The (Brumak|Corpser|Hydra)$", "Boss"),
        (r"Has Joined The Convoy$", "Hero"),
        (r"^Convoy Size: \d+$", "Convoy Capacity"),
        (r"^Enemy Encounter: ", "Encounter"),
        (r"^Complete Optional Objective \d+$", "Optional Objective"),
        (r"^(Support|Sniper|Heavy|Scout|Vanguard) Class Level \d+$", "Class Level"),
        (r"^Jack Level Up \d+$", "Jack Level"),
        (r"^(Support|Sniper|Heavy|Scout|Vanguard|Jackbot) Class Joined$", "Class Joined"),
        (r"^Total Enemies Killed: \d+$", None),          # split below
        (r"^Bayonet Charge Kill \d+$", "Special Kill"),
        (r"^Lancer Chainsaw Kill \d+$", "Special Kill"),
        (r"^Execute An Enemy \d+$", "Special Kill"),
        (r"^Close E-Hole \d+$", "E-Holes"),
        (r"^Revive Any Gear \d+$", "Revives"),
        (r"^Collect Loot Crate \d+$", "Loot Case"),
        (r"^Collect Supreme Loot \d+$", "Supreme Equipment"),
        (r"^Complete Veteran Mission \d+$", "Veteran Mission"),
        (r"^Acquire Legendary .+ \d$", "Legendary Gear"),
        (r"^Reset Token \d+$", "Reset Token"),
        (r"^Rescue Pod \d+$", "Rescue Pod"),   # 2026-10-01: torture pods opened (APRoster); 8 in the main missions
        (r"^(Support|Sniper|Heavy|Scout|Vanguard|Jackbot) \S+$", "Skill Tree Purchase"),
    ]
    for pat, cat in rules:
        if re.search(pat, name):
            if cat is None:
                k = int(name.rsplit(" ", 1)[1])
                return "Kills" if k <= 500 else "High Kills"
            return cat
    raise SystemExit(f"no category for task {name!r}")

# ------------------------------------------------ legacy location id offsets
def legacy_loc_offset(name):
    m = re.match(r"^Complete Act (\d), Mission (\d+)$", name)
    if m:
        a, n = int(m[1]), int(m[2])
        return {1: 0, 2: 8, 3: 21}[a] + n
    m = re.match(r"^Complete Act (\d), Side Mission (\d+)$", name)
    if m:
        a, n = int(m[1]), int(m[2])
        if a == 1: return {1: 7, 2: 401}.get(n)
        if a == 2 and n <= 4: return 16 + n
        if a == 3 and n <= 9: return 29 + n
        return None
    fixed = {"Complete Act 1": 8, "Complete Act 2": 21, "Kill The Brumak": 39,
             "Kill The Corpser": 40, "Kill The Hydra": 41,
             "Gabe Has Joined The Convoy": 44, "Sid Has Joined The Convoy": 45,
             "Mikayla Has Joined The Convoy": 46, "Reina Has Joined The Convoy": 47,
             "Jack Has Joined The Convoy": 406,
             # encounters
             "Enemy Encounter: Drone": 311, "Enemy Encounter: Wretch": 312,
             "Enemy Encounter: Grenadier": 313, "Enemy Encounter: Sniper": 314,
             "Enemy Encounter: Boomer": 315, "Enemy Encounter: Kantus": 316,
             "Enemy Encounter: Ticker": 317, "Enemy Encounter: Disciple": 318,
             "Enemy Encounter: Zealot": 319, "Enemy Encounter: Theron Guard": 320,
             "Enemy Encounter: Emergence Hole": 402, "Enemy Encounter: Brumak": 403,
             "Enemy Encounter: Corpser": 404, "Enemy Encounter: Hydra": 405,
             "Enemy Encounter: Deviant Wretch": 407, "Enemy Encounter: Deviant Drone": 408,
             "Enemy Encounter: Deviant Sniper": 409, "Enemy Encounter: Deviant Disciple": 410,
             "Enemy Encounter: Deviant Kantus": 411}
    if name in fixed: return fixed[name]
    m = re.match(r"^Convoy Size: (\d+)$", name)
    if m: return 47 + int(m[1]) if int(m[1]) <= 26 else None
    m = re.match(r"^Collect Loot Crate (\d+)$", name)
    if m: return 73 + int(m[1])
    m = re.match(r"^Collect Supreme Loot (\d+)$", name)
    if m: return 411 + int(m[1])
    m = re.match(r"^(Support|Vanguard|Heavy|Sniper|Scout) Class Level (\d+)$", name)
    if m: return {"Support": 193, "Vanguard": 203, "Heavy": 213, "Sniper": 223, "Scout": 233}[m[1]] + int(m[2])
    m = re.match(r"^Total Enemies Killed: (\d+)$", name)
    if m:
        k = int(m[1])
        return 243 + k // 25 if k <= 500 else 320 + (k - 500) // 25
    m = re.match(r"^(Bayonet Charge Kill|Lancer Chainsaw Kill|Execute An Enemy) (\d+)$", name)
    if m and int(m[2]) <= 20:
        return {"Bayonet Charge Kill": 431, "Lancer Chainsaw Kill": 451, "Execute An Enemy": 471}[m[1]] + int(m[2])
    m = re.match(r"^Acquire Legendary (.+) (\d)$", name)
    if m:
        base = {"Boots": 263, "Armour": 266, "Helmet": 269, "Retro Lancer Mod": 272,
                "Mulcher Mod": 275, "Gnasher Mod": 278, "Lancer Mod": 281,
                "Longshot Mod": 284, "Grenade": 287}.get(m[1])
        return base + int(m[2]) if base else None
    m = re.match(r"^Complete Veteran Mission (\d+)$", name)
    if m: return 290 + int(m[1])
    m = re.match(r"^Close E-Hole (\d+)$", name)
    if m and int(m[1]) <= 10: return 340 + int(m[1])
    m = re.match(r"^Revive Any Gear (\d+)$", name)
    if m: return 350 + int(m[1])
    m = re.match(r"^Complete Optional Objective (\d+)$", name)
    if m: return 360 + int(m[1])
    if name == "Complete Act 3": return 43
    return None

# ------------------------------------------------------ legacy item offsets
LEGACY_ITEMS = {
    "Support Class Level Up Unlock": 1, "Vanguard Class Level Up Unlock": 2,
    "Sniper Class Level Up Unlock": 3, "Heavy Class Level Up Unlock": 4,
    "Scout Class Level Up Unlock": 5,
    "Random Epic Lancer Mod": 10, "Random Epic Mulcher Mod": 11,
    "Random Epic Longshot Mod": 12, "Random Epic Retro Lancer Mod": 13,
    "Random Epic Gnasher Mod": 14, "Random Epic Random Armour Mod": 15,
    "Random Epic Random Helmet Mod": 16, "Random Epic Random Boots Mod": 17,
    "Random Epic Frag Grenade Mod": 18, "Random Epic Stim Grenade Mod": 19,
    "Random Epic Snub Pistol Mod": 20,
    "Critical Hit Chance +5% For Current Mission": 25,
    "Evasion +20% For Current Mission": 26, "Accuracy +5% For Current Mission": 27,
    "Ammo Clip Size +1 For Current Mission": 28, "Stim Random Gear In Squad": 29,
    "Auto Revive A Downed Gear": 30, "Fully Reload All Weapons": 35,
    "Random Skill Cooldown": 36, "Gain Bonus Supplies For The Convoy": 37,
    "Gears Request Reinforcements over TAC/COM": 38,
    "Decrease All Skill Cooldowns For Current Mission": 39,
    "Reveal Fog Of War For 30 Seconds": 40, "Location Of An Empty Torture Pod": 41,
    "An Empty Loot Crate": 42, "Chance To Hit Increase For Current Mission": 43,
    "Entire Squad Falls Into An Emergence Hole!": 50,
    "Enemy Reinforcements Inbound!": 51, "Enemy Destroys Supplies!": 52,
    "Random Gear In Squad Gets Downed": 53,
    "Increase All Skill Cooldowns For Current Mission": 54,
    "Nemacyst Bombardment Incoming!": 55, "Chance To Hit Decrease For Current Mission": 56,
}

CLASSIFICATION = {"progression": "progression", "useful": "useful",
                  "trap": "trap", "junk": "filler", "filler": "filler"}

# --------------------------------------------------------------- expressions
def parse_and_list(expr, where):
    expr = str(expr or "").strip()
    if not expr:
        return []
    if "||" in expr or "(" in expr:
        raise SystemExit(f"{where}: OR / grouping not supported by this generator: {expr!r}")
    out = []
    for tok in re.split(r"\s*(?:,|&&)\s*", expr):
        if not tok:
            continue
        m = re.fullmatch(r"(\d+)(?:\*(\d+))?", tok)
        if not m:
            raise SystemExit(f"{where}: unsupported token {tok!r} in {expr!r}")
        out.append((int(m[1]), int(m[2] or 1)))
    return out

def main(src, dst):
    d = yaml.safe_load(open(src, encoding="utf-8"))["Taskipelago"]
    g = lambda key, i: (d.get(key) or [])[i] if i < len(d.get(key) or []) else ""
    tasks_raw, items_raw = d["tasks"], d["items"]
    notes = []

    # ---- items
    items = []
    used_ids = set()
    for i, name in enumerate(items_raw):
        count = int(str(g("item_count", i) or 1))
        cls = CLASSIFICATION.get(str(g("item_types", i)).lower(), "filler")
        items.append({"name": name, "count": count, "cls": cls})
    next_item = NEW_ITEM_START
    for it in items:
        off = LEGACY_ITEMS.get(it["name"])
        if off is None:
            off = next_item
            next_item += 1
        assert off not in used_ids, it
        used_ids.add(off)
        it["id"] = ITEM_BASE_ID + off
        it["legacy"] = it["name"] in LEGACY_ITEMS

    # ---- tasks (expanded by task_count; this design has none > 1)
    tasks = []
    for i, raw in enumerate(tasks_raw):
        name = TASK_RENAMES.get(raw, raw)
        if name != raw:
            notes.append(f"renamed design typo: {raw!r} -> {name!r}")
        if int(str(g("task_count", i) or 1)) != 1:
            raise SystemExit(f"task_count > 1 not supported: {raw}")
        tasks.append({
            "name": name,
            "category": task_category(name),
            "priority": str(g("task_priority", i)).lower() == "true",
            "task_pre": [t for t, _ in parse_and_list(g("task_prereqs", i), f"task {i+1} prereqs")],
            "item_pre": parse_and_list(g("item_prereqs", i), f"task {i+1} item prereqs"),
        })

    # own item needs: repeated index = copies (design intent); explicit *N honoured
    for t in tasks:
        need = {}
        for idx, copies in t["item_pre"]:
            nm = items[idx - 1]["name"]
            need[nm] = need.get(nm, 0) + copies
        t["own_items"] = need

    # flatten along the prereq chain (memoised DFS; cycles are an error)
    state = {}
    def flat(i):
        if state.get(i) == "busy":
            raise SystemExit(f"prereq cycle at task {i+1}")
        if i in state:
            return state[i]
        state[i] = "busy"
        need = dict(tasks[i]["own_items"])
        for p in tasks[i]["task_pre"]:
            for nm, c in flat(p - 1).items():
                need[nm] = max(need.get(nm, 0), c)
        state[i] = need
        return need
    for i, t in enumerate(tasks):
        t["requires"] = flat(i)
        t["after"] = [tasks[p - 1]["name"] for p in t["task_pre"]]

    # supply check: every requirement must be satisfiable by the pool
    supply = {it["name"]: it["count"] for it in items}
    for t in tasks:
        for nm, c in t["requires"].items():
            if c > supply.get(nm, 0):
                raise SystemExit(f"{t['name']} needs {c}x {nm}, pool has {supply.get(nm, 0)}")

    # ids
    used = set()
    next_loc = NEW_LOC_START
    for t in tasks:
        off = legacy_loc_offset(t["name"])
        t["legacy"] = off is not None
        if off is None:
            off = next_loc
            next_loc += 1
        assert off not in used, (t["name"], off)
        used.add(off)
        t["id"] = LOCATION_BASE_ID + off

    goal = [tasks[p - 1]["name"] for p, _ in parse_and_list(" && ".join(d.get("goal_tasks") or []), "goal")]

    # ---- write
    L = ['"""',
         "GENERATED by tools/gen_apworld_data.py from " + src.replace("\\", "/").split("/")[-1] + ". Do not edit by hand:",
         "change the design YAML and regenerate.",
         "",
         "TASKS: one per check. 'requires' is the FLATTENED item rule (own needs",
         "merged with every check up the prereq chain), item name -> copies.",
         "'after' is the design's direct task prereq, kept for the client/tracker.",
         '"""',
         "",
         f"LOCATION_BASE_ID = {LOCATION_BASE_ID}",
         f"ITEM_BASE_ID = {ITEM_BASE_ID}",
         f"GOAL_TASKS = {goal!r}",
         "",
         "ITEMS = ["]
    for it in items:
        L.append(f"    ({it['name']!r}, {it['id']}, {it['cls']!r}, {it['count']}),")
    L += ["]", "", "TASKS = ["]
    for t in tasks:
        L.append(f"    ({t['name']!r}, {t['id']}, {t['category']!r}, {t['priority']!r}, "
                 f"{dict(sorted(t['requires'].items()))!r}, {t['after']!r}),")
    L += ["]", ""]
    open(dst, "w", encoding="utf-8", newline="\n").write("\n".join(L))

    n_items = sum(it["count"] for it in items)
    print(f"{len(tasks)} checks ({sum(t['legacy'] for t in tasks)} kept legacy ids, "
          f"{sum(not t['legacy'] for t in tasks)} new), {len(items)} item types, {n_items} item copies")
    print(f"goal: {goal}")
    for n in notes:
        print("NOTE:", n)

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
