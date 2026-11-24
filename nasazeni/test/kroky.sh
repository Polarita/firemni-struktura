#!/bin/bash
# Volá deploy.sh pod společným zámkem na Ejpovicích.
set -euo pipefail
umask 077
commit=$1
sudo -n bash nasazeni/test/zaklad.sh
inc=(sudo -n incus)
guest=("${inc[@]}" exec -T --project polarita polarita-hq --)
[[ $("${guest[@]}" hostname -s) == polarita-hq ]]
dest=/srv/polarita/infra/releases/$commit
"${guest[@]}" install -d "$dest"
tmp=$(mktemp -d)
vpn_tmp=
trap 'rm -rf -- "$tmp"; if [[ -n $vpn_tmp ]]; then "${guest[@]}" rm -rf -- "$vpn_tmp"; fi' EXIT
git archive --format=tar.gz --output="$tmp/zdroj-ci.tar.gz" "$commit"
digest=$(sha256sum "$tmp/zdroj-ci.tar.gz")
upload=$("${guest[@]}" mktemp "$dest/.zdroj-ci-XXXXXXXX")
"${inc[@]}" file push --mode 0600 --project polarita "$tmp/zdroj-ci.tar.gz" "polarita-hq$upload"
"${guest[@]}" bash -ec 'sum=$(sha256sum "$1"); [[ ${sum%% *} == "$3" ]]; mv -T "$1" "$2"' -- "$upload" "$dest/zdroj-ci.tar.gz" "${digest%% *}"
"${guest[@]}" tar -xzf "$dest/zdroj-ci.tar.gz" -C "$dest"
"${guest[@]}" bash "$dest/nasazeni/test/zaklad/pamet.sh"
"${guest[@]}" python3 "$dest/nasazeni/test/pamet/soukrome.py"
"${guest[@]}" bash "$dest/nasazeni/test/karantena/kvm-host.sh"
if ! "${guest[@]}" grep -qw no-kvmapf /proc/cmdline; then
    "${guest[@]}" systemd-run --quiet --pipe --wait --collect \
        -p LoadCredentialEncrypted=polarita-zfs.key:/etc/polarita/zfs/vtpm.cred \
        sh -ec 'zfs load-key -n -L "file://${CREDENTIALS_DIRECTORY}/polarita-zfs.key" polarita_zfs'
    "${guest[@]}" zpool sync polarita_zfs
    "${guest[@]}" systemctl reboot --no-block
    for i in {1..180}; do
        if timeout 4 "${guest[@]}" sh -ec 'grep -qw no-kvmapf /proc/cmdline && systemctl is-active --quiet polarita-bootstrap.service' 2>/dev/null; then break; fi
        sleep 3
    done
    "${guest[@]}" grep -qw no-kvmapf /proc/cmdline
    "${guest[@]}" systemctl is-active --quiet polarita-bootstrap.service
fi
python3 nasazeni/test/inventura.py >"$tmp/inventura.json"
"${guest[@]}" install -d /srv/polarita/workspace/dukazy/blok-01
"${inc[@]}" file push --project polarita "$tmp/inventura.json" "polarita-hq/srv/polarita/workspace/dukazy/blok-01/inventura-$commit.json"
fqdn=$(tailscale status --json | python3 -c 'import json,sys;print(json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))')

uuid=$("${inc[@]}" --project polarita config get polarita-hq volatile.uuid)
guid=$("${guest[@]}" zpool get -Ho value guid polarita_zfs)
[[ $uuid =~ ^[0-9a-f-]{36}$ && $guid =~ ^[0-9]+$ && -n $fqdn ]]
stav=/srv/polarita/infra/instalace-test
"${guest[@]}" install -d -m 0700 "$stav"
aktivni=$("${guest[@]}" bash -ec 'p=/srv/polarita/infra/releases/current; if [[ -L $p ]]; then readlink -e "$p"; fi')
cil="$commit/$uuid/$guid/$fqdn/$aktivni"
prubeh=nasazeni/test/prubeh.py

