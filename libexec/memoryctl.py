#!/usr/bin/env python3
"""Portable, local-only backup and restore for Xiapin learning data."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import zlib
from contextlib import contextmanager
from datetime import datetime, timezone
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile

FORMAT = "ubuntu-cn-input-memory"
FORMAT_VERSION = 2
LEGACY_FORMAT_VERSION = 1
USER_TEXT = "stable-pinyin.user.txt"
HISTORY_TEXT = "stable-pinyin.history.txt"
MANIFEST = "manifest.json"
MAX_ARCHIVE_SIZE = 64 * 1024 * 1024
MAX_MEMBER_SIZE = 32 * 1024 * 1024
ALLOWED_MEMBERS = {MANIFEST, USER_TEXT, HISTORY_TEXT}
PINYIN = re.compile(r"^[a-z]+(?:'[a-z]+)*$", re.IGNORECASE)
SYSTEM_PINYIN_DICTIONARY = Path(
    os.environ.get("UBUNTU_CN_INPUT_SYSTEM_PINYIN_DICTIONARY", "/usr/share/libime/sc.dict")
)
def history_tool() -> Path:
    override = os.environ.get("UBUNTU_CN_INPUT_HISTORY_TOOL")
    candidates = [
        Path(override) if override else None,
        Path("/usr/libexec/xiapin/xiapin-history"),
        Path(__file__).resolve().parents[1] / "build/native/xiapin-history",
    ]
    for candidate in candidates:
        if candidate and candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    raise MemoryError("Xiapin history converter is missing")

class MemoryError(RuntimeError):
    pass

def data_home() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))

def state_home() -> Path:
    return Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))

def state_dir() -> Path:
    return state_home() / "ubuntu-cn-input/memory"

@contextmanager
def memory_lock():
    root = data_home() / "xiapin"
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(root, 0o700)
    descriptor = os.open(root / ".memory.lock", os.O_CREAT | os.O_RDONLY, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)

def reload_running_engines() -> int:
    """Ask this user's installed Xiapin engine processes to reload memory."""
    expected = Path("/usr/libexec/ibus-engine-xiapin")
    count = 0
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            if entry.stat().st_uid != os.getuid():
                continue
            executable = (entry / "exe").resolve(strict=True)
            if executable != expected:
                continue
            os.kill(int(entry.name), 1)  # SIGHUP
            count += 1
        except (FileNotFoundError, PermissionError, ProcessLookupError, OSError):
            continue
    return count

def advance_generation() -> None:
    root = data_home() / "xiapin"
    generation = root / ".memory.generation"
    current = 0
    try:
        current = int(generation.read_text(encoding="ascii").strip())
    except (FileNotFoundError, OSError, UnicodeError, ValueError):
        pass
    atomic_write(generation, f"{current + 1}\n".encode())

def paths() -> dict[str, Path]:
    root = data_home() / "xiapin"
    return {USER_TEXT: root / "user.dict", HISTORY_TEXT: root / "user.history"}

def fcitx_native_paths() -> dict[str, Path]:
    root = data_home() / "fcitx5/pinyin"
    return {USER_TEXT: root / "user.dict", HISTORY_TEXT: root / "user.history"}

def legacy_table_paths() -> dict[str, Path]:
    root = data_home() / "fcitx5/table"
    return {
        USER_TEXT: root / "stable-pinyin.user.dict",
        HISTORY_TEXT: root / "stable-pinyin.history",
    }

def run(command: list[str]) -> None:
    try:
        subprocess.run(command, check=True, timeout=15, stdout=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError) as error:
        raise MemoryError(f"command failed: {command[0]}: {error}") from error

