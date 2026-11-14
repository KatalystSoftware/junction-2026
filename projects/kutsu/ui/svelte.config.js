import { vitePreprocess } from '@sveltejs/vite-plugin-svelte'

// Styles go through Vite before Svelte scopes them, so a component can `@import` a stylesheet it shares
// with another (flow.css, finished.css) and still have every rule scoped to itself.
/** @type {import("@sveltejs/vite-plugin-svelte").SvelteConfig} */
export default { preprocess: vitePreprocess() }
