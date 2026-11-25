// Místní protějšek reklamního tagu umožňuje ověřit načtení a pořadí příkazů v TEST.
if (document.getElementById("reklamni-souhlas")?.dataset.reklama === "granted") {
  window.dataLayer.push({event: "polarita_test_reklamni_mereni"});
}
