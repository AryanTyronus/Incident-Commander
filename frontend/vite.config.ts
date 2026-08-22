import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // The incident event stream is a WebSocket under this same prefix
      // (/api/incidents/{id}/stream), so the proxy must forward upgrades too.
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: true,
      },
      '/health': {
        target: 'http://localhost:8000',
      },
      '/ready': {
        target: 'http://localhost:8000',
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    css: false,
  },
})
