#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == checkmk-test && $EUID == 0 ]]
mountpoint -q /opt/omd/sites
[[ $(readlink -f /omd/sites) == /opt/omd/sites ]]
site=polarita
work=/omd/sites/$site
omd version | grep -F 2.5.0p21
# Webová přejímka se nejprve provede uvnitř aplikační instance.
cat >/etc/apache2/ports.conf <<'CONF'
Listen 127.0.0.1:80
CONF
if ! omd sites -b | awk '{print $1}' | grep -Fxq "$site"; then
    [[ ! -e $work ]]
    # omd vypisuje jednorázové heslo výchozího místního správce.
    omd create --no-tmpfs "$site" >/dev/null
fi
omd config "$site" set AUTOSTART on
apachectl configtest
systemctl enable --now apache2
systemctl reload apache2
omd start "$site"
omd status "$site"
for i in {1..30}; do
    if curl --noproxy '*' --fail --silent --location --max-time 5 "http://127.0.0.1/$site/check_mk/login.py" | grep -iq 'name="\(_username\|username\)"'; then
        echo 'Webové přihlášení lokality Checkmk odpovědělo v oddělené aplikační instanci.'
        exit 0
    fi
    sleep 2
done
exit 1
