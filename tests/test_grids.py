"""Tests for color-based grid recognition against the example images in ./img."""

import sys
import os
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from nqueens_recog.grid_reader import Grid, Tile, read_grid

IMG_DIR = Path(__file__).parent.parent / "img"
WITH_LETTERS = IMG_DIR / "grid-with-letters.png"
NO_LETTERS = IMG_DIR / "grid-no-letters.png"

# ---------------------------------------------------------------------------
# Colour palette – queensgame.vercel.app defaults (settings/palette)
# Letters assigned alphabetically by colour name.
# ---------------------------------------------------------------------------

PALETTE: list[tuple[str, tuple[int, int, int]]] = [
    ("A", (0xC0, 0x6C, 0x84)),  # Atomic Tangerine
    ("B", (0x32, 0x87, 0xBD)),  # Boston Blue
    ("C", (0x5E, 0x4F, 0xA2)),  # Butterfly Bush
    ("D", (0x66, 0x5B, 0x82)),  # Cold Purple
    ("E", (0x4B, 0x6B, 0x5F)),  # Emerald
    ("F", (0x8E, 0x6E, 0x8E)),  # Heather Purple
    ("G", (0xF5, 0x6D, 0x43)),  # Jaffa
    ("H", (0xFD, 0xAE, 0x61)),  # Koromiko
    ("I", (0x60, 0x7D, 0x3B)),  # Light Green
    ("J", (0xA6, 0x7A, 0x50)),  # Mac N Cheese
    ("K", (0xAC, 0xDD, 0xA5)),  # Moss Green
    ("L", (0x46, 0x7A, 0x7D)),  # Ocean Muted
    ("M", (0x4A, 0x5A, 0x77)),  # Periwinkle
    ("N", (0xE6, 0xF5, 0x98)),  # Sandwisp
    ("O", (0x6C, 0x7A, 0x89)),  # Slate Dark
    ("P", (0x8E, 0x88, 0x75)),  # Stone
    ("Q", (0x65, 0xC2, 0xA5)),  # Tradewind
    ("R", (0xD5, 0x3E, 0x4F)),  # Valencia
    ("S", (0xFF, 0xFF, 0xFF)),  # White
]


def _nearest_letter(rgb: tuple[int, int, int]) -> str:
    """Return the palette letter whose colour is closest (by squared RGB distance) to *rgb*."""
    return min(PALETTE, key=lambda kv: sum((a - b) ** 2 for a, b in zip(kv[1], rgb)))[0]


def _grid_to_letters(grid: Grid) -> list[str]:
    """Convert a Grid to rows of palette letters."""
    return [
        "".join(_nearest_letter(t.color_rgb) for t in row)
        for row in grid.tiles
    ]



# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _valid_rgb(color: tuple) -> bool:
    return len(color) == 3 and all(0 <= v <= 255 for v in color)


# ---------------------------------------------------------------------------
# grid-no-letters.png
# ---------------------------------------------------------------------------

class TestGridNoLetters:
    @pytest.fixture(scope="class")
    def grid(self):
        return read_grid(str(NO_LETTERS))

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
# grid-with-letters.png  (skipped when the image is absent)
# ---------------------------------------------------------------------------

class TestGridWithLetters:
    @pytest.fixture(scope="class")
    def grid(self):
        if not WITH_LETTERS.exists():
            pytest.skip("grid-with-letters.png not available")
        return read_grid(str(WITH_LETTERS))

    def test_returns_grid(self, grid):
        assert isinstance(grid, Grid)

    def test_is_square(self, grid):
        assert grid.rows == grid.cols

    def test_n_distinct_colors(self, grid):
        n = grid.rows
        colors = {t.color_rgb for row in grid.tiles for t in row}
        assert len(colors) == n

    def test_tile_colors_valid(self, grid):
        for row in grid.tiles:
            for tile in row:
                assert _valid_rgb(tile.color_rgb)


# ---------------------------------------------------------------------------
# Expected letter grid for grid-no-letters.png
# Colours mapped to palette letters via nearest-RGB matching.
# Correct the rows below if the colour assignments need adjusting.
# ---------------------------------------------------------------------------

def test_grid_no_letters_letter_map():
    grid = read_grid(str(NO_LETTERS))
    result = _grid_to_letters(grid)
    expected = [
        "OHHOOOAMMMAOONOOO",
        "HHHHOMMQCQMODOOOO",
        "HHHHMGCCRCCMOOOOO",
        "OHHAMCKBBBKMMAOON",
        "ONOMMCBBBBBCQMOOO",
        "OOMMCKRBSBRKCMMOO",
        "OONMQCBBBBBCQMONO",
        "OOOAMCGBBBBGMAOOO",
        "NOOOMDCCSCKCMOOOO",
        "OOOOOMMQCQMMDOOOO",
        "POOOOOAMSMAOOOOOO",
        "PPPPPOPOROOOPOPPO",
        "PPEEEEEPSPPPPPEEE",
        "EEIIEEIEEEEEEPEII",
        "EIIIIIIISIIEEEIII",
        "IIILIIIIIIIILIIII",
        "LIILLLIISILILLIII",
    ]
    assert result == expected

