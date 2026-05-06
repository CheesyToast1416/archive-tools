from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox


class EncodingComboBox(QComboBox):
    """
    A QComboBox pre-loaded with encodings commonly found in archive filenames
    and passwords, covering Chinese, Japanese, Korean, and Western scripts.

    The first item is always "Auto-detect" (codec = "").
    Call ``set_detected()`` after charset-normalizer analysis to annotate it
    with the detected encoding, e.g. "Auto-detect  (GBK, 94%)".
    """

    ENCODINGS: list[tuple[str, str]] = [
        # ── Universal ─────────────────────────────────────────────────
        ("Auto-detect", ""),
        ("UTF-8", "utf-8"),
        # ── Chinese ───────────────────────────────────────────────────
        ("GBK  (Simplified Chinese)", "gbk"),
        ("GB18030  (Simplified Chinese, full Unicode)", "gb18030"),
        ("Big5  (Traditional Chinese)", "big5"),
        ("Big5-HKSCS  (Hong Kong)", "big5hkscs"),
        # ── Japanese ──────────────────────────────────────────────────
        ("Shift-JIS / CP932  (Japanese Windows)", "cp932"),
        ("EUC-JP  (Japanese Unix)", "euc_jp"),
        # ── Korean ────────────────────────────────────────────────────
        ("EUC-KR / CP949  (Korean)", "cp949"),
        # ── Western / Legacy ──────────────────────────────────────────
        ("CP1252  (Western European Windows)", "cp1252"),
        ("Latin-1  (ISO 8859-1)", "latin-1"),
        ("CP437  (ZIP/DOS default)", "cp437"),
    ]

    encoding_changed = Signal(str)  # emits codec string, "" = auto

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        for label, codec in self.ENCODINGS:
            self.addItem(label, codec)
        self.currentIndexChanged.connect(
            lambda _: self.encoding_changed.emit(self.current_codec() or "")
        )

    def current_codec(self) -> str | None:
        """Return the selected codec string, or ``None`` for Auto-detect."""
        codec: str = self.currentData()
        return codec or None

    def set_detected(self, codec: str, confidence: float) -> None:
        """
        Annotate the Auto-detect label with the charset-normalizer result.
        Does not change the current selection.
        """
        if confidence >= 0.5:
            label = f"Auto-detect  ({codec.upper()}, {confidence:.0%})"
        else:
            label = "Auto-detect"
        self.setItemText(0, label)

    def reset_detected(self) -> None:
        """Reset the Auto-detect label to its default text."""
        self.setItemText(0, "Auto-detect")
