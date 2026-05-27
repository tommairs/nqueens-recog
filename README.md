# nqueens-recog

[![CI](https://github.com/tuck1s/nqueens-recog/actions/workflows/ci.yml/badge.svg)](https://github.com/tuck1s/nqueens-recog/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/tuck1s/nqueens-recog/graph/badge.svg)](https://codecov.io/gh/tuck1s/nqueens-recog)

Detect and parse a colour grid from an N-Queens puzzle, either from a
[community-level URL](https://queensgame.vercel.app/community-level/657) or
from a screenshot/image file.

**URL mode** fetches the level's TypeScript source directly from the
[queens-game GitHub repo](https://github.com/samimsu/queens-game), giving an
exact, lossless letter grid with no image processing.

**Image mode** uses OpenCV for perspective correction and gradient-based grid
line detection, then k-means colour quantisation to assign each cell to one
of the *n* region colours. No OCR is used; recognition is purely colour-based.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Run

```bash
nqueens-recog https://queensgame.vercel.app/community-level/657
nqueens-recog img/puzzle-687.png
```

Prints `Grid: N × N, N colours`. Add `-v` / `--verbose` to also show the
coloured board (ANSI background per region, region letter in each cell).

Add `--solve` to run the backtracking solver and print the spoiler line of
1-based column positions (one per row):

```
> Solution: 16, 2, 13, 10, 8, 14, 12, 18, 7, 4, 6, 15, 5, 11, 9, 17, 3, 1
Total solutions found: 1
```

`-v` and `--solve` are independent — combine them to show both the coloured
grid and the solved board with queen markers:

```bash
nqueens-recog https://queensgame.vercel.app/community-level/657 --solve -v
```

`python -m nqueens_recog <url_or_image>` also works if the package is not installed.

## Test

```bash
pytest           # fast tests (image recognition, palette, URL parser)
pytest --slow    # also runs the solver against all three sample images
pytest --network # also cross-validates image recognition against GitHub level data
```

## Project layout

```
src/nqueens_recog/
    grid_reader.py   # image → Grid (perspective correct, line detect, k-means)
    palette.py       # queensgame colour palette and nearest-colour matching
    display.py       # ANSI terminal board renderer (letter view and queen view)
    url_reader.py    # community-level URL → letter grid (fetches GitHub TS source)
    solver.py        # backtracking solver; prints spoiler line + coloured board
    __main__.py      # entry point: nqueens-recog <url_or_image> [--solve [-v]]
img/
    puzzle-*.png     # sample puzzle images (test fixtures)
tests/
    conftest.py      # --network and --slow opt-in flags
    test_grids.py    # grid recognition, URL reader, and solver tests
```

## Stepwise solver

`--stepwise` applies human-like logical elimination rules and prints a trace
of each deduction, rather than backtracking exhaustively:

```bash
nqueens-recog https://queensgame.vercel.app/community-level/705 --stepwise
```

Add `-v` / `--verbose` to also render the board state after each rule fires,
showing region letters for active candidates, `✖` for eliminated cells, and
👑 for placed queens (newly-eliminated cells are highlighted in red).

Ten rules are applied in order of increasing cost:

1. **Region singleton** — a region/row/column narrowed to one cell; place the queen.
2. **Region forced row/col** — all candidates for a region share a row or column; claim it.
3. **Squeeze** — a row/col's candidates span ≤ 2 cells, so the queen always diagonally attacks the overlap zone in adjacent rows/cols.
4. **Shadow** — eliminate any cell attacked by *all* candidates of a colour.
5. **N-group** — k regions whose candidates are confined to k rows/cols; reserve those lines.
6. **X-Wing** — c colours whose candidates fit within a rows + b columns (a+b=c); claim all those lines.
7. **Double-block** — tentatively place a queen; if two regions are then forced onto the same row/col, the candidate is invalid.
8. **Elimination** — placing a queen at a candidate leaves another region empty; rule it out.
9. **Lookahead** — trial-place a queen in every candidate of small regions; remove contradictions.
10. **Search** — last resort: pick the most-constrained region, guess, and backtrack.

### HTML output

`solve_html.sh` renders a single level's stepwise trace as a styled HTML file
(requires [`aha`](https://github.com/theZiz/aha): `brew install aha`):

```bash
./solve_html.sh 705          # → all_solutions/level_705.html
```

The HTML uses fixed-width coloured cells so the board renders cleanly in any
browser regardless of font.

## Batch solve all community levels

`solve_all.sh` iterates over all known community levels (1–692) and writes
the full output to `all_solutions/solutions.txt`:

```bash
bash solve_all.sh              # levels 1-692, 1 s delay between requests
bash solve_all.sh 1 692 0.5   # custom range and delay (seconds)
```

Each level prints a `=== Level N ===` header followed by the raw output from
`nqueens-recog --solve`, including any errors. All output is also appended to
`all_solutions/solutions.txt` (excluded from git).

## Cross-check stepwise solver against recursive solver

`chk_stepwise.py` fetches a range of community levels, checks the stepwise
solver against the recursive solver on every level that has a unique solution,
and writes an HTML file for each:

```bash
python chk_stepwise.py [FIRST [LAST [DELAY]]]

python chk_stepwise.py 1 100      # levels 1-100, 1 s delay
python chk_stepwise.py 578 642 0  # no delay
```

For each level in the range it:

1. Fetches the board and reads `solutionsCount` from the TypeScript source (no solver run needed to check uniqueness).
2. Skips levels with `solutionsCount != 1` or levels that cannot be fetched (404, parse errors).
3. Runs the stepwise solver and captures its trace.
4. **For all n**: cross-checks the stepwise result against the recursive solver (with early exit after the first solution is found).
5. Reports any divergence or invalid solution on stderr with a `!! ` prefix.
6. Prints elapsed time for each solver and which deduction rules the stepwise solver used.
7. Writes `all_solutions/level_N.html` (requires `aha`: `brew install aha`).

Example output:

```
=== Level 640 ===
  Board: 6×6, solutionsCount=1
  Stepwise: ok [stepwise 0.002s, recursive 0.000s] — rules used: singleton, forced, squeeze, shadow, n-group
  Written: all_solutions/level_640.html
=== Level 641 ===
  Board: 18×18, solutionsCount=1
  Stepwise: ok [stepwise 0.041s, recursive 2.847s] — rules used: singleton, forced, squeeze, shadow, n-group, x-wing
  Written: all_solutions/level_641.html
```

## How the image recognition works

1. **Perspective correction** — find the four-corner contour of the grid and
   warp it to a rectangle.
2. **Border stripping** — locate the bounding box of dark (grid-line) pixels
   to remove the surrounding cream/white border.
3. **Grid line detection** — project gradient magnitudes along each axis and
   find peaks to locate row and column boundaries.
4. **Squareness check** — raise `ValueError` if the number of detected rows
   differs from the number of columns.
5. **Colour sampling** — take the median colour of the inner 60 % of each cell.
6. **K-means quantisation** — cluster the *n²* samples into *n* canonical
   colours (one per region).
7. **Palette matching** — map each canonical colour to its nearest letter in
   the queensgame default palette by squared RGB distance.
