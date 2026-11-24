#!/usr/bin/python3
"""Register Xiapin with the current IBus/GNOME desktop session."""

import argparse
import fcntl
import json
import os
import pathlib
import signal
import shutil
import subprocess
import sys
import time

try:
    import gi

    gi.require_version("Gio", "2.0")
    gi.require_version("IBus", "1.0")
    from gi.repository import Gio, GLib, IBus
except (ImportError, ValueError) as error:
    print(f"Xiapin needs python3-gi: {error}", file=sys.stderr)
    raise SystemExit(1)


ENGINE = ("ibus", "xiapin")
SCHEMA = "org.gnome.desktop.input-sources"
ENGINE_PATH = pathlib.Path("/usr/libexec/ibus-engine-xiapin")
ENGINE_SYMBOL = "😎"
ENGINE_ICON = "/usr/share/icons/hicolor/scalable/apps/xiapin.svg"
ENGINE_LONGNAME = "瞎拼输入法"
ENGINE_LANGUAGE = "zh_CN"
ENGINE_METADATA = (ENGINE_SYMBOL, ENGINE_ICON, ENGINE_LONGNAME, ENGINE_LANGUAGE)
SCREENSAVER_NAME = "org.gnome.ScreenSaver"
SCREENSAVER_PATH = "/org/gnome/ScreenSaver"
SCREENSAVER_INTERFACE = "org.gnome.ScreenSaver"


def legacy_migration_marker():
    state = pathlib.Path(
        os.environ.get("XDG_STATE_HOME", pathlib.Path.home() / ".local/state")
    ) / "ubuntu-cn-input"
    return state / "2.0-fcitx-migration-complete"


def merge_sources(sources):
    """Return Xiapin first, preserving every unrelated source and its order."""
    return [ENGINE] + [tuple(item) for item in sources if tuple(item) != ENGINE]


def remove_source(sources):
    """Remove only Xiapin from a source sequence."""
    return [tuple(item) for item in sources if tuple(item) != ENGINE]


def run(command, *, check=True):
    return subprocess.run(
        command,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=15,
    )


def dynamic_pid_path():
    runtime = pathlib.Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
    return runtime / "xiapin-dynamic-engine.pid"


def xiapin_engine_processes():
    """Return this user's live static or dynamic Xiapin Engine processes."""
    processes = []
    expected = {str(ENGINE_PATH), f"{ENGINE_PATH} (deleted)"}
    for process in pathlib.Path("/proc").glob("[0-9]*"):
        try:
            executable = os.readlink(process / "exe")
            arguments = (process / "cmdline").read_bytes().split(b"\0")
            if (
                executable in expected
                and process.stat().st_uid == os.getuid()
                and (b"--ibus" in arguments or b"--register" in arguments)
            ):
                processes.append(process)
        except (FileNotFoundError, OSError, PermissionError):
            continue
    return processes


def stop_xiapin_engines():
    """Stop package-owned Engines before removal or after binary replacement."""
    processes = xiapin_engine_processes()
    for process in processes:
        try:
            os.kill(int(process.name), signal.SIGTERM)
        except (FileNotFoundError, OSError, ValueError, PermissionError):
            pass
    for _ in range(30):
        if not any(process.exists() for process in processes):
            break
        time.sleep(0.1)
    try:
        dynamic_pid_path().unlink()
    except FileNotFoundError:
        pass


def ensure_ibus_bus(ibus):
    """Start the session IBus only when the legacy Fcitx setup removed it."""
    # GNOME restarts its systemd-managed IBus service asynchronously. Starting
    # another daemon during that window races for the D-Bus name and can leave
    # the per-user address file pointing at the losing process. Wait for the
    # desktop service before using the direct-start recovery needed by old 1.x
    # migrations and non-systemd sessions.
    for _ in range(50):
        if run([ibus, "list-engine"], check=False).returncode == 0:
            return
        time.sleep(0.1)

    # IBus 1.5.26 on Ubuntu 22.04 exits successfully for `ibus restart` but
    # does not ask systemd to start the GNOME unit again. Prefer restoring the
    # desktop-owned service so it remains tied to the graphical session.
    # Non-systemd desktops fall through to the direct-start recovery below.
    systemctl = shutil.which("systemctl")
    if systemctl:
        service = "org.freedesktop.IBus.session.GNOME.service"
        run([systemctl, "--user", "reset-failed", service], check=False)
        started = run([systemctl, "--user", "start", service], check=False)
        if started.returncode == 0:
            for _ in range(50):
                if run([ibus, "list-engine"], check=False).returncode == 0:
                    return
                time.sleep(0.1)

    # An Fcitx-to-IBus migration can invalidate an address inherited by the
    # systemd user manager. Once that address has failed, keeping it would
    # force every readiness probe to the dead socket even after ibus-daemon
    # writes a fresh address file for this graphical session.
    os.environ.pop("IBUS_ADDRESS", None)
    daemon = shutil.which("ibus-daemon")
    if not daemon:
        raise RuntimeError("IBus session bus is unavailable and ibus-daemon is missing")
    command = [daemon, "--daemonize", "--panel=disable"]
    if os.environ.get("XDG_SESSION_TYPE") == "x11":
        command.append("--xim")
    started = run(command, check=False)
    if started.returncode != 0:
        error = started.stderr.strip() or "ibus-daemon could not start"
        raise RuntimeError(f"IBus session recovery failed: {error}")
    for _ in range(50):
        if run([ibus, "list-engine"], check=False).returncode == 0:
            return
        time.sleep(0.1)
    raise RuntimeError("IBus session bus did not become ready")


