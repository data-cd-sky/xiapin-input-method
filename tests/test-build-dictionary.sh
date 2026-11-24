#!/usr/bin/env bash
set -Eeuo pipefail

readonly project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
work_dir="$(mktemp -d)"
trap 'rm -rf -- "$work_dir"' EXIT

printf '%s\n' \
    $'ni\t你' \
    "ni'hao"$'\t你好' \
    "xia'pin'shu'ru'fa"$'\t瞎拼输入法' \
    >"$work_dir/source.tsv"

"$project_dir/scripts/build-dictionary.sh" \
    --source "$work_dir/source.tsv" \
    --output "$work_dir/output.dict" \
    --keep-text

[[ -s "$work_dir/output.dict" ]]
[[ -s "$work_dir/output.txt" ]]
grep -qx "你好 ni'hao 0" "$work_dir/output.txt"
grep -qx "瞎拼输入法 xia'pin'shu'ru'fa 0" "$work_dir/output.txt"
[[ $(wc -l <"$work_dir/output.txt") -eq 3 ]]

printf '%s\n' $'not valid\t坏' >"$work_dir/invalid.tsv"
if "$project_dir/scripts/build-dictionary.sh" \
    --source "$work_dir/invalid.tsv" --output "$work_dir/bad.dict" \
    >/dev/null 2>&1; then
    echo "invalid pinyin source was accepted" >&2
    exit 1
fi

"$project_dir/scripts/build-dictionary.sh" --compatible \
    --output "$work_dir/compatible.dict" --keep-text
[[ $(wc -l <"$work_dir/compatible.txt") -eq 243 ]]
cmp -s "$project_dir/data/xiapin-extra.libime-1.0.dict" \
    "$work_dir/compatible.dict"
