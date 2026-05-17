"""Entry point: read a grid from an image file or a community-level URL."""

import argparse
import sys

from .grid_reader import read_grid
from .palette import grid_to_letters
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
    parser.add_argument(
        "--solve",
        action="store_true",
        help="Solve the puzzle and print the solution board.",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show the letter grid and coloured board in addition to the solution line.",
    )
    args = parser.parse_args()

    if is_community_level_url(args.input):
        try:
            board = read_community_level(args.input)
        except (ValueError, RuntimeError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)
    else:
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

    print(f"Grid: {size} × {size}, {size} colours")
    if args.verbose:
        from .display import print_board
        print_board(board)

    if args.solve:
        from .solver import solve
        solutions = solve(board, verbose=args.verbose)
        print(f"Total solutions found: {len(solutions)}")


if __name__ == "__main__":
    main()
