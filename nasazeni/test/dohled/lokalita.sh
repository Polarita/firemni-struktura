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
if [[ $(omd config "$site" show AUTOSTART) != on ]]; then
    omd config "$site" set AUTOSTART on
fi
# Jeden lokální reverzní proxy proces stačí pro jednouživatelské testovací rozhraní.
cat >/etc/apache2/conf-enabled/polarita-checkmk-test.conf <<'CONF'
<IfModule mpm_event_module>
    StartServers 1
    ServerLimit 4
    ThreadsPerChild 8
    MinSpareThreads 4
    MaxSpareThreads 12
    MaxRequestWorkers 32
</IfModule>
CONF
apachectl configtest
systemctl enable --now apache2
systemctl reload apache2
if ! omd status "$site" >/dev/null; then
    # Při částečném běhu vrací start některých již běžících démonů nenulový kód.
    # O přijetí rozhodne následná kontrola všech procesů lokality.
    omd start "$site" || omd status "$site" >/dev/null
fi
omd status "$site"
body=$(mktemp)
trap 'rm -f -- "$body"' EXIT
for i in {1..30}; do
    if curl --noproxy '*' --fail --silent --location --max-time 5 --output "$body" "http://127.0.0.1/$site/check_mk/login.py" && grep -iq 'name="\(_username\|username\)"' "$body"; then
        echo 'Webové přihlášení lokality Checkmk odpovědělo v oddělené aplikační instanci.'
        exit 0
    fi
    sleep 2
done
exit 1
