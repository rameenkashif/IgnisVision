/// <reference types="vitest" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import basicSsl from '@vitejs/plugin-basic-ssl';

// Dev: HTTPS so getUserMedia works from a phone on the LAN. /api and /ws proxy to the backend.
const backend = process.env.VITE_BACKEND_URL ?? 'http://localhost:8000';

export default defineConfig(({ mode }) => ({
  plugins: [react(), ...(mode === 'development' ? [basicSsl()] : [])],
  server: {
    host: true,
    port: 5173,
    proxy: {
      '/api': backend,
      '/ws': { target: backend.replace(/^http/, 'ws'), ws: true },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/setupTests.ts'],
  },
}));
