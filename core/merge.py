"""merge – Phase 2 of External Merge Sort.

Provides 2-way and k-way merge primitives that operate on binary run files
using buffered I/O to stay memory-efficient.
"""

from __future__ import annotations

import heapq
import struct
from pathlib import Path
from typing import Optional, Union

from core.binary_io import DOUBLE_SIZE


# ---------------------------------------------------------------------------
# Buffered run reader
# ---------------------------------------------------------------------------

class _BufferedRunReader:
    """Read doubles from a binary run file with an internal buffer.

    This avoids doing one syscall per double while keeping memory bounded.
    """

    __slots__ = ("_fh", "_buf", "_pos", "_buf_len", "_chunk_bytes", "_exhausted")

    def __init__(self, path: Union[str, Path], buffer_size: int = 4096) -> None:
        self._fh = open(path, "rb")
        self._chunk_bytes = buffer_size * DOUBLE_SIZE
        self._buf: list[float] = []
        self._pos = 0
        self._buf_len = 0
        self._exhausted = False
        self._fill()

    # -- internal ----------------------------------------------------------

    def _fill(self) -> None:
        raw = self._fh.read(self._chunk_bytes)
        if not raw:
            self._exhausted = True
            self._buf = []
            self._buf_len = 0
            self._pos = 0
            return
        n = len(raw) // DOUBLE_SIZE
        self._buf = list(struct.unpack(f"<{n}d", raw[: n * DOUBLE_SIZE]))
        self._buf_len = n
        self._pos = 0

    # -- public API --------------------------------------------------------

    @property
    def has_next(self) -> bool:  # noqa: D401
        """True if there is at least one more value to read."""
        if self._pos < self._buf_len:
            return True
        if self._exhausted:
            return False
        self._fill()
        return self._pos < self._buf_len

    def peek(self) -> float:
        """Return the next value **without** advancing the cursor."""
        if self._pos >= self._buf_len:
            self._fill()
        return self._buf[self._pos]

    def pop(self) -> float:
        """Return the next value and advance the cursor."""
        val = self._buf[self._pos]
        self._pos += 1
        if self._pos >= self._buf_len and not self._exhausted:
            self._fill()
        return val

    def close(self) -> None:
        self._fh.close()


# ---------------------------------------------------------------------------
# Buffered writer
# ---------------------------------------------------------------------------

class _BufferedRunWriter:
    """Write doubles to a binary file with an internal buffer."""

    __slots__ = ("_fh", "_buf", "_buf_cap")

    def __init__(self, path: Union[str, Path], buffer_size: int = 4096) -> None:
        self._fh = open(path, "wb")
        self._buf: list[float] = []
        self._buf_cap = buffer_size

    def write(self, value: float) -> None:
        self._buf.append(value)
        if len(self._buf) >= self._buf_cap:
            self._flush()

    def _flush(self) -> None:
        if not self._buf:
            return
        n = len(self._buf)
        self._fh.write(struct.pack(f"<{n}d", *self._buf))
        self._buf.clear()

    def close(self) -> None:
        self._flush()
        self._fh.close()


# ---------------------------------------------------------------------------
# 2-way merge
# ---------------------------------------------------------------------------

def merge_two_runs(
    a_path: Union[str, Path],
    b_path: Union[str, Path],
    out_path: Union[str, Path],
    buffer_size: int = 4096,
) -> Path:
    """Merge two sorted run files into one sorted output file.

    Parameters
    ----------
    a_path, b_path : path-like
        Input sorted run files.
    out_path : path-like
        Destination merged file.
    buffer_size : int
        Number of doubles per read/write buffer.

    Returns
    -------
    Path
        *out_path* as a ``Path`` object.
    """
    out_path = Path(out_path)
    ra = _BufferedRunReader(a_path, buffer_size)
    rb = _BufferedRunReader(b_path, buffer_size)
    writer = _BufferedRunWriter(out_path, buffer_size)

    try:
        while ra.has_next and rb.has_next:
            if ra.peek() <= rb.peek():
                writer.write(ra.pop())
            else:
                writer.write(rb.pop())
        while ra.has_next:
            writer.write(ra.pop())
        while rb.has_next:
            writer.write(rb.pop())
    finally:
        ra.close()
        rb.close()
        writer.close()

    return out_path


# ---------------------------------------------------------------------------
# k-way merge (heap-based)
# ---------------------------------------------------------------------------

def merge_k_runs(
    run_paths: list[Union[str, Path]],
    out_path: Union[str, Path],
    buffer_size: int = 4096,
) -> Path:
    """Merge *k* sorted run files using a min-heap.

    Parameters
    ----------
    run_paths : list[path-like]
        Sorted run files to merge.
    out_path : path-like
        Destination merged file.
    buffer_size : int
        Buffer size in doubles per reader/writer.

    Returns
    -------
    Path
        *out_path* as a ``Path`` object.
    """
    if len(run_paths) == 0:
        raise ValueError("No run files to merge.")
    if len(run_paths) == 1:
        # Just copy
        import shutil
        shutil.copy2(run_paths[0], out_path)
        return Path(out_path)
    if len(run_paths) == 2:
        return merge_two_runs(run_paths[0], run_paths[1], out_path, buffer_size)

    out_path = Path(out_path)
    readers = [_BufferedRunReader(p, buffer_size) for p in run_paths]
    writer = _BufferedRunWriter(out_path, buffer_size)

    # Heap entries: (value, reader_index)
    # Using reader_index as tie-breaker guarantees stable ordering.
    heap: list[tuple[float, int]] = []
    for idx, r in enumerate(readers):
        if r.has_next:
            heapq.heappush(heap, (r.pop(), idx))

    try:
        while heap:
            val, idx = heapq.heappop(heap)
            writer.write(val)
            if readers[idx].has_next:
                heapq.heappush(heap, (readers[idx].pop(), idx))
    finally:
        for r in readers:
            r.close()
        writer.close()

    return out_path
