import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";

export default [
  js.configs.recommended,
  {
    files: ["src/**/*.{ts,tsx}"],
    plugins: {
      "react-hooks": reactHooks,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "no-unused-vars": "off", // TypeScript handles this
    },
    languageOptions: {
      ecmaVersion: 2020,
      sourceType: "module",
      globals: {
        document: "readonly",
        window: "readonly",
        console: "readonly",
        alert: "readonly",
        setTimeout: "readonly",
      },
    },
  },
  {
    ignores: ["dist/", "node_modules/"],
  },
];
