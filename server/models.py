from __future__ import annotations

from pydantic import BaseModel

# ── Archive operations ────────────────────────────────────────────────────────


class ListRequest(BaseModel):
    archive_path: str
    password: str = ""
    filename_encoding: str | None = None
    password_encoding: str | None = None


class ListResponse(BaseModel):
    ok: bool
    encoding: str | None
    names: list[str]


class ExtractRequest(BaseModel):
    archive_path: str
    password: str = ""
    output_dir: str | None = None
    filename_encoding: str | None = None
    password_encoding: str | None = None
    names: list[str] | None = None
    smart: bool = True


class InfoResponse(BaseModel):
    format_name: str
    file_count: int
    compressed_size: int
    uncompressed_size: int
    is_encrypted: bool
    comment: str


class DetectEncodingResponse(BaseModel):
    encoding: str | None
    confidence: float


class TestRequest(BaseModel):
    archive_path: str
    password: str = ""
    filename_encoding: str | None = None
    password_encoding: str | None = None


class TestResponse(BaseModel):
    ok: bool
    failed: list[str]


class CreateRequest(BaseModel):
    output_path: str
    files: list[str]
    format: str = "zip"
    password: str | None = None
    compression_level: int = 6
    filename_encoding: str | None = None


class ConvertRequest(BaseModel):
    input_path: str
    output_path: str
    output_format: str
    password: str | None = None
    output_password: str | None = None
    filename_encoding: str | None = None
    password_encoding: str | None = None


class UpdateRequest(BaseModel):
    archive_path: str
    files_to_add: list[str] = []
    paths_to_remove: list[str] = []


class BatchRequest(BaseModel):
    archives: list[str]
    output_dir: str | None = None
    password: str = ""
    filename_encoding: str | None = None
    password_encoding: str | None = None


# ── Preview ───────────────────────────────────────────────────────────────────


class PreviewRequest(BaseModel):
    archive_path: str
    entry_name: str
    password: str = ""
    filename_encoding: str | None = None
    password_encoding: str | None = None


class PreviewResponse(BaseModel):
    temp_id: str
    file_path: str


# ── Passwords ─────────────────────────────────────────────────────────────────


class PasswordEntryModel(BaseModel):
    id: str
    label: str
    hint: str


class AddPasswordRequest(BaseModel):
    label: str
    password: str
    hint: str = ""


class UpdatePasswordRequest(BaseModel):
    label: str | None = None
    password: str | None = None
    hint: str | None = None


# ── Settings ──────────────────────────────────────────────────────────────────


class AppSettingsModel(BaseModel):
    smart_extraction: bool
    trash_after_extract: bool
    default_output_dir: str
    trash_after_create: bool
    trash_after_batch: bool
    default_password_encoding: str
    default_filename_encoding: str
    notifications_enabled: bool


class UIStateModel(BaseModel):
    theme: str  # "system" | "light" | "dark"
    active_nav: int
    recent_archives: list[str]
    last_archive_dir: str
    # window_geometry omitted — Tauri owns window state
