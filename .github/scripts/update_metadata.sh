#!/usr/bin/env bash
# The electron-updater channel files (latest.yml, latest-mac.yml, latest-linux.yml) of a release.
#   update_metadata.sh patch <channel.yml> <version> <label>   point every url:/path: at freemocap_<version>_<label>.<ext>
#   update_metadata.sh check <dir>                             fail if a url:/path: of a channel file in <dir> is no file in <dir>
#   update_metadata.sh selftest                                the alpha.26 channel files, whose names did not match the assets
# An installed app downloads the file its channel file names; a wrong name means "Update available", then a 404.
set -euo pipefail

entry='^([[:space:]]*-?[[:space:]]*(url|path):[[:space:]]*)'

patch() {  # by extension, not by the electron-builder name: that name's case and form are not ours
  sed -i -E "s#${entry}['\"]?[^'\"]*\.(exe|zip|dmg|AppImage|deb)['\"]?[[:space:]]*\$#\1freemocap_${2}_${3}.\3#" "$1"
}

check() {
  local status=0 yml name
  for yml in "$1"/*.yml; do
    [ -f "$yml" ] || continue
    while read -r name; do
      [ -f "$1/$name" ] || { echo "::error::$(basename "$yml") names '$name', which is not a release asset"; status=1; }
    done < <(sed -n -E "s#${entry}['\"]?([^'\"]*[^'\"[:space:]])['\"]?[[:space:]]*\$#\3#p" "$yml")
  done
  return $status
}

selftest() {
  local dir; dir=$(mktemp -d); trap 'rm -rf "$dir"' RETURN
  printf 'version: 2.0.0-alpha.26\nfiles:\n  - url: FreeMoCap_2.0.0-alpha.26_x64_installer.exe\n    sha512: x\npath: FreeMoCap_2.0.0-alpha.26_x64_installer.exe\n' > "$dir/latest.yml"
  printf 'version: 2.0.0-alpha.26\nfiles:\n  - url: FreeMoCap_2.0.0-alpha.26_arm64_installer.zip\n  - url: FreeMoCap_2.0.0-alpha.26_arm64_installer.dmg\npath: FreeMoCap_2.0.0-alpha.26_arm64_installer.zip\n' > "$dir/latest-mac.yml"
  printf 'version: 2.0.0-alpha.26\nfiles:\n  - url: FreeMoCap_2.0.0-alpha.26_x86_64.AppImage\n  - url: FreeMoCap_2.0.0-alpha.26_amd64.deb\npath: FreeMoCap_2.0.0-alpha.26_x86_64.AppImage\n' > "$dir/latest-linux.yml"
  for ext in exe; do : > "$dir/freemocap_2.0.0-alpha.26_windows-x64-cpu.$ext"; done
  for ext in zip dmg; do : > "$dir/freemocap_2.0.0-alpha.26_macos-arm64-apple-silicon.$ext"; done
  for ext in AppImage deb; do : > "$dir/freemocap_2.0.0-alpha.26_linux-x64-cpu.$ext"; done
  if check "$dir" >/dev/null; then echo "selftest: the unpatched files must fail the check"; return 1; fi
  patch "$dir/latest.yml" 2.0.0-alpha.26 windows-x64-cpu
  patch "$dir/latest-mac.yml" 2.0.0-alpha.26 macos-arm64-apple-silicon
  patch "$dir/latest-linux.yml" 2.0.0-alpha.26 linux-x64-cpu
  check "$dir"
  grep -q '^    sha512: x$' "$dir/latest.yml"  # other lines are kept
  echo "selftest: passed"
}

"$@"
