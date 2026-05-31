#!/usr/bin/env python3
"""Batch stepwise solver for community levels.

Usage:
    python chk_stepwise.py [--first N] [--last N] [--workers N] [--rate R]

Defaults: --first 1, --last 10, --workers 8, --rate 2 (submissions per second).
Set --rate 0 to submit as fast as possible.

For each level in [--first, --last]:
  - Fetch the board and read solutionsCount / createdBy from the TypeScript source.
  - Run the stepwise solver and capture its trace.
  - Validate the result; report invalid/stuck solutions on stderr.
  - Print elapsed time and which deduction rules were used.
  - Write all_solutions/level_<N>.html via aha.
Finally writes all_solutions/index.html with a summary table.
"""

import argparse
import contextlib
import subprocess
import sys
import time
from io import StringIO
from multiprocessing import Pool
from pathlib import Path

# ---------------------------------------------------------------------------
# Imports from the installed package (run from project root with venv active)
# ---------------------------------------------------------------------------
from nqueens_recog.stepwise import solve_stepwise, compact_rules_used
from nqueens_recog.url_reader import read_community_level_info

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_URL = "https://queensgame.vercel.app/community-level/{n}"

STYLE = (
    '<style>'
    'pre{font-family:"SF Pro Rounded",-apple-system,BlinkMacSystemFont,'
    'sans-serif;font-size:14px;line-height:1.4}'
    'pre span{display:inline-block;height:1.4em;overflow:hidden;'
    'vertical-align:top;width:4ch}'
    '</style>'
)

# ---------------------------------------------------------------------------

def p_stderr(*args, **kwargs) -> None:
    """Print to stderr."""
    print(*args, **kwargs, file=sys.stderr)


def _validate(board: list[list[str]], result: dict[int, int]) -> list[str]:
    """Return a list of constraint violations in *result* (empty = valid)."""
    n = len(board)
    errors: list[str] = []
    if set(result.keys()) != set(range(n)):
        errors.append(f"wrong rows: {sorted(result)}")
        return errors
    if len(set(result.values())) != n:
        errors.append("duplicate columns")
    colours = {board[r][result[r]] for r in range(n)}
    if len(colours) != n:
        errors.append("duplicate colours")
    queens = [(result[r], r) for r in range(n)]
    for i, (x1, y1) in enumerate(queens):
        for x2, y2 in queens[i + 1:]:
            if abs(x1 - x2) == 1 and abs(y1 - y2) == 1:
                errors.append(f"diagonal adjacency ({y1},{x1})↔({y2},{x2})")
    return errors


