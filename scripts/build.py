import json, glob, sys, collections, os, re
D = sys.argv[1]; OUT = sys.argv[2]
ST = json.load(open(f"{D}/state.json"))   # written by pull.py
CUR_SEASON = ST["season"]
CUR_LAST_WEEK = 99 if ST["complete"] else ST["last_completed_week"]   # in progress: only completed weeks
P = json.load(open(f"{D}/players.json"))
def pname(pid):
    p = P.get(pid)
    if not p: return pid
    if p.get("position") == "DEF": return f"{pid} D/ST"
    return f"{p.get('first_name','')} {p.get('last_name','')}".strip()
def ppos(pid):
    p = P.get(pid); return (p or {}).get("position") or ("DEF" if pid.isalpha() else "")

# 2021 rosters 5 and 9 have no owner recorded by Sleeper. Assumed to be the 2020 managers of those slots.
ASSUMED = {("2021", 5): "608391943596093440", ("2021", 9): "608460692193898496"}

# Commissioner's keeper tracker: 2020 keepers (Sleeper didn't flag them) and real first names
TRACKER = json.load(open(f"{D}/tracker.json"))
seasons = {}
for f in sorted(glob.glob(f"{D}/20*.json")):
    s = json.load(open(f)); seasons[s["league"]["season"]] = s

# owners: latest display name per user id
owners = {}
for y, s in sorted(seasons.items()):
    for u in s["users"]:
        owners.setdefault(u["user_id"], {"id": u["user_id"]})
        owners[u["user_id"]]["name"] = u["display_name"]
        owners[u["user_id"]]["avatar"] = u.get("avatar")

def owner_of(y, rid):
    r = next(r for r in seasons[y]["rosters"] if r["roster_id"] == rid)
    return r["owner_id"] or ASSUMED.get((y, rid))

def team_name(y, oid):
    for u in seasons[y]["users"]:
        if u["user_id"] == oid:
            return ((u.get("metadata") or {}).get("team_name") or "").strip() or None
    return None

games = []          # one row per game
team_weeks = []     # one row per team-week
seasons_out = []
player_games = []   # top starter performances
for y, s in sorted(seasons.items()):
    L = s["league"]; st = L["settings"]; pws = st["playoff_week_start"]
    complete = L["status"] == "complete"
    last_week = CUR_LAST_WEEK if y == CUR_SEASON else max(int(w) for w in s["matchups"])
    own = {r["roster_id"]: owner_of(y, r["roster_id"]) for r in s["rosters"]}
    # bracket games -> (week, frozenset) : (kind, placement)
    bracket = {}
    for m in s["winners"]:
        if m.get("t1") and m.get("t2"):
            kind = "final" if m.get("p") == 1 else ("playoff" if not m.get("p") else "placement")
            bracket[(pws + m["r"] - 1, frozenset((m["t1"], m["t2"])))] = kind
    for m in s["losers"]:
        if m.get("t1") and m.get("t2"):
            bracket[(pws + m["r"] - 1, frozenset((m["t1"], m["t2"])))] = "consolation"
    for w in range(1, last_week + 1):
        wk = s["matchups"].get(str(w)) or []
        if not wk: continue
        pts = {m["roster_id"]: round(m["points"] or 0, 2) for m in wk}
        reg = w < pws
        if reg:  # all-play
            for m in wk:
                p = pts[m["roster_id"]]
                beat = sum(1 for r, q in pts.items() if r != m["roster_id"] and q < p)
                tie = sum(1 for r, q in pts.items() if r != m["roster_id"] and q == p)
                pp = round(sum(m.get("players_points", {}).get(x, 0) for x in m["players"]), 2) if m.get("players") else None
                team_weeks.append({"season": y, "week": w, "owner": own[m["roster_id"]], "pts": p,
                    "ap_w": beat, "ap_l": len(pts) - 1 - beat - tie, "ap_t": tie})
        for m in wk:
            for pid, sp in zip(m.get("starters") or [], m.get("starters_points") or []):
                if pid and pid != "0" and sp:
                    player_games.append((sp, y, w, own[m["roster_id"]], pid))
        by = collections.defaultdict(list)
        for m in wk:
            if m.get("matchup_id") is not None: by[m["matchup_id"]].append(m["roster_id"])
        for mid, rs in by.items():
            if len(rs) != 2: continue
            a, b = rs
            kind = "regular" if reg else bracket.get((w, frozenset(rs)))
            if kind is None: continue   # unofficial matchups after elimination
            games.append({"season": y, "week": w, "kind": kind,
                          "a": own[a], "b": own[b], "pa": pts[a], "pb": pts[b]})
    # regular-season standings from games
    rec = {o: {"w": 0, "l": 0, "t": 0, "pf": 0.0, "pa": 0.0} for o in own.values()}
    for g in games:
        if g["season"] != y or g["kind"] != "regular": continue
        for me, op, pm, po in ((g["a"], g["b"], g["pa"], g["pb"]), (g["b"], g["a"], g["pb"], g["pa"])):
            r = rec[me]; r["pf"] += pm; r["pa"] += po
            r["w" if pm > po else "l" if pm < po else "t"] += 1
    maxpf = {own[r["roster_id"]]: r["settings"].get("ppts", 0) + r["settings"].get("ppts_decimal", 0) / 100 for r in s["rosters"]}
    order = sorted(rec, key=lambda o: (-(rec[o]["w"] + rec[o]["t"] / 2), -rec[o]["pf"]))
    finish = {}
    if complete:
        for m in s["winners"]:
            p = m.get("p")
            if p in (1, 3, 5) and m.get("w"):
                finish[own[m["w"]]] = p; finish[own[m["l"]]] = p + 1
        rest = [o for o in order if o not in finish]
        for i, o in enumerate(rest): finish[o] = len(finish) + 1
    # playoff seeds: winners bracket round-1 teams + byes = top 6 by Sleeper's seeding
    po_teams = set()
    for m in s["winners"]:
        for t in (m.get("t1"), m.get("t2")):
            if isinstance(t, int): po_teams.add(own[t])
    teams = []
    for i, o in enumerate(order):
        r = rec[o]
        teams.append({"owner": o, "team": team_name(y, o), "w": r["w"], "l": r["l"], "t": r["t"],
            "pf": round(r["pf"], 2), "pa": round(r["pa"], 2), "maxpf": round(maxpf.get(o, 0), 2),
            "rank": i + 1, "playoffs": o in po_teams, "finish": finish.get(o)})
    champ = next((o for o, f in finish.items() if f == 1), None)
    seasons_out.append({"season": y, "name": L["name"], "complete": complete, "weeks_played": last_week,
        "playoff_week_start": pws, "teams": teams, "champion": champ,
        "runner_up": next((o for o, f in finish.items() if f == 2), None),
        "third": next((o for o, f in finish.items() if f == 3), None),
        "last": order[-1] if complete else None})

