import { defineConfig } from 'vite';
import path from 'path';

export default defineConfig({
  root: path.resolve(__dirname, 'gimbal_view'),
  base: './',
  build: {
    outDir: path.resolve(__dirname, '../../src/skylock/ui/web3d/static_gimbal'),
    emptyOutDir: false,
    target: 'es2022'
  }
});