def _write_html(level: int, url: str, out_dir: Path, created_by: str = "") -> None:
    """Run nqueens-recog --stepwise --verbose | aha and write the HTML file."""
    out_path = out_dir / f"level_{level}.html"
    title = f"Level {level}" + (f" \u2014 by {created_by}" if created_by else "")
    try:
        proc1 = subprocess.run(
            [sys.executable, "-m", "nqueens_recog", url, "--stepwise", "--verbose"],
            capture_output=True, text=True, check=True,
        )
    except subprocess.CalledProcessError as exc:
        p_stderr(f"  [HTML] nqueens-recog failed: {exc.stderr.strip()}")
        return

    try:
        proc2 = subprocess.run(
            ["aha", "--title", title],
            input=proc1.stdout, capture_output=True, text=True, check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        p_stderr(f"  [HTML] aha failed: {exc}")
        return

    html = proc2.stdout.replace("</head>", f"{STYLE}</head>", 1)
    out_path.write_text(html, encoding="utf-8")
    print(f"  Written: {out_path}")


def _check_level(level: int, delay: float, out_dir: Path) -> dict:
    import traceback
    url = BASE_URL.format(n=level)
    print(f"=== Level {level} ===")
    try:
        # --- Fetch (board + solutionsCount from TypeScript source) ---
        try:
            board, solutions_count, created_by = read_community_level_info(url)
        except ValueError:
            print("  Skip: could not parse level source")
            return {"level": level, "status": "skipped", "multi": False, "elapsed": None, "rules": [], "created_by": ""}
        except RuntimeError as exc:
            msg = str(exc)
            if "404" in msg or "Not Found" in msg:
                print("  Skip: level not found (404)")
            else:
                print(f"  Skip: fetch error — {exc}")
            return {"level": level, "status": "skipped", "multi": False, "elapsed": None, "rules": [], "created_by": ""}

        n = len(board)
        print(f"  Board: {n}×{n}, solutionsCount={solutions_count}, createdBy={created_by or '(unknown)'}")

        unique = solutions_count == 1

        # --- Stepwise solver (capture trace) ---
        buf = StringIO()
        _stdout_orig = sys.stdout
        sys.stdout = buf
        t0 = time.perf_counter()
        try:
            step_result, rules_used = solve_stepwise(board, quiet=False, verbose=False)
        finally:
            sys.stdout = _stdout_orig
        step_elapsed = time.perf_counter() - t0
        trace = buf.getvalue()

        # Compact rules_used to unique rule names in declaration order using stepwise.py logic
        rules = compact_rules_used(rules_used)

        timing = f"stepwise {step_elapsed:.3f}s"
        tag = "" if unique else " (multi-solution)"

        if step_result is None:
            p_stderr(f"  Stepwise: stuck (returned None) [{timing}]")
            status = "stuck"
        else:
            errors = _validate(board, step_result)
            if errors:
                p_stderr(f"!! INVALID solution level {level}: {'; '.join(errors)}")
                status = "invalid"
            else:
                print(f"  Stepwise: ok{tag} [{timing}] — rules used: {', '.join(rules) if rules else '(none)'}")
                status = "ok"

        # --- Write HTML ---
        _write_html(level, url, out_dir, created_by)

        if delay > 0:
            time.sleep(delay)

        return {"level": level, "status": status, "multi": not unique, "elapsed": step_elapsed, "rules": rules, "created_by": created_by}
    except Exception as exc:
        print(f"[ERROR] Exception in _check_level for level {level}: {exc}")
        traceback.print_exc()
        return {"level": level, "status": "error", "multi": False, "elapsed": None, "rules": [], "created_by": "", "error": str(exc)}


def _worker(args: tuple) -> tuple[str, str, dict]:
    """Run _check_level in a subprocess-safe way, capturing stdout and stderr."""
    import traceback
    level, out_dir = args
    stdout_buf = StringIO()
    stderr_buf = StringIO()
    try:
        with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
            result = _check_level(level, 0, out_dir)
    except Exception as exc:
        print(f"[ERROR] Exception in _worker for level {level}: {exc}")
        traceback.print_exc()
        result = {"level": level, "status": "error", "multi": False, "elapsed": None, "rules": [], "created_by": "", "error": str(exc)}
    return stdout_buf.getvalue(), stderr_buf.getvalue(), result


def _write_index_html(results: list[dict], out_dir: Path) -> None:
    """Write a summary table of all processed levels to index.html."""
    rows = []
    for r in results:
        lvl = r["level"]
        play_cell = f'<a href="https://queensgame.vercel.app/community-level/{lvl}">Play</a>'
        level_cell = (
            f'<a href="level_{lvl}.html">{lvl}</a>'
            if r["status"] != "skipped" else str(lvl)
        )
        multi = "Y" if r["multi"] else ""
        runtime = f"{r['elapsed']:.3f}s" if r["elapsed"] is not None else ""
        if r["status"] == "ok":
            rules_cell = ", ".join(r["rules"]) if r["rules"] else "(none)"
        else:
            rules_cell = f'<em>{r["status"]}</em>'
        rows.append(
            f"  <tr><td>{play_cell}</td><td>{level_cell}</td><td>{multi}</td>"
            f"<td>{r['created_by']}</td><td>{runtime}</td><td>{rules_cell}</td></tr>"
        )
    rows_html = "\n".join(rows)
    html = (
        "<!DOCTYPE html>\n"
        "<html>\n<head>\n<meta charset=\"utf-8\">\n"
        "<title>N-Queens Solutions</title>\n"
        "<style>\n"
        "body{font-family:-apple-system,BlinkMacSystemFont,sans-serif;font-size:14px}\n"
        "table{border-collapse:collapse}\n"
        "th,td{padding:3px 10px;text-align:left;border-bottom:1px solid #ddd}\n"
        "th{background:#f5f5f5;cursor:pointer;user-select:none}\n"
        "th:hover{background:#e8e8e8}\n"
        "td:nth-child(5){text-align:right;font-variant-numeric:tabular-nums}\n"
        "</style>\n"
        "</head>\n<body>\n"
        "<input id=\"filter\" type=\"search\" placeholder=\"Filter\u2026\""
        " style=\"margin-bottom:8px;padding:4px 8px;font-size:14px;"
        "border:1px solid #ccc;border-radius:4px;width:300px\">\n"
        "<table>\n"
        "<thead><tr><th>Play</th><th>Stepwise solution</th><th>Multi</th><th>Created by</th><th>Runtime</th><th>Rules used</th></tr></thead>\n"
        "<tbody>\n"
        f"{rows_html}\n"
        "</tbody>\n</table>\n"
        "<script>\n"
        "(function(){\n"
        "var inp=document.getElementById('filter');\n"
        "inp.addEventListener('input',function(){\n"
        "  var q=this.value.toLowerCase();\n"
        "  document.querySelectorAll('tbody tr').forEach(function(r){\n"
        "    r.style.display=r.textContent.toLowerCase().includes(q)?'':'none';\n"
        "  });\n"
        "});\n"
        "var tbody=document.querySelector('tbody');\n"
        "var sc=-1,sa=true;\n"
        "document.querySelectorAll('thead th').forEach(function(th,col){\n"
        "  th.addEventListener('click',function(){\n"
        "    if(sc===col){sa=!sa;}else{sc=col;sa=true;}\n"
        "    document.querySelectorAll('thead th').forEach(function(h,i){\n"
        "      h.textContent=h.textContent.replace(/ [\u25b2\u25bc]$/,'');\n"
        "      if(i===col)h.textContent+=sa?' \u25b2':' \u25bc';\n"
        "    });\n"
        "    var rows=Array.from(tbody.querySelectorAll('tr'));\n"
        "    rows.sort(function(a,b){\n"
        "      var av=a.cells[col].textContent.trim();\n"
        "      var bv=b.cells[col].textContent.trim();\n"
        "      if(col===1||col===4){\n"
        "        var an=parseFloat(av)||0,bn=parseFloat(bv)||0;\n"
        "        return sa?an-bn:bn-an;\n"
        "      }\n"
        "      return sa?av.localeCompare(bv):bv.localeCompare(av);\n"
        "    });\n"
        "    rows.forEach(function(r){tbody.appendChild(r);});\n"
        "  });\n"
        "});\n"
        "})();\n"
        "</script>\n"
        "</body>\n</html>\n"
    )
    index_path = out_dir / "index.html"
    index_path.write_text(html, encoding="utf-8")
    print(f"Written: {index_path}")


def parse_args():
    parser = argparse.ArgumentParser(
        prog="chk_stepwise",
        description="Run the stepwise solver over community levels and write HTML output.",
    )
    group = parser.add_argument_group("level range (omit both for auto mode)")
    group.add_argument("--first", type=int, metavar="N", help="First level number (inclusive)")
    group.add_argument("--last", type=int, metavar="N", help="Last level number (inclusive)")
    parser.add_argument("--workers", type=int, default=8, metavar="N", help="Worker processes (default: 8)")
    parser.add_argument("--rate", type=float, default=2.0, metavar="R", help="Submissions per second; 0=unlimited (default: 2)")
    args = parser.parse_args()
    if (args.first is not None) ^ (args.last is not None):
        parser.error("--first and --last must be specified together, or both omitted for auto mode.")
    return args

def process_levels(levels, out_dir, workers, rate):
    min_gap = 1.0 / rate if rate > 0 else 0.0
    results: list[dict] = []
    if workers == 1:
        # Directly call _check_level in the main process, no multiprocessing
        for level in levels:
            result = _check_level(level, 0, out_dir)
            results.append(result)
            if min_gap > 0:
                time.sleep(min_gap)
        return results
    else:
        with Pool(workers) as pool:
            futures_by_level: dict[int, object] = {}
            buffered: dict[int, tuple[str, str, dict]] = {}
            next_to_print = min(levels) if levels else 0
            submit_idx = 0
            next_submit_time = time.monotonic()
            found_any = False
            while submit_idx < len(levels) or buffered:
                now = time.monotonic()
                # Submit next level if within rate limit
                if submit_idx < len(levels) and now >= next_submit_time:
                    level = levels[submit_idx]
                    futures_by_level[level] = pool.apply_async(_worker, ((level, out_dir),))
                    submit_idx += 1
                    next_submit_time = now + min_gap
                # Collect completed
                for level, future in list(futures_by_level.items()):
                    if future.ready():
                        buffered[level] = future.get()
                        del futures_by_level[level]
                # Print in order
                while next_to_print in buffered:
                    stdout_text, stderr_text, result = buffered.pop(next_to_print)
                    sys.stdout.write(stdout_text)
                    sys.stdout.flush()
                    if stderr_text:
                        sys.stderr.write(stderr_text)
                        sys.stderr.flush()
                    results.append(result)
                    if result.get("status") == "ok":
                        found_any = True
                    next_to_print += 1
                if submit_idx < len(levels) or buffered:
                    time.sleep(0.05)
        return results

def run_auto_mode(out_dir, workers, rate):
    import re
    index_path = out_dir / "index.html"
    max_level_index = 0
    min_level = None
    prev_results = {}
    if index_path.exists():
        from html import unescape
        with index_path.open("r", encoding="utf-8") as f:
            html_lines = f.readlines()
        tbody = False
        row_lines = []
        for line in html_lines:
            if '<tbody>' in line:
                tbody = True
                continue
            if '</tbody>' in line:
                break
            if not tbody:
                continue
            if '<tr>' in line:
                row_lines = [line]
            elif row_lines:
                row_lines.append(line)
            if row_lines and '</tr>' in line:
                row_html = ''.join(row_lines)
                cols = re.findall(r'<td>(.*?)</td>', row_html, re.DOTALL)
                if len(cols) == 6:
                    m = re.search(r'>(\d+)<', cols[1]) or re.search(r'>(\d+)<', cols[1], re.IGNORECASE)
                    if not m:
                        try:
                            n = int(cols[1])
                        except Exception:
                            continue
                    else:
                        n = int(m.group(1))
                    prev_results[n] = {
                        "level": n,
                        "status": "ok" if not cols[5].startswith('<em>') else unescape(cols[5][4:-5]),
                        "multi": cols[2].strip() == "Y",
                        "created_by": cols[3],
                        "elapsed": float(cols[4].replace('s','')) if cols[4] else None,
                        "rules": [] if cols[5].startswith('<em>') else [r.strip() for r in cols[5].split(',')],
                    }
                    if n > max_level_index:
                        max_level_index = n
                    if min_level is None or n < min_level:
                        min_level = n
                row_lines = []
    else:
        print("No index.html found, starting from level 1.")
    # Only use index.html to determine solved/missing levels
    max_level = max_level_index
    if min_level is None:
        min_level = 1
    solved_levels = set(prev_results.keys())
    all_in_range = set(range(min_level, max_level + 1))
    missing_levels = sorted(all_in_range - solved_levels)
    if missing_levels:
        print(f"Missing levels detected: {missing_levels}")
    else:
        print("No missing levels detected in existing index.html.")
    results = []
    found_any = False
    # Process missing levels (gaps)
    if missing_levels:
        results.extend(process_levels(missing_levels, out_dir, workers, rate))
        found_any = any(r.get("status") == "ok" for r in results)
    # Then, continue with new levels after max_level
    level = max_level + 1
    new_results = []
    while True:
        res = process_levels([level], out_dir, workers, rate)
        if not res:
            break
        r = res[0]
        new_results.append(r)
        sys.stdout.flush()
        if r.get("status") == "ok":
            found_any = True
            level += 1
        elif r.get("status") == "skipped":
            break
        else:
            level += 1
    results.extend(new_results)
    merged = {r["level"]: r for r in results if r.get("status") == "ok"}
    for n, r in prev_results.items():
        if n not in merged:
            merged[n] = r
    merged_results = [merged[n] for n in sorted(merged)]
    if found_any or merged_results:
        _write_index_html(merged_results, out_dir)
    else:
        print("No new levels found to solve.")

def run_range_mode(first, last, out_dir, workers, rate):
    if first > last:
        p_stderr(f"Error: FIRST ({first}) > LAST ({last})")
        sys.exit(1)
    levels = list(range(first, last + 1))
    # Always process the requested levels, regardless of existing files
    results = process_levels(levels, out_dir, workers, rate)
    found_any = any(r.get("status") == "ok" for r in results)
    if found_any:
        _write_index_html(results, out_dir)
    else:
        print("No new levels found to solve.")


def main():
    args = parse_args()
    out_dir = Path("all_solutions")
    out_dir.mkdir(exist_ok=True)
    workers, rate = args.workers, args.rate
    if args.first is None and args.last is None:
        run_auto_mode(out_dir, workers, rate)
    else:
        first = args.first
        last = args.last
        run_range_mode(first, last, out_dir, workers, rate)

        
if __name__ == "__main__":
    main()
