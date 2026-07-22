/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
//
// Task 6: dev proxy + django-vite build wiring.
// - `base` matches django-vite's ``static_url_prefix='frontend'`` so both
//   the dev server and prod URLs land at ``/static/frontend/...``.
// - `server.proxy` forwards /api, /admin, /media, /static to Django (:8000)
//   so the SPA at :5173 can talk same-origin to the backend in dev.
// - `build.outDir` + `manifest` write the prod bundle into Django's
//   STATICFILES_DIRS target so `collectstatic` picks it up. django-vite
//   reads `manifest.json` from there in prod.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: '/static/frontend/',
  resolve: {
    alias: {
      '@': '/src',
    },
  },
  server: {
    port: 5173,
    // Dev proxy → Django. Same-origin from the SPA's perspective so the
    // session cookie set by /login/ is sent on every fetch().
    //
    // ``/static`` uses a filter so Vite keeps serving its own dev assets
    // under ``/static/frontend/`` (set via ``base`` above) — only Django's
    // own static files (anything NOT under /static/frontend/) are proxied.
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/admin': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/media': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/static': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        // Skip Vite-served assets (its base is /static/frontend/).
        bypass: (req) => {
          if (req.url && req.url.startsWith('/static/frontend/')) {
            return req.url // tell Vite to handle it locally
          }
          return undefined // proxy to Django
        },
      },
    },
  },
  build: {
    // Emit into a dir that's already on STATICFILES_DIRS so the dev
    // runserver and prod `collectstatic` both serve the built assets.
    // `property_rental/` is the Django project root (the dir containing
    // manage.py); we anchor relative to this config file under frontend/.
    outDir: '../property_rental/rentals/static/frontend',
    emptyOutDir: true,
    manifest: 'manifest.json',
    // Vite 8's default entry is ``index.html`` (HTML-driven build), but
    // django-vite looks up the entry by its source path (``src/main.tsx``).
    // Declaring the JS entry here puts both keys in the manifest so
    // ``{% vite_asset 'src/main.tsx' %}`` works in prod, and Vite's dev
    // server still serves it under ``/static/frontend/src/main.tsx``.
    rollupOptions: {
      input: 'src/main.tsx',
    },
  },
  // Task 10: Vitest config. Vitest reads this `test` block automatically
  // from vite.config.ts — no separate vitest.config.ts needed.
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    css: false,
  },
})
