#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq ]]
src=$(cd "$(dirname "$0")" && pwd)
work=/srv/polarita/infra/gitea-runner-test
install -d -m 0750 "$work/tofu"
exec 9>"$work/.instalace"
flock 9
exec 8>/run/polarita-test-zatez.lock
flock 8
python3 "$src/runner-podklady.py"
nft -c -f "$src/runner.nft"
install -d -m 0755 /etc/polarita
install -m 0644 "$src/runner-chromium.apparmor" /etc/polarita/runner-chromium.apparmor
install -m 0644 "$src/runner.nft" /etc/polarita/runner.nft
install -m 0644 "$src"/polarita-{runner-sit,gitea-runner}.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now polarita-runner-sit.service
nft -f /etc/polarita/runner.nft
cd "$work/tofu"
install -m 0644 "$src/runner.tf" "$src/../incus/providers.tf" "$src/../incus/.terraform.lock.hcl" .
tofu init -input=false -lockfile=readonly
tofu validate
plan=$(mktemp)
trap 'rm -- "$plan"' EXIT
tofu plan -input=false -out="$plan"
tofu show -json "$plan" | python3 -c '
import json,sys
for item in json.load(sys.stdin).get("resource_changes", []):
    actions=item["change"]["actions"]
    if actions in (["no-op"], ["read"]): continue
    if item["address"] == "incus_instance.runner" and actions in (["create"], ["update"]): continue
    sys.exit("Neočekávaná změna " + item["address"])'
tofu apply -input=false "$plan"
vm=gitea-runner-test
inside=(incus exec -T "$vm" --)
"${inside[@]}" sh -ec 'for i in $(seq 1 60); do if test -S /run/dbus/system_bus_socket && systemctl is-active --quiet systemd-networkd && mountpoint -q /opt/polarita-wheels; then exit 0; fi; sleep 1; done; exit 1'
incus file push --mode=0644 "$src/10-runner.network" "$vm/etc/systemd/network/05-polarita-runner.network"
"${inside[@]}" networkctl reload
"${inside[@]}" networkctl reconfigure eth0
"${inside[@]}" bash -ec '
for i in {1..30}; do if ip -4 -o addr show eth0 | grep -F "10.239.32.14/32" >/dev/null; then break; fi; sleep 1; done
ip -4 route get 10.239.32.13 | grep -F "dev eth0" >/dev/null
[[ -z $(ip -4 route show default) ]]
[[ -z $(ip -6 route show default) ]]
test ! -e /opt/polarita-openbao/agent
test ! -e /run/secrets/polarita-test'
mapfile -t packages < <(python3 -c 'import json,sys; print(*(name+"="+ver for name,ver in json.load(open(sys.argv[1])).items()),sep="\n")' "$src/runner-balicky.json")
bash "$src/../incus/balicky.sh" "$vm" "${packages[@]}"
"${inside[@]}" bash -ec '
getent group pol-ci >/dev/null || groupadd --gid 17308 pol-ci
getent passwd pol-ci >/dev/null || useradd --uid 17308 --gid pol-ci --create-home --home-dir /var/lib/polarita-ci --shell /usr/sbin/nologin pol-ci
test "$(id -u pol-ci)" = 17308
install -d -m 0755 /opt/polarita-runner
git --version
gitleaks version
python3 --version'
bin=/srv/polarita/infra/gitea-test/bin/gitea-runner-6.0.1-linux-amd64
echo "37be79b1e72e31e3e02004ee1d768a0bc23224b9520351f46bb7157de7433fbd  $bin" | sha256sum --check --status
incus file push --mode=0755 "$bin" "$vm/opt/polarita-runner/runner"
apparmor_parser -r -n 'incus-gitea-runner-test_<var-lib-incus>' /etc/polarita/runner-chromium.apparmor
"${inside[@]}" ln -sfn /opt/polarita-prohlizec/chrome-headless-shell-linux64/chrome-headless-shell /usr/local/bin/chromium
"${inside[@]}" /opt/polarita-runner/runner --version
"${inside[@]}" runuser -u pol-ci -- bash -ec '
set -euo pipefail
d=$(mktemp -d)
trap '\''rm -r -- "$d"'\'' EXIT
python3 -m venv "$d/venv"
"$d/venv/bin/pip" --disable-pip-version-check install --no-index --find-links /opt/polarita-wheels markdown pypdf
"$d/venv/bin/python" -c "import markdown, pypdf"
c=/opt/polarita-prohlizec/chrome-headless-shell-linux64/chrome-headless-shell
"$c" --version
if ldd "$c" | grep -F "not found"; then exit 1; fi
echo "<p>Polarita CI</p>" >"$d/test.html"
timeout 60 "$c" --disable-gpu --disable-dev-shm-usage --user-data-dir="$d/chrome" --print-to-pdf="$d/test.pdf" "file://$d/test.html"
"$d/venv/bin/python" -c '\''from pypdf import PdfReader; import sys; assert "Polarita CI" in PdfReader(sys.argv[1]).pages[0].extract_text()'\'' "$d/test.pdf"
'
systemctl enable --now polarita-gitea-runner.service
tofu plan -input=false -detailed-exitcode
