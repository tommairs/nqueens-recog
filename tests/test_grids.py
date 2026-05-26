"""Tests for color-based grid recognition against the example images in ./img."""

import sys
import os
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from nqueens_recog.display import print_board
from nqueens_recog.grid_reader import Grid, Tile, read_grid
from nqueens_recog.__main__ import main
from nqueens_recog.palette import PALETTE, hex_to_rgb, nearest_letter, grid_to_letters
from nqueens_recog.url_reader import is_community_level_url, read_community_level, _parse_color_regions
from nqueens_recog.solver import solve
from nqueens_recog.stepwise import solve_stepwise

IMG_DIR = Path(__file__).parent.parent / "img"
PUZZLE_687   = IMG_DIR / "puzzle-687.png"
PUZZLE_589   = IMG_DIR / "puzzle-589.png"
PUZZLE_657   = IMG_DIR / "puzzle-657-bad-cropping.png"

# ---------------------------------------------------------------------------
# puzzle-687.png — Grid method tests
# ---------------------------------------------------------------------------

class TestPuzzle687:
    @pytest.fixture(scope="class")
    def grid(self):
        return read_grid(str(PUZZLE_687))

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


# ---------------------------------------------------------------------------
# Solver: each puzzle must have exactly one solution
# Board is built from local image recognition (no network required).
# ---------------------------------------------------------------------------

@pytest.mark.slow
@pytest.mark.parametrize("image_path,label,expected_cols", [
    (PUZZLE_589, "589", [10, 1, 5, 8, 6, 2, 7, 4, 9, 11, 3]),
    (PUZZLE_687, "687", [14, 3, 6, 4, 12, 7, 5, 8, 11, 13, 10, 17, 2, 15, 9, 16, 1]),
    (PUZZLE_657, "657", [16, 2, 13, 10, 8, 14, 12, 18, 7, 4, 6, 15, 5, 11, 9, 17, 3, 1]),
])
def test_solver_finds_one_solution(image_path: Path, label: str, expected_cols: list[int]) -> None:
    """Solver must find exactly one solution for each sample puzzle."""
    board = [list(row) for row in grid_to_letters(read_grid(str(image_path)))]
    solutions = solve(board)
    assert len(solutions) == 1, (
        f"Puzzle {label}: expected 1 solution, got {len(solutions)}"
    )
    cols = [x + 1 for x, _ in solutions[0]]
    assert cols == expected_cols, (
        f"Puzzle {label}: solution {cols} != expected {expected_cols}"
    )


# ---------------------------------------------------------------------------
# Stepwise solver helpers
# ---------------------------------------------------------------------------

def _assert_matches_solver(board: list[list[str]], stepwise_result: dict[int, int] | None) -> None:
    """Cross-validate: stepwise result must agree with the unique exhaustive solution."""
    solutions = solve(board, quiet=True)
    if len(solutions) != 1:
        return  # only cross-validate when there is exactly one solution
    expected = {y: x for x, y in solutions[0]}
    assert stepwise_result == expected, (
        f"stepwise={stepwise_result} != solver={expected}"
    )


# ---------------------------------------------------------------------------
# Stepwise solver: X-Wing rule
# ---------------------------------------------------------------------------

def test_stepwise_x_wing_fires(capsys) -> None:
    """{A,B} cells are confined to row-0 ∪ col-0, forcing rule_x_wing to fire.

    A candidates: (0,0), (0,1), (1,0)  — not in row 0 ⟹ col 0
    B candidates: (0,2), (0,3), (2,0)  — not in row 0 ⟹ col 0
    X-Wing (c=2, a=1, b=1): row {0} ∪ col {0} covers all {A,B} cells.
    Expected eliminations: C(3,0) [non-group in col 0] + A(0,0) [intersection].
    """
    board = [
        ["A", "A", "B", "B"],
        ["A", "C", "C", "C"],
        ["B", "D", "D", "D"],
        ["C", "C", "D", "D"],
    ]
    result = solve_stepwise(board)
    assert result is not None
    _assert_matches_solver(board, result)
    assert "x-wing:" in capsys.readouterr().out


