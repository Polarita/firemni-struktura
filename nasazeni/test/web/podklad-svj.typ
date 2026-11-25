#set document(title: "Podklad pro správu objektu", author: "Polarita s.r.o.")
#set page(paper: "a4", margin: 23mm)
#set text(lang: "cs", size: 11pt)
#let d = json(bytes(sys.inputs.at("model")))
#text(size: 11pt, fill: rgb("#285749"))[Polarita s.r.o. · TEST]
= Podklad pro správu objektu
#d.Spravce · #d.Stav

== Modelovaná roční úspora
#text(size: 21pt, weight: "bold")[#d.Uspora Kč]
při snížení odběru o #d.Energie kWh za rok.

#table(columns: (2fr, 1fr), inset: 6pt,
  [Roční odběr společných prostor], [#d.Kwh kWh],
  [Proměnná cena elektřiny], [#d.Cena Kč/kWh],
  [Předpokládané snížení spotřeby], [#d.Procent %],
)
Výpočet násobí roční spotřebu proměnnou cenou a zvoleným procentem úspory. Peněžní výsledek je zaokrouhlený na celé koruny.

== Co projednat na schůzi
#d.RevizniKrok

#d.Riziko

#link(d.Zdroj)[Výklad inspekce práce]

== Návrh zápisu
Správce ověří vstupy proti vyúčtování, doloží stav revize a předloží výboru nebo vedení cenu navržených opatření.

Termín dalšího projednání: #line(length: 45mm)
