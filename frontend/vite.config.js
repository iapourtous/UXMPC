import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    watch: {
      usePolling: true
    },
    proxy: {
      '/api': {
        target: 'http://api:8000',
        changeOrigin: true
      },
      '/ws': {
        target: 'http://api:8000',
        ws: true,
        changeOrigin: true
      },
      '/logs': {
        target: 'http://api:8000',
        changeOrigin: true
      },
      '/mcp': {
        target: 'http://api:8000',
        changeOrigin: true
      },
      '/services': {
        target: 'http://api:8000',
        changeOrigin: true
      },
      '/agents': {
        target: 'http://api:8000',
        changeOrigin: true
      },
      '/settings': {
        target: 'http://api:8000',
        changeOrigin: true
      },
      '/meta-agent': {
        target: 'http://api:8000',
        changeOrigin: true
      },
      '/agent': {
        target: 'http://api:8000',
        changeOrigin: true
      },
      '/demos': {
        target: 'http://api:8000',
        changeOrigin: true
      },
      '/llms': {
        target: 'http://api:8000',
        changeOrigin: true
      }
    }
  }
})