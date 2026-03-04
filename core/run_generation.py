"""run_generation – Phase 1 of External Merge Sort.

Read the input binary file in fixed-size chunks (*run_capacity* doubles),
sort each chunk in memory, and write them as individual temporary run files.
"""

from __future__ import annotations

import os
import struct
from pathlib import Path
from typing import Callable, Optional, Union

from core.binary_io import DOUBLE_SIZE


def make_runs(
    input_path: Union[str, Path],
    run_capacity: int,
    runs_dir: Union[str, Path],
    *,
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> list[Path]:
    """Split *input_path* into sorted run files.

    Parameters
    ----------
    input_path : str | Path
        Path to the binary file of doubles.
    run_capacity : int
        Maximum number of doubles per run (fits in RAM).
    runs_dir : str | Path
        Directory where temporary run files are stored.
    progress_cb : callable, optional
        ``progress_cb(runs_done, total_elements)`` called after each run.

    Returns
    -------
    list[Path]
        Ordered list of run file paths.
    """
    input_path = Path(input_path)
    runs_dir = Path(runs_dir)
    runs_dir.mkdir(parents=True, exist_ok=True)

    file_size = input_path.stat().st_size
    total_doubles = file_size // DOUBLE_SIZE
    chunk_bytes = run_capacity * DOUBLE_SIZE

    run_paths: list[Path] = []
    elements_done = 0

    with open(input_path, "rb") as fh:
        run_index = 0
        while True:
            raw = fh.read(chunk_bytes)
            if not raw:
                break

            n = len(raw) // DOUBLE_SIZE
            # Unpack, sort, repack
            values = list(struct.unpack(f"<{n}d", raw[: n * DOUBLE_SIZE]))
            values.sort()

            run_path = runs_dir / f"run_{run_index:06d}.bin"
            with open(run_path, "wb") as out:
                out.write(struct.pack(f"<{n}d", *values))

            run_paths.append(run_path)
            run_index += 1
            elements_done += n

            if progress_cb is not None:
                progress_cb(elements_done, total_doubles)

    return run_paths
