// Přelož každou šablonu připnutým kompilátorem Astro, pak syntakticky ověř výstup.
const fs = require("node:fs")
const { stripTypeScriptTypes } = require("node:module")
const { spawnSync } = require("node:child_process")
const { compileAstroSync } = require("/opt/polarita-astro-ci/compiler.node")
for (const path of process.argv.slice(2)) {
  const compiled = compileAstroSync(fs.readFileSync(path, "utf8"), { filename: path })
  for (const diagnostic of compiled.diagnostics) {
    if (diagnostic.severity === "error") throw new Error(path + ": " + diagnostic.text)
  }
  if (!compiled.code) throw new Error("Kompilátor vrátil prázdný výstup pro " + path)
  const syntax = spawnSync(process.execPath, ["--check", "--input-type=module", "-"],
                           { input: stripTypeScriptTypes(compiled.code), stdio: ["pipe", "ignore", "inherit"] })
  if (syntax.status !== 0) throw new Error("Neplatný výstup překladu " + path)
}
