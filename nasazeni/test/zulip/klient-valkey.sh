#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
work=/srv/polarita/infra/zulip-test
install -d -m 0755 "$work/conf"
tmp=$(mktemp -d "$work/.klient-XXXXXXXX")
trap 'rm -r -- "$tmp"' EXIT
modules=(zerver/lib/redis_utils.py zproject/backends.py)
mkdir -p "$tmp/zerver/lib" "$tmp/zproject"
tar -xf "$work/zdroje/zulip-server-13.3.tar.gz" --strip-components=1 -C "$tmp" \
    zulip-server-13.3/zerver/lib/redis_utils.py zulip-server-13.3/zproject/backends.py
cd "$tmp"
sha256sum -c <<'UPSTREAM'
96183681492a8c5295fcc6588c47c4ecaaec478c12ca6f135677e2b9761a7203  zerver/lib/redis_utils.py
1c7f5a9ce395969f9150786b22a540c30a2fb29453db19bda703da7a4ddecd80  zproject/backends.py
UPSTREAM
git apply --unidiff-zero "$src/redis-13.3.patch" "$src/oidc-valkey-13.3.patch"
sha256sum -c <<'PATCHED'
addcc82d55a89680b0c9e3ccb50974d727753007a0e4cce20f5e1cdf751d7f42  zerver/lib/redis_utils.py
69f76653777b14a11665a4aaab16d3f61ab1d0a8566478374e7a1d5c325d47e4  zproject/backends.py
PATCHED
python3 -m py_compile "${modules[@]}"
install -m 0644 "${modules[@]}" "$work/conf/"
