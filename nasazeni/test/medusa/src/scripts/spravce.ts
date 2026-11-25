import { readFileSync } from "node:fs"
import type { ExecArgs } from "@medusajs/framework/types"
import { Modules, RBAC_SUPER_ADMIN_ROLE_ID } from "@medusajs/framework/utils"
import { MedusaModule } from "@medusajs/framework/modules-sdk"

const email = "spravce@polarita.test"
const fixture = "spravce-medusa-test"

export default async function pripravSpravce({ container }: ExecArgs) {
  const password = readFileSync(0, "utf8").replace(/[\r\n]+$/, "")
  if (!password || process.getuid?.() !== 17309) throw new Error("Chybí vstup pro prvotní přihlášení správce TEST.")
  const users = container.resolve(Modules.USER)
  const auth = container.resolve(Modules.AUTH)
  const workflows = container.resolve(Modules.WORKFLOW_ENGINE)
  const existing = await users.listUsers({ email })
  if (existing.length > 1 || (existing.length && existing[0].metadata?.polarita_test !== fixture)) {
    throw new Error("E-mail správce už patří jinému účtu.")
  }
  let user = existing[0]
  if (!user) {
    const roles: { role_id: string }[] = []
    if (MedusaModule.isInstalled(Modules.RBAC)) {
      const rbac = container.resolve(Modules.RBAC)
      const [role] = await rbac.listRbacRoles({ id: RBAC_SUPER_ADMIN_ROLE_ID })
      if (!role) throw new Error("Chybí výchozí role správce Medusy.")
      roles.push({ role_id: role.id })
    }
    await workflows.run("create-users-workflow", {
      input: { users: [{ email, roles, metadata: { polarita_test: fixture } }] },
    })
    user = (await users.listUsers({ email }))[0]
  }
  if (!user || user.metadata?.polarita_test !== fixture) throw new Error("Nesouhlasí vlastník testovacího účtu.")
  // Po výpadku mezi registrací a propojením ověří původní heslo vlastnictví existující identity.
  try {
    const input = { url: "", protocol: "", headers: {}, query: {}, body: { email, password } }
    let result = await auth.authenticate("emailpass", input)
    if (!result.success) result = await auth.register("emailpass", input)
    const identity = result.authIdentity
    if (!result.success || !identity) throw new Error()
    const linked = identity.app_metadata?.user_id
    if (linked && linked !== user.id) throw new Error()
    if (!linked) {
      await auth.updateAuthIdentities({ id: identity.id,
        app_metadata: { ...identity.app_metadata, user_id: user.id } })
    }
  } catch {
    throw new Error("Medusa nepotvrdila přihlášení a přiřazení identity správci TEST.")
  }
  console.log("Medusa připravila účet spravce@polarita.test.")
}
