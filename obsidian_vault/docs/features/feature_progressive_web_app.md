---
created: 2026-11-27
updated: 2026-11-27
type: spec
phase: 7
layer: presentation
status: implemented
category: meta-project
tags: [sdd, pwa, manifest, service-worker, offline, multi-tenant, security, vue3, nginx]
---

# Feature Specification: Installable Progressive Web App (PWA) with Multi-Tenant Safe Caching

## 1. Context & Problem Statement

ATENEA (`ai-agent-assistant`) is used across desktop workstations, tablets, and mobile devices (including hands-free voice orchestration via Faster-Whisper, Kokoro-ONNX, and Vosk wake-words). Previously, `frontend/index.html` included iOS-specific meta tags (`apple-mobile-web-app-capable`), but lacked a W3C Web App Manifest (`manifest.webmanifest`), standard `192x192` / `512x512` / `maskable` icons, a Service Worker (`sw.js`), and progressive in-app installation support. Consequently, Chromium, Edge, Android, and desktop operating systems could not install ATENEA as a standalone native-like application or launch its UI shell offline when the backend container restarts.

At the same time, ATENEA is a **multi-tenant, real-time streaming system** authenticated via `HttpOnly` JWT cookies (**ADR-022**). Naive Service Worker caching of `/api/*` responses or `/ws/*` channels would risk stale state or cross-operator cache leakage on shared browsers.

### Key Objectives

1. **Standards-Compliant Web App Manifest (`manifest.webmanifest`):** Declare an explicit same-origin `"id": "/"`, `"start_url": "/"`, `"scope": "/"`, `"display": "standalone"`, space-dark `"theme_color"` / `"background_color"` (`#05070c`), and separate `"purpose": "any"` (`192x192`, `512x512`) and `"purpose": "maskable"` (`512x512` safe-zone padded) PNG icons.
2. **Zero-Dependency Deterministic Build Integration:** Inject hashed Vite build assets (`/assets/*`) and a deterministic SHA-256 build revision into `dist/sw.js` via a lightweight native Vite plugin (`ateneaPwaPlugin`) without introducing third-party Rollup/Workbox dependency trees or CVE surface.
3. **Strict Multi-Tenant Network-Only Boundary (`sw.js`):**
   - Strictly bypass (`Network-Only`) all `/api/*`, `/ws/*`, `/health`, `/metrics`, `/docs`, `/redoc`, and `/openapi.json` paths, as well as all non-`GET` or cross-origin requests.
   - Serve SPA navigation requests (`request.mode === 'navigate'`) via **Network-First** with offline fallback to cached `/index.html` (rendering `BackendUnavailable.vue` cleanly when disconnected).
   - Serve immutable hashed `/assets/*` bundles via **Cache-First** and root icons/manifest via **Stale-While-Revalidate**, purging stale caches immediately on `activate` (`skipWaiting` + `clients.claim`).
4. **Production-Scoped Registration (`registerServiceWorker.ts`):** Register `/sw.js` with `updateViaCache: 'none'` exclusively in production secure contexts so Vite HMR and Playwright E2E route mocks remain unaffected in development/testing.
5. **Progressive Enhancement In-App Install Control (`usePwaInstall.ts` & `AppHeader.vue`):** Support the modern Web Install API (`navigator.install()`) with automatic fallback to `beforeinstallprompt` inside the operator dropdown menu, keeping the install control hidden (`hidden`) when unsupported or already installed, and using `aria-disabled` during user activation.
6. **Nginx Hardening (`frontend/nginx.conf`):** Serve `/manifest.webmanifest` with `Content-Type: application/manifest+json` and enforce `Cache-Control: no-cache, no-store, must-revalidate` on both `/manifest.webmanifest` and `/sw.js` alongside all anti-indexing and security headers.

---

## 2. Acceptance Criteria

- **AC-1 (Manifest & Icons):** `frontend/index.html` sets `lang="es"` and links `/manifest.webmanifest`, which declares `"id": "/"`, `"display": "standalone"`, and valid `192x192`, `512x512`, and `512x512` `maskable` PNG icons present in `frontend/public/`.
- **AC-2 (Multi-Tenant Cache Isolation):** `sw.js` never intercepts or caches `/api/*` or `/ws/*` traffic, uses Network-First with `/index.html` fallback for SPA navigations, and purges outdated `atenea-app-shell-*` caches upon activation.
- **AC-3 (Deterministic Build Injection):** Running `npm run build` produces `dist/sw.js` with a concrete SHA-256 revision identifier and precache manifest including emitted `/assets/*` bundles.
- **AC-4 (Registration Guards):** `registerAteneaServiceWorker` skips registration when `isProd` is `false` or `isSecureContext` is `false`, and registers `/sw.js` with `{ scope: '/', updateViaCache: 'none' }` when enabled.
- **AC-5 (Progressive In-App Install):** `usePwaInstall` and `AppHeader.vue` keep the install action hidden by default, reveal it when `navigator.install()` or `beforeinstallprompt` is available, preserve focus via `aria-disabled="true"`, clear single-use `beforeinstallprompt` events prior to awaiting `prompt()`, and handle `AbortError` gracefully.
- **AC-6 (Nginx MIME & Cache Control):** `frontend/nginx.conf` serves `/manifest.webmanifest` as `application/manifest+json` and prevents browser caching of `/sw.js` and `/manifest.webmanifest`.
