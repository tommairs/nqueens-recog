"""Read a Queens game community level directly from the GitHub source.

Community level data is stored as TypeScript files in the queens-game repo.
Each file contains ``colorRegions`` (the letter grid) and ``regionColors``
(letter → colour mapping), so no image recognition is needed.
"""

import re
import urllib.request
from urllib.error import URLError

_GITHUB_RAW = (
    "https://raw.githubusercontent.com/samimsu/queens-game/main"
    "/src/utils/community-levels/level{n}.ts"
)
_LEVEL_URL_RE = re.compile(
    r"https?://queensgame\.vercel\.app/community-level/(\d+)"
)


def is_community_level_url(arg: str) -> bool:
    """Return True if *arg* looks like a queensgame community-level URL."""
    return bool(_LEVEL_URL_RE.match(arg.strip()))


def _fetch_source(url: str) -> tuple[str, str]:
    """Return (raw_typescript_source, level_number) for a community-level URL."""
    match = _LEVEL_URL_RE.match(url.strip())
    if not match:
        raise ValueError(
            f"Unrecognised URL. Expected a queensgame community-level URL, "
            f"got: {url!r}"
        )
    level_number = match.group(1)
    raw_url = _GITHUB_RAW.format(n=level_number)
    try:
        with urllib.request.urlopen(raw_url, timeout=10) as resp:
            source = resp.read().decode("utf-8")
    except URLError as exc:
        raise RuntimeError(
            f"Could not fetch level {level_number} from GitHub: {exc}"
        ) from exc
    return source, level_number


def read_community_level(url: str) -> list[list[str]]:
    """Fetch a community level by URL and return its letter grid.

    Parameters
    ----------
    url:
        A queensgame community-level URL, e.g.
        ``https://queensgame.vercel.app/community-level/657``

    Returns
    -------
    list[list[str]]
        The letter grid, one list per row.  Each element is a single
        uppercase letter corresponding to a colour region.

    Raises
    ------
    ValueError
        If *url* is not a recognised community-level URL or the source
        cannot be parsed.
    RuntimeError
        If the GitHub fetch fails.
    """
    source, level_number = _fetch_source(url)
    return _parse_color_regions(source, level_number)


def read_community_level_info(url: str) -> tuple[list[list[str]], int]:
    """Fetch a community level and return ``(board, solutions_count)``.

    *solutions_count* is taken from the ``solutionsCount`` field in the
    TypeScript source; returns 0 if the field is absent.
    """
    source, level_number = _fetch_source(url)
    board = _parse_color_regions(source, level_number)
    sc_match = re.search(r"\bsolutionsCount:\s*(\d+)", source)
    solutions_count = int(sc_match.group(1)) if sc_match else 0
    return board, solutions_count


def _parse_color_regions(source: str, level_id: str = "?") -> list[list[str]]:
    """Extract the ``colorRegions`` grid from a community-level TypeScript file."""
    size_match = re.search(r"\bsize:\s*(\d+)", source)
    if not size_match:
        raise ValueError(f"Could not find 'size' in level {level_id} source")
    size = int(size_match.group(1))

    block_match = re.search(
        r"colorRegions:\s*\[(.+?)\],\s*\n\s*regionColors",
        source,
        re.DOTALL,
    )
    if not block_match:
        raise ValueError(
            f"Could not find 'colorRegions' block in level {level_id} source"
        )

    letters = re.findall(r'"([A-Z])"', block_match.group(1))
    expected = size * size
    if len(letters) != expected:
        raise ValueError(
            f"Level {level_id}: expected {expected} cells ({size}×{size}), "
            f"found {len(letters)}"
        )

    return [letters[i * size : (i + 1) * size] for i in range(size)]
