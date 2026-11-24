#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
fqdn=${1:?Chybí VPN jméno}
inside=(incus exec -T paperclip-test --)
sql=(incus exec -T postgres-test -- runuser -u postgres -- psql -XqAt -v ON_ERROR_STOP=1 -d db_paperclip)
work=/srv/polarita/infra/paperclip-test
exec 8>"$work/.spravce"
flock 8
incus file push --mode=0644 "$src/board.py" paperclip-test/etc/polarita-paperclip/
state() {
  "${sql[@]}" -c 'SELECT (SELECT count(*) FROM "user" WHERE lower(email) = '\''spravce@polarita.test'\''), (SELECT count(*) FROM instance_user_roles WHERE role='\''instance_admin'\''), (SELECT count(*) FROM instance_user_roles r JOIN "user" u ON u.id=r.user_id WHERE r.role='\''instance_admin'\'' AND lower(u.email)='\''spravce@polarita.test'\'')'
}
case $(state) in
  '0|0|0') action=vytvor ;;
  '1|0|0') action=prevezmi ;;
  '1|'*'|1') action=over ;;
  *) echo 'Dosavadní správce instance se liší od vlastníka testovací instalace.' >&2; exit 1 ;;
esac
login() {
    "${inside[@]}" python3 /etc/polarita-paperclip/board.py "$fqdn" "$1" </srv/polarita/data/bootstrap-test/test-login/heslo
}
login "$action"
[[ $(state) == '1|'*'|1' ]]
if ! "${inside[@]}" grep -qx PAPERCLIP_AUTH_DISABLE_SIGN_UP=true /etc/polarita-paperclip/server.env; then
    "${inside[@]}" touch /etc/polarita-paperclip/spravce-overen
    bash "$src/server.sh" "$fqdn"
fi
login over
incus file push --mode=0644 "$src/organizace.py" paperclip-test/etc/polarita-paperclip/
store=/srv/polarita/data/paperclip
plan=$(mktemp -p "$store" pozice.XXXXXXXX)
trap 'rm -f -- "$plan"' EXIT
python3 "$src/pozice.py" "${2:?Chybí revize ověřená v Gitee}" >"$plan"
incus file push --mode=0644 "$plan" paperclip-test/etc/polarita-paperclip/pozice.json
"${inside[@]}" python3 /etc/polarita-paperclip/organizace.py "$fqdn" </srv/polarita/data/bootstrap-test/test-login/heslo
mv -T "$plan" "$store/pozice.json"
