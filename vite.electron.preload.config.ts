import { builtinModules } from 'node:module'
import path from 'node:path'
import { defineConfig } from 'vite'

const external = ['electron', ...builtinModules, ...builtinModules.map((moduleName) => `node:${moduleName}`)]

export default defineConfig({
  build: {
    outDir: 'dist-electron',
    emptyOutDir: false,
    sourcemap: true,
    lib: {
      entry: path.resolve(__dirname, 'electron/preload.ts'),
      formats: ['cjs'],
      fileName: () => 'preload/index.js'
    },
    rollupOptions: {
      external
    }
  }
})
