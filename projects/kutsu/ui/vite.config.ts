import { svelte } from '@sveltejs/vite-plugin-svelte'
import { defineConfig } from 'vite'

// The bundle addresses its own files and the API relatively, so serve.py can serve it from any path.
// In development Vite forwards the data and API paths to serve.py.
const api = 'http://127.0.0.1:8046'
export default defineConfig({
  base: './',
  plugins: [svelte()],
  server: {
    host: '127.0.0.1',
    port: 8047,
    strictPort: true,
    proxy: Object.fromEntries(
      ['/logo', '/signals.json', '/presets.json', '/reviews.json', '/pool.json', '/changes.json', '/applications.json', '/role', '/reviews', '/brief', '/progress', '/review'].map((p) => [p, api]),
    ),
  },
})
