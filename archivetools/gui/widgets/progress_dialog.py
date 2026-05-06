from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QProgressBar,
    QSizePolicy,
    QVBoxLayout,
)


def _fmt_size(n: int) -> str:
    if n <= 0:
        return ""
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


class ExtractionProgressDialog(QDialog):
    """
    Non-blocking popup that shows two progress bars:
      • Overall  — file count (works for all formats)
      • Current  — bytes within the active file (ZIP only; indeterminate otherwise)

    Display: archive name · current filename · file counter · percentage.
    """

    def __init__(self, archive_name: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Extracting…")
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setMinimumWidth(460)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )
        self._total_files = 0
        self._build_ui(archive_name)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self, archive_name: str) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        archive_lbl = QLabel(f"<b>{archive_name}</b>")
        archive_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(archive_lbl)

        # Current filename (elided in the middle if long)
        self._file_lbl = QLabel("Preparing…")
        self._file_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._file_lbl.setWordWrap(False)
        self._file_lbl.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        layout.addWidget(self._file_lbl)

        # Overall progress
        self._overall_lbl = QLabel("Overall")
        layout.addWidget(self._overall_lbl)
        self._overall_bar = QProgressBar()
        self._overall_bar.setRange(0, 0)  # indeterminate until we know total
        self._overall_bar.setTextVisible(False)
        layout.addWidget(self._overall_bar)

        # Per-file progress
        self._file_progress_lbl = QLabel("Current file")
        layout.addWidget(self._file_progress_lbl)
        self._file_bar = QProgressBar()
        self._file_bar.setRange(0, 0)  # indeterminate until bytes arrive
        self._file_bar.setTextVisible(False)
        layout.addWidget(self._file_bar)

        # Close button (does not cancel extraction — just hides the dialog)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(self.hide)
        layout.addWidget(btns)

    # ── Public slots ──────────────────────────────────────────────────────────

    def update_file_progress(self, current: int, total: int, filename: str) -> None:
        """Called once per file extracted (file_progress signal)."""
        self._total_files = total

        # Shorten filename for display
        short = filename.split("/")[-1] or filename
        self._file_lbl.setText(short)

        if total > 0:
            pct = int(100 * current / total)
            self._overall_lbl.setText(f"Overall — file {current} of {total}  ({pct}%)")
            self._overall_bar.setRange(0, total)
            self._overall_bar.setValue(current)
        else:
            self._overall_lbl.setText(f"File {current}")
            self._overall_bar.setRange(0, 0)

        # Reset per-file bar for the new file
        self._file_bar.setRange(0, 0)
        self._file_progress_lbl.setText("Current file")

    def update_bytes_progress(self, done: int, size: int) -> None:
        """Called per chunk for the current file (bytes_progress signal, ZIP only)."""
        if size > 0:
            self._file_bar.setRange(0, size)
            self._file_bar.setValue(done)
            self._file_progress_lbl.setText(
                f"Current file — {_fmt_size(done)} / {_fmt_size(size)}"
            )
        else:
            self._file_bar.setRange(0, 0)

    def set_done(self) -> None:
        """Mark both bars as 100% complete before the dialog is closed."""
        if self._total_files > 0:
            self._overall_bar.setRange(0, self._total_files)
            self._overall_bar.setValue(self._total_files)
        self._file_bar.setRange(0, 1)
        self._file_bar.setValue(1)
        self._file_lbl.setText("Done")
        self._overall_lbl.setText("Extraction complete")
        self._file_progress_lbl.setText("")
