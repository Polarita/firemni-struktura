# polarita-ads-mcp v režimu TEST

Instalace připraví ve firemní Gitea soukromý repozitář správce. Rodičem distribuované verze je commit `207c78119124761554c58cd1b92a4b107f085a11` z Draivix/aidvertaiser, který uvádí licenci MIT. Úplná historie je dostupná přes Git. Výchozí větev obsahuje jen místní server pro testování přes MCP stdio, jeho zkoušku a přesné závislosti.

Google Ads, Meta Ads a Sklik mají oddělené seznamy testovacích konceptů. Každý koncept má identifikátor, název, stav `PAUSED` a pevný modelový strop 100 Kč. Skutečná útrata je 0 Kč. Stejný požadavek lze zopakovat i po restartu. Při změně údajů u již použitého identifikátoru server vrátí chybu.

Search Console, Zboží.cz, Heureka a Ecomail vracejí označené syntetické přehledy. Umami uvádí plánované připojení v bloku 9, marže POAS v bloku 11. Přenos do skutečných účtů a schválení konkrétní placené změny v Decisions patří k pozdějšímu přechodu do provozu.

Spuštění klienta probíhá přes `/usr/local/sbin/polarita-ads-mcp-test` uvnitř `polarita-hq`. MCP komunikuje standardním vstupem a výstupem. Instalační zkouška spouští skutečného MCP klienta dvakrát v uzavřeném síťovém prostoru. Svá data ukládá do dočasného adresáře.
