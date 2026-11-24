#!/usr/bin/env bash
set -Eeuo pipefail

readonly project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
readonly version="$(tr -d '[:space:]' <"$project_dir/VERSION")"
readonly package="xiapin-input-method"
readonly release_dir="$project_dir/dist/release-$version"
readonly source_name="$package-$version-source"
readonly architecture="amd64"
readonly deb="$project_dir/dist/${package}_${version}_${architecture}.deb"
readonly release_notes="RELEASE_NOTES_${version}.md"

[[ -s "$deb" ]] || { echo "Missing package: $deb" >&2; exit 1; }
[[ $(dpkg-deb -f "$deb" Package) == "$package" ]] || {
    echo "Unexpected package name in $deb" >&2; exit 1;
}
[[ $(dpkg-deb -f "$deb" Version) == "$version" ]] || {
    echo "Unexpected package version in $deb" >&2; exit 1;
}
[[ $(dpkg-deb -f "$deb" Architecture) == "$architecture" ]] || {
    echo "Unexpected package architecture in $deb" >&2; exit 1;
}

package_root=$(mktemp -d)
trap 'rm -rf -- "$package_root"' EXIT
dpkg-deb --extract "$deb" "$package_root"
for binary in usr/libexec/ibus-engine-xiapin usr/libexec/xiapin/xiapin-history; do
    glibc=$(objdump -T "$package_root/$binary" |
        sed -n 's/.*(GLIBC_\([0-9.]*\)).*/\1/p' | sort -Vu | tail -1)
    glibcxx=$(objdump -T "$package_root/$binary" |
        sed -n 's/.*(GLIBCXX_\([0-9.]*\)).*/\1/p' | sort -Vu | tail -1)
    [[ $(printf '%s\n%s\n' "$glibc" 2.34 | sort -V | tail -1) == 2.34 ]] || {
        echo "$binary requires GLIBC_$glibc; Ubuntu 22.04 supports up to GLIBC_2.34" >&2
        exit 1
    }
    if [[ -n "$glibcxx" ]]; then
        [[ $(printf '%s\n%s\n' "$glibcxx" 3.4.29 | sort -V | tail -1) == 3.4.29 ]] || {
            echo "$binary requires GLIBCXX_$glibcxx; Ubuntu 22.04 supports up to GLIBCXX_3.4.29" >&2
            exit 1
        }
    fi
done
rm -rf -- "$release_dir"
mkdir -p -- "$release_dir" "$release_dir/$source_name"

source_paths=(
    .gitignore AGENTS.md CHANGELOG.md CMakeLists.txt LICENSE Makefile README.md
    "$release_notes" VERSION data debian desktop docs ibus icons libexec
    scripts src systemd tests
)
for path in "${source_paths[@]}"; do
    cp -a -- "$project_dir/$path" "$release_dir/$source_name/"
done

# Generated files, local caches, downloaded dependencies and personal memory
# are intentionally absent because only the explicit source allowlist above is copied.
find "$release_dir/$source_name" -type d -name __pycache__ -prune -exec rm -rf -- {} +
find "$release_dir/$source_name" -type f \( -name '*.pyc' -o -name '*.deb' -o \
    -name '*.ucimem' -o -name 'user.dict' -o -name 'user.history' \) -delete
find "$release_dir/$source_name" -type d -exec chmod 0755 {} +
find "$release_dir/$source_name" -type f -exec chmod 0644 {} +
find "$release_dir/$source_name/scripts" "$release_dir/$source_name/libexec" \
    "$release_dir/$source_name/tests" -type f \( -name '*.sh' -o -name '*.py' \) \
    -exec chmod 0755 {} +
chmod 0755 "$release_dir/$source_name/debian/rules"

tar --sort=name --mtime='2026-11-19 15:00:00Z' --owner=0 --group=0 \
    --numeric-owner -C "$release_dir" -cJf \
    "$release_dir/${source_name}.tar.xz" "$source_name"
rm -rf -- "${release_dir:?}/$source_name"
cp -p -- "$deb" "$project_dir/$release_notes" "$release_dir/"

(
    cd -- "$release_dir"
    sha256sum "${package}_${version}_${architecture}.deb" "${source_name}.tar.xz" \
        "$release_notes" >SHA256SUMS
)

{
    printf 'release_version=%s\n' "$version"
    printf 'source_epoch_utc=2026-11-19T15:00:00Z\n'
    printf 'architecture=%s\n' "$architecture"
    printf 'files:\n'
    (cd -- "$release_dir" && while read -r hash name; do
        size=$(stat -c '%s' "$name")
        printf '  - name: %s\n    size: %s\n    sha256: %s\n' "$name" "$size" "$hash"
    done <SHA256SUMS)
} >"$release_dir/RELEASE_MANIFEST.yml"

printf 'Built release in %s\n' "$release_dir"
