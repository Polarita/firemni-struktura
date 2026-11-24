#!/bin/bash
# Pouze publikované záznamy. Úplný export veřejné zóny poskytne její správce.
set -u
export LC_ALL=C
printf 'Veřejná inventura DNS (%s)\n' "$(date -u --iso-8601=seconds)"
for zone in polarita.cz polarita.eu; do
    printf '\n%s\n' "$zone"
    servers=$(dig +time=3 +tries=1 +short NS "$zone") || { echo 'Delegaci se nepodařilo načíst'; continue; }
    ns=$(awk '/^[[:alnum:].-]+\.$/{print;exit}' <<<"$servers")
    if [[ -z $ns ]]; then echo 'Chybí odpověď NS'; continue; fi
    printf 'Autoritativní server pro měření: %s\n' "$ns"
    dig +time=3 +tries=1 +noall +answer +comments "$zone" DS
    for type in SOA NS A AAAA MX TXT CAA DNSKEY; do
        dig +time=3 +tries=1 +norecurse +noall +answer +comments "@$ns" "$zone" "$type"
    done
    for host in www _dmarc vpn reditelstvi _acme-challenge.reditelstvi; do
        for type in CNAME A AAAA TXT; do
            dig +time=3 +tries=1 +norecurse +noall +answer +comments "@$ns" "$host.$zone" "$type"
        done
    done
done
