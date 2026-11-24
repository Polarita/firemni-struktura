#!/bin/bash
set -euo pipefail
src=$(cd "$(dirname "$0")" && pwd)
fqdn=$(bash "$src/../port-vpn.sh" 8444)
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