def run_capture(command: list[str]) -> bytes:
    try:
        return subprocess.run(
            command, check=True, timeout=15, stdout=subprocess.PIPE
        ).stdout
    except (OSError, subprocess.SubprocessError) as error:
        raise MemoryError(f"command failed: {command[0]}: {error}") from error

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def atomic_write(path: Path, data: bytes, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise

def convert_to_text(
    binary: Path, name: str, output: Path, *, legacy_table: bool = False
) -> None:
    if name == USER_TEXT:
        tool = "libime_tabledict" if legacy_table else "libime_pinyindict"
        args = [tool, "-du", str(binary), str(output)] if legacy_table \
            else [tool, "-d", str(binary), str(output)]
        run(args)
    else:
        atomic_write(
            output,
            run_capture([str(history_tool()), "--dump", str(binary), "-"]),
        )

def convert_to_binary(text: Path, name: str, output: Path) -> None:
    if name == USER_TEXT:
        run(["libime_pinyindict", str(text), str(output)])
    else:
        atomic_write(
            output,
            run_capture([str(history_tool()), "--compile", str(text), "-"]),
        )

def parse_fields(line: str) -> list[str]:
    fields: list[str] = []
    token: list[str] = []
    quoted = False
    escaped = False
    for character in line:
        if escaped:
            token.append({"n": "\n"}.get(character, character))
            escaped = False
        elif character == "\\":
            escaped = True
        elif character == '"':
            quoted = not quoted
        elif character.isspace() and not quoted:
            if token:
                fields.append("".join(token))
                token = []
        else:
            token.append(character)
    if escaped:
        token.append("\\")
    if quoted:
        raise MemoryError("unterminated quoted field")
    if token:
        fields.append("".join(token))
    return fields

def escape_field(value: str) -> str:
    if value and not any(c.isspace() or c in '"\\' for c in value):
        return value
    value = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{value}"'

def valid_pinyin(value: str) -> bool:
    return bool(PINYIN.fullmatch(value))

def pinyin_reference() -> tuple[dict[tuple[str, str], str], set[str]]:
    """Load canonical spellings and syllables from LibIME's system dictionary."""
    if not SYSTEM_PINYIN_DICTIONARY.is_file():
        raise MemoryError(
            f"LibIME system dictionary is missing: {SYSTEM_PINYIN_DICTIONARY}"
        )
    with tempfile.TemporaryDirectory(prefix="xiapin-pinyin-reference-") as directory:
        text = Path(directory) / "sc.txt"
        convert_to_text(SYSTEM_PINYIN_DICTIONARY, USER_TEXT, text)
        canonical: dict[tuple[str, str], str] = {}
        syllables: set[str] = set()
        for raw in text.read_text(encoding="utf-8").splitlines():
            try:
                fields = parse_fields(raw)
            except MemoryError:
                continue
            if len(fields) < 2 or not valid_pinyin(fields[1]):
                continue
            word, spelling = fields[0], fields[1].lower()
            canonical.setdefault((word, spelling.replace("'", "")), spelling)
            syllables.update(spelling.split("'"))
    if not syllables:
        raise MemoryError("LibIME system dictionary contains no pinyin syllables")
    return canonical, syllables

def han_character_count(value: str) -> int:
    return sum(
        "\u3400" <= character <= "\u9fff" or "\uf900" <= character <= "\ufaff"
        for character in value
    )

def segment_pinyin(
    compact: str,
    word: str,
    canonical: dict[tuple[str, str], str],
    syllables: set[str],
) -> str:
    """Turn a Table code such as ``nihao`` into LibIME full pinyin."""
    compact = compact.lower()
    if "'" in compact:
        if all(part in syllables for part in compact.split("'")):
            return compact
        raise MemoryError(f"invalid full pinyin for {word}: {compact}")
    known = canonical.get((word, compact))
    if known:
        return known

    candidates: list[tuple[str, ...]] = []

    def visit(offset: int, parts: tuple[str, ...]) -> None:
        if offset == len(compact):
            candidates.append(parts)
            return
        for end in range(offset + 1, len(compact) + 1):
            syllable = compact[offset:end]
            if syllable in syllables:
                visit(end, (*parts, syllable))

    visit(0, ())
    if not candidates:
        raise MemoryError(f"cannot split legacy pinyin for {word}: {compact}")
    expected = han_character_count(word)
    candidates.sort(
        key=lambda parts: (
            abs(len(parts) - expected) if expected else len(parts),
            -len(parts) if expected else len(parts),
            parts,
        )
    )
    return "'".join(candidates[0])

def normalized_user_text(data: bytes) -> bytes:
    entries: dict[tuple[str, str], str] = {}
    for raw in data.decode("utf-8").splitlines():
        try:
            fields = parse_fields(raw.strip())
        except MemoryError:
            continue
        if len(fields) < 2 or not fields[0] or not valid_pinyin(fields[1]):
            continue
        word, pinyin = fields[0], fields[1].lower()
        weight = fields[2] if len(fields) > 2 else "0"
        try:
            float(weight)
        except ValueError:
            weight = "0"
        entries.setdefault((pinyin, word), weight)
    return b"".join(
        f"{escape_field(word)} {pinyin} {weight}\n".encode()
        for (pinyin, word), weight in entries.items()
    )

def legacy_user_text(data: bytes) -> bytes:
    """Convert Table user words to native pinyin text.

    The Table's opaque ordering value is not the LibIME probability scale, so
    explicit user words are kept at neutral priority and learned automatic
    phrases at low priority. Deleted entries and malformed rows are omitted.
    """
    state = "word"
    output: list[str] = []
    seen: set[tuple[str, str]] = set()
    canonical, syllables = pinyin_reference()
    for raw in data.decode("utf-8").splitlines():
        line = raw.strip()
        if line == "[Auto]":
            state = "auto"
            continue
        if line == "[Delete]":
            state = "delete"
            continue
        if not line or state == "delete":
            continue
        try:
            fields = parse_fields(line)
        except MemoryError:
            continue
        if len(fields) < 2:
            continue
        if valid_pinyin(fields[0]):
            pinyin, word = fields[0].lower(), fields[1]
        elif valid_pinyin(fields[1]):
            word, pinyin = fields[0], fields[1].lower()
        else:
            continue
        pinyin = segment_pinyin(pinyin, word, canonical, syllables)
        key = (pinyin, word)
        if key in seen:
            continue
        output.append(f"{escape_field(word)} {pinyin} {0 if state == 'word' else 1}\n")
        seen.add(key)
    if not output:
        raise MemoryError("legacy user dictionary contains no valid full-pinyin entries")
    return "".join(output).encode()

def validate_text(name: str, data: bytes, temporary_dir: Path) -> None:
    if len(data) > MAX_MEMBER_SIZE:
        raise MemoryError(f"{name} is too large")
    if b"\0" in data:
        raise MemoryError(f"{name} contains a NUL byte")
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise MemoryError(f"{name} is not UTF-8") from error
    source = temporary_dir / name
    source.write_bytes(data)
    if name == USER_TEXT:
        compiled = temporary_dir / f"{name}.validated"
        convert_to_binary(source, name, compiled)
        output = temporary_dir / f"{name}.roundtrip"
        convert_to_text(compiled, name, output)
        actual_rows = output.read_text(encoding="utf-8").splitlines()
        expected_rows = normalized_user_text(data).decode().splitlines()
        if len(actual_rows) != len(expected_rows):
            raise MemoryError(f"LibIME did not preserve all valid rows in {name}")
        def keyed(rows: list[str]) -> dict[tuple[str, str], float]:
            result: dict[tuple[str, str], float] = {}
            for row in rows:
                fields = parse_fields(row)
                result[(fields[0], fields[1])] = float(fields[2])
            return result
        actual_entries = keyed(actual_rows)
        expected_entries = keyed(expected_rows)
        if actual_entries.keys() != expected_entries.keys():
            raise MemoryError(f"LibIME changed a word in {name}")
        for key, expected_weight in expected_entries.items():
            if actual_entries[key] != expected_weight:
                raise MemoryError(f"LibIME changed a weight in {name}")
    else:
        compiled = temporary_dir / f"{name}.validated"
        convert_to_binary(source, name, compiled)
    if not compiled.is_file():
        raise MemoryError(f"LibIME rejected {name}")

def merge_text(name: str, current: bytes | None, incoming: bytes) -> bytes:
    if not current:
        return incoming
    if name == HISTORY_TEXT:
        lines = current.splitlines() + incoming.splitlines()
        return b"\n".join(lines) + (b"\n" if lines else b"")
    if name == USER_TEXT:
        rows: dict[bytes, None] = {}
        for row in current.splitlines() + incoming.splitlines():
            if row:
                rows.setdefault(row, None)
        return b"\n".join(rows) + (b"\n" if rows else b"")
    raise MemoryError(f"unknown memory member: {name}")

def create_archive(destination: Path) -> Path:
    destination = destination.expanduser().resolve()
    with tempfile.TemporaryDirectory(prefix="xiapin-export-") as directory:
        temporary_dir = Path(directory)
        content: dict[str, bytes] = {}
        native, fcitx_native, legacy = paths(), fcitx_native_paths(), legacy_table_paths()
        if native[USER_TEXT].is_file():
            text = temporary_dir / USER_TEXT
            convert_to_text(native[USER_TEXT], USER_TEXT, text)
            content[USER_TEXT] = normalized_user_text(text.read_bytes())
        elif fcitx_native[USER_TEXT].is_file():
            text = temporary_dir / USER_TEXT
            convert_to_text(fcitx_native[USER_TEXT], USER_TEXT, text)
            content[USER_TEXT] = normalized_user_text(text.read_bytes())
        elif legacy[USER_TEXT].is_file():
            text = temporary_dir / USER_TEXT
            convert_to_text(legacy[USER_TEXT], USER_TEXT, text, legacy_table=True)
            content[USER_TEXT] = legacy_user_text(text.read_bytes())
        if native[HISTORY_TEXT].is_file():
            text = temporary_dir / HISTORY_TEXT
            convert_to_text(native[HISTORY_TEXT], HISTORY_TEXT, text)
            content[HISTORY_TEXT] = text.read_bytes()
        elif fcitx_native[HISTORY_TEXT].is_file():
            text = temporary_dir / HISTORY_TEXT
            convert_to_text(fcitx_native[HISTORY_TEXT], HISTORY_TEXT, text)
            content[HISTORY_TEXT] = text.read_bytes()
        elif legacy[HISTORY_TEXT].is_file():
            text = temporary_dir / HISTORY_TEXT
            convert_to_text(legacy[HISTORY_TEXT], HISTORY_TEXT, text)
            content[HISTORY_TEXT] = text.read_bytes()
        manifest = {
            "format": FORMAT,
            "version": FORMAT_VERSION,
            "created_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "engine": "xiapin-ibus/libime",
            "files": {
                name: {"sha256": sha256(data), "size": len(data)}
                for name, data in content.items()
            },
            "privacy": "local-only; archive contains potentially sensitive plaintext",
        }
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor, temporary = tempfile.mkstemp(
            prefix=f".{destination.name}.", dir=destination.parent
        )
        os.close(descriptor)
        try:
            with ZipFile(temporary, "w", ZIP_DEFLATED, compresslevel=9) as archive:
                archive.writestr(
                    MANIFEST,
                    json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2)
                    + "\n",
                )
                for name in sorted(content):
                    archive.writestr(name, content[name])
            os.chmod(temporary, 0o600)
            os.replace(temporary, destination)
        except BaseException:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            raise
    return destination

