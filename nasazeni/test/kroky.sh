#!/bin/bash
# Volá deploy.sh pod společným zámkem na Ejpovicích.
set -euo pipefail
umask 077
commit=$1
sudo -n bash nasazeni/test/zaklad.sh
inc=(sudo -n incus)
guest=("${inc[@]}" exec -T --project polarita polarita-hq --)
# Obnova ve druhé instanci a restart trezoru sdílejí kapacitu VM se sestavením aplikací.
zkouska_bez_sestaveni=("${guest[@]}" flock --close /run/polarita-test-zatez.lock)
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
"${guest[@]}" python3 "$dest/nasazeni/test/zaklad/distribuce.py"
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
"${guest[@]}" install -d /srv/polarita/workspace/dukazy/{blok-00,blok-01,blok-02}
"${inc[@]}" file push --project polarita "$tmp/inventura.json" "polarita-hq/srv/polarita/workspace/dukazy/blok-00/vstupy-test-$commit.json"
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
    go test -count=1 nasazeni/test/{portal,ecomail,svj,portal_test,svj_test}.go
    CGO_ENABLED=0 go build -trimpath -o "$tmp/portal" nasazeni/test/{portal,ecomail,svj}.go
    "${inc[@]}" file push --mode 0755 --project polarita "$tmp/portal" "polarita-hq$dest/portal"
    "${guest[@]}" "$dest/nasazeni/test/incus.sh"
    "${guest[@]}" "$dest/nasazeni/test/site.sh" "$fqdn"
    "${guest[@]}" "$dest/nasazeni/test/portal.sh" "$dest/portal"
    "${guest[@]}" python3 "$dest/nasazeni/test/incus/protokol.py" | tee "$tmp/topologie.txt"
    "${inc[@]}" file push --project polarita "$tmp/topologie.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-02/topologie-$commit.txt"
    "${guest[@]}" "$dest/nasazeni/test/hrana.sh"
    "${guest[@]}" curl -fsS --retry 4 --retry-connrefused -o /dev/null http://127.0.0.1:18184/
    sudo -n bash nasazeni/test/vstup.sh
    over_vstup
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
    go test -count=1 nasazeni/test/{portal,ecomail,svj,portal_test,svj_test}.go
    CGO_ENABLED=0 go build -trimpath -o "$tmp/agent" nasazeni/test/trezor/agent.go
    "${inc[@]}" file push --mode 0755 --project polarita "$tmp/agent" "polarita-hq$dest/agent"
    "${guest[@]}" bash "$dest/nasazeni/test/hesla/instalace.sh" "https://$fqdn/hesla" | tee "$tmp/hesla.txt"
    "${zkouska_bez_sestaveni[@]}" python3 "$dest/nasazeni/test/hesla/obnova.py" | tee "$tmp/obnova-hesel.txt"
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
    "${guest[@]}" bash "$dest/nasazeni/test/akademie/instance.sh"
    "${guest[@]}" bash "$dest/nasazeni/test/medusa/priprava.sh"
    "${guest[@]}" bash "$dest/nasazeni/test/umami/priprava.sh"
    "${guest[@]}" install -dm0750 /srv/polarita/workspace/dukazy/blok-08
    "${guest[@]}" bash "$dest/nasazeni/test/paperless/priprava.sh" "$fqdn" | tee "$tmp/paperless-priprava.txt"
    "${inc[@]}" file push --project polarita "$tmp/paperless-priprava.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-08/paperless-priprava-$commit.txt"
    "${guest[@]}" bash "$dest/nasazeni/test/vikunja/priprava.sh" | tee "$tmp/vikunja-priprava.txt"
    "${inc[@]}" file push --project polarita "$tmp/vikunja-priprava.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-08/vikunja-priprava-$commit.txt"
    "${guest[@]}" bash "$dest/nasazeni/test/paperclip/priprava.sh"
    "${guest[@]}" bash "$dest/nasazeni/test/zulip/fronta.sh"
    "${guest[@]}" bash "$dest/nasazeni/test/zulip/aplikace.sh" "$fqdn"
    "${guest[@]}" bash "$dest/nasazeni/test/karantena/pamet-fronty.sh"
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
    "${guest[@]}" bash "$dest/nasazeni/test/umami/db-ready.sh"
}

