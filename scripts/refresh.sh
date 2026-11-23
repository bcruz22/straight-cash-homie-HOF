#!/usr/bin/env bash
# Weekly Hall of Fame refresh. Usage: refresh.sh <workdir with scripts/ and tracker.json>
set -euo pipefail
W="$1"; cd "$W"
rm -rf raw out && mkdir -p raw out
python3 -I scripts/pull.py 1389303477989048320 raw 593654007445118976
curl -sf https://api.sleeper.app/v1/players/nfl -o raw/players.json
cp tracker.json raw/tracker.json
python3 -I scripts/build.py raw league_history.json
python3 -I scripts/export.py league_history.json out scripts
python3 -I scripts/keepers_next.py raw out scripts | head -1
cat raw/state.json
