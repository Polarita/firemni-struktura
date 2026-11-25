const byId = (id) => document.getElementById(id);
const stav = byId("stav");
const button = byId("zaloz");
const storageKey = "polarita-test-rozpracovane-zalozeni-spisu";

let request = 0;
let nacteniOsy = 0;
let dalsiPozice = null;

async function otevri(url, options) {
    const current = ++request;
    byId("karta").hidden = true;
    byId("osa").open = false;
    byId("udalosti").replaceChildren();
    byId("stav-osy").textContent = "";
    byId("starsi").hidden = true;
    dalsiPozice = null;
    stav.textContent = "Načítám spis…";
    const response = await fetch(url, options);
    const data = await response.json();
    if (current !== request) return;
    if (!response.ok) throw new Error(data.error || "Požadavek se nezdařil.");
    byId("oznaceni").textContent = data.case_id;
    byId("alias").textContent = data.alias;
    byId("pobocka").textContent = String(data.branch_id);
    byId("cas").textContent = new Date(data.zalozeno).toLocaleString("cs-CZ");
    const urlSpisu = new URL(location.href);
    const otevritKnihu = urlSpisu.searchParams.get("spis") === data.case_id && (urlSpisu.searchParams.get("oddil") === "kniha" || urlSpisu.hash === "#kniha-objektu");
    history.replaceState(null, "", "?spis=" + encodeURIComponent(data.case_id) + (otevritKnihu ? "&oddil=kniha#kniha-objektu" : ""));
    byId("cislo").value = data.case_id;
    byId("karta").hidden = false;
    stav.textContent = "Spis je otevřený.";
    byId("prijem").textContent = "";
    byId("sken").value = "";
    byId("prevzate").replaceChildren();
    byId("kniha").reset();
    byId("zapis-revize").hidden = true;
    byId("zapis-revize").open = false;
    byId("stav-knihy").textContent = "";
    byId("terminy").replaceChildren();
    byId("vyrobni-cisla").hidden = !data.rozvadece?.length;
    byId("seznam-rozvadecu").replaceChildren(...(data.rozvadece || []).map(row => {
        const item = document.createElement("li");
        item.textContent = row.oznaceni + " · " + row.vyrobni_cislo;
        if (row.pas) {
            const odkaz = document.createElement("a");
            odkaz.href = "api/pasy/" + encodeURIComponent(data.case_id) + "/" + encodeURIComponent(row.vyrobni_cislo) + "/vyrobni-pas.pdf";
            odkaz.download = row.vyrobni_cislo + "-pas-test.pdf";
            odkaz.textContent = "Stáhnout výrobní pas a štítek (TEST, PDF)";
            item.append(" · ", odkaz);
        }
        return item;
    }));
    byId("revizni-navrh").hidden = !data.revizni_navrh;
    if (data.revizni_navrh) {
        const revize = data.revizni_navrh;
        const vysledek = revize.stav === "navrh-zaporny" ? "Záporný návrh. Závady: " + revize.zavady.join(", ") : "Kladný návrh.";
        byId("vysledek-revize").textContent = vysledek + " Čeká na odborné posouzení. Předání do provozu je zablokované.";
        byId("revize-pdf").href = "api/revize/" + encodeURIComponent(data.case_id) + "/navrh.pdf";
        const pasRevize = byId("revize-pas");
        pasRevize.hidden = !revize.vydani_pasu;
        if (revize.vydani_pasu) {
            pasRevize.href = ["api/pasy", data.case_id, revize.vyrobni_cislo, revize.vydani_pasu, "vyrobni-pas.pdf"].join("/");
            pasRevize.download = revize.vyrobni_cislo + "-podklad-revize.pdf";
        }
        byId("revize-rozhodnuti").href = revize.rozhodnuti;
    }
    byId("rozpocet").hidden = !data.ma_rozpocet;
    for (const format of ["xc4", "xlsx"]) {
        byId(format).href = "api/rozpocty/" + encodeURIComponent(data.case_id) + "/nabidka." + format;
    }
    ukazBilanci(data.bilance_EV);
    byId("ocpp").hidden = true;
    byId("vykopy").hidden = true;
    byId("trasy").replaceChildren();
    await Promise.all([ukazVykopy(data.case_id, current), ukazPrijem(data.case_id, current), ukazKnihu(data.case_id, current), ukazOcpp(data.case_id, current)]);
    if (otevritKnihu && current === request) byId("kniha-objektu").scrollIntoView();
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

function ukazBilanci(bilance) {
    byId("dlm").hidden = !bilance;
    if (!bilance) return;
    const cislo = value => Number(value).toLocaleString("cs-CZ", {maximumFractionDigits: 12});
    const stav = bilance.pretizene_faze.length
        ? "Přetížení " + bilance.pretizene_faze.join(", ") + ". Příděl pro nabíjení je nulový."
        : "Zatížení všech fází se vejde do limitu.";
    byId("dlm-souhrn").textContent = bilance.metodika + " · " + bilance.den + " · Soudobý příkon "
        + cislo(bilance.soudoby_prikon_W) + " W. " + stav;
    byId("dlm-faze").replaceChildren(...Object.entries(bilance.faze).map(([faze, hodnoty]) => {
        const tr = document.createElement("tr");
        for (const udaj of [faze, cislo(hodnoty.soudoby_prikon_W) + " W", hodnoty.prideleno_EV_A + " A",
                 cislo(hodnoty.rezerva_po_EV_W) + " W"]) tr.insertCell().textContent = udaj;
        return tr;
    }));
    byId("dlm-vozidla").textContent = Object.entries(bilance.vozidla_A)
        .map(([vozidlo, proud]) => vozidlo + " · " + proud + " A").join(", ");
}

function odkazNaDokument(res, id) {
    const label = "Dokument " + id;
    const archive = res.headers.get("X-Polarita-Archiv");
    if (!archive || !Number.isSafeInteger(id) || id < 1) return document.createTextNode(label);
    const link = document.createElement("a");
    link.href = new URL("documents/" + id + "/details", archive).href;
    link.textContent = label;
    return link;
}

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
    const doklad = byId("doklad");
    const vybrano = doklad.value;
    doklad.replaceChildren();
    for (const r of receipts) {
        const li = document.createElement("li");
        const when = timestamp => new Date(timestamp).toLocaleString("cs-CZ");
        li.textContent = "Převzato " + when(r.prijato) + " · termín " + when(r.termin) + " · " + r.bajtu.toLocaleString("cs-CZ") + " B";
        const states = {"v-karantene":"v karanténě", "odmitnuto":"karanténa odmítla přílohu",
            "ocr-hotovo":"uloženo v archivu, OCR dokončeno", "ke-kontrole":"uloženo v archivu, OCR vyžaduje kontrolu"};
        if (states[r.stav]) li.textContent += " · " + states[r.stav];
        list.append(li);
        if (r.dokument && ["ocr-hotovo", "ke-kontrole"].includes(r.stav)) {
            li.append(" · ", odkazNaDokument(res, r.dokument));
            doklad.add(new Option("Dokument " + r.dokument + " · " + when(r.prijato), r.priloha));
        }
    }
    if ([...doklad.options].some(option => option.value === vybrano)) doklad.value = vybrano;
    byId("zapis-revize").hidden = !doklad.options.length;
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
            await Promise.all([ukazPrijem(kod, current), obnovOsu()]);
        }
    } catch (err) {
        if (request === current) byId("prijem").textContent = err.message;
    } finally {
        byId("odeslat").disabled = false;
    }
});

