// Cesium loads its workers, shaders, images and widget CSS at runtime from CESIUM_BASE_URL.
// Vite cannot bundle those, so copy them from the package into public/ before dev/build.
import { cp, rm } from "node:fs/promises"
import { dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..")
const source = resolve(root, "node_modules/cesium/Build/Cesium")
const target = resolve(root, "public/cesium")
const folders = ["Assets", "ThirdParty", "Widgets", "Workers"]

await rm(target, { recursive: true, force: true })
for (const folder of folders) {
  await cp(resolve(source, folder), resolve(target, folder), { recursive: true })
}
console.log(`copied cesium runtime assets to ${target}`)