def test_stepwise_singleton_paths_and_stuck(capsys) -> None:
    """Region singleton, squeeze, row singleton, and the stuck path.

    A has exactly one cell → region singleton fires first.  Placing A(0,0)
    eliminates all of B's candidates (row 0 + diagonal), leaving no valid
    solution.  Before search gives up the trace visits:
      region singleton → A(0,0)
      squeeze          → row 1 (cols 2–3) eliminates in adjacent rows
      row singleton    → D placed (only candidate remaining in row 2)
      row singleton    → C placed (only candidate remaining in row 3)
      search exhausted → solve_stepwise returns None  (stuck path)
    """
    board = [
        ["A", "B", "B", "B"],
        ["C", "B", "C", "C"],
        ["C", "D", "D", "C"],
        ["C", "D", "D", "C"],
    ]
    result = solve_stepwise(board)
    out = capsys.readouterr().out
    assert result is None                   # stuck path → return None
    assert "region singleton" in out        # rule_singleton region branch
    assert "squeeze:" in out               # rule_squeeze fires
    assert "row 2 singleton" in out        # rule_singleton row branch
    assert "row 3 singleton" in out        # rule_singleton row branch


# ---------------------------------------------------------------------------
# Stepwise solver: community levels (boards embedded; no network at test time)
# ---------------------------------------------------------------------------

def test_stepwise_ngroup_colour_perspective(capsys) -> None:
    """Community level 150 (7×7): shadow and forced row/col solve without backtracking.

    shadow eliminates candidates for B, C, E before forced col fires for D and B.
    Board is fully solvable by deduction alone.
    Source: https://queensgame.vercel.app/community-level/150
    """
    board = [
        ["A", "A", "C", "C", "A", "A", "F"],
        ["A", "D", "D", "C", "A", "F", "F"],
        ["A", "D", "C", "C", "A", "A", "F"],
        ["G", "A", "C", "A", "A", "A", "A"],
        ["G", "A", "C", "E", "E", "B", "B"],
        ["G", "A", "A", "A", "E", "A", "B"],
        ["G", "G", "G", "A", "A", "A", "A"],
    ]
    result = solve_stepwise(board)
    out = capsys.readouterr().out
    assert result is not None
    _assert_matches_solver(board, result)
    assert "shadow:" in out             # rule_shadow fires
    assert "confined to col" in out     # rule_forced_row_col col branch


def test_stepwise_forced_ngroup_col_lookahead(capsys) -> None:
    """Community level 113 (7×7): forced row/col, n-group col line, and lookahead all fire.

    After A is placed as region singleton:
      forced row  → B confined to row 1, D confined to row 2
      n-group col → cols {6} exclusive to E; cols {5} exclusive to F
      forced col  → C confined to col 1
      lookahead   → G(4,3) contradicts after propagation → eliminated
    Source: https://queensgame.vercel.app/community-level/113
    """
    board = [
        ["A", "B", "B", "B", "D", "E", "E"],
        ["C", "B", "B", "B", "D", "F", "E"],
        ["C", "D", "D", "D", "D", "F", "E"],
        ["C", "C", "C", "G", "F", "F", "E"],
        ["C", "C", "C", "G", "E", "F", "E"],
        ["C", "G", "G", "G", "E", "F", "E"],
        ["C", "G", "G", "G", "E", "E", "E"],
    ]
    result = solve_stepwise(board)
    out = capsys.readouterr().out
    assert result is not None
    _assert_matches_solver(board, result)
    assert "confined to row" in out     # rule_forced_row_col row branch
    assert "confined to col" in out     # rule_forced_row_col col branch
    assert "n-group: cols" in out       # rule_n_group col line perspective
    assert "lookahead:" in out          # rule_lookahead fires


@pytest.mark.slow
def test_stepwise_colour_perspective_and_lookahead_large(capsys) -> None:
    """Community level 114 (11×11): n-group colour perspective + lookahead on a larger board.

    {B,K} candidates span rows {8,9} → claims those rows.
    {H,J} candidates span cols {0,1} → claims those cols.
    Two H placements eliminated by lookahead before backtracking completes the solve.
    Source: https://queensgame.vercel.app/community-level/114
    """
    board = [
        ["H", "H", "D", "D", "D", "D", "D", "D", "I", "I", "I"],
        ["H", "H", "F", "F", "D", "D", "D", "F", "F", "I", "I"],
        ["H", "F", "G", "G", "F", "D", "F", "G", "G", "F", "I"],
        ["H", "F", "G", "G", "G", "F", "G", "G", "G", "F", "I"],
        ["H", "F", "C", "C", "C", "C", "C", "C", "C", "F", "I"],
        ["H", "H", "F", "C", "C", "C", "C", "C", "F", "I", "A"],
        ["A", "A", "A", "F", "E", "E", "E", "F", "A", "A", "A"],
        ["J", "J", "A", "A", "F", "F", "F", "E", "E", "B", "B"],
        ["G", "K", "K", "K", "K", "F", "B", "B", "B", "B", "G"],
        ["G", "K", "K", "K", "K", "B", "B", "B", "B", "B", "G"],
        ["G", "G", "G", "G", "G", "G", "G", "G", "G", "G", "G"],
    ]
    result = solve_stepwise(board)
    out = capsys.readouterr().out
    assert result is not None
    _assert_matches_solver(board, result)
    assert "claims rows" in out     # rule_n_group colour perspective (rows)
    assert "claims cols" in out     # rule_n_group colour perspective (cols)
    assert "lookahead:" in out      # rule_lookahead fires


