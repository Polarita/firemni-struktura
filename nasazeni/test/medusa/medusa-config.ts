import { readFileSync } from "node:fs"
import { defineConfig } from "@medusajs/framework/utils"

const build = process.env.POLARITA_MEDUSA_BUILD === "1"
const secret = (name: string) => build ? "sestaveni-test" : readFileSync("/run/secrets/" + name, "utf8")
const origin = process.env.MEDUSA_TEST_ORIGIN || "http://127.0.0.1:9000"
if (!/^https:\/\/[a-z0-9.-]+\.ts\.net(?::\d{4})?$/.test(origin) && origin !== "http://127.0.0.1:9000") {
  throw new Error("Neznámý původ interního e-shopu")
}
module.exports = defineConfig({
  admin: { disable: build && process.env.POLARITA_MEDUSA_BACKEND === "1" },
  projectConfig: {
    databaseUrl: build ? "postgresql://localhost/build" :
      "postgresql://db_eshop:" + encodeURIComponent(secret("pg-db_eshop")) + "@10.239.33.12:5432/db_eshop",
    databaseSchema: "public",
    sessionOptions: { name: "pol_medusa_sid", resave: false, saveUninitialized: false },
    databaseDriverOptions: {
      ssl: build ? false : { ca: readFileSync("/etc/polarita-medusa/postgres.crt", "utf8"),
        servername: "postgres.polarita.test", rejectUnauthorized: true, minVersion: "TLSv1.3" },
      connectionTimeoutMillis: 25000, pool: { min: 0, max: 4 },
    },
    http: { storeCors: origin, adminCors: origin, authCors: origin,
      jwtSecret: secret("medusa-jwt"), cookieSecret: secret("medusa-cookie") },
  },
})
