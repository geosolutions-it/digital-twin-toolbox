// Cesium runtime assets (not bundleable) -> public/cesium. Skipped when up to date: deleting the
// folder under a running dev server makes it serve index.html for /cesium/*.
import { cp, readFile, rm, writeFile } from "node:fs/promises"
import { dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..")
const source = resolve(root, "node_modules/cesium/Build/Cesium")
const target = resolve(root, "public/cesium")
const marker = resolve(target, ".version")
const folders = ["Assets", "ThirdParty", "Widgets", "Workers"]

const { version } = JSON.parse(
  await readFile(resolve(root, "node_modules/cesium/package.json"), "utf8"),
)
const current = await readFile(marker, "utf8").catch(() => "")
if (current.trim() === version) {
  console.log(`cesium ${version} runtime assets already in ${target}`)
} else {
  await rm(target, { recursive: true, force: true })
  for (const folder of folders) {
    await cp(resolve(source, folder), resolve(target, folder), {
      recursive: true,
    })
  }
  await writeFile(marker, version)
  console.log(`copied cesium ${version} runtime assets to ${target}`)
}
