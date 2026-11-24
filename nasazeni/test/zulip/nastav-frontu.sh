#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
inside=(incus exec -T zulip-fronta-test --)
"${inside[@]}" install -d -m 0755 /usr/local/lib/polarita-zulip /etc/sasl2
incus file push --mode=0644 "$src/pristup-fronty.py" zulip-fronta-test/usr/local/lib/polarita-zulip/
incus file push --mode=0644 "$src"/polarita-pristup-fronty.{service,path} zulip-fronta-test/etc/systemd/system/
"${inside[@]}" bash -se <<'INNER'
set -euo pipefail
cat >/etc/sasl2/memcached.conf <<'SASL'
pwcheck_method: auxprop
auxprop_plugin: sasldb
sasldb_path: /run/polarita-zulip-fronta/sasldb2
mech_list: plain
SASL
cat >/etc/memcached.conf <<'MEMCACHED'
-m 32
-p 11211
-u memcache
-l 10.239.32.17
-U 0
-S
-B binary
-c 64
MEMCACHED
systemctl daemon-reload
systemctl enable --now polarita-pristup-fronty.path
systemctl start polarita-pristup-fronty.service
systemctl restart memcached
systemctl is-active rabbitmq-server memcached
INNER
