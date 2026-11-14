import { svelte } from '@sveltejs/vite-plugin-svelte'
import { defineConfig } from 'vite'

// The bundle is static and addresses its own files relatively, so it can be served from any path.
// The API is always at /api on the same origin; in development Vite forwards it to the data service.
export default defineConfig({
  base: './',
  plugins: [svelte()],
  server: {
    host: '127.0.0.1',
    port: 8079,
    strictPort: true,
    proxy: { '/api': process.env.SINCE_WHEN_API ?? 'http://127.0.0.1:8078' },
  },
})