portal() {
    go test -count=1 nasazeni/test/portal{,_test}.go
    CGO_ENABLED=0 go build -trimpath -o "$tmp/portal" nasazeni/test/portal.go
    "${inc[@]}" file push --mode 0755 --project polarita "$tmp/portal" "polarita-hq$dest/portal"
    "${guest[@]}" "$dest/nasazeni/test/incus.sh"
    "${guest[@]}" "$dest/nasazeni/test/site.sh" "$fqdn"
    "${guest[@]}" "$dest/nasazeni/test/portal.sh" "$dest/portal"
    "${guest[@]}" "$dest/nasazeni/test/hrana.sh"
    "${guest[@]}" curl -fsS --retry 4 --retry-connrefused -o /dev/null http://127.0.0.1:18184/
    sudo -n bash nasazeni/test/vstup.sh
    "${guest[@]}" cat /srv/polarita/data/bootstrap-test/test-login/heslo | python3 nasazeni/test/smoke.py "https://$fqdn"
}

sit() {
    vpn_tmp=$("${guest[@]}" mktemp -d /run/polarita-vpn-test-XXXXXXXX)
    "${inc[@]}" file push --project polarita "$(command -v tailscale)" "$(command -v tailscaled || echo /usr/sbin/tailscaled)" "polarita-hq$vpn_tmp/"
    "${guest[@]}" install -d /srv/polarita/workspace/dukazy/blok-03
    "${guest[@]}" "$dest/nasazeni/test/mx.sh" | tee "$tmp/mx.txt"
    "${inc[@]}" file push --project polarita "$tmp/mx.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-03/mx-$commit.txt"
    "${guest[@]}" "$dest/nasazeni/test/ochrana.sh"
    "${guest[@]}" python3 "$dest/nasazeni/test/ochrana/zkouska.py" | tee "$tmp/ochrana.txt"
    "${inc[@]}" file push --project polarita "$tmp/ochrana.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-03/ochrana-$commit.txt"
    if command -v dig >/dev/null; then
        bash nasazeni/test/hrana/inventura-dns.sh >"$tmp/dns.txt"
        "${inc[@]}" file push --project polarita "$tmp/dns.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-03/verejne-dns-$commit.txt"
    fi
    "${guest[@]}" python3 "$dest/nasazeni/test/hrana/zkouska-vpn.py" "$vpn_tmp" | tee "$tmp/zkouska-vpn.txt"
    "${inc[@]}" file push --project polarita "$tmp/zkouska-vpn.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-03/zkouska-vpn-$commit.txt"
}

hesla() {
    go test -count=1 nasazeni/test/portal{,_test}.go
    CGO_ENABLED=0 go build -trimpath -o "$tmp/agent" nasazeni/test/trezor/agent.go
    "${inc[@]}" file push --mode 0755 --project polarita "$tmp/agent" "polarita-hq$dest/agent"
    "${guest[@]}" bash "$dest/nasazeni/test/hesla/instalace.sh" "https://$fqdn/hesla" | tee "$tmp/hesla.txt"
    "${guest[@]}" python3 "$dest/nasazeni/test/hesla/obnova.py" | tee "$tmp/obnova-hesel.txt"
}

postgres() {
    "${guest[@]}" install -d /srv/polarita/workspace/dukazy/blok-05
    "${guest[@]}" bash "$dest/nasazeni/test/databaze/postgres.sh" | tee "$tmp/postgres.txt"
}

sluzby() {
    "${guest[@]}" bash "$dest/nasazeni/test/identita/instalace.sh" "https://$fqdn/identita"
    "${guest[@]}" bash "$dest/nasazeni/test/pecet/instalace.sh"
    "${guest[@]}" bash "$dest/nasazeni/test/mezipamet/instalace.sh"
    "${guest[@]}" bash "$dest/nasazeni/test/objekty/instalace.sh"
    "${guest[@]}" bash "$dest/nasazeni/test/git/instalace.sh" "https://$fqdn/git/"
    "${guest[@]}" bash "$dest/nasazeni/test/git/runner.sh"
    "${guest[@]}" bash "$dest/nasazeni/test/git/vstup.sh" "https://$fqdn/git/"
}

