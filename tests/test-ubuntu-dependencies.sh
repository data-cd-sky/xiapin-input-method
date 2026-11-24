#!/usr/bin/env bash
set -Eeuo pipefail

readonly project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
readonly package="$project_dir/dist/xiapin-input-method_$(tr -d '[:space:]' <"$project_dir/VERSION")_amd64.deb"

[[ -s "$package" ]] || { echo "Missing package: $package" >&2; exit 1; }
command -v apt-get >/dev/null 2>&1 || { echo "SKIP: apt-get is unavailable" >&2; exit 0; }

test_root=$(mktemp -d)
trap 'rm -rf -- "$test_root"' EXIT

for release in jammy noble; do
    root="$test_root/$release"
    mkdir -p "$root/lists/partial" "$root/cache/archives/partial" "$root/etc/apt"
    : >"$root/status"
    printf '%s\n' \
        "deb [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] https://archive.ubuntu.com/ubuntu $release main universe" \
        >"$root/etc/apt/sources.list"

    common_options=(
        -o "Dir::Etc::sourcelist=$root/etc/apt/sources.list"
        -o Dir::Etc::sourceparts=-
        -o "Dir::State::lists=$root/lists"
        -o "Dir::State::status=$root/status"
        -o "Dir::Cache=$root/cache"
        -o APT::Architecture=amd64
        -o Acquire::Languages=none
        -o APT::Get::List-Cleanup=0
    )
    apt-get "${common_options[@]}" update >/dev/null
    output=$(apt-get "${common_options[@]}" --simulate --no-install-recommends \
        install "$package" 2>&1) || {
        printf '%s\n' "$output" >&2
        echo "Ubuntu $release cannot resolve the package dependencies" >&2
        exit 1
    }
    grep -q '^Inst xiapin-input-method ' <<<"$output"
    if grep -q '^E:' <<<"$output"; then
        printf '%s\n' "$output" >&2
        exit 1
    fi
    default_output=$(apt-get "${common_options[@]}" --simulate \
        install "$package" 2>&1) || {
        printf '%s\n' "$default_output" >&2
        echo "Ubuntu $release cannot resolve the default APT installation" >&2
        exit 1
    }
    grep -q '^Inst xiapin-input-method ' <<<"$default_output"
    ! grep -q '^Inst fcitx5 ' <<<"$default_output"
    printf 'Ubuntu %s: all runtime dependencies resolve\n' "$release"
done
