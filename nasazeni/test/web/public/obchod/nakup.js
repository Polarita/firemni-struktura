"use strict";
const el = (id) => document.getElementById(id);
const money = (amount, code) => new Intl.NumberFormat("cs-CZ", { style: "currency", currency: code.toUpperCase() }).format(amount);
const cartStorageName = "polarita-obchod-test-v1";
let config, product, variant, cart;
let busy = false;

function state() {
    return JSON.parse(sessionStorage.getItem(cartStorageName) || "{}");
}
function save(value) {
    sessionStorage.setItem(cartStorageName, JSON.stringify(value));
}
async function store(path, body) {
    const headers = { "x-publishable-api-key": config.publishable };
    if (body) headers["Content-Type"] = "application/json";
    const response = await fetch("/store/" + path, {
        method: body ? "POST" : "GET", credentials: "omit", cache: "no-store",
        headers, body: body ? JSON.stringify(body) : undefined
    });
    if (!response.ok) throw new Error("Obchod vrátil HTTP " + response.status + ".");
    return response.json();
}
function receipt(order) {
    el("kosik").hidden = el("polozka").hidden = true;
    el("doklad").textContent = "Číslo " + order.display_id + " · " + money(order.total, order.currency_code) + " · osobní odběr v Ejpovicích.";
    el("potvrzeno").hidden = false;
}
async function confirmCart() {
    const result = await store("carts/" + state().cart + "/complete", {});
    if (result.type !== "order") throw new Error("Obchod zatím nepotvrdil testovací platbu.");
    const order = { display_id: result.order.display_id, total: result.order.total, currency_code: result.order.currency_code };
    save({ ...state(), order });
    receipt(order);
}
async function showCart() {
    const path = "carts/" + state().cart;
    const fields = new URLSearchParams({ fields: "id,completed_at,currency_code,total,shipping_total,items.variant_id,items.quantity,items.title,shipping_methods.name,shipping_methods.shipping_option_id" });
    const readCart = async () => (await store(path + "?" + fields)).cart;
    cart = await readCart();
    if (cart.completed_at) {
        await confirmCart();
        return;
    }
    if (!cart.shipping_methods.some(s => s.shipping_option_id === config.shipping_option_id)) {
        const options = (await store("shipping-options?" + new URLSearchParams({ cart_id: cart.id }))).shipping_options;
        if (!options.some(o => o.id === config.shipping_option_id)) throw new Error("Osobní odběr momentálně není dostupný.");
        await store(path + "/shipping-methods", { option_id: config.shipping_option_id });
        cart = await readCart();
    }
    const item = cart.items[0];
    if (cart.items.length !== 1 || item.quantity !== 1 || item.variant_id !== variant.id) throw new Error("Obsah testovacího košíku se změnil.");
    el("radek").textContent = item.quantity + " × " + item.title;
    el("doprava").textContent = cart.shipping_methods[0].name + " · " + money(cart.shipping_total, cart.currency_code);
    el("celkem").textContent = money(cart.total, cart.currency_code);
    el("polozka").hidden = true;
    el("kosik").hidden = false;
}
async function load() {
    if (state().order) { receipt(state().order); return; }
    const response = await fetch("./katalog.json", { credentials: "omit", cache: "no-store" });
    if (!response.ok) throw new Error("Katalog zatím není dostupný.");
    config = await response.json();
    const params = new URLSearchParams({ region_id: config.region_id, fields: "id,title,description,variants.id,variants.sku,*variants.calculated_price" });
    product = (await store("products/" + config.product_id + "?" + params)).product;
    variant = product.variants.find(v => v.sku === "POL-TEST-PASKA-01");
    if (!variant?.calculated_price) throw new Error("V katalogu chybí oceněná varianta.");
    if (state().cart) { await showCart(); return; }
    el("nazev").textContent = product.title;
    el("popis").textContent = product.description;
    el("cena").textContent = money(variant.calculated_price.calculated_amount, variant.calculated_price.currency_code);
    el("polozka").hidden = false;
}
async function add() {
    if (!state().cart) {
        const address = { first_name: "Test", last_name: "Obchod", address_1: "Testovací sklad", city: "Ejpovice", postal_code: "33701", country_code: "cz" };
        const result = await store("carts", { region_id: config.region_id, email: "obchod-rozhrani@polarita.test",
            shipping_address: address, billing_address: address, items: [{ variant_id: variant.id, quantity: 1 }] });
        save({ cart: result.cart.id });
    }
    await showCart();
}
async function checkout() {
    const fields = new URLSearchParams({ fields: "id,completed_at,payment_collection.id,payment_collection.payment_sessions.provider_id" });
    cart = (await store("carts/" + state().cart + "?" + fields)).cart;
    if (!cart.completed_at) {
        const collection = cart.payment_collection || (await store("payment-collections", { cart_id: cart.id })).payment_collection;
        if (!(collection.payment_sessions || []).some(s => s.provider_id === "pp_system_default")) {
            await store("payment-collections/" + collection.id + "/payment-sessions", { provider_id: "pp_system_default" });
        }
    }
    await confirmCart();
}
async function perform(action) {
    if (busy) return;
    busy = true;
    const buttons = document.querySelectorAll("button");
    buttons.forEach(b => { b.disabled = true; });
    el("opakovat").hidden = true;
    el("stav").textContent = "Čekám na odpověď obchodu…";
    try {
        await action();
        el("stav").textContent = "";
    } catch (error) {
        el("stav").textContent = error.message;
        el("opakovat").hidden = false;
    } finally {
        busy = false;
        buttons.forEach(b => { b.disabled = false; });
    }
}
el("pridat").onclick = () => perform(add);
el("odeslat").onclick = () => perform(checkout);
el("novy").onclick = () => perform(async () => { save({}); el("potvrzeno").hidden = true; await load(); });
el("opakovat").onclick = () => perform(load);
perform(load);
