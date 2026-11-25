#!/bin/bash
set -euo pipefail
umask 022
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
root=/opt/polarita-agent-vault
install -dm0755 "$root" "$root/model"
exec 9>/run/polarita-agent-vault-instalace.lock
flock 9
[[ $(findmnt -no SOURCE --mountpoint /srv/polarita/vault) == polarita_zfs/vault ]]
if ! [[ $# == 0 || ( $# == 1 && $1 == --aktualizuj-cli ) ]]; then exit 2; fi
if [[ $# == 1 ]]; then
    [[ -x $root/current/sdk/bin/python && -x /usr/local/bin/agent_vault ]]
fi
rev=761b726dd34fb83930e26aab4e9ac3899aa1fa78
base=https://huggingface.co/Xenova/multilingual-e5-small/resolve/$rev
model() {
    local file=$1 sum=$2 dst=$root/model/${1##*/}
    if [[ ! -f $dst ]] || ! echo "$sum  $dst" | sha256sum --status -c - >/dev/null 2>&1; then
        curl --proto '=https' -fLsS --retry 3 --max-time 300 "$base/$file" -o "$dst.part"
        echo "$sum  $dst.part" | sha256sum --status -c -
        chmod 0644 "$dst.part"
        mv -T "$dst.part" "$dst"
    fi
}
model tokenizer.json 0b44a9d7b51c3c62626640cda0e2c2f70fdacdc25bbbd68038369d14ebdf4c39
model onnx/model_quantized.onnx f80102d3f2a1229f387d3c81909990d8945513e347b0eab049f7de3c6f98c193
recipe=$(cd "$src" && sha256sum cli.py pamet.py doklady.py hledani.py uv-requirements.txt zaklad.py | sha256sum | cut -d' ' -f1)
dir=$root/$recipe
install -dm0755 "$dir"
if ! [[ -s $dir/pripraveno ]]; then
    uv=$(bash "$src/../zaklad/uv.sh")
    export UV_CACHE_DIR=/var/cache/polarita-uv/sdk UV_NO_CONFIG=1 UV_NO_PROGRESS=1
    "$uv" venv --allow-existing --no-python-downloads --python /usr/bin/python3 "$dir/sdk"
    "$uv" pip sync --only-binary=:all: --require-hashes --python "$dir/sdk/bin/python" "$src/uv-requirements.txt"
    install -m0644 "$src"/{cli,pamet,doklady,hledani,zaklad}.py "$dir/"
    "$dir/sdk/bin/python" -Es -c 'import onnxruntime,psycopg,tokenizers'
    echo "$recipe" >"$dir/pripraveno"
fi
aktivuj_cli() {
    "$dir/sdk/bin/python" -Es "$dir/cli.py" prijmi-doklady --help >/dev/null
    ln -sfn "$recipe" "$root/.current-next"
    mv -Tf "$root/.current-next" "$root/current"
    install -m0755 "$src/spust.sh" /usr/local/sbin/.agent_vault-next
    mv -Tf /usr/local/sbin/.agent_vault-next /usr/local/sbin/agent_vault
}
if [[ $# == 1 ]]; then
    aktivuj_cli
    exit 0
fi
incus exec -T postgres-test -- runuser -u postgres -- psql -Xq -v ON_ERROR_STOP=1 -d db_erp_lhutnik <"$src/index.sql"
python3 "$src/pristup.py"
install -m0644 "$src"/polarita-vault-pg.{service,socket} /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now polarita-vault-pg.socket
# Účet znalostí čte výřez provozní charty a registr rolí.
seed=$(mktemp -d)
trap 'rm -r -- "$seed"' EXIT
python3 "$dir/zaklad.py" --priprav "$src/../../.." "$seed"
chmod 0755 "$seed"
runuser -u polarita-pamet -- /usr/bin/python3 -Es "$dir/zaklad.py" "$seed"
aktivuj_cli
python3 "$src/role.py" "$seed"
ln -sfn /usr/local/sbin/agent_vault /usr/local/bin/agent_vault
python3 "$src/zkouska.py" "$seed/oddeleni"
dest=$(cd "$src/../../.." && pwd)
python3 "$src/puvod.py" "$dest"
rev=${dest##*/}
[[ $rev =~ ^[0-9a-f]{40}$ ]]
printf 'Ověřeno v TEST na polarita-hq. Znalostní účet 11001 ve stavu SHADOW přečetl schválené podklady a měl zablokován zápis. Role 17005 uložila předávku a ADR. Český dotaz našel odpovědný útvar přes místní E5 a PostgreSQL pgvector. Zdroj instalační revize %s je ověřený proti soukromé Gitea.
' "$rev" |
    /usr/local/sbin/agent_vault log "overeni-pameti-$rev"
