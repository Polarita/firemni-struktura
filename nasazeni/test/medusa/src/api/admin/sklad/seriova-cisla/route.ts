import type { AuthenticatedMedusaRequest, MedusaResponse } from "@medusajs/framework/http"
import { ContainerRegistrationKeys } from "@medusajs/framework/utils"
import { jeUuid } from "../../../../lib/reklamace"

type Connection = { raw(sql: string, params: unknown[]): Promise<{ rows: Record<string, unknown>[] }> }

function label(value: unknown, max: number): value is string {
  return typeof value === "string" && value.trim().length > 0 && value.length <= max
}

export async function GET(req: AuthenticatedMedusaRequest, res: MedusaResponse) {
  const { vyrobce, serie } = req.query
  if (!label(vyrobce,120) || !label(serie,160)) {
    res.status(400).json({ message: "Vyberte výrobce a naskenujte sériové číslo." })
    return
  }
  const conn: Connection = req.scope.resolve(ContainerRegistrationKeys.PG_CONNECTION)
  const { rows } = await conn.raw("SELECT * FROM wms.serie_prehled WHERE vyrobce=? AND serie=?", [vyrobce,serie])
  if (rows.length) res.json({ kus: rows[0] })
  else res.status(404).json({ message: "Kus s tímto sériovým číslem ve skladu není." })
}

export async function POST(req: AuthenticatedMedusaRequest, res: MedusaResponse) {
  const b = req.body as Record<string,unknown> | null
  if (!b || !jeUuid(b.id) || !label(b.vyrobce,120) || !label(b.serie,160) || !label(b.sklad,120)) {
    res.status(400).json({ message: "Zadejte identifikátor pohybu, výrobce, sken a sklad." })
    return
  }
  let sql: string
  let params: unknown[]
  if (b.operace === "prijem" && label(b.varianta,120)) {
    sql = "SELECT * FROM wms.prijmi_sken(?::uuid,?::text,?::text,?::text,?::text)"
    params = [b.id,b.vyrobce,b.serie,b.varianta,b.sklad]
  } else if (b.operace === "vydej" && jeUuid(b.kus) && typeof b.spis === "string" && /^POL-[0-9]{4}-[0-9]{5}$/.test(b.spis)) {
    sql = "SELECT * FROM wms.vydej_sken(?::uuid,?::uuid,?::text,?::text,?::text,?::text)"
    params = [b.id,b.kus,b.vyrobce,b.serie,b.sklad,b.spis]
  } else {
    res.status(400).json({ message: "Zkontrolujte variantu při příjmu nebo číslo kusu a spisu při výdeji." })
    return
  }
  const conn: Connection = req.scope.resolve(ContainerRegistrationKeys.PG_CONNECTION)
  try {
    const { rows } = await conn.raw(sql,params)
    res.json({ pohyb: rows[0] })
  } catch (error) {
    switch ((error as { code?: string }).code) {
      case "P0002": case "23503": res.status(404).json({ message: "Sken, sklad nebo doklad dodavatele nesouhlasí." }); return
      case "23505": res.status(409).json({ message: "Kus nebo požadavek již patří jinému pohybu." }); return
      case "P1002": res.status(409).json({ message: "Dodavatelská záruka není aktivní." }); return
      case "P1003": res.status(409).json({ message: "Doplňte výrobní pas a štítek CE tohoto kusu." }); return
      default: throw error
    }
  }
}
