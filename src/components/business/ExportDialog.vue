<template>
  <div :data-testid="testIds.exportDialog" class="export-dialog">
    <h3 class="ed-title">{{ t('business.export.title') }}</h3>

    <div class="ed-body">
      <!-- Export mode / 导出模式 -->
      <label class="ed-field">
        <span class="ed-field-label">{{ t('business.export.mode') }}</span>
        <div class="ed-mode-row">
          <button
            type="button"
            class="ed-mode-btn"
            :class="{ active: exportMode === 'single' }"
            @click="exportMode = 'single'"
          >{{ t('business.export.mergeSingle') }}</button>
          <button
            type="button"
            class="ed-mode-btn"
            :class="{ active: exportMode === 'separate' }"
            @click="exportMode = 'separate'"
          >{{ t('business.export.exportSeparate') }}</button>
        </div>
      </label>

      <!-- Format selector / 格式选择 -->
      <label class="ed-field">
        <span class="ed-field-label">{{ t('business.export.chooseFormat') }}</span>
        <select
          class="ed-select"
          :value="selectedFormat"
          :data-testid="testIds.exportFormatSelect"
          @change="onFormatChange($event)"
        >
          <option v-for="fmt in formats" :key="fmt" :value="fmt">
            {{ fmt.toUpperCase() }}
          </option>
        </select>
      </label>

      <!-- Output path / 输出路径 (Web: auto-download) -->
      <p v-if="!transport.isDesktop()" class="ed-web-hint">
        {{ t('business.export.webDownloadHint') }}
      </p>

      <!-- Export button / 导出按钮 -->
      <button
        type="button"
        class="ed-execute"
        :disabled="!canExport"
        :data-testid="testIds.exportExecute"
        @click="handleExport"
      >
        {{ transport.isDesktop() ? t('business.export.execute') : t('business.export.download') }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { testIds } from '@/lib/testIds'
import { useTransport } from '@/lib/transport'

export type ExportFormat = 'txt' | 'hdf5' | 'tiff' | 'csv' | 'xy' | 'edf' | 'npy'
export type ExportMode = 'single' | 'separate'

const props = withDefaults(defineProps<{
  result?: unknown
  formats?: ExportFormat[]
}>(), {
  result: undefined,
  formats: () => ['txt', 'csv', 'hdf5', 'tiff', 'edf', 'npy'] as ExportFormat[],
})

const emit = defineEmits<{
  export: [payload: { format: ExportFormat; path: string; mode: ExportMode }]
}>()

const { t } = useI18n()
const transport = useTransport()

const selectedFormat = ref<ExportFormat>(props.formats[0])
const exportMode = ref<ExportMode>('single')

const FORMAT_EXTENSIONS: Record<ExportFormat, string[]> = {
  txt: ['txt'],
  csv: ['csv'],
  hdf5: ['h5', 'hdf5'],
  tiff: ['tif', 'tiff'],
  xy: ['xy'],
  edf: ['edf'],
  npy: ['npy'],
}

const currentFilters = computed(() => {
  const exts = FORMAT_EXTENSIONS[selectedFormat.value] ?? ['*']
  return [{ name: selectedFormat.value.toUpperCase(), extensions: exts }]
})

const canExport = computed(() => {
  // Desktop: always enabled — file dialog opens on click
  // Web: always enabled — triggers browser download
  return true
})

async function handleExport(): Promise<void> {
  if (transport.isDesktop()) {
    let finalPath: string | null = null

    if (exportMode.value === 'single') {
      // Open save-file dialog on click
      finalPath = await transport.selectSavePath({ filters: currentFilters.value })
      if (!finalPath) return // user cancelled

      // Auto-append extension if missing
      const exts = FORMAT_EXTENSIONS[selectedFormat.value] ?? []
      const hasKnownExt = exts.some((ext) => finalPath!.toLowerCase().endsWith(`.${ext.toLowerCase()}`))
      if (!hasKnownExt && exts.length > 0) {
        finalPath = `${finalPath}.${exts[0]}`
      }
    } else {
      // Open folder-selection dialog on click
      finalPath = await transport.selectFolder()
      if (!finalPath) return // user cancelled
    }

    emit('export', { format: selectedFormat.value, path: finalPath, mode: exportMode.value })
  } else {
    // Web mode: trigger browser download via transport
    emit('export', { format: selectedFormat.value, path: '', mode: exportMode.value })
  }
}

function onFormatChange(event: Event): void {
  const val = (event.target as unknown as HTMLSelectElement).value
  selectedFormat.value = val as ExportFormat
}
</script>

<style scoped>
.export-dialog {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.ed-title {
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.ed-body {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.ed-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.ed-field-label {
  font-size: 0.8125rem;
  color: var(--text-secondary);
  font-weight: 500;
}

.ed-mode-row {
  display: flex;
  gap: 8px;
}

.ed-mode-btn {
  flex: 1;
  padding: 6px 10px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-secondary);
  font-size: 0.8125rem;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.ed-mode-btn.active {
  background: var(--primary);
  color: var(--text-inverse);
  border-color: var(--primary);
}

.ed-mode-btn:not(.active):hover {
  border-color: var(--border-focus);
}

.ed-select {
  padding: 8px 10px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: 0.875rem;
  transition: border-color var(--transition-fast);
}

.ed-select:focus {
  outline: none;
  border-color: var(--border-focus);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}

.ed-execute {
  padding: 10px 24px;
  border-radius: var(--radius-md);
  border: none;
  background: var(--primary);
  color: var(--text-inverse);
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  transition: opacity var(--transition-fast);
}

.ed-execute:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.ed-execute:not(:disabled):hover {
  opacity: 0.9;
}
</style>
