#!/usr/bin/env bash
set -euo pipefail

# Re-run specific levels that previously showed x-wing size 8,
# forcing a deeper x-wing scan cap.
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_ROOT="${ROOT_DIR}/reruns/xwing_size8"
MAX_JOBS="${MAX_JOBS:-4}"

if [[ -n "${VIRTUAL_ENV:-}" && -x "${VIRTUAL_ENV}/bin/python" ]]; then
  PYTHON_BIN="${VIRTUAL_ENV}/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3)"
else
  PYTHON_BIN="$(command -v python)"
fi

PYTHONPATH_ROOT="${ROOT_DIR}/src"

if ! [[ "${MAX_JOBS}" =~ ^[0-9]+$ ]] || [[ "${MAX_JOBS}" -lt 1 ]]; then
  echo "MAX_JOBS must be a positive integer (got: ${MAX_JOBS})" >&2
  exit 2
fi

# Note put 641 and 647 last as they are SLOW

levels=(
#   273
#   538
#   583
#   587
#   589
#   600
#   601
#   623
#   636
#   674
  641
  647
)

echo "Running ${#levels[@]} level(s) in parallel with MAX_JOBS=${MAX_JOBS}"
echo "Outputs/logs root: ${OUT_ROOT}"
echo "Python: ${PYTHON_BIN}"
echo "PYTHONUNBUFFERED: 1"

pids=()
pid_to_level=()
failures=()

start_level() {
  local lvl="$1"
  local run_dir="${OUT_ROOT}/level_${lvl}"
  local log_file="${run_dir}/run.log"
  mkdir -p "${run_dir}"
  echo "=== Launching level ${lvl} (log: ${log_file}) ==="
  (
    cd "${run_dir}"
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="${PYTHONPATH_ROOT}:${PYTHONPATH:-}" \
      "${PYTHON_BIN}" "${ROOT_DIR}/chk_stepwise.py" \
      --first "${lvl}" --last "${lvl}" --verbose --timestamps --x-wing-max 18
  ) >"${log_file}" 2>&1 &
  local pid=$!
  pids+=("${pid}")
  pid_to_level["${pid}"]="${lvl}"
}

wait_for_one() {
  local pid
  pid="${pids[0]}"
  if wait "${pid}"; then
    echo "=== Level ${pid_to_level[${pid}]} finished OK ==="
  else
    echo "=== Level ${pid_to_level[${pid}]} FAILED (see reruns/xwing_size8/level_${pid_to_level[${pid}]}/run.log) ===" >&2
    failures+=("${pid_to_level[${pid}]}")
  fi
  pids=("${pids[@]:1}")
}

for lvl in "${levels[@]}"; do
  start_level "${lvl}"
  if [[ "${#pids[@]}" -ge "${MAX_JOBS}" ]]; then
    wait_for_one
  fi
done

while [[ "${#pids[@]}" -gt 0 ]]; do
  wait_for_one
done

if [[ "${#failures[@]}" -gt 0 ]]; then
  echo "Done with failures in level(s): ${failures[*]}" >&2
  exit 1
fi

echo "Done. Outputs are under ${OUT_ROOT}/level_*/all_solutions/."
