# ArchiveTools

An encoding-aware archive manager for ZIP, RAR, 7z, and TAR — built for archives with CJK filenames, encrypted contents,
and multi-volume sets.

## Features

- **Encoding-aware extraction** — auto-detects CJK filename encodings (GBK, GB18030, Shift-JIS, EUC-KR, CP437); manual
  override per-operation
- **Encrypted archives** — AES-256 ZIP, RAR5 header-encrypted (`-hp`), 7z with password
- **Multi-volume sets** — automatically detects and joins split archives
- **Batch extraction** — extract many archives at once with shared or per-archive passwords
- **Format conversion** — convert between ZIP, 7z, and TAR family without extracting to disk
- **Archive creation** — create ZIP (plain or AES-256), 7z, TAR / TAR.GZ / TAR.BZ2 / TAR.XZ
- **In-app preview** — browse archive contents with image, text, PDF, audio, and video preview
- **Auto-updater** — notifies you when a new version is available and installs it in one click

## Platform support

| Platform            | Installer        |
|---------------------|------------------|
| Linux x86_64        | AppImage, `.deb` |
| macOS Apple Silicon | `.dmg`           |
| Windows x86_64      | `.exe` (NSIS)    |

## Installation

Download the latest installer for your platform from
the [Releases](https://github.com/cheesytoast1416/ArchiveTools/releases) page.

## Building from source

**Prerequisites:** Rust (stable), Python 3.12+, Node.js 22+, pnpm 10

```bash
# 1. Install Python backend (no PySide6 needed)
pip install -e ".[server]"

# 2. Install frontend dependencies
cd frontend && pnpm install

# 3. Run in development mode
pnpm tauri dev
```

Production release builds (PyInstaller sidecar + signed Tauri bundles) run via GitHub Actions — see [
`.github/workflows/release.yml`](.github/workflows/release.yml).

## License

GPLv3 — see [LICENSE.txt](LICENSE.txt).
