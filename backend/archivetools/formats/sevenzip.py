from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from archivetools.formats.base import (
    ArchiveHandler,
    ArchiveInfo,
    resolve_password_candidates,
)

log = logging.getLogger(__name__)


class SevenZipHandler(ArchiveHandler):
    FORMAT_NAME = "7z"
    CAN_CREATE = True
    CAN_ENCRYPT_CREATE = True

    @staticmethod
    def _import() -> Any:
        try:
            import py7zr  # type: ignore[import]

            return py7zr
        except ImportError:
            raise ImportError("Run:  pip install py7zr")

    def _str_candidates(
        self,
        password: str,
        password_encoding: str | None = None,
    ) -> list[tuple[str, str]]:
        seen: set[str] = set()
        result: list[tuple[str, str]] = []

        def _add(s: str, label: str) -> None:
            if s not in seen:
                seen.add(s)
                result.append((s, label))

        _add(password, "utf-8 (str)")
        for raw, enc in resolve_password_candidates(password, password_encoding):
            try:
                proxy = raw.decode("latin-1")
                _add(proxy, f"{enc}→latin-1 proxy")
            except Exception:  # noqa: BLE001
                pass
        return result

    def extract(
        self,
        archive_path: Path,
        password: str,
        output_dir: Path,
        *,
        filename_encoding: str | None = None,
        password_encoding: str | None = None,
        verbose: bool = True,
        progress: Callable[[int, int, str], None] | None = None,
        bytes_progress: Callable[[int, int], None] | None = None,
    ) -> tuple[bool, str | None]:
        # 7z stores filenames in UTF-16; filename_encoding is intentionally ignored.
        py7zr = self._import()
        str_candidates = self._str_candidates(password, password_encoding)

        if verbose:
            log.info("Format   : %s", self.FORMAT_NAME)
            log.info("Trying %d password variant(s)", len(str_candidates))

        for pwd_str, label in str_candidates:
            try:
                with py7zr.SevenZipFile(
                    str(archive_path), mode="r", password=pwd_str
                ) as sz:
                    sz.extractall(path=str(output_dir))
                return True, label
            except (py7zr.exceptions.PasswordRequired, py7zr.exceptions.Bad7zFile):
                continue
            except Exception:  # noqa: BLE001
                continue

        return False, None

    def list_contents(
        self,
        archive_path: Path,
        password: str,
        filename_encoding: str | None = None,
        password_encoding: str | None = None,
    ) -> tuple[bool, str | None, list[str]]:
        py7zr = self._import()
        for pwd_str, label in self._str_candidates(password, password_encoding):
            try:
                with py7zr.SevenZipFile(
                    str(archive_path), mode="r", password=pwd_str
                ) as sz:
                    return True, label, sz.getnames()
            except Exception:  # noqa: BLE001
                continue
        return False, None, []

    def test(
        self,
        archive_path: Path,
        password: str,
        *,
        filename_encoding: str | None = None,
        password_encoding: str | None = None,
    ) -> tuple[bool, list[str]]:
        py7zr = self._import()
        for pwd_str, _ in self._str_candidates(password, password_encoding):
            try:
                with py7zr.SevenZipFile(
                    str(archive_path), mode="r", password=pwd_str
                ) as sz:
                    sz.read()  # reads all to memory; raises on bad password / CRC
                return True, []
            except (py7zr.exceptions.PasswordRequired, py7zr.exceptions.Bad7zFile):
                continue
            except Exception:  # noqa: BLE001
                continue
        return False, ["Wrong password or could not open archive"]

    def create(
        self,
        output_path: Path,
        files: list[Path],
        *,
        password: str | None = None,
        compression_level: int = 6,
        filename_encoding: str | None = None,
    ) -> bool:
        py7zr = self._import()
        kwargs: dict = {}
        if password:
            kwargs["password"] = password
        with py7zr.SevenZipFile(str(output_path), mode="w", **kwargs) as sz:
            for f in files:
                f = Path(f)
                if f.is_dir():
                    sz.writeall(str(f), f.name)
                elif f.is_file():
                    sz.write(str(f), f.name)
        log.info("✓ Created 7z: %s", output_path)
        return True

    def get_info(self, archive_path: Path) -> ArchiveInfo:
        py7zr = self._import()
        try:
            with py7zr.SevenZipFile(str(archive_path), mode="r") as sz:
                files = sz.list()
                compressed = sum(getattr(f, "compressed", 0) or 0 for f in files)
                uncompressed = sum(
                    getattr(f, "uncompressed_size", 0) or 0 for f in files
                )
                return ArchiveInfo(
                    format_name=self.FORMAT_NAME,
                    file_count=len(files),
                    compressed_size=compressed,
                    uncompressed_size=uncompressed,
                    is_encrypted=sz.needs_password(),
                    archive_path=archive_path,
                )
        except Exception:  # noqa: BLE001
            return super().get_info(archive_path)
