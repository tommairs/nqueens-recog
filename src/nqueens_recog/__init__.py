"""N-Queens Recognition package."""

__all__ = ["Grid", "Tile", "read_grid"]


def __getattr__(name: str):
    if name in __all__:
        from .grid_reader import Grid, Tile, read_grid  # noqa: F401
        globals().update({"Grid": Grid, "Tile": Tile, "read_grid": read_grid})
        return globals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
