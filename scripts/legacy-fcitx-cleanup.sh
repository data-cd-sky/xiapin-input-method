#!/usr/bin/env bash
set -Eeuo pipefail

state_home="${XDG_STATE_HOME:-$HOME/.local/state}"
profile="${XDG_CONFIG_HOME:-$HOME/.config}/fcitx5/profile"
profilectl="${UBUNTU_CN_INPUT_PROFILECTL:-/usr/libexec/xiapin/legacy-profilectl.py}"
config_home="${XDG_CONFIG_HOME:-$HOME/.config}"
global_config="$config_home/fcitx5/config"
pinyin_config="$config_home/fcitx5/conf/pinyin.conf"
classicui_config="$config_home/fcitx5/conf/classicui.conf"
notifications_config="$config_home/fcitx5/conf/notifications.conf"
original_global_config_pointer="$state_home/ubuntu-cn-input/original-global-config-backup"
applied_global_config_hash="$state_home/ubuntu-cn-input/applied-global-config.sha256"
original_pinyin_pointer="$state_home/ubuntu-cn-input/original-pinyin-backup"
applied_pinyin_hash="$state_home/ubuntu-cn-input/applied-pinyin.sha256"
original_classicui_pointer="$state_home/ubuntu-cn-input/original-classicui-backup"
applied_classicui_hash="$state_home/ubuntu-cn-input/applied-classicui.sha256"
original_notifications_pointer="$state_home/ubuntu-cn-input/original-notifications-backup"
applied_notifications_hash="$state_home/ubuntu-cn-input/applied-notifications.sha256"
gnomerc="$HOME/.gnomerc"
original_gnomerc_pointer="$state_home/ubuntu-cn-input/original-gnomerc-backup"
applied_gnomerc_hash="$state_home/ubuntu-cn-input/applied-gnomerc.sha256"
xinputrc="${UBUNTU_CN_INPUT_XINPUTRC:-$HOME/.xinputrc}"
original_xinputrc_pointer="$state_home/ubuntu-cn-input/original-xinputrc-backup"
applied_xinputrc_hash="$state_home/ubuntu-cn-input/applied-xinputrc.sha256"
systemd_user_home="$config_home/systemd/user"
ibus_unit="org.freedesktop.IBus.session.GNOME.service"
ibus_user_unit="$systemd_user_home/$ibus_unit"
original_ibus_pointer="$state_home/ubuntu-cn-input/original-ibus-unit-backup"

[[ $# -eq 0 ]] || {
    echo "Usage: legacy-fcitx-cleanup" >&2
    exit 2
}

if [[ -x "$profilectl" && -f "$profile" ]]; then
    umask 077
    mkdir -p "$state_home/ubuntu-cn-input/backups"
    backup=$(mktemp "$state_home/ubuntu-cn-input/backups/profile-before-cleanup.XXXXXX")
    install -m 0600 "$profile" "$backup"
    "$profilectl" remove "$profile" --name xiapin
    "$profilectl" remove "$profile" --name stable-pinyin
    echo "Profile backup: $backup"
fi

if [[ -r "$original_classicui_pointer" && -r "$applied_classicui_hash" &&
      -f "$classicui_config" ]]; then
    read -r original_backup <"$original_classicui_pointer"
    read -r expected_hash <"$applied_classicui_hash"
    current_hash=$(sha256sum "$classicui_config" | awk '{print $1}')
    case "$original_backup" in
        "$state_home"/ubuntu-cn-input/backups/setup-*)
            if [[ "$current_hash" == "$expected_hash" ]]; then
                if [[ -f "$original_backup/classicui.conf" ]]; then
                    install -m 0600 "$original_backup/classicui.conf" "$classicui_config"
                elif [[ -f "$original_backup/classicui.conf.absent" ]]; then
                    rm -f -- "$classicui_config"
                fi
                rm -f -- "$original_classicui_pointer" "$applied_classicui_hash"
                echo "Restored the pre-Xiapin Classic UI configuration."
            else
                echo "Kept classicui.conf because it changed after Xiapin setup."
            fi
            ;;
        *) echo "Ignored unsafe Classic UI backup pointer." >&2 ;;
    esac
