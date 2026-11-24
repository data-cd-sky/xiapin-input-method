#!/usr/bin/env bash
set -Eeuo pipefail
readonly project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd -- "$project_dir"

required=(AGENTS.md README.md CHANGELOG.md "RELEASE_NOTES_$(<VERSION).md" LICENSE VERSION
 CMakeLists.txt src/engine_core.h src/engine_core.cpp src/emoji_index.h
 src/emoji_index.cpp src/ibus_engine.cpp
 src/history_tool.cpp
 ibus/xiapin.xml libexec/ibusctl.py libexec/memoryctl.py
 systemd/xiapin-bootstrap.service systemd/xiapin-unlock.service
 desktop/xiapin-ibus-autostart.desktop
 data/base.tsv data/hotwords.tsv data/xiapin-extra.libime-1.0.dict data/SOURCES.md
 icons/xiapin.svg scripts/build-dictionary.sh scripts/build-deb.sh
 scripts/legacy-fcitx-cleanup.sh scripts/doctor.sh docs/ubuntu-cn-input-memory.1
 docs/ubuntu-cn-input-doctor.1 docs/RELEASE_ACCEPTANCE.md docs/DEVELOPMENT.md
 debian/control debian/binary-control debian/rules debian/changelog
 debian/xiapin-input-method.postinst debian/xiapin-input-method.prerm
 debian/xiapin-input-method.postrm debian/xiapin-input-method.preinst
 debian/xiapin-input-method.maintscript
 tests/native-engine-core-test.cpp tests/emoji-index-test.cpp
 tests/test-native-engine.sh tests/test_ibusctl.py tests/test-ubuntu-dependencies.sh)
for path in "${required[@]}"; do
    [[ -s "$path" ]] || { echo "Missing or empty: $path" >&2; exit 1; }
done

