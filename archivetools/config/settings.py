from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

log = logging.getLogger(__name__)

_CONFIG_DIR = Path.home() / ".config" / "archivetools"
_SETTINGS_PATH = _CONFIG_DIR / "settings.json"

_instance: AppSettings | None = None


@dataclass
class AppSettings:
    """Persistent application preferences, backed by a JSON file."""

    # ── Extraction ────────────────────────────────────────────────────────────
    smart_extraction: bool = True
    trash_after_extract: bool = False
    default_output_dir: str = ""

    # ── Creation ──────────────────────────────────────────────────────────────
    trash_after_create: bool = False

    # ── Batch ─────────────────────────────────────────────────────────────────
    trash_after_batch: bool = False

    # ── Encoding defaults  ("" = auto-detect) ────────────────────────────────
    default_password_encoding: str = ""
    default_filename_encoding: str = ""

    # ── Notifications ─────────────────────────────────────────────────────────
    notifications_enabled: bool = True

    # ── Appearance ────────────────────────────────────────────────────────────
    theme: str = "system"  # "system" | "light" | "dark"

    # ── UI ────────────────────────────────────────────────────────────────────
    last_archive_dir: str = ""
    active_nav: int = 1  # sidebar index (0=Recent, 1=Extract, …)
    window_geometry: str = ""  # base64-encoded QByteArray from saveGeometry()
    recent_archives: list = field(default_factory=list)  # list[str], max 15

    # ── Persistence ───────────────────────────────────────────────────────────

    @classmethod
    def load(cls) -> AppSettings:
        if _SETTINGS_PATH.exists():
            try:
                raw = json.loads(_SETTINGS_PATH.read_text(encoding="utf-8"))
                known = {f.name for f in fields(cls)}
                return cls(**{k: v for k, v in raw.items() if k in known})
            except Exception as exc:  # noqa: BLE001
                log.warning("Could not load settings (%s); using defaults.", exc)
        return cls()

    def save(self) -> None:
        try:
            _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            _SETTINGS_PATH.write_text(
                json.dumps(asdict(self), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("Could not save settings: %s", exc)


def get_settings() -> AppSettings:
    """Return the application-wide ``AppSettings`` singleton."""
    global _instance
    if _instance is None:
        _instance = AppSettings.load()
    return _instance


def _reset_for_tests() -> None:
    """Reset the singleton so tests can inject fresh instances."""
    global _instance
    _instance = None
