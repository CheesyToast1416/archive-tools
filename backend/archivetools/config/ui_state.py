from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

log = logging.getLogger(__name__)

_CONFIG_DIR = Path.home() / ".config" / "archivetools"
_UI_STATE_PATH = _CONFIG_DIR / "ui_state.json"
_LEGACY_SETTINGS_PATH = _CONFIG_DIR / "settings.json"

_UI_FIELDS = {
    "theme",
    "active_nav",
    "window_geometry",
    "recent_archives",
    "last_archive_dir",
}

_instance: UIState | None = None


@dataclass
class UIState:
    """GUI-only persistent state (theme, navigation, window layout, recent files)."""

    theme: str = "system"  # "system" | "light" | "dark"
    active_nav: int = 1  # sidebar index (0=Recent, 1=Extract, …)
    window_geometry: str = ""  # base64-encoded QByteArray from saveGeometry()
    recent_archives: list = field(default_factory=list)  # list[str], max 15
    last_archive_dir: str = ""

    @classmethod
    def load(cls) -> UIState:
        # Try the dedicated ui_state.json first.
        if _UI_STATE_PATH.exists():
            try:
                raw = json.loads(_UI_STATE_PATH.read_text(encoding="utf-8"))
                known = {f.name for f in fields(cls)}
                return cls(**{k: v for k, v in raw.items() if k in known})
            except Exception as exc:  # noqa: BLE001
                log.warning("Could not load ui_state (%s); using defaults.", exc)
            return cls()

        # Migrate from legacy settings.json if it exists.
        if _LEGACY_SETTINGS_PATH.exists():
            try:
                raw = json.loads(_LEGACY_SETTINGS_PATH.read_text(encoding="utf-8"))
                known = {f.name for f in fields(cls)}
                state = cls(**{k: v for k, v in raw.items() if k in known})
                state.save()  # write the new file so future loads skip migration
                return state
            except Exception as exc:  # noqa: BLE001
                log.warning(
                    "Could not migrate legacy settings (%s); using defaults.", exc
                )

        return cls()

    def save(self) -> None:
        try:
            _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            _UI_STATE_PATH.write_text(
                json.dumps(asdict(self), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("Could not save ui_state: %s", exc)


def get_ui_state() -> UIState:
    """Return the application-wide ``UIState`` singleton."""
    global _instance
    if _instance is None:
        _instance = UIState.load()
    return _instance


def _reset_for_tests() -> None:
    """Reset the singleton so tests can inject fresh instances."""
    global _instance
    _instance = None