async function ukazKnihu(kod, current) {
    const res = await fetch("api/kniha/" + encodeURIComponent(kod));
    if (current !== request) return;
    if (!res.ok) {
        byId("stav-knihy").textContent = "Knihu se nepodařilo načíst.";
        return;
    }
    const rows = await res.json();
    if (current !== request) return;
    const list = byId("terminy");
    list.replaceChildren();
    if (!rows.length) list.textContent = "Platnost revizí zatím nedoložena.";
    const stavy = {"ve-lhute":"Ve lhůtě", "blizi-se":"Blíží se termín", "po-lhute":"Po lhůtě"};
    for (const row of rows) {
        const li = document.createElement("li");
        const badge = document.createElement("span");
        badge.classList.add("lhuta", row.stav);
        badge.textContent = stavy[row.stav];
        const den = row.platnost.split("-").reverse().join(". ");
        li.append(row.objekt + " / " + row.zarizeni + " · ", badge,
            " · platnost do " + den + " · ", odkazNaDokument(res, row.dokument));
        list.append(li);
    }
}

byId("kniha").addEventListener("submit", async event => {
    event.preventDefault();
    const form = event.currentTarget;
    const kod = byId("oznaceni").textContent;
    const current = request;
    const button = form.querySelector("button");
    button.disabled = true;
    try {
        const res = await fetch("api/kniha/" + encodeURIComponent(kod), {method:"POST",
            headers:{"Content-Type":"application/json"}, body:JSON.stringify(Object.fromEntries(new FormData(form)))});
        const result = await res.json();
        if (current !== request) return;
        if (!res.ok) throw new Error(result.error || "Zápis se nezdařil.");
        byId("stav-knihy").textContent = "Revize zapsána.";
        await Promise.all([ukazKnihu(kod, current), obnovOsu()]);
    } catch (err) {
        if (current === request) byId("stav-knihy").textContent = err.message;
    } finally {
        button.disabled = false;
    }
});

