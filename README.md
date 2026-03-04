# External Merge Sort Visualizer

A production-ready desktop application that sorts large binary files of IEEE-754 double-precision floating-point numbers using **External Merge Sort**, with a full PySide6 GUI and step-by-step demo mode.

Built as a university assignment for **Advanced Data Structures & Algorithms**.

---

## Table of Contents

- [Algorithm Overview](#algorithm-overview)
- [Features](#features)
- [Project Structure](#project-structure)
- [Installation](#installation)
- [CLI Usage](#cli-usage)
- [GUI Usage](#gui-usage)
- [Building an Executable](#building-an-executable)
- [License](#license)

---

## Algorithm Overview

**External Merge Sort** is designed to sort data that does not fit entirely in RAM. It works in two phases:

### Phase 1 — Run Generation

1. Read the input file in fixed-size chunks of `run_capacity` doubles.
2. Sort each chunk in memory using Python's built-in Timsort.
3. Write each sorted chunk to a temporary **run file** on disk.

### Phase 2 — Multi-Pass Merge

1. Group the run files into batches of `k` (default: 2).
2. Merge each group using buffered I/O:
   - **2-way merge**: classic two-pointer technique.
   - **k-way merge** (k > 2): min-heap (`heapq`) selects the smallest element across `k` input buffers.
3. Write merged results to new run files.
4. Repeat until only **one** sorted run remains — this becomes the output file.

### Key Properties

| Property | Value |
|---|---|
| Time complexity | O(N log N) |
| I/O passes | O(log_k(N / M)) |
| Memory usage | O(M) where M = run_capacity × 8 bytes |
| Merge strategy | Buffered k-way merge with `heapq` |

---

## Features

- **CLI mode** — sort files from the command line with progress bar
- **GUI mode** — full PySide6 desktop application
- **Demo mode** — step-by-step visualisation of every comparison and output during merge
- **Configurable parameters** — run capacity, buffer size, k-way fan-in
- **Verification** — automatically verifies the output is sorted
- **No numpy** — lightweight, uses only `struct` for binary I/O
- **Windows compatible** — tested on Windows 10/11

---

## Project Structure

```
external-merge-sort-visualizer/
├── app/
│   ├── __init__.py
│   ├── main.py            # CLI entry-point & argument parser
│   └── ui_main.py         # PySide6 GUI (QThread workers, demo table)
├── core/
│   ├── __init__.py
│   ├── binary_io.py       # Read/write IEEE-754 doubles (no numpy)
│   ├── run_generation.py  # Phase 1: split input into sorted runs
│   ├── merge.py           # Phase 2: 2-way & k-way buffered merge
│   ├── external_sort.py   # Full pipeline orchestrator
│   ├── demo_steps.py      # Generator-based demo (yields events)
│   └── verify.py          # Post-sort verification
├── samples/
│   └── generate_samples.py
├── docs/
│   └── USER_GUIDE.md
├── README.md
├── requirements.txt
├── .gitignore
└── LICENSE
```

---

## Installation

### Prerequisites

- Python **3.10+**
- pip

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/your-username/external-merge-sort-visualizer.git
cd external-merge-sort-visualizer

# 2. (Recommended) Create a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS / Linux

# 3. Install dependencies
pip install -r requirements.txt
```

---

## CLI Usage

### Generate a sample file

```bash
python samples/generate_samples.py --count 100000 --output samples/data.bin
```

### Sort with default settings

```bash
python -m app.main --input samples/data.bin --output samples/sorted.bin --verify
```

### Sort with custom parameters

```bash
python -m app.main \
  --input samples/data.bin \
  --output samples/sorted.bin \
  --run-capacity 20000 \
  --buffer 8192 \
  --k 4 \
  --verify
```

### Demo mode (small files)

```bash
python samples/generate_samples.py --count 20 --output samples/tiny.bin --seed 42
python -m app.main --input samples/tiny.bin --output samples/tiny_sorted.bin --demo
```

### All CLI options

| Option | Default | Description |
|---|---|---|
| `--input` / `-i` | *required* | Input binary file path |
| `--output` / `-o` | *required* | Output binary file path |
| `--run-capacity` | 50000 | Doubles per in-memory run |
| `--buffer` | 4096 | Doubles per I/O buffer |
| `--k` | 2 | Merge fan-in (2, 4, or 8) |
| `--demo` | off | Step-by-step demo output |
| `--verify` | off | Verify output is sorted |
| `--keep-runs` | off | Preserve temp run files |
| `--gui` | off | Launch GUI instead of CLI |

---

## GUI Usage

```bash
python -m app.main --gui
```

1. **Select input file** using the Browse button.
2. **Select output file** location.
3. Adjust **Run capacity**, **Buffer size**, and **k-way** as needed.
4. (Optional) Check **Demo Mode** to visualise the merge step by step.
5. Click **Start**.
6. Use **Pause / Resume** to control execution.
7. In Demo Mode, use **Step** to advance one event at a time.
8. Watch the **progress bar** and **log area** for status updates.
9. The demo table shows every compare and output event with colour highlighting.

---

## Building an Executable

Use [PyInstaller](https://pyinstaller.org/) to create a standalone `.exe`:

```bash
pip install pyinstaller
pyinstaller --noconfirm --onedir --windowed --name ExternalSortApp app/main.py
```

The output will be in `dist/ExternalSortApp/`. Run `ExternalSortApp.exe` directly.

---

## License

MIT License — see [LICENSE](LICENSE) for details.
