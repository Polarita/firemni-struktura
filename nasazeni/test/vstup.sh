#!/bin/bash
# Spouští root na zvoleném uzlu vnějšího clusteru; aplikace zůstává uvnitř VM.
set -euo pipefail
[[ $(hostname -s) == ejpovice ]]
vm=polarita-hq
guest=(incus exec --project polarita "$vm" --)
[[ $("${guest[@]}" hostname -s) == "$vm" ]]
ip=$("${guest[@]}" ip -4 -o addr show dev enp5s0 | awk '{print $4}' | cut -d/ -f1)
vpn=$(tailscale ip -4)
fqdn=$(tailscale status --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))')
[[ $fqdn =~ ^[-a-z0-9.]+\.ts\.net$ ]]
relay=/etc/polarita-test-relay
install -d -m 700 "$relay"
cd "$relay"
if [[ ! -e key ]]; then ssh-keygen -q -t ed25519 -N '' -C polarita-test-relay -f key; fi
# Hostitelský klíč pochází přímo z konzole ověřené VM.
printf '%s %s\n' "$ip" "$("${guest[@]}" cat /etc/ssh/ssh_host_ed25519_key.pub)" >known_hosts
"${guest[@]}" sh -eu -c '
if ! id polarita-relay >/dev/null 2>&1; then
    useradd -m -s /usr/sbin/nologin polarita-relay
fi
install -d -m 700 -o polarita-relay -g polarita-relay /home/polarita-relay/.ssh
'
printf 'restrict,port-forwarding,permitopen="127.0.0.1:18184",command="/bin/false" %s\n' "$(cat key.pub)" |
    "${guest[@]}" sh -c 'umask 077; cat >/home/polarita-relay/.ssh/authorized_keys; chown polarita-relay:polarita-relay /home/polarita-relay/.ssh/authorized_keys'
# Uživatel smí jen místní forwarding na jediný port aplikace.
gateway=$(ip -4 route get "$ip" | awk '{for(i=1;i<=NF;i++) if ($i=="src") print $(i+1)}')
printf '%s\n' 'Match User polarita-relay' "    AllowUsers polarita-relay@$gateway" '    AllowTcpForwarding local' '    AllowStreamLocalForwarding no' '    PermitOpen 127.0.0.1:18184' '    MaxSessions 0' 'Match all' |
    "${guest[@]}" sh -ec 'cat >/etc/ssh/sshd_config.d/60-polarita-relay.conf; sshd -t; systemctl reload ssh'
cat >/etc/systemd/system/polarita-test-tunnel.service <<UNIT
[Unit]
Description=Privatni spojeni k testovacimu reditelstvi
After=network-online.target
[Service]
ExecStart=/usr/bin/ssh -NT -F /dev/null -i $relay/key -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=$relay/known_hosts -o ExitOnForwardFailure=yes -o ServerAliveInterval=20 -o ServerAliveCountMax=3 -L 127.0.0.1:18183:127.0.0.1:18184 polarita-relay@$ip
Restart=always
RestartSec=4
[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable polarita-test-tunnel.service
systemctl restart polarita-test-tunnel.service
curl --retry 8 --retry-all-errors --retry-delay 1 -fsS -o /dev/null http://127.0.0.1:18183/
# Ostatní pravidla Serve se zachovají. Obsazená cesta patří jiné službě.
tailscale serve status --json | python3 -c '
import json, sys
d=json.load(sys.stdin)
web=d.get("Web",{}).get(sys.argv[1]+":443",{}).get("Handlers",{})
tcp=d.get("TCP",{}).get("443",{})
if (tcp and not tcp.get("HTTPS")) or ("/" in web and web["/"].get("Proxy")!="http://127.0.0.1:18183"):
    sys.exit("HTTPS vstup používá jiná služba")
' "$fqdn"
tailscale serve --bg --yes --https=443 http://127.0.0.1:18183
cat >landing.html <<HTML
<!doctype html><html lang="cs"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="0;url=https://$fqdn/"><title>Ředitelství Polarity</title><h1>Ředitelství Polarity</h1><a href="https://$fqdn/">Otevřít zabezpečené přihlášení</a></html>
HTML
cat >landing.cfg <<CFG
global
    maxconn 64
defaults
    mode http
    timeout connect 3s
    timeout client 5s
    timeout server 5s
frontend portal_vpn
    bind $vpn:80 interface tailscale0
    bind $vpn:80 interface lo
    http-request deny unless { hdr(host) -i reditelstvi.polarita.cz reditelstvi.polarita.cz:80 }
    http-request deny unless METH_GET or METH_HEAD
    http-request return status 200 content-type "text/html; charset=utf-8" file $relay/landing.html
CFG
haproxy -c -f "$relay/landing.cfg"
cat >/etc/systemd/system/polarita-test-vstup.service <<UNIT
[Unit]
Description=Vstup do reditelstvi pres firemni VPN
After=tailscaled.service network-online.target
[Service]
ExecStart=/usr/sbin/haproxy -db -f $relay/landing.cfg
Restart=on-failure
RestartSec=5
[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable polarita-test-vstup.service
systemctl restart polarita-test-vstup.service
