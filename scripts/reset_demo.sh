#!/usr/bin/env bash
# Put the demo back to its starting state (docs/nba-guide.md §6.10). Nothing is deleted: the API's state files
# (decisions, Rule Center edits, customer memory, service feedback) are moved to out/_reset_<time>/.
#   scripts/reset_demo.sh                  reset, then learn the starting memory from the workbook (API = static export)
#   scripts/reset_demo.sh --no-memory      reset to "nothing learned yet"
#   scripts/reset_demo.sh --restore-inputs also put data/, config/, kg/ and web/public/data back to the committed version
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PY:-.venv/bin/python}
learn=1; restore=0
for a in "$@"; do
  case "$a" in
    --no-memory) learn=0 ;;
    --restore-inputs) restore=1 ;;
    *) echo "unknown option $a" >&2; exit 2 ;;
  esac
done

keep="out/_reset_$(date +%Y%m%d-%H%M%S)"
mkdir -p "$keep"
for f in decision_log.jsonl rule_versions.jsonl customer_memory.jsonl service_feedback.jsonl; do
  if [ -f "out/$f" ]; then mv "out/$f" "$keep/"; echo "moved out/$f -> $keep/"; fi
done

changed=$(git status --porcelain -- data config kg web/public/data | wc -l | tr -d ' ')
if [ "$restore" = 1 ]; then
  git restore --source=HEAD --staged --worktree -- data config kg web/public/data
  echo "restored data/, config/, kg/ and web/public/data to the committed version"
elif [ "$changed" != 0 ]; then
  echo "note: $changed changed file(s) in data/, config/, kg/ or web/public/data; run with --restore-inputs to discard them:"
  git status --short -- data config kg web/public/data | head -10
fi

if [ "$learn" = 1 ]; then
  "$PY" -m nba.ai feedback --no-ai | tail -1
fi

cat <<'MSG'

Done. Now:
  1. Restart the API (it keeps its state in memory):  .venv/bin/uvicorn api.app:app --port 8000
  2. In the browser, open the app and clear its local data: DevTools > Console, paste
       Object.keys(localStorage).filter(k => k.startsWith("maingau.")).forEach(k => localStorage.removeItem(k)); location.reload()
     (or use a private window).
MSG
