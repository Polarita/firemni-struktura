#!/bin/sh
set -eu
# Incus vytváří /etc/hosts při startu OCI. Zachovej jeho obsah a připoj jméno z certifikátu PostgreSQL.
name=postgres.polarita.test
address=10.239.33.12
found=$(awk -v name="$name" '{for (i=2;i<=NF && $i !~ /^#/;i++) if ($i==name) print $1}' /etc/hosts)
if [ "$found" = "$address" ]; then exit 0; fi
[ -z "$found" ] || { echo "Jméno PostgreSQL už má jinou adresu." >&2; exit 1; }
file=$(mktemp /run/postgres-hosts.XXXXXX)
trap 'rm -f "$file"' EXIT
cat /etc/hosts >"$file"
printf '\n%s %s\n' "$address" "$name" >>"$file"
chmod 0644 "$file"
mount --bind "$file" /etc/hosts
