"""Entry point: read a grid from an image file or a community-level URL."""

import argparse
import sys

from .url_reader import is_community_level_url, read_community_level


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="nqueens-recog",
        description="Recognise an N-Queens puzzle grid and optionally solve it.",
    )
    parser.add_argument(
        "input",
        metavar="IMAGE_OR_URL",
        help="Path to a puzzle screenshot, or a queensgame community-level URL.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--solve",
        action="store_true",
        help="Solve the puzzle and print the solution board.",
    )
    mode.add_argument(
        "--stepwise",
        action="store_true",
        help="Apply human-like elimination rules step by step, printing a trace.",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show the letter grid and coloured board in addition to the solution line.",
    )
    parser.add_argument(
        "--timestamps",
        action="store_true",
        help="Prefix stepwise trace lines with elapsed time (e.g. 20.1s: ...).",
    )
    parser.add_argument(
        "--x-wing-max",
        type=int,
        default=6,
        help="Maximum X-Wing group size to scan (default: 6).",
    )
    parser.add_argument(
        "--lookahead-max-cands",
        type=int,
        default=None,
        metavar="N",
        help=(
            "If set, lookahead only evaluates colours with at most N active "
            "candidates and applies all such lookahead eliminations in one pass."
        ),
    )
    args = parser.parse_args()
    if args.x_wing_max < 2:
        print("Error: --x-wing-max must be >= 2", file=sys.stderr)
        sys.exit(1)
    if args.lookahead_max_cands is not None and args.lookahead_max_cands < 1:
        print("Error: --lookahead-max-cands must be >= 1", file=sys.stderr)
        sys.exit(1)

    if is_community_level_url(args.input):
        try:
            board = read_community_level(args.input)
        except (ValueError, RuntimeError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)
    else:
        from .grid_reader import read_grid
        from .palette import grid_to_letters
        board = [list(row) for row in grid_to_letters(read_grid(args.input))]

    # Check board validity before attempting to solve.
    size = len(board)
    col_counts = {len(row) for row in board}
    if col_counts != {size}:
        print(f"Error: board is not square ({size} rows, column counts: {sorted(col_counts)})", file=sys.stderr)
        sys.exit(1)
    n_colours = len({cell for row in board for cell in row})
    if n_colours != size:
        print(f"Error: expected {size} distinct colours for a {size}×{size} board, found {n_colours}", file=sys.stderr)
        sys.exit(1)

    from .stepwise import row_col_str
    print(f"Grid: {size} × {size}, {size} colours. Top left is shown as {row_col_str(0,0)}")
    if args.verbose:
        from .display import print_board
        print_board(board)

    if args.solve:
        import time
        from .solver import solve
        t0 = time.monotonic()
        solutions = solve(board, verbose=args.verbose)
        elapsed = time.monotonic() - t0
        print(f"Total solutions found: {len(solutions)}  ({elapsed:.1f}s)")

    if args.stepwise:
        from .stepwise import solve_stepwise
        solve_stepwise(
            board,
            verbose=args.verbose,
            timestamps=args.timestamps,
            x_wing_max=args.x_wing_max,
            lookahead_max_cands=args.lookahead_max_cands,
        )


if __name__ == "__main__":
    main()
