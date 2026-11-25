#set page(paper: "a4", margin: 20mm)
#set text(lang: "cs", size: 10.5pt)
#let f = json(bytes(sys.inputs.model))
#let cz(v) = v.replace(".", ",")
#let kc(v) = cz(v) + " Kč"
#set document(title: "Faktura TEST · " + f.cislo)
#text(size: 11pt, fill: rgb("#23546a"))[*POLARITA · TEST*]
#v(3mm)
#text(size: 23pt, weight: "bold")[Faktura #f.cislo]
#parbreak()
Spis #f.spis #h(1fr) Vystaveno #f.datum
#v(8mm)
#grid(columns: (1fr,1fr), [*Dodavatel* \ #f.dodavatel], [*Odběratel* \ #f.odberatel])
#v(9mm)
#table(columns: (1fr,auto,auto,auto,auto), inset: 5pt, stroke: 0.45pt + gray,
       table.header([*Položka*], [*Množství*], [*Cena za MJ*], [*DPH*], [*Základ*]),
       ..f.radky.map(r => (r.popis,cz(r.pocet)+" "+r.jednotka,kc(r.cena),r.sazba+" %",kc(r.zaklad))).flatten())
#align(right)[Základ daně #h(5mm) #kc(f.zaklad) \ DPH #h(5mm) #kc(f.dan) \
  #text(size: 15pt, weight: "bold")[Celkem #h(5mm) #kc(f.celkem)]]
#v(10mm)
#grid(columns: (44mm,1fr), gutter: 5mm, align: horizon,
  image(bytes(f.qr), format: "svg", width: 42mm),
  [*Zkušební QR platba · nehradit* \ Variabilní symbol #f.vs \
   Kód obsahuje modelový účet s kódem banky 0000.])
