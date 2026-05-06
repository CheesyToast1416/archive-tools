from __future__ import annotations

import tarfile
import zipfile
from pathlib import Path

from archivetools.formats.tar import TarHandler
from archivetools.formats.zip import ZipHandler
from archivetools.operations.extract import extract_cjk


def _make_zip(tmp_path: Path, n_files: int = 3) -> Path:
    p = tmp_path / "test.zip"
    with zipfile.ZipFile(p, "w") as zf:
        for i in range(n_files):
            zf.writestr(f"file{i}.txt", f"content {i}")
    return p


def _make_tar(tmp_path: Path, n_files: int = 3) -> Path:
    src = tmp_path / "src"
    src.mkdir()
    for i in range(n_files):
        (src / f"file{i}.txt").write_text(f"content {i}")
    p = tmp_path / "test.tar"
    with tarfile.open(p, "w") as tf:
        tf.add(src, arcname="src")
    return p


class TestProgressCallback:
    def test_zip_calls_progress(self, tmp_path):
        archive = _make_zip(tmp_path, n_files=4)
        out = tmp_path / "out"
        out.mkdir()
        calls = []
        ZipHandler()._try_extract(
            archive,
            b"",
            out,
            None,
            progress=lambda c, t, f: calls.append((c, t)),
        )
        assert len(calls) == 4
        assert calls[-1] == (4, 4)
        # values are monotonically increasing
        assert [c for c, _ in calls] == list(range(1, 5))

    def test_tar_calls_progress(self, tmp_path):
        archive = _make_tar(tmp_path, n_files=3)
        out = tmp_path / "out"
        out.mkdir()
        calls = []
        TarHandler().extract(
            archive,
            "",
            out,
            progress=lambda c, t, f: calls.append((c, t)),
        )
        assert len(calls) > 0
        totals = {t for _, t in calls}
        assert len(totals) == 1  # consistent total throughout
        assert calls[-1][0] == calls[-1][1]  # last call: current == total

    def test_no_progress_arg_still_works(self, tmp_path):
        archive = _make_zip(tmp_path)
        out = tmp_path / "out"
        out.mkdir()
        ok, _ = ZipHandler().extract(archive, "", out)
        assert ok is True

    def test_extract_cjk_progress(self, tmp_path):
        archive = _make_zip(tmp_path, n_files=5)
        out = tmp_path / "out"
        calls = []
        ok, _ = extract_cjk(
            archive,
            "",
            str(out),
            filename_encoding=None,
            password_encoding=None,
            progress=lambda c, t, f: calls.append(c),
        )
        assert ok is True
        assert calls == list(range(1, 6))
