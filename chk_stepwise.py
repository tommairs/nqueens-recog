#!/usr/bin/env python3
"""Check stepwise solver against recursive solver for community levels.

Usage:
    python chk_stepwise.py [FIRST [LAST [DELAY]]]

Defaults: FIRST=1, LAST=10, DELAY=1 (seconds between requests).
Set DELAY=0 to disable.

For each level in [FIRST, LAST]:
  - Fetch the board from the queensgame GitHub source.
  - Run the recursive solver (quiet) to count solutions.
  - If the level has exactly one solution:
      - Run the stepwise solver and capture its trace.
      - Compare results; print a warning on stderr if they diverge.
      - Report which deduction rules the stepwise solver used.
      - Write all_solutions/level_<N>.html via aha.
"""

import subprocess
import sys
import time
import urllib.error
from io import StringIO
from pathlib import Path

# ---------------------------------------------------------------------------
# Imports from the installed package (run from project root with venv active)
# ---------------------------------------------------------------------------
from nqueens_recog.solver import solve
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


def _solution_as_row_col(solution: list[tuple[int, int]]) -> dict[int, int]:
    """Convert a recursive-solver solution (list of (col, row)) to {row: col}."""
    return {row: col for col, row in solution}


def _rules_used(trace: str) -> list[str]:
    """Return the names of rules that fired, in definition order."""
    return [name for name, marker in RULE_MARKERS if marker in trace]


def _write_html(level: int, url: str, out_dir: Path) -> None:
    """Run nqueens-recog --stepwise --verbose | aha and write the HTML file."""
    out_path = out_dir / f"level_{level}.html"
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
            ["aha"],
            input=proc1.stdout, capture_output=True, text=True, check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        p_stderr(f"  [HTML] aha failed: {exc}")
        return

    html = proc2.stdout.replace("</head>", f"{STYLE}</head>", 1)
    out_path.write_text(html, encoding="utf-8")
    print(f"  Written: {out_path}")


def _check_level(level: int, delay: float, out_dir: Path) -> None:
    url = BASE_URL.format(n=level)
    print(f"=== Level {level} ===")

    # --- Fetch (board + solutionsCount from TypeScript source) ---
    try:
        board, solutions_count = read_community_level_info(url)
    except ValueError:
        print("  Skip: could not parse level source")
        return
    except RuntimeError as exc:
        msg = str(exc)
        if "404" in msg or "Not Found" in msg:
            print("  Skip: level not found (404)")
        else:
            print(f"  Skip: fetch error — {exc}")
        return

    n = len(board)
    print(f"  Board: {n}×{n}, solutionsCount={solutions_count}")

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

    if not unique:
        # Multi-solution level: validate and report, but skip recursive cross-check.
        if step_result is None:
            p_stderr(f"  Stepwise: stuck (returned None) [stepwise {step_elapsed:.3f}s]")
        else:
            errors = _validate(board, step_result)
            if errors:
                p_stderr(f"!! INVALID solution level {level}: {'; '.join(errors)}")
            else:
                print(f"  Stepwise: ok (multi-solution) [stepwise {step_elapsed:.3f}s]"
                      f" — rules used: {', '.join(rules) if rules else '(none)'}")
    else:
        # --- Recursive solver ---
        t0 = time.perf_counter()
        rec_solutions = solve(board, quiet=True, verbose=False, max_solutions=1)
        rec_elapsed = time.perf_counter() - t0

        timing = f"stepwise {step_elapsed:.3f}s, recursive {rec_elapsed:.3f}s"

        # --- Compare / validate ---
        if step_result is None:
            p_stderr(f"  Stepwise: stuck (returned None) [{timing}]")
        else:
            errors = _validate(board, step_result)
            if errors:
                p_stderr(f"!! INVALID solution level {level}: {'; '.join(errors)}")
            elif not rec_solutions:
                p_stderr(f"!! RECURSIVE found no solution for level {level}")
            else:
                rec_result = _solution_as_row_col(rec_solutions[0])
                if step_result != rec_result:
                    p_stderr(
                        f"!! DIVERGE level {level}: "
                        f"recursive={rec_result} stepwise={step_result}",
                    )
                else:
                    print(f"  Stepwise: ok [{timing}] — rules used: {', '.join(rules) if rules else '(none)'}")

    # --- Write HTML ---
    _write_html(level, url, out_dir)

    if delay > 0:
        time.sleep(delay)


def main() -> None:
    args = sys.argv[1:]
    try:
        first = int(args[0]) if len(args) >= 1 else 1
        last  = int(args[1]) if len(args) >= 2 else 10
        delay = float(args[2]) if len(args) >= 3 else 1.0
    except ValueError:
        p_stderr(f"Usage: {sys.argv[0]} [FIRST [LAST [DELAY]]]")
        sys.exit(1)

    if first > last:
        p_stderr(f"Error: FIRST ({first}) > LAST ({last})")
        sys.exit(1)

    out_dir = Path("all_solutions")
    out_dir.mkdir(exist_ok=True)

    for level in range(first, last + 1):
        _check_level(level, delay, out_dir)


if __name__ == "__main__":
    main()
