import importlib.util
import pathlib
import sys
import tempfile
import types
import unittest
from unittest import mock


class FakeSettings:
    @staticmethod
    def new(_schema):
        return None

    @staticmethod
    def sync():
        return None


class FakeVariant:
    def __init__(self, _signature, value):
        self.value = value


fake_gi = types.ModuleType("gi")
fake_gi.require_version = lambda *_args: None
fake_repository = types.ModuleType("gi.repository")
fake_repository.Gio = types.SimpleNamespace(Settings=FakeSettings)
fake_repository.GLib = types.SimpleNamespace(Variant=FakeVariant)
fake_repository.IBus = types.SimpleNamespace(
    init=lambda: None,
    SERVICE_PANEL="org.freedesktop.IBus.Panel",
)
sys.modules.setdefault("gi", fake_gi)
sys.modules.setdefault("gi.repository", fake_repository)

MODULE = pathlib.Path(__file__).parents[1] / "libexec" / "ibusctl.py"
SPEC = importlib.util.spec_from_file_location("ibusctl", MODULE)
ibusctl = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ibusctl)


class SourceListTests(unittest.TestCase):
    def test_merge_places_xiapin_first_and_preserves_other_sources(self):
        sources = [("xkb", "us"), ("ibus", "libpinyin"), ("ibus", "xiapin")]
        self.assertEqual(
            ibusctl.merge_sources(sources),
            [("ibus", "xiapin"), ("xkb", "us"), ("ibus", "libpinyin")],
        )

    def test_merge_is_idempotent(self):
        sources = [("ibus", "xiapin"), ("xkb", "cn")]
        self.assertEqual(ibusctl.merge_sources(sources), sources)

    def test_cleanup_removes_only_xiapin(self):
        sources = [("ibus", "xiapin"), ("xkb", "cn"), ("ibus", "libpinyin")]
        self.assertEqual(
            ibusctl.remove_source(sources),
            [("xkb", "cn"), ("ibus", "libpinyin")],
        )

    def test_cleanup_without_graphical_session_still_stops_engine(self):
        with mock.patch.object(ibusctl.os, "geteuid", return_value=1000), \
             mock.patch.object(
                 ibusctl, "graphical_session_available", return_value=False
             ), mock.patch.object(ibusctl, "settings") as settings, \
             mock.patch.object(ibusctl, "stop_xiapin_engines") as stop:
            self.assertEqual(ibusctl.cleanup(), 0)
        settings.assert_not_called()
        stop.assert_called_once_with()

    def test_gnome_selection_activates_only_xiapin_then_restores_sources(self):
        values = {
            "sources": [("xkb", "cn"), ("ibus", "libpinyin")],
            "mru-sources": [("ibus", "libpinyin"), ("xkb", "cn")],
        }
        config = mock.Mock()
        config.get_value.side_effect = lambda key: types.SimpleNamespace(
            unpack=lambda: values[key]
        )
        writes = []
        config.set_value.side_effect = lambda key, variant: writes.append(
            (key, variant.value)
        )
        listing = types.SimpleNamespace(
            returncode=0,
            stdout=(
                "  xkb:us::eng - English (US)\n"
                "  xkb:cn::zho - Chinese\n"
                "  libpinyin - Intelligent Pinyin\n"
            ),
            stderr="",
        )
        with mock.patch.object(
            ibusctl, "wait_for_engine", return_value=True
        ) as wait, mock.patch.object(ibusctl, "run", return_value=listing):
            ibusctl.configure_sources_and_select(config, "/usr/bin/ibus")
        self.assertEqual(
            writes,
            [
                ("mru-sources", [("ibus", "xiapin"), ("ibus", "libpinyin"), ("xkb", "cn")]),
                ("sources", [("ibus", "xiapin")]),
                ("sources", [("ibus", "xiapin"), ("xkb", "cn"), ("ibus", "libpinyin")]),
            ],
        )
        self.assertEqual(
            wait.call_args_list,
            [
                mock.call("/usr/bin/ibus", "xiapin", 100),
                mock.call("/usr/bin/ibus", "xiapin", 50),
            ],
        )

    def test_unavailable_sources_drops_engines_ibus_cannot_resolve(self):
        listing = types.SimpleNamespace(
            returncode=0,
            stdout=(
                "language: English\n"
                "  xkb:us::eng - English (US)\n"
                "language: Chinese\n"
                "  libpinyin - Intelligent Pinyin\n"
                "  xiapin - 瞎拼输入法\n"
            ),
            stderr="",
        )
        with mock.patch.object(ibusctl, "run", return_value=listing):
            kept, dropped, pruned = ibusctl.unavailable_sources(
                "/usr/bin/ibus",
                [
                    ("ibus", "xiapin"),
                    ("xkb", "us"),
                    ("xkb", "cn"),
                    ("ibus", "libpinyin"),
                ],
            )
        self.assertTrue(pruned)
        self.assertEqual(
            kept, [("ibus", "xiapin"), ("xkb", "us"), ("ibus", "libpinyin")]
        )
        self.assertEqual(dropped, [("xkb", "cn")])

    def test_unavailable_sources_keeps_everything_when_listing_fails(self):
        failure = types.SimpleNamespace(returncode=1, stdout="", stderr="bus down")
        sources = [("ibus", "xiapin"), ("xkb", "cn")]
        with mock.patch.object(ibusctl, "run", return_value=failure):
            kept, dropped, pruned = ibusctl.unavailable_sources(
                "/usr/bin/ibus", sources
            )
        self.assertEqual(kept, sources)
        self.assertEqual(dropped, [])
        self.assertFalse(pruned)

    def test_unavailable_sources_keeps_keyboard_variants(self):
        listing = types.SimpleNamespace(
            returncode=0,
            stdout=(
                "  xkb:us::eng - English (US)\n"
                "  xkb:us:intl:eng - English (US, intl.)\n"
                "  libpinyin - Intelligent Pinyin\n"
            ),
            stderr="",
        )
        sources = [
            ("ibus", "xiapin"),
            ("xkb", "us"),
            ("xkb", "us+intl"),
            ("ibus", "libpinyin"),
        ]
        with mock.patch.object(ibusctl, "run", return_value=listing):
            kept, dropped, pruned = ibusctl.unavailable_sources(
                "/usr/bin/ibus", sources
            )
        self.assertEqual(kept, sources)
        self.assertEqual(dropped, [])
        self.assertFalse(pruned)

    def test_unavailable_sources_keeps_everything_without_xkb_engines(self):
        listing = types.SimpleNamespace(
            returncode=0,
            stdout="  libpinyin - Intelligent Pinyin\n  xiapin - 瞎拼输入法\n",
            stderr="",
        )
        sources = [("ibus", "xiapin"), ("xkb", "us")]
        with mock.patch.object(ibusctl, "run", return_value=listing):
            kept, dropped, pruned = ibusctl.unavailable_sources(
                "/usr/bin/ibus", sources
            )
        self.assertEqual(kept, sources)
        self.assertEqual(dropped, [])
        self.assertFalse(pruned)

    def test_selection_prunes_broken_source_before_activating(self):
        values = {
            "sources": [("xkb", "cn"), ("ibus", "libpinyin")],
            "mru-sources": [("ibus", "libpinyin"), ("xkb", "cn")],
        }
        config = mock.Mock()
        config.get_value.side_effect = lambda key: types.SimpleNamespace(
            unpack=lambda: values[key]
        )
        writes = []
        config.set_value.side_effect = lambda key, variant: writes.append(
            (key, variant.value)
        )
        listing = types.SimpleNamespace(
            returncode=0,
            stdout="  xkb:us::eng - English (US)\n  libpinyin - Intelligent Pinyin\n",
            stderr="",
        )
        with mock.patch.object(ibusctl, "run", return_value=listing), \
                mock.patch.object(ibusctl, "wait_for_engine", return_value=True):
            ibusctl.configure_sources_and_select(config, "/usr/bin/ibus")
        self.assertEqual(
            writes[0], ("mru-sources", [("ibus", "xiapin"), ("ibus", "libpinyin")])
        )
        self.assertEqual(writes[1], ("sources", [("ibus", "xiapin")]))
        self.assertEqual(
            writes[2], ("sources", [("ibus", "xiapin"), ("ibus", "libpinyin")])
        )
        for _key, value in writes:
            self.assertNotIn(("xkb", "cn"), value)

    def test_gnome_selection_does_not_force_the_ibus_backend(self):
        values = {
            "sources": [("xkb", "cn"), ("ibus", "libpinyin")],
            "mru-sources": [("ibus", "libpinyin"), ("xkb", "cn")],
        }
        config = mock.Mock()
        config.get_value.side_effect = lambda key: types.SimpleNamespace(
            unpack=lambda: values[key]
        )
        listing = types.SimpleNamespace(
            returncode=0,
            stdout="  xkb:cn::zho - Chinese\n  libpinyin - Intelligent Pinyin\n",
            stderr="",
        )
        with mock.patch.object(
            ibusctl, "wait_for_engine", side_effect=[True, True]
        ), mock.patch.object(ibusctl, "run", return_value=listing) as run:
            ibusctl.configure_sources_and_select(config, "/usr/bin/ibus")
        # Listing engines is allowed; forcing the Engine behind GNOME is not.
        self.assertNotIn(
            mock.call(["/usr/bin/ibus", "engine", "xiapin"], check=False),
            run.call_args_list,
        )

    def test_gnome_selection_failure_is_reported(self):
        values = {"sources": [], "mru-sources": []}
        config = mock.Mock()
        config.get_value.side_effect = lambda key: types.SimpleNamespace(
            unpack=lambda: values[key]
        )
        with mock.patch.object(
            ibusctl, "wait_for_engine", return_value=False
        ):
            with self.assertRaisesRegex(RuntimeError, "did not activate Xiapin"):
                ibusctl.configure_sources_and_select(config, "/usr/bin/ibus")
        self.assertEqual(
            [call.args[0] for call in config.set_value.call_args_list],
            ["mru-sources", "sources", "sources"],
        )

    def test_locked_screen_adds_xiapin_without_forcing_selection(self):
        values = {
            "sources": [("xkb", "cn"), ("ibus", "libpinyin")],
            "mru-sources": [("ibus", "libpinyin"), ("xkb", "cn")],
        }
        config = mock.Mock()
        config.get_value.side_effect = lambda key: types.SimpleNamespace(
            unpack=lambda: values[key]
        )
        writes = []
        config.set_value.side_effect = lambda key, variant: writes.append(
            (key, variant.value)
        )
        ibusctl.configure_sources(config)
        self.assertEqual(
            writes,
            [
                ("mru-sources", [("ibus", "xiapin"), ("ibus", "libpinyin"), ("xkb", "cn")]),
                ("sources", [("ibus", "xiapin"), ("xkb", "cn"), ("ibus", "libpinyin")]),
            ],
        )

    def test_unlock_helper_is_started_without_blocking_setup(self):
        result = types.SimpleNamespace(returncode=0, stderr="")
        with mock.patch.object(
            ibusctl.shutil, "which", return_value="/usr/bin/systemctl"
        ), mock.patch.object(ibusctl, "run", return_value=result) as run:
            ibusctl.defer_selection_until_unlock()
        run.assert_called_once_with(
            [
                "/usr/bin/systemctl",
                "--user",
                "start",
                "--no-block",
                "xiapin-unlock.service",
            ],
            check=False,
        )


