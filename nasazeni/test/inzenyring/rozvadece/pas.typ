#set page(paper: "a4", margin: 19mm, footer: context [Ředitelství Polarity · zkušební prostředí #h(1fr) #counter(page).display("1 / 1", both: true)])
#set text(lang: "cs",size: 10pt)
#let m = json(bytes(sys.inputs.model))
#let hlavicka(t) = [
  #text(size: 12pt, weight: "bold")[TEST · pouze pro ověření softwaru]
  #heading(level: 1, t)
  Spis #m.spis · Rozváděč #m.oznaceni · Výrobní číslo #m.cislo
  #parbreak()
]
#hlavicka("Tisková předloha štítku CE")
#block(stroke: 0.7pt, inset: 6mm)[
  *VZOREK · NEPOUŽÍT NA VÝROBEK* \
  Polarita s.r.o. · #m.typ \
  #m.oznaceni · #m.cislo · #m.napeti · #m.proud · #m.kryti \
  #image(bytes(m.qr), format: "svg", width: 40mm) \
  Digitální kniha objektu · #m.spis
]
#pagebreak()
#hlavicka("Výrobní pas rozváděče")
Model skříně #m.skrin \
Modelový den posouzení #m.den · Metodika #m.edice \
Zkušební pravidla #m.pravidla.join(", ").
== Osazení a tepelné ztráty
#table(columns:(auto,1fr,auto),table.header([*Prvek*],[*Popis a výrobní identifikace*],[*Ztráta*]),
  ..m.prvky.map(p => (p.oznaceni,p.popis+" · "+p.sn,p.ztrata_W+" W")).flatten())
== Výpočet oteplení
Interpolace modelové křivky skříně při součtu ztrát #m.teplo.ztrata_W W.
Při okolí #m.okoli °C je oteplení uprostřed #m.teplo.stred_K K a nahoře #m.teplo.vrch_K K.
Teplota nahoře #m.teplo.uvnitr_C °C. Nejnižší modelová mez přístrojů #m.teplo.mez_C °C.
#pagebreak()
#hlavicka("Protokol ověření návrhu")
Podklady vzoru S1. Záznamy níže popisují modelové ověření pro zkoušku generátoru.
#for r in m.navrh [#parbreak() *#r.bod* · #r.zapis]
#pagebreak()
#hlavicka("Protokol kusového ověření")
Hodnoty převzaté ze zkušebního kusového protokolu S1.
#for r in m.kus [#parbreak() *#r.bod* · #r.zapis]
#pagebreak()
#hlavicka("Návrh EU prohlášení o shodě")
Výrobce ve vzoru: Polarita s.r.o. \
Určené použití ve vzoru: #m.pouziti \
Modelové podklady: #m.pravidla.join(", ") · #m.edice.
#parbreak()
Dokument čeká na výběr použitelných předpisů a norem pro skutečný výrobek, odborné posouzení a podpis výrobce. Tento vzorek neopravňuje k označení výrobku ani k předání do provozu.
