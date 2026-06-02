import { builtinModules } from 'node:module'
import path from 'node:path'
import { defineConfig } from 'vite'

const external = ['electron', ...builtinModules, ...builtinModules.map((moduleName) => `node:${moduleName}`)]

export default defineConfig({
  build: {
    outDir: 'dist-electron',
    emptyOutDir: true,
    minify: false,
    sourcemap: true,
    lib: {
      entry: {
        'main/index': path.resolve(__dirname, 'electron/main.ts'),
        'tools/python-health': path.resolve(__dirname, 'electron/python-health-cli.ts')
      },
      formats: ['es'],
      fileName: (_format, entryName) => `${entryName}.js`
    },
    rollupOptions: {
      external
    }
  }
})
