#!/usr/bin/env bash
set -uo pipefail

readonly release_version="2.0.4"

if [[ ${1:-} == --version ]]; then
    printf '瞎拼输入法 %s\n' "$release_version"
    exit 0
fi
if (($#)); then
    echo "Usage: ubuntu-cn-input-doctor [--version]" >&2
    exit 2
fi

printf '瞎拼输入法 %s 诊断\n\n' "$release_version"
ok=0
warnings=0
failures=0
pass() { printf '[ OK ] %s\n' "$*"; ((ok += 1)); }
warn() { printf '[WARN] %s\n' "$*"; ((warnings += 1)); }
fail() { printf '[FAIL] %s\n' "$*"; ((failures += 1)); }

if [[ -r /etc/os-release ]]; then
    # shellcheck disable=SC1091
    source /etc/os-release
    case "${VERSION_ID:-}" in
        22.04|24.04|26.04) pass "Ubuntu ${VERSION_ID} is supported" ;;
        *) warn "Ubuntu ${VERSION_ID:-unknown} is outside the tested matrix" ;;
    esac
else
    warn "Cannot identify the operating system"
fi

if dpkg-query -W -f='${db:Status-Abbrev} ${Version} ${Architecture}\n' \
    xiapin-input-method 2>/dev/null | grep -Fqx "ii  $release_version amd64"; then
    pass "xiapin-input-method $release_version amd64 is installed"
else
    fail "xiapin-input-method $release_version amd64 is not fully installed"
fi

for path in /usr/libexec/ibus-engine-xiapin \
    /usr/libexec/xiapin/xiapin-history \
    /usr/libexec/xiapin/ibusctl.py \
    /usr/share/ibus/component/xiapin.xml \
    /usr/share/xiapin/xiapin-extra.dict \
    /usr/share/ibus/dicts/emoji-zh.dict \
    /usr/share/libime/sc.dict; do
    if [[ -r "$path" ]]; then
        pass "$path is present"
    else
        fail "$path is missing"
    fi
done

for command in ibus libime_pinyindict python3 gsettings; do
    if command -v "$command" >/dev/null 2>&1; then
        pass "$command is available"
    else
        fail "$command is missing"
    fi
done

if locale charmap 2>/dev/null | grep -qi '^UTF-8$'; then
    pass "terminal locale uses UTF-8"
else
    warn "terminal locale is not UTF-8"
fi
if fc-match 'Noto Sans CJK SC' 2>/dev/null | grep -qi 'Noto.*CJK'; then
    pass "Noto CJK font is available"
else
    warn "Noto CJK font lookup failed"
fi
if fc-match 'Noto Color Emoji' 2>/dev/null | grep -qi 'Noto.*Emoji'; then
    pass "Noto Color Emoji font is available"
else
    fail "Noto Color Emoji font lookup failed"
fi

if systemctl --user is-enabled xiapin-bootstrap.service >/dev/null 2>&1; then
    pass "xiapin-bootstrap.service is enabled"
else
    fail "xiapin-bootstrap.service is not enabled"
fi
if systemctl --user is-active xiapin-bootstrap.service >/dev/null 2>&1; then
    pass "xiapin-bootstrap.service is active"
else
    warn "xiapin-bootstrap.service is not active in this shell's user session"
fi

if gsettings get org.gnome.desktop.input-sources sources 2>/dev/null |
    grep -Fq "('ibus', 'xiapin')"; then
    pass "GNOME contains the Xiapin input source"
else
    warn "GNOME does not expose Xiapin in this session"
fi
engine_metadata=$(python3 - <<'PY' 2>/dev/null || true
import gi
gi.require_version("IBus", "1.0")
from gi.repository import IBus
IBus.init()
bus = IBus.Bus.new()
if bus.is_connected():
    for engine in bus.list_engines():
        if engine.get_name() == "xiapin":
            print("\t".join((
                engine.get_longname(), engine.get_language(),
                engine.get_symbol(), engine.get_icon(),
            )))
            break
PY
)
expected_metadata=$'瞎拼输入法\tzh_CN\t😎\t/usr/share/icons/hicolor/scalable/apps/xiapin.svg'
if [[ "$engine_metadata" == "$expected_metadata" ]]; then
    pass "IBus exposes Xiapin as Simplified Chinese with current metadata"
elif [[ -n "$engine_metadata" ]]; then
    fail "the current IBus registry contains stale Xiapin metadata"
else
    fail "the current IBus registry does not contain Xiapin"
fi
if pgrep -af '^/usr/libexec/ibus-engine-xiapin --ibus$' \
    >/dev/null 2>&1; then
    pass "the static Xiapin Engine is running"
elif pgrep -af '^/usr/libexec/ibus-engine-xiapin --register$' \
    >/dev/null 2>&1; then
    fail "only a temporary Xiapin Engine is running"
else
    warn "the Engine is not running; IBus starts it when selected"
fi

memory_root="${XDG_DATA_HOME:-$HOME/.local/share}/xiapin"
for file in "$memory_root/user.dict" "$memory_root/user.history"; do
    [[ -e "$file" ]] || continue
    mode=$(stat -c '%a' "$file" 2>/dev/null || true)
    if [[ "$mode" == 600 ]]; then
        pass "${file##*/} has private permissions"
    else
        warn "${file##*/} has mode ${mode:-unknown}; expected 600"
    fi
done
if [[ ! -e "$memory_root/user.dict" && ! -e "$memory_root/user.history" ]]; then
    pass "learning data has not been created yet"
fi

ibus_override="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user/org.freedesktop.IBus.session.GNOME.service"
if [[ -L "$ibus_override" && $(readlink "$ibus_override") == /dev/null ]]; then
    fail "a user IBus service mask remains from an incomplete 1.x migration"
fi

printf '\nSummary: %d OK, %d warnings, %d failures\n' "$ok" "$warnings" "$failures"
((failures == 0))
