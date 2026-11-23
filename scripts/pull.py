import json, sys, os, urllib.request, time
B="https://api.sleeper.app/v1"
out=sys.argv[2]
def get(p):
    for i in range(4):
        try:
            with urllib.request.urlopen(B+p, timeout=30) as r: return json.load(r)
        except Exception as e:
            time.sleep(2**i); err=e
    raise err
lid=sys.argv[1]; seasons=[]
USER = sys.argv[3] if len(sys.argv) > 3 else None   # commissioner's Sleeper user id, to find next season's league
state = get("/state/nfl")
if USER:  # a new season's league points back to the one we know; follow the chain forward
    for yr in (int(state["league_season"]), int(state["league_season"]) + 1):
        for lg in get(f"/user/{USER}/leagues/nfl/{yr}") or []:
            chain, cur = set(), lg["league_id"]
            for _ in range(15):
                if not cur or cur == "0" or cur in chain: break
                chain.add(cur)
                if cur == lid: break
                cur = (get(f"/league/{cur}") or {}).get("previous_league_id")
            if lid in chain: lid = lg["league_id"]
newest = None
while lid and lid!="0":
    L=get(f"/league/{lid}"); s={"league":L}
    s["users"]=get(f"/league/{lid}/users"); s["rosters"]=get(f"/league/{lid}/rosters")
    s["winners"]=get(f"/league/{lid}/winners_bracket"); s["losers"]=get(f"/league/{lid}/losers_bracket")
    last=(L["settings"].get("playoff_week_start") or 15)+3
    s["matchups"]={};s["tx"]={}
    for w in range(1,min(last,19)):
        m=get(f"/league/{lid}/matchups/{w}")
        if m: s["matchups"][w]=m
        s["tx"][w]=get(f"/league/{lid}/transactions/{w}")
    s["drafts"]=[]
    for d in get(f"/league/{lid}/drafts"):
        s["drafts"].append({"draft":d,"picks":get(f"/draft/{d['draft_id']}/picks"),"traded":get(f"/draft/{d['draft_id']}/traded_picks")})
    json.dump(s,open(f"{out}/{L['season']}.json","w"))
    if newest is None:  # last completed week of the newest season
        newest = L["season"]
        import datetime, zoneinfo
        if L["status"] == "complete" or state["season"] != L["season"] or state["season_type"] == "off":
            done = max((int(w) for w in s["matchups"]), default=0)
        else:
            done = int(state["week"]) - 1
            now = datetime.datetime.now(zoneinfo.ZoneInfo("America/New_York"))
            wk = s["matchups"].get(int(state["week"])) or []
            if now.weekday() in (1, 2) and wk and all((m.get("points") or 0) > 0 for m in wk): done = int(state["week"])
        json.dump({"league_id": L["league_id"], "season": L["season"], "complete": L["status"] == "complete", "last_completed_week": done,
                   "pulled_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="minutes")}, open(f"{out}/state.json", "w"))
    print(L["season"],L["name"],L["status"],L["total_rosters"],"teams", len(s["matchups"]),"wks")
    lid=L.get("previous_league_id")
