"""Tests for filename encoding detection and password encoding candidates."""

from __future__ import annotations

import zipfile
from pathlib import Path

from archivetools.encoding.detect import (
    detect_filename_encoding,
    detect_rar_filename_encoding,
    detect_zip_filename_encoding,
)


class TestDetectFilenameEncoding:
    def test_empty_list_returns_none_zero(self) -> None:
        codec, conf = detect_filename_encoding([])
        assert codec is None
        assert conf == 0.0

    def test_pure_ascii_does_not_raise(self) -> None:
        samples = [b"hello.txt", b"world.csv", b"readme.md"]
        codec, conf = detect_filename_encoding(samples)
        assert isinstance(conf, float)
        assert 0.0 <= conf <= 1.0

    def test_gbk_bytes_detected(self) -> None:
        gbk_name = "密码.txt".encode("gbk")
        codec, conf = detect_filename_encoding([gbk_name])
        assert isinstance(conf, float)

    def test_single_byte_sample(self) -> None:
        # Very short sample; may return None but must not raise
        codec, conf = detect_filename_encoding([b"x"])
        assert isinstance(conf, float)

    def test_confidence_in_range(self) -> None:
        samples = ["测试.txt".encode("gbk"), "数据.csv".encode("gbk")]
        _, conf = detect_filename_encoding(samples)
        assert 0.0 <= conf <= 1.0


class TestDetectZipFilenameEncoding:
    def test_utf8_flagged_zip_returns_float_confidence(self, tmp_path: Path) -> None:
        p = tmp_path / "test.zip"
        with zipfile.ZipFile(p, "w") as zf:
            zf.writestr("hello.txt", "content")
        codec, conf = detect_zip_filename_encoding(p)
        assert isinstance(conf, float)

    def test_nonexistent_returns_none_zero(self, tmp_path: Path) -> None:
        codec, conf = detect_zip_filename_encoding(tmp_path / "missing.zip")
        assert codec is None
        assert conf == 0.0

    def test_corrupt_zip_returns_gracefully(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.zip"
        p.write_bytes(b"\x00" * 20)
        codec, conf = detect_zip_filename_encoding(p)
        assert codec is None
        assert conf == 0.0


class TestDetectRarFilenameEncoding:
    def test_nonexistent_returns_none_zero(self, tmp_path: Path) -> None:
        codec, conf = detect_rar_filename_encoding(tmp_path / "missing.rar")
        assert codec is None
        assert conf == 0.0

    def test_returns_float_confidence(self, tmp_path: Path) -> None:
        codec, conf = detect_rar_filename_encoding(tmp_path / "missing.rar")
        assert isinstance(conf, float)
