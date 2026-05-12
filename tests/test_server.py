"""Integration tests for the FastAPI server layer.

These tests use FastAPI's TestClient (synchronous ASGI transport via httpx)
so no running uvicorn process is needed.  The TOKEN is imported directly from
server._token so it matches what the auth middleware checks.
"""

from __future__ import annotations

import io
import time
import zipfile

import pytest
from fastapi.testclient import TestClient

from server._token import TOKEN
from server.main import create_app

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def client():
    """Shared TestClient for the full FastAPI app."""
    app = create_app()
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def auth(client):
    """Shorthand: returns auth headers dict."""
    return {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def simple_zip(tmp_path):
    """A minimal ZIP archive containing one text file."""
    p = tmp_path / "sample.zip"
    with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("hello.txt", "Hello, world!")
        zf.writestr("subdir/nested.txt", "nested content")
    return p


@pytest.fixture
def encrypted_zip(tmp_path):
    """A ZIP archive protected with a known password (uses ZipFile's simple pwd)."""
    import pyzipper

    p = tmp_path / "secret.zip"
    with pyzipper.AESZipFile(p, "w", encryption=pyzipper.WZ_AES) as zf:
        zf.setpassword(b"correcthorsebattery")
        zf.writestr("secret.txt", "top secret")
    return p


# ── Auth ──────────────────────────────────────────────────────────────────────


class TestAuth:
    def test_health_no_auth_required(self, client):
        """GET /health is the only endpoint that skips token validation."""
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"ok": True}

    def test_missing_token_returns_401(self, client):
        r = client.get("/settings/app")
        assert r.status_code == 401

    def test_wrong_token_returns_401(self, client):
        r = client.get("/settings/app", headers={"Authorization": "Bearer wrongtoken"})
        assert r.status_code == 401

    def test_malformed_header_returns_401(self, client):
        r = client.get("/settings/app", headers={"Authorization": "Basic notbearer"})
        assert r.status_code == 401

    def test_correct_token_accepted(self, client, auth):
        r = client.get("/settings/app", headers=auth)
        assert r.status_code == 200


# ── Settings ──────────────────────────────────────────────────────────────────


class TestSettings:
    def test_get_app_settings_shape(self, client, auth):
        r = client.get("/settings/app", headers=auth)
        assert r.status_code == 200
        data = r.json()
        expected_keys = {
            "smart_extraction",
            "trash_after_extract",
            "default_output_dir",
            "trash_after_create",
            "trash_after_batch",
            "default_password_encoding",
            "default_filename_encoding",
            "notifications_enabled",
        }
        assert expected_keys == set(data.keys())

    def test_put_app_settings_roundtrip(self, client, auth):
        # Read current state
        original = client.get("/settings/app", headers=auth).json()
        # Modify one field
        modified = {**original, "default_output_dir": "/tmp/test_output"}
        r = client.put("/settings/app", json=modified, headers=auth)
        assert r.status_code == 200
        assert r.json()["ok"] is True
        # Verify persisted
        updated = client.get("/settings/app", headers=auth).json()
        assert updated["default_output_dir"] == "/tmp/test_output"
        # Restore
        client.put("/settings/app", json=original, headers=auth)

    def test_get_ui_state_shape(self, client, auth):
        r = client.get("/settings/ui", headers=auth)
        assert r.status_code == 200
        data = r.json()
        assert "theme" in data
        assert "active_nav" in data
        assert "recent_archives" in data
        assert "last_archive_dir" in data
        # window_geometry must NOT be present (Tauri owns it)
        assert "window_geometry" not in data

    def test_put_ui_state_trims_recent_to_15(self, client, auth):
        original = client.get("/settings/ui", headers=auth).json()
        big_list = [f"/path/archive_{i}.zip" for i in range(20)]
        r = client.put(
            "/settings/ui", json={**original, "recent_archives": big_list}, headers=auth
        )
        assert r.status_code == 200
        updated = client.get("/settings/ui", headers=auth).json()
        assert len(updated["recent_archives"]) == 15
        # Restore
        client.put("/settings/ui", json=original, headers=auth)


# ── Passwords ─────────────────────────────────────────────────────────────────


class TestPasswords:
    def test_list_returns_list(self, client, auth):
        r = client.get("/passwords/", headers=auth)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_keyring_status_shape(self, client, auth):
        r = client.get("/passwords/keyring-status", headers=auth)
        assert r.status_code == 200
        assert "keyring_available" in r.json()

    def test_add_and_delete_password(self, client, auth):
        # Add
        r = client.post(
            "/passwords/",
            json={"label": "test_label", "password": "s3cr3t", "hint": "a hint"},
            headers=auth,
        )
        assert r.status_code == 200
        entry = r.json()
        assert entry["label"] == "test_label"
        assert entry["hint"] == "a hint"
        assert "id" in entry

        # Retrieve secret
        entry_id = entry["id"]
        r2 = client.get(f"/passwords/{entry_id}/secret", headers=auth)
        assert r2.status_code == 200
        assert r2.json()["password"] == "s3cr3t"

        # Delete
        r3 = client.delete(f"/passwords/{entry_id}", headers=auth)
        assert r3.status_code == 200

        # Verify removed from metadata list
        entries = client.get("/passwords/", headers=auth).json()
        assert not any(e["id"] == entry_id for e in entries)

    def test_delete_nonexistent_is_idempotent(self, client, auth):
        # PasswordStore.delete silently ignores unknown IDs — that's acceptable
        r = client.delete(
            "/passwords/00000000-0000-0000-0000-000000000000", headers=auth
        )
        assert r.status_code == 200


# ── Archive: list ─────────────────────────────────────────────────────────────


