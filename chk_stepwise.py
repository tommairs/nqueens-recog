#!/usr/bin/env python3
"""Batch stepwise solver for community levels.

Usage:
    python chk_stepwise.py [--first N] [--last N] [--rate R] [--timestamps] [--x-wing-max N] [--lookahead-max-cands N] [--verbose]

Defaults: --first 1, --last 10, --rate 2 (submissions per second).
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
import re
import subprocess
import sys
import time
from io import StringIO
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


def _write_html(
    level: int,
    out_dir: Path,
    trace: str,
    created_by: str = "",
) -> None:
    """Convert a captured stepwise trace to HTML via aha and write it."""
    out_path = out_dir / f"level_{level}.html"
    title = f"Level {level}" + (f" \u2014 by {created_by}" if created_by else "")
    try:
        proc2 = subprocess.run(
            ["aha", "--title", title],
            input=trace, capture_output=True, text=True, check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        p_stderr(f"  [HTML] aha failed: {exc}")
        return

    html = proc2.stdout.replace("</head>", f"{STYLE}</head>", 1)
    out_path.write_text(html, encoding="utf-8")
    print(f"  Written: {out_path}")


def _check_level(
    level: int,
    delay: float,
    out_dir: Path,
    timestamps: bool = False,
    x_wing_max: int = 6,
    lookahead_max_cands: int | None = None,
    verbose: bool = False,
) -> dict:
    url = BASE_URL.format(n=level)
    print(f"=== Level {level} ===")
    try:
        class _TeeBuffer:
            """Capture writes and optionally mirror them to another stream."""

            def __init__(self, sink: StringIO, mirror=None):
                self.sink = sink
                self.mirror = mirror

            def write(self, data: str) -> int:
                written = self.sink.write(data)
                if self.mirror is not None:
                    self.mirror.write(data)
                return written

            def flush(self) -> None:
                self.sink.flush()
                if self.mirror is not None:
                    self.mirror.flush()

        # --- Fetch (board + solutionsCount from TypeScript source) ---
        try:
            board, solutions_count, created_by = read_community_level_info(url)
        except ValueError:
            print("  Skip: could not parse level source")
            return {"level": level, "status": "skipped", "size": None, "multi": False, "elapsed": None, "xwing_max": None, "rules": [], "created_by": ""}
        except RuntimeError as exc:
            msg = str(exc)
            if "404" in msg or "Not Found" in msg:
                print("  Skip: level not found (404)")
            else:
                print(f"  Skip: fetch error — {exc}")
            return {"level": level, "status": "skipped", "size": None, "multi": False, "elapsed": None, "xwing_max": None, "rules": [], "created_by": ""}

        n = len(board)
        print(f"  Board: {n}×{n}, solutionsCount={solutions_count}, createdBy={created_by or '(unknown)'}")

        unique = solutions_count == 1

        # --- Stepwise solver (single run: capture trace + optional live mirror) ---
        t0 = time.perf_counter()
        buf = StringIO()
        _stdout_orig = sys.stdout
        sys.stdout = _TeeBuffer(buf, _stdout_orig if verbose else None)
        try:
            # Match CLI stepwise output: include the starting grid before deductions.
            from nqueens_recog.display import print_board
            print(f"Grid: {n} × {n}, {n} colours")
            print_board(board)
            step_result, rules_used = solve_stepwise(
                board,
                quiet=False,
                verbose=True,
                timestamps=timestamps,
                x_wing_max=x_wing_max,
                lookahead_max_cands=lookahead_max_cands,
            )
        finally:
            sys.stdout = _stdout_orig
        trace = buf.getvalue()
        step_elapsed = time.perf_counter() - t0
        xwing_sizes = [int(m.group(1)) for m in re.finditer(r"x-wing: size (\d+)", trace)]
        max_xwing_size = max(xwing_sizes) if xwing_sizes else None

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
        _write_html(level, out_dir, trace, created_by)

        if delay > 0:
            time.sleep(delay)

        return {
            "level": level,
            "status": status,
            "size": n,
            "multi": not unique,
            "elapsed": step_elapsed,
            "xwing_max": max_xwing_size,
            "rules": rules,
            "created_by": created_by,
        }
    except Exception as exc:
        print(f"[ERROR] Exception in _check_level for level {level}: {exc}")
        return {"level": level, "status": "error", "size": None, "multi": False, "elapsed": None, "xwing_max": None, "rules": [], "created_by": "", "error": str(exc)}


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
        size = r.get("size")
        size_cell = str(size) if size is not None else ""
        multi = "Y" if r["multi"] else ""
        runtime = f"{r['elapsed']:.3f}s" if r["elapsed"] is not None else ""
        xwing_cell = str(r.get("xwing_max")) if r.get("xwing_max") is not None else ""
        if r["status"] == "ok":
            rules_cell = ", ".join(r["rules"]) if r["rules"] else "(none)"
        else:
            rules_cell = f'<em>{r["status"]}</em>'
        rows.append(
            f"  <tr><td>{play_cell}</td><td>{level_cell}</td><td>{size_cell}</td><td>{multi}</td>"
            f"<td>{r['created_by']}</td><td>{runtime}</td><td>{xwing_cell}</td><td>{rules_cell}</td></tr>"
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
        "td:nth-child(6){text-align:right;font-variant-numeric:tabular-nums}\n"
        "</style>\n"
        "</head>\n<body>\n"
        "<input id=\"filter\" type=\"search\" placeholder=\"Filter\u2026\""
        " style=\"margin-bottom:8px;padding:4px 8px;font-size:14px;"
        "border:1px solid #ccc;border-radius:4px;width:300px\">\n"
        "<table>\n"
        "<thead><tr><th>Play</th><th>Stepwise solution</th><th>Size</th><th>Multi</th><th>Created by</th><th>Runtime</th><th>Max X-Wing</th><th>Rules used</th></tr></thead>\n"
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
        "      if(col===1||col===2||col===5||col===6){\n"
        "        var an=(col===2||col===6?parseInt(av,10):parseFloat(av))||0;\n"
        "        var bn=(col===2||col===6?parseInt(bv,10):parseFloat(bv))||0;\n"
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
    parser.add_argument("--rate", type=float, default=2.0, metavar="R", help="Submissions per second; 0=unlimited (default: 2)")
    parser.add_argument("--timestamps", action="store_true", help="Prefix stepwise trace lines with elapsed time in generated outputs")
    parser.add_argument(
        "--x-wing-max",
        type=int,
        default=6,
        metavar="N",
        help="Maximum X-Wing group size to scan (default: 6)",
    )
    parser.add_argument(
        "--lookahead-max-cands",
        type=int,
        default=None,
        metavar="N",
        help=(
            "If set, lookahead only evaluates colours with at most N active "
            "candidates and applies all such lookahead eliminations in one pass"
        ),
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Stream stepwise trace to stdout during batch processing",
    )
    args = parser.parse_args()
    if (args.first is not None) ^ (args.last is not None):
        parser.error("--first and --last must be specified together, or both omitted for auto mode.")
    if args.x_wing_max < 2:
        parser.error("--x-wing-max must be >= 2")
    if args.lookahead_max_cands is not None and args.lookahead_max_cands < 1:
        parser.error("--lookahead-max-cands must be >= 1")
    return args

def process_levels(
    levels,
    out_dir,
    rate,
    timestamps=False,
    x_wing_max=6,
    lookahead_max_cands=None,
    verbose=False,
):
    min_gap = 1.0 / rate if rate > 0 else 0.0
    results: list[dict] = []
    # Directly call _check_level in the main process, no multiprocessing
    for level in levels:
        result = _check_level(level, 0, out_dir, timestamps, x_wing_max, lookahead_max_cands, verbose)
        results.append(result)
        if min_gap > 0:
            time.sleep(min_gap)
    return results


def _process_levels_compat(
    levels,
    out_dir,
    rate,
    timestamps=False,
    x_wing_max=6,
    lookahead_max_cands=None,
    verbose=False,
):
    """Call process_levels with backward compatibility for test monkeypatches."""
    try:
        return process_levels(
            levels,
            out_dir,
            rate,
            timestamps,
            x_wing_max,
            lookahead_max_cands,
            verbose,
        )
    except TypeError as exc:
        # Some tests monkeypatch process_levels with the old 4-argument shape.
        msg = str(exc)
        if "positional argument" in msg or "unexpected keyword argument" in msg:
            return process_levels(levels, out_dir, rate, timestamps)
        raise


def run_auto_mode(
    out_dir,
    rate,
    timestamps=False,
    x_wing_max=6,
    lookahead_max_cands=None,
    verbose=False,
):
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
                if len(cols) in (6, 7, 8):
                    m = re.search(r'>(\d+)<', cols[1]) or re.search(r'>(\d+)<', cols[1], re.IGNORECASE)
                    if not m:
                        try:
                            n = int(cols[1])
                        except Exception:
                            continue
                    else:
                        n = int(m.group(1))
                    if len(cols) == 8:
                        size_match = re.search(r'(\d+)\s*(?:[xX×]\s*\1)?$', cols[2].strip())
                        size_val = int(size_match.group(1)) if size_match else None
                        multi_col = cols[3]
                        created_col = cols[4]
                        runtime_col = cols[5]
                        xwing_col = cols[6]
                        rules_col = cols[7]
                    elif len(cols) == 7:
                        size_match = re.search(r'(\d+)\s*(?:[xX×]\s*\1)?$', cols[2].strip())
                        size_val = int(size_match.group(1)) if size_match else None
                        multi_col = cols[3]
                        created_col = cols[4]
                        runtime_col = cols[5]
                        xwing_col = ""
                        rules_col = cols[6]
                    else:
                        size_val = None
                        multi_col = cols[2]
                        created_col = cols[3]
                        runtime_col = cols[4]
                        xwing_col = ""
                        rules_col = cols[5]
                    xwing_match = re.search(r'(\d+)', xwing_col.strip())
                    xwing_val = int(xwing_match.group(1)) if xwing_match else None
                    prev_results[n] = {
                        "level": n,
                        "status": "ok" if not rules_col.startswith('<em>') else unescape(rules_col[4:-5]),
                        "size": size_val,
                        "multi": multi_col.strip() == "Y",
                        "created_by": created_col,
                        "elapsed": float(runtime_col.replace('s','')) if runtime_col else None,
                        "xwing_max": xwing_val,
                        "rules": [] if rules_col.startswith('<em>') else [r.strip() for r in rules_col.split(',')],
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
        results.extend(
            _process_levels_compat(
                missing_levels,
                out_dir,
                rate,
                timestamps,
                x_wing_max,
                lookahead_max_cands,
                verbose,
            )
        )
        found_any = any(r.get("status") == "ok" for r in results)
    # Then, continue with new levels after max_level
    level = max_level + 1
    print(f"Checking if new level {level} exists yet: ", end="")
    while True:
        url = BASE_URL.format(n=level)
        try:
            board, solutions_count, created_by = read_community_level_info(url)
        except Exception as exc:
            # If 404 or not found, stop searching for new levels
            msg = str(exc)
            if "404" in msg or "Not Found" in msg:
                print("level not found (404)")
                break
            else:
                print(f"fetch error — {exc}")
                break
        # If found, process it fully
        res = _process_levels_compat(
            [level],
            out_dir,
            rate,
            timestamps,
            x_wing_max,
            lookahead_max_cands,
            verbose,
        )
        if not res:
            break
        r = res[0]
        results.append(r)
        sys.stdout.flush()
        if r.get("status") == "ok":
            found_any = True
            level += 1
        elif r.get("status") == "skipped":
            break
        else:
            level += 1
    merged = {r["level"]: r for r in results if r.get("status") == "ok"}
    for n, r in prev_results.items():
        if n not in merged:
            merged[n] = r
    merged_results = [merged[n] for n in sorted(merged)]
    if found_any or merged_results:
        _write_index_html(merged_results, out_dir)
    else:
        print("No new levels found to solve.")

def run_range_mode(
    first,
    last,
    out_dir,
    rate,
    timestamps=False,
    x_wing_max=6,
    lookahead_max_cands=None,
    verbose=False,
):
    if first > last:
        p_stderr(f"Error: FIRST ({first}) > LAST ({last})")
        sys.exit(1)
    levels = list(range(first, last + 1))
    # Always process the requested levels, regardless of existing files
    results = _process_levels_compat(
        levels,
        out_dir,
        rate,
        timestamps,
        x_wing_max,
        lookahead_max_cands,
        verbose,
    )
    found_any = any(r.get("status") == "ok" for r in results)
    if found_any:
        _write_index_html(results, out_dir)
    else:
        print("No new levels found to solve.")


def main():
    args = parse_args()
    out_dir = Path("all_solutions")
    out_dir.mkdir(exist_ok=True)
    if args.first is None and args.last is None:
        run_auto_mode(
            out_dir,
            args.rate,
            args.timestamps,
            args.x_wing_max,
            args.lookahead_max_cands,
            args.verbose,
        )
    else:
        first = args.first
        last = args.last
        run_range_mode(
            first,
            last,
            out_dir,
            args.rate,
            args.timestamps,
            args.x_wing_max,
            args.lookahead_max_cands,
            args.verbose,
        )

if __name__ == "__main__":
    main()