@pytest.mark.slow
def test_stepwise_lookahead_10x10(capsys) -> None:
    """Community level 108 (10×10): rule_lookahead fires twice before backtracking solves.

    Two placements (E at (5,1) and H at (5,6)) each lead to a contradiction
    after propagation and are eliminated by lookahead before search takes over.
    Source: https://queensgame.vercel.app/community-level/108
    """
    board = [
        ["E", "D", "D", "D", "D", "C", "A", "A", "A", "A"],
        ["E", "D", "C", "C", "C", "C", "A", "A", "A", "A"],
        ["E", "D", "D", "D", "D", "C", "B", "B", "A", "B"],
        ["E", "E", "E", "E", "D", "D", "B", "B", "A", "B"],
        ["F", "F", "F", "E", "D", "B", "B", "B", "B", "B"],
        ["F", "E", "E", "E", "D", "H", "H", "I", "I", "J"],
        ["F", "E", "F", "F", "F", "H", "H", "I", "I", "J"],
        ["F", "F", "F", "G", "F", "F", "H", "I", "I", "J"],
        ["G", "G", "G", "G", "F", "F", "H", "J", "J", "J"],
        ["H", "H", "H", "H", "H", "H", "H", "J", "J", "J"],
    ]
    result = solve_stepwise(board)
    out = capsys.readouterr().out
    assert result is not None
    _assert_matches_solver(board, result)
    assert "lookahead:" in out      # rule_lookahead fires


def test_stepwise_xwing_with_lookahead(capsys) -> None:
    """Community level 578 (8×8): forced row, n-group colour perspective, x-wing, and lookahead all fire.

    D candidates are confined to row 2 → forced row fires.
    {E,F} candidates span exactly rows {0,1} → n-group claims those rows.
    x-wing fires twice, and lookahead eliminates three A candidates before
    singletons resolve the board without backtracking.
    Source: https://queensgame.vercel.app/community-level/578
    """
    board = [
        ["F", "F", "A", "A", "A", "E", "E", "E"],
        ["F", "A", "A", "C", "A", "A", "A", "E"],
        ["A", "A", "C", "C", "D", "D", "A", "E"],
        ["A", "C", "C", "C", "C", "C", "A", "A"],
        ["A", "A", "B", "B", "C", "C", "C", "A"],
        ["G", "A", "B", "B", "B", "B", "A", "A"],
        ["G", "A", "A", "A", "B", "A", "A", "H"],
        ["G", "G", "G", "A", "A", "A", "H", "H"],
    ]
    result = solve_stepwise(board)
    out = capsys.readouterr().out
    assert result is not None
    _assert_matches_solver(board, result)
    assert "confined to row" in out     # rule_forced_row_col row branch
    assert "claims rows" in out         # rule_n_group colour perspective (rows)
    assert "x-wing:" in out             # rule_x_wing fires
    assert "lookahead:" in out          # rule_lookahead fires


# ---------------------------------------------------------------------------
# Solver unit tests (no images needed)
# ---------------------------------------------------------------------------

class TestSolveUnit:
    # 1×1 board: trivially one solution
    _1x1 = [["A"]]

    # 2×2 board: no solution – diagonal adjacency blocks all placements
    _2x2_nosol = [["A", "B"], ["A", "B"]]

    # 4×4 board with exactly 2 known solutions
    _4x4 = [
        ["A", "A", "B", "B"],
        ["A", "A", "B", "B"],
        ["C", "C", "D", "D"],
        ["C", "C", "D", "D"],
    ]

    def test_1x1_one_solution(self):
        sols = solve(self._1x1, quiet=True)
        assert sols == [[(0, 0)]]

    def test_no_solution(self):
        sols = solve(self._2x2_nosol, quiet=True)
        assert sols == []

    def test_4x4_two_solutions(self):
        sols = solve(self._4x4, quiet=True)
        assert len(sols) == 2
        assert [(1, 0), (3, 1), (0, 2), (2, 3)] in sols
        assert [(2, 0), (0, 1), (3, 2), (1, 3)] in sols

