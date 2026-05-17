"""Entry point: read a grid image and print it."""

import sys

from .grid_reader import Grid, read_grid


def print_grid(grid: Grid) -> None:
    """Print the grid as a table of colour indices (0 … n-1)."""
    palette = sorted({t.color_rgb for row in grid.tiles for t in row})
    idx = {c: i for i, c in enumerate(palette)}
    width = len(str(len(palette) - 1))
    for row in grid.tiles:
        print(" ".join(f"{idx[t.color_rgb]:{width}d}" for t in row))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m nqueens_recog <image_path>")
        sys.exit(1)
    grid = read_grid(sys.argv[1])
    print(f"Grid: {grid.rows} × {grid.cols}, {grid.rows} colours")
    print_grid(grid)