fi
if [[ -r "$original_global_config_pointer" && -r "$applied_global_config_hash" &&
      -f "$global_config" ]]; then
    read -r original_backup <"$original_global_config_pointer"
    read -r expected_hash <"$applied_global_config_hash"
    current_hash=$(sha256sum "$global_config" | awk '{print $1}')
    case "$original_backup" in
        "$state_home"/ubuntu-cn-input/backups/setup-*)
            if [[ "$current_hash" == "$expected_hash" ]]; then
                if [[ -f "$original_backup/config" ]]; then
                    install -m 0600 "$original_backup/config" "$global_config"
                elif [[ -f "$original_backup/config.absent" ]]; then
                    rm -f -- "$global_config"
                fi
                rm -f -- "$original_global_config_pointer" "$applied_global_config_hash"
                echo "Restored the pre-Xiapin Fcitx global configuration."
            else
                echo "Kept the Fcitx global config because it changed after Xiapin setup."
            fi
            ;;
        *) echo "Ignored unsafe Fcitx global config backup pointer." >&2 ;;
    esac
fi
if [[ -r "$original_notifications_pointer" && -r "$applied_notifications_hash" &&
      -f "$notifications_config" ]]; then
    read -r original_backup <"$original_notifications_pointer"
    read -r expected_hash <"$applied_notifications_hash"
    current_hash=$(sha256sum "$notifications_config" | awk '{print $1}')
    case "$original_backup" in
        "$state_home"/ubuntu-cn-input/backups/setup-*)
            if [[ "$current_hash" == "$expected_hash" ]]; then
                if [[ -f "$original_backup/notifications.conf" ]]; then
                    install -m 0600 "$original_backup/notifications.conf" "$notifications_config"
                elif [[ -f "$original_backup/notifications.conf.absent" ]]; then
                    rm -f -- "$notifications_config"
                fi
                rm -f -- "$original_notifications_pointer" "$applied_notifications_hash"
                echo "Restored the pre-Xiapin notification configuration."
            else
                echo "Kept notifications.conf because it changed after Xiapin setup."
            fi
            ;;
        *) echo "Ignored unsafe notification backup pointer." >&2 ;;
    esac
fi
if command -v systemctl >/dev/null 2>&1; then
    systemctl --user disable --now ubuntu-cn-input-watchdog.timer \
        ubuntu-cn-input-watchdog.service ubuntu-cn-input.service 2>/dev/null || true
fi

# Xiapin is an input-method entry for Fcitx's native pinyin addon, so its
# required cursor/privacy settings live in the addon's shared pinyin.conf.
# Restore the pre-Xiapin file only when the user has not edited it since setup.
if [[ -r "$original_pinyin_pointer" && -r "$applied_pinyin_hash" &&
      -f "$pinyin_config" ]]; then
    read -r original_backup <"$original_pinyin_pointer"
    read -r expected_hash <"$applied_pinyin_hash"
    current_hash=$(sha256sum "$pinyin_config" | awk '{print $1}')
    case "$original_backup" in
        "$state_home"/ubuntu-cn-input/backups/setup-*)
            if [[ "$current_hash" == "$expected_hash" ]]; then
                if [[ -f "$original_backup/pinyin.conf" ]]; then
                    install -m 0600 "$original_backup/pinyin.conf" "$pinyin_config"
                elif [[ -f "$original_backup/pinyin.conf.absent" ]]; then
                    rm -f -- "$pinyin_config"
                fi
                rm -f -- "$original_pinyin_pointer" "$applied_pinyin_hash"
                echo "Restored the pre-Xiapin native pinyin configuration."
            else
                echo "Kept pinyin.conf because it changed after Xiapin setup."
            fi
            ;;
        *) echo "Ignored unsafe original pinyin backup pointer." >&2 ;;
    esac
