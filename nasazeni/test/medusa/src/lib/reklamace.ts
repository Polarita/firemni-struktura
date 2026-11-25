import type { AuthenticatedMedusaRequest, MedusaResponse } from "@medusajs/framework/http"
import { ContainerRegistrationKeys } from "@medusajs/framework/utils"

export const kategorie = ["k_posouzeni", "b2b_servis", "b2c_reklamace"]
export const jeUuid = (value: unknown): value is string =>
  typeof value === "string" && /^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/i.test(value)
export const jeCas = (value: unknown): value is string =>
  typeof value === "string" && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$/.test(value)

type Databaze = { raw(sql: string, params: unknown[]): Promise<{ rows: Record<string, unknown>[] }> }

export async function odpoved(req: AuthenticatedMedusaRequest, res: MedusaResponse, sql: string, params: unknown[]) {
  const db: Databaze = req.scope.resolve(ContainerRegistrationKeys.PG_CONNECTION)
  try {
    const { rows } = await db.raw("SELECT to_jsonb(r) AS reklamace FROM (" + sql + ") r", params)
    if (!rows.length) {
      res.status(404).json({ message: "Reklamace nebyla nalezena." })
      return
    }
    res.json({ reklamace: rows[0].reklamace })
  } catch (err) {
    const code = (err as { code?: string }).code
    if (code === "P0002") {
      res.status(404).json({ message: "Reklamace nebyla nalezena." })
    } else if (code === "23505" || code === "40001") {
      res.status(409).json({ message: "Požadavek koliduje s již uloženou verzí." })
    } else if (["22023", "22007", "22008", "23514", "23502"].includes(code || "")) {
      res.status(400).json({ message: "Ověřte údaje a původní okamžik uplatnění reklamace." })
    } else {
      throw err
    }
  }
}