tym() {
    "${guest[@]}" install -dm0750 /srv/polarita/workspace/dukazy/blok-08
    "${guest[@]}" bash "$dest/nasazeni/test/paperless/priprava.sh" | tee "$tmp/paperless-priprava.txt"
    "${inc[@]}" file push --project polarita "$tmp/paperless-priprava.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-08/paperless-priprava-$commit.txt"
    "${guest[@]}" bash "$dest/nasazeni/test/vikunja/priprava.sh" | tee "$tmp/vikunja-priprava.txt"
    "${inc[@]}" file push --project polarita "$tmp/vikunja-priprava.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-08/vikunja-priprava-$commit.txt"
    "${guest[@]}" bash "$dest/nasazeni/test/paperclip/priprava.sh"
    "${guest[@]}" bash "$dest/nasazeni/test/zulip/fronta.sh"
    "${guest[@]}" bash "$dest/nasazeni/test/zulip/aplikace.sh" "$fqdn"
}

trezor() {
    sudo -n bash nasazeni/test/trezor/prijemce.sh
    if "${guest[@]}" test -e /srv/polarita/data/bootstrap-test/openbao-test/inicializovano; then
        sudo -n python3 nasazeni/test/trezor/rozsireni.py "$dest/nasazeni/test/trezor"
    fi
    "${guest[@]}" install -d /srv/polarita/workspace/dukazy/blok-04
    "${guest[@]}" bash "$dest/nasazeni/test/trezor/instalace.sh" "$dest/agent" | tee "$tmp/trezor.txt"
}

databaze() {
    "${guest[@]}" bash "$dest/nasazeni/test/databaze/aplikace.sh" | tee "$tmp/databaze.txt"
}

paperclip() {
    "${guest[@]}" bash "$dest/nasazeni/test/paperclip/server.sh" "$fqdn" | tee "$tmp/paperclip.txt"
    "${guest[@]}" touch /srv/polarita/infra/keycloak-test/conf/databaze-pripravena
}

identita() {
    "${guest[@]}" bash "$dest/nasazeni/test/trezor/zkouska-startu.sh" | tee "$tmp/restart.txt"
    sudo -n python3 nasazeni/test/trezor/zkouska-obnovy.py "$dest/nasazeni/test/trezor" | tee "$tmp/obnova.txt"
    "${guest[@]}" python3 "$dest/nasazeni/test/pecet/zkouska.py" | tee "$tmp/pecet.txt"
    sum=$("${guest[@]}" sha256sum /srv/polarita/workspace/dukazy/blok-04/pecet/predavaci-protokol.pdf)
    "${guest[@]}" cat /srv/polarita/data/bootstrap-test/test-login/heslo | python3 nasazeni/test/pecet/portal.py "https://$fqdn" "${sum%% *}" | tee -a "$tmp/pecet.txt"
    python3 nasazeni/test/identita/overeni.py "https://$fqdn/identita" | tee "$tmp/identita.txt"
    "${guest[@]}" cat /srv/polarita/data/bootstrap-test/test-login/heslo | python3 nasazeni/test/identita/prihlaseni.py "https://$fqdn/identita" | tee -a "$tmp/identita.txt"
    "${guest[@]}" python3 "$dest/nasazeni/test/identita/sprava_klientu.py" | tee -a "$tmp/identita.txt"
    "${guest[@]}" python3 "$dest/nasazeni/test/mezipamet/overeni.py" | tee "$tmp/valkey.txt"
}

firemni_git() {
    "${guest[@]}" bash "$dest/nasazeni/test/git/spust.sh" | tee "$tmp/gitea.txt"
    "${guest[@]}" python3 "$dest/nasazeni/test/git/pripoj_identitu.py" | tee -a "$tmp/gitea.txt"
    "${guest[@]}" cat /srv/polarita/data/bootstrap-test/test-login/heslo | python3 nasazeni/test/git/zkouska_prihlaseni.py "https://$fqdn" | tee -a "$tmp/gitea.txt"
    "${guest[@]}" python3 "$dest/nasazeni/test/git/repozitar.py" | tee -a "$tmp/gitea.txt"
    "${guest[@]}" bash "$dest/nasazeni/test/git/fronta.sh" | tee -a "$tmp/gitea.txt"
    "${guest[@]}" bash "$dest/nasazeni/test/git/kontrola.sh" "$dest" | tee -a "$tmp/gitea.txt"
}

