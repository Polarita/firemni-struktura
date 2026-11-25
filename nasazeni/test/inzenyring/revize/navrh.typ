#set text(lang: "cs", size: 10pt)
#set page(paper: "a4", margin: 19mm, footer: context align(right)[TEST · #counter(page).display("1 / 1", both: true)])
#let m = json(bytes(sys.inputs.model))
#let negative = m.stav == "navrh-zaporny"
#text(size: 11pt)[Ředitelství Polarity · zkušební prostředí]
= Návrh revizní zprávy
#text(size: 15pt, weight: "bold", fill: if negative { rgb("902425") } else { rgb("205841") })[
  #if negative [NÁVRH — NESCHOPNO BEZPEČNÉHO PROVOZU] else [NÁVRH — SCHOPNO BEZPEČNÉHO PROVOZU]
]
#parbreak()
Cvičný dokument pro přezkoušení softwaru. Vztahuje se výhradně na modelová měření.
#parbreak()
Spis #m.spis · Projekt #m.projekt · Den měření #m.den \
Zkušební metodika #m.metodika · Určeno k posouzení revizním technikem
== Naměřené hodnoty
#table(columns: (auto, 1fr, auto, auto, auto), align: (left,left,right,right,left),
  table.header([*Bod*], [*Obvod*], [*Hodnota*], [*Mez*], [*Výsledek*]),
  ..m.vysledky.map(r => (r.bod, r.obvod, r.hodnota+" "+r.jednotka,
    (if r.porovnani=="max" { "≤ " } else { "≥ " })+r.mez, if r.vyhovel { "Vyhověl" } else { "Závada" })).flatten())
#if negative [
  == Zjištěné závady
  #for r in m.vysledky.filter(r => not r.vyhovel) [
    *#r.bod · #r.obvod* · #r.ustanoveni \
    Naměřeno #r.hodnota #r.jednotka. Návrh termínu odstranění: #r.navrh_lhuty.
    #parbreak()
  ]
]
== Výrobní pas použitého rozváděče
#m.pas.vyrobni_cislo · Den posouzení #m.pas.den · #link(m.pas.kniha)[Digitální kniha objektu] \
SHA-256 pasu a štítku: #text(size: 8pt)[#m.pas.pdf_sha256]
== Měřidla a kalibrační doklady
#for r in m.vysledky [#r.bod · #r.pristroj · #r.kalibracni_list #linebreak()]
Předání do provozu je zablokované. Dokument čeká na odborné posouzení.
