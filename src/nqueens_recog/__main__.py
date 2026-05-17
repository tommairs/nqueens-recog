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
    args = parser.parse_args()

    if is_community_level_url(args.input):
        board = read_community_level(args.input)
    else:
        board = [list(row) for row in grid_to_letters(read_grid(args.input))]

    size = len(board)
    print(f"Grid: {size} × {size}, {size} colours")
    for row in board:
        print(" ".join(row))

    if args.solve:
        from .solver import solve
        print("\nSolving ...")
        solutions = solve(board)
        print(f"Total solutions found: {len(solutions)}")


if __name__ == "__main__":
    main()
