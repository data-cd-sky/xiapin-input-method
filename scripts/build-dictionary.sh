#!/usr/bin/env bash
set -Eeuo pipefail

readonly project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
output="$project_dir/build/xiapin-extra.dict"
keep_text=false
use_compatible=false
sources=("$project_dir/data/base.tsv" "$project_dir/data/hotwords.tsv")
readonly compatible_dictionary="$project_dir/data/xiapin-extra.libime-1.0.dict"
readonly compatible_sha256="2c1c8e400585775584a1ff221f7a54f36e8ff551109820f71eaa7ed5f45de87d"

usage() {
    cat <<'EOF'
Usage: build-dictionary.sh [--output FILE] [--keep-text] [--compatible]
                           [--source FILE ...]

Build Xiapin's native LibIME extra dictionary. Sources contain
full-pinyin<TAB>word rows. By default both data/base.tsv and
data/hotwords.tsv are compiled. --source replaces the default source list.
--compatible installs the LibIME 1.0 format artifact after checking its hash
and verifying that its 243 entries exactly match the current TSV sources.
EOF
}

custom_sources=false
while (($#)); do
    case "$1" in
        --output)
            (($# >= 2)) || { echo "--output needs a path" >&2; exit 2; }
            output=$2
            shift 2
            ;;
        --source)
            (($# >= 2)) || { echo "--source needs a path" >&2; exit 2; }
            if [[ "$custom_sources" == false ]]; then
                sources=()
                custom_sources=true
            fi
            sources+=("$2")
            shift 2
            ;;
        --keep-text)
            keep_text=true
            shift
            ;;
        --compatible)
            use_compatible=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown argument: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

command -v libime_pinyindict >/dev/null 2>&1 || {
    echo "Missing libime_pinyindict. Install package: libime-bin" >&2
    exit 1
}
for source in "${sources[@]}"; do
    [[ -r "$source" ]] || { echo "Cannot read source: $source" >&2; exit 1; }
done

mkdir -p -- "$(dirname -- "$output")"
work_dir="$(mktemp -d)"
output_tmp=""
text_tmp=""
cleanup() {
    rm -rf -- "$work_dir"
    [[ -z "$output_tmp" ]] || rm -f -- "$output_tmp"
    [[ -z "$text_tmp" ]] || rm -f -- "$text_tmp"
}
trap cleanup EXIT

merged="$work_dir/xiapin-extra.txt"
awk -F '\t' '
    BEGIN { OFS=" " }
    /^#/ || NF == 0 { next }
    NF != 2 { print FILENAME ": malformed row " FNR > "/dev/stderr"; bad=1; next }
    $1 !~ /^[a-z]+(\047[a-z]+)*$/ {
        print FILENAME ": invalid full pinyin at row " FNR > "/dev/stderr"
        bad=1
        next
    }
    seen[$1 SUBSEP $2]++ {
        print FILENAME ": duplicate pinyin/word at row " FNR > "/dev/stderr"
        bad=1
        next
    }
    { print $2, $1, 0 }
    END { exit bad }
' "${sources[@]}" >"$merged"

roundtrip="$work_dir/roundtrip.txt"
compiled="$work_dir/xiapin-extra.dict"
if [[ "$use_compatible" == true ]]; then
    [[ "$custom_sources" == false ]] || {
        echo "--compatible cannot be combined with --source" >&2
        exit 2
    }
    [[ -r "$compatible_dictionary" ]] || {
        echo "Missing compatible dictionary: $compatible_dictionary" >&2
        exit 1
    }
    actual_sha256=$(sha256sum "$compatible_dictionary" | awk '{print $1}')
    [[ "$actual_sha256" == "$compatible_sha256" ]] || {
        echo "Compatible dictionary checksum mismatch" >&2
        exit 1
    }
    install -m 0644 "$compatible_dictionary" "$compiled"
else
    timeout --signal=KILL 30s libime_pinyindict "$merged" "$compiled"
fi
timeout --signal=KILL 30s libime_pinyindict -d "$compiled" "$roundtrip"

expected=$(wc -l <"$merged")
actual=$(wc -l <"$roundtrip")
[[ "$actual" -eq "$expected" ]] || {
    echo "LibIME accepted $actual of $expected entries" >&2
    exit 1
}
normalize() {
    LC_ALL=C sort -k2,2 -k1,1 "$1"
}
if ! diff -u <(normalize "$merged") <(normalize "$roundtrip") >/dev/null; then
    echo "LibIME dictionary content does not match TSV sources" >&2
    exit 1
fi

output_dir="$(dirname -- "$output")"
output_name="$(basename -- "$output")"
output_tmp="$(mktemp "$output_dir/.${output_name}.XXXXXX")"
install -m 0644 "$compiled" "$output_tmp"
mv -f -- "$output_tmp" "$output"
output_tmp=""

if [[ "$keep_text" == true ]]; then
    text_output="${output%.dict}.txt"
    text_dir="$(dirname -- "$text_output")"
    text_name="$(basename -- "$text_output")"
    text_tmp="$(mktemp "$text_dir/.${text_name}.XXXXXX")"
    install -m 0644 "$roundtrip" "$text_tmp"
    mv -f -- "$text_tmp" "$text_output"
    text_tmp=""
fi

printf 'Built %s (%s entries)\n' "$output" "$actual"
