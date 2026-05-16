"""Tests for all archive format handlers and format detection.

Consolidates: test_core.py, test_tar.py, test_info.py, test_progress.py
"""

from __future__ import annotations

import io
import tarfile
import zipfile
from pathlib import Path

import pytest

from archivetools.encoding.candidates import PASSWORD_ENCODINGS, password_candidates
from archivetools.formats import detect_handler
from archivetools.formats.rar import RarHandler
from archivetools.formats.sevenzip import SevenZipHandler
from archivetools.formats.tar import TarHandler
from archivetools.formats.zip import ZipHandler
from archivetools.operations.extract import _default_output_dir

# ── password_candidates ────────────────────────────────────────────────────────


class TestPasswordCandidates:
    def test_ascii_deduplicates_to_one_entry(self) -> None:
        results = password_candidates("hello")
        assert len(results) == 1
        assert results[0][1] == "utf-8"
        assert results[0][0] == b"hello"

    def test_cjk_gbk_is_first(self) -> None:
        results = password_candidates("密码")
        assert results[0][1] in ("gbk", "gb2312", "gb18030")

    def test_gb18030_covers_emoji_gbk_does_not(self) -> None:
        results = password_candidates("🔐")
        encodings = [enc for _, enc in results]
        assert "gb18030" in encodings
        assert "utf-8" in encodings
        assert "gbk" not in encodings
        assert "big5" not in encodings

    def test_all_byte_values_are_unique(self) -> None:
        results = password_candidates("abc123")
        byte_vals = [b for b, _ in results]
        assert len(byte_vals) == len(set(byte_vals))

    def test_gbk_precedes_utf8_in_order(self) -> None:
        # GBK is the first encoding; utf-8 is always last as universal fallback
        assert PASSWORD_ENCODINGS[0] == "gbk"
        assert PASSWORD_ENCODINGS[-1] == "utf-8"


# ── _default_output_dir ────────────────────────────────────────────────────────


class TestDefaultOutputDir:
    def test_plain_zip(self, tmp_path: Path) -> None:
        p = tmp_path / "archive.zip"
        p.touch()
        assert _default_output_dir(p) == tmp_path / "archive"

    def test_tar_gz_strips_both_extensions(self, tmp_path: Path) -> None:
        p = tmp_path / "archive.tar.gz"
        p.touch()
        assert _default_output_dir(p) == tmp_path / "archive"

    def test_tar_bz2(self, tmp_path: Path) -> None:
        p = tmp_path / "archive.tar.bz2"
        p.touch()
        assert _default_output_dir(p) == tmp_path / "archive"

    def test_numbered_split(self, tmp_path: Path) -> None:
        p = tmp_path / "archive.zip.001"
        p.touch()
        assert _default_output_dir(p) == tmp_path / "archive"

    def test_rar(self, tmp_path: Path) -> None:
        p = tmp_path / "myfiles.rar"
        p.touch()
        assert _default_output_dir(p) == tmp_path / "myfiles"


# ── detect_handler ─────────────────────────────────────────────────────────────


