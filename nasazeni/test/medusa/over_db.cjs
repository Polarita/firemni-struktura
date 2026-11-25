// Spouští se účtem medusa uvnitř medusa-test.
const assert = require("node:assert/strict")
const { readFileSync, statSync } = require("node:fs")
const { createRequire } = require("node:module")
const { Client } = createRequire(process.argv[2] || "/opt/medusa/current/package.json")("pg")

async function main() {
  assert.equal(process.getuid(), 17309)
  const credential = "/run/secrets/pg-db_eshop"
  assert.equal(statSync(credential).mode & 0o777, 0o400)
  for (const name of ["jwt", "cookie"]) {
    const file = statSync("/run/secrets/medusa-" + name)
    assert.ok(file.size >= 32 && file.uid === process.getuid() && (file.mode & 0o777) === 0o400)
  }
  const options = {
    host: "10.239.33.12", port: 5432, user: "db_eshop",
    password: readFileSync(credential, "utf8"),
    ssl: { ca: readFileSync("/etc/polarita-medusa/postgres.crt"), rejectUnauthorized: true,
           servername: "postgres.polarita.test", minVersion: "TLSv1.3" },
    connectionTimeoutMillis: 15000, statement_timeout: 10000,
  }
  const shop = new Client({ ...options, database: "db_eshop" })
  try {
    await shop.connect()
    const { rows } = await shop.query(`SELECT current_user AS role, current_database() AS db, version AS tls,
      has_schema_privilege(current_user,'public','CREATE') AS vendor_migrations,
      has_table_privilege(current_user,'wms.rma_prehled','SELECT') AS rma_view
      FROM pg_stat_ssl WHERE pid=pg_backend_pid()`)
    assert.deepEqual(rows, [{ role: "db_eshop", db: "db_eshop", tls: "TLSv1.3", vendor_migrations: true, rma_view: true }])
  } finally {
    await shop.end()
  }
  const other = new Client({ ...options, database: "db_akademie" })
  try {
    await assert.rejects(other.connect(), { code: "28000" })
  } finally {
    await other.end()
  }
  console.log("Proces Medusy ověřil certifikát PostgreSQL, přímé připojení TLS 1.3 do db_eshop, právo na vendor migrace a čtení reklamací. Spojení do databáze Akademie server odmítl.")
}
main().catch(error => {
  console.error("Kontrola PostgreSQL selhala:", error.code || error.name)
  process.exitCode = 1
})
