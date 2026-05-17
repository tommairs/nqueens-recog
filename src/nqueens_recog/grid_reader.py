"""Grid image recognition for the nqueens-recog project."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class Tile:
    """A single tile in the recognised grid."""

    row: int
    col: int
    color_rgb: tuple[int, int, int]
    letter: Optional[str]

    def __repr__(self) -> str:
        return f"Tile({self.row},{self.col} rgb={self.color_rgb})"


@dataclass
class Grid:
    """2-D array of Tiles.  Origin (0, 0) is top-left."""

    tiles: list[list[Tile]]
    rows: int
    cols: int

    def __getitem__(self, pos: tuple[int, int]) -> Tile:
        row, col = pos
        return self.tiles[row][col]

    def letter_grid(self) -> list[list[Optional[str]]]:
        """Return a 2-D list of letters (always None; OCR is not used)."""
        return [[t.letter for t in row] for row in self.tiles]

    def color_grid(self) -> list[list[tuple[int, int, int]]]:
        """Return a 2-D list of (R, G, B) colour tuples."""
        return [[t.color_rgb for t in row] for row in self.tiles]

    def color_index_grid(self) -> list[list[int]]:
        """Return a 2-D list of 0-based colour indices (0 … n-1)."""
        palette = sorted({t.color_rgb for row in self.tiles for t in row})
        idx = {c: i for i, c in enumerate(palette)}
        return [[idx[t.color_rgb] for t in row] for row in self.tiles]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _order_points(pts: np.ndarray) -> np.ndarray:
    """Order 4 corner points: TL, TR, BR, BL."""
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]    # top-left  (smallest x+y)
    rect[2] = pts[np.argmax(s)]    # bottom-right (largest x+y)
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)] # top-right
    rect[3] = pts[np.argmax(diff)] # bottom-left
    return rect


def _perspective_correct(img: np.ndarray, pts: np.ndarray) -> np.ndarray:
    """Warp *img* so that the quadrilateral *pts* becomes a rectangle."""
    rect = _order_points(pts)
    tl, tr, br, bl = rect
    w = int(max(np.linalg.norm(br - bl), np.linalg.norm(tr - tl)))
    h = int(max(np.linalg.norm(tr - br), np.linalg.norm(tl - bl)))
    dst = np.array([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]], dtype="float32")
    M = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(img, M, (w, h))


def _find_grid_corners(gray: np.ndarray) -> Optional[np.ndarray]:
    """
    Return the 4 corner points of the largest near-rectangular contour
    covering at least 10 % of the image, or None.
    """
    img_area = gray.shape[0] * gray.shape[1]
    for thresh_flag in (cv2.THRESH_BINARY_INV, cv2.THRESH_BINARY):
        _, binary = cv2.threshold(gray, 0, 255, thresh_flag | cv2.THRESH_OTSU)
        closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in sorted(contours, key=cv2.contourArea, reverse=True)[:10]:
            if cv2.contourArea(c) < img_area * 0.10:
                break
            peri = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.02 * peri, True)
            if len(approx) == 4:
                return approx.reshape(4, 2).astype("float32")
    return None


def _find_content_bbox(gray: np.ndarray, dark_threshold: int = 100) -> tuple[int, int, int, int]:
    """
    Return (y0, y1, x0, x1) of the tight bounding box around the grid,
    identified by the presence of dark grid-line pixels.

    Light-coloured borders (cream, white) contain no pixels below
    *dark_threshold* and are therefore excluded.
    """
    mask = gray < dark_threshold
    rows_with_dark = np.any(mask, axis=1)
    cols_with_dark = np.any(mask, axis=0)
    if not np.any(rows_with_dark) or not np.any(cols_with_dark):
        return 0, gray.shape[0], 0, gray.shape[1]
    y_idx = np.where(rows_with_dark)[0]
    x_idx = np.where(cols_with_dark)[0]
    return int(y_idx[0]), int(y_idx[-1] + 1), int(x_idx[0]), int(x_idx[-1] + 1)


def _line_positions(
    gray: np.ndarray,
    axis: int,
    min_spacing: int,
) -> list[int]:
    """
    Locate grid-line centres along one axis via gradient projection.

    Parameters
    ----------
    gray:        Grayscale rectified grid image.
    axis:        0 → horizontal lines (y positions),
                 1 → vertical lines (x positions).
    min_spacing: Minimum pixel distance between two distinct lines.
    """
    kx, ky = (0, 1) if axis == 0 else (1, 0)
    grad = cv2.Sobel(gray, cv2.CV_64F, kx, ky, ksize=3)
    profile = np.abs(grad).mean(axis=1 - axis)

    # Smooth to merge multi-pixel-wide line edges
    k = max(3, (min_spacing // 2)) | 1   # force odd
    profile = np.convolve(profile, np.ones(k) / k, mode="same")

    threshold = float(np.percentile(profile, 80))

    peaks: list[int] = []
    for i in range(1, len(profile) - 1):
        if (
            profile[i] >= threshold
            and profile[i] >= profile[i - 1]
            and profile[i] >= profile[i + 1]
        ):
            if not peaks or i - peaks[-1] >= min_spacing:
                peaks.append(i)
            elif profile[i] > profile[peaks[-1]]:
                peaks[-1] = i

    return peaks


def _cell_color(region_rgb: np.ndarray) -> tuple[int, int, int]:
    """Median colour of the inner 60 % of *region_rgb* (avoids border lines)."""
    h, w = region_rgb.shape[:2]
    m = max(2, min(h, w) // 5)
    inner = region_rgb[m: h - m, m: w - m]
    if inner.size == 0:
        inner = region_rgb
    return (
        int(np.median(inner[:, :, 0])),
        int(np.median(inner[:, :, 1])),
        int(np.median(inner[:, :, 2])),
    )


def _quantize_colors(tiles: list[list[Tile]], n: int) -> list[list[Tile]]:
    """
    Replace each tile's color_rgb with the nearest k-means centroid.
    After quantization every tile has one of exactly *n* canonical colours.
    """
    raw = np.array(
        [[t.color_rgb for t in row] for row in tiles], dtype=np.float32
    ).reshape(-1, 3)

    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 200, 0.5)
    _, labels, centers = cv2.kmeans(
        raw, n, None, criteria, 10, cv2.KMEANS_PP_CENTERS
    )
    centers = np.round(centers).astype(int)
    labels_flat = labels.flatten()

    result: list[list[Tile]] = []
    idx = 0
    for row in tiles:
        new_row: list[Tile] = []
        for tile in row:
            rgb = tuple(int(v) for v in centers[labels_flat[idx]])
            new_row.append(Tile(row=tile.row, col=tile.col, color_rgb=rgb, letter=None))
            idx += 1
        result.append(new_row)
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def read_grid(image_path: str, *, ocr: bool = False) -> Grid:
    """
    Detect and parse a square colour grid from *image_path*.

    The image may have a light-coloured (white/cream) border which is
    stripped automatically.  The inner grid must be square (n × n); a
    :exc:`ValueError` is raised if it is not.

    Tile colours are quantized to exactly *n* canonical colours via k-means,
    on the assumption that an n × n puzzle uses exactly n distinct colours.

    OCR is not performed.  The ``ocr`` parameter is accepted for API
    compatibility but ignored; ``tile.letter`` is always ``None``.

    Parameters
    ----------
    image_path:
        Path to the source image.
    ocr:
        Ignored.

    Returns
    -------
    Grid
        ``grid.tiles[row][col]`` → :class:`Tile`.
        ``tile.color_rgb`` is one of exactly *n* canonical colours.
        ``tile.letter`` is always ``None``.
    """
    bgr = cv2.imread(str(image_path))
    if bgr is None:
        raise FileNotFoundError(f"Cannot read image: {image_path}")

    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    # Perspective-correct when the image was taken at an angle
    corners = _find_grid_corners(gray)
    if corners is not None:
        bgr = _perspective_correct(bgr, corners)
        rgb = _perspective_correct(rgb, corners)
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    # Strip white/cream border so the image spans exactly the grid frame
    cy0, cy1, cx0, cx1 = _find_content_bbox(gray)
    rgb = rgb[cy0:cy1, cx0:cx1]
    gray = gray[cy0:cy1, cx0:cx1]

    H, W = gray.shape
    min_spacing = max(8, min(H, W) // 40)

    row_lines = _line_positions(gray, axis=0, min_spacing=min_spacing)
    col_lines = _line_positions(gray, axis=1, min_spacing=min_spacing)

    def to_bounds(lines: list[int], size: int) -> list[int]:
        """Convert sorted line positions into cell boundary positions."""
        all_pts = sorted({0, size} | set(lines))
        result = [all_pts[0]]
        for b in all_pts[1:]:
            if b - result[-1] >= min_spacing:
                result.append(b)
        # Extend a trailing sliver into the last real cell rather than adding
        # an extra boundary, which would create a spurious thin cell.
        if result[-1] != size:
            if size - result[-1] < min_spacing:
                result[-1] = size
            else:
                result.append(size)
        return result

    row_bounds = to_bounds(row_lines, H)
    col_bounds = to_bounds(col_lines, W)

    n_rows = len(row_bounds) - 1
    n_cols = len(col_bounds) - 1

    if n_rows != n_cols:
        raise ValueError(
            f"Grid is not square: detected {n_rows} rows × {n_cols} cols. "
            "Ensure the image contains a complete, uncropped grid."
        )

    n = n_rows

    tiles: list[list[Tile]] = []
    for r in range(n):
        yr0, yr1 = row_bounds[r], row_bounds[r + 1]
        row_tiles: list[Tile] = []
        for c in range(n):
            xc0, xc1 = col_bounds[c], col_bounds[c + 1]
            color = _cell_color(rgb[yr0:yr1, xc0:xc1])
            row_tiles.append(Tile(row=r, col=c, color_rgb=color, letter=None))
        tiles.append(row_tiles)

    tiles = _quantize_colors(tiles, n)

    return Grid(tiles=tiles, rows=n, cols=n)
