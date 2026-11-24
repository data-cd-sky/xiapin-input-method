#!/usr/bin/env bash
set -Eeuo pipefail

readonly project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
readonly bootstrap="$project_dir/systemd/xiapin-bootstrap.service"
readonly unlock="$project_dir/systemd/xiapin-unlock.service"

# Xiapin must not supervise, restart, or directly own the Fcitx main process.
[[ ! -e "$project_dir/systemd/ubuntu-cn-input.service" ]]
! rg -q 'RestartForceExitStatus|Restart=on-failure|ExecStart=/usr/bin/fcitx5' \
    "$project_dir/systemd"

grep -qx 'ExecStart=/usr/libexec/xiapin/ibusctl.py setup' "$bootstrap"
grep -qx 'ExecStop=/usr/libexec/xiapin/ibusctl.py cleanup' "$bootstrap"
grep -qx 'PartOf=graphical-session.target' "$bootstrap"
grep -qx 'WantedBy=graphical-session.target' "$bootstrap"
grep -qx 'ExecStart=/usr/libexec/xiapin/ibusctl.py wait_unlock' "$unlock"
grep -qx 'PartOf=graphical-session.target' "$unlock"
! grep -q '^Restart=' "$unlock"
[[ ! -e "$project_dir/systemd/ubuntu-cn-input-watchdog.timer" ]]
[[ ! -e "$project_dir/systemd/ubuntu-cn-input-watchdog.service" ]]

# Verify only the one-shot per-session IBus configuration unit.
if command -v systemd-analyze >/dev/null 2>&1; then
    verify_root=$(mktemp -d)
    trap 'rm -rf -- "$verify_root"' EXIT
    sed -e '/^ExecCondition=/d' \
        -e 's|^ExecStart=.*|ExecStart=/bin/true|' \
        -e 's|^ExecStop=.*|ExecStop=/bin/true|' \
        "$bootstrap" >"$verify_root/bootstrap.service"
    set +e
    verify_output=$(systemd-analyze --man=no --generators=no verify \
        "$verify_root/bootstrap.service" 2>&1)
    verify_status=$?
    set -e
    if ((verify_status != 0)); then
        unexpected=$(printf '%s\n' "$verify_output" | grep -Ev \
            '^(Failed to turn off SO_PASSRIGHTS|Failed to enable SO_PASSCRED|netplan-ovs-cleanup.service: Failed to open .*: Permission denied)' || true)
        if [[ -n "$unexpected" ]]; then
            printf '%s\n' "$verify_output" >&2
            exit "$verify_status"
        fi
        echo 'SKIP: systemd-analyze is restricted by this container' >&2
    fi
    sed -e 's|^ExecStart=.*|ExecStart=/bin/true|' \
        "$unlock" >"$verify_root/unlock.service"
    systemd-analyze --man=no --generators=no verify "$verify_root/unlock.service"
fi
