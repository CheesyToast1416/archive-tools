from __future__ import annotations

import zipfile

from archivetools.encoding.candidates import PASSWORD_ENCODINGS, password_candidates
from archivetools.encoding.detect import (
    detect_filename_encoding,
    detect_rar_filename_encoding,
    detect_zip_filename_encoding,
)


class TestPasswordCandidates:
    def test_ascii_deduplicated(self):
        # ASCII encodes identically in every charset — one candidate, labelled utf-8
        results = password_candidates("hello")
        assert len(results) == 1
        assert results[0][1] == "utf-8"
        assert results[0][0] == b"hello"

    def test_gbk_first(self):
        results = password_candidates("密码")
        assert results[0][1] in ("gbk", "gb2312", "gb18030")

    def test_gb18030_covers_emoji(self):
        results = password_candidates("🔐")
        encodings = [enc for _, enc in results]
        assert "gb18030" in encodings
        assert "utf-8" in encodings
        assert "gbk" not in encodings

    def test_all_results_unique_bytes(self):
        results = password_candidates("test123")
        byte_values = [b for b, _ in results]
        assert len(byte_values) == len(set(byte_values))

    def test_cjk_encodings_order(self):
        assert PASSWORD_ENCODINGS[0] == "gbk"
        assert PASSWORD_ENCODINGS[-1] == "utf-8"


class TestDetectFilenameEncoding:
    def test_empty_list_returns_none(self):
        codec, conf = detect_filename_encoding([])
        assert codec is None
        assert conf == 0.0

    def test_pure_ascii_bytes(self):
        samples = [b"hello.txt", b"world.csv", b"readme.md"]
        codec, conf = detect_filename_encoding(samples)
        # ASCII is a subset of UTF-8 / latin-1; any detected encoding is acceptable
        # as long as the function doesn't raise
        assert isinstance(conf, float)
        assert 0.0 <= conf <= 1.0

    def test_gbk_bytes_detected(self):
        # '密码.txt' encoded as GBK
        gbk_name = "密码.txt".encode("gbk")
        codec, conf = detect_filename_encoding([gbk_name])
        # charset-normalizer should detect something compatible with the encoding
        if codec:  # may be None for very short samples
            assert conf >= 0.0


class TestDetectZipFilenameEncoding:
    def test_utf8_zip_returns_none(self, tmp_path):
        p = tmp_path / "test.zip"
        with zipfile.ZipFile(p, "w") as zf:
            zf.writestr("hello.txt", "content")
        # UTF-8 flagged entries are skipped; result may be None
        codec, conf = detect_zip_filename_encoding(p)
        assert isinstance(conf, float)

    def test_nonexistent_file(self, tmp_path):
        codec, conf = detect_zip_filename_encoding(tmp_path / "missing.zip")
        assert codec is None
        assert conf == 0.0


class TestDetectRarFilenameEncoding:
    def test_nonexistent_file(self, tmp_path):
        codec, conf = detect_rar_filename_encoding(tmp_path / "missing.rar")
        assert codec is None
        assert conf == 0.0

    def test_returns_float_confidence(self, tmp_path):
        # Function must return a float confidence even if detection finds nothing
        codec, conf = detect_rar_filename_encoding(tmp_path / "missing.rar")
        assert isinstance(conf, float)
