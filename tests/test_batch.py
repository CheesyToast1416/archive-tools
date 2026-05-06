from __future__ import annotations

import tarfile
import zipfile
from pathlib import Path

import pytest

from archivetools.operations import extract_cjk


def _make_zip(path: Path, name: str = "hello.txt") -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(name, "content")
    return path


def _make_tar(path: Path) -> Path:
    src = path.parent / "src"
    src.mkdir(exist_ok=True)
    (src / "a.txt").write_text("hello")
    with tarfile.open(path, "w") as tf:
        tf.add(src, arcname="src")
    return path


class TestBatchExtraction:
    """Test the underlying extract_cjk() used by BatchExtractionWorker."""

    def test_multiple_zips(self, tmp_path: Path) -> None:
        a = _make_zip(tmp_path / "a.zip")
        b = _make_zip(tmp_path / "b.zip", "data.csv")
        out_a = tmp_path / "out_a"
        out_b = tmp_path / "out_b"
        ok_a, _ = extract_cjk(
            a, "", str(out_a), filename_encoding=None, password_encoding=None
        )
        ok_b, _ = extract_cjk(
            b, "", str(out_b), filename_encoding=None, password_encoding=None
        )
        assert ok_a and ok_b
        assert (out_a / "hello.txt").exists()
        assert (out_b / "data.csv").exists()

    def test_zip_and_tar(self, tmp_path: Path) -> None:
        z = _make_zip(tmp_path / "c.zip")
        t = _make_tar(tmp_path / "d.tar")
        out_z = tmp_path / "out_z"
        out_t = tmp_path / "out_t"
        ok_z, _ = extract_cjk(
            z, "", str(out_z), filename_encoding=None, password_encoding=None
        )
        ok_t, _ = extract_cjk(
            t, "", str(out_t), filename_encoding=None, password_encoding=None
        )
        assert ok_z and ok_t

    def test_nonexistent_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            extract_cjk(
                tmp_path / "missing.zip",
                "",
                None,
                filename_encoding=None,
                password_encoding=None,
            )
