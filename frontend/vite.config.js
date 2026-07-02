import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const SERVER_PORT = 8000;

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: `http://localhost:${SERVER_PORT}`,
        changeOrigin: true,
      },
    },
  },
});