class TestArchiveList:
    def test_list_simple_zip(self, client, auth, simple_zip):
        r = client.post(
            "/archives/list", json={"archive_path": str(simple_zip)}, headers=auth
        )
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert "hello.txt" in data["names"]
        assert "subdir/nested.txt" in data["names"]

    def test_list_nonexistent_returns_500(self, client, auth):
        r = client.post(
            "/archives/list", json={"archive_path": "/no/such/file.zip"}, headers=auth
        )
        assert r.status_code == 500

    def test_list_encrypted_zip_names_always_readable(
        self, client, auth, encrypted_zip
    ):
        # AES-ZIP encrypts file *content* but not the directory (entry names are always
        # visible regardless of password).  list_archive returns ok=True even with
        # wrong password for AES-ZIP.  Only extraction would fail.
        r = client.post(
            "/archives/list",
            json={"archive_path": str(encrypted_zip), "password": "wrongpass"},
            headers=auth,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert "secret.txt" in data["names"]

    def test_list_correct_password(self, client, auth, encrypted_zip):
        r = client.post(
            "/archives/list",
            json={
                "archive_path": str(encrypted_zip),
                "password": "correcthorsebattery",
            },
            headers=auth,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert "secret.txt" in data["names"]


# ── Archive: info ─────────────────────────────────────────────────────────────


class TestArchiveInfo:
    def test_info_simple_zip(self, client, auth, simple_zip):
        r = client.post(
            "/archives/info", json={"archive_path": str(simple_zip)}, headers=auth
        )
        assert r.status_code == 200
        data = r.json()
        assert data["format_name"] == "ZIP"
        assert data["file_count"] == 2
        assert data["is_encrypted"] is False

    def test_info_nonexistent_returns_500(self, client, auth):
        r = client.post(
            "/archives/info", json={"archive_path": "/no/such/file.zip"}, headers=auth
        )
        assert r.status_code == 500


# ── Archive: detect encoding ──────────────────────────────────────────────────


class TestDetectEncoding:
    def test_utf8_zip_returns_none_or_utf8(self, client, auth, simple_zip):
        r = client.post(
            "/archives/detect-encoding",
            json={"archive_path": str(simple_zip)},
            headers=auth,
        )
        assert r.status_code == 200
        data = r.json()
        assert "encoding" in data
        assert "confidence" in data
        assert 0.0 <= data["confidence"] <= 1.0

    def test_non_zip_returns_null_encoding(self, client, auth, tmp_path):
        tar = tmp_path / "test.tar"
        import tarfile

        with tarfile.open(tar, "w") as tf:
            info = tarfile.TarInfo("file.txt")
            info.size = 5
            tf.addfile(info, io.BytesIO(b"hello"))
        r = client.post(
            "/archives/detect-encoding", json={"archive_path": str(tar)}, headers=auth
        )
        assert r.status_code == 200
        assert r.json()["encoding"] is None


# ── Archive: test integrity ───────────────────────────────────────────────────


class TestArchiveTest:
    def test_valid_zip(self, client, auth, simple_zip):
        r = client.post(
            "/archives/test", json={"archive_path": str(simple_zip)}, headers=auth
        )
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert data["failed"] == []

    def test_nonexistent_returns_500(self, client, auth):
        r = client.post(
            "/archives/test", json={"archive_path": "/no/such.zip"}, headers=auth
        )
        assert r.status_code == 500


# ── Archive: create ───────────────────────────────────────────────────────────


class TestArchiveCreate:
    def test_create_zip(self, client, auth, tmp_path):
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
        assert out.exists()
        # Verify the created archive is valid
        with zipfile.ZipFile(out) as zf:
            assert "source.txt" in zf.namelist()

    def test_create_invalid_format_returns_500(self, client, auth, tmp_path):
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


# ── Preview: temp dir lifecycle ───────────────────────────────────────────────


class TestPreview:
    def test_preview_valid_entry(self, client, auth, simple_zip):
        r = client.post(
            "/preview/",
            json={"archive_path": str(simple_zip), "entry_name": "hello.txt"},
            headers=auth,
        )
        assert r.status_code == 200
        data = r.json()
        assert "temp_id" in data
        assert "file_path" in data
        import os

        assert os.path.isfile(data["file_path"])

        # Content should match what we wrote
        with open(data["file_path"]) as f:
            assert f.read() == "Hello, world!"

        # Cleanup
        r2 = client.delete(f"/preview/{data['temp_id']}", headers=auth)
        assert r2.status_code == 200
        assert not os.path.exists(data["file_path"])

    def test_preview_nonexistent_archive_returns_500(self, client, auth):
        r = client.post(
            "/preview/",
            json={"archive_path": "/no/such.zip", "entry_name": "file.txt"},
            headers=auth,
        )
        assert r.status_code == 500

    def test_cleanup_nonexistent_temp_id_ok(self, client, auth):
        """Deleting an unknown temp_id should not error."""
        r = client.delete("/preview/00000000-0000-0000-0000-000000000000", headers=auth)
        assert r.status_code == 200

    def test_stale_preview_ttl_cleanup(self, tmp_path):
        """_cleanup_stale() removes dirs older than max age."""
        import tempfile

        from server.routes.preview import _PREVIEW_DIRS, _PREVIEW_TIMES, _cleanup_stale

        tid = "test-ttl-id"
        tmpdir = tempfile.mkdtemp(prefix="atpreview_test_")
        _PREVIEW_DIRS[tid] = tmpdir
        _PREVIEW_TIMES[tid] = time.monotonic() - 9999  # force it to be old

        _cleanup_stale()

        assert tid not in _PREVIEW_DIRS
        assert tid not in _PREVIEW_TIMES
        import os

        assert not os.path.exists(tmpdir)
