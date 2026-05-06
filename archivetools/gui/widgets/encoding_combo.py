from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox


class EncodingComboBox(QComboBox):
    """
    A QComboBox pre-loaded with common CJK encodings.

    The first item is always "Auto-detect" (codec = "").
    Call ``set_detected()`` after charset-normalizer analysis to annotate it
    with the detected encoding, e.g. "Auto-detect  (GBK, 94%)".
    """

    ENCODINGS: list[tuple[str, str]] = [
        ("Auto-detect", ""),
        ("GBK (Simplified Chinese)", "gbk"),
        ("Big5 (Traditional Chinese)", "big5"),
        ("Big5-HKSCS (Hong Kong)", "big5hkscs"),
        ("GB18030 (Mainland China)", "gb18030"),
        ("UTF-8", "utf-8"),
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
