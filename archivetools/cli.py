from __future__ import annotations

import argparse
import getpass
import logging
import sys

from archivetools.operations import extract_cjk, list_cjk

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")


def main() -> None:
    # ── Interactive Mode (no arguments) ──────────────────────────────────────
    if len(sys.argv) == 1:
        print("CJK Archive Password Fixer")
        print("Supports: .zip  .rar  .7z  .tar.*")
        print("=" * 44)
        archive = input("Archive path: ").strip()
        password = getpass.getpass("Password (Unicode): ")
        output = input("Output directory (blank = default): ").strip() or None
        filename_encoding = (
            input("Filename encoding (e.g. gbk, big5) [blank = auto]: ").strip() or None
        )

        args = argparse.Namespace(
            archive=archive,
            password=password,
            output=output,
            filename_encoding=filename_encoding,
            yes=False,
        )

    # ── Command-Line Mode ─────────────────────────────────────────────────────
    else:
        parser = argparse.ArgumentParser(
            description="Extract CJK encoded password-protected archives."
        )
        parser.add_argument("archive", help="Path to the archive")
        parser.add_argument("password", help="The archive password in plain Unicode")
        parser.add_argument(
            "output", nargs="?", help="Extraction destination directory"
        )
        parser.add_argument(
            "-e",
            "--filename-encoding",
            help="Apply encoding to gibberish filenames (e.g., gbk, big5)",
        )
        parser.add_argument(
            "-y",
            "--yes",
            action="store_true",
            help="Skip preview prompt and extract immediately",
        )
        args = parser.parse_args()

    # ── Core Execution Flow ───────────────────────────────────────────────────
    try:
        ok, enc, names = list_cjk(args.archive, args.password, args.filename_encoding)
    except TypeError as exc:
        print(f"\nError: {exc}\n")
        sys.exit(1)

    if not ok:
        print("\n✗ Failed to list archive contents. Please check the password.")
        sys.exit(1)

    print(f"\nArchive contents (Password valid! Encoding: {enc}):")
    for n in names:
        print(f"  {n}")
    print()

    if not args.yes:
        proceed = input("Proceed with extraction? [Y/n]: ").strip().lower()
        if proceed not in ("", "y", "yes"):
            print("Aborted.")
            sys.exit(0)

    success, enc = extract_cjk(
        args.archive,
        args.password,
        args.output,
        filename_encoding=args.filename_encoding,
    )

    if success:
        print("\n✓ Extracted successfully.")
        sys.exit(0)
    else:
        print("\n✗ Extraction failed during the final unpack stage.")
        sys.exit(1)
