"""verify – Post-sort verification utilities.

Functions to check whether a binary doubles file is sorted and to count
its elements.
"""

from __future__ import annotations

import struct
from pathlib import Path
from typing import Union

from core.binary_io import DOUBLE_SIZE


def verify_sorted(path: Union[str, Path], buffer_size: int = 8192) -> bool:
    """Return *True* if the doubles in *path* are in non-decreasing order.

    Parameters
    ----------
    path : path-like
        Binary doubles file to check.
    buffer_size : int
        Number of doubles to read per I/O call.

    Returns
    -------
    bool
        ``True`` when sorted ascending; ``False`` otherwise.
    """
    path = Path(path)
    chunk_bytes = buffer_size * DOUBLE_SIZE
    prev: float | None = None

    with open(path, "rb") as fh:
        while True:
            raw = fh.read(chunk_bytes)
            if not raw:
                break
            n = len(raw) // DOUBLE_SIZE
            values = struct.unpack(f"<{n}d", raw[: n * DOUBLE_SIZE])
            for v in values:
                if prev is not None and v < prev:
                    return False
                prev = v
    return True


def count_elements(path: Union[str, Path]) -> int:
    """Return the number of doubles stored in *path*.

    Parameters
    ----------
    path : path-like
        Binary doubles file.

    Returns
    -------
    int
    """
    return Path(path).stat().st_size // DOUBLE_SIZE
