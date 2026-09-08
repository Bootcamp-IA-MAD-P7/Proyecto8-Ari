import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Fixed port so the dev server origin matches the backend's CORS
    // allowlist (CORS_ORIGINS default: http://localhost:5173). Fail loudly
    // if the port is taken instead of silently moving to another one.
    port: 5173,
    strictPort: true,
  },
})
