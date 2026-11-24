#!/usr/bin/env bash
set -Eeuo pipefail

readonly project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
readonly version="$(tr -d '[:space:]' <"$project_dir/VERSION")"
readonly package="xiapin-input-method"
readonly architecture="amd64"
readonly output="$project_dir/dist/${package}_${version}_${architecture}.deb"
readonly release_notes="$project_dir/RELEASE_NOTES_${version}.md"

for command in dpkg dpkg-deb install sed gzip find xargs md5sum du; do
    command -v "$command" >/dev/null 2>&1 || { echo "Missing $command" >&2; exit 1; }
done

# Keep direct invocations safe: package files must reflect the current source,
# not whatever happens to remain under build/ from an earlier release.
make -C "$project_dir" build

root=$(mktemp -d)
trap 'rm -rf -- "$root"' EXIT
install -d "$root/DEBIAN" "$root/etc/xdg/autostart" "$root/usr/bin" \
    "$root/usr/libexec/xiapin" "$root/usr/lib/systemd/user" \
    "$root/usr/share/ibus/component" "$root/usr/share/xiapin" \
    "$root/usr/share/man/man1" \
    "$root/usr/share/doc/xiapin-input-method" \
    "$root/usr/share/icons/hicolor/scalable/apps"

install -m 0644 "$project_dir/debian/binary-control" "$root/DEBIAN/control"
for script in preinst postinst prerm postrm; do
    install -m 0755 "$project_dir/debian/xiapin-input-method.$script" "$root/DEBIAN/$script"
done
# The debhelper build expands #DEBHELPER# from the maintscript declaration.
# Keep the dependency-light fallback package upgrade-compatible as well.
for script in preinst postinst postrm; do
    sed -i '/#DEBHELPER#/c\
if dpkg-maintscript-helper supports rm_conffile; then\
    dpkg-maintscript-helper rm_conffile /etc/xdg/autostart/xiapin-input-method-autostart.desktop 2.0.0~ xiapin-input-method -- "$@"\
fi' "$root/DEBIAN/$script"
done

install -m 0755 "$project_dir/build/native/ibus-engine-xiapin" "$root/usr/libexec/"
install -m 0755 "$project_dir/build/native/xiapin-history" "$root/usr/libexec/xiapin/"
install -m 0755 "$project_dir/build/package/ubuntu-cn-input-memory" "$root/usr/bin/"
install -m 0755 "$project_dir/scripts/doctor.sh" "$root/usr/bin/ubuntu-cn-input-doctor"
install -m 0755 "$project_dir/libexec/ibusctl.py" "$root/usr/libexec/xiapin/"
install -m 0755 "$project_dir/scripts/legacy-fcitx-cleanup.sh" "$root/usr/libexec/xiapin/legacy-fcitx-cleanup"
install -m 0755 "$project_dir/libexec/legacy_profilectl.py" "$root/usr/libexec/xiapin/legacy-profilectl.py"
gzip -9n <"$project_dir/docs/ubuntu-cn-input-memory.1" \
    >"$root/usr/share/man/man1/ubuntu-cn-input-memory.1.gz"
gzip -9n <"$project_dir/docs/ubuntu-cn-input-doctor.1" \
    >"$root/usr/share/man/man1/ubuntu-cn-input-doctor.1.gz"
install -m 0644 "$project_dir/systemd/xiapin-bootstrap.service" "$root/usr/lib/systemd/user/"
install -m 0644 "$project_dir/systemd/xiapin-unlock.service" "$root/usr/lib/systemd/user/"
install -m 0644 "$project_dir/ibus/xiapin.xml" "$root/usr/share/ibus/component/"
install -m 0644 "$project_dir/ibus/xiapin.xml" "$root/usr/share/xiapin/"
install -m 0644 "$project_dir/build/xiapin-extra.dict" "$root/usr/share/xiapin/xiapin-extra.dict"
install -m 0644 "$project_dir/icons/xiapin.svg" \
    "$root/usr/share/icons/hicolor/scalable/apps/"
install -m 0644 "$project_dir/desktop/xiapin-ibus-autostart.desktop" \
    "$root/etc/xdg/autostart/xiapin-ibus-autostart.desktop"
install -m 0644 "$project_dir/README.md" "$project_dir/CHANGELOG.md" \
    "$release_notes" "$project_dir/docs/DEVELOPMENT.md" \
    "$project_dir/docs/RELEASE_ACCEPTANCE.md" \
    "$project_dir/docs/INPUT_METHOD_COMPARISON.md" "$project_dir/docs/ARCHITECTURE_REVIEW.md" \
    "$project_dir/data/SOURCES.md" \
    "$root/usr/share/doc/xiapin-input-method/"
install -m 0644 "$project_dir/debian/copyright" "$root/usr/share/doc/xiapin-input-method/copyright"
gzip -9n <"$project_dir/debian/changelog" >"$root/usr/share/doc/xiapin-input-method/changelog.gz"
chmod 0644 "$root/usr/share/doc/xiapin-input-method/changelog.gz"
chmod 0644 "$root/usr/share/man/man1/"*.1.gz

installed_size=$(du -sk "$root/usr" "$root/etc" | awk '{sum += $1} END {print sum}')
sed -i "s/^Installed-Size: .*/Installed-Size: $installed_size/" "$root/DEBIAN/control"

(cd "$root" && find etc usr -type f -print0 | sort -z | xargs -0 md5sum) >"$root/DEBIAN/md5sums"
chmod 0644 "$root/DEBIAN/md5sums"

find "$root" -type d -exec chmod 0755 {} +
mkdir -p "$project_dir/dist"
SOURCE_DATE_EPOCH=1795075200 dpkg-deb --root-owner-group --build "$root" "$output"
printf 'Built %s\n' "$output"
