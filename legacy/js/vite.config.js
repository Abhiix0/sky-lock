import { defineConfig } from 'vite';

export default defineConfig(({ command }) => ({
  // './' is needed for Electron (file:// protocol) and production builds.
  // The dev server must use '/' (the default) — a relative base breaks
  // Vite's HTML transform and causes 500 errors on index.html.
  base: command === 'build' ? './' : '/',
  server: {
    port: 3000,
    open: true
  },
  build: {
    outDir: 'dist'
  }
}));
