"""Entry point: read a grid from an image file or a community-level URL."""

import sys

from .grid_reader import Grid, read_grid
from .palette import grid_to_letters
from .url_reader import is_community_level_url, read_community_level


def _print_image_grid(grid: Grid) -> None:
    for row in grid_to_letters(grid):
        print(" ".join(row))


def _print_letter_grid(rows: list[list[str]]) -> None:
    for row in rows:
        print(" ".join(row))


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: nqueens-recog <image_path | community_level_url>")
        sys.exit(1)

    arg = sys.argv[1]
    if is_community_level_url(arg):
        rows = read_community_level(arg)
        size = len(rows)
        print(f"Grid: {size} × {size}, {size} colours")
        _print_letter_grid(rows)
    else:
        grid = read_grid(arg)
        print(f"Grid: {grid.rows} × {grid.cols}, {grid.rows} colours")
        _print_image_grid(grid)


if __name__ == "__main__":
    main()
