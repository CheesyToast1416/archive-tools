from __future__ import annotations

import logging
import tarfile
from collections.abc import Callable
from pathlib import Path

from archivetools.formats.base import ArchiveHandler, ArchiveInfo

log = logging.getLogger(__name__)


class TarHandler(ArchiveHandler):
    FORMAT_NAME = "TAR"
    CAN_CREATE = True
    CAN_ENCRYPT_CREATE = False  # TAR has no native encryption

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
        if password:
            raise TypeError(
                "TAR archives do not support encryption. "
                "Extract the outer ZIP/RAR/7z first, then open the TAR."
            )
        if verbose:
            log.info("Format   : %s", self.FORMAT_NAME)
            log.info("Archive  : %s", archive_path)
            log.info("Output   : %s", output_dir)
        try:
            with tarfile.open(archive_path) as tf:
                members = tf.getmembers()
                total = len(members)
                for i, member in enumerate(members):
                    tf.extract(member, path=output_dir, filter="data")
                    if progress:
                        progress(i + 1, total, member.name)
            if verbose:
                log.info("✓ TAR extracted successfully.")
            return True, None
        except Exception as exc:  # noqa: BLE001
            log.error("TAR extraction failed: %s", exc)
            return False, None

    def list_contents(
        self,
        archive_path: Path,
        password: str,
        filename_encoding: str | None = None,
        password_encoding: str | None = None,
    ) -> tuple[bool, str | None, list[str]]:
        if password:
            raise TypeError("TAR archives do not support encryption.")
        try:
            with tarfile.open(archive_path) as tf:
                return True, None, tf.getnames()
        except Exception:  # noqa: BLE001
            return False, None, []

    def test(
        self,
        archive_path: Path,
        password: str,
        *,
        filename_encoding: str | None = None,
        password_encoding: str | None = None,
    ) -> tuple[bool, list[str]]:
        if password:
            raise TypeError("TAR archives do not support encryption.")
        try:
            with tarfile.open(archive_path) as tf:
                failed: list[str] = []
                for member in tf.getmembers():
                    if not member.isfile():
                        continue
                    try:
                        f = tf.extractfile(member)
                        if f:
                            while f.read(1 << 16):
                                pass
                    except Exception as exc:  # noqa: BLE001
                        log.debug("TAR test entry %s: %s", member.name, exc)
                        failed.append(member.name)
                return len(failed) == 0, failed
        except Exception as exc:  # noqa: BLE001
            log.error("Cannot open TAR archive for testing: %s", exc)
            return False, [str(exc)]

    @staticmethod
    def _write_mode(output_path: Path) -> str:
        name = output_path.name.lower()
        if name.endswith((".tar.gz", ".tgz")):
            return "w:gz"
        if name.endswith(".tar.bz2"):
            return "w:bz2"
        if name.endswith(".tar.xz"):
            return "w:xz"
        return "w"

    def create(
        self,
        output_path: Path,
        files: list[Path],
        *,
        password: str | None = None,
        compression_level: int = 6,
        filename_encoding: str | None = None,
    ) -> bool:
        if password:
            raise TypeError(
                "TAR archives do not support encryption. "
                "Use ZIP-AES or 7z for encrypted archives."
            )
        mode = self._write_mode(output_path)
        with tarfile.open(str(output_path), mode) as tf:  # type: ignore[call-overload]
            for f in files:
                f = Path(f)
                tf.add(str(f), arcname=f.name)
        log.info("✓ Created TAR (%s): %s", mode, output_path)
        return True

    def get_info(self, archive_path: Path) -> ArchiveInfo:
        try:
            with tarfile.open(archive_path) as tf:
                members = tf.getmembers()
                uncompressed = sum(m.size for m in members)
                return ArchiveInfo(
                    format_name=self.FORMAT_NAME,
                    file_count=len(members),
                    compressed_size=archive_path.stat().st_size,
                    uncompressed_size=uncompressed,
                    is_encrypted=False,
                    archive_path=archive_path,
                )
        except Exception:  # noqa: BLE001
            return super().get_info(archive_path)
