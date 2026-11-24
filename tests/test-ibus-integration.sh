#!/usr/bin/env bash
set -Eeuo pipefail
readonly project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
readonly root="${TMPDIR:-/tmp}/xiapin-ibus-integration-$$"
cleanup_test() {
    if [[ ${XIAPIN_KEEP_TEST:-false} == true ]]; then
        printf 'Preserved IBus test directory: %s\n' "$root" >&2
    else
        rm -rf -- "$root"
    fi
}
trap cleanup_test EXIT
mkdir -p "$root/data" "$root/home" "$root/config" "$root/cache" "$root/runtime"
chmod 0700 "$root/runtime"

# Always run the incremental build. Checking only whether the executable exists
# can run a stale Engine after a source edit and turn both failures and passes
# into false evidence.
make -C "$project_dir" build
"$project_dir/build/native/ibus-engine-xiapin" --invalid \
    >"$root/invalid.out" 2>"$root/invalid.err" && exit 1
grep -q -- '--ibus|--register' "$root/invalid.err"
install -m 0644 "$project_dir/data/xiapin-extra.libime-1.0.dict" \
    "$root/data/xiapin-extra.dict"
apply_wrapper="$root/data/start-xiapin"
sed "s|@ENGINE@|$project_dir/build/native/ibus-engine-xiapin|g; s|@LOG@|$root/static-cache/engine-start.log|g" \
    >"$apply_wrapper" <<'EOF'
#!/usr/bin/env bash
printf 'argv:' >>'@LOG@'
printf ' <%s>' "$@" >>'@LOG@'
printf '\nIBUS_ADDRESS=%s\n' "${IBUS_ADDRESS:-}" >>'@LOG@'
exec '@ENGINE@' "$@" 2>>'@LOG@'
EOF
chmod 0755 "$apply_wrapper"
sed "s|<exec>[^<]*</exec>|<exec>$project_dir/build/native/ibus-engine-xiapin --ibus</exec>|" \
    "$project_dir/ibus/xiapin.xml" >"$root/data/xiapin.xml"

dbus-run-session -- env HOME="$root/home" XDG_CONFIG_HOME="$root/config" \
    XDG_CACHE_HOME="$root/cache" XDG_RUNTIME_DIR="$root/runtime" \
    XIAPIN_DATA_DIR="$root/data" IBUS_ADDRESS= \
    DISPLAY= WAYLAND_DISPLAY= \
    XDG_SESSION_TYPE=x11 bash -Eeuo pipefail -c '
        ibus-daemon --daemonize --single --panel=disable --config=disable --cache=none
        address_file=""
        for _ in {1..50}; do
            address_file=$(find "$XDG_CONFIG_HOME/ibus/bus" -type f -print -quit 2>/dev/null || true)
            [[ -n "$address_file" ]] && break
            sleep 0.1
        done
        [[ -n "$address_file" ]]
        IBUS_ADDRESS=$(sed -n "s/^IBUS_ADDRESS=//p" "$address_file")
        export IBUS_ADDRESS
        unset IBUS_USE_PORTAL
        env -u IBUS_USE_PORTAL "$1/build/native/ibus-engine-xiapin" --register \
            2>"$XDG_CACHE_HOME/engine.log" &
        engine_pid=$!
        trap "kill $engine_pid 2>/dev/null || true" EXIT
        for _ in {1..50}; do
            if ! kill -0 "$engine_pid" 2>/dev/null; then
                cat "$XDG_CACHE_HOME/engine.log" >&2
                echo "Xiapin registration process exited early" >&2
                exit 1
            fi
            if env -u IBUS_USE_PORTAL ibus engine xiapin \
                >"$XDG_CACHE_HOME/select.log" 2>&1; then
                break
            fi
            sleep 0.1
        done
        if [[ $(env -u IBUS_USE_PORTAL ibus engine 2>/dev/null) != xiapin ]]; then
            cat "$XDG_CACHE_HOME/engine.log" >&2
            cat "$XDG_CACHE_HOME/select.log" >&2 || true
            echo "Xiapin could not become the active IBus engine" >&2
            exit 1
        fi
        python3 "$1/tests/ibus-integration-client.py"
        ibus exit >/dev/null 2>&1 || true
    ' _ "$project_dir"

# Exercise the ordinary --ibus process path used after a fresh login. Starting
# components on demand itself requires a real graphical IBus session and is
# covered by the Ubuntu VM acceptance test; here the private daemon verifies
# that the static factory can own its standard name and serve input contexts.
mkdir -p "$root/static-home" "$root/static-config" "$root/static-cache" \
    "$root/static-runtime"
chmod 0700 "$root/static-runtime"
sed -i "s|<exec>[^<]*</exec>|<exec>$apply_wrapper --ibus</exec>|" "$root/data/xiapin.xml"
dbus-run-session -- env HOME="$root/static-home" \
    XDG_CONFIG_HOME="$root/static-config" XDG_CACHE_HOME="$root/static-cache" \
    XDG_RUNTIME_DIR="$root/static-runtime" XIAPIN_DATA_DIR="$root/data" \
    IBUS_COMPONENT_PATH="$root/data" \
    IBUS_ADDRESS="unix:path=$root/static-runtime/ibus.sock" \
    DISPLAY= WAYLAND_DISPLAY= XDG_SESSION_TYPE=x11 \
    env -u IBUS_USE_PORTAL bash -Eeuo pipefail -c '
        unset IBUS_USE_PORTAL
        ibus-daemon --daemonize --single --panel=disable --config=disable \
            --cache=none --address="$IBUS_ADDRESS"
        for _ in {1..50}; do
            env -u IBUS_USE_PORTAL ibus list-engine >/dev/null 2>&1 && break
            sleep 0.1
        done
        discovered=false
        for _ in {1..50}; do
            if env -u IBUS_USE_PORTAL ibus list-engine 2>/dev/null | grep -q xiapin; then
                discovered=true
                break
            fi
            sleep 0.1
        done
        [[ "$discovered" == true ]]
        "$2/data/start-xiapin" --ibus &
        engine_pid=$!
        trap "kill $engine_pid 2>/dev/null || true" EXIT
        for _ in {1..50}; do
            if env -u IBUS_USE_PORTAL ibus engine xiapin >/dev/null 2>&1; then
                break
            fi
            sleep 0.1
        done
        [[ $(env -u IBUS_USE_PORTAL ibus engine 2>/dev/null) == xiapin ]] || {
            cat "$XDG_CACHE_HOME/engine-start.log" >&2 || true
            cat "$XDG_CACHE_HOME/ibus-daemon.log" >&2 || true
            exit 1
        }
        python3 "$1/tests/ibus-integration-client.py"
        kill "$engine_pid"
        wait "$engine_pid" 2>/dev/null || true
        ibus exit >/dev/null 2>&1 || true
    ' _ "$project_dir" "$root"