# ---- drafts, keepers ----
def starter_points(y, oid, pid, from_week=1, to_week=99):
    s = seasons[y]; tot = 0.0; gp = 0
    last = CUR_LAST_WEEK if y == CUR_SEASON else 99
    for w, wk in s["matchups"].items():
        w = int(w)
        if w < from_week or w > to_week or w > last: continue
        for m in wk:
            if owner_of(y, m["roster_id"]) != oid: continue
            for pid2, sp in zip(m.get("starters") or [], m.get("starters_points") or []):
                if pid2 == pid: tot += sp or 0; gp += 1
    return round(tot, 2), gp
picks = []
for y, s in sorted(seasons.items()):
    for d in s["drafts"]:
        for p in d["picks"]:
            # Unowned 2021 slots: Sleeper's pick roster_id is unreliable there, so use the week-1 roster that held the player
            w1 = {pid: m["roster_id"] for m in s["matchups"].get("1", []) for pid in (m.get("players") or [])}
            oid = p.get("picked_by") or owner_of(y, w1.get(p["player_id"], p["roster_id"]))
            pts, gp = starter_points(y, oid, p["player_id"])
            nm = pname(p["player_id"]).lower(); rd = p["round"]
            is_k = bool(p.get("is_keeper"))
            if y == "2020":  # tracker lists 2020 keepers and the round each cost (it wins over Sleeper's draft slot)
                base = re.sub(r"\s+(jr|sr|ii|iii|iv)\.?$", "", nm)
                same = [k for k in TRACKER["keepers_2020"] if k["owner"] == oid and base.endswith(" " + k["last"].lower())]
                k20 = same[0] if same else None
                if k20:  # same last name on this team's 2020 picks: the tracker's first initial (or the round) decides
                    rivals = [q for q in d["picks"] if (q.get("picked_by") or owner_of(y, q["roster_id"])) == oid and q is not p
                              and re.sub(r"\s+(jr|sr|ii|iii|iv)\.?$", "", pname(q["player_id"]).lower()).endswith(" " + k20["last"].lower())]
                    if rivals and not (base.startswith(k20["first"].lower()) or p["round"] == k20["round"]): k20 = None
                if k20: is_k, rd = True, k20["round"]
            if any(x["season"] == y and x["owner"] == oid and nm.endswith(x["last"].lower()) for x in TRACKER["not_keepers"]):
                is_k = False  # commissioner corrections: drafted, not kept
            picks.append({"season": y, "round": rd, "pick": p["pick_no"], "owner": oid,
                "player": pname(p["player_id"]), "pid": p["player_id"], "pos": p["metadata"].get("position") or ppos(p["player_id"]),
                "keeper": is_k, "pts": pts, "gp": gp})