def read_archive(source: Path, temporary_dir: Path) -> tuple[dict, dict[str, bytes]]:
    source = source.expanduser().resolve()
    if not source.is_file() or source.stat().st_size > MAX_ARCHIVE_SIZE:
        raise MemoryError("archive is missing or too large")
    try:
        with ZipFile(source) as archive:
            infos = archive.infolist()
            names = {item.filename for item in infos}
            if len(names) != len(infos) or not names <= ALLOWED_MEMBERS:
                raise MemoryError("archive contains unexpected or duplicate members")
            if MANIFEST not in names:
                raise MemoryError("archive has no manifest")
            for item in infos:
                if stat.S_ISLNK(item.external_attr >> 16) or item.file_size > MAX_MEMBER_SIZE:
                    raise MemoryError("archive contains an unsafe member")
            manifest = json.loads(archive.read(MANIFEST))
            version = manifest.get("version")
            if manifest.get("format") != FORMAT or version not in {
                FORMAT_VERSION, LEGACY_FORMAT_VERSION
            }:
                raise MemoryError("unsupported memory archive format")
            metadata = manifest.get("files")
            if not isinstance(metadata, dict) or set(metadata) != names - {MANIFEST}:
                raise MemoryError("manifest does not match archive members")
            content: dict[str, bytes] = {}
            for name, item in metadata.items():
                data = archive.read(name)
                if item != {"sha256": sha256(data), "size": len(data)}:
                    raise MemoryError(f"checksum failed for {name}")
                if version == FORMAT_VERSION and name == USER_TEXT:
                    data = normalized_user_text(data)
                if name == USER_TEXT and version == LEGACY_FORMAT_VERSION:
                    data = legacy_user_text(data)
                validate_text(name, data, temporary_dir)
                content[name] = data
            return manifest, content
    except (BadZipFile, json.JSONDecodeError, KeyError, TypeError, zlib.error) as error:
        raise MemoryError(f"invalid archive: {error}") from error

