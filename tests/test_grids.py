"""Tests for color-based grid recognition against the example images in ./img."""

import sys
import os
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from nqueens_recog.grid_reader import Grid, Tile, read_grid
from nqueens_recog.palette import PALETTE, hex_to_rgb, nearest_letter, grid_to_letters

IMG_DIR = Path(__file__).parent.parent / "img"
PUZZLE_687   = IMG_DIR / "puzzle-687.png"

# ---------------------------------------------------------------------------
# Colour palette and matching helpers are imported from nqueens_recog.palette.
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _valid_rgb(color: tuple) -> bool:
    return len(color) == 3 and all(0 <= v <= 255 for v in color)


# ---------------------------------------------------------------------------
# puzzle-687.png
# ---------------------------------------------------------------------------

class TestPuzzle687:
    @pytest.fixture(scope="class")
    def grid(self):
        return read_grid(str(PUZZLE_687))

    def test_returns_grid(self, grid):
        assert isinstance(grid, Grid)

    def test_is_square(self, grid):
        assert grid.rows == grid.cols

    def test_n_distinct_colors(self, grid):
        n = grid.rows
        colors = {t.color_rgb for row in grid.tiles for t in row}
        assert len(colors) == n, f"Expected {n} distinct colors, got {len(colors)}"

    def test_tile_colors_valid(self, grid):
        for row in grid.tiles:
            for tile in row:
                assert _valid_rgb(tile.color_rgb), (
                    f"Invalid RGB at ({tile.row},{tile.col}): {tile.color_rgb}"
                )

    def test_no_letters(self, grid):
        for row in grid.tiles:
            for tile in row:
                assert tile.letter is None

    def test_tile_coordinates(self, grid):
        for r, row in enumerate(grid.tiles):
            for c, tile in enumerate(row):
                assert tile.row == r
                assert tile.col == c

    def test_indexing(self, grid):
        assert grid[0, 0] is grid.tiles[0][0]
        assert grid[grid.rows - 1, grid.cols - 1] is grid.tiles[-1][-1]

    def test_color_grid_shape(self, grid):
        cg = grid.color_grid()
        assert len(cg) == grid.rows
        assert all(len(row) == grid.cols for row in cg)
        assert all(_valid_rgb(c) for row in cg for c in row)

    def test_color_index_grid(self, grid):
        cig = grid.color_index_grid()
        n = grid.rows
        assert len(cig) == n
        assert all(len(row) == n for row in cig)
        assert all(0 <= v < n for row in cig for v in row)


# ---------------------------------------------------------------------------
# Expected letter grid for puzzle-687.png  (standard test image)
# Uses the default game palette; colours mapped via nearest-RGB matching.
# Correct the rows below if the colour assignments need adjusting.
# ---------------------------------------------------------------------------

def test_puzzle_687_letter_map():
    grid = read_grid(str(PUZZLE_687))
    result = grid_to_letters(grid)
    expected = [
        "EBBEEELOOOLEEGEEE",
        "BBBBEOOJAJOEPEEEE",
        "BBBBOIAAFAAOEEEEE",
        "EBBLOADCCCDOOLEEG",
        "EGEOOACCCCCAJOEEE",
        "EEOOADFCQCFDAOOEE",
        "EEGOJACCCCCAJOEGE",
        "EEELOAICCCCIOLEEE",
        "GEEEOPAAQADAOEEEE",
        "EEEEEOOJAJOOPEEEE",
        "HEEEEELOQOLEEEEEE",
        "HHHHHEHEFEEEHEHHE",
        "HHNNNNNHQHHHHHNNN",
        "NNMMNNMNNNNNNHNMM",
        "NMMMMMMMQMMNNNMMM",
        "MMMKMMMMMMMMKMMMM",
        "KMMKKKMMQMKMKKMMM",
    ]
    assert result == expected