# keeper chains: (owner, player) consecutive keeper seasons
kchains = collections.defaultdict(list)
for p in picks:
    if p["keeper"]: kchains[(p["owner"], p["pid"])].append(p)

# ---- transactions ----
trades, adds, drops = [], [], []
for y, s in sorted(seasons.items()):
    if True:
        for w, txs in s["tx"].items():
            w = int(w)
            for t in txs:
                if t["status"] != "complete": continue
                if t["type"] == "trade":
                    sides = {}
                    for rid in t["roster_ids"]:
                        oid = owner_of(y, rid)
                        got = [pid for pid, r in (t.get("adds") or {}).items() if r == rid]
                        pk = [f"{dp['season']} R{dp['round']}" for dp in t.get("draft_picks") or [] if dp["owner_id"] == rid]
                        val = sum(starter_points(y, oid, pid, w + (0 if w == 0 else 1) if False else w)[0] for pid in got)
                        sides[oid] = {"players": [pname(x) + f" ({ppos(x)})" for x in got], "picks": pk, "pts": round(val, 2)}
                    trades.append({"season": y, "week": w, "sides": sides})
                else:
                    for pid, rid in (t.get("adds") or {}).items():
                        oid = owner_of(y, rid); v, gp = starter_points(y, oid, pid, w)
                        adds.append({"season": y, "week": w, "owner": oid, "player": pname(pid), "pos": ppos(pid), "pts": v, "gp": gp, "type": t["type"]})
                    for pid, rid in (t.get("drops") or {}).items():
                        drops.append((y, w, owner_of(y, rid), pid))
# drop regret: points started for OTHER teams after the drop, same season
regret = []
for y, w, oid, pid in drops:
    if not oid: continue
    tot = 0.0; who = collections.Counter()
    for o in set(owner_of(y, r["roster_id"]) for r in seasons[y]["rosters"]):
        if o and o != oid:
            v, _ = starter_points(y, o, pid, w + 1)
            if v: tot += v; who[o] += v
    if tot > 0:
        regret.append({"season": y, "week": w, "owner": oid, "player": pname(pid), "pos": ppos(pid),
                       "pts": round(tot, 2), "to": who.most_common(1)[0][0]})
# keep only the largest regret per (owner, player, season)
best = {}
for r in regret:
    k = (r["season"], r["owner"], r["player"])
    if k not in best or r["pts"] > best[k]["pts"]: best[k] = r
regret = sorted(best.values(), key=lambda r: -r["pts"])[:25]
adds = sorted(adds, key=lambda r: -r["pts"])[:25]

player_games.sort(reverse=True)
top_players = [{"pts": round(p, 2), "season": y, "week": w, "owner": o, "player": pname(pid), "pos": ppos(pid)} for p, y, w, o, pid in player_games[:15]]

used = set()
for g in games: used.update([g["a"], g["b"]])
data = {"league": seasons[CUR_SEASON]["league"]["name"], "current_season": CUR_SEASON, "current_week": CUR_LAST_WEEK,
    "owners": {k: v for k, v in owners.items() if k in used},
    "assumed": [{"season": y, "slot": r, "owner": o} for (y, r), o in ASSUMED.items()],
    "seasons": seasons_out, "games": games, "team_weeks": team_weeks, "picks": picks,
    "keepers": [{"owner": o, "player": ps[0]["player"], "pos": ps[0]["pos"], "seasons": [p["season"] for p in ps], "rounds": [p["round"] for p in ps], "pts": [p["pts"] for p in ps]} for (o, _), ps in kchains.items()],
    "trades": trades, "top_adds": adds, "drop_regret": regret, "top_players": top_players}
json.dump(data, open(OUT, "w"), separators=(",", ":"))
print("games", len(games), "picks", len(picks), "trades", len(trades), "size", os.path.getsize(OUT))
for s in seasons_out:
    print(s["season"], "champ", owners.get(s["champion"], {}).get("name"), "2nd", owners.get(s["runner_up"], {}).get("name"), "last", owners.get(s["last"], {}).get("name"),
          [(owners[t["owner"]]["name"], f'{t["w"]}-{t["l"]}', t["finish"]) for t in s["teams"]][:3])
