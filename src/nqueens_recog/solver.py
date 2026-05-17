"""N-Queens solver adapted from https://github.com/tuck1s/nqueens/blob/main/solve.py.

Accepts a letter grid (list[list[str]]) as produced by grid_to_letters() or
read_community_level(), rather than the original Color enum board.

Rules (LinkedIn / queensgame variant):
  - One queen per row, one queen per column, one queen per colour region.
  - No two queens may be diagonally *adjacent* (touching corners).
    Longer diagonals are allowed, unlike standard chess.
"""

from .palette import PALETTE, hex_to_rgb

# Map palette letter → hex colour string for terminal display.
_LETTER_TO_HEX: dict[str, str] = {letter: hex_color for letter, hex_color in PALETTE}
_UNKNOWN_COLOR = "#888888"


def solve(
    board: list[list[str]], verbose: bool = True
) -> list[list[tuple[int, int]]]:
    """Return all solutions for *board* as lists of (col, row) queen positions.

    Each solution is a list of *n* ``(x, y)`` tuples – one queen per row –
    where ``x`` is the column index and ``y`` is the row index.

    The ``Solution:`` spoiler line is always printed for each solution found.
    When *verbose* is true the coloured board is also printed.
    """
    size = len(board)
    all_solutions: list[list[tuple[int, int]]] = []

    def is_diagonally_adjacent(
        x: int, y: int, queens: list[tuple[int, int]]
    ) -> bool:
        return any(abs(qx - x) == 1 and abs(qy - y) == 1 for qx, qy in queens)

    def solve_from(
        y: int,
        used_columns: set[int],
        used_colors: set[str],
        queens: list[tuple[int, int]],
    ) -> None:
        if y == size:
            # queens is in row order: queens[i] = (col, row_i)
            cols = [x + 1 for x, _ in queens]
            print("Solution: " + ", ".join(str(c) for c in cols))
            if verbose:
                print_board(board, queens)
            all_solutions.append(queens)
            return
        for x in range(size):
            color = board[y][x]
            if (
                x not in used_columns
                and color not in used_colors
                and not is_diagonally_adjacent(x, y, queens)
            ):
                solve_from(
                    y + 1,
                    used_columns | {x},
                    used_colors | {color},
                    queens + [(x, y)],
                )

    solve_from(0, set(), set(), [])
    return all_solutions


def print_board(
    board: list[list[str]],
    queens: list[tuple[int, int]] | None = None,
) -> None:
    """Print *board* to stdout with ANSI background colours.

    When *queens* is ``None`` (default) each cell shows its region letter.
    When *queens* is provided, queen positions show 👑 and empty cells show
    a blank — matching the same 4-column cell width in both cases.
    """
    RESET = "\033[0m"
    queen_set = set(queens) if queens is not None else set()
    for y in range(len(board)):
        row = ""
        for x in range(len(board[y])):
            hex_color = _LETTER_TO_HEX.get(board[y][x], _UNKNOWN_COLOR)
            r, g, b = hex_to_rgb(hex_color)
            bg = f"\033[48;2;{r};{g};{b}m"
            if queens is None:
                cell = f"  {board[y][x]} "  # 4 cols: matches queen/blank width
            elif (x, y) in queen_set:
                cell = " 👑 "  # 4 cols (emoji is 2-wide)
            else:
                cell = " \u3000 "  # full-width space, 4 cols
            row += f"{bg}{cell}{RESET}"
        print(row)
    print()
