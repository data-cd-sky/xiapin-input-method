from pathlib import Path
import importlib.util
import json
import os
import stat
import tempfile
import unittest
from unittest import mock
from zipfile import ZipFile
import zlib


MODULE_PATH = Path(__file__).parents[1] / "libexec" / "memoryctl.py"
SPEC = importlib.util.spec_from_file_location("memoryctl", MODULE_PATH)
assert SPEC and SPEC.loader
memoryctl = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(memoryctl)


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.environment = mock.patch.dict(
            os.environ,
            {
                "HOME": str(self.root / "home"),
                "XDG_DATA_HOME": str(self.root / "data"),
                "XDG_STATE_HOME": str(self.root / "state"),
                "XDG_RUNTIME_DIR": str(self.root / "runtime"),
            },
        )
        self.environment.start()
        memoryctl.paths()[memoryctl.USER_TEXT].parent.mkdir(parents=True)

    def tearDown(self):
        self.environment.stop()
        self.temporary.cleanup()

    def compile_fixture(self, name: str, text: bytes) -> None:
        source = self.root / name
        source.write_bytes(text)
        destination = memoryctl.paths()[name]
        memoryctl.convert_to_binary(source, name, destination)

    def test_export_verify_and_replace_import(self):
        user_text = "你 ni 0\n你好 ni'hao 0\n".encode()
        history_text = "你好\tnihao\n中国\tzhongguo\n".encode()
        self.compile_fixture(memoryctl.USER_TEXT, user_text)
        self.compile_fixture(memoryctl.HISTORY_TEXT, history_text)

        archive = self.root / "portable.ucimem"
        memoryctl.create_archive(archive)
        self.assertEqual(stat.S_IMODE(archive.stat().st_mode), 0o600)
        with tempfile.TemporaryDirectory() as directory:
            manifest, content = memoryctl.read_archive(archive, Path(directory))
        self.assertEqual(manifest["format"], memoryctl.FORMAT)
        self.assertEqual(set(content), {memoryctl.USER_TEXT, memoryctl.HISTORY_TEXT})

        for path in memoryctl.paths().values():
            path.unlink()
        backup = memoryctl.install_archive(archive, replace=True)
        self.assertTrue(backup.is_file())
        for path in memoryctl.paths().values():
            self.assertTrue(path.is_file())
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_checksum_tampering_is_rejected(self):
        archive = self.root / "portable.ucimem"
        memoryctl.create_archive(archive)
        broken = self.root / "broken.ucimem"
        with ZipFile(archive) as source, ZipFile(broken, "w") as output:
            manifest = json.loads(source.read(memoryctl.MANIFEST))
            manifest["format"] = "wrong-format"
            output.writestr(memoryctl.MANIFEST, json.dumps(manifest))
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(memoryctl.MemoryError):
                memoryctl.read_archive(broken, Path(directory))

    def test_decompression_failure_is_reported_as_archive_error(self):
        archive = self.root / "broken-compression.ucimem"
        archive.write_bytes(b"not a zip archive")
        with mock.patch.object(
            memoryctl,
            "ZipFile",
            side_effect=zlib.error("invalid compressed data"),
        ):
            with tempfile.TemporaryDirectory() as directory:
                with self.assertRaisesRegex(memoryctl.MemoryError, "invalid archive"):
                    memoryctl.read_archive(archive, Path(directory))

    def test_history_merge_preserves_repetitions(self):
        line = "你好\tnihao\n".encode()
        merged = memoryctl.merge_text(memoryctl.HISTORY_TEXT, line, line)
        self.assertEqual(merged.count(line), 2)

    def test_native_user_dictionary_merge(self):
        current = "你 ni 0\n".encode()
        incoming = "你 ni 0\n好 hao 0\n".encode()
        merged = memoryctl.merge_text(memoryctl.USER_TEXT, current, incoming)
        self.assertEqual(merged.count("你 ni 0".encode()), 1)
        self.assertEqual(merged.count("好 hao 0".encode()), 1)

    def test_legacy_table_dictionary_is_migrated(self):
        legacy = "nihaoni 你好你 1\n[Auto]\nnihao 你好 2\n你 ni\n[Delete]\nma 吗\n".encode()
        result = memoryctl.legacy_user_text(legacy)
        self.assertIn("你好 ni'hao 1".encode(), result)
        self.assertIn("你好你 ni'hao'ni 0".encode(), result)
        self.assertNotIn("吗".encode(), result)

    def test_legacy_pinyin_segmentation_uses_word_length(self):
        canonical, syllables = memoryctl.pinyin_reference()
        self.assertEqual(
            memoryctl.segment_pinyin("xian", "西安", canonical, syllables), "xi'an"
        )
        self.assertEqual(
            memoryctl.segment_pinyin("xian", "先", canonical, syllables), "xian"
        )
        self.assertEqual(
            memoryctl.segment_pinyin("wending", "稳定", canonical, syllables),
            "wen'ding",
        )

if __name__ == "__main__":
    unittest.main()
