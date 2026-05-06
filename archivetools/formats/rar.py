from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from archivetools.formats.base import ArchiveHandler, ArchiveInfo

log = logging.getLogger(__name__)


class RarHandler(ArchiveHandler):
    FORMAT_NAME = "RAR"
    CAN_CREATE = False  # rarfile is read-only; RAR creation requires rar CLI
    CAN_ENCRYPT_CREATE = False

    @staticmethod
    def _import() -> Any:
        try:
            import rarfile  # type: ignore[import]

            return rarfile
        except ImportError:
            raise ImportError(
                "rarfile is required for RAR archives.\nRun:  pip install rarfile"
            )

    # rarfile 4.x exception aliases ─────────────────────────────────────────
    # BadRarPassword was removed in rarfile 4.x; use the new names instead.
    _WRONG_PWD_EXCS = ("RarWrongPassword", "PasswordRequired", "BadRarFile")

    @classmethod
    def _is_wrong_password(cls, rf: Any, exc: BaseException) -> bool:
        return isinstance(
            exc, tuple(getattr(rf, n) for n in cls._WRONG_PWD_EXCS if hasattr(rf, n))
        )

    def _try_extract(
        self,
        archive_path: Path,
        pwd_bytes: bytes,
        output_dir: Path,
        filename_encoding: str | None,
        progress: Callable[[int, int, str], None] | None = None,
        bytes_progress: Callable[[int, int], None] | None = None,
    ) -> bool:
        rf = self._import()
        kwargs = {"charset": filename_encoding} if filename_encoding else {}
        pwd = pwd_bytes or None
        try:
            with rf.RarFile(str(archive_path), **kwargs) as rar:
                if pwd:
                    rar.setpassword(pwd)
                if progress:
                    infos = rar.infolist()
                    total = len(infos)
                    for i, info in enumerate(infos):
                        rar.extract(info, path=str(output_dir), pwd=pwd)
                        progress(i + 1, total, info.filename)
                else:
                    rar.extractall(path=str(output_dir), pwd=pwd)
            return True
        except rf.RarCRCError:
            return False
        except rf.RarCannotExec as exc:
            raise RuntimeError(
                "RAR3 extraction requires the 'unrar' command-line tool, "
                "which was not found.\n"
                "Install it with:  pacman -S unrar   (Arch Linux)\n"
                "               or  apt install unrar  (Debian/Ubuntu)"
            ) from exc
        except Exception as exc:  # noqa: BLE001
            if self._is_wrong_password(rf, exc):
                return False
            raise

    def _list_names(
        self,
        archive_path: Path,
        pwd_bytes: bytes,
        filename_encoding: str | None,
    ) -> list[str] | None:
        rf = self._import()
        kwargs = {"charset": filename_encoding} if filename_encoding else {}
        pwd = pwd_bytes or None
        try:
            with rf.RarFile(str(archive_path), **kwargs) as rar:
                if pwd:
                    # setpassword() before infolist() triggers a re-parse so
                    # header-encrypted archives decrypt their file listing.
                    rar.setpassword(pwd)
                names = [info.filename for info in rar.infolist()]
                # For header-encrypted archives, a missing or wrong password
                # causes the file list to come back empty without an exception.
                # Use the public needs_password() to detect this case.
                if not names and rar.needs_password():
                    return None
                return names
        except rf.RarCannotExec:
            return None
        except Exception as exc:  # noqa: BLE001
            if self._is_wrong_password(rf, exc):
                return None
            return None

    def test(
        self,
        archive_path: Path,
        password: str,
        *,
        filename_encoding: str | None = None,
        password_encoding: str | None = None,
    ) -> tuple[bool, list[str]]:
        rf = self._import()
        candidates = self._resolve_candidates(password, password_encoding)
        for pwd_bytes, _enc in candidates:
            pwd = pwd_bytes or None
            try:
                with rf.RarFile(str(archive_path)) as rar:
                    if pwd:
                        rar.setpassword(pwd)
                    bad = rar.testrar()  # None on success, raises on error
                return True, list(bad) if bad else []
            except rf.RarCRCError as exc:
                return False, [str(exc)]
            except rf.RarCannotExec:
                return False, ["Requires 'unrar' executable (not found)"]
            except Exception as exc:  # noqa: BLE001
                if self._is_wrong_password(rf, exc):
                    continue
                continue
        return False, ["Wrong password or could not open archive"]

    def get_info(self, archive_path: Path) -> ArchiveInfo:
        rf = self._import()
        try:
            with rf.RarFile(str(archive_path)) as rar:
                infos = rar.infolist()
                is_enc = any(
                    getattr(i, "needs_password", lambda: False)() for i in infos
                )
                compressed = sum(getattr(i, "compress_size", 0) or 0 for i in infos)
                uncompressed = sum(getattr(i, "file_size", 0) or 0 for i in infos)
                return ArchiveInfo(
                    format_name=self.FORMAT_NAME,
                    file_count=len(infos),
                    compressed_size=compressed,
                    uncompressed_size=uncompressed,
                    is_encrypted=is_enc,
                    archive_path=archive_path,
                )
        except Exception:  # noqa: BLE001
            return super().get_info(archive_path)
