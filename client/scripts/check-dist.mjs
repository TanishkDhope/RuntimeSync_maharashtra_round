import { readdir, readFile } from "node:fs/promises"
import path from "node:path"

const distDir = path.resolve("dist")
const forbidden = ["SAMPLE DATA", "sampleApi.js", "src/mocks"]

async function filesIn(directory) {
  const entries = await readdir(directory, { withFileTypes: true })
  const files = []
  for (const entry of entries) {
    const entryPath = path.join(directory, entry.name)
    if (entry.isDirectory()) files.push(...(await filesIn(entryPath)))
    else files.push(entryPath)
  }
  return files
}

const violations = []
for (const file of await filesIn(distDir)) {
  const content = await readFile(file, "utf8")
  for (const marker of forbidden) {
    if (content.includes(marker)) violations.push(`${path.relative(distDir, file)} contains ${marker}`)
  }
}

if (violations.length > 0) {
  console.error("Development-only mock data leaked into the production build:")
  for (const violation of violations) console.error(`- ${violation}`)
  process.exitCode = 1
} else {
  console.log("Production build does not contain development-only mock data.")
}
