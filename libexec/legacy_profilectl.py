#!/usr/bin/env python3
"""Remove only Xiapin 1.x entries from an Fcitx profile."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import sys
import tempfile

SECTION_RE = re.compile(r"^\[([^]]+)]\s*$")
ITEM_RE = re.compile(r"^Groups/0/Items/(\d+)$")


def remove_input_method(text: str, name: str) -> str:
    lines = text.splitlines()
    sections: list[tuple[str, int, int]] = []
    current_name = ""
    current_start = 0
    for index, line in enumerate(lines):
        match = SECTION_RE.match(line)
        if match:
            if current_name:
                sections.append((current_name, current_start, index))
            current_name = match.group(1)
            current_start = index
    if current_name:
        sections.append((current_name, current_start, len(lines)))

    remove_ranges = []
    for section, start, end in sections:
        if ITEM_RE.match(section) and any(
            line == f"Name={name}" for line in lines[start + 1 : end]
        ):
            remove_ranges.append((start, end))
    for start, end in reversed(remove_ranges):
        del lines[start:end]
        while start < len(lines) and start > 0 and not lines[start] and not lines[start - 1]:
            del lines[start]
    for index, line in enumerate(lines):
        if line == f"DefaultIM={name}":
            lines[index] = "DefaultIM=keyboard-us"
    return "\n".join(lines).rstrip() + "\n"


def atomic_write(path: Path, text: str) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("remove",))
    parser.add_argument("profile", type=Path)
    parser.add_argument("--name", choices=("xiapin", "stable-pinyin"), required=True)
    args = parser.parse_args()
    try:
        text = args.profile.read_text(encoding="utf-8")
        atomic_write(args.profile, remove_input_method(text, args.name))
    except (OSError, UnicodeError) as error:
        print(f"legacy-profilectl: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
