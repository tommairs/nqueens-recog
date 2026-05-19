#!/usr/bin/env python3
"""Batch-solve all community levels and write results as JSON.

Usage (with the project venv active):
    python solve_all.py [--first N] [--last N] [--delay S] [--output PATH]

Output format (all_solutions/solutions.json by default):

    [
      {
        "level": 1,
        "solution_count": 1,
        "solutions": [[3, 1, 4, 2]]
      },
      ...
    ]

Each element of "solutions" is a list of 1-based column numbers,
one per row from top to bottom.  Levels that cannot be fetched are
skipped and reported on stderr.
"""

import argparse
import json
import sys
import time
from pathlib import Path

from nqueens_recog.url_reader import read_community_level
from nqueens_recog.solver import solve


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Batch-solve queensgame community levels and output JSON.",
    )
    parser.add_argument("--first", type=int, default=1, metavar="N",
                        help="First level number (default: 1)")
    parser.add_argument("--last", type=int, default=692, metavar="N",
                        help="Last level number (default: 692)")
    parser.add_argument("--delay", type=float, default=1.0, metavar="S",
                        help="Seconds to sleep between requests (default: 1.0)")
    parser.add_argument("--output", default="all_solutions/solutions.json",
                        metavar="PATH",
                        help="Output file (default: all_solutions/solutions.json)")
    args = parser.parse_args()

    results: list[dict] = []

    for n in range(args.first, args.last + 1):
        url = f"https://queensgame.vercel.app/community-level/{n}"
        try:
            board = read_community_level(url)
        except (ValueError, RuntimeError) as exc:
            print(f"Level {n}: skipping ({exc})", file=sys.stderr)
            time.sleep(args.delay)
            continue

        solutions = solve(board, quiet=True)
        solution_columns = [
            [x + 1 for x, _y in queens]
            for queens in solutions
        ]
        results.append({
            "level": n,
            "solution_count": len(solutions),
            "solutions": solution_columns,
        })
        print(f"Level {n}: {len(solutions)} solution(s)", file=sys.stderr)
        time.sleep(args.delay)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2)
    print(f"Done. {len(results)} levels written to {output_path}.", file=sys.stderr)


if __name__ == "__main__":
    main()
