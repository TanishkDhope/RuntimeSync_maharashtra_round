import js from "@eslint/js"
import reactHooks from "eslint-plugin-react-hooks"
import reactRefresh from "eslint-plugin-react-refresh"
import { defineConfig, globalIgnores } from "eslint/config"
import globals from "globals"

export default defineConfig([
  globalIgnores(["dist"]),
  {
    files: ["src/**/*.{js,jsx}"],
    extends: [js.configs.recommended, reactHooks.configs.flat.recommended, reactRefresh.configs.vite],
    languageOptions: {
      ecmaVersion: "latest",
      globals: globals.browser,
      parserOptions: { ecmaFeatures: { jsx: true }, sourceType: "module" },
    },
    rules: {
      "no-unused-vars": ["error", { varsIgnorePattern: "^([A-Z_]|motion$)", argsIgnorePattern: "^_" }],
    },
  },
  {
    files: ["vite.config.js", "eslint.config.js", "scripts/**/*.mjs"],
    extends: [js.configs.recommended],
    languageOptions: { ecmaVersion: "latest", sourceType: "module", globals: globals.node },
  },
])