fi

# Restore the pre-Xiapin GNOME/Wayland environment only when the managed file
# has not been edited since setup. This avoids overwriting unrelated changes.
if [[ -r "$original_gnomerc_pointer" && -r "$applied_gnomerc_hash" &&
      -f "$gnomerc" ]]; then
    read -r original_backup <"$original_gnomerc_pointer"
    read -r expected_hash <"$applied_gnomerc_hash"
    current_hash=$(sha256sum "$gnomerc" | awk '{print $1}')
    case "$original_backup" in
        "$state_home"/ubuntu-cn-input/backups/setup-*)
            if [[ "$current_hash" == "$expected_hash" ]]; then
                if [[ -f "$original_backup/gnomerc" ]]; then
                    install -m 0600 "$original_backup/gnomerc" "$gnomerc"
                elif [[ -f "$original_backup/gnomerc.absent" ]]; then
                    rm -f -- "$gnomerc"
                fi
                rm -f -- "$original_gnomerc_pointer" "$applied_gnomerc_hash"
                echo "Restored the pre-Xiapin GNOME input-method environment."
            else
                echo "Kept .gnomerc because it changed after Xiapin setup."
            fi
            ;;
        *) echo "Ignored unsafe original GNOME environment backup pointer." >&2 ;;
    esac
fi

if [[ -r "$original_xinputrc_pointer" && -r "$applied_xinputrc_hash" &&
      -f "$xinputrc" ]]; then
    read -r original_backup <"$original_xinputrc_pointer"
    read -r expected_hash <"$applied_xinputrc_hash"
    current_hash=$(sha256sum "$xinputrc" | awk '{print $1}')
    case "$original_backup" in
        "$state_home"/ubuntu-cn-input/backups/setup-*)
            if [[ "$current_hash" == "$expected_hash" ]]; then
                if [[ -e "$original_backup/xinputrc" || -L "$original_backup/xinputrc" ]]; then
                    rm -f -- "$xinputrc"
                    cp -a -- "$original_backup/xinputrc" "$xinputrc"
                elif [[ -f "$original_backup/xinputrc.absent" ]]; then
                    rm -f -- "$xinputrc"
                fi
                rm -f -- "$original_xinputrc_pointer" "$applied_xinputrc_hash"
                echo "Restored the pre-Xiapin im-config selection."
            else
                echo "Kept .xinputrc because it changed after Xiapin setup."
            fi
            ;;
        *) echo "Ignored unsafe im-config backup pointer." >&2 ;;
    esac
fi

# Remove only the exact mask installed by setup. A later user override is left
# untouched. Restore a pre-existing per-user unit when one was backed up.
if [[ -r "$original_ibus_pointer" ]]; then
    read -r original_backup <"$original_ibus_pointer"
    case "$original_backup" in
        "$state_home"/ubuntu-cn-input/backups/setup-*)
            if [[ -L "$ibus_user_unit" && $(readlink -- "$ibus_user_unit") == /dev/null ]]; then
                rm -f -- "$ibus_user_unit"
                if [[ -e "$original_backup/systemd-user/$ibus_unit" ||
                      -L "$original_backup/systemd-user/$ibus_unit" ]]; then
                    mkdir -p -- "$systemd_user_home"
                    cp -a -- "$original_backup/systemd-user/$ibus_unit" "$ibus_user_unit"
                fi
                rm -f -- "$original_ibus_pointer"
                echo "Restored the pre-Xiapin IBus user-service state."
            else
                echo "Kept the IBus user-service override because it changed after setup."
            fi
            ;;
        *) echo "Ignored unsafe IBus unit backup pointer." >&2 ;;
    esac
fi
if command -v systemctl >/dev/null 2>&1; then
    systemctl --user daemon-reload 2>/dev/null || true
fi
echo "Xiapin 1.x managed configuration restored; legacy learning data retained."
