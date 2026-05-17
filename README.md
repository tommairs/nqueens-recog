# nqueens-recog

Detect and parse a colour grid from an image, designed for N-Queens puzzle recognition.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

OCR support (optional) requires Tesseract:

```bash
brew install tesseract            # macOS
# apt install tesseract-ocr       # Debian/Ubuntu
```

## Run

Print the grid from an image:

```bash
python -m nqueens_recog img/grid-with-letters.png
```

Add `--ocr` to enable Tesseract letter recognition:

```bash
python -m nqueens_recog img/grid-with-letters.png --ocr
```

Each tile is printed as its detected letter, or as `(R, G, B)` if no letter was found.

## Test

```bash
pytest
```

## Project layout

```
src/nqueens_recog/
    grid_reader.py   # image → Grid (core recognition logic)
    __main__.py      # entry point (python -m nqueens_recog)
img/                 # example puzzle images
tests/
    test_grids.py    # grid recognition tests
```
