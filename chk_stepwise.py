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
from nqueens_recog.stepwise import solve_stepwise
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

# Substrings that appear in the stepwise trace for each rule, in the order
# they are listed in the solver's main loop.
RULE_MARKERS: list[tuple[str, str]] = [
    ("singleton",    "singleton"),
    ("forced",       "forced:"),
    ("squeeze",      "squeeze:"),
    ("shadow",       "shadow:"),
    ("n-group",      "n-group:"),
    ("x-wing",       "x-wing:"),
    ("elimination",  "eliminate:"),
    ("double-block", "double-block:"),
    ("search",       "search ["),
]

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


def _rules_used(trace: str) -> list[str]:
    """Return the names of rules that fired, in definition order."""
    return [name for name, marker in RULE_MARKERS if marker in trace]


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
    url = BASE_URL.format(n=level)
    print(f"=== Level {level} ===")

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
        step_result = solve_stepwise(board, quiet=False, verbose=False)
    finally:
        sys.stdout = _stdout_orig
    step_elapsed = time.perf_counter() - t0
    trace = buf.getvalue()
    rules = _rules_used(trace)

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


def _worker(args: tuple) -> tuple[str, str, dict]:
    """Run _check_level in a subprocess-safe way, capturing stdout and stderr."""
    level, out_dir = args
    stdout_buf = StringIO()
    stderr_buf = StringIO()
    with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
        result = _check_level(level, 0, out_dir)
    return stdout_buf.getvalue(), stderr_buf.getvalue(), result


def _write_index_html(results: list[dict], out_dir: Path) -> None:
    """Write a summary table of all processed levels to index.html."""
    rows = []
    for r in results:
        lvl = r["level"]
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
            f"  <tr><td>{level_cell}</td><td>{multi}</td>"
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
        "td:nth-child(4){text-align:right;font-variant-numeric:tabular-nums}\n"
        "</style>\n"
        "</head>\n<body>\n"
        "<input id=\"filter\" type=\"search\" placeholder=\"Filter\u2026\""
        " style=\"margin-bottom:8px;padding:4px 8px;font-size:14px;"
        "border:1px solid #ccc;border-radius:4px;width:300px\">\n"
        "<table>\n"
        "<thead><tr><th>Level</th><th>Multi</th><th>Created by</th><th>Runtime</th><th>Rules used</th></tr></thead>\n"
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
        "      if(col===0||col===3){\n"
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


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="chk_stepwise",
        description="Run the stepwise solver over community levels and write HTML output.",
    )
    parser.add_argument("--first",   type=int,   default=1,   metavar="N", help="First level (default: 1)")
    parser.add_argument("--last",    type=int,   default=10,  metavar="N", help="Last level (default: 10)")
    parser.add_argument("--workers", type=int,   default=8,   metavar="N", help="Worker processes (default: 8)")
    parser.add_argument("--rate",    type=float, default=2.0, metavar="R", help="Submissions per second; 0=unlimited (default: 2)")
    args = parser.parse_args()
    first, last, workers, rate = args.first, args.last, args.workers, args.rate

    if first > last:
        p_stderr(f"Error: FIRST ({first}) > LAST ({last})")
        sys.exit(1)

    out_dir = Path("all_solutions")
    out_dir.mkdir(exist_ok=True)

    min_gap = 1.0 / rate if rate > 0 else 0.0

    with Pool(workers) as pool:
        futures_by_level: dict[int, object] = {}
        buffered: dict[int, tuple[str, str, dict]] = {}
        results: list[dict] = []
        next_to_print = first
        levels = list(range(first, last + 1))
        submit_idx = 0
        next_submit_time = time.monotonic()

        while next_to_print <= last:
            now = time.monotonic()

            # Submit the next level if the rate window has elapsed.
            if submit_idx < len(levels) and now >= next_submit_time:
                level = levels[submit_idx]
                futures_by_level[level] = pool.apply_async(_worker, ((level, out_dir),))
                submit_idx += 1
                next_submit_time = now + min_gap

            # Collect any newly completed futures.
            for level, future in list(futures_by_level.items()):
                if future.ready():
                    buffered[level] = future.get()
                    del futures_by_level[level]

            # Flush consecutive completed levels in order.
            while next_to_print in buffered:
                stdout_text, stderr_text, result = buffered.pop(next_to_print)
                sys.stdout.write(stdout_text)
                sys.stdout.flush()
                if stderr_text:
                    sys.stderr.write(stderr_text)
                    sys.stderr.flush()
                results.append(result)
                next_to_print += 1

            if next_to_print <= last:
                time.sleep(0.05)

    _write_index_html(results, out_dir)


if __name__ == "__main__":
    main()
