#!/bin/bash
# Připnuté schéma OASIS UBL 2.1 a obchodní pravidla OpenPeppol BIS Billing 3.0.22.
set -euo pipefail
cache=$1
install -d "$cache"
exec 9>"$cache/.priprava"
flock 9
rev=$(sha256sum "$0" | cut -d' ' -f1)
dest=$cache/$rev
if [[ -d $dest ]]; then
    (cd "$dest" && sha256sum -c --status SHA256SUMS)
    printf '%s\n' "$dest"
    exit 0
fi
tmp=$(mktemp -d "$cache/.peppol-XXXXXXXX")
trap 'rm -rf -- "$tmp"' EXIT
cd "$tmp"
nacti() {
    local nazev=$1 otisk=$2 url=$3
    curl -fsSL --retry 3 --max-time 180 --proto '=https' --proto-redir '=https' "$url" -o "$nazev"
    echo "$otisk  $nazev" | sha256sum -c --status
}
maven=https://repo.maven.apache.org/maven2
rules=https://raw.githubusercontent.com/OpenPEPPOL/peppol-bis-invoice-3/38d693d71d28d813781323a6ca97324edcc4d239/rules/sch
nacti saxon.jar 491d8edf4ec811d15c2b2417b007218b9b938f15e4dfbad004025beb4e70e960 "$maven/net/sf/saxon/Saxon-HE/10.9/Saxon-HE-10.9.jar"
nacti schxslt.jar 4f4f21edab7b37f96ad59ae12a344d3510f1092ac46b6d81a4efa0120b73cb58 "$maven/name/dmaus/schxslt/schxslt/1.10.1/schxslt-1.10.1.jar"
nacti ubl.zip 60b80d76394a8a2add90723ecb8e0e2e9d826775de9749df37a72d60703f86ed https://docs.oasis-open.org/ubl/os-UBL-2.1/UBL-2.1.zip
nacti peppol.sch f637444fab75a6da7e5004f94a6de8e71383ef5658dafe6c68925103b17ea148 "$rules/PEPPOL-EN16931-UBL.sch"
nacti cen.sch 268d4f7a2688676695e6c69cba6fba69a6802604fee12cb544a6b30ff09555a3 "$rules/CEN-EN16931-UBL.sch"
python3 - <<'PY'
from zipfile import ZipFile
for file,folder,ext in (("ubl.zip","xsd/",".xsd"),("schxslt.jar","xslt/2.0/",".xsl")):
    with ZipFile(file) as archive:
        for path in archive.namelist():
            if path.startswith(folder) and path.endswith(ext):
                archive.extract(path)
PY
for set in peppol cen; do
    java -Xmx256m -cp saxon.jar net.sf.saxon.Transform "-s:$set.sch" -xsl:xslt/2.0/pipeline-for-svrl.xsl "-o:$set.xsl"
done
rm -r -- ubl.zip schxslt.jar xslt
find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum >SHA256SUMS
mv -T "$tmp" "$dest"
printf '%s\n' "$dest"
