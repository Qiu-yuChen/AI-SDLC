import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5050,
    proxy: {
      '/api': 'http://localhost:7070',
      '/ws': {
        target: 'http://localhost:7070',
        ws: true,
        changeOrigin: true,
      },
      '/workspace': 'http://localhost:7070',
    },
  },
})
