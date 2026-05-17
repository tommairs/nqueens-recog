"""ANSI terminal rendering for Queens game boards."""

from .palette import PALETTE, hex_to_rgb

# Map palette letter → hex colour string for terminal display.
_LETTER_TO_HEX: dict[str, str] = {letter: hex_color for letter, hex_color in PALETTE}
_UNKNOWN_COLOR = "#888888"


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
                cell = " 　 "  # full-width space, 4 cols
            row += f"{bg}{cell}{RESET}"
        print(row)
    print()
