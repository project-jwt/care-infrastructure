import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const SERVER_PORT = 8000;

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        // 127.0.0.1, not localhost: Node resolves localhost to IPv6 (::1)
        // but uvicorn binds IPv4 only, so the proxy would get refused.
        target: `http://127.0.0.1:${SERVER_PORT}`,
        changeOrigin: true,
      },
    },
  },
});
