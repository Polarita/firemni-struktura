const byId = (id) => document.getElementById(id);
const stav = byId("stav");
const button = byId("zaloz");
const storageKey = "polarita-test-rozpracovane-zalozeni-spisu";

let request = 0;

async function otevri(url, options) {
    const current = ++request;
    byId("karta").hidden = true;
    stav.textContent = "Načítám spis…";
    const response = await fetch(url, options);
    const data = await response.json();
    if (current !== request) return;
    if (!response.ok) throw new Error(data.error || "Požadavek se nezdařil.");
    byId("oznaceni").textContent = data.case_id;
    byId("alias").textContent = data.alias;
    byId("pobocka").textContent = String(data.branch_id);
    byId("cas").textContent = new Date(data.zalozeno).toLocaleString("cs-CZ");
    history.replaceState(null, "", "#" + data.case_id);
    byId("cislo").value = data.case_id;
    byId("karta").hidden = false;
    stav.textContent = "Spis je otevřený.";
}

button.addEventListener("click", async () => {
    button.disabled = true;
    try {
        const id = sessionStorage.getItem(storageKey) || crypto.randomUUID();
        sessionStorage.setItem(storageKey, id);
        await otevri("api/spisy", {method: "POST", headers: {"Content-Type":"application/json"},
            body: JSON.stringify({pozadavek: id, branch_id: 101})});
        sessionStorage.removeItem(storageKey);
    } catch (err) {
        stav.textContent = "Založení se nepodařilo ověřit. Můžete ho zopakovat. " + err.message;
    } finally {
        button.disabled = false;
    }
});

byId("hledani").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
        await otevri("api/spisy/" + encodeURIComponent(byId("cislo").value.trim()));
    } catch (err) {
        stav.textContent = err.message;
    }
});

async function otevriOdkaz() {
    const code = location.hash.slice(1);
    if (!code) {
        ++request;
        byId("karta").hidden = true;
        stav.textContent = "";
        return;
    }
    try {
        await otevri("api/spisy/" + encodeURIComponent(code));
    } catch (err) {
        stav.textContent = err.message;
    }
}
window.addEventListener("hashchange", otevriOdkaz);
if (location.hash) otevriOdkaz();
