"""binary_io – Low-level helpers for reading / writing IEEE-754 double files.

All functions operate on **binary** files whose content is a sequence of
8-byte little-endian doubles.  No numpy dependency is required.
"""

from __future__ import annotations

import os
import struct
from pathlib import Path
from typing import Generator, Iterable, Union

# Each double-precision float is 8 bytes (IEEE-754, little-endian).
DOUBLE_SIZE: int = 8
# struct format: '<' = little-endian, 'd' = double
_LE_DOUBLE = struct.Struct("<d")


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_file(path: Union[str, Path]) -> int:
    """Validate that *path* exists and its size is a multiple of 8.

    Returns
    -------
    int
        The number of doubles stored in the file.

    Raises
    ------
    FileNotFoundError
        If *path* does not exist.
    ValueError
        If the file size is not divisible by 8.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    size = path.stat().st_size
    if size % DOUBLE_SIZE != 0:
        raise ValueError(
            f"File size ({size} bytes) is not a multiple of {DOUBLE_SIZE}. "
            "The file may be corrupt or not in the expected format."
        )
    return size // DOUBLE_SIZE


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------

def iter_read_doubles(
    path: Union[str, Path],
    chunk_size: int = 4096,
) -> Generator[float, None, None]:
    """Yield doubles from a binary file, reading *chunk_size* values at a time.

    Parameters
    ----------
    path : str | Path
        Path to the binary file.
    chunk_size : int
        Number of doubles to read per disk I/O call.

    Yields
    ------
    float
        The next double-precision value in the file.
    """
    buf_bytes = chunk_size * DOUBLE_SIZE
    fmt = f"<{chunk_size}d"
    with open(path, "rb") as fh:
        while True:
            data = fh.read(buf_bytes)
            if not data:
                break
            n = len(data) // DOUBLE_SIZE
            if n == chunk_size:
                for v in struct.unpack(fmt, data):
                    yield v
            else:
                for v in struct.unpack(f"<{n}d", data[:n * DOUBLE_SIZE]):
                    yield v


def read_doubles(path: Union[str, Path], count: int, offset: int = 0) -> list[float]:
    """Read exactly *count* doubles starting at byte *offset*.

    Parameters
    ----------
    path : str | Path
        Binary file path.
    count : int
        Number of doubles to read.
    offset : int
        Byte offset to seek to before reading.

    Returns
    -------
    list[float]
    """
    with open(path, "rb") as fh:
        fh.seek(offset)
        data = fh.read(count * DOUBLE_SIZE)
    n = len(data) // DOUBLE_SIZE
    return list(struct.unpack(f"<{n}d", data[:n * DOUBLE_SIZE]))


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------

def write_doubles(path: Union[str, Path], values: Iterable[float]) -> int:
    """Write an iterable of doubles to a binary file.

    Parameters
    ----------
    path : str | Path
        Destination file path (will be created / overwritten).
    values : Iterable[float]
        Values to write.

    Returns
    -------
    int
        The number of values written.
    """
    count = 0
    with open(path, "wb") as fh:
        for v in values:
            fh.write(_LE_DOUBLE.pack(v))
            count += 1
    return count


def write_doubles_bulk(path: Union[str, Path], values: list[float]) -> int:
    """Write a list of doubles in one call (faster for in-memory lists).

    Parameters
    ----------
    path : str | Path
        Destination file path.
    values : list[float]
        Values to write.

    Returns
    -------
    int
        Number of values written.
    """
    n = len(values)
    with open(path, "wb") as fh:
        fh.write(struct.pack(f"<{n}d", *values))
    return n


def count_doubles(path: Union[str, Path]) -> int:
    """Return the number of doubles in *path* (file-size / 8)."""
    return os.path.getsize(path) // DOUBLE_SIZE
