#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
rev=${1:?Chybí sestavení}
schema=${2:?Chybí nainstalované schéma}
[[ $rev =~ ^releases/[a-f0-9]{64}$ && $schema =~ ^pol_mdl_[a-f0-9]{16}$ ]]
app=/srv/polarita/apps/akademie-test
work=/srv/polarita/infra/akademie-test/stav
vm=akademie-test
conf=/etc/polarita-akademie
inside=(incus exec -T "$vm" --)
pg=(incus exec -T postgres-test -- runuser -u postgres -- psql -XqAt -v ON_ERROR_STOP=1 -d db_akademie)
exec 7>"$work/.publikace"
flock 7
[[ $(readlink "$app/candidate") == "$rev" && -f $app/$rev/config.php ]]
if [[ -s $work/schema ]]; then [[ $(cat "$work/schema") == "$schema" ]]; fi
# Kontrolní režim CLI skončí kódem 2, pokud zdroj a databáze vyžadují aktualizaci.
incus exec -T "$vm" --user 33 --group 33 -- env POLARITA_AKADEMIE_SCHEMA="$schema" php8.4 \
    -d max_input_vars=5000 "/opt/polarita-akademie/$rev/admin/cli/upgrade.php" --is-pending
[[ $("${pg[@]}" -c "SELECT count(*) FROM $schema.mdl_modules WHERE name IN ('customcert','offlinequiz')") == 2 ]]
[[ $("${pg[@]}" -c "SELECT count(*) FROM $schema.mdl_user WHERE username='spravce' AND deleted=0 AND suspended=0 AND confirmed=1 AND email='spravce@polarita.test'") == 1 ]]
[[ $("${pg[@]}" -c "SELECT value FROM $schema.mdl_config WHERE name='lang'") == cs ]]
printf '%s\n' "$schema" >"$work/.schema-next"
mv -T "$work/.schema-next" "$work/schema"
incus file push --mode=0644 "$work/schema" "$vm$conf/.schema-next"
"${inside[@]}" mv -T "$conf/.schema-next" "$conf/schema"
ln -sfn "$rev" "$app/.current-next"
mv -Tf "$app/.current-next" "$app/current"
printf 'Moodle má databázi, účet spravce, češtinu a registrované moduly Offline Quiz a Custom Certificate.\n'
