#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == silverbullet-test && $EUID == 0 ]]
account=pol-pamet-oidc
if ! id -u "$account" >/dev/null 2>&1; then
    useradd --system --user-group --no-create-home --shell /usr/sbin/nologin "$account"
fi
[[ $(id -gn "$account") == "$account" && $(id -u "$account") != "$(id -u pol-silverbullet)" ]]
cd /etc/polarita-silverbullet
install -dm0750 -o root -g "$account" pristup
for name in client cookie; do
    [[ -f $name && ! -L $name && -s $name ]]
    install -m0440 -o root -g "$account" "$name" "pristup/$name.next"
    mv -T "pristup/$name.next" "pristup/$name"
    runuser -u "$account" -- test -r "pristup/$name"
    if runuser -u pol-silverbullet -- test -r "pristup/$name"; then exit 1; fi
done
