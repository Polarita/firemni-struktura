import type { AuthenticatedMedusaRequest, MedusaResponse } from "@medusajs/framework/http"
import { ContainerRegistrationKeys } from "@medusajs/framework/utils"

type DB = { raw(sql: string, params: unknown[]): Promise<{ rows: Record<string, unknown>[] }> }
const uuid = (v: unknown): v is string => typeof v === "string" && /^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i.test(v)
const text = (v: unknown): v is string => typeof v === "string" && v.trim().length > 0 && v.length <= 120
const caseNumber = (v: unknown): v is string => typeof v === "string" && /^POL-[0-9]{4}-[0-9]{5}$/.test(v)

export async function GET(req: AuthenticatedMedusaRequest, res: MedusaResponse) {
  const label = req.query.stitek
  if (!text(label)) {
    res.status(400).json({ message: "Zadejte štítek bubnu." })
    return
  }
  const db: DB = req.scope.resolve(ContainerRegistrationKeys.PG_CONNECTION)
  const { rows } = await db.raw(`SELECT b.*,
    coalesce((SELECT jsonb_agg(to_jsonb(r) ORDER BY r.spis,r.id)
              FROM wms.otevrene_rezervace r WHERE r.buben=b.id),'[]') AS rezervace
    FROM wms.bubny_prehled b WHERE b.stitek=?`,[label])
  if (!rows.length) res.status(404).json({ message: "Tento štítek ve skladu není." })
  else res.json({ buben: rows[0] })
}

export async function POST(req: AuthenticatedMedusaRequest, res: MedusaResponse) {
  const b = req.body as Record<string, unknown> | null
  if (!b || !uuid(b.id) || typeof b.mm !== "number" || !Number.isSafeInteger(b.mm) || b.mm <= 0) {
    res.status(400).json({ message: "Požadavek musí mít identifikátor a kladnou délku v celých milimetrech." })
    return
  }
  let sql: string
  let params: unknown[]
  if (b.operace === "prijem" && text(b.stitek) && text(b.varianta) && text(b.sklad)) {
    sql = "SELECT * FROM wms.prijmi_buben(?::uuid,?::text,?::text,?::text,?::bigint)"
    params = [b.id,b.stitek,b.varianta,b.sklad,b.mm]
  } else if (b.operace === "rezervace" && uuid(b.buben) && caseNumber(b.spis)) {
    sql = "SELECT * FROM wms.rezervuj_kabel(?::uuid,?::uuid,?::text,?::bigint)"
    params = [b.id,b.buben,b.spis,b.mm]
  } else if (["vydej","uvolneni"].includes(String(b.operace)) && uuid(b.rezervace) && text(b.stitek) && caseNumber(b.spis)) {
    sql = "SELECT * FROM wms.pohyb_kabelu(?::uuid,?::uuid,?::text,?::text,?::text,?::bigint)"
    params = [b.id,b.rezervace,b.stitek,b.spis,b.operace,b.mm]
  } else {
    res.status(400).json({ message: "Doplňte údaje skladového pohybu." })
    return
  }
  const db: DB = req.scope.resolve(ContainerRegistrationKeys.PG_CONNECTION)
  try {
    const { rows } = await db.raw(sql,params)
    res.json({ pohyb: rows[0] })
  } catch (error) {
    const code = (error as { code?: string }).code
    if (code === "P1001") res.status(409).json({ message: "Požadavek přesahuje dostupnou metráž." })
    else if (code === "23505") res.status(409).json({ message: "Požadavek nebo štítek už patří jinému záznamu." })
    else if (code === "P0002" || code === "23503") res.status(404).json({ message: "Ověřte sklad, buben, rezervaci a spis." })
    else throw error
  }
}
