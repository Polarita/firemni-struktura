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
    history.replaceState(null, "", "?spis=" + encodeURIComponent(data.case_id));
    byId("cislo").value = data.case_id;
    byId("karta").hidden = false;
    stav.textContent = "Spis je otevřený.";
    byId("prijem").textContent = "";
    byId("sken").value = "";
    byId("prevzate").replaceChildren();
    await ukazPrijem(data.case_id, current);
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
    const code = new URL(location.href).searchParams.get("spis") || location.hash.slice(1);
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
window.addEventListener("popstate", otevriOdkaz);
if (location.search || location.hash) otevriOdkaz();

async function ukazPrijem(kod, current) {
    const res = await fetch("api/sanony/" + encodeURIComponent(kod));
    if (request !== current) return;
    if (!res.ok) {
        byId("prijem").textContent = "Potvrzení se nepodařilo načíst.";
        return;
    }
    const receipts = await res.json();
    if (request !== current) return;
    const list = byId("prevzate");
    list.replaceChildren();
    for (const r of receipts) {
        const li = document.createElement("li");
        const when = timestamp => new Date(timestamp).toLocaleString("cs-CZ");
        li.textContent = "Převzato " + when(r.prijato) + " · termín " + when(r.termin) + " · " + r.bajtu.toLocaleString("cs-CZ") + " B";
        list.append(li);
    }
    if (!receipts.length) list.textContent = "Spis zatím nemá potvrzení.";
}

byId("sanony").addEventListener("submit", async event => {
    event.preventDefault();
    const kod = byId("oznaceni").textContent;
    const file = byId("sken").files[0];
    const current = request;
    if (!file || file.size < 1 || file.size > 64 * 1024 * 1024) {
        byId("prijem").textContent = "Zvolte neprázdné PDF do 64 MiB.";
        return;
    }
    byId("odeslat").disabled = true;
    try {
        const storage = JSON.stringify(["polarita-sanon", kod, file.name, file.size, file.lastModified]);
        const key = sessionStorage.getItem(storage) || crypto.randomUUID();
        sessionStorage.setItem(storage, key);
        byId("prijem").textContent = "Předávám PDF do karantény…";
        const res = await fetch("api/sanony/" + kod + "/" + key, {
            method:"PUT", headers:{"Content-Type":"application/pdf"}, body:file
        });
        if (res.status === 409) {
            sessionStorage.removeItem(storage);
            throw new Error("Obsah se změnil. Zkontrolujte vybraný soubor a odešlete jej znovu.");
        }
        if (!res.ok) throw new Error("Převzetí se nepodařilo potvrdit (HTTP " + res.status + ").");
        const receipt = await res.json();
        if (receipt.case_id !== kod || receipt.priloha !== key) throw new Error("Potvrzení nesouhlasí se spisem.");
        if (request === current) {
            byId("prijem").textContent = "Příjem do karantény potvrzen.";
            await ukazPrijem(kod, current);
        }
    } catch (err) {
        if (request === current) byId("prijem").textContent = err.message;
    } finally {
        byId("odeslat").disabled = false;
    }
});
