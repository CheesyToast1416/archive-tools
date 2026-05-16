"""Tests for archivetools.config: settings, ui_state, passwords."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from archivetools.config.settings import AppSettings, _reset_for_tests, get_settings
from archivetools.config.ui_state import UIState, get_ui_state
from archivetools.config.ui_state import _reset_for_tests as _reset_ui_state

# ── AppSettings ───────────────────────────────────────────────────────────────


class TestAppSettings:
    def test_defaults_match_spec(self) -> None:
        s = AppSettings()
        assert s.smart_extraction is True
        assert s.trash_after_extract is False
        assert s.trash_after_create is False
        assert s.trash_after_batch is False
        assert s.default_output_dir == ""
        assert s.default_password_encoding == ""
        assert s.default_filename_encoding == ""
        assert s.notifications_enabled is True

    def test_does_not_have_ui_fields(self) -> None:
        s = AppSettings()
        assert not hasattr(s, "active_nav")
        assert not hasattr(s, "recent_archives")
        assert not hasattr(s, "theme")

    def test_load_overrides_defaults(self, tmp_path: Path) -> None:
        cfg = tmp_path / "settings.json"
        cfg.write_text(json.dumps({"smart_extraction": False}), encoding="utf-8")
        with patch("archivetools.config.settings._SETTINGS_PATH", cfg):
            s = AppSettings.load()
        assert s.smart_extraction is False
        assert s.trash_after_extract is False  # default preserved

    def test_load_ignores_unknown_keys(self, tmp_path: Path) -> None:
        cfg = tmp_path / "settings.json"
        cfg.write_text(
            json.dumps({"future_key": True, "smart_extraction": False}),
            encoding="utf-8",
        )
        with patch("archivetools.config.settings._SETTINGS_PATH", cfg):
            s = AppSettings.load()
        assert s.smart_extraction is False
        assert not hasattr(s, "future_key")

    def test_load_corrupt_file_returns_defaults(self, tmp_path: Path) -> None:
        cfg = tmp_path / "settings.json"
        cfg.write_bytes(b"not valid json {{")
        with patch("archivetools.config.settings._SETTINGS_PATH", cfg):
            s = AppSettings.load()
        assert s == AppSettings()

    def test_load_missing_file_returns_defaults(self, tmp_path: Path) -> None:
        with patch(
            "archivetools.config.settings._SETTINGS_PATH", tmp_path / "missing.json"
        ):
            s = AppSettings.load()
        assert s == AppSettings()

    def test_save_round_trips(self, tmp_path: Path) -> None:
        cfg = tmp_path / "settings.json"
        with (
            patch("archivetools.config.settings._SETTINGS_PATH", cfg),
            patch("archivetools.config.settings._CONFIG_DIR", tmp_path),
        ):
            AppSettings(smart_extraction=False).save()
            loaded = AppSettings.load()
        assert loaded.smart_extraction is False

    def test_save_creates_missing_directory(self, tmp_path: Path) -> None:
        cfg = tmp_path / "sub" / "settings.json"
        cfg_dir = tmp_path / "sub"
        with (
            patch("archivetools.config.settings._SETTINGS_PATH", cfg),
            patch("archivetools.config.settings._CONFIG_DIR", cfg_dir),
        ):
            AppSettings().save()
        assert cfg.exists()

    def test_get_settings_returns_singleton(self, tmp_path: Path) -> None:
        _reset_for_tests()
        with (
            patch("archivetools.config.settings._SETTINGS_PATH", tmp_path / "s.json"),
            patch("archivetools.config.settings._CONFIG_DIR", tmp_path),
        ):
            a = get_settings()
            b = get_settings()
        assert a is b
        _reset_for_tests()


# ── UIState ───────────────────────────────────────────────────────────────────


class TestUIState:
    def test_defaults(self) -> None:
        s = UIState()
        assert s.active_nav == 1
        assert s.recent_archives == []
        assert s.theme == "system"
        assert s.last_archive_dir == ""

    def test_load_overrides_selected_fields(self, tmp_path: Path) -> None:
        cfg = tmp_path / "ui_state.json"
        cfg.write_text(json.dumps({"active_nav": 3, "theme": "dark"}), encoding="utf-8")
        with patch("archivetools.config.ui_state._UI_STATE_PATH", cfg):
            s = UIState.load()
        assert s.active_nav == 3
        assert s.theme == "dark"

    def test_load_ignores_unknown_keys(self, tmp_path: Path) -> None:
        cfg = tmp_path / "ui_state.json"
        cfg.write_text(
            json.dumps({"future_key": True, "active_nav": 2}), encoding="utf-8"
        )
        with patch("archivetools.config.ui_state._UI_STATE_PATH", cfg):
            s = UIState.load()
        assert s.active_nav == 2
        assert not hasattr(s, "future_key")

    def test_load_corrupt_file_returns_defaults(self, tmp_path: Path) -> None:
        cfg = tmp_path / "ui_state.json"
        cfg.write_bytes(b"not valid json {{")
        with patch("archivetools.config.ui_state._UI_STATE_PATH", cfg):
            s = UIState.load()
        assert s == UIState()

    def test_save_round_trips(self, tmp_path: Path) -> None:
        cfg = tmp_path / "ui_state.json"
        with (
            patch("archivetools.config.ui_state._UI_STATE_PATH", cfg),
            patch("archivetools.config.ui_state._CONFIG_DIR", tmp_path),
        ):
            UIState(active_nav=2).save()
            loaded = UIState.load()
        assert loaded.active_nav == 2

    def test_recent_archives_round_trips(self, tmp_path: Path) -> None:
        cfg = tmp_path / "ui_state.json"
        paths = ["/home/user/a.zip", "/home/user/b.rar"]
        with (
            patch("archivetools.config.ui_state._UI_STATE_PATH", cfg),
            patch("archivetools.config.ui_state._CONFIG_DIR", tmp_path),
        ):
            UIState(recent_archives=paths).save()
            loaded = UIState.load()
        assert loaded.recent_archives == paths

    def test_get_ui_state_returns_singleton(self, tmp_path: Path) -> None:
        _reset_ui_state()
        with (
            patch("archivetools.config.ui_state._UI_STATE_PATH", tmp_path / "ui.json"),
            patch("archivetools.config.ui_state._CONFIG_DIR", tmp_path),
        ):
            a = get_ui_state()
            b = get_ui_state()
        assert a is b
        _reset_ui_state()

    def test_migration_from_legacy_settings_file(self, tmp_path: Path) -> None:
        legacy = tmp_path / "settings.json"
        legacy.write_text(
            json.dumps({"smart_extraction": False, "active_nav": 4, "theme": "dark"}),
            encoding="utf-8",
        )
        ui_cfg = tmp_path / "ui_state.json"
        with (
            patch("archivetools.config.ui_state._UI_STATE_PATH", ui_cfg),
            patch("archivetools.config.ui_state._LEGACY_SETTINGS_PATH", legacy),
            patch("archivetools.config.ui_state._CONFIG_DIR", tmp_path),
        ):
            s = UIState.load()
        assert s.active_nav == 4
        assert s.theme == "dark"
        assert ui_cfg.exists()


# ── PasswordStore ─────────────────────────────────────────────────────────────


class TestPasswordStore:
    @pytest.fixture()
    def store(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        from archivetools.config.passwords import PasswordStore, _reset_for_tests

        _reset_for_tests()
        monkeypatch.setattr(
            "archivetools.config.passwords._PASSWORDS_PATH", tmp_path / "passwords.json"
        )
        monkeypatch.setattr("archivetools.config.passwords._CONFIG_DIR", tmp_path)

        _vault: dict[str, str] = {}
        with (
            patch(
                "keyring.set_password",
                lambda _svc, user, pwd: _vault.__setitem__(user, pwd),
            ),
            patch("keyring.get_password", lambda _svc, user: _vault.get(user)),
            patch("keyring.delete_password", lambda _svc, user: _vault.pop(user, None)),
        ):
            s = PasswordStore()
            s._keyring_ok = True
            yield s

        _reset_for_tests()

    def test_add_and_retrieve_password(self, store) -> None:
        entry = store.add("Work", "secret123")
        assert entry.label == "Work"
        assert store.get_password(entry.id) == "secret123"

    def test_list_entries_in_insertion_order(self, store) -> None:
        store.add("A", "pw1")
        store.add("B", "pw2")
        assert [e.label for e in store.entries()] == ["A", "B"]

    def test_update_password(self, store) -> None:
        entry = store.add("Label", "old")
        store.update(entry.id, password="new")
        assert store.get_password(entry.id) == "new"

    def test_update_label(self, store) -> None:
        entry = store.add("OldLabel", "pw")
        store.update(entry.id, label="NewLabel")
        assert store.entries()[0].label == "NewLabel"

    def test_delete_removes_entry(self, store) -> None:
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

    def test_hint_stored_in_metadata(self, store) -> None:
        entry = store.add("Label", "pw", hint="work files")
        assert entry.hint == "work files"
        assert store.entries()[0].hint == "work files"

    def test_on_change_observer_called_on_add(self, store) -> None:
        called: list[int] = []
        store.on_change(lambda: called.append(1))
        store.add("X", "pw")
        assert called == [1]

    def test_on_change_observer_called_on_delete(self, store) -> None:
        entry = store.add("X", "pw")
        called: list[int] = []
        store.on_change(lambda: called.append(1))
        store.delete(entry.id)
        assert called == [1]

    def test_metadata_persists_to_new_store_instance(
        self, tmp_path: Path, store
    ) -> None:
        from archivetools.config.passwords import PasswordStore

        _vault: dict[str, str] = {}
        store.add("A", "pw-a", hint="hint-a")
        with patch("keyring.get_password", lambda _svc, user: _vault.get(user)):
            store2 = PasswordStore()
            store2._keyring_ok = True
        assert any(e.label == "A" for e in store2.entries())