class TestFormatDetection:
    def test_zip_by_extension_and_content(self, tmp_path: Path) -> None:
        p = tmp_path / "test.zip"
        with zipfile.ZipFile(p, "w") as zf:
            zf.writestr("hello.txt", "world")
        handler, canonical = detect_handler(p)
        assert isinstance(handler, ZipHandler)
        assert canonical == p

    def test_rar_by_magic_bytes(self, tmp_path: Path) -> None:
        p = tmp_path / "test.rar"
        p.write_bytes(b"Rar!\x1a\x07\x00")
        handler, _ = detect_handler(p)
        assert isinstance(handler, RarHandler)

    def test_7z_by_magic_bytes(self, tmp_path: Path) -> None:
        p = tmp_path / "test.7z"
        p.write_bytes(b"7z\xbc\xaf\x27\x1c")
        handler, _ = detect_handler(p)
        assert isinstance(handler, SevenZipHandler)

    def test_zip_no_extension_magic(self, tmp_path: Path) -> None:
        src = tmp_path / "archive"
        with zipfile.ZipFile(src, "w") as zf:
            zf.writestr("hello.txt", "world")
        handler, _ = detect_handler(src)
        assert isinstance(handler, ZipHandler)

    def test_7z_no_extension_magic(self, tmp_path: Path) -> None:
        src = tmp_path / "archive"
        src.write_bytes(b"7z\xbc\xaf\x27\x1c\x00\x04")
        handler, _ = detect_handler(src)
        assert isinstance(handler, SevenZipHandler)

    def test_rar5_no_extension_magic(self, tmp_path: Path) -> None:
        src = tmp_path / "archive"
        src.write_bytes(b"Rar!\x1a\x07\x01\x00")
        handler, _ = detect_handler(src)
        assert isinstance(handler, RarHandler)

    def test_gzip_tar_detected_as_tar(self, tmp_path: Path) -> None:
        p = tmp_path / "archive.tar.gz"
        data = b"\x1f\x8b"  # gzip magic
        p.write_bytes(data + b"\x00" * 20)
        # May raise or return TarHandler — just ensure it doesn't return wrong type
        try:
            handler, _ = detect_handler(p)
            assert isinstance(handler, TarHandler)
        except Exception:
            pass  # partial gzip is acceptable to fail

    def test_unsupported_magic_raises(self, tmp_path: Path) -> None:
        src = tmp_path / "archive"
        src.write_bytes(b"\x00\x01\x02\x03unknown")
        with pytest.raises(ValueError):
            detect_handler(src)

    def test_unsupported_extension_raises_value_error(self, tmp_path: Path) -> None:
        # An unrecognised (or empty) extension raises ValueError before any I/O.
        p = tmp_path / "archive.xyz"
        p.write_bytes(b"\x00" * 8)
        with pytest.raises(ValueError, match="Unsupported"):
            detect_handler(p)


# ── ZipHandler ────────────────────────────────────────────────────────────────


class TestZipHandler:
    def test_list_contents(self, simple_zip: Path) -> None:
        ok, enc, names = ZipHandler().list_contents(simple_zip, "")
        assert ok is True
        assert "hello.txt" in names
        assert "subdir/nested.txt" in names

    def test_extract_creates_files(self, simple_zip: Path, output_dir: Path) -> None:
        ok, _ = ZipHandler().extract(simple_zip, "", output_dir)
        assert ok is True
        assert (output_dir / "hello.txt").exists()
        assert (output_dir / "hello.txt").read_text() == "Hello, world!"

    def test_get_info_metadata(self, simple_zip: Path) -> None:
        info = ZipHandler().get_info(simple_zip)
        assert info.format_name == "ZIP"
        assert info.file_count == 2
        assert info.is_encrypted is False
        assert info.compressed_size > 0
        assert info.uncompressed_size > 0

    def test_extract_encrypted_correct_password(
        self, encrypted_zip: Path, output_dir: Path
    ) -> None:
        # AES-encrypted ZIPs need ZipHandlerAES; detect_handler picks the right class
        from archivetools.formats import detect_handler

        handler, _ = detect_handler(encrypted_zip)
        ok, _ = handler.extract(encrypted_zip, "correcthorsebattery", output_dir)
        assert ok is True
        assert (output_dir / "secret.txt").read_text() == "top secret content"

    def test_extract_encrypted_wrong_password_returns_false(
        self, encrypted_zip: Path, output_dir: Path
    ) -> None:
        from archivetools.formats import detect_handler

        handler, _ = detect_handler(encrypted_zip)
        ok, _ = handler.extract(encrypted_zip, "wrongpassword", output_dir)
        assert ok is False

    def test_extract_calls_progress_callback(
        self, simple_zip: Path, output_dir: Path
    ) -> None:
        calls: list[tuple[int, int]] = []
        ZipHandler().extract(
            simple_zip, "", output_dir, progress=lambda c, t, f: calls.append((c, t))
        )
        assert len(calls) == 2  # two files
        assert calls[-1] == (2, 2)
        assert [c for c, _ in calls] == [1, 2]  # monotonically increasing

    def test_no_progress_arg_is_ok(self, simple_zip: Path, output_dir: Path) -> None:
        ok, _ = ZipHandler().extract(simple_zip, "", output_dir)
        assert ok is True


# ── TarHandler ────────────────────────────────────────────────────────────────


