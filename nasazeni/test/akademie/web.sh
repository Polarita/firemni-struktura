#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
exec 8>/run/polarita-akademie-web.lock
flock 8
vm=akademie-test
inside=(incus exec -T "$vm" --)
"${inside[@]}" test -s /etc/polarita-akademie/schema
"${inside[@]}" test -s /opt/polarita-akademie/current/public/login/index.php
incus file push --mode=0644 "$src/nginx.conf" "$vm/etc/nginx/sites-available/.polarita-akademie-next"
"${inside[@]}" bash -se <<'WEB'
set -euo pipefail
cd /etc/nginx
# Moodle porovnává kanonický port s FastCGI SERVER_PORT ještě před obsluhou přihlášení.
# Ponech systémové parametry včetně sanitizace Host a nahraď pouze port této VPN služby.
awk '$1 == "fastcgi_param" && $2 == "SERVER_PORT" { $3="8451;"; count++ } { print } END { if (count != 1) exit 1 }' \
    fastcgi_params >polarita-akademie-fastcgi.conf.next
mv -T polarita-akademie-fastcgi.conf.next polarita-akademie-fastcgi.conf
mv -T sites-available/.polarita-akademie-next sites-available/polarita-akademie
if [[ -L sites-enabled/default && $(readlink -f sites-enabled/default) == /etc/nginx/sites-available/default ]]; then
    unlink sites-enabled/default
fi
ln -sfn /etc/nginx/sites-available/polarita-akademie sites-enabled/polarita-akademie
cat >/etc/php/8.4/fpm/pool.d/zz-akademie.conf <<'POOL'
[www]
pm = ondemand
pm.max_children = 2
pm.process_idle_timeout = 120s
pm.max_requests = 100
php_admin_value[max_input_vars] = 5000
php_admin_value[upload_max_filesize] = 20M
php_admin_value[post_max_size] = 24M
php_admin_flag[display_errors] = off
POOL
nginx -t
php-fpm8.4 -t
install -d -m 0755 /run/polarita-akademie-web
activate() {
    local unit=$1 stamp=/run/polarita-akademie-web/$1
    shift
    local fingerprint
    fingerprint=$(sha256sum "$@")
    if [[ $(systemctl is-enabled "$unit") == masked ]]; then systemctl unmask "$unit"; fi
    if ! systemctl is-enabled --quiet "$unit"; then systemctl enable "$unit"; fi
    if ! systemctl is-active --quiet "$unit"; then
        systemctl start "$unit"
    elif [[ ! -f $stamp || $(cat "$stamp") != "$fingerprint" ]]; then
        systemctl reload "$unit"
    fi
    systemctl is-active --quiet "$unit"
    printf '%s\n' "$fingerprint" >"$stamp.next"
    mv -T "$stamp.next" "$stamp"
}
activate php8.4-fpm /etc/php/8.4/fpm/pool.d/zz-akademie.conf
activate nginx sites-available/polarita-akademie polarita-akademie-fastcgi.conf
WEB
origin=$("${inside[@]}" cat /etc/polarita-akademie/url)
[[ $origin =~ ^https://[a-z0-9.-]+\.ts\.net:8451$ ]]
tmp=$(mktemp)
trap 'unlink "$tmp"' EXIT
status=$(curl --silent --show-error --fail --max-time 310 -H "Host: ${origin#https://}" \
    http://10.239.32.24:8080/login/index.php -o "$tmp" -w '%{http_code}')
[[ $status == 200 ]] || { echo "Přihlašovací formulář Moodle vrátil HTTP $status." >&2; exit 1; }
grep -q 'name="logintoken"' "$tmp"
grep -q 'name="username"' "$tmp"
echo 'Nginx a PHP-FPM zobrazily skutečný přihlašovací formulář Moodle v interní síti.'
