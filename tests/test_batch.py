from __future__ import annotations

import tarfile
import zipfile
from pathlib import Path

import pytest

from archivetools.operations import extract_archive, list_archive


def _make_zip(path: Path, entries: dict[str, str] | None = None) -> Path:
    entries = entries or {"hello.txt": "content"}
    with zipfile.ZipFile(path, "w") as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
    return path


def _make_tar(path: Path) -> Path:
    src = path.parent / "src"
    src.mkdir(exist_ok=True)
    (src / "a.txt").write_text("hello")
    with tarfile.open(path, "w") as tf:
        tf.add(src, arcname="src")
    return path


def _smart_extract(archive: Path, output_dir: str | None = None) -> bool:
    """Simulate what BatchExtractionWorker now does: list then smart-extract."""
    _, _, names = list_archive(archive, "", None, None)
    ok, _ = extract_archive(
        archive,
        "",
        output_dir,
        filename_encoding=None,
        password_encoding=None,
        names=names,
        smart=True,
    )
    return ok


class TestBatchExtraction:
    """Tests for BatchExtractionWorker's smart-extraction path."""

    def test_multiple_zips(self, tmp_path: Path) -> None:
        a = _make_zip(tmp_path / "a.zip")
        b = _make_zip(tmp_path / "b.zip", {"data.csv": "x,y"})
        out = tmp_path / "out"
        out.mkdir()
        assert _smart_extract(a, str(out))
        assert _smart_extract(b, str(out))
        assert (out / "hello.txt").exists()
        assert (out / "data.csv").exists()

    def test_zip_and_tar(self, tmp_path: Path) -> None:
        z = _make_zip(tmp_path / "c.zip")
        t = _make_tar(tmp_path / "d.tar")
        out = tmp_path / "out"
        out.mkdir()
        assert _smart_extract(z, str(out))
        assert _smart_extract(t, str(out))

    def test_single_dir_multi_children_no_double_wrap(self, tmp_path: Path) -> None:
        # myapp.zip → myapp/file1.txt, myapp/file2.txt (2 children → keep dir)
        # Without smart: output/myapp/myapp/file1.txt ← double-nested
        # With smart:    output/myapp/file1.txt        ← correct
        z = _make_zip(
            tmp_path / "myapp.zip", {"myapp/file1.txt": "x", "myapp/file2.txt": "y"}
        )
        out = tmp_path / "out"
        out.mkdir()
        assert _smart_extract(z, str(out))
        assert (out / "myapp" / "file1.txt").exists()
        assert not (out / "myapp" / "myapp").exists(), "double-nesting still present"

    def test_single_dir_one_child_unwrapped(self, tmp_path: Path) -> None:
        # myapp.zip → myapp/only.txt (1 child → unwrap the wrapper dir)
        # With smart: output/only.txt
        z = _make_zip(tmp_path / "myapp.zip", {"myapp/only.txt": "x"})
        out = tmp_path / "out"
        out.mkdir()
        assert _smart_extract(z, str(out))
        assert (out / "only.txt").exists()
        assert not (out / "myapp").exists(), "wrapper not collapsed"

    def test_multi_archive_wrapped(self, tmp_path: Path) -> None:
        # Archive files.zip containing file1.txt, file2.txt (no top-level dir)
        # Should be wrapped: output/files/file1.txt
        z = _make_zip(tmp_path / "files.zip", {"file1.txt": "a", "file2.txt": "b"})
        out = tmp_path / "out"
        out.mkdir()
        assert _smart_extract(z, str(out))
        assert (out / "files" / "file1.txt").exists()
        assert (out / "files" / "file2.txt").exists()

    def test_nonexistent_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            extract_archive(
                tmp_path / "missing.zip",
                "",
                None,
                filename_encoding=None,
                password_encoding=None,
            )
