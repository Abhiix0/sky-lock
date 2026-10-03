import { defineConfig } from 'vite';
import path from 'path';

export default defineConfig({
  root: path.resolve(__dirname, 'space_view'),
  base: './',
  build: {
    outDir: path.resolve(__dirname, '../../src/skylock/ui/web3d/static'),
    emptyOutDir: false, // Don't wipe assets/ we already copied!
    target: 'es2022'
  }
});
