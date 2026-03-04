"""demo_steps – Generator-based merge demo for small files.

Yields step-by-step events (compare / output / done) so the GUI can
visualise every comparison made during the merge phase.

This module is intentionally simple: it reads small run files entirely
into memory and yields events instead of writing directly to disk.
"""

from __future__ import annotations

import heapq
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Generator, Union

from core.binary_io import DOUBLE_SIZE
from core.run_generation import make_runs


# ---------------------------------------------------------------------------
# Event types
# ---------------------------------------------------------------------------

@dataclass
class DemoEvent:
    """Base class for demo events."""
    kind: str  # "compare", "output", "run_generated", "pass_start", "done"


@dataclass
class RunGeneratedEvent(DemoEvent):
    """Emitted after each initial sorted run is created (Phase 1)."""
    kind: str = "run_generated"
    run_index: int = 0
    values: list[float] = field(default_factory=list)


@dataclass
class PassStartEvent(DemoEvent):
    """Emitted when a new merge pass begins."""
    kind: str = "pass_start"
    pass_number: int = 0
    num_runs: int = 0


@dataclass
class CompareEvent(DemoEvent):
    """Emitted when two values from different runs are compared."""
    kind: str = "compare"
    left_value: float = 0.0
    right_value: float = 0.0
    left_run: int = 0
    right_run: int = 0


@dataclass
class OutputEvent(DemoEvent):
    """Emitted when a value is written to the merged output."""
    kind: str = "output"
    value: float = 0.0
    from_run: int = 0
    merged_so_far: list[float] = field(default_factory=list)


@dataclass
class DoneEvent(DemoEvent):
    """Emitted when the entire sort is finished."""
    kind: str = "done"
    sorted_values: list[float] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helper: read entire small run into list
# ---------------------------------------------------------------------------

def _read_run(path: Union[str, Path]) -> list[float]:
    data = Path(path).read_bytes()
    n = len(data) // DOUBLE_SIZE
    if n == 0:
        return []
    return list(struct.unpack(f"<{n}d", data[: n * DOUBLE_SIZE]))


# ---------------------------------------------------------------------------
# Public generator
# ---------------------------------------------------------------------------

def demo_merge_sort(
    input_path: Union[str, Path],
    run_capacity: int = 10,
    k: int = 2,
) -> Generator[DemoEvent, None, list[float]]:
    """Yield step-by-step events for an external merge sort of a small file.

    Parameters
    ----------
    input_path : path-like
        Binary doubles file (should be small — a few hundred values max).
    run_capacity : int
        Doubles per initial run.
    k : int
        Merge fan-in (2-way or k-way).

    Yields
    ------
    DemoEvent
        One event per logical step (compare, output, etc.).

    Returns
    -------
    list[float]
        The final sorted list.
    """
    import tempfile, shutil

    input_path = Path(input_path)
    tmp_dir = Path(tempfile.mkdtemp(prefix="ems_demo_"))

    try:
        # Phase 1 — run generation
        run_paths = make_runs(input_path, run_capacity, tmp_dir)
        for idx, rp in enumerate(run_paths):
            vals = _read_run(rp)
            yield RunGeneratedEvent(run_index=idx, values=vals)

        # Phase 2 — iterative merge passes in memory
        runs: list[list[float]] = [_read_run(rp) for rp in run_paths]
        pass_number = 0

        while len(runs) > 1:
            pass_number += 1
            yield PassStartEvent(pass_number=pass_number, num_runs=len(runs))
            new_runs: list[list[float]] = []

            for g_start in range(0, len(runs), k):
                group = runs[g_start : g_start + k]
                if len(group) == 1:
                    new_runs.append(group[0])
                    continue

                merged = yield from _demo_merge_group(group, g_start, k)
                new_runs.append(merged)

            runs = new_runs

        final = runs[0] if runs else []
        yield DoneEvent(sorted_values=final)
        return final

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _demo_merge_group(
    group: list[list[float]],
    group_offset: int,
    k: int,
) -> Generator[DemoEvent, None, list[float]]:
    """Merge a group of sorted lists, yielding compare/output events.

    For k == 2 we do a simple two-pointer merge (more readable events).
    For k > 2 we use a heap.
    """
    if len(group) == 2:
        return (yield from _demo_merge_two(group[0], group[1], group_offset))
    return (yield from _demo_merge_k(group, group_offset))


def _demo_merge_two(
    left: list[float],
    right: list[float],
    group_offset: int,
) -> Generator[DemoEvent, None, list[float]]:
    merged: list[float] = []
    i, j = 0, 0
    left_id = group_offset
    right_id = group_offset + 1

    while i < len(left) and j < len(right):
        yield CompareEvent(
            left_value=left[i],
            right_value=right[j],
            left_run=left_id,
            right_run=right_id,
        )
        if left[i] <= right[j]:
            merged.append(left[i])
            yield OutputEvent(value=left[i], from_run=left_id, merged_so_far=list(merged))
            i += 1
        else:
            merged.append(right[j])
            yield OutputEvent(value=right[j], from_run=right_id, merged_so_far=list(merged))
            j += 1

    while i < len(left):
        merged.append(left[i])
        yield OutputEvent(value=left[i], from_run=left_id, merged_so_far=list(merged))
        i += 1

    while j < len(right):
        merged.append(right[j])
        yield OutputEvent(value=right[j], from_run=right_id, merged_so_far=list(merged))
        j += 1

    return merged


def _demo_merge_k(
    group: list[list[float]],
    group_offset: int,
) -> Generator[DemoEvent, None, list[float]]:
    """Heap-based k-way merge with compare/output events."""
    merged: list[float] = []
    # heap entries: (value, run_id, index_in_run)
    heap: list[tuple[float, int, int]] = []
    for g_idx, run in enumerate(group):
        if run:
            heapq.heappush(heap, (run[0], group_offset + g_idx, 0))

    while len(heap) > 1:
        val, run_id, pos = heapq.heappop(heap)
        # The compare event uses the current minimum vs. the new heap top
        next_val, next_run, _ = heap[0]
        yield CompareEvent(
            left_value=val,
            right_value=next_val,
            left_run=run_id,
            right_run=next_run,
        )
        merged.append(val)
        yield OutputEvent(value=val, from_run=run_id, merged_so_far=list(merged))
        src = group[run_id - group_offset]
        if pos + 1 < len(src):
            heapq.heappush(heap, (src[pos + 1], run_id, pos + 1))

    if heap:
        val, run_id, pos = heap[0]
        src = group[run_id - group_offset]
        while pos < len(src):
            merged.append(src[pos])
            yield OutputEvent(value=src[pos], from_run=run_id, merged_so_far=list(merged))
            pos += 1

    return merged