rozhodnuti() {
    "${guest[@]}" bash "$dest/nasazeni/test/paperclip/spravce.sh" "$fqdn" "$dest/revize-ci.json" | tee -a "$tmp/paperclip.txt"
    "${guest[@]}" bash "$dest/nasazeni/test/paperclip/stage1.sh" | tee -a "$tmp/paperclip.txt"
    "${guest[@]}" bash "$dest/nasazeni/test/decisions/instalace.sh" | tee -a "$tmp/paperclip.txt"
    "${guest[@]}" bash "$dest/nasazeni/test/decisions/paperclip.sh" "$fqdn" | tee -a "$tmp/paperclip.txt"
    bash nasazeni/test/reklama/podklad.sh
    "${guest[@]}" bash "$dest/nasazeni/test/reklama/instalace.sh" | tee -a "$tmp/paperclip.txt"
    "${guest[@]}" bash "$dest/nasazeni/test/finops/instalace.sh" "$fqdn" | tee -a "$tmp/paperclip.txt"
    "${guest[@]}" bash "$dest/nasazeni/test/paperclip/vstup.sh"
    sudo -n bash nasazeni/test/port-vpn.sh 8445 >/dev/null
    "${guest[@]}" cat /srv/polarita/data/bootstrap-test/test-login/heslo | python3 nasazeni/test/paperclip/zkouska_vpn.py "$fqdn" --decisions | tee -a "$tmp/paperclip.txt"
    printf 'https://%s:8445/\n' "$fqdn" | "${inc[@]}" exec --project polarita -T polarita-hq -- incus exec -T reditelstvi-test -- sh -ec 'umask 022; cat >/usr/local/share/.polarita-paperclip-url.next; mv -T /usr/local/share/.polarita-paperclip-url.next /usr/local/share/polarita-paperclip-url'
    "${guest[@]}" install -d /srv/polarita/workspace/dukazy/blok-07
    "${inc[@]}" file push --project polarita "$tmp/paperclip.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-07/paperclip-$commit.txt"
    "${guest[@]}" incus exec -T reditelstvi-test -- touch /usr/local/share/polarita-gitea-oidc.ok
}

metadata() {
    "${guest[@]}" bash "$dest/nasazeni/test/metadata-schema-kernel/instalace.sh" | tee "$tmp/metadata.txt"
    "${guest[@]}" cat /srv/polarita/data/bootstrap-test/test-login/heslo |
        python3 nasazeni/test/metadata-schema-kernel/over_portal.py "https://$fqdn" | tee -a "$tmp/metadata.txt"
    "${inc[@]}" file push --project polarita "$tmp/metadata.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-07/metadata-$commit.txt"
}

