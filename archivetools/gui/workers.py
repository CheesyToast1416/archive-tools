from __future__ import annotations

import logging
from collections.abc import Sequence

from PySide6.QtCore import QThread, Signal

from archivetools.gui.log_handler import GuiLogHandler
from archivetools.operations import (
    convert_archive,
    create_archive,
    extract_cjk,
    get_archive_info,
    list_cjk,
    test_archive,
)

_CORE_LOGGER = "archivetools.formats"  # formats/* now owns the log output


class _BaseWorker(QThread):
    error = Signal(str)
    log_message = Signal(str)

    def _install_log_handler(self) -> GuiLogHandler:
        handler = GuiLogHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s  %(message)s"))
        handler.message.connect(self.log_message)
        # Capture both formats and operations loggers
        for name in (_CORE_LOGGER, "archivetools.operations"):
            logging.getLogger(name).addHandler(handler)
        return handler

    def _remove_log_handler(self, handler: GuiLogHandler) -> None:
        for name in (_CORE_LOGGER, "archivetools.operations"):
            logging.getLogger(name).removeHandler(handler)


class ListWorker(_BaseWorker):
    """Calls list_cjk() in a background thread and emits results via signals."""

    result = Signal(bool, str, list)

    def __init__(
        self,
        archive_path: str,
        password: str,
        filename_encoding: str | None,
        password_encoding: str | None = None,
    ) -> None:
        super().__init__()
        self._archive_path = archive_path
        self._password = password
        self._filename_encoding = filename_encoding
        self._password_encoding = password_encoding

    def run(self) -> None:
        handler = self._install_log_handler()
        try:
            ok, enc, names = list_cjk(
                self._archive_path,
                self._password,
                self._filename_encoding,
                self._password_encoding,
            )
            self.result.emit(ok, enc or "", names)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))
        finally:
            self._remove_log_handler(handler)


class ExtractionWorker(_BaseWorker):
    """Calls extract_cjk() in a background thread and emits results via signals."""

    result = Signal(bool, str)
    file_progress = Signal(int, int, str)  # current_file, total_files, filename
    bytes_progress = Signal(int, int)  # bytes_done, file_size

    def __init__(
        self,
        archive_path: str,
        password: str,
        output_dir: str,
        filename_encoding: str | None,
        password_encoding: str | None = None,
        names: list[str] | None = None,
    ) -> None:
        super().__init__()
        self._archive_path = archive_path
        self._password = password
        self._output_dir = output_dir or None
        self._filename_encoding = filename_encoding
        self._password_encoding = password_encoding
        self._names = names  # pre-fetched file list for smart extraction

    def run(self) -> None:
        handler = self._install_log_handler()
        try:
            ok, enc = extract_cjk(
                self._archive_path,
                self._password,
                self._output_dir,
                filename_encoding=self._filename_encoding,
                password_encoding=self._password_encoding,
                progress=lambda c, t, f: self.file_progress.emit(c, t, f),
                bytes_progress=lambda d, s: self.bytes_progress.emit(d, s),
                names=self._names,
                smart=True,
            )
            self.result.emit(ok, enc or "")
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))
        finally:
            self._remove_log_handler(handler)


class TestWorker(_BaseWorker):
    """Calls test_archive() in a background thread."""

    result = Signal(bool, list)  # (all_ok, failed_entry_names)

    def __init__(
        self,
        archive_path: str,
        password: str,
        filename_encoding: str | None,
        password_encoding: str | None = None,
    ) -> None:
        super().__init__()
        self._archive_path = archive_path
        self._password = password
        self._filename_encoding = filename_encoding
        self._password_encoding = password_encoding

    def run(self) -> None:
        handler = self._install_log_handler()
        try:
            ok, failed = test_archive(
                self._archive_path,
                self._password,
                filename_encoding=self._filename_encoding,
                password_encoding=self._password_encoding,
            )
            self.result.emit(ok, failed)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))
        finally:
            self._remove_log_handler(handler)