# ---------------------------------------------------------------------------
# display.print_board unit tests
# ---------------------------------------------------------------------------

class TestPrintBoard:
    _board = [["A", "B"], ["C", "D"]]

    def test_no_queens_shows_letters(self, capsys):
        print_board(self._board)
        out = capsys.readouterr().out
        assert "A" in out and "B" in out

    def test_queens_shows_crown(self, capsys):
        print_board(self._board, queens=[(0, 0), (1, 1)])
        out = capsys.readouterr().out
        assert "\U0001f451" in out

    def test_unknown_color_uses_fallback(self, capsys):
        board = [["Z"]]  # 'Z' not in PALETTE
        print_board(board)
        out = capsys.readouterr().out
        assert "\033[" in out  # ANSI escape still produced with fallback colour


# ---------------------------------------------------------------------------
# url_reader.read_community_level: mock network tests
# ---------------------------------------------------------------------------

class TestReadCommunityLevelMocked:
    _valid_url = "https://queensgame.vercel.app/community-level/1"
    _fake_ts = (
        "const level = {\n"
        "  size: 2,\n"
        "  colorRegions: [\n"
        '    ["A", "B"],\n'
        '    ["B", "A"],\n'
        "  ],\n"
        "  regionColors: {},\n"
        "};\n"
    )

    def test_raises_on_bad_url(self):
        with pytest.raises(ValueError, match="Unrecognised URL"):
            read_community_level("https://example.com/not-a-level")

    def test_raises_runtime_on_network_error(self):
        with patch("nqueens_recog.url_reader.urllib.request.urlopen") as mock_open:
            mock_open.side_effect = URLError("connection refused")
            with pytest.raises(RuntimeError, match="Could not fetch"):
                read_community_level(self._valid_url)

    def test_returns_grid_on_success(self):
        fake_ts = self._fake_ts

        class _FakeResp:
            def read(self):
                return fake_ts.encode()
            def __enter__(self):
                return self
            def __exit__(self, *_):
                pass

        with patch("nqueens_recog.url_reader.urllib.request.urlopen", return_value=_FakeResp()):
            result = read_community_level(self._valid_url)
        assert result == [["A", "B"], ["B", "A"]]


# ---------------------------------------------------------------------------
# palette.grid_to_letters: unknown-colour fallback
# ---------------------------------------------------------------------------

class TestGridToLettersUnknown:
    def test_unknown_rgb_gets_lowercase_letter(self):
        tile = Tile(row=0, col=0, color_rgb=(1, 2, 3))  # far outside all palette colours
        grid = Grid(tiles=[[tile]], rows=1, cols=1)
        result = grid_to_letters(grid)
        assert result[0][0].islower()

    def test_two_unknown_colors_get_distinct_letters(self):
        t1 = Tile(row=0, col=0, color_rgb=(1, 2, 3))
        t2 = Tile(row=0, col=1, color_rgb=(4, 5, 6))
        grid = Grid(tiles=[[t1, t2]], rows=1, cols=2)
        result = grid_to_letters(grid)
        assert result[0][0] != result[0][1]
        assert result[0][0].islower() and result[0][1].islower()


# ---------------------------------------------------------------------------
# __main__.main(): CLI entry point
# ---------------------------------------------------------------------------

_SIMPLE_BOARD_STR = ["AB", "BA"]  # grid_to_letters returns list of strings


