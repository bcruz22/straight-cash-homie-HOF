# Turns league_history.json (from build.py) into the row files the dashboard reads.
import json, sys, os, datetime
SRC, OUT, SCRIPTS = sys.argv[1], sys.argv[2], sys.argv[3]
d = json.load(open(SRC)); os.makedirs(OUT, exist_ok=True)
DISPLAY = json.load(open(os.path.join(os.path.dirname(SRC), "raw", "tracker.json")))["display"]  # real names from the commissioner's tracker
N = {k: DISPLAY.get(k, v["name"]) for k, v in d["owners"].items()}
code = [{"label": f, "value": open(os.path.join(SCRIPTS, f)).read(), "type": "code", "lang": "python"} for f in ("pull.py", "build.py", "export.py")]
meta = code + [{"label": "Input", "value": "Sleeper API (api.sleeper.app), league 1389303477989048320 and its previous seasons"},
               {"label": "Pulled", "value": datetime.date.today().isoformat() + (f", {d['current_season']} through week {d['current_week']}" if d['current_week'] < 99 else f", {d['current_season']} complete")}]
def write(name, rows):
    json.dump({"rows": rows, "meta": meta}, open(f"{OUT}/{name}.json", "w"), ensure_ascii=False, separators=(",", ":"))
    print(name, len(rows), os.path.getsize(f"{OUT}/{name}.json"))
assumed = {(a["season"], a["owner"]) for a in d["assumed"]}
ts = []
for s in d["seasons"]:
    for t in s["teams"]:
        ts.append({"key": f"{s['season']}-{N[t['owner']]}", "season": int(s["season"]), "manager": N[t["owner"]],
            "team": t["team"] or "", "w": t["w"], "l": t["l"], "t": t["t"], "pf": t["pf"], "pa": t["pa"], "max_pf": t["maxpf"],
            "rank": t["rank"], "playoffs": t["playoffs"], "finish": t["finish"], "complete": s["complete"],
            "assumed_owner": (s["season"], t["owner"]) in assumed})
write("team_seasons", ts)
write("games", [{"key": f"{g['season']}-{g['week']}-{i}", "season": int(g["season"]), "week": g["week"], "kind": g["kind"],
    "home": N[g["a"]], "away": N[g["b"]], "home_pts": g["pa"], "away_pts": g["pb"]} for i, g in enumerate(d["games"])])
write("team_weeks", [{"key": f"{r['season']}-{r['week']}-{N[r['owner']]}", "season": int(r["season"]), "week": r["week"], "manager": N[r["owner"]],
    "pts": r["pts"], "allplay_w": r["ap_w"], "allplay_l": r["ap_l"], "allplay_t": r["ap_t"]} for r in d["team_weeks"]])
write("picks", [{"key": f"{p['season']}-{p['pick']}", "season": int(p["season"]), "round": p["round"], "pick": p["pick"], "manager": N[p["owner"]],
    "player": p["player"], "pos": p["pos"], "keeper": p["keeper"], "pts": p["pts"], "games_started": p["gp"]} for p in d["picks"]])
kp = []
for k in d["keepers"]:
    kp.append({"key": f"{N[k['owner']]}-{k['player']}", "manager": N[k["owner"]], "player": k["player"], "pos": k["pos"],
        "times_kept": len(k["seasons"]), "seasons": ", ".join(k["seasons"]), "rounds": ", ".join(map(str, k["rounds"])),
        "pts": round(sum(k["pts"]), 2)})
write("keepers", sorted(kp, key=lambda r: (-r["times_kept"], -r["pts"])))
tr = []
for i, t in enumerate(d["trades"]):
    (a, sa), (b, sb) = list(t["sides"].items())[:2]
    tr.append({"key": f"T{i+1}", "season": int(t["season"]), "week": t["week"],
        "side_a": N.get(a, "?"), "a_got": ", ".join(sa["players"] + sa["picks"]) or "nothing", "a_pts": sa["pts"],
        "side_b": N.get(b, "?"), "b_got": ", ".join(sb["players"] + sb["picks"]) or "nothing", "b_pts": sb["pts"]})
write("trades", tr)
write("pickups", [{"key": f"A{i+1}", "season": int(r["season"]), "week": r["week"], "manager": N[r["owner"]], "player": r["player"], "pos": r["pos"],
    "pts": r["pts"], "games_started": r["gp"], "how": "Waiver" if r["type"] == "waiver" else "Free agent"} for i, r in enumerate(d["top_adds"])])
write("drop_regret", [{"key": f"D{i+1}", "season": int(r["season"]), "week": r["week"], "dropped_by": N[r["owner"]], "player": r["player"], "pos": r["pos"],
    "pts_for_others": r["pts"], "mostly_for": N[r["to"]]} for i, r in enumerate(d["drop_regret"])])
write("player_games", [{"key": f"P{i+1}", "season": int(r["season"]), "week": r["week"], "manager": N[r["owner"]], "player": r["player"], "pos": r["pos"],
    "pts": r["pts"]} for i, r in enumerate(d["top_players"])])
