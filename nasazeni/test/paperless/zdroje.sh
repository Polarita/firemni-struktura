#!/bin/bash
# Připraví obraz vydavatele a českou sadu OCR pro pozdější start v polarita-hq.
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
work=/srv/polarita/infra/paperless-test/zdroje
install -dm0755 "$work"
cd "$work"
exec 9>.priprava
flock 9
ces=934bcaf97ef3348413263331131c9fa7f55f30db333c711929c124fb635f7e1b
if ! [[ -f ces.traineddata ]] || ! printf '%s  ces.traineddata\n' "$ces" | sha256sum --check --status; then
    model=$(mktemp -p "$work" .ces-XXXXXXXX)
    trap 'rm -f -- "$model"' EXIT
    curl --proto '=https' --fail --silent --show-error --location --retry 3 --max-time 120 \
        'https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/87416418657359cb625c412a48b6e1d6d41c29bd/ces.traineddata' -o "$model"
    printf '%s  %s\n' "$ces" "$model" | sha256sum --check --status
    chmod 0644 "$model"
    mv -T "$model" ces.traineddata
fi
image=paperless-ngx/paperless-ngx@sha256:f477d12a1ff8740d9a32bccc50814cd7740bf00d5e2694c294ae0334bb956539
alias=polarita-paperless-3.5.1
if ! incus image info "$alias" >/dev/null 2>&1; then
    exec 8>/run/polarita-test-zatez.lock
    flock 8
    incus image copy "ghcr:$image" local: --alias "$alias"
fi
[[ $(incus image get-property "$alias" id) == "$image" ]]
[[ $(incus image get-property "$alias" oci.source) == https://github.com/paperless-ngx/paperless-ngx ]]
[[ $(incus image get-property "$alias" oci.revision) == 35b0439195bbdb87a6d519152e6782abe0720c3b ]]
printf 'Paperless-ngx 3.5.1 má ověřený obraz pro linux/amd64 a ověřený český jazykový soubor Tesseractu.\n'
