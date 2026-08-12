import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { execSync } from 'node:child_process';

const silverBackendUrl =
  process.env.SILVER_API_URL ?? 'https://silver-refinement-agent-mkqutd4koq-uc.a.run.app';

function readIdentityToken() {
  if (process.env.GCP_IDENTITY_TOKEN) return process.env.GCP_IDENTITY_TOKEN;
  try {
    return execSync('gcloud auth print-identity-token', {
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore'],
    }).trim();
  } catch {
    return '';
  }
}

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: silverBackendUrl,
        changeOrigin: true,
        secure: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
        configure: (proxy) => {
          proxy.on('proxyReq', (proxyReq) => {
            const token = readIdentityToken();
            if (token) proxyReq.setHeader('Authorization', `Bearer ${token}`);
          });
        },
      },
    },
  },
});
