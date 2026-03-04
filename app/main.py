"""main – CLI entry-point and GUI launcher for External Merge Sort.

Usage examples
--------------
CLI sort::

    python -m app.main --input data.bin --output sorted.bin

CLI sort with verification::

    python -m app.main --input data.bin --output sorted.bin --verify

Demo mode (small file, step-by-step)::

    python -m app.main --input small.bin --output sorted.bin --demo

Launch the GUI::

    python -m app.main --gui
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Ensure the project root is on sys.path so ``core`` and ``app`` are importable
# regardless of where the script is invoked from.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.binary_io import validate_file, count_doubles
from core.external_sort import external_merge_sort, SortProgress
from core.verify import verify_sorted, count_elements
from core.demo_steps import demo_merge_sort


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Construct the CLI argument parser."""
    p = argparse.ArgumentParser(
        prog="external-merge-sort",
        description="Sort a binary file of IEEE-754 doubles using External Merge Sort.",
    )
    p.add_argument("--input", "-i", type=str, help="Path to the input binary file.")
    p.add_argument("--output", "-o", type=str, help="Path for the sorted output file.")
    p.add_argument(
        "--run-capacity",
        type=int,
        default=50_000,
        help="Number of doubles per in-memory run (default: 50 000).",
    )
    p.add_argument(
        "--buffer",
        type=int,
        default=4096,
        help="Number of doubles per I/O buffer (default: 4096).",
    )
    p.add_argument(
        "--k",
        type=int,
        default=2,
        choices=[2, 4, 8],
        help="Merge fan-in: 2 (default), 4, or 8.",
    )
    p.add_argument("--demo", action="store_true", help="Run step-by-step demo (small files).")
    p.add_argument("--verify", action="store_true", help="Verify the output is sorted.")
    p.add_argument("--keep-runs", action="store_true", help="Keep temporary run files.")
    p.add_argument("--gui", action="store_true", help="Launch the GUI instead of CLI.")
    return p


# ---------------------------------------------------------------------------
# CLI demo mode
# ---------------------------------------------------------------------------

def run_demo(input_path: str, run_capacity: int, k: int) -> None:
    """Execute the demo generator and print each event to stdout."""
    print(f"\n{'='*60}")
    print("  DEMO MODE — step-by-step External Merge Sort")
    print(f"{'='*60}\n")

    gen = demo_merge_sort(input_path, run_capacity=run_capacity, k=k)
    try:
        while True:
            event = next(gen)
            if event.kind == "run_generated":
                vals = ", ".join(f"{v:.4f}" for v in event.values)
                print(f"[Run {event.run_index}] sorted: [{vals}]")
            elif event.kind == "pass_start":
                print(f"\n--- Merge pass {event.pass_number} ({event.num_runs} runs) ---")
            elif event.kind == "compare":
                print(
                    f"  COMPARE  run{event.left_run}:{event.left_value:.4f}  vs  "
                    f"run{event.right_run}:{event.right_value:.4f}"
                )
            elif event.kind == "output":
                print(f"  OUTPUT   {event.value:.4f}  (from run {event.from_run})")
            elif event.kind == "done":
                vals = ", ".join(f"{v:.4f}" for v in event.sorted_values)
                print(f"\nFinal sorted result: [{vals}]")
    except StopIteration:
        pass
    print()


# ---------------------------------------------------------------------------
# CLI sort
# ---------------------------------------------------------------------------

def run_cli_sort(args: argparse.Namespace) -> None:
    """Perform external merge sort via CLI, printing progress to stdout."""
    input_path = Path(args.input)
    output_path = Path(args.output)

    n = validate_file(input_path)
    print(f"Input file : {input_path}")
    print(f"Elements   : {n:,} doubles")
    print(f"Run capacity: {args.run_capacity:,}")
    print(f"Buffer size : {args.buffer:,}")
    print(f"Merge fan-in: {args.k}-way")
    print()

    t0 = time.perf_counter()

    def _progress(p: SortProgress) -> None:
        bar_len = 40
        filled = int(bar_len * p.percent / 100)
        bar = "█" * filled + "░" * (bar_len - filled)
        print(f"\r  [{bar}] {p.percent:5.1f}%  {p.detail}", end="", flush=True)

    external_merge_sort(
        input_path=input_path,
        output_path=output_path,
        run_capacity=args.run_capacity,
        buffer_size=args.buffer,
        k=args.k,
        keep_runs=args.keep_runs,
        progress_cb=_progress,
    )

    elapsed = time.perf_counter() - t0
    print(f"\n\nSorting completed in {elapsed:.2f}s → {output_path}")

    if args.verify:
        print("Verifying output … ", end="", flush=True)
        if verify_sorted(output_path):
            out_n = count_elements(output_path)
            print(f"OK ({out_n:,} elements, sorted ascending)")
        else:
            print("FAILED — output is NOT sorted!")
            sys.exit(1)


# ---------------------------------------------------------------------------
# GUI launcher
# ---------------------------------------------------------------------------

def launch_gui() -> None:
    """Import and start the PySide6 GUI application."""
    try:
        from app.ui_main import run_gui
    except ImportError as exc:
        print(f"Could not import PySide6 GUI: {exc}", file=sys.stderr)
        print("Install PySide6:  pip install PySide6", file=sys.stderr)
        sys.exit(1)
    run_gui()


# ---------------------------------------------------------------------------
# Entry-point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # Default to GUI when no CLI arguments are provided (e.g. double-click EXE)
    if args.gui or (not args.input and not args.output and not args.demo):
        launch_gui()
        return

    # CLI requires --input and --output
    if not args.input or not args.output:
        parser.error("--input and --output are required in CLI mode (or use --gui).")

    if args.demo:
        run_demo(args.input, run_capacity=args.run_capacity, k=args.k)
    else:
        run_cli_sort(args)


if __name__ == "__main__":
    main()
