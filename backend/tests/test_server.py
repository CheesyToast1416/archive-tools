"""Integration tests for the FastAPI server layer.

Uses FastAPI's TestClient (synchronous ASGI transport) so no uvicorn needed.
The ``client`` and ``auth`` fixtures come from conftest.py.

SSE endpoints are exercised by reading the complete response body and parsing
the event-stream format via ``conftest.parse_sse``.
"""

from __future__ import annotations

import time
import zipfile
from pathlib import Path

from tests.conftest import parse_sse

# ── Health ────────────────────────────────────────────────────────────────────


class TestHealth:
    def test_health_no_auth_required(self, client) -> None:
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"ok": True}


# ── Auth ──────────────────────────────────────────────────────────────────────


class TestAuth:
    def test_missing_token_returns_401(self, client) -> None:
        assert client.get("/settings/app").status_code == 401

    def test_wrong_token_returns_401(self, client) -> None:
        r = client.get("/settings/app", headers={"Authorization": "Bearer wrongtoken"})
        assert r.status_code == 401

    def test_malformed_header_returns_401(self, client) -> None:
        r = client.get("/settings/app", headers={"Authorization": "Basic notbearer"})
        assert r.status_code == 401

    def test_correct_token_accepted(self, client, auth) -> None:
        assert client.get("/settings/app", headers=auth).status_code == 200


# ── Settings ──────────────────────────────────────────────────────────────────


class TestSettings:
    def test_get_app_settings_has_expected_keys(self, client, auth) -> None:
        data = client.get("/settings/app", headers=auth).json()
        assert {
            "smart_extraction",
            "trash_after_extract",
            "default_output_dir",
            "trash_after_create",
            "trash_after_batch",
            "default_password_encoding",
            "default_filename_encoding",
            "notifications_enabled",
        } == set(data.keys())

    def test_put_app_settings_persists(self, client, auth) -> None:
        original = client.get("/settings/app", headers=auth).json()
        try:
            modified = {**original, "default_output_dir": "/tmp/test_atout"}
            r = client.put("/settings/app", json=modified, headers=auth)
            assert r.status_code == 200
            assert r.json()["ok"] is True
            assert (
                client.get("/settings/app", headers=auth).json()["default_output_dir"]
                == "/tmp/test_atout"
            )
        finally:
            client.put("/settings/app", json=original, headers=auth)

    def test_get_ui_state_has_expected_keys(self, client, auth) -> None:
        data = client.get("/settings/ui", headers=auth).json()
        for key in ("theme", "active_nav", "recent_archives", "last_archive_dir"):
            assert key in data

    def test_put_ui_state_trims_recent_to_15(self, client, auth) -> None:
        original = client.get("/settings/ui", headers=auth).json()
        try:
            big = [f"/path/archive_{i}.zip" for i in range(20)]
            client.put(
                "/settings/ui", json={**original, "recent_archives": big}, headers=auth
            )
            updated = client.get("/settings/ui", headers=auth).json()
            assert len(updated["recent_archives"]) == 15
        finally:
            client.put("/settings/ui", json=original, headers=auth)


# ── Passwords ─────────────────────────────────────────────────────────────────


class TestPasswords:
    def test_list_returns_list(self, client, auth) -> None:
        assert isinstance(client.get("/passwords/", headers=auth).json(), list)

    def test_keyring_status_has_field(self, client, auth) -> None:
        assert (
            "keyring_available"
            in client.get("/passwords/keyring-status", headers=auth).json()
        )

    def test_add_retrieve_delete_lifecycle(self, client, auth) -> None:
        r = client.post(
            "/passwords/",
            json={"label": "test_label", "password": "s3cr3t", "hint": "a hint"},
            headers=auth,
        )
        assert r.status_code == 200
        entry = r.json()
        assert entry["label"] == "test_label"
        assert entry["hint"] == "a hint"
        entry_id = entry["id"]

        r2 = client.get(f"/passwords/{entry_id}/secret", headers=auth)
        assert r2.json()["password"] == "s3cr3t"

        assert client.delete(f"/passwords/{entry_id}", headers=auth).status_code == 200
        entries = client.get("/passwords/", headers=auth).json()
        assert not any(e["id"] == entry_id for e in entries)

    def test_delete_nonexistent_is_idempotent(self, client, auth) -> None:
        r = client.delete(
            "/passwords/00000000-0000-0000-0000-000000000000", headers=auth
        )
        assert r.status_code == 200


# ── Archive: list ─────────────────────────────────────────────────────────────


