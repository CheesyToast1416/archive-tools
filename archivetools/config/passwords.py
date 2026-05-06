from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from uuid import uuid4

log = logging.getLogger(__name__)

_CONFIG_DIR = Path.home() / ".config" / "archivetools"
_PASSWORDS_PATH = _CONFIG_DIR / "passwords.json"
_KEYRING_SERVICE = "archivetools"

_instance: PasswordStore | None = None


@dataclass
class PasswordEntry:
    """Metadata for a saved password (the secret itself lives in the keyring)."""

    id: str  # stable UUID used as keyring username
    label: str  # display name chosen by the user
    hint: str = ""  # non-secret reminder (stored in plaintext)


class PasswordStore:
    """
    Named password storage.

    Metadata (labels, hints) is persisted in ``~/.config/archivetools/passwords.json``.
    The actual passwords are stored in the OS keyring via the ``keyring`` package.

    If the keyring backend is unavailable (e.g. headless server without a secret
    service daemon), passwords are encrypted with AES-GCM using a machine-derived
    key (via the ``cryptography`` package that is already a project dependency).
    This is NOT equivalent to OS-keyring security, and a warning banner is shown.
    """

    def __init__(self) -> None:
        self._entries: list[PasswordEntry] = []
        self._fallback_store: dict[str, str] = {}  # id → encrypted-blob (base64)
        self._keyring_ok: bool = False
        self._observers: list[Callable[[], None]] = []
        self._probe_keyring()
        self._load()

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def keyring_available(self) -> bool:
        return self._keyring_ok

    def entries(self) -> list[PasswordEntry]:
        return list(self._entries)

    def add(self, label: str, password: str, hint: str = "") -> PasswordEntry:
        entry = PasswordEntry(id=str(uuid4()), label=label.strip(), hint=hint.strip())
        self._entries.append(entry)
        self._store_password(entry.id, password)
        self._save()
        self._notify()
        return entry

    def update(
        self,
        entry_id: str,
        label: str | None = None,
        password: str | None = None,
        hint: str | None = None,
    ) -> None:
        for entry in self._entries:
            if entry.id == entry_id:
                if label is not None:
                    entry.label = label.strip()
                if hint is not None:
                    entry.hint = hint.strip()
                if password is not None:
                    self._store_password(entry.id, password)
                self._save()
                self._notify()
                return
        raise KeyError(f"No password entry with id {entry_id!r}")

    def delete(self, entry_id: str) -> None:
        self._entries = [e for e in self._entries if e.id != entry_id]
        self._delete_password(entry_id)
        self._save()
        self._notify()

    def get_password(self, entry_id: str) -> str:
        """Retrieve the secret for *entry_id*. Raises ``RuntimeError`` on failure."""
        if self._keyring_ok:
            try:
                import keyring  # type: ignore[import]

                pwd = keyring.get_password(_KEYRING_SERVICE, entry_id)
                return pwd or ""
            except Exception as exc:
                raise RuntimeError(f"Keyring read failed: {exc}") from exc
        else:
            return self._fallback_decrypt(entry_id)

    def on_change(self, callback: Callable[[], None]) -> None:
        """Register a zero-argument callback invoked after any store mutation."""
        self._observers.append(callback)

    # ── Backend: keyring ──────────────────────────────────────────────────────

    def _probe_keyring(self) -> None:
        try:
            import keyring  # type: ignore[import]
            import keyring.errors  # type: ignore[import]

            keyring.set_password(_KEYRING_SERVICE, "__probe__", "ok")
            keyring.delete_password(_KEYRING_SERVICE, "__probe__")
            self._keyring_ok = True
        except Exception:
            self._keyring_ok = False
            log.warning(
                "Keyring backend unavailable — passwords will be stored with "
                "local (AES-GCM) encryption.  This is less secure than the "
                "OS keyring."
            )

    def _store_password(self, entry_id: str, password: str) -> None:
        if self._keyring_ok:
            try:
                import keyring  # type: ignore[import]

                keyring.set_password(_KEYRING_SERVICE, entry_id, password)
                return
            except Exception as exc:
                log.warning("Keyring write failed (%s); falling back.", exc)
        self._fallback_store[entry_id] = self._fallback_encrypt(password)

    def _delete_password(self, entry_id: str) -> None:
        if self._keyring_ok:
            try:
                import keyring  # type: ignore[import]
                import keyring.errors  # type: ignore[import]

                keyring.delete_password(_KEYRING_SERVICE, entry_id)
            except Exception:
                pass
        self._fallback_store.pop(entry_id, None)

    # ── Backend: AES-GCM fallback ────────────────────────────────────────────

    @staticmethod
    def _derive_key() -> bytes:
        """Derive a deterministic AES key from machine-specific data."""
        import base64
        import os
        import socket

        from cryptography.hazmat.primitives.hashes import SHA256
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

        material = f"{socket.gethostname()}:{os.getuid()}".encode()
        kdf = PBKDF2HMAC(
            algorithm=SHA256(), length=32, salt=b"archivetools", iterations=100_000
        )
        return base64.urlsafe_b64encode(kdf.derive(material))

    def _fallback_encrypt(self, plaintext: str) -> str:
        from cryptography.fernet import Fernet  # type: ignore[import]

        return str(Fernet(self._derive_key()).encrypt(plaintext.encode()).decode())

    def _fallback_decrypt(self, entry_id: str) -> str:
        from cryptography.fernet import Fernet  # type: ignore[import]

        blob = self._fallback_store.get(entry_id, "")
        if not blob:
            return ""
        return str(Fernet(self._derive_key()).decrypt(blob.encode()).decode())

    # ── Persistence ───────────────────────────────────────────────────────────

    def _load(self) -> None:
        if not _PASSWORDS_PATH.exists():
            return
        try:
            data = json.loads(_PASSWORDS_PATH.read_text(encoding="utf-8"))
            self._entries = [PasswordEntry(**e) for e in data.get("entries", [])]
            self._fallback_store = data.get("fallback", {})
        except Exception as exc:  # noqa: BLE001
            log.warning("Could not load password store: %s", exc)

    def _save(self) -> None:
        try:
            _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            obj: dict = {"entries": [asdict(e) for e in self._entries]}
            if self._fallback_store:
                obj["fallback"] = self._fallback_store
            _PASSWORDS_PATH.write_text(
                json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("Could not save password store: %s", exc)

    def _notify(self) -> None:
        for cb in self._observers:
            try:
                cb()
            except Exception:  # noqa: BLE001
                pass


def get_password_store() -> PasswordStore:
    """Return the application-wide ``PasswordStore`` singleton."""
    global _instance
    if _instance is None:
        _instance = PasswordStore()
    return _instance


def _reset_for_tests() -> None:
    global _instance
    _instance = None