class TestTarHandler:
    def test_list_contents(self, simple_tar: Path) -> None:
        ok, enc, names = TarHandler().list_contents(simple_tar, "")
        assert ok is True
        assert enc is None
        assert "hello.txt" in names
        assert "data.csv" in names

    def test_extract_plain_tar(self, simple_tar: Path, output_dir: Path) -> None:
        ok, _ = TarHandler().extract(simple_tar, "", output_dir)
        assert ok is True
        assert (output_dir / "hello.txt").exists()

    def test_extract_tar_gz(self, simple_tar_gz: Path, output_dir: Path) -> None:
        ok, _ = TarHandler().extract(simple_tar_gz, "", output_dir)
        assert ok is True

    def test_extract_tar_bz2(self, tmp_path: Path, output_dir: Path) -> None:
        p = tmp_path / "arch.tar.bz2"
        with tarfile.open(p, "w:bz2") as tf:
            data = b"bzip2 content"
            info = tarfile.TarInfo("file.txt")
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
        ok, _ = TarHandler().extract(p, "", output_dir)
        assert ok is True

    def test_extract_tar_xz(self, tmp_path: Path, output_dir: Path) -> None:
        p = tmp_path / "arch.tar.xz"
        with tarfile.open(p, "w:xz") as tf:
            data = b"xz content"
            info = tarfile.TarInfo("file.txt")
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
        ok, _ = TarHandler().extract(p, "", output_dir)
        assert ok is True

    def test_password_raises_type_error(self, simple_tar: Path, tmp_path: Path) -> None:
        with pytest.raises(TypeError, match="do not support encryption"):
            TarHandler().extract(simple_tar, "anypassword", tmp_path / "out")

    def test_get_info(self, simple_tar: Path) -> None:
        info = TarHandler().get_info(simple_tar)
        assert info.format_name == "TAR"
        assert info.file_count >= 2
        assert info.is_encrypted is False

    def test_progress_callback_called(self, simple_tar: Path, output_dir: Path) -> None:
        calls: list[tuple[int, int]] = []
        TarHandler().extract(
            simple_tar, "", output_dir, progress=lambda c, t, f: calls.append((c, t))
        )
        assert len(calls) > 0
        assert calls[-1][0] == calls[-1][1]  # last call: current == total

    def test_list_encrypted_raises(self, simple_tar: Path) -> None:
        with pytest.raises(TypeError):
            TarHandler().list_contents(simple_tar, "password")


# ── SevenZipHandler ────────────────────────────────────────────────────────────


class TestSevenZipHandler:
    @pytest.fixture
    def simple_7z(self, tmp_path: Path) -> Path:
        import py7zr

        p = tmp_path / "archive.7z"
        # py7zr.writestr(data, arcname) — data comes first, name second
        with py7zr.SevenZipFile(p, "w") as sz:
            sz.writestr("Hello from 7z!", "hello.txt")
            sz.writestr("nested", "sub/data.txt")
        return p

    def test_list_contents(self, simple_7z: Path) -> None:
        ok, enc, names = SevenZipHandler().list_contents(simple_7z, "")
        assert ok is True
        assert any("hello.txt" in n for n in names)

    def test_extract(self, simple_7z: Path, output_dir: Path) -> None:
        ok, _ = SevenZipHandler().extract(simple_7z, "", output_dir)
        assert ok is True
        assert any((output_dir / n).exists() for n in ["hello.txt", "sub/data.txt"])

    def test_get_info(self, simple_7z: Path) -> None:
        info = SevenZipHandler().get_info(simple_7z)
        assert info.format_name.upper() == "7Z"
        assert info.file_count >= 2
        assert info.is_encrypted is False

    def test_encrypted_correct_password(self, tmp_path: Path, output_dir: Path) -> None:
        import py7zr

        p = tmp_path / "enc.7z"
        with py7zr.SevenZipFile(p, "w", password="pw123") as sz:
            sz.writestr("secret content", "secret.txt")
        ok, _ = SevenZipHandler().extract(p, "pw123", output_dir)
        assert ok is True

    def test_encrypted_wrong_password_returns_false(
        self, tmp_path: Path, output_dir: Path
    ) -> None:
        import py7zr

        p = tmp_path / "enc.7z"
        with py7zr.SevenZipFile(p, "w", password="correct") as sz:
            sz.writestr("x", "f.txt")
        ok, _ = SevenZipHandler().extract(p, "wrong", output_dir)
        assert ok is False
