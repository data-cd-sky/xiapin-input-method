#!/usr/bin/env bash
set -Eeuo pipefail

readonly project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
readonly build_dir="${TMPDIR:-/tmp}/xiapin-native-build-$$"
readonly data_dir="$build_dir/user-data"
trap 'rm -rf -- "$build_dir"' EXIT

for dependency in cmake pkg-config; do
    if ! command -v "$dependency" >/dev/null 2>&1; then
        echo "SKIP: $dependency is unavailable" >&2
        exit 77
    fi
done
if ! pkg-config --exists ibus-1.0 ||
   [[ ! -f /usr/include/LibIME/libime/pinyin/pinyincontext.h ]]; then
    echo "SKIP: IBus/LibIME development files are unavailable" >&2
    exit 77
fi

cmake -S "$project_dir" -B "$build_dir" -G Ninja \
    -DCMAKE_BUILD_TYPE=RelWithDebInfo
cmake --build "$build_dir"
mkdir -p -- "$data_dir"
timeout --signal=KILL 30s "$build_dir/xiapin-core-test" \
    /usr/share/libime/sc.dict \
    "$project_dir/data/xiapin-extra.libime-1.0.dict" \
    /usr/lib/x86_64-linux-gnu/libime/zh_CN.lm \
    "$data_dir" \
    /usr/share/ibus/dicts/emoji-zh.dict
