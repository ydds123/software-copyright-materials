#!/usr/bin/env python3
"""Safe file overwrite — IDE local history is the version recovery mechanism.

This script only guards against the one irrecoverable error: writing empty content
over an existing file. JetBrains IDE Local History (File → Local History → Show History)
captures every save automatically — no manual .bak files needed.

Usage:
    python3 safe_write.py --target <file> --incoming <tmpfile>
        → writes tmpfile into target, rejecting empty content
        → exits 0 on success, 1 on failure

Recovery if something goes wrong:
    IDE: File → Local History → Show History → revert to any prior version
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


def _fmt_size(size: int) -> str:
    if size < 1024:
        return f"{size}B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f}KB"
    return f"{size / (1024 * 1024):.1f}MB"


def safe_write(target: Path, incoming: Path) -> bool:
    """Write incoming into target. Only guard: refuse empty content."""
    if not incoming.exists():
        print(f"ERROR: incoming file does not exist: {incoming}", file=sys.stderr)
        return False

    incoming_size = incoming.stat().st_size
    if incoming_size == 0:
        print("ERROR: incoming file is empty — refusing to overwrite target", file=sys.stderr)
        return False

    if target.exists():
        old_size = target.stat().st_size
    else:
        old_size = 0

    # Atomic: write to temp, then os.replace (atomic on same filesystem)
    tmp = target.with_suffix(target.suffix + ".swp")
    try:
        shutil.copy2(incoming, tmp)
        if tmp.stat().st_size != incoming_size:
            tmp.unlink(missing_ok=True)
            print("ERROR: temp write size mismatch", file=sys.stderr)
            return False
        tmp.replace(target)
    finally:
        tmp.unlink(missing_ok=True)

    print(f"OK: {target} {_fmt_size(old_size)} → {_fmt_size(incoming_size)} (IDE Local History has prior version)")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Safe file overwrite (IDE local history = recovery)")
    parser.add_argument("--target", required=True, type=Path, help="Target file to overwrite")
    parser.add_argument("--incoming", required=True, type=Path, help="Temp file with new content")
    args = parser.parse_args()

    ok = safe_write(args.target, args.incoming)
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
