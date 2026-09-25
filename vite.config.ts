import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'node:path'

export default defineConfig(({ mode }) => ({
  plugins: [vue()],
  base: mode === 'web' ? '/' : './',
  resolve: {
    alias: [
      { find: '@', replacement: path.resolve(__dirname, './src') },
      // AI isolation (v0.3.0): only the Jev test build (--mode jev) gets the
      // real AssistantBar; every other build resolves a no-op stub, so the AI
      // subtree (src/ai/**, providers, skills) can never enter main bundles.
      // AI 隔离（v0.3.0）：只有 Jev 测试构建（--mode jev）解析真实
      // AssistantBar；其余构建一律解析空桩，AI 子树（src/ai/**、providers、
      // skills）绝无可能进入主线产物。
      ...(mode === 'jev'
        ? []
        : [{
            find: /^@\/components\/ai\/AssistantBar\.vue$/,
            replacement: path.resolve(__dirname, './src/ai-stub/AssistantBarStub.vue')
          }])
    ]
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true
  },
  build: {
    outDir: 'dist'
  }
}))