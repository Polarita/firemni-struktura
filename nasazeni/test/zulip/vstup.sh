#!/bin/bash
# Použije již ověřený soukromý tunel ředitelství a druhý HTTPS port téhož VPN jména.
set -euo pipefail
[[ $(hostname -s) == ejpovice && $EUID == 0 ]]
fqdn=$(tailscale status --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))')
[[ $fqdn =~ ^[a-z0-9.-]+\.ts\.net$ ]]
tailscale serve status --json | python3 -c '
import json,sys
cfg=json.load(sys.stdin)
tcp=cfg.get("TCP",{}).get("8444",{})
web=cfg.get("Web",{}).get(sys.argv[1]+":8444",{}).get("Handlers",{})
if (tcp and not tcp.get("HTTPS")) or (web and web!={"/":{"Proxy":"http://127.0.0.1:18183"}}):
    sys.exit("Port týmového chatu používá jiná služba")' "$fqdn"
tailscale serve --bg --yes --https=8444 http://127.0.0.1:18183
url="https://$fqdn:8444"
curl -fsS --max-time 15 "$url/api/v1/server_settings" | python3 -c '
import json,sys
data=json.load(sys.stdin)
providers=data.get("external_authentication_methods", [])
if (data.get("result")!="success" or not data.get("zulip_version") or
    data.get("realm_name")!="Ředitelství Polarity" or
    not any(p.get("name")=="oidc:polarita" and p.get("login_url","").endswith("/accounts/login/social/oidc/polarita") for p in providers)):
    sys.exit("Zulip ve VPN nepotvrdil server s přihlášením OIDC")
print("Zulip ve firemní VPN odpověděl verzí",data["zulip_version"])'
