import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const backend = 'http://127.0.0.1:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Spotify requires loopback IPs (not "localhost") for redirect URIs,
    // so serve the app on 127.0.0.1 to keep origins consistent.
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/api': backend,
      '/auth': backend,
    },
  },
})
