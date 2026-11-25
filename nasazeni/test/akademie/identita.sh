#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
host=${1:?Chybí název TEST}
[[ $host =~ ^[a-z0-9.-]+[.]ts[.]net$ ]]
inside=(incus exec -T akademie-test --)
exec 8>/run/polarita-akademie-identita.lock
flock 8
tmp=$(mktemp)
trap 'unlink "$tmp"' EXIT
incus exec -T gitea-test -- cat /etc/polarita-gitea/git-ca.crt >"$tmp"
openssl x509 -noout -checkend 0 -in "$tmp" >/dev/null
incus file push --mode=0644 "$tmp" akademie-test/usr/local/share/ca-certificates/polarita-oidc.crt
"${inside[@]}" update-ca-certificates
"${inside[@]}" env POLARITA_AKADEMIE_HOST="$host" php8.4 <<'PHP'
<?php
$path = '/etc/hosts';
$tag = '# polarita-akademie-oidc';
$entries = array_filter(file($path, FILE_IGNORE_NEW_LINES), fn($line) => !str_ends_with($line, $tag));
$entries[] = '10.239.32.13 ' . getenv('POLARITA_AKADEMIE_HOST') . ' ' . $tag;
if (file_put_contents($path, implode("\n", $entries) . "\n", LOCK_EX) === false) {
    throw new RuntimeException('Nelze zapsat adresu identity v Akademii.');
}
PHP
bash "$src/../git/obnov-proxy.sh"
python3 "$src/../identita/sluzba_oidc.py" "$host" moodle
"${inside[@]}" env POLARITA_AKADEMIE_HOST="$host" php8.4 <<'PHP'
<?php
$origin = 'https://' . getenv('POLARITA_AKADEMIE_HOST');
$issuer = $origin . '/identita/realms/polarita';
$request = curl_init($issuer . '/.well-known/openid-configuration');
curl_setopt_array($request, [CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => 20]);
$body = curl_exec($request);
if ($body === false || curl_getinfo($request, CURLINFO_RESPONSE_CODE) !== 200) {
    throw new RuntimeException('Kontejner Akademie neověřil metadata přes HTTPS.');
}
$doc = json_decode($body, true, flags: JSON_THROW_ON_ERROR);
if (($doc['issuer'] ?? '') !== $issuer) {
    throw new RuntimeException('Nesouhlasí identita vydavatele.');
}
foreach (['authorization_endpoint' => 'auth', 'token_endpoint' => 'token', 'userinfo_endpoint' => 'userinfo', 'jwks_uri' => 'certs'] as $field => $path) {
    if (($doc[$field] ?? '') !== "$issuer/protocol/openid-connect/$path") {
        throw new RuntimeException('Metadata neposkytla očekávanou cestu realmu.');
    }
}
curl_setopt($request, CURLOPT_URL, $origin . '/git/');
if (curl_exec($request) === false || curl_getinfo($request, CURLINFO_RESPONSE_CODE) !== 403) {
    throw new RuntimeException('Interní vstup nepotvrdil odmítnutí Gitu pro Akademii.');
}
echo "Kontejner Moodle ověřil TLS a koncové body Keycloaku. Soukromý Git přístup z Akademie odmítl.\n";
PHP
