from __future__ import annotations

ARCHIVE_FILTER = (
    "Archives (*.zip *.rar *.7z *.z01 *.r00 *.001 *.tar *.tar.gz *.tgz "
    "*.tar.bz2 *.tar.xz);;"
    "All files (*)"
)

# Authoritative format list for archive creation and conversion.
# Columns: (display_label, format_key, file_extension, supports_password)
ARCHIVE_FORMATS: list[tuple[str, str, str, bool]] = [
    ("ZIP (no password)", "zip", ".zip", False),
    ("ZIP (AES-256 encrypted)", "zip-aes", ".zip", True),
    ("7z", "7z", ".7z", True),
    ("TAR (.tar)", "tar", ".tar", False),
    ("TAR.GZ (.tar.gz)", "tar.gz", ".tar.gz", False),
    ("TAR.BZ2 (.tar.bz2)", "tar.bz2", ".tar.bz2", False),
    ("TAR.XZ (.tar.xz)", "tar.xz", ".tar.xz", False),
]
