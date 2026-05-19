"""N-Queens solver adapted from https://github.com/tuck1s/nqueens/blob/main/solve.py.

Accepts a letter grid (list[list[str]]) as produced by grid_to_letters() or
read_community_level(), rather than the original Color enum board.

Rules (LinkedIn / queensgame variant):
  - One queen per row, one queen per column, one queen per colour region.
  - No two queens may be diagonally *adjacent* (touching corners).
    Longer diagonals are allowed, unlike standard chess.
"""

from .display import print_board


def solve(
    board: list[list[str]], verbose: bool = True, quiet: bool = False
) -> list[list[tuple[int, int]]]:
    """Return all solutions for *board* as lists of (col, row) queen positions.

    Each solution is a list of *n* ``(x, y)`` tuples – one queen per row –
    where ``x`` is the column index and ``y`` is the row index.

    The ``Solution:`` spoiler line is always printed for each solution found
    unless *quiet* is true.  When *verbose* is true the coloured board is also
    printed (ignored when *quiet* is true).
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
            if not quiet:
                print("> Solution: " + ", ".join(str(c) for c in cols))
            if verbose and not quiet:
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
