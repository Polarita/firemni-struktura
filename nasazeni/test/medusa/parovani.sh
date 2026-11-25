#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
db=(incus exec -T postgres-test -- runuser -u postgres -- psql -Xqw -v ON_ERROR_STOP=1 -d db_eshop)
"${db[@]}" < "$src/parovani.sql" >/dev/null
"${db[@]}" < "$src/parovani-test.sql"
echo 'Sklad porovnal objednávku, příjemky a faktury včetně množství, měny, jednotkové ceny a samostatného PHE. Neshodné podklady nepřipsaly materiál.'
echo 'Ze tří dodacích řádků přijal 10 kusů dvěma pohyby. Opakovaný sken zachoval zůstatek. Skladový účet nemůže vystavit dodavatelskou fakturu ani objednávku.'