class TestMain:
    """Tests for the CLI entry point in __main__.main()."""

    def test_image_path_prints_grid_size(self, capsys):
        with patch("sys.argv", ["nqueens-recog", "fake.png"]), \
             patch("nqueens_recog.__main__.is_community_level_url", return_value=False), \
             patch("nqueens_recog.__main__.read_grid"), \
             patch("nqueens_recog.__main__.grid_to_letters", return_value=_SIMPLE_BOARD_STR):
            main()
        assert "2 \u00d7 2" in capsys.readouterr().out

    def test_url_path_success(self, capsys):
        with patch("sys.argv", ["nqueens-recog", "https://queensgame.vercel.app/community-level/1"]), \
             patch("nqueens_recog.__main__.is_community_level_url", return_value=True), \
             patch("nqueens_recog.__main__.read_community_level", return_value=[["A", "B"], ["B", "A"]]):
            main()
        assert "2 \u00d7 2" in capsys.readouterr().out

    def test_url_value_error_exits(self):
        with patch("sys.argv", ["nqueens-recog", "https://queensgame.vercel.app/community-level/1"]), \
             patch("nqueens_recog.__main__.is_community_level_url", return_value=True), \
             patch("nqueens_recog.__main__.read_community_level", side_effect=ValueError("bad")):
            with pytest.raises(SystemExit) as exc_info:
                main()
        assert exc_info.value.code == 1

    def test_url_runtime_error_exits(self):
        with patch("sys.argv", ["nqueens-recog", "https://queensgame.vercel.app/community-level/1"]), \
             patch("nqueens_recog.__main__.is_community_level_url", return_value=True), \
             patch("nqueens_recog.__main__.read_community_level", side_effect=RuntimeError("net")):
            with pytest.raises(SystemExit) as exc_info:
                main()
        assert exc_info.value.code == 1

    def test_non_square_board_exits(self):
        with patch("sys.argv", ["nqueens-recog", "fake.png"]), \
             patch("nqueens_recog.__main__.is_community_level_url", return_value=False), \
             patch("nqueens_recog.__main__.read_grid"), \
             patch("nqueens_recog.__main__.grid_to_letters", return_value=["AB", "B"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
        assert exc_info.value.code == 1

    def test_wrong_color_count_exits(self):
        with patch("sys.argv", ["nqueens-recog", "fake.png"]), \
             patch("nqueens_recog.__main__.is_community_level_url", return_value=False), \
             patch("nqueens_recog.__main__.read_grid"), \
             patch("nqueens_recog.__main__.grid_to_letters", return_value=["AA", "AA"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
        assert exc_info.value.code == 1

    def test_verbose_flag_prints_board(self, capsys):
        with patch("sys.argv", ["nqueens-recog", "--verbose", "fake.png"]), \
             patch("nqueens_recog.__main__.is_community_level_url", return_value=False), \
             patch("nqueens_recog.__main__.read_grid"), \
             patch("nqueens_recog.__main__.grid_to_letters", return_value=_SIMPLE_BOARD_STR):
            main()
        assert "\033[" in capsys.readouterr().out

    def test_solve_flag_prints_total(self, capsys):
        with patch("sys.argv", ["nqueens-recog", "--solve", "fake.png"]), \
             patch("nqueens_recog.__main__.is_community_level_url", return_value=False), \
             patch("nqueens_recog.__main__.read_grid"), \
             patch("nqueens_recog.__main__.grid_to_letters", return_value=_SIMPLE_BOARD_STR):
            main()
        assert "Total solutions found:" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# grid_reader internal helpers: edge-case coverage
# ---------------------------------------------------------------------------


class TestGridReaderInternals:
    def test_read_grid_raises_for_nonsquare(self, tmp_path):
        """read_grid raises ValueError when detected row/col counts differ."""
        import numpy as np
        import cv2
        img = np.full((100, 150, 3), 200, dtype=np.uint8)
        p = tmp_path / "fake.png"
        cv2.imwrite(str(p), img)
        with patch(
            "nqueens_recog.grid_reader._line_positions",
            side_effect=[[20, 50, 80], [30, 60]],  # 4 rows, 3 cols
        ):
            with pytest.raises(ValueError, match="not square"):
                read_grid(str(p))


# ---------------------------------------------------------------------------
# Stepwise solver: rules 1-3 must be sufficient for sample puzzles
# ---------------------------------------------------------------------------

@pytest.mark.slow
@pytest.mark.parametrize("image_path,label,expected_cols", [
    (PUZZLE_589, "589", [10, 1, 5, 8, 6, 2, 7, 4, 9, 11, 3]),
    (PUZZLE_687, "687", [14, 3, 6, 4, 12, 7, 5, 8, 11, 13, 10, 17, 2, 15, 9, 16, 1]),
    (PUZZLE_657, "657", [16, 2, 13, 10, 8, 14, 12, 18, 7, 4, 6, 15, 5, 11, 9, 17, 3, 1]),
])
def test_stepwise_solves_puzzle(image_path: Path, label: str, expected_cols: list[int]) -> None:
    """All seven rules must fully solve each sample puzzle."""
    board = [list(row) for row in grid_to_letters(read_grid(str(image_path)))]
    result = solve_stepwise(board, quiet=True)
    assert result is not None, f"Puzzle {label}: stepwise solver got stuck"
    cols = [result[r] + 1 for r in range(len(board))]
    assert cols == expected_cols, (
        f"Puzzle {label}: stepwise solution {cols} != expected {expected_cols}"
    )