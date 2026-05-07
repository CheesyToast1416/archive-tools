from __future__ import annotations

import logging
import os
import shutil
import tempfile
from collections.abc import Sequence
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from archivetools.gui.log_handler import GuiLogHandler
from archivetools.operations import (
    convert_archive,
    create_archive,
    extract_archive,
    get_archive_info,
    list_archive,
    test_archive,
    update_archive,
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


# ── Read-only workers ───────────────────────────────────────────────────────


class ListWorker(_BaseWorker):
    """Calls list_archive() in a background thread and emits results via signals."""

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
            ok, enc, names = list_archive(
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


# ── Write workers ───────────────────────────────────────────────────────────


class ExtractionWorker(_BaseWorker):
    """Calls extract_archive() in a background thread and emits results via signals."""

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
            ok, enc = extract_archive(
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


# ── Background / async workers ──────────────────────────────────────────────


class PreviewWorker(_BaseWorker):
    """Extracts a single archive entry to a temp dir for in-app preview."""

    # Emits (tmpdir_to_cleanup, extracted_file_path)
    result = Signal(str, str)

    def __init__(
        self,
        archive_path: str,
        entry_name: str,
        password: str,
        filename_encoding: str | None,
        password_encoding: str | None = None,
    ) -> None:
        super().__init__()
        self._archive_path = archive_path
        self._entry_name = entry_name
        self._password = password
        self._filename_encoding = filename_encoding
        self._password_encoding = password_encoding

    def run(self) -> None:
        tmpdir = tempfile.mkdtemp(prefix="atpreview_")
        handler = self._install_log_handler()
        try:
            # filename_encoding / password_encoding are keyword-only in extract_archive
            ok, _ = extract_archive(
                self._archive_path,
                self._password,
                tmpdir,
                filename_encoding=self._filename_encoding,
                password_encoding=self._password_encoding,
                smart=False,  # no directory restructuring inside the temp dir
            )
            if not ok:
                shutil.rmtree(tmpdir, ignore_errors=True)
                self.error.emit("Could not extract entry for preview")
                return
            found = self._locate_entry(tmpdir)
            if found:
                self.result.emit(tmpdir, found)
            else:
                shutil.rmtree(tmpdir, ignore_errors=True)
                self.error.emit("Extracted file not found in archive")
        except Exception as exc:  # noqa: BLE001
            shutil.rmtree(tmpdir, ignore_errors=True)
            self.error.emit(str(exc))
        finally:
            self._remove_log_handler(handler)

    def _locate_entry(self, tmpdir: str) -> str | None:
        """Find the extracted file matching self._entry_name inside tmpdir."""
        # 1. Direct match: tmpdir / entry_name
        direct = Path(tmpdir) / self._entry_name
        if direct.is_file():
            return str(direct)
        # 2. Strip leading ./ (common in tar archives)
        stripped = Path(tmpdir) / self._entry_name.lstrip("./")
        if stripped.is_file():
            return str(stripped)
        # 3. Basename search (handles encoding / path prefix differences)
        target = Path(self._entry_name).name
        for root, _dirs, files in os.walk(tmpdir):
            for fname in files:
                if fname == target:
                    return os.path.join(root, fname)
        # 4. Last resort: first file found
        for root, _dirs, files in os.walk(tmpdir):
            if files:
                return os.path.join(root, files[0])
        return None


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


class UpdateWorker(_BaseWorker):
    """Calls update_archive() in a background thread."""

    result = Signal(bool)

    def __init__(
        self,
        archive_path: str,
        files_to_add: list[str],
        paths_to_remove: list[str],
    ) -> None:
        super().__init__()
        self._archive_path = archive_path
        self._files_to_add = files_to_add
        self._paths_to_remove = paths_to_remove

    def run(self) -> None:
        handler = self._install_log_handler()
        try:
            ok = update_archive(
                self._archive_path,
                files_to_add=self._files_to_add,
                paths_to_remove=self._paths_to_remove,
            )
            self.result.emit(ok)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))
        finally:
            self._remove_log_handler(handler)


# ── Batch worker ────────────────────────────────────────────────────────────


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
                    # list_archive is a fast header scan (no decompression).
                    _ok, _enc, names = list_archive(
                        archive_path,
                        self._password,
                        self._filename_encoding,
                        self._password_encoding,
                    )
                    ok, enc = extract_archive(
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
