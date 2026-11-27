import { createHash } from 'node:crypto'
import { existsSync, readdirSync, readFileSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { fileURLToPath, URL } from 'node:url'

import { defineConfig, loadEnv, type Plugin } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'

import tailwindcss from '@tailwindcss/vite'

/**
 * Deterministic zero-dependency PWA build plugin.
 * Injects a content-derived SHA-256 cache version and core App Shell asset URLs into dist/sw.js.
 */
function ateneaPwaPlugin(): Plugin {
  let outDir = 'dist'
  return {
    name: 'atenea-pwa-manifest-injector',
    apply: 'build',
    configResolved(config) {
      outDir = resolve(config.root, config.build.outDir)
    },
    writeBundle() {
      const swPath = resolve(outDir, 'sw.js')
      const indexPath = resolve(outDir, 'index.html')
      const assetsDir = resolve(outDir, 'assets')
      if (!existsSync(swPath) || !existsSync(indexPath)) {
        return
      }

      const indexHtml = readFileSync(indexPath, 'utf-8')
      const allAssetFiles = existsSync(assetsDir) ? readdirSync(assetsDir).sort() : []

      // Compute deterministic revision hash across index.html and all emitted asset filenames
      const hash = createHash('sha256')
      hash.update(indexHtml)
      for (const file of allAssetFiles) {
        hash.update(file)
      }
      const revision = hash.digest('hex').slice(0, 12)

      // Precache entry bundles referenced in index.html plus core SPA view chunks
      const referencedAssets = new Set<string>()
      const assetRegex = /(?:src|href)="(\/assets\/[^"]+)"/g
      for (const match of indexHtml.matchAll(assetRegex)) {
        if (match[1]) {
          referencedAssets.add(match[1])
        }
      }
      const coreViewPrefix = /^(HomeView|TopologyView|HistoryView|LoginView|InitialSetupView)-.*\.(js|css)$/
      for (const file of allAssetFiles) {
        if (coreViewPrefix.test(file)) {
          referencedAssets.add(`/assets/${file}`)
        }
      }

      const serializedAssets = Array.from(referencedAssets)
        .sort()
        .map((u) => JSON.stringify(u))
        .join(', ')

      const rawSw = readFileSync(swPath, 'utf-8')
      const compiledSw = rawSw
        .replace('__ATENEA_SW_VERSION__', revision)
        .replace('/* __ATENEA_PRECACHE_MANIFEST__ */', serializedAssets)
      writeFileSync(swPath, compiledSw, 'utf-8')
    },
  }
}

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
    ateneaPwaPlugin(),
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


