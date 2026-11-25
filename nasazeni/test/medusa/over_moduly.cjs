// Oba ovladače si převezmou nastavení přímo ze sestavené konfigurace aplikace.
const assert = require("node:assert/strict")
const { createRequire } = require("node:module")
const path = require("node:path")
const app = createRequire(path.join(process.argv[2], "package.json"))

async function main() {
  const { ModulesSdkUtils } = app("@medusajs/framework/utils")
  const { EntitySchema, MikroORM } = app("@medusajs/deps/mikro-orm/postgresql")
  const { projectConfig } = app("./.medusa/server/medusa-config.js")
  const clientUrl = projectConfig.databaseUrl
  const driverOptions = projectConfig.databaseDriverOptions
  const conn = driverOptions.connection
  assert.equal(conn.ssl.rejectUnauthorized, true)
  assert.equal(conn.ssl.servername, "postgres.polarita.test")
  const query = "select version, current_database() as db from pg_stat_ssl where pid=pg_backend_pid()"
  const expected = [{ version: "TLSv1.3", db: "db_eshop" }]
  const pg = ModulesSdkUtils.createPgConnection({ clientUrl, driverOptions, pool: { min: 0, max: 1 } })
  try {
    assert.deepEqual((await pg.raw(query)).rows, expected)
  } finally {
    await pg.destroy()
  }

  const entity = new EntitySchema({ name: "KontrolaSpojeni", properties: { id: { type: "integer", primary: true } } })
  const orm = await MikroORM.init({ entities: [entity], clientUrl, driverOptions, pool: { min: 0, max: 1 } })
  try {
    assert.deepEqual(await orm.em.getConnection().execute(query), expected)
  } finally {
    await orm.close(true)
  }
  console.log("Sdílené spojení Medusy i modulový MikroORM ověřily TLS 1.3 na db_eshop.")
}
main().catch(error => {
  console.error("Kontrola modulových spojení Medusy selhala:", error.code || error.name)
  process.exitCode = 1
})