def install_archive(source: Path, replace: bool) -> Path:
    backup = state_dir() / "backups" / (
        f"before-import-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}.ucimem"
    )
    create_archive(backup)
    with tempfile.TemporaryDirectory(prefix="xiapin-import-") as directory:
        temporary_dir = Path(directory)
        _, content = read_archive(source, temporary_dir)
        destinations = paths()
        for name, incoming in content.items():
            destination = destinations[name]
            data = incoming
            if not replace and destination.is_file():
                current_text = temporary_dir / f"current-{name}"
                convert_to_text(destination, name, current_text)
                current = current_text.read_bytes()
                if name == USER_TEXT:
                    current = normalized_user_text(current)
                data = merge_text(name, current, incoming)
            text = temporary_dir / f"install-{name}"
            text.write_bytes(data)
            binary = temporary_dir / f"install-{name}.dict"
            convert_to_binary(text, name, binary)
            atomic_write(destination, binary.read_bytes())
    return backup

def default_backup_path() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return state_dir() / "backups" / f"xiapin-{stamp}.ucimem"

def migrate_legacy() -> Path | None:
    """Copy the newest legacy LibIME memory into Xiapin's private directory."""
    destinations = paths()
    if all(path.is_file() for path in destinations.values()):
        return None
    sources = (*fcitx_native_paths().values(), *legacy_table_paths().values())
    if not any(path.is_file() for path in sources):
        return None
    state_dir().mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.TemporaryDirectory(prefix="xiapin-migrate-") as directory:
        archive = Path(directory) / "legacy.ucimem"
        create_archive(archive)
        return install_archive(archive, True)

