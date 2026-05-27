#!/usr/bin/env bash
# Fetch, solve, and render a single community level as a styled HTML file.
#
# Usage (with the project venv active):
#   bash solve_html.sh <level>
#
# Output: all_solutions/level_<N>.html

set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 <level>" >&2
    exit 1
fi

PUZZLE=$1
URL="https://queensgame.vercel.app/community-level/$PUZZLE"
OUTPUT="all_solutions/level_${PUZZLE}.html"
STYLE='<style>pre{font-family:"SF Pro Rounded",-apple-system,BlinkMacSystemFont,sans-serif;font-size:14px;line-height:1.4}pre span{display:inline-block;height:1.4em;overflow:hidden;vertical-align:top;width:4ch}</style>'

mkdir -p all_solutions
nqueens-recog "$URL" --stepwise --verbose \
    | aha \
    | sed "s|</head>|${STYLE}</head>|" \
    > "$OUTPUT"

echo "Written: $OUTPUT" >&2
