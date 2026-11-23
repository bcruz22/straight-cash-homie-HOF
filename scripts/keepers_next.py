# Keeper options for next season's draft, from current Sleeper rosters and league keeper rules:
# - max 2 straight seasons as a keeper (any roster); cost = round the player went in this season's draft
#   (drafted or kept), else round 12 for a free agent / waiver pickup.
import json, glob, os, sys, datetime
RAW, OUT, SCRIPTS = sys.argv[1], sys.argv[2], sys.argv[3]
ST = json.load(open(f"{RAW}/state.json"))   # written by pull.py
CUR = int(ST["season"]); NEXT = CUR + 1
LAST_WEEK = 99 if ST["complete"] else ST["last_completed_week"]
P = json.load(open(f"{RAW}/players.json"))
S = {int(json.load(open(f))["league"]["season"]): json.load(open(f)) for f in sorted(glob.glob(f"{RAW}/20*.json"))}
def name(pid):
    p = P.get(pid) or {}
    return f"{pid} D/ST" if p.get("position") == "DEF" else f"{p.get('first_name','')} {p.get('last_name','')}".strip() or pid
TRACKER = json.load(open(f"{RAW}/tracker.json"))  # commissioner corrections to Sleeper keeper flags
kept_years = {}  # Sleeper keeper flags (2021 on); only the last two seasons matter for eligibility
for y, s in S.items():
    for d in s["drafts"]:
        for p in d["picks"]:
            nm = name(p["player_id"]).lower()
            if p.get("is_keeper") and not any(x["season"] == str(y) and nm.endswith(x["last"].lower()) for x in TRACKER["not_keepers"]):
                kept_years.setdefault(p["player_id"], set()).add(y)
cur = S[CUR]
draft_round, draft_kept = {}, {}
for d in cur["drafts"]:
    for p in d["picks"]:
        draft_round[p["player_id"]] = p["round"]; draft_kept[p["player_id"]] = bool(p.get("is_keeper"))
pts = {}
for w, wk in cur["matchups"].items():
    if int(w) > LAST_WEEK: continue
    for m in wk:
        for pid, v in (m.get("players_points") or {}).items(): pts[pid] = pts.get(pid, 0) + (v or 0)
DISPLAY = json.load(open(f"{RAW}/tracker.json"))["display"]  # real names from the commissioner's tracker
users = {u["user_id"]: DISPLAY.get(u["user_id"], u["display_name"]) for u in cur["users"]}
rows = []
for r in cur["rosters"]:
    mgr = users.get(r["owner_id"], f"Team {r['roster_id']}")
    for pid in r.get("players") or []:
        streak, y = 0, CUR
        while y in kept_years.get(pid, set()): streak += 1; y -= 1
        eligible = streak < 2
        if pid in draft_round:
            rd = draft_round[pid]
            basis = f"Kept at round {rd} in {CUR}" if draft_kept[pid] else f"Drafted in round {rd} in {CUR}"
        else:
            rd, basis = 12, "Free agent or waiver pickup"
        status = ("Not eligible: kept in " + " and ".join(str(CUR - i) for i in range(streak - 1, -1, -1))) if not eligible else \
                 ("Eligible: would be 2nd straight year kept" if streak == 1 else "Eligible")
        pos = (P.get(pid) or {}).get("position") or ""
        rows.append({"key": f"{mgr}|{pid}", "manager": mgr, "player": name(pid), "pos": pos, "nfl_team": (P.get(pid) or {}).get("team") or "",
                     "eligible": eligible, "years_kept_in_a_row": streak, "status": status, "cost_round": rd, "cost_basis": basis,
                     "pts": round(pts.get(pid, 0), 2)})
rows.sort(key=lambda r: (r["manager"].lower(), not r["eligible"], -r["pts"]))
code = [{"label": "keepers_next.py", "value": open(os.path.join(SCRIPTS, "keepers_next.py")).read(), "type": "code", "lang": "python"},
        {"label": "pull.py", "value": open(os.path.join(SCRIPTS, "pull.py")).read(), "type": "code", "lang": "python"}]
meta = code + [{"label": "Input", "value": "Sleeper API (api.sleeper.app), league 1389303477989048320: current rosters, every season's draft keeper flags, 2026 weekly player points"},
               {"label": "Pulled", "value": f"{datetime.date.today().isoformat()}, rosters as of that day" + (f", points through week {LAST_WEEK}" if LAST_WEEK < 99 else "")}]
json.dump({"rows": rows, "meta": meta}, open(f"{OUT}/keeper_options.json", "w"), ensure_ascii=False, separators=(",", ":"))
print(len(rows), sum(r["eligible"] for r in rows), "eligible")
for r in rows:
    if not r["eligible"] or r["years_kept_in_a_row"]: print(r["manager"], r["player"], r["status"], r["cost_round"])
