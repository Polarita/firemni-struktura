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
rev=761b726dd34fb83930e26aab4e9ac3899aa1fa78
base=https://huggingface.co/Xenova/multilingual-e5-small/resolve/$rev
model() {
    local file=$1 sum=$2 dst=$root/model/${1##*/}
    if ! echo "$sum  $dst" | sha256sum --status -c - 2>/dev/null; then
        curl --proto '=https' -fLsS --retry 3 --max-time 300 "$base/$file" -o "$dst.part"
        echo "$sum  $dst.part" | sha256sum --status -c -
        chmod 0644 "$dst.part"
        mv -T "$dst.part" "$dst"
    fi
}
model tokenizer.json 0b44a9d7b51c3c62626640cda0e2c2f70fdacdc25bbbd68038369d14ebdf4c39
model onnx/model_quantized.onnx f80102d3f2a1229f387d3c81909990d8945513e347b0eab049f7de3c6f98c193
recipe=$(cd "$src" && sha256sum cli.py pamet.py hledani.py uv-requirements.txt zaklad.py | sha256sum | cut -d' ' -f1)
dir=$root/$recipe
install -dm0755 "$dir"
if ! [[ -s $dir/pripraveno ]]; then
    uv=$(bash "$src/../zaklad/uv.sh")
    export UV_CACHE_DIR=/var/cache/polarita-uv/sdk UV_NO_CONFIG=1 UV_NO_PROGRESS=1
    "$uv" venv --allow-existing --no-python-downloads --python /usr/bin/python3 "$dir/sdk"
    "$uv" pip sync --only-binary=:all: --require-hashes --python "$dir/sdk/bin/python" "$src/uv-requirements.txt"
    install -m0644 "$src"/{cli,pamet,hledani,zaklad}.py "$dir/"
    "$dir/sdk/bin/python" -Es -c 'import onnxruntime,psycopg,tokenizers'
    echo "$recipe" >"$dir/pripraveno"
fi
incus exec -T postgres-test -- runuser -u postgres -- psql -Xq -v ON_ERROR_STOP=1 -d db_erp_lhutnik <"$src/index.sql"
python3 "$src/pristup.py"
# Přenes jen role a schválené názvy. Karty obsahující osobní údaje se do Vaultu nekopírují.
seed=$(mktemp -d)
trap 'rm -r -- "$seed"' EXIT
install -dm0755 "$seed/nastroje" "$seed/oddeleni"
python3 - "$src/../../../nastroje/kanon.json" "$seed/nastroje/kanon.json" <<'PYTHON'
import json,sys
from pathlib import Path
data=json.loads(Path(sys.argv[1]).read_text())
rows=[{k:a[k] for k in ("id","sysid","department")} for a in data["agents"]]
Path(sys.argv[2]).write_text(json.dumps({"agents":rows,"company":{"branch":data["company"]["branch"]}}))
PYTHON
for f in "$src"/../../../oddeleni/*.md; do head -n1 "$f" >"$seed/oddeleni/${f##*/}"; done
chmod 0755 "$seed"
runuser -u polarita-pamet -- /usr/bin/python3 -Es "$dir/zaklad.py" "$seed"
ln -sfn "$recipe" "$root/.current-next"
mv -Tf "$root/.current-next" "$root/current"
install -m0755 "$src/spust.sh" /usr/local/sbin/agent_vault
python3 "$src/role.py" "$seed"
ln -sfn /usr/local/sbin/agent_vault /usr/local/bin/agent_vault
python3 "$src/zkouska.py"
