import type { AuthenticatedMedusaRequest, MedusaResponse } from "@medusajs/framework/http"
import { jeCas, jeUuid, kategorie, odpoved } from "../../../../lib/reklamace"

export async function GET(req: AuthenticatedMedusaRequest, res: MedusaResponse) {
  if (!jeUuid(req.params.id)) {
    res.status(400).json({ message: "Neplatný identifikátor." })
    return
  }
  await odpoved(req,res,"SELECT * FROM wms.rma_prehled WHERE id=?::uuid",[req.params.id])
}

export async function POST(req: AuthenticatedMedusaRequest, res: MedusaResponse) {
  const b = req.body as Record<string, unknown> | null
  if (!b || !jeUuid(req.params.id) || !jeUuid(b.pozadavek) || typeof b.verze !== "number" ||
      !Number.isInteger(b.verze) || b.verze < 1 || b.verze > 2147483646 ||
      typeof b.druh !== "string" || !kategorie.includes(b.druh) ||
      (b.complaint_asserted_at != null && !jeCas(b.complaint_asserted_at))) {
    res.status(400).json({ message: "Neplatné údaje pro změnu kategorie." })
    return
  }
  await odpoved(req,res,"SELECT * FROM wms.zarad_rma(?::uuid,?::uuid,?::integer,?::text,?::timestamptz)",
    [req.params.id,b.pozadavek,b.verze,b.druh,b.complaint_asserted_at ?? null])
}
