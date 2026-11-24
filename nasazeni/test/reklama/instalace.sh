#!/bin/bash
set -euo pipefail
umask 022
[[ $(hostname -s) == polarita-hq && $EUID == 0 && $(uname -m) == x86_64 ]]
src=$(cd "$(dirname "$0")" && pwd)
root=/opt/polarita-ads-mcp-test
cache=/var/cache/polarita-reklama-test
state=/srv/polarita/workspace/reklama-test
[[ $(findmnt -no SOURCE -T /srv/polarita/workspace) == polarita_zfs/workspace ]]
[[ $(zfs get -H -o value encryption polarita_zfs/workspace) == aes-256-gcm ]]
install -d -m0755 "$root" /var/lib/polarita-ads-test
install -d -m0700 "$cache"
exec 9>"$cache/instalace.lock"
flock 9
if ! id pol-ads-test >/dev/null 2>&1; then
    useradd --system --user-group --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin pol-ads-test
fi
[[ $(id -gn pol-ads-test) == pol-ads-test && $(getent passwd pol-ads-test | cut -d: -f7) == /usr/sbin/nologin ]]
install -d -m0700 -o pol-ads-test -g pol-ads-test "$state"
python3 "$src/gitea.py"
recipe=$(cd "$src" && sha256sum server.py sdk.lock zkouska.py instalace.sh | sha256sum | cut -d' ' -f1)
dir=$root/$recipe
install -d -m0755 "$dir"
if ! [[ -e $dir/overeno ]]; then
    url=https://files.pythonhosted.org/packages/3d/aa/26d64642d808de4a652579ef950d7cd2d37f080a8babf9c67c6b75fc4c3f/uv-0.13.9-py3-none-manylinux_2_17_x86_64.manylinux2014_x86_64.whl
    wheel=$cache/uv-0.13.9.whl
    if ! [[ -e $wheel ]]; then
        curl --fail --retry 3 --proto '=https' -LsS "$url" -o "$wheel.part"
        echo "d7f459fe4fd247d830351c75686d3996ace3c6f3f728eb0e85a30b7ada0cef19  $wheel.part" | sha256sum -c --status
        mv -T "$wheel.part" "$wheel"
    fi
    echo "d7f459fe4fd247d830351c75686d3996ace3c6f3f728eb0e85a30b7ada0cef19  $wheel" | sha256sum -c --status
    python3 - "$wheel" "$cache/uv" <<'PY'
from zipfile import ZipFile
from pathlib import Path
import sys
with ZipFile(sys.argv[1]) as z:
    dst = Path(sys.argv[2])
    dst.write_bytes(z.read(next(n for n in z.namelist() if n.endswith("/scripts/uv"))))
    dst.chmod(0o700)
PY
    export UV_CACHE_DIR="$cache/sdk" UV_NO_CONFIG=1 UV_NO_PROGRESS=1
    "$cache/uv" venv --allow-existing --no-python-downloads --python /usr/bin/python3 "$dir/sdk"
    "$cache/uv" pip sync --only-binary=:all: --require-hashes --python "$dir/sdk/bin/python" "$src/sdk.lock"
    install -m0644 "$src/server.py" "$src/zkouska.py" "$dir/"
    systemd-run --quiet --pipe --wait --collect -p User=pol-ads-test -p PrivateNetwork=yes -p NoNewPrivileges=yes \
        -p PrivateTmp=yes -p ProtectSystem=strict -p InaccessiblePaths=/srv \
        "$dir/sdk/bin/python" -I "$dir/zkouska.py" "$dir/server.py"
    touch "$dir/overeno"
fi
ln -sfn "$recipe" "$root/.current-next"
mv -Tf "$root/.current-next" "$root/current"
install -m0755 "$src/spust.sh" /usr/local/sbin/polarita-ads-mcp-test
/usr/local/sbin/polarita-ads-mcp-test --zkouska
"$dir/sdk/bin/python" -I "$src/zkouska_vstupu.py"
