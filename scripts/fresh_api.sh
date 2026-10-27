#!/usr/bin/env bash
# Start the API from a fresh demo state, every time it runs (docs/nba-guide.md §6.10):
#   1. stop an API already listening on the port;
#   2. scripts/reset_demo.sh: move the state files (decisions, Rule Center edits, customer memory, service feedback,
#      campaign fast-forwards) to out/_reset_<time>/ and learn the starting memory from the workbook;
#   3. rebuild the Knowledge Base file (web/public/data/kg_viz.json);
#   4. run uvicorn in the foreground (Ctrl+C stops it).
#   scripts/fresh_api.sh                 fresh start on port 8000
#   scripts/fresh_api.sh --no-memory     start from "nothing learned yet"
#   scripts/fresh_api.sh --port 8001     another port
# The browser keeps its own data (decisions, campaigns, outcomes) in localStorage; clear it as reset_demo.sh prints.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PY:-.venv/bin/python}
port=8000; reset_args=()
while [ $# -gt 0 ]; do
  case "$1" in
    --no-memory) reset_args+=(--no-memory) ;;
    --port) port=${2:?--port needs a value}; shift ;;
    *) echo "unknown option $1" >&2; exit 2 ;;
  esac
  shift
done

running=$(lsof -ti "tcp:$port" -sTCP:LISTEN || true)
if [ -n "$running" ]; then
  echo "stopping the process on port $port ($running)"
  kill $running
  for _ in $(seq 1 50); do lsof -ti "tcp:$port" -sTCP:LISTEN >/dev/null || break; sleep 0.1; done
fi

scripts/reset_demo.sh ${reset_args[@]+"${reset_args[@]}"} | sed '/^Done\. Now:/,$d'
"$PY" scripts/export_kg_viz.py --out web/public/data/kg_viz.json | tail -1

echo
echo "API on http://127.0.0.1:$port. In the browser, clear the app's local data once:"
echo '  Object.keys(localStorage).filter(k => k.startsWith("maingau.")).forEach(k => localStorage.removeItem(k)); location.reload()'
echo
exec "$PY" -m uvicorn api.app:app --port "$port"
