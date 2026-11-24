#!/bin/bash
# Znovu použije lokální tunel ředitelství pro službu se samostatným HTTPS portem.
set -euo pipefail
[[ $(hostname -s) == ejpovice && $EUID == 0 ]]
port=${1:?Chybí port}
[[ $port == 8444 || $port == 8445 || $port == 8446 || $port == 8447 ]]
fqdn=$(tailscale status --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))')
[[ $fqdn =~ ^[a-z0-9.-]+\.ts\.net$ ]]
tailscale serve status --json | python3 -c '
import json,sys
cfg=json.load(sys.stdin)
host,port=sys.argv[1:]
tcp=cfg.get("TCP",{}).get(port,{})
web=cfg.get("Web",{}).get(host+":"+port,{}).get("Handlers",{})
if (tcp and not tcp.get("HTTPS")) or (web and web!={"/":{"Proxy":"http://127.0.0.1:18183"}}):
    sys.exit("VPN port používá jiná služba")' "$fqdn" "$port"
tailscale serve --bg --yes --https="$port" http://127.0.0.1:18183 >&2
printf '%s\n' "$fqdn"
