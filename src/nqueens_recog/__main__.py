"""Entry point: read a grid image and print it."""

import sys

from .grid_reader import Grid, read_grid
from .palette import grid_to_letters


def print_grid(grid: Grid) -> None:
    """Print the grid as a table of palette letters (lowercase = unknown colour)."""
    for row in grid_to_letters(grid):
        print(" ".join(row))


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: nqueens-recog <image_path>")
        sys.exit(1)
    grid = read_grid(sys.argv[1])
    print(f"Grid: {grid.rows} × {grid.cols}, {grid.rows} colours")
    print_grid(grid)


if __name__ == "__main__":
    main()
