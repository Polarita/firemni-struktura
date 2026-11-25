import type { AuthenticatedMedusaRequest, MedusaResponse } from "@medusajs/framework/http"
import { ContainerRegistrationKeys } from "@medusajs/framework/utils"
import { jeUuid } from "../../../../lib/reklamace"

type Connection = { raw(sql: string, params: unknown[]): Promise<{ rows: Record<string, unknown>[] }> }

export async function GET(req: AuthenticatedMedusaRequest, res: MedusaResponse) {
  const order = req.query.objednavka
  if (!jeUuid(order)) {
    res.status(400).json({ message: "Zadejte identifikátor položky nákupní objednávky." })
    return
  }
  const db: Connection = req.scope.resolve(ContainerRegistrationKeys.PG_CONNECTION)
  const { rows } = await db.raw(
    "SELECT * FROM wms.prijaty_material WHERE objednavka=?::uuid ORDER BY prijato_at,prijemka", [order])
  res.json({ prijate_radky: rows })
}

export async function POST(req: AuthenticatedMedusaRequest, res: MedusaResponse) {
  const body = req.body as Record<string, unknown> | null
  if (!body || !jeUuid(body.id) || !jeUuid(body.objednavka) || !Array.isArray(body.doklady)
      || body.doklady.length < 2 || !body.doklady.every(jeUuid)) {
    res.status(400).json({ message: "Zadejte identifikátor příjmu, položky objednávky a řádky příjemek a faktur." })
    return
  }
  const db: Connection = req.scope.resolve(ContainerRegistrationKeys.PG_CONNECTION)
  try {
    const { rows } = await db.raw("SELECT * FROM wms.potvrd_nakup(?::uuid,?::uuid,?::uuid[])",
      [body.id, body.objednavka, body.doklady])
    res.json({ prijem: rows[0] })
  } catch (error) {
    switch ((error as { code?: string }).code) {
      case "22023": res.status(400).json({ message: "Každý doklad uveďte právě jednou." }); return
      case "P0002": res.status(404).json({ message: "Položka nákupní objednávky nebyla nalezena." }); return
      case "P1004": res.status(409).json({ message: "Zkontrolujte shodu dokladů a zbývající množství na objednávce." }); return
      case "23505": res.status(409).json({ message: "Příjem nebo doklad už patří jinému spárování." }); return
      default: throw error
    }
  }
}
