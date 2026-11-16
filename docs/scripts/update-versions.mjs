// Usage: node update-versions.mjs <site-dir>, with one folder per version in <site-dir>
import { readdirSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'

const [siteDir] = process.argv.slice(2)
if (!siteDir) {
  console.error('usage: update-versions.mjs <site-dir>')
  process.exit(1)
}

function parse(tag) {
  const [core, pre = ''] = tag.replace(/^v/, '').split('-', 2)
  return { core: core.split('.').map(Number), pre }
}

// Newest first; a final release sorts above its prereleases.
function compare(a, b) {
  const pa = parse(a)
  const pb = parse(b)
  for (let i = 0; i < 3; i++) {
    const d = (pb.core[i] || 0) - (pa.core[i] || 0)
    if (d) return d
  }
  if (!pa.pre || !pb.pre) return Number(!pb.pre) - Number(!pa.pre)
  return pb.pre.localeCompare(pa.pre, undefined, { numeric: true })
}

const tags = readdirSync(siteDir, { withFileTypes: true })
  .filter((d) => d.isDirectory() && /^v\d/.test(d.name))
  .map((d) => d.name)
  .sort(compare)
const release = tags[0] ?? null
const versions = ['latest', ...tags]

writeFileSync(join(siteDir, 'versions.json'), `${JSON.stringify({ release, versions }, null, 2)}\n`)

writeFileSync(
  join(siteDir, 'index.html'),
  `<!doctype html>
<meta charset="utf-8">
<title>Digital Twin Toolbox</title>
<meta http-equiv="refresh" content="0; url=./latest/">
<link rel="canonical" href="./latest/">
<a href="./latest/">Digital Twin Toolbox documentation</a>
`,
)

console.log(`release=${release} versions=${versions.join(',')}`)
