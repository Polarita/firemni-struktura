#!/bin/bash
set -euo pipefail
[[ $(hostname -s) == polarita-hq && $EUID == 0 ]]
src=$(cd "$(dirname "$0")" && pwd)
db=(incus exec -T postgres-test -- runuser -u postgres -- psql -Xqw -v ON_ERROR_STOP=1 -d db_eshop)
"${db[@]}" <"$src/seriova-cisla.sql" >/dev/null
"${db[@]}" <"$src/seriova-cisla-test.sql"
echo 'Příjem a výdej testovacího kusu kontrolují S/N a dodavatelskou záruku. Chybný sken a výdej při propadlé záruce byly odmítnuty.'
echo 'Rozváděč zůstal ve skladu bez dokladů i se samotným pasem. Po doplnění evidence štítku CE prošel jediný výdej a opakování zachovalo stejný pohyb.'
