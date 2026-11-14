// Strict, type-aware linting for the page: .ts and .svelte alike. `npm run check` fails on any
// warning, and deploy.sh runs it before it builds or copies anything.
import js from '@eslint/js'
import svelte from 'eslint-plugin-svelte'
import globals from 'globals'
import ts from 'typescript-eslint'
import svelteConfig from './svelte.config.js'

export default ts.config(
  { ignores: ['dist/', 'node_modules/'] },
  js.configs.recommended,
  ...ts.configs.strictTypeChecked,
  ...svelte.configs.recommended,
  {
    languageOptions: {
      globals: globals.browser,
      parserOptions: { projectService: { allowDefaultProject: ['*.mjs'] }, extraFileExtensions: ['.svelte'], tsconfigRootDir: import.meta.dirname },
    },
    rules: {
      // a number in a template string says what it is; the preset only allows strings
      '@typescript-eslint/restrict-template-expressions': ['error', { allowNumber: true }],
    },
  },
  {
    files: ['**/*.svelte', '**/*.svelte.ts'],
    languageOptions: { parserOptions: { parser: ts.parser, svelteConfig } },
  },
  { files: ['*.js', '*.config.ts'], ...ts.configs.disableTypeChecked },
  // the headless walk is a plain Node script outside the page's TypeScript project
  { files: ['*.mjs'], ...ts.configs.disableTypeChecked, languageOptions: { globals: globals.node } },
)
