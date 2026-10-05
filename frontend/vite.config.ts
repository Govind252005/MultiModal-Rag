import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Vite dev-server config.
// The proxy forwards every request that starts with `/api` to the Python
// backend running on http://localhost:8000. Because of this, the whole
// frontend can use RELATIVE URLs like `/api/query` or `/api/media/<file>`.
// That also means media/image/audio URLs work directly inside
// <img src="/api/media/..."> and <audio src="/api/media/..."> tags.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
