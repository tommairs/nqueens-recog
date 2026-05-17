# nqueens-recog

Detect and parse a colour grid from an image, designed for
[N-Queens puzzle](https://queensgame.vercel.app/) recognition.

The pipeline uses OpenCV for perspective correction and gradient-based grid
line detection, then k-means colour quantisation to assign each cell to one
of the *n* region colours. No OCR is used; recognition is purely colour-based.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Run

Print the letter grid for a puzzle image:

```bash
nqueens-recog img/puzzle-687.png
```

Each cell is printed as its palette letter (A–S). Colours not matching the
game palette are assigned consecutive lowercase letters (a, b, c, …).

```
Grid: 17 × 17, 17 colours
E B B E E E L O O O L E E G E E E
B B B B E O O J A J O E P E E E E
...
```

`python -m nqueens_recog <image>` also works if the package is not installed.

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
    __main__.py      # entry point: nqueens-recog <image>
img/
    puzzle-687.png   # reference puzzle image (standard test fixture)
tests/
    test_grids.py    # grid recognition tests
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
