"""generate_samples – Create sample binary files for testing.

Usage::

    python samples/generate_samples.py            # default: 1000 doubles
    python samples/generate_samples.py --count 20 --output tiny.bin
    python samples/generate_samples.py --count 500000 --output large.bin

The generated file contains *count* random IEEE-754 doubles in
little-endian format (8 bytes each).
"""

from __future__ import annotations

import argparse
import os
import random
import struct
import sys
from pathlib import Path

# Ensure project root is on path for potential imports
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


def generate_sample(
    output_path: str | Path,
    count: int = 1000,
    low: float = -1e6,
    high: float = 1e6,
    seed: int | None = None,
) -> Path:
    """Generate a binary file of random doubles.

    Parameters
    ----------
    output_path : path-like
        Destination file.
    count : int
        Number of doubles to generate.
    low, high : float
        Range for ``random.uniform``.
    seed : int, optional
        Random seed for reproducibility.

    Returns
    -------
    Path
        The output file path.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if seed is not None:
        random.seed(seed)

    batch = 10_000 
    with open(output_path, "wb") as fh:
        remaining = count
        while remaining > 0:
            n = min(batch, remaining)
            values = [random.uniform(low, high) for _ in range(n)]
            fh.write(struct.pack(f"<{n}d", *values))
            remaining -= n

    size_bytes = output_path.stat().st_size
    print(f"Generated {count:,} doubles → {output_path}  ({size_bytes:,} bytes)")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate sample binary files of doubles.")
    parser.add_argument("--count", "-n", type=int, default=1000, help="Number of doubles.")
    parser.add_argument("--output", "-o", type=str, default="samples/sample_1000.bin", help="Output path.")
    parser.add_argument("--low", type=float, default=-1e6, help="Lower bound.")
    parser.add_argument("--high", type=float, default=1e6, help="Upper bound.")
    parser.add_argument("--seed", type=int, default=None, help="Random seed.")
    args = parser.parse_args()
    generate_sample(args.output, args.count, args.low, args.high, args.seed)


if __name__ == "__main__":
    main()
