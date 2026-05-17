# nqueens-recog

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

Print the letter grid for a community level by URL:

```bash
nqueens-recog https://queensgame.vercel.app/community-level/657
```

Or from a local screenshot:

```bash
nqueens-recog img/puzzle-687.png
```

Each cell is printed as its palette letter (A–S). In image mode, colours not
matching the game palette are assigned consecutive lowercase letters (a, b, c, …).

```
Grid: 17 × 17, 17 colours
E B B E E E L O O O L E E G E E E
B B B B E O O J A J O E P E E E E
...
```

Add `--solve` to run the backtracking solver. By default only the terse
spoiler line is printed:

```bash
nqueens-recog https://queensgame.vercel.app/community-level/657 --solve
```

```
Solution: 16, 2, 13, 10, 8, 14, 12, 18, 7, 4, 6, 15, 5, 11, 9, 17, 3, 1
Total solutions found: 1
```

Add `-v` / `--verbose` to also show the letter grid and the coloured board
with queen markers:

```bash
nqueens-recog https://queensgame.vercel.app/community-level/657 --solve -v
```

The spoiler line lists 1-based column positions, one per row.

`python -m nqueens_recog <url_or_image>` also works if the package is not installed.

## Test

```bash
pytest
```

Tests run against `img/puzzle-687.png` using the
[queensgame default palette](https://github.com/samimsu/queens-game).
Each detected cluster colour is matched to the nearest palette entry by
squared RGB distance and the resulting letter grid is compared to a known
expected output.

## Project layout

```
src/nqueens_recog/
    grid_reader.py   # image → Grid (perspective correct, line detect, k-means)
    palette.py       # queensgame colour palette and nearest-colour matching
    url_reader.py    # community-level URL → letter grid (fetches GitHub TS source)
    solver.py        # backtracking solver; prints coloured board + spoiler line
    __main__.py      # entry point: nqueens-recog <url_or_image> [--solve [-v]]
img/
    puzzle-687.png   # reference puzzle image (standard test fixture)
tests/
    test_grids.py    # grid recognition, URL reader, and solver tests
```

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
