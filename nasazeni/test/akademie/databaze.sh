#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
host=${1:?Chybí DNS jméno TEST}
[[ $host =~ ^[a-z0-9.-]+[.]ts[.]net$ ]]
vm=akademie-test
inside=(incus exec -T "$vm" --)
pg=(incus exec -T postgres-test -- runuser -u postgres -- psql -X --no-psqlrc --set=ON_ERROR_STOP=1 -At -d db_akademie)
work=/srv/polarita/infra/akademie-test/stav
app=/srv/polarita/apps/akademie-test
rev=$(readlink "$app/candidate")
[[ $rev =~ ^releases/[0-9a-f]{64}$ ]]
tree=/opt/polarita-akademie/$rev
install -dm0700 "$work"
exec 9>"$work/.instalace"
flock 9
exec 8>/run/polarita-test-zatez.lock
flock 8
[[ -s $app/$rev/vendor/autoload.php ]]
conf=/etc/polarita-akademie
for file in nastaveni instaluj; do
    incus file push --mode=0644 "$src/$file.php" "$vm$conf/.$file.next"
    "${inside[@]}" mv -T "$conf/.$file.next" "$conf/$file.php"
done
printf 'https://%s:8451\n' "$host" | incus file push --mode=0644 - "$vm$conf/.url-next"
"${inside[@]}" mv -T "$conf/.url-next" "$conf/url"
# Citlivé nastavení je v kontejneru, kód PHP zůstává připojen jen pro čtení.
tmp=$(mktemp "$app/$rev/.bootstrap-XXXXXXXX")
trap 'unlink "$tmp" 2>/dev/null || true' EXIT
printf '%s\n' '<?php' "require '/etc/polarita-akademie/nastaveni.php';" "require_once __DIR__ . '/lib/setup.php';" >"$tmp"
chmod 0644 "$tmp"
if [[ -e $app/$rev/config.php ]]; then cmp "$tmp" "$app/$rev/config.php"; else mv -T "$tmp" "$app/$rev/config.php"; fi
ready="$work/schema-pripraveno-${rev##*/}"
if [[ -s $work/schema ]]; then
    read -r schema <"$work/schema"
    [[ $schema =~ ^pol_mdl_[a-f0-9]{16}$ ]]
elif [[ -s $ready ]]; then
    read -r schema <"$ready"
    [[ $schema =~ ^pol_mdl_[a-f0-9]{16}$ ]]
else
    # Každá nedokončená prvotní instalace má své schéma a soubory. Aplikaci
    # předáme jméno teprve po úspěchu instalačního CLI a kontrole obou pluginů.
    schema=pol_mdl_$(openssl rand -hex 8)
    "${pg[@]}" -c "CREATE SCHEMA $schema AUTHORIZATION db_akademie"
    "${inside[@]}" install -dm0700 -o www-data -g www-data "/var/lib/polarita-akademie/$schema" "/var/lib/polarita-akademie/$schema/lang"
    "${inside[@]}" ln -s "$tree/jazyk/cs" "/var/lib/polarita-akademie/$schema/lang/cs"
    incus exec -T "$vm" --user 33 --group 33 -- env POLARITA_AKADEMIE_SCHEMA="$schema" \
        php8.4 -d max_input_vars=5000 -d zend.exception_ignore_args=1 "$conf/instaluj.php" "$tree" \
        </srv/polarita/data/bootstrap-test/test-login/heslo
    printf '%s\n' "$schema" >"$ready.next"
    mv -T "$ready.next" "$ready"
fi
cli=(incus exec -T "$vm" --user 33 --group 33 -- env POLARITA_AKADEMIE_SCHEMA="$schema" php8.4 -d max_input_vars=5000)
"${cli[@]}" "$tree/admin/cli/upgrade.php" --non-interactive
"${cli[@]}" "$tree/admin/cli/cfg.php" --name=lang --set=cs
bash "$src/publikuj-db.sh" "$rev" "$schema"
