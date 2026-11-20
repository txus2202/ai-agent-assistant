import { fileURLToPath, URL } from 'node:url'

import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'

import tailwindcss from '@tailwindcss/vite'

const env = loadEnv(process.env.NODE_ENV || 'development', '../', '')
const langfuseMetricsEnabled =
  env.LANGFUSE_METRICS_ENABLED || process.env.LANGFUSE_METRICS_ENABLED || 'false'
const langfuseDashboardUrl =
  env.VITE_LANGFUSE_DASHBOARD_URL ||
  env.LANGFUSE_DASHBOARD_URL ||
  env.LANGFUSE_BASE_URL ||
  env.LANGFUSE_HOST ||
  process.env.VITE_LANGFUSE_DASHBOARD_URL ||
  process.env.LANGFUSE_DASHBOARD_URL ||
  process.env.LANGFUSE_BASE_URL ||
  process.env.LANGFUSE_HOST ||
  ''

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    vueDevTools(),
    tailwindcss(),
  ],
  define: {
    'import.meta.env.VITE_LANGFUSE_METRICS_ENABLED': JSON.stringify(langfuseMetricsEnabled),
    'import.meta.env.VITE_LANGFUSE_DASHBOARD_URL': JSON.stringify(langfuseDashboardUrl),
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
        changeOrigin: true,
      },
    },
  },
})