def main() -> int:
    parser = argparse.ArgumentParser(description="Manage Xiapin's local learning memory")
    sub = parser.add_subparsers(dest="action", required=True)
    export = sub.add_parser("export", aliases=["backup"])
    export.add_argument("output", nargs="?", type=Path)
    verify = sub.add_parser("verify")
    verify.add_argument("archive", type=Path)
    restore = sub.add_parser("import", aliases=["restore"])
    restore.add_argument("archive", type=Path)
    restore.add_argument("--replace", action="store_true")
    sub.add_parser("migrate")
    sub.add_parser("status")
    args = parser.parse_args()
    try:
        if args.action in {"export", "backup"}:
            with memory_lock():
                result = create_archive(args.output or default_backup_path())
            print(result)
        elif args.action == "verify":
            with tempfile.TemporaryDirectory(prefix="xiapin-verify-") as directory:
                manifest, content = read_archive(args.archive, Path(directory))
            print(f"OK: format {manifest['version']}, {len(content)} data file(s)")
        elif args.action in {"import", "restore"}:
            with memory_lock():
                backup = install_archive(args.archive, args.replace)
                advance_generation()
            reload_running_engines()
            print(f"Imported. Previous memory backup: {backup}")
        elif args.action == "migrate":
            with memory_lock():
                backup = migrate_legacy()
                if backup:
                    advance_generation()
            if backup:
                print(f"Migrated legacy learning data. Backup: {backup}")
            else:
                print("No legacy learning data migration was needed.")
        else:
            for name, path in paths().items():
                print(f"{name}: {path if path.is_file() else 'not created yet'}")
            for name, path in fcitx_native_paths().items():
                if path.is_file():
                    print(f"legacy Fcitx {name}: {path}")
            for name, path in legacy_table_paths().items():
                if path.is_file():
                    print(f"legacy {name}: {path}")
            print("network: disabled (this tool has no network code)")
    except (MemoryError, OSError) as error:
        print(f"ubuntu-cn-input-memory: {error}", file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