class SessionBusTests(unittest.TestCase):
    @staticmethod
    def result(returncode=0, stderr="", stdout=""):
        return types.SimpleNamespace(
            returncode=returncode, stderr=stderr, stdout=stdout
        )

    def test_metadata_query_uses_a_fresh_helper_process(self):
        encoded = '["\\ud83d\\ude0e", "/icon.svg", "name", "zh_CN"]\n'
        with mock.patch.object(
            ibusctl, "run", return_value=self.result(stdout=encoded)
        ) as run:
            metadata = ibusctl.installed_engine_metadata()
        self.assertEqual(metadata, ("😎", "/icon.svg", "name", "zh_CN"))
        run.assert_called_once_with(
            [str(pathlib.Path(ibusctl.__file__).resolve()), "_metadata"], check=False
        )

    def test_desktop_panel_waits_for_gnome_shell_to_reconnect(self):
        bus = mock.Mock()
        bus.is_connected.side_effect = [False, True, True]
        bus.name_has_owner.side_effect = [False, True]
        with mock.patch.object(
            ibusctl.IBus, "Bus", types.SimpleNamespace(new=lambda: bus), create=True
        ), mock.patch.object(ibusctl.time, "sleep") as sleep:
            self.assertTrue(ibusctl.wait_for_desktop_panel(3))
        self.assertEqual(bus.name_has_owner.call_args_list, [
            mock.call("org.freedesktop.IBus.Panel"),
            mock.call("org.freedesktop.IBus.Panel"),
        ])
        self.assertEqual(sleep.call_count, 2)

    def test_desktop_panel_timeout_is_reported(self):
        bus = mock.Mock()
        bus.is_connected.return_value = True
        bus.name_has_owner.return_value = False
        with mock.patch.object(
            ibusctl.IBus, "Bus", types.SimpleNamespace(new=lambda: bus), create=True
        ), mock.patch.object(ibusctl.time, "sleep") as sleep:
            self.assertFalse(ibusctl.wait_for_desktop_panel(2))
        self.assertEqual(sleep.call_count, 2)

    def test_existing_bus_is_not_restarted(self):
        with mock.patch.object(ibusctl, "run", return_value=self.result()) as run, \
             mock.patch.object(ibusctl.time, "sleep") as sleep:
            ibusctl.ensure_ibus_bus("/usr/bin/ibus")
        run.assert_called_once_with(["/usr/bin/ibus", "list-engine"], check=False)
        sleep.assert_not_called()

    def test_asynchronous_systemd_restart_is_waited_for(self):
        results = [self.result(1), self.result(1), self.result(0)]
        with mock.patch.object(ibusctl, "run", side_effect=results) as run, \
             mock.patch.object(ibusctl.shutil, "which") as which, \
             mock.patch.object(ibusctl.time, "sleep") as sleep:
            ibusctl.ensure_ibus_bus("/usr/bin/ibus")
        self.assertEqual(
            run.call_args_list,
            [mock.call(["/usr/bin/ibus", "list-engine"], check=False)] * 3,
        )
        self.assertEqual(sleep.call_count, 2)
        which.assert_not_called()

    def test_missing_x11_bus_is_started_and_waited_for(self):
        results = (
            [self.result(1)] * 50
            + [self.result(1), self.result(1)]
            + [self.result(0), self.result(0)]
        )
        with mock.patch.object(ibusctl, "run", side_effect=results) as run, \
             mock.patch.object(
                 ibusctl.shutil,
                 "which",
                 side_effect=["/usr/bin/systemctl", "/usr/bin/ibus-daemon"],
             ), \
             mock.patch.object(ibusctl.time, "sleep"), \
             mock.patch.dict(
                 ibusctl.os.environ,
                 {"XDG_SESSION_TYPE": "x11", "IBUS_ADDRESS": "unix:path=/stale"},
             ):
            ibusctl.ensure_ibus_bus("/usr/bin/ibus")
            self.assertNotIn("IBUS_ADDRESS", ibusctl.os.environ)
        self.assertEqual(
            run.call_args_list,
            [mock.call(["/usr/bin/ibus", "list-engine"], check=False)] * 50 + [
                mock.call(
                    [
                        "/usr/bin/systemctl",
                        "--user",
                        "reset-failed",
                        "org.freedesktop.IBus.session.GNOME.service",
                    ],
                    check=False,
                ),
                mock.call(
                    [
                        "/usr/bin/systemctl",
                        "--user",
                        "start",
                        "org.freedesktop.IBus.session.GNOME.service",
                    ],
                    check=False,
                ),
                mock.call(
                    [
                        "/usr/bin/ibus-daemon",
                        "--daemonize",
                        "--panel=disable",
                        "--xim",
                    ],
                    check=False,
                ),
                mock.call(["/usr/bin/ibus", "list-engine"], check=False),
            ],
        )

    def test_missing_bus_is_restored_by_the_gnome_systemd_service(self):
        results = (
            [self.result(1)] * 50
            + [self.result(0), self.result(0), self.result(0)]
        )
        with mock.patch.object(ibusctl, "run", side_effect=results) as run, \
             mock.patch.object(
                 ibusctl.shutil, "which", return_value="/usr/bin/systemctl"
             ) as which, mock.patch.object(ibusctl.time, "sleep"):
            ibusctl.ensure_ibus_bus("/usr/bin/ibus")
        self.assertEqual(
            run.call_args_list[-3:],
            [
                mock.call(
                    [
                        "/usr/bin/systemctl",
                        "--user",
                        "reset-failed",
                        "org.freedesktop.IBus.session.GNOME.service",
                    ],
                    check=False,
                ),
                mock.call(
                    [
                        "/usr/bin/systemctl",
                        "--user",
                        "start",
                        "org.freedesktop.IBus.session.GNOME.service",
                    ],
                    check=False,
                ),
                mock.call(["/usr/bin/ibus", "list-engine"], check=False),
            ],
        )
        which.assert_called_once_with("systemctl")

    def test_current_metadata_does_not_restart_ibus(self):
        current = ibusctl.ENGINE_METADATA
        with mock.patch.object(
            ibusctl, "installed_engine_metadata", return_value=current
        ), mock.patch.object(ibusctl, "run") as run:
            self.assertFalse(ibusctl.refresh_stale_ibus_metadata("/usr/bin/ibus"))
        run.assert_not_called()

    def test_first_install_refreshes_missing_registry_entry(self):
        with mock.patch.object(
            ibusctl,
            "installed_engine_metadata",
            side_effect=[None, ibusctl.ENGINE_METADATA],
        ), mock.patch.object(
            ibusctl, "run", return_value=self.result()
        ) as run, mock.patch.object(ibusctl, "ensure_ibus_bus") as ensure:
            self.assertTrue(ibusctl.refresh_stale_ibus_metadata("/usr/bin/ibus"))
        run.assert_called_once_with(["/usr/bin/ibus", "restart"], check=False)
        ensure.assert_called_once_with("/usr/bin/ibus")

    def test_stale_metadata_restarts_ibus_and_recovers_the_bus(self):
        with mock.patch.object(
            ibusctl,
            "installed_engine_metadata",
            side_effect=[
                ("瞎", ibusctl.ENGINE_ICON, "瞎拼", "zh_CN"),
                ibusctl.ENGINE_METADATA,
            ],
        ), mock.patch.object(ibusctl, "run", return_value=self.result()) as run, \
             mock.patch.object(ibusctl, "ensure_ibus_bus") as ensure, \
             mock.patch.dict(ibusctl.os.environ, {"IBUS_ADDRESS": "old"}):
            self.assertTrue(ibusctl.refresh_stale_ibus_metadata("/usr/bin/ibus"))
            self.assertNotIn("IBUS_ADDRESS", ibusctl.os.environ)
        run.assert_called_once_with(["/usr/bin/ibus", "restart"], check=False)
        ensure.assert_called_once_with("/usr/bin/ibus")

    def test_missing_registry_entry_after_refresh_is_reported(self):
        with mock.patch.object(
            ibusctl, "installed_engine_metadata", side_effect=[None, None]
        ), mock.patch.object(
            ibusctl, "run", return_value=self.result()
        ), mock.patch.object(ibusctl, "ensure_ibus_bus"):
            with self.assertRaisesRegex(RuntimeError, "still absent"):
                ibusctl.refresh_stale_ibus_metadata("/usr/bin/ibus")

    def test_failed_metadata_restart_is_reported(self):
        failure = self.result(1, "restart denied")
        with mock.patch.object(
            ibusctl,
            "installed_engine_metadata",
            return_value=("瞎", ibusctl.ENGINE_ICON),
        ), mock.patch.object(ibusctl, "run", return_value=failure):
            with self.assertRaisesRegex(RuntimeError, "restart denied"):
                ibusctl.refresh_stale_ibus_metadata("/usr/bin/ibus")

    def test_legacy_fcitx_waits_for_original_pid_without_reactivation(self):
        process = mock.Mock()
        process.exists.side_effect = [True, False]
        status = mock.Mock()
        status.read_text.return_value = "Name:\tfcitx5\nUid:\t1000 1000 1000 1000\n"
        status.parent = process
        with mock.patch.object(ibusctl.pathlib.Path, "glob", return_value=[status]), \
             mock.patch.object(ibusctl.os, "getuid", return_value=1000), \
             mock.patch.object(ibusctl, "run", return_value=self.result()) as run, \
             mock.patch.object(
                 ibusctl.shutil, "which", return_value="/usr/bin/fcitx5-remote"
             ):
            ibusctl.stop_legacy_fcitx()
        run.assert_called_once_with(["/usr/bin/fcitx5-remote", "-e"], check=False)

    def test_absent_legacy_fcitx_does_not_call_remote(self):
        with mock.patch.object(ibusctl.pathlib.Path, "glob", return_value=[]), \
             mock.patch.object(ibusctl, "run") as run:
            ibusctl.stop_legacy_fcitx()
        run.assert_not_called()

    def test_stop_xiapin_engines_stops_static_and_dynamic_processes(self):
        static = mock.Mock()
        static.name = "101"
        static.exists.side_effect = [True, False, False]
        dynamic = mock.Mock()
        dynamic.name = "102"
        dynamic.exists.side_effect = [True, False]
        with mock.patch.object(
            ibusctl, "xiapin_engine_processes", return_value=[static, dynamic]
        ), mock.patch.object(ibusctl.os, "kill") as kill, mock.patch.object(
            ibusctl, "dynamic_pid_path"
        ) as pid_path, mock.patch.object(ibusctl.time, "sleep"):
            ibusctl.stop_xiapin_engines()
        self.assertEqual(
            kill.call_args_list,
            [mock.call(101, ibusctl.signal.SIGTERM), mock.call(102, ibusctl.signal.SIGTERM)],
        )
        pid_path.return_value.unlink.assert_called_once_with()

    def test_engine_scan_accepts_live_and_deleted_package_binary(self):
        live = mock.Mock()
        live.name = "201"
        live.stat.return_value.st_uid = 1000
        deleted = mock.Mock()
        deleted.name = "202"
        deleted.stat.return_value.st_uid = 1000
        unrelated = mock.Mock()
        unrelated.name = "203"
        unrelated.stat.return_value.st_uid = 1000

        def readlink(path):
            process = path.parent
            if process is live:
                return str(ibusctl.ENGINE_PATH)
            if process is deleted:
                return f"{ibusctl.ENGINE_PATH} (deleted)"
            return "/usr/libexec/another-engine"

        def read_bytes(process):
            if process is live:
                return b"/usr/libexec/ibus-engine-xiapin\0--ibus\0"
            if process is deleted:
                return b"/usr/libexec/ibus-engine-xiapin\0--register\0"
            return b"/usr/libexec/another-engine\0--ibus\0"

        live.__truediv__ = lambda process, name: types.SimpleNamespace(
            parent=process, read_bytes=lambda: read_bytes(process)
        )
        deleted.__truediv__ = lambda process, name: types.SimpleNamespace(
            parent=process, read_bytes=lambda: read_bytes(process)
        )
        unrelated.__truediv__ = lambda process, name: types.SimpleNamespace(
            parent=process, read_bytes=lambda: read_bytes(process)
        )
        with mock.patch.object(
            ibusctl.pathlib.Path, "glob", return_value=[live, deleted, unrelated]
        ), mock.patch.object(ibusctl.os, "readlink", side_effect=readlink), mock.patch.object(
            ibusctl.os, "getuid", return_value=1000
        ):
            self.assertEqual(ibusctl.xiapin_engine_processes(), [live, deleted])

    def test_completed_migration_marker_uses_xdg_state_home(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            ibusctl.os.environ, {"XDG_STATE_HOME": directory}
        ):
            self.assertEqual(
                ibusctl.legacy_migration_marker(),
                pathlib.Path(directory)
                / "ubuntu-cn-input/2.0-fcitx-migration-complete",
            )

    def test_completed_migration_does_not_touch_fcitx_or_memory(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            ibusctl.os.environ, {"XDG_STATE_HOME": directory}
        ), mock.patch.object(ibusctl, "stop_legacy_fcitx") as stop, \
             mock.patch.object(ibusctl, "restore_legacy_environment") as restore, \
             mock.patch.object(ibusctl, "run") as run:
            marker = ibusctl.legacy_migration_marker()
            marker.parent.mkdir(parents=True)
            marker.touch()
            ibusctl.migrate_legacy_once()
        stop.assert_not_called()
        restore.assert_not_called()
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
