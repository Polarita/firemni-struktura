#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
work=/srv/polarita/infra/zulip-test
exec 9>"$work/.organizace"
flock 9
install -m 0644 "$src/zkouska_botu.py" "$work/conf/"
incus exec -T zulip-test -- runuser -u zulip -- /home/zulip/deployments/current/manage.py shell \
    -c 'exec(compile(open("/etc/polarita-zulip/zkouska_botu.py").read(),"/etc/polarita-zulip/zkouska_botu.py","exec"))'
