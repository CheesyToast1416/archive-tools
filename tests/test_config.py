"""Tests for config.settings and config.passwords (no GUI, no keyring needed)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from archivetools.config.settings import AppSettings, _reset_for_tests, get_settings

# ── AppSettings ───────────────────────────────────────────────────────────────


class TestAppSettings:
    def test_defaults(self) -> None:
        s = AppSettings()
        assert s.smart_extraction is True
        assert s.trash_after_extract is False
        assert s.default_password_encoding == ""
        assert s.active_tab == 0

    def test_load_from_file(self, tmp_path: Path) -> None:
        cfg = tmp_path / "settings.json"
        cfg.write_text(
            json.dumps({"smart_extraction": False, "active_tab": 3}), encoding="utf-8"
        )
        with patch("archivetools.config.settings._SETTINGS_PATH", cfg):
            s = AppSettings.load()
        assert s.smart_extraction is False
        assert s.active_tab == 3
        # Unset fields use defaults
        assert s.trash_after_extract is False

    def test_load_ignores_unknown_keys(self, tmp_path: Path) -> None:
        cfg = tmp_path / "settings.json"
        cfg.write_text(
            json.dumps({"unknown_future_key": True, "active_tab": 2}),
            encoding="utf-8",
        )
        with patch("archivetools.config.settings._SETTINGS_PATH", cfg):
            s = AppSettings.load()
        assert s.active_tab == 2  # known key loaded
        assert not hasattr(s, "unknown_future_key")

    def test_load_corrupt_file_returns_defaults(self, tmp_path: Path) -> None:
        cfg = tmp_path / "settings.json"
        cfg.write_bytes(b"not valid json {{")
        with patch("archivetools.config.settings._SETTINGS_PATH", cfg):
            s = AppSettings.load()
        assert s == AppSettings()  # all defaults

    def test_save_round_trips(self, tmp_path: Path) -> None:
        cfg = tmp_path / "settings.json"
        cfg_dir = tmp_path
        with (
            patch("archivetools.config.settings._SETTINGS_PATH", cfg),
            patch("archivetools.config.settings._CONFIG_DIR", cfg_dir),
        ):
            s = AppSettings(smart_extraction=False, active_tab=2)
            s.save()
            loaded = AppSettings.load()
        assert loaded.smart_extraction is False
        assert loaded.active_tab == 2

    def test_get_settings_singleton(self, tmp_path: Path) -> None:
        _reset_for_tests()
        cfg = tmp_path / "settings.json"
        cfg_dir = tmp_path
        with (
            patch("archivetools.config.settings._SETTINGS_PATH", cfg),
            patch("archivetools.config.settings._CONFIG_DIR", cfg_dir),
        ):
            a = get_settings()
            b = get_settings()
        assert a is b
        _reset_for_tests()

    def test_save_handles_missing_dir(self, tmp_path: Path) -> None:
        cfg = tmp_path / "sub" / "settings.json"
        cfg_dir = tmp_path / "sub"
        with (
            patch("archivetools.config.settings._SETTINGS_PATH", cfg),
            patch("archivetools.config.settings._CONFIG_DIR", cfg_dir),
        ):
            AppSettings().save()
        assert cfg.exists()


# ── PasswordStore (mocked keyring) ───────────────────────────────────────────


class TestPasswordStore:
    """Tests using a mocked keyring to avoid OS-level side effects."""

    @pytest.fixture()
    def store(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        from archivetools.config.passwords import (
            PasswordStore,
            _reset_for_tests,
        )

        _reset_for_tests()
        monkeypatch.setattr(
            "archivetools.config.passwords._PASSWORDS_PATH",
            tmp_path / "passwords.json",
        )
        monkeypatch.setattr("archivetools.config.passwords._CONFIG_DIR", tmp_path)

        # Mock keyring
        _vault: dict[str, str] = {}

        def mock_set(service, user, pwd):
            _vault[user] = pwd

        def mock_get(service, user):
            return _vault.get(user)

        def mock_del(service, user):
            _vault.pop(user, None)

        with (
            patch("keyring.set_password", mock_set),
            patch("keyring.get_password", mock_get),
            patch("keyring.delete_password", mock_del),
        ):
            s = PasswordStore()
            s._keyring_ok = True  # force keyring path
            yield s

        _reset_for_tests()

    def test_add_and_retrieve(self, store) -> None:
        entry = store.add("Work", "secret123")
        assert entry.label == "Work"
        assert store.get_password(entry.id) == "secret123"

    def test_list_entries(self, store) -> None:
        store.add("A", "pw1")
        store.add("B", "pw2")
        labels = [e.label for e in store.entries()]
        assert labels == ["A", "B"]

    def test_update_password(self, store) -> None:
        entry = store.add("MyLabel", "old")
        store.update(entry.id, password="new")
        assert store.get_password(entry.id) == "new"

    def test_update_label(self, store) -> None:
        entry = store.add("OldLabel", "pw")
        store.update(entry.id, label="NewLabel")
        assert store.entries()[0].label == "NewLabel"

    def test_delete_entry(self, store) -> None:
        entry = store.add("ToDelete", "pw")
        store.delete(entry.id)
        assert store.entries() == []

    def test_delete_nonexistent_id_noop(self, store) -> None:
        store.add("Keep", "pw")
        store.delete("nonexistent-uuid")
        assert len(store.entries()) == 1

    def test_update_nonexistent_raises(self, store) -> None:
        with pytest.raises(KeyError):
            store.update("bad-id", label="X")

    def test_observer_called_on_add(self, store) -> None:
        called = []
        store.on_change(lambda: called.append(1))
        store.add("X", "pw")
        assert called == [1]

    def test_observer_called_on_delete(self, store) -> None:
        entry = store.add("X", "pw")
        called = []
        store.on_change(lambda: called.append(1))
        store.delete(entry.id)
        assert called == [1]

    def test_hint_stored_in_metadata(self, tmp_path: Path, store) -> None:
        entry = store.add("Label", "pw", hint="work files")
        assert entry.hint == "work files"
        reloaded_entries = [e for e in store.entries() if e.id == entry.id]
        assert reloaded_entries[0].hint == "work files"

    def test_persistence_round_trip(self, tmp_path: Path, store) -> None:
        from archivetools.config.passwords import PasswordStore

        _vault: dict[str, str] = {}

        def mock_get(service, user):
            return _vault.get(user)

        store.add("A", "pw-a", hint="hint-a")

        with patch("keyring.get_password", mock_get):
            store2 = PasswordStore()
            store2._keyring_ok = True
        labels = [e.label for e in store2.entries()]
        assert "A" in labels
