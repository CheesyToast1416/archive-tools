import js from "@eslint/js";
import { configs as tsConfigs, parser as tsParser } from "typescript-eslint";
import sveltePlugin from "eslint-plugin-svelte";
import svelteParser from "svelte-eslint-parser";
import globals from "globals";

/** @type {import("eslint").Linter.Config[]} */
export default [
  js.configs.recommended,
  ...tsConfigs.recommended,
  ...sveltePlugin.configs["flat/recommended"],
  {
    languageOptions: {
      globals: {
        ...globals.browser,
        ...globals.node,
      },
    },
  },
  {
    files: ["**/*.svelte"],
    languageOptions: {
      parser: svelteParser,
      parserOptions: { parser: tsParser },
    },
  },
  {
    rules: {
      // Tauri/SSE event payloads legitimately require `any` at the boundary
      "@typescript-eslint/no-explicit-any": "warn",
    },
  },
  {
    ignores: [".svelte-kit/", "build/", "node_modules/", "src-tauri/"],
  },
];
