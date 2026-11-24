#!/usr/bin/env bash
set -Eeuo pipefail
readonly project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
readonly version="$(tr -d '[:space:]' <"$project_dir/VERSION")"
readonly package="$project_dir/dist/xiapin-input-method_${version}_amd64.deb"
[[ -s "$package" ]] || { echo "Missing package: $package" >&2; exit 1; }

[[ $(dpkg-deb -f "$package" Package) == xiapin-input-method ]]
[[ $(dpkg-deb -f "$package" Version) == "$version" ]]
[[ $(dpkg-deb -f "$package" Architecture) == amd64 ]]
depends=",$(dpkg-deb -f "$package" Depends | tr -d ' '),"
for dependency in ibus ibus-gtk ibus-gtk3 ibus-gtk4 im-config libime-bin \
 ibus-data libime-data libime-data-language-model libimecore0 libimepinyin0 \
 libibus-1.0-5 libfcitx5utils2 python3 python3-gi gir1.2-glib-2.0 \
 gir1.2-ibus-1.0 fonts-noto-cjk fonts-noto-color-emoji systemd \
 init-system-helpers dbus-bin; do
    [[ "$depends" == *",$dependency,"* || "$depends" == *",$dependency("* ]] || {
        echo "Missing dependency: $dependency" >&2; exit 1;
    }
done
[[ "$depends" != *",fcitx5,"* ]]

root=$(mktemp -d)
trap 'rm -rf -- "$root"' EXIT
dpkg-deb --extract "$package" "$root"
required=(usr/libexec/ibus-engine-xiapin usr/libexec/xiapin/ibusctl.py
 usr/libexec/xiapin/xiapin-history
 usr/libexec/xiapin/legacy-fcitx-cleanup usr/libexec/xiapin/legacy-profilectl.py
 usr/bin/ubuntu-cn-input-memory usr/bin/ubuntu-cn-input-doctor
 usr/share/man/man1/ubuntu-cn-input-memory.1.gz
 usr/share/man/man1/ubuntu-cn-input-doctor.1.gz
 usr/lib/systemd/user/xiapin-bootstrap.service
 usr/lib/systemd/user/xiapin-unlock.service usr/share/ibus/component/xiapin.xml
 usr/share/xiapin/xiapin.xml usr/share/xiapin/xiapin-extra.dict
 usr/share/icons/hicolor/scalable/apps/xiapin.svg
 etc/xdg/autostart/xiapin-ibus-autostart.desktop)
for path in "${required[@]}"; do
    [[ -s "$root/$path" ]] || { echo "Missing from deb: $path" >&2; exit 1; }
done

file "$root/usr/libexec/ibus-engine-xiapin" | grep -q 'ELF 64-bit.*x86-64'
ldd "$root/usr/libexec/ibus-engine-xiapin" | grep -q 'libIMEPinyin.so.0'
ldd "$root/usr/libexec/ibus-engine-xiapin" | grep -q 'libibus-1.0.so.5'
ldd "$root/usr/libexec/xiapin/xiapin-history" | grep -q 'libIMECore.so.0'
grep -q '<name>xiapin</name>' "$root/usr/share/ibus/component/xiapin.xml"
grep -q '<symbol>😎</symbol>' "$root/usr/share/ibus/component/xiapin.xml"
grep -qx 'ExecStart=/usr/libexec/xiapin/ibusctl.py setup' \
 "$root/usr/lib/systemd/user/xiapin-bootstrap.service"
grep -qx 'ExecStart=/usr/libexec/xiapin/ibusctl.py wait_unlock' \
 "$root/usr/lib/systemd/user/xiapin-unlock.service"
grep -qx 'Exec=/usr/libexec/xiapin/ibusctl.py setup' \
 "$root/etc/xdg/autostart/xiapin-ibus-autostart.desktop"
[[ ! -e "$root/etc/xdg/autostart/xiapin-input-method-autostart.desktop" ]]
! find "$root" -path '*/fcitx5/*' -print -quit | grep -q .
! rg -q 'ibus-daemon.*--replace|ibus exit' \
 "$root/usr/libexec/xiapin/ibusctl.py"
grep -q 'refresh_stale_ibus_metadata' "$root/usr/libexec/xiapin/ibusctl.py"

control="$root/control"
dpkg-deb --control "$package" "$control"
grep -q 'rm_conffile' "$control/preinst"
grep -q 'xiapin-input-method-autostart.desktop' "$control/preinst"
grep -q 'enable xiapin-bootstrap.service' "$control/postinst"
grep -q 'restart xiapin-bootstrap.service' "$control/postinst"
grep -q 'machine=.*daemon-reload' "$control/postinst"
grep -q 'ubuntu-cn-input-doctor' "$control/postinst"
grep -q 'stop xiapin-bootstrap.service' "$control/prerm"
grep -q 'stop xiapin-unlock.service' "$control/prerm"
grep -q 'purge xiapin-bootstrap.service' "$control/postrm"

if rg -a -n '(^|[[:space:]`(])/home/[^ /`)]+' "$root"; then
    echo 'Machine-specific path found in .deb' >&2
    exit 1
fi
if command -v lintian >/dev/null 2>&1; then
    lintian --fail-on error "$package"
else
    echo 'SKIP: lintian is not installed' >&2
fi
