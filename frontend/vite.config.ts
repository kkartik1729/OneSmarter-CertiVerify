import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  return {
    plugins: [react()],
    server: {
      host: '0.0.0.0',
      port: 5173,
      strictPort: false,
      proxy: {
        '/api': {
          target: env.DEV_API_PROXY_TARGET || 'http://127.0.0.1:8000',
          changeOrigin: true,
          secure: false,
        },
        '/media': {
          target: env.DEV_API_PROXY_TARGET || 'http://127.0.0.1:8000',
          changeOrigin: true,
          secure: false,
        },
      },
    },
    build: {
      rollupOptions: {
        output: {
          manualChunks(id) {
            const normalizedId = id.replace(/\\/g, '/');
            if (/node_modules\/(react|react-dom|scheduler)\//.test(normalizedId)) return 'react-vendor';
            if (normalizedId.includes('/node_modules/react-router')) return 'router-vendor';
            if (normalizedId.includes('/node_modules/lucide-react')) return 'icons-vendor';
            if (normalizedId.includes('/node_modules/recharts')) return 'charts-vendor';
            return undefined;
          },
        },
      },
    },
  };
});
