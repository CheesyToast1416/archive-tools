from __future__ import annotations

import zipfile

import pytest

from archivetools.core import (
    RarHandler,
    SevenZipHandler,
    ZipHandler,
    _default_output_dir,
    detect_handler,
    password_candidates,
)


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