class TestArchiveList:
    def test_list_simple_zip(self, client, auth, simple_zip) -> None:
        r = client.post(
            "/archives/list", json={"archive_path": str(simple_zip)}, headers=auth
        )
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert "hello.txt" in data["names"]

    def test_list_nonexistent_returns_500(self, client, auth) -> None:
        assert (
            client.post(
                "/archives/list",
                json={"archive_path": "/no/such/file.zip"},
                headers=auth,
            ).status_code
            == 500
        )

    def test_list_aes_zip_names_visible_without_password(
        self, client, auth, encrypted_zip
    ) -> None:
        r = client.post(
            "/archives/list",
            json={"archive_path": str(encrypted_zip), "password": "wrong"},
            headers=auth,
        )
        assert r.status_code == 200
        assert r.json()["ok"] is True
        assert "secret.txt" in r.json()["names"]

    def test_list_with_correct_password(self, client, auth, encrypted_zip) -> None:
        r = client.post(
            "/archives/list",
            json={
                "archive_path": str(encrypted_zip),
                "password": "correcthorsebattery",
            },
            headers=auth,
        )
        assert r.json()["ok"] is True


# ── Archive: info ─────────────────────────────────────────────────────────────


class TestArchiveInfo:
    def test_info_simple_zip(self, client, auth, simple_zip) -> None:
        r = client.post(
            "/archives/info", json={"archive_path": str(simple_zip)}, headers=auth
        )
        assert r.status_code == 200
        data = r.json()
        assert data["format_name"] == "ZIP"
        assert data["file_count"] == 2
        assert data["is_encrypted"] is False

    def test_info_nonexistent_returns_500(self, client, auth) -> None:
        assert (
            client.post(
                "/archives/info", json={"archive_path": "/no/such.zip"}, headers=auth
            ).status_code
            == 500
        )


# ── Archive: detect encoding ──────────────────────────────────────────────────


class TestDetectEncoding:
    def test_utf8_zip_returns_float_confidence(self, client, auth, simple_zip) -> None:
        r = client.post(
            "/archives/detect-encoding",
            json={"archive_path": str(simple_zip)},
            headers=auth,
        )
        assert r.status_code == 200
        data = r.json()
        assert "encoding" in data
        assert 0.0 <= data["confidence"] <= 1.0

    def test_tar_returns_null_encoding(self, client, auth, simple_tar) -> None:
        r = client.post(
            "/archives/detect-encoding",
            json={"archive_path": str(simple_tar)},
            headers=auth,
        )
        assert r.status_code == 200
        assert r.json()["encoding"] is None


# ── Archive: test integrity ───────────────────────────────────────────────────


class TestArchiveTest:
    def test_valid_zip_passes(self, client, auth, simple_zip) -> None:
        r = client.post(
            "/archives/test", json={"archive_path": str(simple_zip)}, headers=auth
        )
        assert r.status_code == 200
        assert r.json()["ok"] is True
        assert r.json()["failed"] == []

    def test_nonexistent_returns_500(self, client, auth) -> None:
        assert (
            client.post(
                "/archives/test", json={"archive_path": "/no/such.zip"}, headers=auth
            ).status_code
            == 500
        )


# ── Archive: create ───────────────────────────────────────────────────────────


class TestArchiveCreate:
    def test_create_zip(self, client, auth, tmp_path) -> None:
        src = tmp_path / "source.txt"
        src.write_text("test content")
        out = tmp_path / "output.zip"
        r = client.post(
            "/archives/create",
            json={"output_path": str(out), "files": [str(src)], "format": "zip"},
            headers=auth,
        )
        assert r.status_code == 200
        assert r.json()["ok"] is True
        with zipfile.ZipFile(out) as zf:
            assert "source.txt" in zf.namelist()

    def test_create_invalid_format_returns_500(self, client, auth, tmp_path) -> None:
        src = tmp_path / "f.txt"
        src.write_text("x")
        r = client.post(
            "/archives/create",
            json={
                "output_path": str(tmp_path / "out.xyz"),
                "files": [str(src)],
                "format": "notaformat",
            },
            headers=auth,
        )
        assert r.status_code == 500


# ── Archive: convert ──────────────────────────────────────────────────────────


