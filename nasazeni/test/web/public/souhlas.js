// Místní brána souhlasu pro reklamní měření v TEST.
(() => {
  const panel = document.getElementById("reklamni-souhlas");
  if (!panel) return;
  const status = panel.querySelector("output");
  const key = "polarita.web-test.reklama.v1";
  let tag;
  let previous;
  try { previous = localStorage.getItem(key); } catch { /* Souhlas pak platí jen na stránce. */ }

  window.dataLayer = window.dataLayer || [];
  function gtag() { window.dataLayer.push(arguments); }
  function consent(action, marketing) {
    const ad = marketing ? "granted" : "denied";
    gtag("consent", action, {
      ad_storage: ad, ad_user_data: ad, ad_personalization: ad, analytics_storage: "denied"
    });
  }
  function apply(choice) {
    const active = choice === "granted";
    consent("update", active);
    panel.dataset.reklama = active ? "granted" : "denied";
    status.textContent = active ? "Reklamní měření je povolené." : "Reklamní měření je vypnuté.";
    if (active && !tag) {
      tag = document.createElement("script");
      tag.src = "/web-test/reklama-test.js";
      document.head.append(tag);
    } else if (!active && tag) {
      tag.remove();
      tag = undefined;
    }
  }
  consent("default", false);
  if (previous === "granted" || previous === "denied") apply(previous);
  for (const button of panel.querySelectorAll("button[data-volba]")) {
    button.addEventListener("click", () => {
      const choice = button.dataset.volba;
      try { localStorage.setItem(key, choice); } catch { /* Volba funguje i bez úložiště. */ }
      apply(choice);
    });
  }
  window.addEventListener("storage", event => {
    if (event.key === key || event.key === null) apply(event.newValue === "granted" ? "granted" : "denied");
  });
  panel.hidden = false;
})();
