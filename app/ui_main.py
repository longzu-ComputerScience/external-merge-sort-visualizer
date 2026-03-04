"""ui_main – PySide6 desktop GUI for External Merge Sort Visualizer.

Provides:
* File selectors (input / output)
* Parameter spin-boxes (run_capacity, buffer_size, k)
* Demo-mode checkbox and step button
* Start / Pause / Resume controls
* Progress bar + log area
* QThread-based sorting (no UI freeze)
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Optional

from PySide6.QtCore import (
    Qt,
    QThread,
    Signal,
    Slot,
    QMutex,
    QWaitCondition,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtGui import QColor, QFont

# Ensure project root is importable
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.external_sort import external_merge_sort, SortProgress
from core.verify import verify_sorted, count_elements
from core.demo_steps import (
    demo_merge_sort,
    DemoEvent,
    RunGeneratedEvent,
    PassStartEvent,
    CompareEvent,
    OutputEvent,
    DoneEvent,
)
from core.binary_io import validate_file


# ═══════════════════════════════════════════════════════════════════════════
# Worker thread — normal sort
# ═══════════════════════════════════════════════════════════════════════════

class SortWorker(QThread):
    """Runs external_merge_sort in a background thread."""

    progress = Signal(str, float)       # (detail, percent)
    finished = Signal(bool, str)        # (success, message)

    def __init__(
        self,
        input_path: str,
        output_path: str,
        run_capacity: int,
        buffer_size: int,
        k: int,
        keep_runs: bool,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.input_path = input_path
        self.output_path = output_path
        self.run_capacity = run_capacity
        self.buffer_size = buffer_size
        self.k = k
        self.keep_runs = keep_runs
        self._cancel = False
        self._paused = False
        self._mutex = QMutex()
        self._pause_cond = QWaitCondition()

    # -- pause / resume / cancel ------------------------------------------

    def pause(self) -> None:
        self._mutex.lock()
        self._paused = True
        self._mutex.unlock()

    def resume(self) -> None:
        self._mutex.lock()
        self._paused = False
        self._mutex.unlock()
        self._pause_cond.wakeAll()

    def cancel(self) -> None:
        self._cancel = True
        self.resume()  # unblock if paused

    def _check_cancel(self) -> bool:
        # Also handle pause
        self._mutex.lock()
        while self._paused and not self._cancel:
            self._pause_cond.wait(self._mutex)
        self._mutex.unlock()
        return self._cancel

    # -- thread entry ------------------------------------------------------

    def run(self) -> None:
        try:
            t0 = time.perf_counter()

            def _cb(p: SortProgress) -> None:
                self.progress.emit(p.detail, p.percent)

            external_merge_sort(
                input_path=self.input_path,
                output_path=self.output_path,
                run_capacity=self.run_capacity,
                buffer_size=self.buffer_size,
                k=self.k,
                keep_runs=self.keep_runs,
                progress_cb=_cb,
                cancel_check=self._check_cancel,
            )
            elapsed = time.perf_counter() - t0
            self.finished.emit(True, f"Sorting completed in {elapsed:.2f}s")
        except RuntimeError as exc:
            self.finished.emit(False, str(exc))
        except Exception as exc:
            self.finished.emit(False, f"Error: {exc}")


# ═══════════════════════════════════════════════════════════════════════════
# Worker thread — demo mode
# ═══════════════════════════════════════════════════════════════════════════

class DemoWorker(QThread):
    """Runs the demo generator and emits events one at a time.

    In *auto* mode events are emitted with a small delay.
    When stepping, the thread waits on a condition variable until
    ``step_one()`` is called.
    """

    event_ready = Signal(object)    # DemoEvent
    finished = Signal(bool, str)

    def __init__(
        self,
        input_path: str,
        run_capacity: int,
        k: int,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.input_path = input_path
        self.run_capacity = run_capacity
        self.k = k
        self._cancel = False
        self._paused = False  # start in auto-play mode
        self._stepping = False
        self._mutex = QMutex()
        self._step_cond = QWaitCondition()

    # -- control -----------------------------------------------------------

    def set_auto(self) -> None:
        """Switch to auto-play: events emitted with delay."""
        self._mutex.lock()
        self._stepping = False
        self._paused = False
        self._mutex.unlock()
        self._step_cond.wakeAll()

    def set_stepping(self) -> None:
        """Switch to stepping mode."""
        self._mutex.lock()
        self._stepping = True
        self._paused = True
        self._mutex.unlock()

    def step_one(self) -> None:
        """Advance exactly one event (when in stepping mode)."""
        self._mutex.lock()
        self._paused = False
        self._mutex.unlock()
        self._step_cond.wakeAll()

    def pause(self) -> None:
        self._mutex.lock()
        self._paused = True
        self._mutex.unlock()

    def resume(self) -> None:
        self._mutex.lock()
        self._paused = False
        self._mutex.unlock()
        self._step_cond.wakeAll()

    def cancel(self) -> None:
        self._cancel = True
        self._mutex.lock()
        self._paused = False
        self._mutex.unlock()
        self._step_cond.wakeAll()

    # -- thread entry ------------------------------------------------------

    def run(self) -> None:
        try:
            gen = demo_merge_sort(self.input_path, self.run_capacity, self.k)
            for event in gen:
                if self._cancel:
                    break

                # Wait if paused / stepping
                self._mutex.lock()
                while self._paused and not self._cancel:
                    self._step_cond.wait(self._mutex)
                self._mutex.unlock()

                if self._cancel:
                    break

                self.event_ready.emit(event)

                if self._stepping:
                    self._mutex.lock()
                    self._paused = True
                    self._mutex.unlock()
                else:
                    self.msleep(120)  # auto-play delay

            if self._cancel:
                self.finished.emit(False, "Demo cancelled.")
            else:
                self.finished.emit(True, "Demo completed.")
        except Exception as exc:
            self.finished.emit(False, f"Demo error: {exc}")


# ═══════════════════════════════════════════════════════════════════════════
# Main Window
# ═══════════════════════════════════════════════════════════════════════════

class MainWindow(QMainWindow):
    """Primary application window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("External Merge Sort Visualizer")
        self.setMinimumSize(960, 700)
        self._worker: Optional[SortWorker] = None
        self._demo_worker: Optional[DemoWorker] = None
        self._build_ui()
        self._connect_signals()
        self._set_idle_state()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)

        # ── File selectors ────────────────────────────────────────────
        file_group = QGroupBox("Files")
        fg_layout = QVBoxLayout(file_group)

        row_in = QHBoxLayout()
        row_in.addWidget(QLabel("Input file:"))
        self.input_edit = QLineEdit()
        self.input_edit.setReadOnly(True)
        row_in.addWidget(self.input_edit, 1)
        self.btn_browse_in = QPushButton("Browse …")
        row_in.addWidget(self.btn_browse_in)
        fg_layout.addLayout(row_in)

        row_out = QHBoxLayout()
        row_out.addWidget(QLabel("Output file:"))
        self.output_edit = QLineEdit()
        self.output_edit.setReadOnly(True)
        row_out.addWidget(self.output_edit, 1)
        self.btn_browse_out = QPushButton("Browse …")
        row_out.addWidget(self.btn_browse_out)
        fg_layout.addLayout(row_out)

        root_layout.addWidget(file_group)

        # ── Parameters ────────────────────────────────────────────────
        param_group = QGroupBox("Parameters")
        pg_layout = QHBoxLayout(param_group)

        pg_layout.addWidget(QLabel("Run capacity:"))
        self.spin_run_cap = QSpinBox()
        self.spin_run_cap.setRange(2, 10_000_000)
        self.spin_run_cap.setValue(50_000)
        self.spin_run_cap.setSingleStep(1000)
        pg_layout.addWidget(self.spin_run_cap)

        pg_layout.addWidget(QLabel("Buffer size:"))
        self.spin_buffer = QSpinBox()
        self.spin_buffer.setRange(1, 1_000_000)
        self.spin_buffer.setValue(4096)
        self.spin_buffer.setSingleStep(512)
        pg_layout.addWidget(self.spin_buffer)

        pg_layout.addWidget(QLabel("k-way:"))
        self.combo_k = QComboBox()
        self.combo_k.addItems(["2", "4", "8"])
        pg_layout.addWidget(self.combo_k)

        self.chk_demo = QCheckBox("Demo Mode")
        pg_layout.addWidget(self.chk_demo)

        pg_layout.addStretch()
        root_layout.addWidget(param_group)

        # ── Buttons ───────────────────────────────────────────────────
        btn_layout = QHBoxLayout()
        self.btn_start = QPushButton("Start")
        self.btn_pause = QPushButton("Pause")
        self.btn_resume = QPushButton("Resume")
        self.btn_step = QPushButton("Step")
        self.btn_exit = QPushButton("Exit")
        for b in (self.btn_start, self.btn_pause, self.btn_resume, self.btn_step, self.btn_exit):
            b.setMinimumWidth(90)
            btn_layout.addWidget(b)
        btn_layout.addStretch()
        root_layout.addLayout(btn_layout)

        # ── Progress bar ──────────────────────────────────────────────
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1000)
        self.progress_bar.setValue(0)
        root_layout.addWidget(self.progress_bar)

        # ── Splitter: log + demo table ────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Vertical)

        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setFont(QFont("Consolas", 9))
        splitter.addWidget(self.log_area)

        self.demo_table = QTableWidget()
        self.demo_table.setColumnCount(4)
        self.demo_table.setHorizontalHeaderLabels(["Event", "Value(s)", "From", "Merged so far"])
        self.demo_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.demo_table.setVisible(False)  # hidden until demo mode
        splitter.addWidget(self.demo_table)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        root_layout.addWidget(splitter, 1)

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        self.btn_browse_in.clicked.connect(self._browse_input)
        self.btn_browse_out.clicked.connect(self._browse_output)
        self.btn_start.clicked.connect(self._on_start)
        self.btn_pause.clicked.connect(self._on_pause)
        self.btn_resume.clicked.connect(self._on_resume)
        self.btn_step.clicked.connect(self._on_step)
        self.btn_exit.clicked.connect(self._on_exit)
        self.chk_demo.toggled.connect(self._on_demo_toggled)

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------

    def _set_idle_state(self) -> None:
        self.btn_start.setEnabled(True)
        self.btn_pause.setEnabled(False)
        self.btn_resume.setEnabled(False)
        self.btn_step.setEnabled(False)
        self.btn_exit.setEnabled(False)

    def _set_running_state(self) -> None:
        self.btn_start.setEnabled(False)
        self.btn_pause.setEnabled(True)
        self.btn_resume.setEnabled(False)
        self.btn_step.setEnabled(False)
        self.btn_exit.setEnabled(True)

    def _set_paused_state(self) -> None:
        self.btn_start.setEnabled(False)
        self.btn_pause.setEnabled(False)
        self.btn_resume.setEnabled(True)
        self.btn_step.setEnabled(self.chk_demo.isChecked())
        self.btn_exit.setEnabled(True)

    # ------------------------------------------------------------------
    # Slots — file browsing
    # ------------------------------------------------------------------

    @Slot()
    def _browse_input(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Input Binary File", "", "Binary Files (*.bin);;All Files (*)"
        )
        if path:
            self.input_edit.setText(path)

    @Slot()
    def _browse_output(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Select Output File", "", "Binary Files (*.bin);;All Files (*)"
        )
        if path:
            self.output_edit.setText(path)

    # ------------------------------------------------------------------
    # Slots — controls
    # ------------------------------------------------------------------

    @Slot()
    def _on_demo_toggled(self, checked: bool) -> None:
        self.demo_table.setVisible(checked)

    @Slot()
    def _on_start(self) -> None:
        input_path = self.input_edit.text().strip()
        output_path = self.output_edit.text().strip()
        if not input_path:
            QMessageBox.warning(self, "Missing input", "Please select an input file.")
            return
        if not output_path:
            QMessageBox.warning(self, "Missing output", "Please select an output file.")
            return

        # Validate
        try:
            n = validate_file(input_path)
        except (FileNotFoundError, ValueError) as exc:
            QMessageBox.critical(self, "Invalid file", str(exc))
            return

        if Path(input_path).resolve() == Path(output_path).resolve():
            QMessageBox.critical(self, "Invalid", "Output must differ from input.")
            return

        self.log_area.clear()
        self.demo_table.setRowCount(0)
        self.progress_bar.setValue(0)
        self._log(f"Input: {input_path}  ({n:,} doubles)")

        run_cap = self.spin_run_cap.value()
        buf_size = self.spin_buffer.value()
        k = int(self.combo_k.currentText())

        if self.chk_demo.isChecked():
            self._start_demo(input_path, run_cap, k)
        else:
            self._start_sort(input_path, output_path, run_cap, buf_size, k)

    @Slot()
    def _on_pause(self) -> None:
        if self._worker:
            self._worker.pause()
        if self._demo_worker:
            self._demo_worker.pause()
        self._set_paused_state()
        self._log("⏸  Paused.")

    @Slot()
    def _on_resume(self) -> None:
        if self._worker:
            self._worker.resume()
        if self._demo_worker:
            self._demo_worker.set_auto()
        self._set_running_state()
        self._log("▶  Resumed.")

    @Slot()
    def _on_step(self) -> None:
        if self._demo_worker:
            self._demo_worker.set_stepping()
            self._demo_worker.step_one()

    @Slot()
    def _on_exit(self) -> None:
        """Cancel any running sort/demo and return to idle."""
        if self._worker:
            self._worker.cancel()
            self._log("⛔  Sort cancelled.")
        if self._demo_worker:
            self._demo_worker.cancel()
            self._log("⛔  Demo cancelled.")

    # ------------------------------------------------------------------
    # Normal sort
    # ------------------------------------------------------------------

    def _start_sort(
        self, input_path: str, output_path: str, run_cap: int, buf: int, k: int
    ) -> None:
        self._log(f"Starting sort  (run_capacity={run_cap}, buffer={buf}, k={k})")
        self._set_running_state()

        self._worker = SortWorker(input_path, output_path, run_cap, buf, k, False, self)
        self._worker.progress.connect(self._on_sort_progress)
        self._worker.finished.connect(self._on_sort_finished)
        self._worker.start()

    @Slot(str, float)
    def _on_sort_progress(self, detail: str, percent: float) -> None:
        self.progress_bar.setValue(int(percent * 10))
        self._log(f"[{percent:5.1f}] {detail}")

    @Slot(bool, str)
    def _on_sort_finished(self, success: bool, msg: str) -> None:
        self._worker = None
        self._set_idle_state()
        self.progress_bar.setValue(1000 if success else 0)
        self._log(msg)

        if success:
            output_path = self.output_edit.text().strip()
            if output_path and Path(output_path).exists():
                ok = verify_sorted(output_path)
                n = count_elements(output_path)
                if ok:
                    self._log(f"Verification: PASSED ({n:,} elements, sorted ascending)")
                else:
                    self._log("Verification: FAILED — output is NOT sorted!")

    # ------------------------------------------------------------------
    # Demo sort
    # ------------------------------------------------------------------

    def _start_demo(self, input_path: str, run_cap: int, k: int) -> None:
        self._log(f"Starting demo  (run_capacity={run_cap}, k={k})")
        self._set_running_state()

        self._demo_worker = DemoWorker(input_path, run_cap, k, self)
        self._demo_worker.event_ready.connect(self._on_demo_event)
        self._demo_worker.finished.connect(self._on_demo_finished)
        self._demo_worker.start()

    @Slot(object)
    def _on_demo_event(self, event: DemoEvent) -> None:
        row = self.demo_table.rowCount()
        self.demo_table.insertRow(row)

        if isinstance(event, RunGeneratedEvent):
            vals = ", ".join(f"{v:.4f}" for v in event.values)
            self._set_demo_row(row, "RUN", vals, f"run {event.run_index}", "")
            self._log(f"[Run {event.run_index}] {vals}")

        elif isinstance(event, PassStartEvent):
            self._set_demo_row(
                row, "PASS", f"Pass {event.pass_number}", f"{event.num_runs} runs", ""
            )
            self._log(f"--- Pass {event.pass_number} ({event.num_runs} runs) ---")

        elif isinstance(event, CompareEvent):
            self._set_demo_row(
                row,
                "CMP",
                f"{event.left_value:.4f} vs {event.right_value:.4f}",
                f"run{event.left_run} / run{event.right_run}",
                "",
            )
            self._highlight_row(row, QColor(80, 80, 40), QColor(255, 220, 120))

        elif isinstance(event, OutputEvent):
            merged = ", ".join(f"{v:.4f}" for v in event.merged_so_far[-8:])
            self._set_demo_row(
                row, "OUT", f"{event.value:.4f}", f"run {event.from_run}", merged
            )
            self._highlight_row(row, QColor(35, 75, 45), QColor(140, 230, 140))

        elif isinstance(event, DoneEvent):
            vals = ", ".join(f"{v:.4f}" for v in event.sorted_values)
            self._set_demo_row(row, "DONE", vals, "", "")
            self._highlight_row(row, QColor(30, 60, 90), QColor(130, 190, 255))
            self._log("Demo finished — see table above.")

        self.demo_table.scrollToBottom()

    @Slot(bool, str)
    def _on_demo_finished(self, success: bool, msg: str) -> None:
        self._demo_worker = None
        self._set_idle_state()
        self.progress_bar.setValue(1000 if success else 0)
        self._log(msg)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _log(self, text: str) -> None:
        self.log_area.append(text)

    def _set_demo_row(self, row: int, *cols: str) -> None:
        for c, text in enumerate(cols):
            item = QTableWidgetItem(text)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.demo_table.setItem(row, c, item)

    def _highlight_row(self, row: int, bg: QColor, fg: QColor | None = None) -> None:
        for c in range(self.demo_table.columnCount()):
            item = self.demo_table.item(row, c)
            if item:
                item.setBackground(bg)
                if fg is not None:
                    item.setForeground(fg)

    # ------------------------------------------------------------------
    # Cleanup on close
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self._worker:
            self._worker.cancel()
            self._worker.wait()
        if self._demo_worker:
            self._demo_worker.cancel()
            self._demo_worker.wait()
        event.accept()


# ═══════════════════════════════════════════════════════════════════════════
# Entry-point
# ═══════════════════════════════════════════════════════════════════════════

def run_gui() -> None:
    """Create the QApplication and show the main window."""
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run_gui()