version=$(tr -d '[:space:]' <VERSION)
[[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]
grep -qx "Version: $version" debian/binary-control
grep -q "^xiapin-input-method ($version)" debian/changelog

awk -F '\t' '
 /^#/ || NF == 0 { next }
 NF != 2 { exit 1 }
 $1 !~ /^[a-z\047]+$/ { exit 1 }
 seen[$1 SUBSEP $2]++ { exit 1 }
' data/base.tsv data/hotwords.tsv

grep -q '<name>org.freedesktop.IBus.Xiapin</name>' ibus/xiapin.xml
grep -q '<name>xiapin</name>' ibus/xiapin.xml
grep -q '<longname>瞎拼输入法</longname>' ibus/xiapin.xml
grep -q 'ibus_factory_add_engine(factory, "xiapin"' src/ibus_engine.cpp
grep -q 'IBUS_ORIENTATION_HORIZONTAL' src/ibus_engine.cpp
grep -q 'IBUS_INPUT_PURPOSE_PASSWORD' src/ibus_engine.cpp
grep -q 'IBUS_INPUT_HINT_PRIVATE' src/ibus_engine.cpp
grep -qx 'ExecStart=/usr/libexec/xiapin/ibusctl.py setup' systemd/xiapin-bootstrap.service
grep -qx 'ExecStop=/usr/libexec/xiapin/ibusctl.py cleanup' systemd/xiapin-bootstrap.service
grep -qx 'WantedBy=graphical-session.target' systemd/xiapin-bootstrap.service
grep -qx 'ExecStart=/usr/libexec/xiapin/ibusctl.py wait_unlock' systemd/xiapin-unlock.service
grep -qx 'Exec=/usr/libexec/xiapin/ibusctl.py setup' desktop/xiapin-ibus-autostart.desktop
grep -qx 'Architecture: amd64' debian/control
grep -q '^Depends:.*ibus' debian/control
grep -q 'ibus-data' debian/control
grep -q 'fonts-noto-color-emoji' debian/control
grep -q '/usr/share/ibus/dicts/emoji-zh.dict' scripts/doctor.sh
grep -q "fc-match 'Noto Color Emoji'" scripts/doctor.sh
grep -q 'expected_metadata=' scripts/doctor.sh
grep -q "ibus-engine-xiapin --ibus\\\$" scripts/doctor.sh
grep -q 'libimepinyin-dev' debian/control
! grep -Eq 'fcitx5($|[ ,(])|fcitx5-frontend|fcitx5-pinyin' debian/control debian/binary-control
! grep -Eq 'ibus-daemon.*--replace|ibus exit' libexec/ibusctl.py src/ibus_engine.cpp
grep -q 'refresh_stale_ibus_metadata' libexec/ibusctl.py
grep -q 'aria-label="瞎拼输入法像素墨镜标志"' icons/xiapin.svg
grep -q '<symbol>😎</symbol>' ibus/xiapin.xml
grep -q '冷缓存直接安装' docs/RELEASE_ACCEPTANCE.md
grep -q '不要写死 doctor 的 OK 数量' docs/RELEASE_ACCEPTANCE.md
grep -q '临时.*--register' docs/RELEASE_ACCEPTANCE.md
grep -q '安装前后学习数据逐文件 SHA-256' docs/RELEASE_ACCEPTANCE.md
grep -q 'uptime' docs/RELEASE_ACCEPTANCE.md
grep -q 'idle-space=1' docs/RELEASE_ACCEPTANCE.md
grep -q 'idle-passthrough=1' docs/RELEASE_ACCEPTANCE.md
grep -q 'engine->core->empty()' src/ibus_engine.cpp

for obsolete in libexec/bootstrap.sh libexec/configctl.py libexec/sessionctl.sh \
 libexec/settings-launcher.sh scripts/install.sh scripts/setup.sh scripts/uninstall.sh \
 desktop/xiapin-input-method-autostart.desktop desktop/xiapin-input-method.desktop \
 systemd/ubuntu-cn-input-bootstrap.service templates themes LOCAL_WORKSPACE.md; do
    [[ ! -e "$obsolete" ]] || { echo "Obsolete 1.x path remains: $obsolete" >&2; exit 1; }
done

machine_home_pattern='(^|[[:space:]`(])/'"home/"'[[:alnum:]_.-]+'
if rg -n "$machine_home_pattern" . \
 --glob '!build/**' --glob '!dist/**' --glob '!.git/**'; then
    echo 'Machine-specific path found in releaseable source' >&2
    exit 1
fi

if find . -path './build' -prune -o -path './dist' -prune -o \
 -type f \( -name '*.ucimem' -o -name 'user.dict' -o -name 'user.history' \
 -o -name '*.qcow2' -o -name '*.iso' \) -print -quit | grep -q .; then
    echo 'Personal memory or virtual-machine image found in releaseable source' >&2
    exit 1
fi

private_key_pattern='BEGIN (RSA |OPENSSH |EC )?'"PRIVATE KEY"
if rg -n "$private_key_pattern" . \
 --glob '!build/**' --glob '!dist/**' --glob '!.git/**'; then
    echo 'Private key material found in releaseable source' >&2
    exit 1
fi

email_pattern='[[:alnum:]_.+-]+@[[:alnum:].-]+\.[[:alpha:]]{2,}'
if rg -n -o "$email_pattern" . --glob '!build/**' --glob '!dist/**' \
 --glob '!.git/**' | grep -Ev '@(example\.org|example\.invalid)$'; then
    echo 'Non-placeholder email address found in releaseable source' >&2
    exit 1
fi
if command -v shellcheck >/dev/null 2>&1; then
    # SC2016: the integration tests deliberately defer variables to an inner
    # shell. SC2155 is the project's readonly initialization style. SC2251 is
    # used for negative test assertions whose status is checked by set -e.
    shopt -s nullglob
    shell_files=(scripts/*.sh libexec/*.sh tests/*.sh)
    shellcheck --exclude=SC2016,SC2155,SC2251 "${shell_files[@]}"
fi
