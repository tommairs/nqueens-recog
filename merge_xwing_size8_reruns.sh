#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAIN_SOLUTIONS_DIR="${ROOT_DIR}/all_solutions"
MAIN_INDEX="${MAIN_SOLUTIONS_DIR}/index.html"
RERUN_ROOT="${ROOT_DIR}/reruns/xwing_size8"
BACKUP_INDEX="${MAIN_INDEX}.bak.xwing_size8_merge"

levels=(

  647
  674
)

if [[ ! -f "${MAIN_INDEX}" ]]; then
  echo "Missing main index: ${MAIN_INDEX}" >&2
  exit 1
fi

cp "${MAIN_INDEX}" "${BACKUP_INDEX}"
echo "Backed up main index to ${BACKUP_INDEX}"

for lvl in "${levels[@]}"; do
  rerun_dir="${RERUN_ROOT}/level_${lvl}/all_solutions"
  rerun_html="${rerun_dir}/level_${lvl}.html"
  rerun_index="${rerun_dir}/index.html"
  main_html="${MAIN_SOLUTIONS_DIR}/level_${lvl}.html"

  if [[ ! -f "${rerun_html}" ]]; then
    echo "Missing rerun html for level ${lvl}: ${rerun_html}" >&2
    exit 1
  fi
  if [[ ! -f "${rerun_index}" ]]; then
    echo "Missing rerun index for level ${lvl}: ${rerun_index}" >&2
    exit 1
  fi

  echo "=== Merging level ${lvl} ==="
  cp "${rerun_html}" "${main_html}"

  python3 - <<'PY' "${MAIN_INDEX}" "${rerun_index}" "${lvl}"
from pathlib import Path
import re
import sys

main_index = Path(sys.argv[1])
rerun_index = Path(sys.argv[2])
level = sys.argv[3]
pattern = rf'^\s*<tr><td><a href="https://queensgame\.vercel\.app/community-level/{re.escape(level)}">Play</a></td><td><a href="level_{re.escape(level)}\.html">{re.escape(level)}</a></td>.*</tr>$'
row_re = re.compile(pattern, re.MULTILINE)

main_text = main_index.read_text(encoding='utf-8')
rerun_text = rerun_index.read_text(encoding='utf-8')

main_match = row_re.search(main_text)
if not main_match:
    raise SystemExit(f"Could not find main index row for level {level}")
rerun_match = row_re.search(rerun_text)
if not rerun_match:
    raise SystemExit(f"Could not find rerun index row for level {level}")

updated = main_text[:main_match.start()] + rerun_match.group(0) + main_text[main_match.end():]
main_index.write_text(updated, encoding='utf-8')
PY

done

echo "Merge prepared successfully. Updated files are in ${MAIN_SOLUTIONS_DIR}."
echo "Main index backup: ${BACKUP_INDEX}"
