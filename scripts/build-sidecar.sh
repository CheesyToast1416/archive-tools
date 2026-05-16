#!/usr/bin/env bash
# Build the Python server sidecar for the current platform and copy it
# to frontend/src-tauri/binaries/ with the Tauri-required platform triple suffix.
#
# Usage: ./scripts/build-sidecar.sh
#
# Requires: pyinstaller, rustc (for 'rustc --print host-triple')

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "▶ Detecting platform triple…"
TRIPLE="$(rustc --print host-triple)"
echo "  triple = $TRIPLE"

echo "▶ Building server binary with PyInstaller…"
cd "$ROOT/backend"
pyinstaller server.spec

SRC="dist/archivetools-server"
[ "$TRIPLE" = *windows* ] && SRC="dist/archivetools-server.exe" || true

DST="${ROOT}/frontend/src-tauri/binaries/archivetools-server-${TRIPLE}"
[ "$TRIPLE" = *windows* ] && DST="${DST}.exe" || true

echo "▶ Copying to ${DST}…"
mkdir -p "${ROOT}/frontend/src-tauri/binaries"
cp "$SRC" "$DST"
chmod +x "$DST" 2>/dev/null || true

echo "✓ Sidecar ready: ${DST}"
echo ""
echo "  Next: cd frontend && pnpm tauri dev"
