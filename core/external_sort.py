"""external_sort – Full External Merge Sort pipeline.

Orchestrates run generation (Phase 1) and multi-pass merging (Phase 2),
with support for progress callbacks and optional run preservation.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Callable, Optional, Union

from core.binary_io import validate_file
from core.merge import merge_k_runs
from core.run_generation import make_runs


# ---------------------------------------------------------------------------
# Progress info dataclass-like
# ---------------------------------------------------------------------------

class SortProgress:
    """Container for progress information sent to callbacks."""

    __slots__ = ("phase", "detail", "percent")

    def __init__(self, phase: str, detail: str, percent: float) -> None:
        self.phase = phase
        self.detail = detail
        self.percent = percent  # 0.0 – 100.0

    def __repr__(self) -> str:
        return f"SortProgress({self.phase!r}, {self.detail!r}, {self.percent:.1f}%)"


ProgressCallback = Callable[[SortProgress], None]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def external_merge_sort(
    input_path: Union[str, Path],
    output_path: Union[str, Path],
    run_capacity: int = 50_000,
    buffer_size: int = 4096,
    k: int = 2,
    keep_runs: bool = False,
    progress_cb: Optional[ProgressCallback] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> Path:
    """Run a complete external merge sort.

    Parameters
    ----------
    input_path : path-like
        Binary file of little-endian doubles.
    output_path : path-like
        Where the sorted binary file is written.
    run_capacity : int
        Doubles per in-memory run (Phase 1 chunk size).
    buffer_size : int
        Doubles per I/O buffer during merge.
    k : int
        Merge fan-in (2 = classic 2-way; >2 = k-way with heap).
    keep_runs : bool
        If *True*, temporary run files are preserved after sorting.
    progress_cb : callable, optional
        Called with a `SortProgress` object on every notable event.
    cancel_check : callable, optional
        If provided, called periodically; must return *True* to cancel.

    Returns
    -------
    Path
        ``output_path`` as a `Path` object.

    Raises
    ------
    FileNotFoundError
        If the input file does not exist.
    ValueError
        If the input file size is not a multiple of 8.
    RuntimeError
        If sorting is cancelled via *cancel_check*.
    """
    input_path = Path(input_path)
    output_path = Path(output_path)
    validate_file(input_path)

    if input_path.resolve() == output_path.resolve():
        raise ValueError("Output path must differ from input path.")

    # Temporary directory for run files
    tmp_dir = Path(tempfile.mkdtemp(prefix="ems_runs_"))

    def _emit(phase: str, detail: str, percent: float) -> None:
        if progress_cb is not None:
            progress_cb(SortProgress(phase, detail, percent))

    def _cancelled() -> bool:
        return cancel_check is not None and cancel_check()

    try:
        # ---- Phase 1: Run generation ------------------------------------
        _emit("phase1", "Generating sorted runs …", 0.0)

        total_doubles = input_path.stat().st_size // 8

        def _run_progress(done: int, total: int) -> None:
            pct = done / total * 50 if total else 0
            _emit("phase1", f"Run generation: {done}/{total} elements", pct)

        run_paths = make_runs(input_path, run_capacity, tmp_dir, progress_cb=_run_progress)

        if _cancelled():
            raise RuntimeError("Sort cancelled during run generation.")

        _emit("phase1", f"Created {len(run_paths)} initial run(s).", 50.0)

        # ---- Phase 2: Merge passes --------------------------------------
        pass_num = 0
        while len(run_paths) > 1:
            if _cancelled():
                raise RuntimeError("Sort cancelled during merge.")

            pass_num += 1
            new_runs: list[Path] = []
            groups = _partition(run_paths, k)
            total_groups = len(groups)

            for g_idx, group in enumerate(groups):
                if _cancelled():
                    raise RuntimeError("Sort cancelled during merge.")
                merged_path = tmp_dir / f"pass{pass_num:03d}_run{g_idx:06d}.bin"
                if len(group) == 1:
                    # Nothing to merge – just reuse the file.
                    new_runs.append(group[0])
                else:
                    merge_k_runs(group, merged_path, buffer_size)
                    new_runs.append(merged_path)

                pct = 50 + (pass_num / (pass_num + 1)) * 50 * ((g_idx + 1) / total_groups)
                _emit(
                    "phase2",
                    f"Pass {pass_num}: merged group {g_idx + 1}/{total_groups}",
                    min(pct, 99.0),
                )

            run_paths = new_runs

        # ---- Finalise ----------------------------------------------------
        if run_paths:
            shutil.copy2(run_paths[0], output_path)
        else:
            # Edge case: empty input → empty output
            output_path.write_bytes(b"")

        _emit("done", "Sorting complete.", 100.0)

    finally:
        if not keep_runs:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    return output_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _partition(items: list, k: int) -> list[list]:
    """Split *items* into groups of at most *k*."""
    return [items[i : i + k] for i in range(0, len(items), k)]
