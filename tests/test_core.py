from __future__ import annotations

import zipfile

import pytest

from archivetools.encoding.candidates import password_candidates
from archivetools.formats import detect_handler
from archivetools.formats.rar import RarHandler
from archivetools.formats.sevenzip import SevenZipHandler
from archivetools.formats.zip import ZipHandler
from archivetools.operations.extract import _default_output_dir


class TestPasswordCandidates:
    def test_ascii_single_result(self):
        # ASCII encodes identically in all CJK codecs → deduplicated to one entry
        results = password_candidates("hello")
        assert len(results) == 1
        assert results[0][1] == "gbk"

    def test_gbk_is_first(self):
        # '密码' is a valid GBK string; GBK / gb2312 / gb18030 share the same bytes
        results = password_candidates("密码")
        assert results[0][1] in ("gbk", "gb2312", "gb18030")

    def test_gb18030_covers_emoji(self):
        # GB18030 is a full-Unicode superset and can encode emoji;
        # gbk / gb2312 / big5 cannot, so they should be absent.
        results = password_candidates("🔐")
        encodings = [enc for _, enc in results]
        assert "gb18030" in encodings
        assert "utf-8" in encodings
        assert "gbk" not in encodings
        assert "big5" not in encodings


class TestDefaultOutputDir:
    def test_zip(self, tmp_path):
        p = tmp_path / "archive.zip"
        p.touch()
        assert _default_output_dir(p) == tmp_path / "archive"

    def test_numbered_split(self, tmp_path):
        p = tmp_path / "archive.zip.001"
        p.touch()
        assert _default_output_dir(p) == tmp_path / "archive"

    def test_tar_gz(self, tmp_path):
        p = tmp_path / "archive.tar.gz"
        p.touch()
        assert _default_output_dir(p) == tmp_path / "archive"

    def test_rar(self, tmp_path):
        p = tmp_path / "myfiles.rar"
        p.touch()
        assert _default_output_dir(p) == tmp_path / "myfiles"


class TestDetectHandler:
    def test_zip_returns_zip_handler(self, tmp_path):
        p = tmp_path / "test.zip"
        with zipfile.ZipFile(p, "w") as zf:
            zf.writestr("hello.txt", "world")
        handler, canonical = detect_handler(p)
        assert isinstance(handler, ZipHandler)
        assert canonical == p

    def test_rar_extension(self, tmp_path):
        p = tmp_path / "test.rar"
        p.write_bytes(b"Rar!\x1a\x07\x00")
        handler, canonical = detect_handler(p)
        assert isinstance(handler, RarHandler)
        assert canonical == p

    def test_7z_extension(self, tmp_path):
        p = tmp_path / "test.7z"
        p.write_bytes(b"7z\xbc\xaf\x27\x1c")
        handler, canonical = detect_handler(p)
        assert isinstance(handler, SevenZipHandler)
        assert canonical == p


class TestMagicByteDetection:
    def test_zip_no_extension(self, tmp_path):
        import zipfile
        src = tmp_path / "archive"  # no extension
        with zipfile.ZipFile(src, "w") as zf:
            zf.writestr("hello.txt", "world")
        handler, _ = detect_handler(src)
        assert isinstance(handler, ZipHandler)

    def test_7z_no_extension(self, tmp_path):
        src = tmp_path / "archive"
        src.write_bytes(b"7z\xbc\xaf\x27\x1c\x00\x04")
        handler, _ = detect_handler(src)
        assert isinstance(handler, SevenZipHandler)

    def test_rar5_no_extension(self, tmp_path):
        src = tmp_path / "archive"
        src.write_bytes(b"Rar!\x1a\x07\x01\x00")
        handler, _ = detect_handler(src)
        assert isinstance(handler, RarHandler)

    def test_unsupported_no_extension(self, tmp_path):
        src = tmp_path / "archive"
        src.write_bytes(b"\x00\x01\x02\x03unknown")
        with pytest.raises(ValueError):
            detect_handler(src)
