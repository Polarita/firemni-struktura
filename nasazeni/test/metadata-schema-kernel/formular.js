"use strict";
const form = document.querySelector("form");
const statusLine = document.querySelector("output");
const route = "./api/" + form.dataset.entity;
const inputs = [...form.querySelectorAll("input")];
let id = new URL(location.href).searchParams.get("id");
let etag;

async function apply(response) {
    if (!response.ok) {
        if (response.status === 412) throw Error("Záznam se změnil. Obnovte stránku před další úpravou.");
        throw Error("Požadavek selhal (HTTP " + response.status + ").");
    }
    const row = await response.json();
    id = row.id;
    etag = response.headers.get("ETag");
    for (const input of inputs) {
        if (input.type === "checkbox") input.checked = row[input.name];
        else input.value = row[input.name];
    }
    const url = new URL(location.href);
    url.searchParams.set("id", id);
    history.replaceState(null, "", url);
    statusLine.textContent = "Verze " + row.version;
}
form.addEventListener("submit", async event => {
    event.preventDefault();
    const button = form.querySelector("button");
    button.disabled = true;
    try {
        const row = {};
        for (const input of inputs) {
            const value = input.type === "number" ? input.valueAsNumber : input.value;
            row[input.name] = input.type === "checkbox" ? input.checked : value;
        }
        const headers = {"Content-Type": "application/json"};
        if (id) headers["If-Match"] = etag;
        await apply(await fetch(id ? route + "/" + encodeURIComponent(id) : route,
            {method: id ? "PUT" : "POST", headers, body: JSON.stringify(row)}));
    } catch (error) {
        statusLine.textContent = error.message;
    } finally {
        button.disabled = false;
    }
});
if (id) {
    const button = form.querySelector("button");
    button.disabled = true;
    fetch(route + "/" + encodeURIComponent(id)).then(apply).then(() => { button.disabled = false; })
        .catch(error => { statusLine.textContent = error.message; });
}