obnova_databazi() {
    "${guest[@]}" bash "$dest/nasazeni/test/objekty/zkouska.sh" | tee "$tmp/garage.txt"
    "${guest[@]}" python3 "$dest/nasazeni/test/databaze/obnova.py" | tee "$tmp/obnova-databazi.txt"
    "${guest[@]}" bash "$dest/nasazeni/test/pamet/instalace.sh" | tee "$tmp/znalosti.txt"
    "${guest[@]}" bash "$dest/nasazeni/test/agent-vault/instalace.sh" | tee -a "$tmp/znalosti.txt"
    "${guest[@]}" bash "$dest/nasazeni/test/den-1/instalace.sh" | tee -a "$tmp/znalosti.txt"
    "${guest[@]}" bash "$dest/nasazeni/test/silverbullet/instalace.sh" | tee -a "$tmp/znalosti.txt"
    "${guest[@]}" bash "$dest/nasazeni/test/silverbullet/vstup.sh" | tee -a "$tmp/znalosti.txt"
    sudo -n bash nasazeni/test/port-vpn.sh 8446 >/dev/null
    "${guest[@]}" cat /srv/polarita/data/bootstrap-test/test-login/heslo |
        python3 nasazeni/test/silverbullet/zkouska_prihlaseni.py "$fqdn" | tee -a "$tmp/znalosti.txt"
    printf 'https://%s:8446/pamet/\n' "$fqdn" | "${guest[@]}" incus exec -T reditelstvi-test -- sh -ec 'umask 022; cat >/usr/local/share/.polarita-silverbullet-url.next; mv -T /usr/local/share/.polarita-silverbullet-url.next /usr/local/share/polarita-silverbullet-url'

    "${guest[@]}" install -dm0750 /srv/polarita/workspace/dukazy/blok-08
    "${guest[@]}" bash "$dest/nasazeni/test/paperless/server.sh" "$fqdn" | tee "$tmp/paperless-server.txt"
    "${inc[@]}" file push --project polarita "$tmp/paperless-server.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-08/paperless-server-$commit.txt"
    "${guest[@]}" bash "$dest/nasazeni/test/vikunja/server.sh" "$fqdn"
    "${guest[@]}" bash "$dest/nasazeni/test/hrana/obnov-vstup.sh"
    sudo -n bash nasazeni/test/port-vpn.sh 8447 >/dev/null
    "${guest[@]}" cat /srv/polarita/data/bootstrap-test/test-login/heslo |
        python3 nasazeni/test/vikunja/zkouska.py "$fqdn" | tee "$tmp/vikunja.txt"
    "${inc[@]}" file push --project polarita "$tmp/vikunja.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-08/vikunja-$commit.txt"
    printf 'https://%s:8447/\n' "$fqdn" | "${guest[@]}" incus exec -T reditelstvi-test -- sh -ec 'umask 022; cat >/usr/local/share/.polarita-vikunja-url.next; mv -T /usr/local/share/.polarita-vikunja-url.next /usr/local/share/polarita-vikunja-url'
    "${guest[@]}" bash "$dest/nasazeni/test/archiv/instalace.sh" | tee "$tmp/archiv.txt"
    for proof in identita postgres databaze obnova-databazi znalosti valkey garage archiv gitea; do
        "${inc[@]}" file push --project polarita "$tmp/$proof.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-05/$proof-$commit.txt"
    done
    for proof in trezor restart obnova hesla obnova-hesel pecet; do
        "${inc[@]}" file push --project polarita "$tmp/$proof.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-04/$proof-$commit.txt"
    done
}

karantena() {
    for step in proxy signatury priprava offline fronta; do
        printf 'Karanténa – %s\n' "$step"
        "${guest[@]}" bash "$dest/nasazeni/test/karantena/$step.sh" </dev/null
    done
    "${guest[@]}" python3 "$dest/nasazeni/test/karantena/zkouska.py" | tee "$tmp/karantena.txt"
    "${inc[@]}" file push --project polarita "$tmp/karantena.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-04/karantena-$commit.txt"
}

zalohy() {
    "${guest[@]}" install -d /srv/polarita/workspace/dukazy/blok-06
    "${guest[@]}" bash "$dest/nasazeni/test/zalohy/snimky.sh" | tee "$tmp/sanoid.txt"
    "${inc[@]}" file push --project polarita "$tmp/sanoid.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-06/sanoid-$commit.txt"
    "${guest[@]}" bash "$dest/nasazeni/test/zalohy/wal-instalace.sh"
    "${guest[@]}" bash "$dest/nasazeni/test/zalohy/instalace.sh"
    "${guest[@]}" bash "$dest/nasazeni/test/zalohy/obraz.sh"
    "${guest[@]}" python3 "$dest/nasazeni/test/zalohy/zkouska_pristupu.py" | tee "$tmp/restic.txt"
    sudo -n bash nasazeni/test/zalohy/zkouska_obalky.sh "$dest/nasazeni/test/zalohy" | tee -a "$tmp/restic.txt"
}

dohled() {
    "${guest[@]}" bash "$dest/nasazeni/test/dohled/instalace.sh" | tee "$tmp/dohled.txt"
}

