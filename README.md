# nqueens-recog

[![CI](https://github.com/tuck1s/nqueens-recog/actions/workflows/ci.yml/badge.svg)](https://github.com/tuck1s/nqueens-recog/actions/workflows/ci.yml)

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

## How it works

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
