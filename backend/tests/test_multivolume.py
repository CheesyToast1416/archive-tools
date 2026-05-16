from __future__ import annotations

from pathlib import Path

from archivetools._multivolume import (
    _7z_first_part,
    _find_numbered_parts,
    _find_zip_split_parts,
    _rar_first_part,
)


class TestFindNumberedParts:
    def test_three_parts(self, tmp_path):
        for i in range(1, 4):
            (tmp_path / f"archive.zip.{i:03d}").touch()
        parts = _find_numbered_parts(tmp_path / "archive.zip.001")
        assert [p.name for p in parts] == [
            "archive.zip.001",
            "archive.zip.002",
            "archive.zip.003",
        ]

    def test_single_part_returns_empty(self, tmp_path):
        (tmp_path / "archive.zip.001").touch()
        assert _find_numbered_parts(tmp_path / "archive.zip.001") == []

    def test_non_numbered_returns_empty(self, tmp_path):
        p = tmp_path / "archive.zip"
        p.touch()
        assert _find_numbered_parts(p) == []


class TestFindZipSplitParts:
    def _make_split(self, tmp_path: Path, n: int) -> None:
        for i in range(1, n + 1):
            (tmp_path / f"archive.z{i:02d}").touch()
        (tmp_path / "archive.zip").touch()

    def test_from_z01(self, tmp_path):
        self._make_split(tmp_path, 2)
        parts = _find_zip_split_parts(tmp_path / "archive.z01")
        names = {p.name for p in parts}
        assert {"archive.z01", "archive.z02", "archive.zip"} == names

    def test_from_zip(self, tmp_path):
        self._make_split(tmp_path, 2)
        parts = _find_zip_split_parts(tmp_path / "archive.zip")
        assert len(parts) == 3

    def test_plain_zip_no_z_parts(self, tmp_path):
        (tmp_path / "archive.zip").touch()
        assert _find_zip_split_parts(tmp_path / "archive.zip") == []


class TestRarFirstPart:
    def test_new_style(self, tmp_path):
        (tmp_path / "file.part1.rar").touch()
        (tmp_path / "file.part2.rar").touch()
        assert (
            _rar_first_part(tmp_path / "file.part2.rar") == tmp_path / "file.part1.rar"
        )

    def test_old_style(self, tmp_path):
        (tmp_path / "file.rar").touch()
        (tmp_path / "file.r00").touch()
        assert _rar_first_part(tmp_path / "file.r00") == tmp_path / "file.rar"

    def test_already_first_part(self, tmp_path):
        p = tmp_path / "file.rar"
        p.touch()
        assert _rar_first_part(p) == p


class Test7zFirstPart:
    def test_from_later_part(self, tmp_path):
        (tmp_path / "arch.7z.001").touch()
        (tmp_path / "arch.7z.003").touch()
        assert _7z_first_part(tmp_path / "arch.7z.003") == tmp_path / "arch.7z.001"

    def test_non_numbered(self, tmp_path):
        p = tmp_path / "arch.7z"
        p.touch()
        assert _7z_first_part(p) == p
