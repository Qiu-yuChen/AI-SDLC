import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8001',
      '/ws': {
        target: 'http://localhost:8001',
        ws: true,
        changeOrigin: true,
      },
      '/workspace': 'http://localhost:8001',
    },
  },
})
