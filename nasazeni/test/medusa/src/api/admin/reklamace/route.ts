import type { AuthenticatedMedusaRequest, MedusaResponse } from "@medusajs/framework/http"
import { jeCas, jeUuid, kategorie, odpoved } from "../../../lib/reklamace"

export async function POST(req: AuthenticatedMedusaRequest, res: MedusaResponse) {
  const b = req.body as Record<string, unknown> | null
  if (!b || !jeUuid(b.id) || !jeCas(b.received_at) ||
      (b.complaint_asserted_at != null && !jeCas(b.complaint_asserted_at)) ||
      (b.objednavka != null && (typeof b.objednavka !== "string" || !b.objednavka.trim() || b.objednavka.length > 120)) ||
      typeof b.druh !== "string" || !kategorie.includes(b.druh)) {
    res.status(400).json({ message: "Neplatné údaje pro příjem reklamace." })
    return
  }
  await odpoved(req,res,"SELECT * FROM wms.prijmi_rma(?::uuid,?::text,?::timestamptz,?::timestamptz,?::text)",
    [b.id,b.objednavka ?? null,b.received_at,b.complaint_asserted_at ?? null,b.druh])
}
