from __future__ import annotations

import os

from PySide6.QtCore import QSizeF, Qt, QUrl, Signal
from PySide6.QtGui import QFontDatabase, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFormLayout,
    QFrame,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSlider,
    QStackedWidget,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

try:
    from PySide6.QtPdf import QPdfDocument
    from PySide6.QtPdfWidgets import QPdfView

    _HAS_PDF = True
except ImportError:
    _HAS_PDF = False

try:
    from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
    from PySide6.QtMultimediaWidgets import QGraphicsVideoItem

    _HAS_MULTIMEDIA = True
except ImportError:
    _HAS_MULTIMEDIA = False

from archivetools.gui.theme import LIGHT, ThemeColors

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".ico", ".tiff"}
_TEXT_EXTS = {
    ".txt",
    ".md",
    ".py",
    ".js",
    ".ts",
    ".css",
    ".html",
    ".xml",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
    ".log",
    ".sh",
    ".bash",
    ".diff",
    ".patch",
    ".rst",
    ".csv",
    ".c",
    ".h",
    ".cpp",
    ".java",
    ".rb",
    ".go",
    ".zsh",
    ".fish",
}
_PDF_EXTS = {".pdf"}
_AUDIO_EXTS = {".mp3", ".wav", ".ogg", ".flac", ".aac", ".m4a", ".opus", ".wma"}
_VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v", ".flv", ".wmv"}

_RIGHT_PLACEHOLDER = 0
_RIGHT_IMAGE = 1
_RIGHT_TEXT = 2
_RIGHT_UNSUPPORTED = 3
_RIGHT_LOADING_PREVIEW = 4
_RIGHT_INFO = 5
_RIGHT_LOADING_INFO = 6
_RIGHT_PDF = 7
_RIGHT_MEDIA = 8


class _ClickSlider(QSlider):
    """QSlider that jumps to the exact click position instead of paging by a step."""

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            val = QStyle.sliderValueFromPosition(
                self.minimum(),
                self.maximum(),
                int(event.position().x()),
                self.width(),
            )
            self.setValue(val)
            self.sliderMoved.emit(val)
        super().mousePressEvent(event)


class _ScaledImageLabel(QLabel):
    """QLabel that rescales its pixmap to fill available space on every resize."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._source: QPixmap | None = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(1, 1)

    def set_source(self, pixmap: QPixmap) -> None:
        self._source = pixmap
        self._rescale()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._rescale()

    def _rescale(self) -> None:
        if self._source is None or self._source.isNull():
            return
        w, h = self.width(), self.height()
        if w < 1 or h < 1:
            return
        scaled = self._source.scaled(
            w,
            h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(scaled)


class _VideoView(QGraphicsView):
    """QGraphicsView wrapper for video — avoids native-window sizing/layout bugs."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        scene = QGraphicsScene(self)
        self.setScene(scene)
        if _HAS_MULTIMEDIA:
            self._item: QGraphicsVideoItem = QGraphicsVideoItem()
            scene.addItem(self._item)
        else:
            self._item = None  # type: ignore[assignment]
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("background: black; border: none;")
        self.setMinimumSize(1, 1)

    def video_item(self):
        return self._item

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        w, h = self.width(), self.height()
        if self._item is not None and w > 0 and h > 0:
            self._item.setSize(QSizeF(w, h))
            self.setSceneRect(0, 0, w, h)