def read_live_engine_metadata():
    """Read Xiapin metadata from a new GI bus object in this process."""
    IBus.init()
    bus = IBus.Bus.new()
    if not bus.is_connected():
        return None
    for engine in bus.list_engines():
        if engine.get_name() == ENGINE[1]:
            return (
                engine.get_symbol(),
                engine.get_icon(),
                engine.get_longname(),
                engine.get_language(),
            )
    return None


def installed_engine_metadata():
    """Read metadata in a fresh process so an IBus restart cannot reuse GI state."""
    helper = pathlib.Path(__file__).resolve()
    result = run([str(helper), "_metadata"], check=False)
    if result.returncode != 0:
        error = result.stderr.strip() or "metadata helper could not query IBus"
        raise RuntimeError(error)
    try:
        metadata = json.loads(result.stdout)
    except (json.JSONDecodeError, TypeError) as error:
        raise RuntimeError("metadata helper returned invalid data") from error
    if metadata is None:
        return None
    if not isinstance(metadata, list) or len(metadata) != len(ENGINE_METADATA):
        raise RuntimeError("metadata helper returned an invalid engine descriptor")
    return tuple(metadata)


def refresh_stale_ibus_metadata(ibus):
    """Make the installed static component visible on the live IBus bus."""
    metadata = installed_engine_metadata()
    if metadata == ENGINE_METADATA:
        return False

    restarted = run([ibus, "restart"], check=False)
    if restarted.returncode != 0:
        error = restarted.stderr.strip() or "ibus restart failed"
        raise RuntimeError(f"IBus metadata refresh failed: {error}")

    # The user manager can retain the old daemon address across an in-place
    # package upgrade. Let the ibus command discover the replacement socket.
    os.environ.pop("IBUS_ADDRESS", None)
    # IBus 1.5.26 can stop without relaunching its daemon, while newer
    # releases relaunch asynchronously. The normal recovery helper handles
    # both cases. Do not reuse the pre-restart IBus GI object here: older
    # releases cache its dead address for the lifetime of this Python process.
    ensure_ibus_bus(ibus)
    refreshed = installed_engine_metadata()
    if refreshed is None:
        raise RuntimeError(
            "Xiapin is still absent from the IBus registry after refresh"
        )
    if refreshed != ENGINE_METADATA:
        raise RuntimeError(
            "Xiapin metadata is still stale after the IBus registry refresh"
        )
    return True


def wait_for_desktop_panel(attempts=100):
    """Wait until GNOME Shell has reattached its panel to the live IBus bus."""
    # `ibus list-engine` can succeed as soon as the replacement daemon owns
    # org.freedesktop.IBus. GNOME Shell reconnects asynchronously and only
    # rebuilds its Engine descriptors after it owns org.freedesktop.IBus.Panel
    # on that same private bus. Changing `sources` in the gap makes Shell drop
    # the newly installed Engine as unavailable, so the top-bar source remains
    # unchanged even though `ibus engine` can already query the daemon.
    IBus.init()
    bus = IBus.Bus.new()
    for _ in range(attempts):
        if bus.is_connected() and bus.name_has_owner(IBus.SERVICE_PANEL):
            return True
        time.sleep(0.1)
    return False


def wait_for_engine(ibus, expected, attempts):
    """Observe GNOME's selected Engine without changing it behind the Shell."""
    for _ in range(attempts):
        current = run([ibus, "engine"], check=False)
        if current.returncode == 0 and current.stdout.strip() == expected:
            return True
        time.sleep(0.1)
    return False