zulip() {
    "${guest[@]}" bash "$dest/nasazeni/test/zulip/spust.sh" "$fqdn"
    "${guest[@]}" bash "$dest/nasazeni/test/zulip/organizace.sh"
    "${guest[@]}" bash "$dest/nasazeni/test/zulip/boti.sh" | tee "$tmp/zulip-boti.txt"
    "${guest[@]}" install -d /srv/polarita/workspace/dukazy/blok-07
    "${inc[@]}" file push --project polarita "$tmp/zulip-boti.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-07/zulip-boti-$commit.txt"
    "${guest[@]}" bash "$dest/nasazeni/test/zulip/dohled.sh" "$fqdn"
    "${guest[@]}" python3 "$dest/nasazeni/test/dohled/zkouska_vypadku.py" --zulip | tee "$tmp/zulip-alert.txt"
    "${guest[@]}" install -d /srv/polarita/workspace/dukazy/blok-07
    "${inc[@]}" file push --project polarita "$tmp/zulip-alert.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-07/checkmk-zulip-$commit.txt"
    sudo -n bash nasazeni/test/zulip/vstup.sh
    "${guest[@]}" cat /srv/polarita/data/bootstrap-test/test-login/heslo | python3 nasazeni/test/zulip/zkouska_prihlaseni.py "$fqdn" | tee "$tmp/zulip-oidc.txt"
    "${guest[@]}" install -d /srv/polarita/workspace/dukazy/blok-07
    "${inc[@]}" file push --project polarita "$tmp/zulip-oidc.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-07/zulip-oidc-$commit.txt"
    printf 'https://%s:8444/\n' "$fqdn" | "${inc[@]}" exec --project polarita -T polarita-hq -- incus exec -T reditelstvi-test -- sh -ec 'umask 022; cat >/usr/local/share/.polarita-zulip-url.next; mv -T /usr/local/share/.polarita-zulip-url.next /usr/local/share/polarita-zulip-url'
}

obnova() {
    "${guest[@]}" python3 "$dest/nasazeni/test/zalohy/sber.py" | tee -a "$tmp/restic.txt"
    "${guest[@]}" python3 "$dest/nasazeni/test/zalohy/obnov.py" | tee -a "$tmp/restic.txt"
    "${guest[@]}" bash "$dest/nasazeni/test/zalohy/retence.sh" | tee -a "$tmp/restic.txt"
    "${guest[@]}" bash "$dest/nasazeni/test/zalohy/hovory-instalace.sh"
    "${guest[@]}" python3 "$dest/nasazeni/test/zalohy/zkouska_hovoru.py" | tee -a "$tmp/restic.txt"
    "${guest[@]}" python3 "$dest/nasazeni/test/zalohy/hovory_sber.py" | tee -a "$tmp/restic.txt"
    "${guest[@]}" bash "$dest/nasazeni/test/zalohy/naplanuj.sh"
}

predani() {
    "${guest[@]}" systemctl start polarita-dohled-sber.service
    "${guest[@]}" cat /srv/polarita/data/bootstrap-test/test-login/heslo | python3 nasazeni/test/smoke.py "https://$fqdn" --dohled --paperclip --zulip --decisions
    "${inc[@]}" file push --project polarita "$tmp/dohled.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-06/dohled-$commit.txt"
    "${inc[@]}" file push --project polarita "$tmp/restic.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-06/restic-$commit.txt"
    # Starší vydání vytvořilo přímý vstup. Odstraň ho až po ověření nové cesty.
    if [[ $("${guest[@]}" incus config device get reditelstvi-test portal listen 2>/dev/null || true) == tcp:127.0.0.1:18182 ]]; then
        "${guest[@]}" incus config device remove reditelstvi-test portal
    fi
    "${guest[@]}" sh -ec 'ln -sfn "$1" /srv/polarita/infra/releases/.current-new; mv -Tf /srv/polarita/infra/releases/.current-new /srv/polarita/infra/releases/current' deploy "$dest"
}

kroky=(portal sit hesla postgres sluzby tym trezor databaze paperclip identita firemni_git rozhodnuti metadata obnova_databazi karantena zalohy dohled zulip obnova predani)
over_vstup() {
    "${guest[@]}" cat /srv/polarita/data/bootstrap-test/test-login/heslo | python3 nasazeni/test/smoke.py "https://$fqdn"
}
source nasazeni/test/prubeh.sh
proved_kroky "${kroky[@]}"
printf 'Ověřené přihlášení ve VPN: https://%s/\n' "$fqdn"