class TestArchiveConvert:
    def test_zip_to_tar_gz(self, client, auth, simple_zip, tmp_path) -> None:
        out = tmp_path / "out.tar.gz"
        r = client.post(
            "/archives/convert",
            json={
                "input_path": str(simple_zip),
                "output_path": str(out),
                "output_format": "tar.gz",
            },
            headers=auth,
        )
        assert r.status_code == 200
        assert r.json()["ok"] is True
        assert out.exists()

    def test_zip_to_7z(self, client, auth, simple_zip, tmp_path) -> None:
        out = tmp_path / "out.7z"
        r = client.post(
            "/archives/convert",
            json={
                "input_path": str(simple_zip),
                "output_path": str(out),
                "output_format": "7z",
            },
            headers=auth,
        )
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_nonexistent_source_returns_500(self, client, auth, tmp_path) -> None:
        r = client.post(
            "/archives/convert",
            json={
                "input_path": "/no/such.zip",
                "output_path": str(tmp_path / "out.7z"),
                "output_format": "7z",
            },
            headers=auth,
        )
        assert r.status_code == 500

    def test_unsupported_output_format_returns_500(
        self, client, auth, simple_zip, tmp_path
    ) -> None:
        r = client.post(
            "/archives/convert",
            json={
                "input_path": str(simple_zip),
                "output_path": str(tmp_path / "out.rar"),
                "output_format": "rar",
            },
            headers=auth,
        )
        assert r.status_code == 500


# ── Archive: update ───────────────────────────────────────────────────────────


class TestArchiveUpdate:
    def test_add_file_to_zip(self, client, auth, simple_zip, tmp_path) -> None:
        new_file = tmp_path / "extra.txt"
        new_file.write_text("extra content")
        r = client.post(
            "/archives/update",
            json={
                "archive_path": str(simple_zip),
                "files_to_add": [str(new_file)],
                "paths_to_remove": [],
            },
            headers=auth,
        )
        assert r.status_code == 200
        assert r.json()["ok"] is True
        with zipfile.ZipFile(simple_zip) as zf:
            assert "extra.txt" in zf.namelist()

    def test_remove_entry_from_zip(self, client, auth, tmp_path) -> None:
        p = tmp_path / "a.zip"
        with zipfile.ZipFile(p, "w") as zf:
            zf.writestr("keep.txt", "keep")
            zf.writestr("drop.txt", "drop")
        r = client.post(
            "/archives/update",
            json={
                "archive_path": str(p),
                "files_to_add": [],
                "paths_to_remove": ["drop.txt"],
            },
            headers=auth,
        )
        assert r.status_code == 200
        with zipfile.ZipFile(p) as zf:
            assert "keep.txt" in zf.namelist()
            assert "drop.txt" not in zf.namelist()

    def test_noop_update_returns_ok(self, client, auth, simple_zip) -> None:
        r = client.post(
            "/archives/update",
            json={
                "archive_path": str(simple_zip),
                "files_to_add": [],
                "paths_to_remove": [],
            },
            headers=auth,
        )
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_rar_update_returns_500(self, client, auth, tmp_path) -> None:
        p = tmp_path / "a.rar"
        p.write_bytes(b"Rar!\x1a\x07\x00")
        r = client.post(
            "/archives/update",
            json={"archive_path": str(p), "files_to_add": [], "paths_to_remove": ["x"]},
            headers=auth,
        )
        assert r.status_code == 500


# ── Archive: extract (SSE) ────────────────────────────────────────────────────


class TestArchiveExtractSSE:
    def test_extract_streams_complete_event(
        self, client, auth, simple_zip, tmp_path
    ) -> None:
        out = tmp_path / "out"
        r = client.post(
            "/archives/extract",
            json={
                "archive_path": str(simple_zip),
                "password": "",
                "output_dir": str(out),
                "smart": False,
            },
            headers=auth,
        )
        assert r.status_code == 200
        events = parse_sse(r.text)
        event_types = [e["event"] for e in events]
        assert "complete" in event_types
        complete = next(e for e in events if e["event"] == "complete")
        assert complete["data"]["ok"] is True

    def test_extract_progress_events_emitted(
        self, client, auth, simple_zip, tmp_path
    ) -> None:
        out = tmp_path / "out"
        r = client.post(
            "/archives/extract",
            json={
                "archive_path": str(simple_zip),
                "password": "",
                "output_dir": str(out),
                "smart": False,
            },
            headers=auth,
        )
        events = parse_sse(r.text)
        progress_events = [e for e in events if e["event"] == "progress"]
        assert len(progress_events) > 0

    def test_extract_nonexistent_archive_emits_error(
        self, client, auth, tmp_path
    ) -> None:
        r = client.post(
            "/archives/extract",
            json={
                "archive_path": "/no/such/file.zip",
                "password": "",
                "output_dir": str(tmp_path / "out"),
                "smart": False,
            },
            headers=auth,
        )
        assert r.status_code == 200
        events = parse_sse(r.text)
        event_types = [e["event"] for e in events]
        assert "error" in event_types

    def test_extracted_files_exist_on_disk(
        self, client, auth, simple_zip, tmp_path
    ) -> None:
        out = tmp_path / "out"
        client.post(
            "/archives/extract",
            json={
                "archive_path": str(simple_zip),
                "password": "",
                "output_dir": str(out),
                "smart": False,
            },
            headers=auth,
        )
        assert (out / "hello.txt").exists()


