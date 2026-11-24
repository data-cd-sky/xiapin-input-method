#!/usr/bin/env bash
set -Eeuo pipefail

readonly project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
root=$(mktemp -d)
trap 'rm -rf -- "$root"' EXIT
mkdir -p "$root/bin"

cat >"$root/bin/deb-systemd-helper" <<'EOF'
#!/bin/sh
printf 'helper %s\n' "$*" >>"$TEST_MAINTAINER_LOG"
exit 0
EOF
cat >"$root/bin/deb-systemd-invoke" <<'EOF'
#!/bin/sh
printf 'invoke %s\n' "$*" >>"$TEST_MAINTAINER_LOG"
exit 0
EOF
cat >"$root/bin/systemctl" <<'EOF'
#!/bin/sh
printf 'systemctl %s\n' "$*" >>"$TEST_MAINTAINER_LOG"
if [ "$1" = --no-legend ]; then
    printf 'user%s1000.service loaded active running User Manager for UID 1000\n' '@'
fi
exit 0
EOF
cat >"$root/bin/update-desktop-database" <<'EOF'
#!/bin/sh
printf 'desktop %s\n' "$*" >>"$TEST_MAINTAINER_LOG"
EOF
cat >"$root/bin/gtk-update-icon-cache" <<'EOF'
#!/bin/sh
printf 'icon %s\n' "$*" >>"$TEST_MAINTAINER_LOG"
EOF
chmod 0755 "$root/bin/"*
export PATH="$root/bin:/usr/bin:/bin"
export TEST_MAINTAINER_LOG="$root/log"

postinst_output=$("$project_dir/debian/xiapin-input-method.postinst" configure 1.0.0)
grep -q 'ubuntu-cn-input-doctor' <<<"$postinst_output"
grep -q '^invoke --user stop ubuntu-cn-input-watchdog.timer ubuntu-cn-input-watchdog.service$' \
    "$root/log"
grep -q '^helper --user purge ubuntu-cn-input-watchdog.timer ubuntu-cn-input-watchdog.service$' \
    "$root/log"
grep -q '^invoke --user stop ubuntu-cn-input.service$' "$root/log"
grep -q '^helper --user purge ubuntu-cn-input.service$' "$root/log"
grep -q '^helper --user purge ubuntu-cn-input-bootstrap.service$' "$root/log"
grep -q '^invoke --user stop xiapin-bootstrap.service$' "$root/log"
grep -q '^helper --user unmask xiapin-bootstrap.service$' "$root/log"
grep -q '^helper --user purge xiapin-bootstrap.service$' "$root/log"
grep -q '^helper --user enable xiapin-bootstrap.service$' "$root/log"
! grep -q 'was-enabled\|update-state' "$root/log"
grep -q '^systemctl --no-legend --quiet list-units user@\*\.service$' "$root/log"
grep -q '^systemctl --quiet --user --machine=1000@ daemon-reload$' "$root/log"
grep -q '^invoke --user restart xiapin-bootstrap.service$' "$root/log"
reload_line=$(grep -n '^systemctl --quiet --user --machine=1000@ daemon-reload$' "$root/log" | cut -d: -f1)
restart_line=$(grep -n '^invoke --user restart xiapin-bootstrap.service$' "$root/log" | cut -d: -f1)
((reload_line < restart_line))
grep -q '^desktop -q /usr/share/applications$' "$root/log"
grep -q '^icon -q -t -f /usr/share/icons/hicolor$' "$root/log"

"$project_dir/debian/xiapin-input-method.prerm" remove 1.0.1
grep -q '^invoke --user stop xiapin-unlock.service$' "$root/log"
grep -q '^invoke --user stop xiapin-bootstrap.service$' "$root/log"
grep -q '^helper --user disable xiapin-bootstrap.service$' "$root/log"

"$project_dir/debian/xiapin-input-method.postrm" purge
grep -q '^helper --user purge xiapin-bootstrap.service$' "$root/log"

# Staged/chroot installs must not contact or mutate host user managers.
: >"$root/log"
DPKG_ROOT="$root/staging" \
    "$project_dir/debian/xiapin-input-method.postinst" configure 1.0.0
! grep -q '^helper\|^invoke\|^systemctl' "$root/log"
