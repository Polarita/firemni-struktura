import { defineRouteConfig } from "@medusajs/admin-sdk"
import { Button, Container, Heading, Input, Label } from "@medusajs/ui"
import { useRef, useState } from "react"
import type { FormEvent } from "react"

type Reservation = { id: string, spis: string, zbyva_mm: string }
type Drum = { id: string, stitek: string, varianta: string, sklad: string, skladem_mm: string,
  volno_mm: string, rezervovano_mm: string, rezervace: Reservation[] }
const api = "/admin/sklad/bubny"
const meters = (mm: string) => (Number(mm) / 1000).toLocaleString("cs-CZ", { maximumFractionDigits: 3 }) + " m"

async function request(path: string, options?: RequestInit) {
  const response = await fetch(path, { credentials: "include", ...options })
  const data = await response.json()
  if (!response.ok) throw new Error(data.message || "Sklad požadavek nepřijal.")
  return data
}

export default function KabeloveBubny() {
  const [drum, setDrum] = useState<Drum | null>(null)
  const [label, setLabel] = useState("")
  const [operation, setOperation] = useState("rezervace")
  const [message, setMessage] = useState("")
  const [busy, setBusy] = useState(false)
  const inFlight = useRef(false)
  const pending = useRef<{ payload: string, id: string } | null>(null)
  const lookup = async (tag: string) => (await request(api + "?stitek=" + encodeURIComponent(tag))).buben as Drum

  async function find(event: FormEvent) {
    event.preventDefault()
    if (inFlight.current) return
    inFlight.current = true
    setBusy(true)
    setMessage("")
    setDrum(null)
    try { setDrum(await lookup(label.trim())) }
    catch (e) { setMessage(e instanceof Error ? e.message : "Načtení se nezdařilo.") }
    finally { inFlight.current = false; setBusy(false) }
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (inFlight.current) return
    const form = event.currentTarget
    const values = new FormData(form)
    const length = String(values.get("delka") || "").trim().replace(",",".")
    if (!/^\d+(\.\d{1,3})?$/.test(length)) { setMessage("Zadejte metry s přesností na milimetry."); return }
    const [whole, fraction = ""] = length.split(".")
    const mm = Number(whole) * 1000 + Number(fraction.padEnd(3, "0"))
    if (!Number.isSafeInteger(mm) || mm < 1) { setMessage("Zkontrolujte délku kabelu."); return }
    const body: Record<string, unknown> = { operace: operation, mm }
    let tag = drum?.stitek || ""
    if (operation === "prijem") {
      tag = String(values.get("stitek")).trim()
      Object.assign(body, { stitek: tag, varianta: String(values.get("varianta")).trim(), sklad: "MAIN-101" })
    } else if (operation === "rezervace" && drum) {
      Object.assign(body, { buben: drum.id, spis: String(values.get("spis")).trim() })
    } else {
      const reservation = drum?.rezervace.find(r => r.id === values.get("rezervace"))
      if (!reservation) { setMessage("Vyberte otevřenou rezervaci."); return }
      Object.assign(body, { rezervace: reservation.id, stitek: String(values.get("sken")).trim(), spis: reservation.spis })
    }
    const payload = JSON.stringify(body)
    if (pending.current?.payload !== payload) pending.current = { payload, id: crypto.randomUUID() }
    inFlight.current = true
    setBusy(true)
    setMessage("")
    let saved = false
    try {
      await request(api, { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...body, id: pending.current.id }) })
      saved = true
      const updated = await lookup(tag)
      setDrum(updated)
      setLabel(tag)
      form.reset()
      pending.current = null
      setMessage("Pohyb byl uložen.")
    } catch (e) {
      setMessage(saved ? "Pohyb byl uložen. Zopakujte načtení štítku pro aktuální zůstatek." :
        (e instanceof Error ? e.message : "Přenos se přerušil. Požadavek můžete zopakovat."))
    } finally { inFlight.current = false; setBusy(false) }
  }

  return <Container className="p-6">
    <Heading level="h1">Kabelové bubny</Heading>
    <form className="flex items-end gap-2 my-4" onSubmit={find}>
      <Label>Štítek bubnu<Input value={label} onChange={e => setLabel(e.target.value)} required /></Label>
      <Button type="submit" disabled={busy}>Načíst buben</Button>
    </form>
    {drum && <section className="mb-5">
      <Heading level="h2">{drum.stitek}</Heading>
      <p>{drum.varianta} · {drum.sklad}</p>
      <dl className="my-3 grid grid-cols-3 gap-3">
        {([["Skladem",drum.skladem_mm],["Rezervováno",drum.rezervovano_mm],["Volně",drum.volno_mm]] as const)
          .map(([name,value]) => <div key={name}><dt>{name}</dt><dd>{meters(value)}</dd></div>)}
      </dl>
    </section>}
    <Label>Skladový pohyb <select value={operation} disabled={busy} onChange={e => setOperation(e.target.value)}>
      <option value="prijem">Příjem na MAIN-101</option><option value="rezervace">Rezervace pro stavbu</option>
      <option value="vydej">Výdej z rezervace</option><option value="uvolneni">Uvolnění rezervace</option>
    </select></Label>
    {(operation === "prijem" || drum) &&
      <form key={operation + (drum?.id || "")} onSubmit={save} className="mt-4 grid max-w-md gap-3">
        {operation === "prijem" && <><Label>Štítek přijímaného bubnu<Input name="stitek" required /></Label>
          <Label>Identifikátor varianty kabelu<Input name="varianta" required /></Label></>}
        {operation === "rezervace" && <Label>Číslo spisu stavby<Input name="spis" placeholder="POL-2026-00001" pattern="POL-[0-9]{4}-[0-9]{5}" required /></Label>}
        {["vydej","uvolneni"].includes(operation) && <><Label>Rezervace <select name="rezervace" required>
          {drum?.rezervace.map(r => <option key={r.id} value={r.id}>{r.spis} · {meters(r.zbyva_mm)} · {r.id.slice(0,8)}</option>)}
        </select></Label><Label>Ověřte štítek bubnu<Input name="sken" required /></Label></>}
        <Label>Délka v metrech<Input name="delka" inputMode="decimal" required /></Label>
        <Button type="submit" disabled={busy}>Uložit pohyb</Button>
      </form>}
    <p role="status" className="mt-3">{message}</p>
  </Container>
}
export const config = defineRouteConfig({ label: "Kabelové bubny" })
