#!/usr/bin/env python3
"""
Generate a pinned Flathub manifest from the upstream QA manifest.
تولید مانیفست Pinشده Flathub از مانیفست کنترل کیفیت بالادستی.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

APP_ID = "io.github.Mahdi_Arts.eOVPN_Pro"
SOURCE_BLOCK = """      # Upstream CI builds the current checkout. The Flathub submission
      # replaces this with the signed release archive and SHA-256.
      # CI بالادستی Checkout فعلی را می‌سازد؛ Flathub آن را با آرشیو
      # امضاشده جایگزین می‌کند.
      - type: dir
        path: ../../
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True, help="Release version without the v prefix")
    parser.add_argument("--sha256", required=True, help="SHA-256 of the release source archive")
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", args.version):
        raise SystemExit("--version must use semantic X.Y.Z form")
    if not re.fullmatch(r"[0-9a-f]{64}", args.sha256.lower()):
        raise SystemExit("--sha256 must contain 64 hexadecimal characters")

    source = Path(__file__).with_name(f"{APP_ID}.yml")
    content = source.read_text(encoding="utf-8")
    archive_url = (
        "https://github.com/Mahdi-Arts/eOVPN-Pro/releases/download/"
        f"v{args.version}/eovpn-pro-{args.version}.tar.xz"
    )
    archive_block = f"""      - type: archive
        url: >-
          {archive_url}
        sha256: {args.sha256.lower()}
"""
    if SOURCE_BLOCK not in content:
        raise SystemExit("upstream manifest source block was not found")
    generated = content.replace(SOURCE_BLOCK, archive_block, 1)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(generated, encoding="utf-8")
    print(f"Wrote pinned Flathub manifest: {args.output}")


if __name__ == "__main__":
    main()