paperclip() {
    "${guest[@]}" bash "$dest/nasazeni/test/paperclip/server.sh" "$fqdn" | tee "$tmp/paperclip.txt"
    "${guest[@]}" touch /srv/polarita/infra/keycloak-test/conf/databaze-pripravena
}

identita() {
    "${zkouska_bez_sestaveni[@]}" bash "$dest/nasazeni/test/trezor/zkouska-startu.sh" | tee "$tmp/restart.txt"
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
    "${zkouska_bez_sestaveni[@]}" python3 "$dest/nasazeni/test/databaze/obnova.py" | tee "$tmp/obnova-databazi.txt"
    "${guest[@]}" bash "$dest/nasazeni/test/pamet/instalace.sh" | tee "$tmp/znalosti.txt"
    "${guest[@]}" bash "$dest/nasazeni/test/agent-vault/instalace.sh" | tee -a "$tmp/znalosti.txt"
    "${guest[@]}" bash "$dest/nasazeni/test/den-1/instalace.sh" | tee -a "$tmp/znalosti.txt"
    "${guest[@]}" bash "$dest/nasazeni/test/inzenyring/metodiky-vault.sh" | tee -a "$tmp/znalosti.txt"
    "${guest[@]}" bash "$dest/nasazeni/test/silverbullet/instalace.sh" | tee -a "$tmp/znalosti.txt"
    "${guest[@]}" bash "$dest/nasazeni/test/silverbullet/vstup.sh" | tee -a "$tmp/znalosti.txt"
    sudo -n bash nasazeni/test/port-vpn.sh 8446 >/dev/null
    "${guest[@]}" cat /srv/polarita/data/bootstrap-test/test-login/heslo |
        python3 nasazeni/test/silverbullet/zkouska_prihlaseni.py "$fqdn" --projektove-metodiky | tee -a "$tmp/znalosti.txt"
    printf 'https://%s:8446/pamet/\n' "$fqdn" | "${guest[@]}" incus exec -T reditelstvi-test -- sh -ec 'umask 022; cat >/usr/local/share/.polarita-silverbullet-url.next; mv -T /usr/local/share/.polarita-silverbullet-url.next /usr/local/share/polarita-silverbullet-url'

    "${guest[@]}" install -dm0750 /srv/polarita/workspace/dukazy/blok-08
    "${guest[@]}" bash "$dest/nasazeni/test/paperless/server.sh" "$fqdn" | tee "$tmp/paperless-server.txt"
    "${inc[@]}" file push --project polarita "$tmp/paperless-server.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-08/paperless-server-$commit.txt"
    "${guest[@]}" bash "$dest/nasazeni/test/vikunja/server.sh" "$fqdn"
    "${guest[@]}" bash "$dest/nasazeni/test/hrana/obnov-vstup.sh"
    sudo -n bash nasazeni/test/port-vpn.sh 8447 >/dev/null
    "${guest[@]}" cat /srv/polarita/data/bootstrap-test/test-login/heslo |
        python3 nasazeni/test/vikunja/zkouska.py "$fqdn" --nastenky | tee "$tmp/vikunja.txt"
    "${inc[@]}" file push --project polarita "$tmp/vikunja.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-08/vikunja-$commit.txt"
    "${guest[@]}" python3 "$dest/nasazeni/test/pamet/protokol.py" 08 "$commit" vikunja
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
    "${guest[@]}" bash "$dest/nasazeni/test/sanony/instalace.sh"
    "${guest[@]}" cat /srv/polarita/data/bootstrap-test/test-login/heslo |
        python3 nasazeni/test/sanony/overeni.py "https://$fqdn" | tee "$tmp/sanony.txt"
    "${inc[@]}" file push --project polarita "$tmp/sanony.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-08/sanony-$commit.txt"
    "${guest[@]}" python3 "$dest/nasazeni/test/paperless/vzor.py" | tee "$tmp/paperless-vzor.txt"
    "${inc[@]}" file push --project polarita "$tmp/paperless-vzor.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-08/paperless-vzor-$commit.txt"
    sudo -n bash nasazeni/test/port-vpn.sh 8448 >/dev/null
    "${guest[@]}" cat /srv/polarita/data/bootstrap-test/test-login/heslo |
        python3 nasazeni/test/paperless/prihlaseni.py "$fqdn" | tee "$tmp/paperless-prihlaseni.txt"
    "${inc[@]}" file push --project polarita "$tmp/paperless-prihlaseni.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-08/paperless-prihlaseni-$commit.txt"
    local case checksum doc field job sum
    read -r case checksum < <("${guest[@]}" python3 -c 'import json; d=json.load(open("/srv/polarita/infra/paperless-test/vzor-overen.json")); print(d["case_id"], d["sha256"])')
    read -r doc field < <("${guest[@]}" incus exec -T paperless-test -- /command/with-contenv /command/s6-setuidgid paperless python3 - "$case" "$checksum" <nasazeni/test/paperless/cteni.py)
    "${guest[@]}" cat /srv/polarita/data/bootstrap-test/test-login/heslo |
        python3 nasazeni/test/paperless/prihlaseni.py "$fqdn" "$case" "$doc" "$field" "$checksum" | tee "$tmp/paperless-cteni.txt"
    "${inc[@]}" file push --project polarita "$tmp/paperless-cteni.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-08/paperless-cteni-$commit.txt"
    printf 'https://%s:8448/\n' "$fqdn" | "${guest[@]}" incus exec -T reditelstvi-test -- sh -ec 'umask 022; cat >/usr/local/share/.polarita-paperless-url.next; mv -T /usr/local/share/.polarita-paperless-url.next /usr/local/share/polarita-paperless-url'
    "${guest[@]}" cat /srv/polarita/data/bootstrap-test/test-login/heslo |
        python3 nasazeni/test/sanony/zkouska_knihy.py "https://$fqdn" --doklad "$tmp/doklad-knihy" | tee "$tmp/kniha-objektu.txt"
    "${inc[@]}" file push --project polarita "$tmp/kniha-objektu.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-08/kniha-objektu-$commit.txt"
    read -r case doc job <"$tmp/doklad-knihy"
    [[ $job =~ ^[0-9a-f]{32}\.pdf$ ]]
    sum=$("${guest[@]}" sha256sum "/srv/polarita/workspace/karantena/vysledky/$job")
    "${guest[@]}" cat /srv/polarita/data/bootstrap-test/test-login/heslo |
        python3 nasazeni/test/paperless/prihlaseni.py "$fqdn" --priloha "$case" "$doc" "$field" "${sum%% *}" | tee "$tmp/archiv-revize.txt"
    "${inc[@]}" file push --project polarita "$tmp/archiv-revize.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-08/archiv-revize-$commit.txt"
    "${guest[@]}" python3 "$dest/nasazeni/test/pamet/protokol.py" 08 "$commit" sanony paperless-vzor paperless-prihlaseni paperless-cteni kniha-objektu archiv-revize
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

web() {
    "${guest[@]}" python3 "$dest/nasazeni/test/akademie/podklady.py" | tee "$tmp/akademie-podklady.txt"
    "${guest[@]}" bash "$dest/nasazeni/test/akademie/php.sh"
    "${guest[@]}" bash "$dest/nasazeni/test/akademie/spojeni.sh" | tee "$tmp/akademie-spojeni.txt"
    "${guest[@]}" bash "$dest/nasazeni/test/akademie/identita.sh" "$fqdn"
    "${guest[@]}" bash "$dest/nasazeni/test/akademie/aplikace.sh"
    "${guest[@]}" bash "$dest/nasazeni/test/akademie/databaze.sh" "$fqdn"
    "${guest[@]}" bash "$dest/nasazeni/test/akademie/sso.sh" "$fqdn"
    "${guest[@]}" bash "$dest/nasazeni/test/akademie/cache.sh" | tee "$tmp/akademie-cache.txt"
    "${guest[@]}" bash "$dest/nasazeni/test/akademie/web.sh"
    "${guest[@]}" bash "$dest/nasazeni/test/akademie/cron.sh"
    "${guest[@]}" bash "$dest/nasazeni/test/akademie/kurz.sh" | tee "$tmp/akademie-kurz.txt"
    "${guest[@]}" bash "$dest/nasazeni/test/akademie/sken.sh" | tee "$tmp/akademie-sken.txt"
    "${guest[@]}" python3 "$dest/nasazeni/test/akademie/rest.py" --pro-komisi | tee "$tmp/akademie-rest.txt"
    "${guest[@]}" bash "$dest/nasazeni/test/akademie/vydani.sh" | tee "$tmp/akademie-vydani.txt"
    "${guest[@]}" python3 "$dest/nasazeni/test/akademie/komise.py" | tee "$tmp/akademie-komise.txt"
    "${guest[@]}" python3 "$dest/nasazeni/test/akademie/predat_spis.py" "$fqdn" | tee "$tmp/akademie-rozhodnuti.txt"
    "${guest[@]}" bash "$dest/nasazeni/test/akademie/prehled.sh" | tee "$tmp/akademie-prehled.txt"
    "${guest[@]}" python3 "$dest/nasazeni/test/akademie/evidence.py" | tee "$tmp/akademie-evidence.txt"
    "${guest[@]}" bash "$dest/nasazeni/test/medusa/rma.sh" | tee "$tmp/reklamace.txt"
    "${guest[@]}" bash "$dest/nasazeni/test/medusa/bubny.sh" | tee "$tmp/bubny.txt"
    "${guest[@]}" bash "$dest/nasazeni/test/medusa/seriova-cisla.sh" | tee "$tmp/seriova-cisla.txt"
    "${guest[@]}" bash "$dest/nasazeni/test/medusa/parovani.sh" | tee "$tmp/parovani.txt"
    "${guest[@]}" bash "$dest/nasazeni/test/medusa/sestav.sh"
    "${guest[@]}" bash "$dest/nasazeni/test/medusa/start.sh" "$fqdn"
    "${guest[@]}" bash "$dest/nasazeni/test/medusa/objednavka.sh" | tee "$tmp/eshop-objednavka.txt"
    "${guest[@]}" bash "$dest/nasazeni/test/hrana/obnov-vstup.sh"
    sudo -n bash nasazeni/test/port-vpn.sh 8451 >/dev/null
    "${guest[@]}" cat /srv/polarita/data/bootstrap-test/test-login/heslo |
        python3 nasazeni/test/akademie/over_vpn.py "$fqdn" --kurz | tee "$tmp/akademie-prihlaseni.txt"
    "${guest[@]}" cat /srv/polarita/data/bootstrap-test/test-login/heslo |
        python3 nasazeni/test/akademie/over_vpn.py "$fqdn" --sso | tee -a "$tmp/akademie-prihlaseni.txt"
    printf 'https://%s:8451/my/\n' "$fqdn" | "${guest[@]}" incus exec -T reditelstvi-test -- sh -ec 'umask 022; cat >/usr/local/share/.akademie-next; mv -T /usr/local/share/.akademie-next /usr/local/share/polarita-akademie-url'
    sudo -n bash nasazeni/test/port-vpn.sh 8450 >/dev/null
    "${guest[@]}" cat /srv/polarita/data/bootstrap-test/test-login/heslo |
        python3 nasazeni/test/medusa/prihlaseni.py "$fqdn" --sklad | tee "$tmp/eshop-prihlaseni.txt"
    printf 'https://%s:8450/app/\n' "$fqdn" | "${guest[@]}" incus exec -T reditelstvi-test -- sh -ec 'umask 022; cat >/usr/local/share/.medusa-next; mv -T /usr/local/share/.medusa-next /usr/local/share/polarita-medusa-url'
    "${guest[@]}" bash "$dest/nasazeni/test/umami/over.sh" | tee "$tmp/umami.txt"
    sudo -n bash nasazeni/test/port-vpn.sh 8449 >/dev/null
    "${guest[@]}" cat /srv/polarita/data/bootstrap-test/test-login/heslo |
        python3 nasazeni/test/umami/over_vpn.py "$fqdn" | tee -a "$tmp/umami.txt"
    printf 'https://%s:8449/\n' "$fqdn" | "${guest[@]}" incus exec -T reditelstvi-test -- sh -ec 'umask 022; cat >/usr/local/share/.umami-next; mv -T /usr/local/share/.umami-next /usr/local/share/polarita-umami-url'
    bash nasazeni/test/ecomail/zkouska.sh "$dest" "$fqdn" "$commit" | tee "$tmp/ecomail.txt"
    "${guest[@]}" bash "$dest/nasazeni/test/web/instalace.sh" | tee "$tmp/web.txt"
    "${guest[@]}" bash "$dest/nasazeni/test/medusa/storefront.sh"
    python3 nasazeni/test/medusa/over_storefront.py "$fqdn" | tee "$tmp/eshop-katalog.txt"
    "${guest[@]}" incus exec -T reditelstvi-test -- touch /usr/local/share/polarita-obchod-overen
    "${guest[@]}" cat /srv/polarita/data/bootstrap-test/test-login/heslo |
        python3 nasazeni/test/web/over_portal.py "https://$fqdn" | tee "$tmp/web-pristup.txt" | tee -a "$tmp/web.txt"
    "${guest[@]}" install -d -m0750 /srv/polarita/workspace/dukazy/blok-09
    "${inc[@]}" file push --project polarita "$tmp/web.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-09/web-$commit.txt"
    "${inc[@]}" file push --project polarita "$tmp/web-pristup.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-09/web-pristup-$commit.txt"
    "${inc[@]}" file push --project polarita "$tmp/eshop-prihlaseni.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-09/eshop-prihlaseni-$commit.txt"
    "${inc[@]}" file push --project polarita "$tmp/eshop-objednavka.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-09/eshop-objednavka-$commit.txt"
    "${inc[@]}" file push --project polarita "$tmp/eshop-katalog.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-09/eshop-katalog-$commit.txt"
    "${inc[@]}" file push --project polarita "$tmp/bubny.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-09/bubny-$commit.txt"
    "${inc[@]}" file push --project polarita "$tmp/seriova-cisla.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-09/seriova-cisla-$commit.txt"
    "${inc[@]}" file push --project polarita "$tmp/parovani.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-09/parovani-$commit.txt"
    "${inc[@]}" file push --project polarita "$tmp/reklamace.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-09/reklamace-$commit.txt"
    "${inc[@]}" file push --project polarita "$tmp/bubny.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-09/bubny-$commit.txt"
    "${inc[@]}" file push --project polarita "$tmp/seriova-cisla.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-09/seriova-cisla-$commit.txt"
    "${inc[@]}" file push --project polarita "$tmp/akademie-prihlaseni.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-09/akademie-prihlaseni-$commit.txt"
    "${inc[@]}" file push --project polarita "$tmp/akademie-spojeni.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-09/akademie-spojeni-$commit.txt"
    "${inc[@]}" file push --project polarita "$tmp/akademie-cache.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-09/akademie-cache-$commit.txt"
    "${inc[@]}" file push --project polarita "$tmp/akademie-kurz.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-09/akademie-kurz-$commit.txt"
    "${inc[@]}" file push --project polarita "$tmp/akademie-sken.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-09/akademie-sken-$commit.txt"
    "${inc[@]}" file push --project polarita "$tmp/akademie-rozhodnuti.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-09/akademie-rozhodnuti-$commit.txt"
    "${inc[@]}" file push --project polarita "$tmp/akademie-komise.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-09/akademie-komise-$commit.txt"
    "${inc[@]}" file push --project polarita "$tmp/akademie-rest.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-09/akademie-rest-$commit.txt"
    "${inc[@]}" file push --project polarita "$tmp/akademie-vydani.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-09/akademie-vydani-$commit.txt"
    "${inc[@]}" file push --project polarita "$tmp/akademie-prehled.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-09/akademie-prehled-$commit.txt"
    "${inc[@]}" file push --project polarita "$tmp/akademie-evidence.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-09/akademie-evidence-$commit.txt"
    "${inc[@]}" file push --project polarita "$tmp/akademie-podklady.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-09/akademie-podklady-$commit.txt"
    "${inc[@]}" file push --project polarita "$tmp/parovani.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-09/parovani-$commit.txt"
    "${inc[@]}" file push --project polarita "$tmp/ecomail.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-09/ecomail-$commit.txt"
    "${inc[@]}" file push --project polarita "$tmp/umami.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-09/umami-$commit.txt"
    "${guest[@]}" python3 "$dest/nasazeni/test/pamet/protokol.py" 09 "$commit" umami ecomail reklamace bubny seriova-cisla parovani akademie-prehled akademie-evidence akademie-rozhodnuti akademie-komise akademie-vydani akademie-rest akademie-sken akademie-kurz akademie-podklady akademie-spojeni akademie-cache akademie-prihlaseni eshop-prihlaseni eshop-objednavka eshop-katalog web-pristup | tee "$tmp/web-predavka.jsonl"
    "${guest[@]}" systemctl start polarita-silverbullet-export.service
    "${guest[@]}" cat /srv/polarita/data/bootstrap-test/test-login/heslo |
        python3 nasazeni/test/silverbullet/zkouska_prihlaseni.py "$fqdn" --predavky "$tmp/web-predavka.jsonl"
}

vykresy() {
    "${guest[@]}" cat /srv/polarita/data/bootstrap-test/test-login/heslo |
        python3 nasazeni/test/inzenyring/prijem.py "https://$fqdn"
    "${guest[@]}" bash "$dest/nasazeni/test/inzenyring/instalace.sh"
    "${guest[@]}" bash "$dest/nasazeni/test/inzenyring/rozpocet/publikuj.sh" | tee "$tmp/rozpocet.txt"
    local rozpocet_spis
    rozpocet_spis=$(cd nasazeni/test/inzenyring && python3 -c 'from prijem import CASE; print(CASE)')
    {
        "${guest[@]}" cat /srv/polarita/data/bootstrap-test/test-login/heslo
        printf '\n'
        "${guest[@]}" incus exec -T postgres-test -- cat "/opt/polarita-inzenyring-test/rozpocty/$rozpocet_spis/current/SHA256SUMS"
    } | python3 nasazeni/test/inzenyring/rozpocet/portal.py "https://$fqdn" | tee -a "$tmp/rozpocet.txt"
    "${guest[@]}" cat /srv/polarita/data/bootstrap-test/test-login/heslo |
        python3 nasazeni/test/inzenyring/revize/spisy_rz.py "https://$fqdn"
    "${guest[@]}" cat /srv/polarita/data/bootstrap-test/test-login/heslo |
        python3 nasazeni/test/inzenyring/over_bilanci.py "https://$fqdn" | tee "$tmp/bilance.txt"
    "${guest[@]}" python3 "$dest/nasazeni/test/inzenyring/rozvadece/pas.py" "$fqdn" | tee "$tmp/vyrobni-pasy.txt"
    "${guest[@]}" python3 "$dest/nasazeni/test/inzenyring/revize/instaluj.py" "$fqdn"
    "${guest[@]}" cat /srv/polarita/data/bootstrap-test/test-login/heslo |
        python3 nasazeni/test/inzenyring/revize/spisy_rz.py "https://$fqdn" --over | tee "$tmp/revizni-zpravy.txt"
    "${guest[@]}" cat /srv/polarita/data/bootstrap-test/test-login/heslo |
        python3 nasazeni/test/inzenyring/rozvadece/over_portal.py "https://$fqdn" | tee -a "$tmp/vyrobni-pasy.txt"
    "${guest[@]}" bash "$dest/nasazeni/test/inzenyring/ocpp/instalace.sh" | tee "$tmp/ocpp.txt"
    "${guest[@]}" cat /srv/polarita/data/bootstrap-test/test-login/heslo |
        python3 nasazeni/test/inzenyring/ocpp/over_portal.py "https://$fqdn" | tee -a "$tmp/ocpp.txt"
    "${guest[@]}" bash "$dest/nasazeni/test/qet/schema.sh" | tee "$tmp/qet-schema.txt"
    "${guest[@]}" bash "$dest/nasazeni/test/cad/offline.sh" | tee "$tmp/cad-vykresy.txt"
    local cad_verze
    cad_verze=$(bash nasazeni/test/cad/offline.sh --revize)
    "${guest[@]}" python3 "$dest/nasazeni/test/cad/tok.py" "$cad_verze" | tee -a "$tmp/cad-vykresy.txt"
    "${guest[@]}" cat /srv/polarita/data/bootstrap-test/test-login/heslo |
        python3 nasazeni/test/inzenyring/zkouska.py "https://$fqdn" | tee "$tmp/dtm-spis.txt"
    cat "$tmp/rozpocet.txt" "$tmp/bilance.txt" "$tmp/ocpp.txt" "$tmp/vyrobni-pasy.txt" "$tmp/revizni-zpravy.txt" "$tmp/qet-schema.txt" "$tmp/dtm-spis.txt" >> "$tmp/cad-vykresy.txt"
    "${inc[@]}" file push --project polarita "$tmp/cad-vykresy.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-10/cad-vykresy-$commit.txt"
    "${guest[@]}" python3 "$dest/nasazeni/test/pamet/protokol.py" 10 "$commit" cad-vykresy
}

registr_dokladu() {
    "${guest[@]}" bash "$dest/nasazeni/test/registry/zkouska.sh" | tee "$tmp/registr-dokladu.txt"
    "${guest[@]}" cat /srv/polarita/data/bootstrap-test/test-login/heslo |
        python3 nasazeni/test/registry/over_portal.py "https://$fqdn" "$tmp/registr-dokladu.txt" >"$tmp/registr-karty.txt"
    cat "$tmp/registr-karty.txt" >>"$tmp/registr-dokladu.txt"
    "${guest[@]}" bash "$dest/nasazeni/test/finance/export.sh" | tee "$tmp/isdoc.txt"
    "${guest[@]}" cat /srv/polarita/data/bootstrap-test/test-login/heslo |
        python3 nasazeni/test/finance/over_portal.py "https://$fqdn" "$tmp/isdoc.txt" | tee -a "$tmp/registr-dokladu.txt"
    cat "$tmp/isdoc.txt" >>"$tmp/registr-dokladu.txt"
    "${guest[@]}" unshare --net sh -ec 'ip link set lo up; exec python3 -B "$1"' -- "$dest/nasazeni/test/finance/zkouska_vypisu.py" | tee -a "$tmp/registr-dokladu.txt"
    "${guest[@]}" install -dm0750 /srv/polarita/workspace/dukazy/blok-11
    "${inc[@]}" file push --project polarita "$tmp/registr-dokladu.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-11/registr-dokladu-$commit.txt"
    "${guest[@]}" python3 "$dest/nasazeni/test/pamet/protokol.py" 11 "$commit" registr-dokladu
}

predani() {
    python3 nasazeni/test/vydani.py "$commit"
    "${guest[@]}" systemctl start polarita-dohled-sber.service
    "${guest[@]}" cat /srv/polarita/data/bootstrap-test/test-login/heslo | python3 nasazeni/test/smoke.py "https://$fqdn" --dohled --paperclip --zulip --decisions --akademie --protokol-komise --termin-akademie | tee "$tmp/vstup-predani.txt"
    "${guest[@]}" install -d -m 0750 /srv/polarita/workspace/dukazy/blok-12
    "${inc[@]}" file push --project polarita "$tmp/vstup-predani.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-12/vstup-predani-$commit.txt"
    "${inc[@]}" file push --project polarita "$tmp/dohled.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-06/dohled-$commit.txt"
    "${inc[@]}" file push --project polarita "$tmp/restic.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-06/restic-$commit.txt"
    "${guest[@]}" python3 "$dest/nasazeni/test/pamet/podklady.py" --predat | tee "$tmp/prenos-dokladu.json"
    "${inc[@]}" file push --project polarita "$tmp/prenos-dokladu.json" "polarita-hq/srv/polarita/workspace/dukazy/blok-08/prenos-dokladu-$commit.json"
    "${guest[@]}" python3 "$dest/nasazeni/test/pamet/predavka_dokladu.py" <"$tmp/prenos-dokladu.json" | tee "$tmp/prenos-dokladu.txt"
    "${inc[@]}" file push --project polarita "$tmp/prenos-dokladu.txt" "polarita-hq/srv/polarita/workspace/dukazy/blok-08/prenos-dokladu-$commit.txt"
    "${guest[@]}" python3 "$dest/nasazeni/test/pamet/protokol.py" 08 "$commit" prenos-dokladu >"$tmp/prenos-do-pameti.jsonl"
    "${guest[@]}" python3 "$dest/nasazeni/test/predani.py" "$commit" "$fqdn"
    "${guest[@]}" python3 "$dest/nasazeni/test/pamet/protokol.py" 12 "$commit" predani-spravci >>"$tmp/prenos-do-pameti.jsonl"
    "${guest[@]}" systemctl start polarita-silverbullet-export.service
    "${guest[@]}" cat /srv/polarita/data/bootstrap-test/test-login/heslo |
        python3 nasazeni/test/silverbullet/zkouska_prihlaseni.py "$fqdn" --predavky "$tmp/prenos-do-pameti.jsonl"
    # Starší vydání vytvořilo přímý vstup. Odstraň ho až po ověření nové cesty.
    if [[ $("${guest[@]}" incus config device get reditelstvi-test portal listen 2>/dev/null || true) == tcp:127.0.0.1:18182 ]]; then
        "${guest[@]}" incus config device remove reditelstvi-test portal
    fi
    "${guest[@]}" sh -ec 'ln -sfn "$1" /srv/polarita/infra/releases/.current-new; mv -Tf /srv/polarita/infra/releases/.current-new /srv/polarita/infra/releases/current' deploy "$dest"
}

kroky=(portal sit hesla postgres sluzby tym trezor databaze paperclip identita firemni_git rozhodnuti metadata obnova_databazi karantena zalohy dohled zulip obnova web vykresy registr_dokladu predani)
over_vstup() {
    "${guest[@]}" cat /srv/polarita/data/bootstrap-test/test-login/heslo | python3 nasazeni/test/smoke.py "https://$fqdn" || return $?
    printf 'Ověřené přihlášení ve VPN: https://%s/ (účet spravce)\n' "$fqdn"
}
source nasazeni/test/prubeh.sh
proved_kroky "${kroky[@]}"
printf 'Ověřené přihlášení ve VPN: https://%s/\n' "$fqdn"