class ConvertWorker(_BaseWorker):
    """Calls convert_archive() in a background thread."""

    result = Signal(bool)

    def __init__(
        self,
        input_path: str,
        output_path: str,
        output_format: str,
        password: str,
        output_password: str,
        filename_encoding: str | None = None,
        password_encoding: str | None = None,
    ) -> None:
        super().__init__()
        self._input_path = input_path
        self._output_path = output_path
        self._output_format = output_format
        self._password = password or None
        self._output_password = output_password or None
        self._filename_encoding = filename_encoding
        self._password_encoding = password_encoding

    def run(self) -> None:
        handler = self._install_log_handler()
        try:
            ok = convert_archive(
                self._input_path,
                self._output_path,
                self._output_format,
                password=self._password,
                output_password=self._output_password,
                filename_encoding=self._filename_encoding,
                password_encoding=self._password_encoding,
            )
            self.result.emit(ok)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))
        finally:
            self._remove_log_handler(handler)


class InfoWorker(_BaseWorker):
    """Calls get_archive_info() in a background thread and emits result."""

    result = Signal(object)  # ArchiveInfo on success

    def __init__(self, archive_path: str) -> None:
        super().__init__()
        self._archive_path = archive_path

    def run(self) -> None:
        handler = self._install_log_handler()
        try:
            info = get_archive_info(self._archive_path)
            self.result.emit(info)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))
        finally:
            self._remove_log_handler(handler)


class CreateWorker(_BaseWorker):
    """Runs create_archive() in a background thread."""

    result = Signal(bool)

    def __init__(
        self,
        output_path: str,
        files: Sequence[str],
        format: str,
        password: str,
        compression_level: int,
        filename_encoding: str | None = None,
    ) -> None:
        super().__init__()
        self._output_path = output_path
        self._files = list(files)
        self._format = format
        self._password = password or None
        self._compression_level = compression_level
        self._filename_encoding = filename_encoding

    def run(self) -> None:
        handler = self._install_log_handler()
        try:
            ok = create_archive(
                self._output_path,
                self._files,
                format=self._format,
                password=self._password,
                compression_level=self._compression_level,
                filename_encoding=self._filename_encoding,
            )
            self.result.emit(ok)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))
        finally:
            self._remove_log_handler(handler)


class BatchExtractionWorker(_BaseWorker):
    """Extracts a list of archives sequentially, emitting per-archive status signals."""

    archive_started = Signal(int)  # queue index
    archive_done = Signal(int, bool, str)  # index, ok, detail_message
    file_progress = Signal(int, int, str)
    bytes_progress = Signal(int, int)
    result = Signal(int, int)  # archives_ok, archives_failed

    def __init__(
        self,
        archives: Sequence[str],
        output_dir: str,
        password: str,
        filename_encoding: str | None,
        password_encoding: str | None = None,
    ) -> None:
        super().__init__()
        self._archives = list(archives)
        self._output_dir = output_dir or None
        self._password = password
        self._filename_encoding = filename_encoding
        self._password_encoding = password_encoding

    def run(self) -> None:
        handler = self._install_log_handler()
        ok_count = 0
        fail_count = 0
        try:
            for i, archive_path in enumerate(self._archives):
                self.archive_started.emit(i)
                try:
                    # List archive first so smart extraction can pick the right dest.
                    # list_cjk is a fast header scan (no decompression).
                    _ok, _enc, names = list_cjk(
                        archive_path,
                        self._password,
                        self._filename_encoding,
                        self._password_encoding,
                    )
                    ok, enc = extract_cjk(
                        archive_path,
                        self._password,
                        self._output_dir,  # None → extract next to archive
                        filename_encoding=self._filename_encoding,
                        password_encoding=self._password_encoding,
                        progress=lambda c, t, f: self.file_progress.emit(c, t, f),
                        bytes_progress=lambda d, s: self.bytes_progress.emit(d, s),
                        names=names if _ok else None,
                        smart=True,
                    )
                    if ok:
                        ok_count += 1
                        self.archive_done.emit(i, True, f"encoding: {enc or 'auto'}")
                    else:
                        fail_count += 1
                        self.archive_done.emit(i, False, "extraction failed")
                except Exception as exc:  # noqa: BLE001
                    fail_count += 1
                    self.archive_done.emit(i, False, str(exc))
        finally:
            self._remove_log_handler(handler)
            self.result.emit(ok_count, fail_count)
