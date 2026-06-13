<template>
  <aside class="mask-toolbar">
    <!-- File operations -->
    <div class="toolbar-group">
      <h4 class="group-title">{{ t('maskMaker.toolbar.file') }}</h4>
      <button class="toolbar-btn" @click="$emit('open-image')">
        <span class="btn-icon">📂</span>
        <span>{{ t('maskMaker.toolbar.openImage') }}</span>
      </button>
      <button class="toolbar-btn" :disabled="!imageLoaded" @click="$emit('load-mask')">
        <span class="btn-icon">📥</span>
        <span>{{ t('maskMaker.toolbar.loadMask') }}</span>
      </button>
      <button class="toolbar-btn" :disabled="!imageLoaded" @click="$emit('export-mask')">
        <span class="btn-icon">📤</span>
        <span>{{ t('maskMaker.toolbar.exportMask') }}</span>
      </button>
    </div>

    <!-- Draw tools -->
    <div class="toolbar-group">
      <h4 class="group-title">{{ t('maskMaker.toolbar.drawTools') }}</h4>
      <div class="tool-grid">
        <button
          v-for="tool in drawTools"
          :key="tool.value"
          class="tool-btn"
          :class="{ active: activeTool === tool.value }"
          :disabled="!imageLoaded"
          :title="tool.label"
          @click="$emit('select-tool', tool.value)"
        >
          <span class="tool-icon">{{ tool.icon }}</span>
          <span class="tool-label">{{ tool.label }}</span>
        </button>
      </div>
    </div>

    <!-- Mask mode -->
    <div class="toolbar-group">
      <h4 class="group-title">{{ t('maskMaker.toolbar.mode') }}</h4>
      <div class="mode-toggle">
        <button
          class="mode-btn"
          :class="{ active: maskMode === 'mask' }"
          :disabled="!imageLoaded"
          @click="$emit('select-mode', 'mask')"
        >
          {{ t('maskMaker.toolbar.mask') }}
        </button>
        <button
          class="mode-btn"
          :class="{ active: maskMode === 'unmask' }"
          :disabled="!imageLoaded"
          @click="$emit('select-mode', 'unmask')"
        >
          {{ t('maskMaker.toolbar.unmask') }}
        </button>
      </div>
    </div>

    <!-- Edit operations -->
    <div class="toolbar-group">
      <h4 class="group-title">{{ t('maskMaker.toolbar.edit') }}</h4>
      <button class="toolbar-btn" :disabled="!canUndo" @click="$emit('undo')">
        <span class="btn-icon">↩</span>
        <span>{{ t('maskMaker.toolbar.undo') }}</span>
      </button>
      <button class="toolbar-btn" :disabled="!canRedo" @click="$emit('redo')">
        <span class="btn-icon">↪</span>
        <span>{{ t('maskMaker.toolbar.redo') }}</span>
      </button>
      <button class="toolbar-btn" :disabled="!imageLoaded" @click="$emit('invert')">
        <span class="btn-icon">⇄</span>
        <span>{{ t('maskMaker.toolbar.invert') }}</span>
      </button>
      <button class="toolbar-btn" :disabled="!imageLoaded" @click="$emit('clear')">
        <span class="btn-icon">✕</span>
        <span>{{ t('maskMaker.toolbar.clear') }}</span>
      </button>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { MaskTool, MaskMode } from '@/types/mask'

const { t } = useI18n()

defineProps<{
  imageLoaded: boolean
  activeTool: MaskTool
  maskMode: MaskMode
  canUndo: boolean
  canRedo: boolean
}>()

defineEmits<{
  'open-image': []
  'load-mask': []
  'export-mask': []
  'select-tool': [tool: MaskTool]
  'select-mode': [mode: MaskMode]
  undo: []
  redo: []
  invert: []
  clear: []
}>()

const drawTools: Array<{ value: MaskTool; icon: string; label: string }> = [
  { value: 'pan', icon: '✋', label: t('maskMaker.tools.pan') },
  { value: 'rectangle', icon: '▭', label: t('maskMaker.tools.rectangle') },
  { value: 'disk', icon: '○', label: t('maskMaker.tools.disk') },
  { value: 'ellipse', icon: '⬭', label: t('maskMaker.tools.ellipse') },
  { value: 'polygon', icon: '⬠', label: t('maskMaker.tools.polygon') },
  { value: 'line', icon: '╱', label: t('maskMaker.tools.line') },
]
</script>

<style scoped>
.mask-toolbar {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px;
  background: rgba(255, 255, 255, 0.84);
  border: 1px solid rgba(226, 232, 240, 0.9);
  border-radius: 16px;
  box-shadow: var(--shadow-card);
  min-width: 160px;
}

.toolbar-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.group-title {
  font-size: 0.75rem;
  font-weight: 700;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin: 0;
  padding: 0 4px;
}

.toolbar-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.7);
  color: var(--text-primary);
  font-size: 0.85rem;
  cursor: pointer;
  transition: all var(--transition-fast);
  text-align: left;
}

.toolbar-btn:hover:not(:disabled) {
  background: var(--primary-bg);
  border-color: var(--primary);
}

.toolbar-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.btn-icon {
  font-size: 1rem;
  width: 20px;
  text-align: center;
  flex-shrink: 0;
}

/* Tool grid */
.tool-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
}

.tool-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 8px 4px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.7);
  color: var(--text-primary);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.tool-btn:hover:not(:disabled) {
  background: var(--primary-bg);
  border-color: var(--primary);
}

.tool-btn.active {
  background: var(--primary);
  color: var(--text-inverse);
  border-color: var(--primary);
  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.3);
}

.tool-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.tool-icon {
  font-size: 1.2rem;
}

.tool-label {
  font-size: 0.7rem;
  font-weight: 600;
}

/* Mode toggle */
.mode-toggle {
  display: flex;
  gap: 4px;
}

.mode-btn {
  flex: 1;
  padding: 8px 4px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.7);
  color: var(--text-primary);
  font-size: 0.8rem;
  font-weight: 600;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.mode-btn:hover:not(:disabled) {
  background: var(--primary-bg);
}

.mode-btn.active {
  background: var(--primary);
  color: var(--text-inverse);
  border-color: var(--primary);
}

.mode-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
</style>
