from pathlib import Path
import importlib.util
import tempfile
import unittest


MODULE = Path(__file__).parents[1] / "libexec" / "legacy_profilectl.py"
SPEC = importlib.util.spec_from_file_location("legacy_profilectl", MODULE)
profilectl = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(profilectl)

PROFILE = """[Groups/0]
DefaultIM=xiapin

[Groups/0/Items/0]
Name=keyboard-us
Layout=

[Groups/0/Items/1]
Name=xiapin
Layout=

[Groups/0/Items/2]
Name=unrelated-im
Layout=de

[GroupOrder]
0=Default
"""


class LegacyProfileTests(unittest.TestCase):
    def test_remove_only_xiapin_and_preserve_unrelated_method(self):
        result = profilectl.remove_input_method(PROFILE, "xiapin")
        self.assertNotIn("Name=xiapin", result)
        self.assertIn("DefaultIM=keyboard-us", result)
        self.assertIn("Name=unrelated-im\nLayout=de", result)

    def test_remove_missing_entry_is_idempotent(self):
        once = profilectl.remove_input_method(PROFILE, "stable-pinyin")
        twice = profilectl.remove_input_method(once, "stable-pinyin")
        self.assertEqual(once, twice)

    def test_atomic_write_is_private(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile"
            path.write_text(PROFILE, encoding="utf-8")
            profilectl.atomic_write(path, PROFILE)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
