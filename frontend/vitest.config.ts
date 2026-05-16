import { defineConfig } from "vitest/config";
import { svelte } from "@sveltejs/vite-plugin-svelte";
import { resolve } from "path";

export default defineConfig({
  plugins: [svelte({ hot: !process.env.VITEST })],
  resolve: {
    alias: {
      $lib: resolve(__dirname, "src/lib"),
    },
    conditions: ["browser"],
  },
  test: {
    include: ["src/**/*.test.ts"],
    environment: "happy-dom",
    setupFiles: ["src/tests/setup.ts"],
    globals: true,
    coverage: {
      provider: "v8",
      include: ["src/lib/**"],
      reporter: ["text", "html"],
    },
  },
});
