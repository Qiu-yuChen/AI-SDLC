import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const BACKEND_PORT = process.env.BACKEND_PORT || '8001'
const FRONTEND_PORT = parseInt(process.env.FRONTEND_PORT || '5173')

export default defineConfig({
  plugins: [react()],
  server: {
    port: FRONTEND_PORT,
    host: '0.0.0.0',
    allowedHosts: true,
    proxy: {
      '/api': `http://localhost:${BACKEND_PORT}`,
      '/ws': {
        target: `http://localhost:${BACKEND_PORT}`,
        ws: true,
        changeOrigin: true,
      },
      '/workspace': `http://localhost:${BACKEND_PORT}`,
    },
  },
})