def configure_sources_and_select(config, ibus):
    """Ask GNOME Shell to rebuild its input-source state with Xiapin first."""
    sources = merge_sources(get_sources(config, "sources"))
    mru_sources = merge_sources(get_sources(config, "mru-sources"))

    # GNOME Shell owns the top-bar currentSource. Its deprecated `current`
    # GSettings key is ignored, and selecting only the IBus backend leaves the
    # Shell indicator stale. It also keeps an in-memory MRU list and does not
    # watch external mru-sources changes. Temporarily leave only Xiapin in the
    # source list, so Shell itself must activate it, then restore every original
    # source with Xiapin first. No `ibus engine xiapin` shortcut is used here.
    set_sources(config, "sources", [ENGINE])
    Gio.Settings.sync()
    if not wait_for_engine(ibus, ENGINE[1], 100):
        # Never strand the user with a temporary one-item list on failure.
        set_sources(config, "mru-sources", mru_sources)
        set_sources(config, "sources", sources)
        Gio.Settings.sync()
        raise RuntimeError("GNOME Shell did not activate Xiapin from its input-source list")

    set_sources(config, "mru-sources", mru_sources)
    set_sources(config, "sources", sources)
    Gio.Settings.sync()
    if not wait_for_engine(ibus, ENGINE[1], 50):
        raise RuntimeError("GNOME Shell did not keep Xiapin active after restoring input sources")


def setup_lock():
    runtime = pathlib.Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
    runtime.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = (runtime / "xiapin-bootstrap.lock").open("w")
    fcntl.flock(lock, fcntl.LOCK_EX)
    return lock


def settings():
    return Gio.Settings.new(SCHEMA)


def get_sources(config, key):
    return [tuple(item) for item in config.get_value(key).unpack()]


def set_sources(config, key, values):
    config.set_value(key, GLib.Variant("a(ss)", values))


def screen_is_locked():
    """Return whether the GNOME screen shield currently owns text focus."""
    try:
        proxy = Gio.DBusProxy.new_for_bus_sync(
            Gio.BusType.SESSION,
            Gio.DBusProxyFlags.DO_NOT_AUTO_START,
            None,
            SCREENSAVER_NAME,
            SCREENSAVER_PATH,
            SCREENSAVER_INTERFACE,
            None,
        )
        result = proxy.call_sync(
            "GetActive", None, Gio.DBusCallFlags.NONE, 2000, None
        )
        return bool(result.unpack()[0])
    except GLib.Error:
        return False


def configure_sources(config):
    """Add Xiapin first without changing the active input source."""
    set_sources(config, "mru-sources", merge_sources(get_sources(config, "mru-sources")))
    set_sources(config, "sources", merge_sources(get_sources(config, "sources")))
    Gio.Settings.sync()


def defer_selection_until_unlock():
    """Start the signal-driven unlock helper without delaying package setup."""
    systemctl = shutil.which("systemctl")
    if not systemctl:
        return
    result = run(
        [systemctl, "--user", "start", "--no-block", "xiapin-unlock.service"],
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "unlock helper could not start")


def graphical_session_available():
    runtime = pathlib.Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
    return (runtime / "bus").is_socket() and bool(
        os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
    )


def restore_legacy_environment():
    """Use the 1.x cleanup helper when upgrading from the Fcitx package."""
    cleanup = pathlib.Path("/usr/libexec/xiapin/legacy-fcitx-cleanup")
    marker = legacy_migration_marker()
    state = marker.parent
    if marker.exists():
        return
    config = pathlib.Path(
        os.environ.get("XDG_CONFIG_HOME", pathlib.Path.home() / ".config")
    )
    profile = config / "fcitx5/profile"
    managed_state = any(
        state.glob("original-*-backup")
    ) or any(state.glob("applied-*.sha256"))
    managed_profile = False
    try:
        text = profile.read_text(encoding="utf-8")
        managed_profile = "Name=xiapin\n" in text or "Name=stable-pinyin\n" in text
    except (FileNotFoundError, UnicodeError, OSError):
        pass
    if cleanup.is_file() and (managed_state or managed_profile):
        result = run([str(cleanup)], check=False)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "legacy Fcitx cleanup failed")
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    marker.touch(mode=0o600, exist_ok=True)


