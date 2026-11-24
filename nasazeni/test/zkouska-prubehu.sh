#!/bin/bash
# Bez Incusu: použije skutečný řadič a stejné příkazy pro atomické uložení.
set -euo pipefail
umask 077
cd "$(dirname "$0")/../.."
dir=$(mktemp -d)
trap 'rm -rf -- "$dir"' EXIT
stav=$dir/stav
dest=$PWD
prubeh=nasazeni/test/prubeh.py
guest=()
mkdir "$stav"
source nasazeni/test/prubeh.sh

prvni() {
    echo 1 >> "$dir/provedene"
    echo prvni > "$tmp/overeni.txt"
}
druhy() {
    echo 2 >> "$dir/provedene"
    echo druhy >> "$tmp/overeni.txt"
    if [[ -f $dir/prerus ]]; then false | cat; fi
}
treti() {
    echo 3 >> "$dir/provedene"
    [[ $(cat "$tmp/overeni.txt") == $'prvni\ndruhy' ]]
}
over_vstup() { [[ ! -e $dir/porucha ]]; }
beh() (
    set -euo pipefail
    tmp=$(mktemp -d -p "$dir")
    proved_kroky prvni druhy treti
)
test_preruseni() {
    touch "$dir/prerus"
    set +e
    beh
    rc=$?
    set -e
    [[ $rc != 0 && -s $stav/prubeh.json ]]
    cp "$stav/prubeh.json" "$dir/ulozeno"
    if head -c 12 "$dir/ulozeno" | python3 "$prubeh" uloz "$stav/prubeh.json" 2>/dev/null; then exit 1; fi
    cmp "$dir/ulozeno" "$stav/prubeh.json"
    rm "$dir/prerus"
}
cil=revize/vm/pool/vpn/aktivni
test_preruseni
beh
[[ $(cat "$dir/provedene") == $'1\n2\n2\n3' && ! -e $stav/prubeh.json ]]
: > "$dir/provedene"
beh
[[ $(cat "$dir/provedene") == $'1\n2\n3' ]]
for pripad in cil porucha poskozeny; do
    cp "$dir/ulozeno" "$stav/prubeh.json"
    case "$pripad" in
        cil) cil=druha-vm ;;
        porucha) touch "$dir/porucha" ;;
        poskozeny) sed -i 's/prvni/xxxx/g' "$stav/prubeh.json" ;;
    esac
    : > "$dir/provedene"
    beh
    [[ $(cat "$dir/provedene") == $'1\n2\n3' ]]
    cil=revize/vm/pool/vpn/aktivni
    rm -f "$dir/porucha"
done
printf 'Ověřeno přerušení, nedokončený přenos, navázání, nový běh, záměna cíle, oprava vstupu a poškozený záznam.\n'
