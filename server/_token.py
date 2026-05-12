"""Single source of truth for the per-process secret token."""

from __future__ import annotations

import secrets

TOKEN: str = secrets.token_hex(32)
