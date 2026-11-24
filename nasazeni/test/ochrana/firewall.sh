#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $(systemd-detect-virt) == kvm ]]
# Mezizónová pravidla připravil site.sh. Modul potřebujeme pouze na mostu DMZ.
modprobe br_netfilter
sysctl -qw net.bridge.bridge-nf-call-iptables=0 net.bridge.bridge-nf-call-ip6tables=0 net.bridge.bridge-nf-call-arptables=0
ip link set dev dmz_edge type bridge nf_call_iptables 1
# Opakování ponechá aktivní položky i jejich časový limit v rukou bounceru.
nft -f - <<'NFT'
add table ip polarita_crowdsec
add set ip polarita_crowdsec blokovane { type ipv4_addr; flags timeout; }
add chain ip polarita_crowdsec hrana { type filter hook forward priority -30; policy accept; }
flush chain ip polarita_crowdsec hrana
add rule ip polarita_crowdsec hrana oifname "dmz_edge" ip saddr @blokovane ip daddr 10.239.31.12 tcp dport 25 counter drop
add rule ip polarita_crowdsec hrana oifname "dmz_edge" ip saddr @blokovane ip daddr 10.239.31.10 tcp dport 8443 counter drop
add rule ip polarita_crowdsec hrana oifname "dmz_edge" ip saddr @blokovane ip daddr 10.239.31.11 udp dport 3478 counter drop
NFT