# ── Archive: batch (SSE) ──────────────────────────────────────────────────────


class TestArchiveBatchSSE:
    def _make_zip(self, path: Path, name: str = "f.txt") -> Path:
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr(name, "content")
        return path

    def test_batch_emits_complete_event(self, client, auth, tmp_path) -> None:
        a = self._make_zip(tmp_path / "a.zip", "a.txt")
        b = self._make_zip(tmp_path / "b.zip", "b.txt")
        out = tmp_path / "out"
        r = client.post(
            "/archives/batch",
            json={
                "archives": [str(a), str(b)],
                "output_dir": str(out),
                "password": "",
            },
            headers=auth,
        )
        assert r.status_code == 200
        events = parse_sse(r.text)
        event_types = [e["event"] for e in events]
        assert "complete" in event_types
        complete = next(e for e in events if e["event"] == "complete")
        assert complete["data"]["ok_count"] == 2
        assert complete["data"]["fail_count"] == 0

    def test_batch_emits_archive_started_done(self, client, auth, tmp_path) -> None:
        a = self._make_zip(tmp_path / "a.zip")
        out = tmp_path / "out"
        r = client.post(
            "/archives/batch",
            json={"archives": [str(a)], "output_dir": str(out), "password": ""},
            headers=auth,
        )
        events = parse_sse(r.text)
        event_types = [e["event"] for e in events]
        assert "archive_started" in event_types
        assert "archive_done" in event_types

    def test_batch_bad_archive_counted_as_failure(self, client, auth, tmp_path) -> None:
        bad = tmp_path / "bad.zip"
        bad.write_bytes(b"not a zip")
        good = self._make_zip(tmp_path / "good.zip")
        out = tmp_path / "out"
        r = client.post(
            "/archives/batch",
            json={
                "archives": [str(bad), str(good)],
                "output_dir": str(out),
                "password": "",
            },
            headers=auth,
        )
        events = parse_sse(r.text)
        complete = next((e for e in events if e["event"] == "complete"), None)
        assert complete is not None
        assert complete["data"]["fail_count"] == 1
        assert complete["data"]["ok_count"] == 1


# ── Preview ───────────────────────────────────────────────────────────────────


class TestPreview:
    def test_preview_extracts_entry_to_temp_file(
        self, client, auth, simple_zip
    ) -> None:
        import os

        r = client.post(
            "/preview/",
            json={"archive_path": str(simple_zip), "entry_name": "hello.txt"},
            headers=auth,
        )
        assert r.status_code == 200
        data = r.json()
        assert "temp_id" in data
        assert os.path.isfile(data["file_path"])
        assert open(data["file_path"]).read() == "Hello, world!"

        r2 = client.delete(f"/preview/{data['temp_id']}", headers=auth)
        assert r2.status_code == 200
        assert not os.path.exists(data["file_path"])

    def test_preview_nonexistent_archive_returns_500(self, client, auth) -> None:
        assert (
            client.post(
                "/preview/",
                json={"archive_path": "/no/such.zip", "entry_name": "x.txt"},
                headers=auth,
            ).status_code
            == 500
        )

    def test_cleanup_unknown_temp_id_ok(self, client, auth) -> None:
        r = client.delete("/preview/00000000-0000-0000-0000-000000000000", headers=auth)
        assert r.status_code == 200

    def test_stale_preview_ttl_cleanup(self) -> None:
        import tempfile

        from server.routes.preview import _PREVIEW_DIRS, _PREVIEW_TIMES, _cleanup_stale

        tid = "test-ttl-id"
        tmpdir = tempfile.mkdtemp(prefix="atpreview_test_")
        _PREVIEW_DIRS[tid] = tmpdir
        _PREVIEW_TIMES[tid] = time.monotonic() - 9999

        _cleanup_stale()

        assert tid not in _PREVIEW_DIRS
        assert tid not in _PREVIEW_TIMES
        import os

        assert not os.path.exists(tmpdir)