class PreviewPane(QWidget):
    """
    Right-pane preview and archive-info display.

    Owns the [Preview] / [Info] toggle buttons, entry filename label, and a
    stacked widget with pages for image, text, PDF, audio/video, info, and
    loading/placeholder states.

    Signals
    -------
    info_requested():
        User switched to [Info] tab and no cached info is available.
        Connect to a slot that starts an ``InfoWorker``.
    preview_requested(str):
        User switched back to [Preview] tab while an entry is selected.
        Carries the archive entry path.  Connect to start a preview worker.
    """

    info_requested = Signal()
    preview_requested = Signal(str)

    def __init__(
        self,
        colors: ThemeColors | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._colors: ThemeColors = colors or LIGHT
        self._current_entry: str = ""
        self._info_cached: bool = False
        self._media_player = None
        self._media_audio = None
        self._pdf_doc = None
        self._pdf_view = None
        self._build_ui()
        self.set_theme(self._colors)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(4)

        # Header: [Preview] [Info] + entry filename
        header = QHBoxLayout()
        header.setSpacing(2)

        self._preview_btn = QPushButton("Preview")
        self._preview_btn.setCheckable(True)
        self._preview_btn.setFlat(True)
        self._preview_btn.setChecked(True)

        self._info_btn = QPushButton("Info")
        self._info_btn.setCheckable(True)
        self._info_btn.setFlat(True)

        self._mode_group = QButtonGroup(self)
        self._mode_group.setExclusive(True)
        self._mode_group.addButton(self._preview_btn, 0)
        self._mode_group.addButton(self._info_btn, 1)
        self._mode_group.idClicked.connect(self._on_mode_clicked)

        self._entry_lbl = QLabel("")
        self._entry_lbl.setStyleSheet("color:#888888;font-size:11px;")

        header.addWidget(self._preview_btn)
        header.addWidget(self._info_btn)
        header.addSpacing(8)
        header.addWidget(self._entry_lbl, stretch=1)

        # Stacked content
        self._stack = QStackedWidget()

        placeholder = QLabel("Select a file to preview")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet("color:#AAAAAA;font-size:12px;")
        self._stack.addWidget(placeholder)  # 0 _RIGHT_PLACEHOLDER

        self._img_label = _ScaledImageLabel()
        self._stack.addWidget(self._img_label)  # 1 _RIGHT_IMAGE

        self._text_view = QPlainTextEdit()
        self._text_view.setReadOnly(True)
        self._text_view.setMaximumBlockCount(5000)
        self._text_view.setFont(
            QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        )
        self._stack.addWidget(self._text_view)  # 2 _RIGHT_TEXT

        unsupported = QLabel("No preview available")
        unsupported.setAlignment(Qt.AlignmentFlag.AlignCenter)
        unsupported.setStyleSheet("color:#AAAAAA;font-size:12px;")
        self._stack.addWidget(unsupported)  # 3 _RIGHT_UNSUPPORTED

        loading_prev = QLabel("Loading preview…")
        loading_prev.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_prev.setStyleSheet("color:#AAAAAA;font-size:12px;")
        self._stack.addWidget(loading_prev)  # 4 _RIGHT_LOADING_PREVIEW

        self._stack.addWidget(self._build_info_widget())  # 5 _RIGHT_INFO

        loading_info = QLabel("Loading archive info…")
        loading_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_info.setStyleSheet("color:#AAAAAA;font-size:12px;")
        self._stack.addWidget(loading_info)  # 6 _RIGHT_LOADING_INFO

        # PDF page
        if _HAS_PDF:
            self._pdf_doc = QPdfDocument(self)
            self._pdf_view = QPdfView(self)
            self._pdf_view.setDocument(self._pdf_doc)
            self._pdf_view.setPageMode(QPdfView.PageMode.MultiPage)
            self._stack.addWidget(self._pdf_view)  # 7 _RIGHT_PDF
        else:
            pdf_lbl = QLabel(
                "PDF preview requires PySide6 PDF modules\n(pip install pyside6-addons)"
            )
            pdf_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pdf_lbl.setStyleSheet("color:#AAAAAA;font-size:12px;")
            self._stack.addWidget(pdf_lbl)  # 7 _RIGHT_PDF

        # Media page
        if _HAS_MULTIMEDIA:
            media_widget = QWidget()
            mlayout = QVBoxLayout(media_widget)
            mlayout.setContentsMargins(4, 4, 4, 4)
            mlayout.setSpacing(4)

            self._video_view = _VideoView()
            mlayout.addWidget(self._video_view, stretch=1)

            self._audio_lbl = QLabel("♫")
            self._audio_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._audio_lbl.setStyleSheet("font-size:48px;color:#888888;")
            self._audio_lbl.setVisible(False)
            mlayout.addWidget(self._audio_lbl, stretch=1)

            self._seek_bar = _ClickSlider(Qt.Orientation.Horizontal)
            self._seek_bar.setRange(0, 0)
            self._seek_bar.setEnabled(False)
            self._seek_bar.sliderMoved.connect(self._on_seek_moved)
            mlayout.addWidget(self._seek_bar)

            ctrl = QHBoxLayout()
            ctrl.setSpacing(4)

            self._play_btn = QPushButton("▶")
            self._play_btn.setFixedWidth(30)
            self._play_btn.setEnabled(False)
            self._play_btn.clicked.connect(self._toggle_playback)

            self._time_lbl = QLabel("—")
            self._time_lbl.setStyleSheet("font-size:11px;color:#888888;")

            self._mute_btn = QToolButton()
            self._mute_btn.setText("🔊")
            self._mute_btn.setCheckable(True)
            self._mute_btn.setToolTip("Mute / unmute")
            self._mute_btn.toggled.connect(self._on_mute_toggled)

            self._vol_slider = _ClickSlider(Qt.Orientation.Horizontal)
            self._vol_slider.setRange(0, 100)
            self._vol_slider.setValue(100)
            self._vol_slider.setFixedWidth(60)
            self._vol_slider.setToolTip("Volume")
            self._vol_slider.valueChanged.connect(self._on_volume_changed)

            self._speed_combo = QComboBox()
            for _lbl, _rate in (
                ("0.25×", 0.25),
                ("0.5×", 0.5),
                ("0.75×", 0.75),
                ("1×", 1.0),
                ("1.25×", 1.25),
                ("1.5×", 1.5),
                ("2×", 2.0),
            ):
                self._speed_combo.addItem(_lbl, _rate)
            self._speed_combo.setCurrentIndex(3)
            self._speed_combo.setFixedWidth(66)
            self._speed_combo.setToolTip("Playback speed")
            self._speed_combo.currentIndexChanged.connect(self._on_speed_changed)

            ctrl.addWidget(self._play_btn)
            ctrl.addWidget(self._time_lbl, stretch=1)
            ctrl.addWidget(self._mute_btn)
            ctrl.addWidget(self._vol_slider)
            ctrl.addWidget(self._speed_combo)
            mlayout.addLayout(ctrl)

            self._media_player = QMediaPlayer()
            self._media_audio = QAudioOutput()
            self._media_player.setAudioOutput(self._media_audio)
            self._media_player.setVideoOutput(self._video_view.video_item())
            self._media_player.playbackStateChanged.connect(self._on_playback_state)
            self._media_player.positionChanged.connect(self._on_position_changed)
            self._media_player.durationChanged.connect(self._on_duration_changed)
            self._stack.addWidget(media_widget)  # 8 _RIGHT_MEDIA
        else:
            media_lbl = QLabel(
                "Media preview requires PySide6 multimedia modules\n"
                "(pip install pyside6-addons)"
            )
            media_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            media_lbl.setStyleSheet("color:#AAAAAA;font-size:12px;")
            self._stack.addWidget(media_lbl)  # 8 _RIGHT_MEDIA

        vbox.addLayout(header)
        vbox.addWidget(self._stack, stretch=1)

    def _build_info_widget(self) -> QWidget:
        w = QWidget()
        vbox = QVBoxLayout(w)
        vbox.setContentsMargins(8, 8, 8, 8)
        vbox.setSpacing(4)

        self._info_title_lbl = QLabel("Archive Info")
        vbox.addWidget(self._info_title_lbl)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(4)
        form.setContentsMargins(0, 4, 0, 0)

        def _val() -> QLabel:
            return QLabel("—")

        self._info_format = _val()
        self._info_files = _val()
        self._info_compressed = _val()
        self._info_uncompressed = _val()
        self._info_ratio = _val()
        self._info_encrypted = _val()
        self._info_comment = _val()
        self._info_comment.setWordWrap(True)
        self._info_row_labels: list[QLabel] = []

        for label, widget in [
            ("Format:", self._info_format),
            ("Files:", self._info_files),
            ("Compressed:", self._info_compressed),
            ("Original:", self._info_uncompressed),
            ("Ratio:", self._info_ratio),
            ("Encrypted:", self._info_encrypted),
            ("Comment:", self._info_comment),
        ]:
            row_lbl = QLabel(label)
            self._info_row_labels.append(row_lbl)
            form.addRow(row_lbl, widget)

        vbox.addLayout(form)
        vbox.addStretch()
        return w

    # ── Public interface ──────────────────────────────────────────────────────

    def set_entry(self, archive_entry_path: str) -> None:
        """Update the filename label. Does not start a preview worker."""
        self._current_entry = archive_entry_path
        if archive_entry_path and not archive_entry_path.endswith("/"):
            self._entry_lbl.setText(os.path.basename(archive_entry_path))
        else:
            self._entry_lbl.setText("")

    def show_file(self, file_path: str) -> None:
        """Display preview for file_path (already extracted to a temp directory)."""
        ext = os.path.splitext(file_path)[1].lower()

        if ext in _IMAGE_EXTS:
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                self._img_label.set_source(pixmap)
                self._stack.setCurrentIndex(_RIGHT_IMAGE)
                return

        if ext in _TEXT_EXTS:
            try:
                with open(file_path, encoding="utf-8", errors="replace") as fh:
                    content = fh.read(100_000)
                self._text_view.setPlainText(content)
                self._stack.setCurrentIndex(_RIGHT_TEXT)
                return
            except OSError:
                pass

        if ext in _PDF_EXTS:
            if _HAS_PDF and self._pdf_doc is not None:
                self._pdf_doc.close()
                self._pdf_doc.load(file_path)
            self._stack.setCurrentIndex(_RIGHT_PDF)
            return

        if ext in _AUDIO_EXTS or ext in _VIDEO_EXTS:
            if self._media_player is not None:
                is_video = ext in _VIDEO_EXTS
                self._video_view.setVisible(is_video)
                self._audio_lbl.setVisible(not is_video)
                self._seek_bar.setRange(0, 0)
                self._seek_bar.setValue(0)
                self._seek_bar.setEnabled(False)
                self._play_btn.setEnabled(False)
                self._play_btn.setText("▶")
                self._time_lbl.setText("—")
                self._media_player.setSource(QUrl.fromLocalFile(file_path))
                self._media_player.play()
            self._stack.setCurrentIndex(_RIGHT_MEDIA)
            return

        self._stack.setCurrentIndex(_RIGHT_UNSUPPORTED)

    def show_info(self, info) -> None:
        """Display archive metadata on the info page."""
        self._info_cached = True

        def _fmt(n: int) -> str:
            if n < 0:
                return "—"
            for unit in ("B", "KB", "MB", "GB"):
                if n < 1024:
                    return f"{n:.1f} {unit}"
                n //= 1024  # type: ignore[assignment]
            return f"{n} TB"

        self._info_format.setText(info.format_name)
        self._info_files.setText(str(info.file_count))
        self._info_compressed.setText(_fmt(info.compressed_size))
        self._info_uncompressed.setText(_fmt(info.uncompressed_size))
        if info.compressed_size > 0 and info.uncompressed_size > 0:
            self._info_ratio.setText(
                f"{info.compressed_size / info.uncompressed_size:.1%}"
            )
        else:
            self._info_ratio.setText("—")
        self._info_encrypted.setText("Yes" if info.is_encrypted else "No")
        self._info_comment.setText(info.comment or "—")
        self._stack.setCurrentIndex(_RIGHT_INFO)

    def show_info_error(self, msg: str) -> None:
        self._info_format.setText(f"Error: {msg[:40]}")
        self._stack.setCurrentIndex(_RIGHT_INFO)

    def show_loading_preview(self) -> None:
        self._stack.setCurrentIndex(_RIGHT_LOADING_PREVIEW)

    def show_loading_info(self) -> None:
        self._stack.setCurrentIndex(_RIGHT_LOADING_INFO)

    def show_placeholder(self) -> None:
        self._stack.setCurrentIndex(_RIGHT_PLACEHOLDER)

    def show_unsupported(self) -> None:
        self._stack.setCurrentIndex(_RIGHT_UNSUPPORTED)

    def clear(self) -> None:
        """Reset to placeholder state and stop any media."""
        self.stop_media()
        self._current_entry = ""
        self._info_cached = False
        self._entry_lbl.setText("")
        self._preview_btn.setChecked(True)
        self._stack.setCurrentIndex(_RIGHT_PLACEHOLDER)
        self._clear_info_labels()

    def stop_media(self) -> None:
        if self._media_player is not None:
            self._media_player.stop()

    def is_preview_mode(self) -> bool:
        return self._preview_btn.isChecked()

    def current_entry(self) -> str:
        return self._current_entry

    # ── Theme ─────────────────────────────────────────────────────────────────

    def set_theme(self, c: ThemeColors) -> None:
        self._colors = c
        for btn in (self._preview_btn, self._info_btn):
            btn.setStyleSheet(
                f"QPushButton{{border:1px solid {c['border']};border-radius:4px;"
                f"padding:3px 10px;font-size:12px;"
                f"background:{c['surface']};color:{c['text_secondary']};}}"
                f"QPushButton:checked{{"
                f"color:{c['accent']};border-color:{c['accent']};background:{c['surface']};}}"
            )
        self._entry_lbl.setStyleSheet(f"color:{c['text_secondary']};font-size:11px;")
        if hasattr(self, "_info_title_lbl"):
            self._info_title_lbl.setStyleSheet(
                f"font-size:13px;font-weight:600;color:{c['text']};"
            )
        for lbl in getattr(self, "_info_row_labels", []):
            lbl.setStyleSheet(f"color:{c['text_secondary']};font-size:12px;")
        for lbl in (
            self._info_format,
            self._info_files,
            self._info_compressed,
            self._info_uncompressed,
            self._info_ratio,
            self._info_encrypted,
            self._info_comment,
        ):
            lbl.setStyleSheet(f"font-size:12px;color:{c['text']};")

    # ── Private slots ─────────────────────────────────────────────────────────

    def _on_mode_clicked(self, mode_id: int) -> None:
        if mode_id == 1:  # Info
            if self._info_cached:
                self._stack.setCurrentIndex(_RIGHT_INFO)
            else:
                self.show_loading_info()
                self.info_requested.emit()
        else:  # Preview
            if self._current_entry and not self._current_entry.endswith("/"):
                self._stack.setCurrentIndex(_RIGHT_LOADING_PREVIEW)
                self.preview_requested.emit(self._current_entry)
            else:
                self._stack.setCurrentIndex(_RIGHT_PLACEHOLDER)

    def _clear_info_labels(self) -> None:
        for lbl in (
            self._info_format,
            self._info_files,
            self._info_compressed,
            self._info_uncompressed,
            self._info_ratio,
            self._info_encrypted,
            self._info_comment,
        ):
            lbl.setText("—")

    def _toggle_playback(self) -> None:
        if not _HAS_MULTIMEDIA or self._media_player is None:
            return
        _playing = QMediaPlayer.PlaybackState.PlayingState
        if self._media_player.playbackState() == _playing:
            self._media_player.pause()
        else:
            self._media_player.play()

    def _on_playback_state(self, state) -> None:
        if not _HAS_MULTIMEDIA or not hasattr(self, "_play_btn"):
            return
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        self._play_btn.setText("⏸" if playing else "▶")

    def _on_duration_changed(self, duration: int) -> None:
        has_media = duration > 0
        if hasattr(self, "_seek_bar"):
            self._seek_bar.setRange(0, duration)
            self._seek_bar.setEnabled(has_media)
        if hasattr(self, "_play_btn"):
            self._play_btn.setEnabled(has_media)

    def _on_position_changed(self, pos: int) -> None:
        if self._media_player is None:
            return

        def _fmt(ms: int) -> str:
            s = ms // 1000
            return f"{s // 60}:{s % 60:02d}"

        total = self._media_player.duration()
        if hasattr(self, "_time_lbl"):
            if total > 0:
                self._time_lbl.setText(f"{_fmt(pos)} / {_fmt(total)}")
            else:
                self._time_lbl.setText(_fmt(pos))
        if hasattr(self, "_seek_bar") and not self._seek_bar.isSliderDown():
            self._seek_bar.setValue(pos)

    def _on_seek_moved(self, pos: int) -> None:
        if self._media_player is not None:
            self._media_player.setPosition(pos)

    def _on_volume_changed(self, value: int) -> None:
        if self._media_audio is not None:
            self._media_audio.setVolume(value / 100.0)
        if value > 0 and hasattr(self, "_mute_btn") and self._mute_btn.isChecked():
            self._mute_btn.setChecked(False)

    def _on_mute_toggled(self, muted: bool) -> None:
        if self._media_audio is not None:
            self._media_audio.setMuted(muted)
        if hasattr(self, "_mute_btn"):
            self._mute_btn.setText("🔇" if muted else "🔊")

    def _on_speed_changed(self, index: int) -> None:
        if self._media_player is not None and hasattr(self, "_speed_combo"):
            rate = self._speed_combo.itemData(index)
            if rate is not None:
                self._media_player.setPlaybackRate(float(rate))
