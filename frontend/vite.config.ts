import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: false, // fall back to 5174 if 5173 is taken; both are in CORS_ALLOWED_ORIGINS
  },
});
