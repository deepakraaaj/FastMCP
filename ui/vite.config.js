import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react-swc'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/mcp': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
      },
      '/session': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
      },
      '/chat': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
      },
      '/admin': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
      },
      '/healthz': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
      },
    },
  },
})
