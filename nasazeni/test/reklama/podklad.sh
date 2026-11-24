#!/bin/bash
# Předá vnitřnímu instalátoru nezměněnou historii připnuté veřejné předlohy.
set -euo pipefail
[[ $(hostname -s) == ejpovice ]]
pin=$(python3 -c 'import runpy,sys; print(runpy.run_path(sys.argv[1])["UPSTREAM"])' "$(dirname "$0")/fork.py")
[[ $pin =~ ^[0-9a-f]{40}$ ]]
dst=/var/cache/polarita-reklama-test/aidvertaiser-$pin.bundle
g=(sudo -n incus exec -T --project polarita polarita-hq --)
"${g[@]}" install -d -m0700 /var/cache/polarita-reklama-test
if "${g[@]}" git bundle list-heads "$dst" refs/heads/zdroj 2>/dev/null | grep -Fxq "$pin refs/heads/zdroj"; then exit 0; fi
tmp=$(mktemp -d)
trap 'rm -r -- "$tmp"' EXIT
git init -q -b zdroj "$tmp/zdroj"
git -C "$tmp/zdroj" -c http.lowSpeedLimit=512 -c http.lowSpeedTime=45 fetch -q --no-tags https://github.com/Draivix/aidvertaiser.git "$pin"
[[ $(git -C "$tmp/zdroj" rev-parse FETCH_HEAD) == "$pin" ]]
git -C "$tmp/zdroj" update-ref refs/heads/zdroj "$pin"
git -C "$tmp/zdroj" bundle create "$tmp/zdroj.bundle" refs/heads/zdroj
sum=$(sha256sum "$tmp/zdroj.bundle")
pending=$("${g[@]}" mktemp /var/cache/polarita-reklama-test/.prijem-XXXXXXXX)
sudo -n incus file push --project polarita --mode 0600 "$tmp/zdroj.bundle" "polarita-hq$pending"
"${g[@]}" bash -ec 'printf "%s  %s\n" "$1" "$2" | sha256sum --status -c -; mv -T "$2" "$3"' -- "${sum%% *}" "$pending" "$dst"
