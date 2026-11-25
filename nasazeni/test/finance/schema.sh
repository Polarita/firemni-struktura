#!/bin/bash
set -euo pipefail
cache=$1
install -d "$cache"
soubor=$cache/isdoc-invoice-6.0.2.xsd
sha=fb5de36fe7b5517acb8aa0c7950d91f8e28910e63b8cdcaaf7db0b0f4f0420bb
if [[ ! -f $soubor ]] || ! echo "$sha  $soubor" | sha256sum -c --status; then
    tmp=$(mktemp "$cache/.isdoc-XXXXXXXX")
    trap 'rm -f -- "$tmp"' EXIT
    curl -fsSL --retry 3 --max-time 60 --proto '=https' --proto-redir '=https' "https://isdoc.cz/6.0.2/xsd/isdoc-invoice-6.0.2.xsd" -o "$tmp"
    echo "$sha  $tmp" | sha256sum -c --status
    chmod 0644 "$tmp"
    mv -T "$tmp" "$soubor"
fi
printf '%s\n' "$soubor"