async function nactiOsu(pred) {
    const current = request;
    const nacteni = ++nacteniOsy;
    const kod = byId("oznaceni").textContent;
    const stavOsy = byId("stav-osy");
    const starsi = byId("starsi");
    const list = byId("udalosti");
    if (pred === null) list.replaceChildren();
    dalsiPozice = pred;
    starsi.hidden = true;
    stavOsy.textContent = "Načítám události…";
    try {
        const path = "api/spisy/" + encodeURIComponent(kod) + "/osa";
        const res = await fetch(pred === null ? path : path + "/" + encodeURIComponent(pred));
        if (!res.ok) throw new Error();
        const page = await res.json();
        if (current !== request || nacteni !== nacteniOsy) return;
        for (const event of page.udalosti) {
            const li = document.createElement("li");
            const time = document.createElement("time");
            time.dateTime = event.cas;
            time.textContent = new Date(event.cas).toLocaleString("cs-CZ");
            li.append(time, " · ", event.popis);
            if (event.dokument) li.append(" · ", odkazNaDokument(res, event.dokument));
            list.append(li);
        }
        dalsiPozice = page.dalsi;
        stavOsy.textContent = list.childElementCount ? "" : "Spis zatím nemá zaznamenané události.";
        starsi.hidden = dalsiPozice === null;
        starsi.textContent = "Načíst starší události";
    } catch {
        if (current !== request || nacteni !== nacteniOsy) return;
        stavOsy.textContent = "Události se nepodařilo načíst.";
        starsi.textContent = "Zkusit znovu";
        starsi.hidden = false;
    }
}

function obnovOsu() {
    if (byId("osa").open && !byId("karta").hidden) return nactiOsu(null);
}
byId("osa").addEventListener("toggle", obnovOsu);
byId("starsi").addEventListener("click", () => nactiOsu(dalsiPozice));

async function ukazVykopy(kod, current) {
    const url = "api/vykopy/" + encodeURIComponent(kod);
    const response = await fetch(url);
    if (current !== request) return;
    if (!response.ok) {
        byId("vykopy").hidden = false;
        byId("trasy").textContent = "Stav výkopů se nepodařilo načíst.";
        return;
    }
    const rows = await response.json();
    if (current !== request) return;
    byId("vykopy").hidden = rows.length === 0;
    for (const row of rows) {
        const item = document.createElement("li");
        item.textContent = row.trasa + " · " + (row.duvody.length ? row.duvody.join(" ") : "Podklady jsou úplné.");
        if (row.stav === "uvolneno-test") item.textContent = row.trasa + " · Uvolněno v testu pro den " + row.den + ".";
        if (row.stav === "pripraveno-test") {
            const submit = document.createElement("button");
            submit.type = "button";
            submit.textContent = "Uvolnit v testu";
            submit.addEventListener("click", async () => {
                submit.disabled = true;
                try {
                    const res = await fetch(url, {method:"POST", headers:{"Content-Type":"application/json"},
                        body:JSON.stringify({trasa:row.trasa, revize:row.revize})});
                    const saved = await res.json();
                    if (!res.ok) throw new Error(saved.error);
                    item.textContent = saved.trasa + " · Uvolněno v testu pro den " + saved.den + ".";
                } catch (error) {
                    item.textContent = row.trasa + " · " + error.message;
                }
            });
            item.append(" ", submit);
        }
        byId("trasy").append(item);
    }
}

async function ukazOcpp(kod, current) {
    const seznam = byId("ocpp-stavy");
    const stavy = {Available:"K dispozici", Occupied:"Obsazený", Reserved:"Rezervovaný", Unavailable:"Nedostupný", Faulted:"Porucha"};
    try {
        const odpoved = await fetch("api/ocpp/" + encodeURIComponent(kod));
        if (!odpoved.ok) throw new Error();
        const data = await odpoved.json();
        if (current !== request) return;
        seznam.replaceChildren(...data.map(row => {
            const li = document.createElement("li");
            li.textContent = row.stanice + " · EVSE " + row.evse + ", konektor " + row.konektor + " · " +
                stavy[row.stav] + " · " + new Date(row.cas).toLocaleString("cs-CZ") + " · počet hlášení " + row.pocet;
            return li;
        }));
        byId("ocpp").hidden = data.length === 0;
    } catch {
        if (current !== request) return;
        const li = document.createElement("li");
        li.textContent = "Telemetrii se nepodařilo načíst.";
        seznam.replaceChildren(li);
        byId("ocpp").hidden = false;
    }
}
