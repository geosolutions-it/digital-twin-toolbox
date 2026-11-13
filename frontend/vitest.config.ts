import { defineConfig } from "vitest/config"

// separate from vite.config.ts so tests don't run the router code generator
export default defineConfig({
  test: { include: ["src/**/*.test.ts"] },
})
