"""Tests for color-based grid recognition against the example images in ./img."""

import sys
import os
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from nqueens_recog.grid_reader import Grid, Tile, read_grid
from nqueens_recog.palette import PALETTE, hex_to_rgb, nearest_letter, grid_to_letters
from nqueens_recog.url_reader import is_community_level_url, read_community_level, _parse_color_regions

IMG_DIR = Path(__file__).parent.parent / "img"
PUZZLE_687   = IMG_DIR / "puzzle-687.png"
PUZZLE_589   = IMG_DIR / "puzzle-589.png"
PUZZLE_657   = IMG_DIR / "puzzle-657-bad-cropping.png"

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
# Disable annoying spell checker in the expected letter grid
# cspell: disable

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


def test_puzzle_589_letter_map():
    grid = read_grid(str(PUZZLE_589))
    result = grid_to_letters(grid)
    expected = [
        "EEEEIIIJJJJ",
        "EIIAKKKFIII",
        "AAAAAIIFFJJ",
        "IIIAKKKFIII",
        "IIIAKKKKIII",
        "IIKKKKKDKKI",
        "CCCCIDDDDHB",
        "HHHCKKKHHHB",
        "HHHIKKKDHHB",
        "GHHIKKKDIHB",
        "GGGGIIIDIBB",
    ]
    assert result == expected


def test_puzzle_657_letter_map():
    """18x18 puzzle with UI chrome above and below the grid."""
    grid = read_grid(str(PUZZLE_657))
    result = grid_to_letters(grid)
    expected = [
        "OONKKKKKKKKKKKKKOO",
        "ONNNKKKKKKKKKKKKKO",
        "KKNKKQQQQQQQQKKKKK",
        "KKKKQLLLLGLLLQKKKK",
        "KKKQLLLFLLJLGLQKKK",
        "KKQLLLILLLLLLHLQKK",
        "KKQALLLLRRLJLLLQKK",
        "KKQLBLLRRRRLLLLQKP",
        "KKQLLLRRRRRRLDLQKP",
        "KKQLLLRRRRRRLLLQKK",
        "KKQLLCLRRRRLLLLQKK",
        "KKQLLLLLRRLLLLBQKK",
        "KKQLDLLLHLLGLLLQKK",
        "KKKQLCLGLLALLLQKKK",
        "KKKKQLLLILLFLQKKKK",
        "KKKKKQQQQQQQQKKKEO",
        "OKMMKKKKKKKKKKKEEE",
        "OOOMKKKKKKKKKKKOEO",
    ]
    assert result == expected

# cspell: enable


# ---------------------------------------------------------------------------
# url_reader: unit tests (no network required)
# ---------------------------------------------------------------------------

_MINIMAL_TS = """\
import {{ turquoiseBlue }} from "../colors";

const level = {{
  path: "/community-level/1",
  size: 3,
  colorRegions: [
    ["A", "A", "B"],
    ["A", "C", "B"],
    ["C", "C", "B"],
  ],
  regionColors: {{
    A: turquoiseBlue,
  }},
  solutionsCount: 1,
}};

export default level;
"""


class TestIsCommunityLevelUrl:
    def test_valid(self):
        assert is_community_level_url(
            "https://queensgame.vercel.app/community-level/657"
        )

    def test_valid_http(self):
        assert is_community_level_url(
            "http://queensgame.vercel.app/community-level/1"
        )

    def test_rejects_image_path(self):
        assert not is_community_level_url("img/puzzle-687.png")

    def test_rejects_other_url(self):
        assert not is_community_level_url("https://example.com/community-level/1")


class TestParseColorRegions:
    def test_returns_correct_shape(self):
        rows = _parse_color_regions(_MINIMAL_TS, "1")
        assert len(rows) == 3
        assert all(len(r) == 3 for r in rows)

    def test_returns_correct_letters(self):
        rows = _parse_color_regions(_MINIMAL_TS, "1")
        assert rows[0] == ["A", "A", "B"]
        assert rows[1] == ["A", "C", "B"]
        assert rows[2] == ["C", "C", "B"]

    def test_raises_on_missing_size(self):
        bad = _MINIMAL_TS.replace("size: 3,", "")
        with pytest.raises(ValueError, match="size"):
            _parse_color_regions(bad, "1")

    def test_raises_on_missing_block(self):
        bad = _MINIMAL_TS.replace("colorRegions", "gridData")
        with pytest.raises(ValueError, match="colorRegions"):
            _parse_color_regions(bad, "1")

    def test_raises_on_wrong_cell_count(self):
        bad = _MINIMAL_TS.replace('size: 3,', 'size: 4,')
        with pytest.raises(ValueError, match="expected"):
            _parse_color_regions(bad, "1")


# ---------------------------------------------------------------------------
# Cross-validation: image recognition vs. authoritative URL data
# Run with:  pytest --network
# ---------------------------------------------------------------------------

_COMMUNITY_LEVELS = {
    "589": PUZZLE_589,
    "657": PUZZLE_657,
    "687": PUZZLE_687,
}


@pytest.mark.network
@pytest.mark.parametrize("level_id,image_path", _COMMUNITY_LEVELS.items())
def test_image_matches_community_level(level_id: str, image_path: Path) -> None:
    """Image recognition output must exactly match the authoritative level data."""
    url = f"https://queensgame.vercel.app/community-level/{level_id}"
    url_rows = read_community_level(url)
    expected = ["".join(r) for r in url_rows]

    img_rows = grid_to_letters(read_grid(str(image_path)))

    assert img_rows == expected, (
        f"Level {level_id}: image recognition differs from community-level data.\n"
        + "\n".join(
            f"  row {i}: img={img!r}  url={url_r!r}"
            for i, (img, url_r) in enumerate(zip(img_rows, expected))
            if img != url_r
        )
    )