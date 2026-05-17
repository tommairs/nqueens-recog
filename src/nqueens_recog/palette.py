"""Queensgame colour palette and nearest-colour matching.

Palette order follows the game's region key sequence.
Source: src/hooks/useLevelBuilderLogic.ts  initialRegionColors
        https://github.com/samimsu/queens-game
"""

import string
from .grid_reader import Grid

# ---------------------------------------------------------------------------
# Palette – (letter, hex) pairs in game order
# ---------------------------------------------------------------------------

PALETTE: list[tuple[str, str]] = [
    ("A", "#5E4FA2"),  # lightWisteria / Butterfly Bush
    ("B", "#FDAE61"),  # chardonnay / Koromiko
    ("C", "#3287BD"),  # anakiwa / Boston Blue
    ("D", "#ACDDA5"),  # celadon / Moss Green
    ("E", "#6C7A89"),  # altoMain / Slate Dark
    ("F", "#D53E4F"),  # bittersweet / Valencia
    ("G", "#E6F598"),  # saharaSand / Sandwisp
    ("H", "#8E8875"),  # nomad / Stone
    ("I", "#F56D43"),  # lightOrchid / Jaffa
    ("J", "#65C2A5"),  # halfBaked / Tradewind
    ("K", "#467A7D"),  # turquoiseBlue / Ocean Muted
    ("L", "#C06C84"),  # atomicTangerine
    ("M", "#607D3B"),  # lightGreen
    ("N", "#4B6B5F"),  # emerald
    ("O", "#4A5A77"),  # periwinkle
    ("P", "#665B82"),  # coldPurple
    ("Q", "#A67A50"),  # macNCheese
    ("R", "#FFFFFF"),  # white
    ("S", "#8E6E8E"),  # lavenderRose / Heather Purple
]

# Maximum squared RGB distance to count as a palette match (≈50 per channel).
MATCH_THRESHOLD: int = 50 * 50 * 3


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def nearest_letter(rgb: tuple[int, int, int]) -> str | None:
    """Return the palette letter closest to *rgb*, or ``None`` if it exceeds MATCH_THRESHOLD."""
    letter, dist = min(
        ((ltr, sum((a - b) ** 2 for a, b in zip(hex_to_rgb(hx), rgb)))
         for ltr, hx in PALETTE),
        key=lambda x: x[1],
    )
    return letter if dist <= MATCH_THRESHOLD else None


def grid_to_letters(grid: Grid) -> list[str]:
    """Convert a Grid to rows of letters.

    Each cell's cluster colour is matched against the palette.  Colours that
    fall outside *MATCH_THRESHOLD* are treated as unknown and assigned
    consecutive lowercase letters (a, b, c, …) in order of first appearance.
    """
    unknown_map: dict[tuple[int, int, int], str] = {}
    lowercase = iter(string.ascii_lowercase)
    rows: list[str] = []
    for row in grid.tiles:
        line: list[str] = []
        for tile in row:
            letter = nearest_letter(tile.color_rgb)
            if letter is None:
                if tile.color_rgb not in unknown_map:
                    unknown_map[tile.color_rgb] = next(lowercase)
                letter = unknown_map[tile.color_rgb]
            line.append(letter)
        rows.append("".join(line))
    return rows
