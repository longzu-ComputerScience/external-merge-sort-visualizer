# User Guide — External Merge Sort Visualizer

## Overview

This application sorts large binary files containing IEEE-754 double-precision floating-point numbers (8 bytes each, little-endian) using the **External Merge Sort** algorithm.

It can be operated via:
- **Command Line (CLI)** — for automation and scripting
- **Desktop GUI** — for interactive use and visualisation

---

## File Format

The input/output files are **raw binary** — no headers, no delimiters.

| Property | Value |
|---|---|
| Element type | `double` (IEEE-754) |
| Size per element | 8 bytes |
| Byte order | Little-endian |
| File size | Must be a multiple of 8 |

To inspect a file, you can use the provided Python helper:

```python
from core.binary_io import iter_read_doubles
for val in iter_read_doubles("samples/sample_1000.bin", chunk_size=100):
    print(val)
```

---

## Installation

```bash
# Clone and install
git clone https://github.com/your-username/external-merge-sort-visualizer.git
cd external-merge-sort-visualizer
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

---

## Step 1 — Generate a Sample File

```bash
# Small file for demo (20 values)
python samples/generate_samples.py --count 20 --output samples/tiny.bin --seed 42

# Medium file (100,000 values ≈ 781 KB)
python samples/generate_samples.py --count 100000 --output samples/medium.bin

# Large file (5,000,000 values ≈ 38 MB)
python samples/generate_samples.py --count 5000000 --output samples/large.bin
```

---

## Step 2a — Sort via CLI

```bash
python -m app.main \
  --input samples/medium.bin \
  --output samples/medium_sorted.bin \
  --run-capacity 50000 \
  --buffer 4096 \
  --k 2 \
  --verify
```

Expected output:

```
Input file : samples\medium.bin
Elements   : 100,000 doubles
Run capacity: 50,000
Buffer size : 4,096
Merge fan-in: 2-way

  [████████████████████████████████████████] 100.0%  Sorting complete.

Sorting completed in 0.45s → samples\medium_sorted.bin
Verifying output … OK (100,000 elements, sorted ascending)
```

---

## Step 2b — Sort via GUI

```bash
python -m app.main --gui
```

### GUI Walkthrough

1. **Browse Input** — click "Browse …" next to *Input file* and select your `.bin` file.
2. **Browse Output** — choose where to save the sorted result.
3. **Set Parameters**:
   - *Run capacity*: number of doubles loaded per chunk (e.g. 50,000)
   - *Buffer size*: doubles per I/O buffer during merge (e.g. 4,096)
   - *k-way*: merge fan-in (2, 4, or 8)
4. **Start** — begins sorting in a background thread.
5. **Progress bar** and **Log area** show real-time updates.
6. **Pause / Resume** — control execution flow.
7. After completion, verification runs automatically.

<!-- Screenshot placeholder: ![GUI Main Window](screenshots/gui_main.png) -->

---

## Step 3 — Demo Mode (Small Files Only)

Demo mode visualises every comparison and output during the merge.

### CLI Demo

```bash
python -m app.main --input samples/tiny.bin --output samples/tiny_sorted.bin --demo
```

### GUI Demo

1. Check the **Demo Mode** checkbox before clicking Start.
2. A table appears showing events:
   - **RUN** — an initial sorted run was generated
   - **PASS** — a new merge pass begins
   - **CMP** — two values are being compared (yellow highlight)
   - **OUT** — a value was output to the merge result (green highlight)
   - **DONE** — sorting complete (blue highlight)
3. Use the **Step** button to advance one event at a time.

<!-- Screenshot placeholder: ![Demo Table](screenshots/demo_table.png) -->

---

## Example Run

```bash
# 1. Generate
python samples/generate_samples.py --count 20 --output samples/tiny.bin --seed 42

# 2. Demo
python -m app.main --input samples/tiny.bin --output samples/tiny_sorted.bin --demo

# Output:
# ============================================================
#   DEMO MODE — step-by-step External Merge Sort
# ============================================================
#
# [Run 0] sorted: [-859191.7382, -652282.6501, ..., 959518.3892]
# [Run 1] sorted: [-770728.3744, -624099.2365, ..., 837638.2839]
#
# --- Merge pass 1 (2 runs) ---
#   COMPARE  run0:-859191.7382  vs  run1:-770728.3744
#   OUTPUT   -859191.7382  (from run 0)
#   COMPARE  run0:-652282.6501  vs  run1:-770728.3744
#   OUTPUT   -770728.3744  (from run 1)
#   ...
#
# Final sorted result: [-859191.7382, -770728.3744, ..., 959518.3892]
```

---

## Building a Standalone Executable

```bash
pip install pyinstaller
pyinstaller --noconfirm --onedir --windowed --name ExternalSortApp app/main.py
```

The executable will be in `dist/ExternalSortApp/ExternalSortApp.exe`.

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `File size is not a multiple of 8` | The file is corrupt or not in the expected format. Regenerate with `generate_samples.py`. |
| `ModuleNotFoundError: PySide6` | Run `pip install PySide6`. |
| GUI freezes | This should not happen — sorting runs on a QThread. File a bug report. |
| Out of memory | Reduce `--run-capacity` to a smaller value. |
