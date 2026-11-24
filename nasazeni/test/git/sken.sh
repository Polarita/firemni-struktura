#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq ]]
src=$(cd "$(dirname "$0")" && pwd)
bash "$src/balicky.sh" gitea-test gitleaks=8.16.0-1build2
repo=/var/lib/gitea/git/spravce/firemni-struktura-test.git
incus exec -T gitea-test -- runuser -u gitea-test -- test -x "$repo/hooks/pre-receive.d/gitea"
incus file push --mode=0644 "$src/gitleaks.toml" gitea-test/etc/polarita-gitea/
incus file push --mode=0755 "$src/pred-prijetim" "gitea-test$repo/hooks/pre-receive.d/.polarita-next"
incus exec -T gitea-test -- mv -T "$repo/hooks/pre-receive.d/.polarita-next" "$repo/hooks/pre-receive.d/polarita-gitleaks"
