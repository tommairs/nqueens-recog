#!/usr/bin/env bash
# Fetch and solve all known community levels, writing terse solution lines to
# all_solutions/solutions.txt.
#
# Usage (with the project venv active):
#   bash solve_all.sh [FIRST [LAST]]
#
# Defaults: levels 1-699.  Levels that don't exist (404) are silently skipped.

set -euo pipefail

FIRST=${1:-1}
LAST=${2:-699}
DELAY=${3:-1}   # seconds between requests (default 1); set to 0 to disable
mkdir -p all_solutions
OUTPUT="all_solutions/solutions.txt"
: > "$OUTPUT"   # truncate / create

echo "Solving levels $FIRST-$LAST -> $OUTPUT (delay=${DELAY}s)" >&2

for n in $(seq "$FIRST" "$LAST"); do
    url="https://queensgame.vercel.app/community-level/$n"
    echo "=== Level $n ===" | tee -a "$OUTPUT"
    nqueens-recog "$url" --solve 2>&1 | tee -a "$OUTPUT" || true
    sleep "$DELAY"
done
