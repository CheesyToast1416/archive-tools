from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal


class _LogEmitter(QObject):
    message = Signal(str)


class GuiLogHandler(logging.Handler):
    """Routes log records to a Qt signal for display in the GUI.

    PySide6's QObject and logging.Handler have metaclass conflicts, so the
    signal lives in a separate _LogEmitter instance held inside the handler.
    """

    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self._emitter = _LogEmitter()
        self.message: Signal = self._emitter.message

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._emitter.message.emit(self.format(record))
        except Exception:  # noqa: BLE001
            self.handleError(record)
