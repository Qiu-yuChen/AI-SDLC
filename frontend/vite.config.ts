import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '')
  const backendTarget = env.AI_SDLC_BACKEND_URL || env.VITE_BACKEND_URL || 'http://localhost:7070'
  const host = env.VITE_HOST || '127.0.0.1'
  const port = Number(env.VITE_PORT || 3000)

  return {
    plugins: [react()],
    server: {
      host,
      port,
      proxy: {
        '/api': backendTarget,
        '/ws': {
          target: backendTarget,
          ws: true,
          changeOrigin: true,
        },
        '/workspace': backendTarget,
      },
    },
  }
})