def stop_legacy_fcitx():
    processes = []
    for status in pathlib.Path("/proc").glob("[0-9]*/status"):
        try:
            fields = status.read_text(encoding="ascii").splitlines()
            name = next(line.split()[1] for line in fields if line.startswith("Name:"))
            uid = int(next(line.split()[1] for line in fields if line.startswith("Uid:")))
            if name == "fcitx5" and uid == os.getuid():
                processes.append(status.parent)
        except (FileNotFoundError, OSError, StopIteration, ValueError):
            continue
    if not processes:
        return
    remote = shutil.which("fcitx5-remote")
    if not remote:
        raise RuntimeError("fcitx5 is running but fcitx5-remote is unavailable")
    stopped = run([remote, "-e"], check=False)
    if stopped.returncode != 0:
        raise RuntimeError(stopped.stderr.strip() or "fcitx5 refused the exit request")
    for _ in range(30):
        if not any(process.exists() for process in processes):
            return
        time.sleep(0.1)
    raise RuntimeError("the legacy Fcitx process did not stop for data migration")


def migrate_legacy_once():
    if legacy_migration_marker().exists():
        return
    stop_legacy_fcitx()
    memory = pathlib.Path("/usr/bin/ubuntu-cn-input-memory")
    if memory.is_file():
        run([str(memory), "migrate"])
    restore_legacy_environment()


def setup():
    if os.geteuid() == 0:
        raise RuntimeError("Xiapin setup must run as the desktop user")
    if not graphical_session_available():
        print("No active graphical session; Xiapin will configure at next login.")
        return 0

    with setup_lock():
        stop_xiapin_engines()
        # Stopping Fcitx is necessary only while taking the one-time 1.x data
        # snapshot. A user may keep an unrelated Fcitx installation, and its
        # user service can legitimately restart after `fcitx5-remote -e`.
        # Ordinary 2.0 reinstalls must not fight that service or fail setup.
        migrate_legacy_once()
        im_config = shutil.which("im-config")
        if im_config:
            run([im_config, "-n", "ibus"], check=False)

        ibus = shutil.which("ibus")
        if not ibus:
            raise RuntimeError("ibus command is unavailable")
        ensure_ibus_bus(ibus)
        refresh_stale_ibus_metadata(ibus)
        if not wait_for_desktop_panel():
            raise RuntimeError("GNOME Shell did not reconnect to the IBus panel")
        # A successful install must leave the static component discoverable by
        # GNOME Settings and the top-bar input switcher. A temporary dynamic
        # registration can accept keys but disappears later and is therefore
        # not an acceptable installation fallback.
        config = settings()
        if screen_is_locked():
            # GNOME deliberately disables third-party Engines in password
            # fields. Register Xiapin now, but never use the temporary
            # single-source selection trick to bypass that boundary. The
            # signal-driven helper completes selection as soon as the normal
            # desktop returns and consumes no polling CPU while locked.
            configure_sources(config)
            defer_selection_until_unlock()
            return 0
        configure_sources_and_select(config, ibus)
        return 0


def wait_unlock():
    """Wait without polling, then rerun normal setup after screen unlock."""
    if not graphical_session_available() or not screen_is_locked():
        return setup()

    loop = GLib.MainLoop()
    proxy = Gio.DBusProxy.new_for_bus_sync(
        Gio.BusType.SESSION,
        Gio.DBusProxyFlags.DO_NOT_AUTO_START,
        None,
        SCREENSAVER_NAME,
        SCREENSAVER_PATH,
        SCREENSAVER_INTERFACE,
        None,
    )

    def changed(_proxy, _sender, signal_name, parameters):
        if signal_name == "ActiveChanged" and not parameters.unpack()[0]:
            loop.quit()

    proxy.connect("g-signal", changed)
    # Close the race between the initial check and signal subscription.
    if not screen_is_locked():
        return setup()
    loop.run()
    return setup()


def cleanup():
    if os.geteuid() == 0:
        return 0
    if graphical_session_available():
        config = settings()
        set_sources(config, "sources", remove_source(get_sources(config, "sources")))
        set_sources(
            config, "mru-sources", remove_source(get_sources(config, "mru-sources"))
        )
        Gio.Settings.sync()
    stop_xiapin_engines()
    return 0


def status():
    config = settings()
    sources = get_sources(config, "sources")
    current = run(["ibus", "engine"], check=False)
    print(f"installed_source={'yes' if ENGINE in sources else 'no'}")
    print(f"current_engine={current.stdout.strip() if current.returncode == 0 else 'unavailable'}")
    return 0 if ENGINE in sources and current.stdout.strip() == "xiapin" else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command", choices=("setup", "cleanup", "status", "wait_unlock", "_metadata")
    )
    args = parser.parse_args()
    if args.command == "_metadata":
        print(json.dumps(read_live_engine_metadata(), ensure_ascii=True))
        return 0
    try:
        return globals()[args.command]()
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"Xiapin {args.command} failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
