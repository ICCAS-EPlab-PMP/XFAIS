<template>
  <div v-if="visible" class="dialog-backdrop" @click.self="$emit('close')">
    <div class="dialog-panel">
      <h3 class="dialog-title">{{ t('maskMaker.export.title') }}</h3>

      <div class="dialog-body">
        <!-- Format selection -->
        <div class="form-group">
          <label class="form-label">{{ t('maskMaker.export.format') }}</label>
          <div class="format-grid">
            <button
              v-for="fmt in MASK_EXPORT_FORMATS"
              :key="fmt.value"
              class="format-btn"
              :class="{ active: selectedFormat === fmt.value }"
              @click="selectedFormat = fmt.value"
            >
              {{ fmt.label }}
            </button>
          </div>
        </div>

        <!-- Save path -->
        <div class="form-group">
          <label class="form-label">{{ t('maskMaker.export.savePath') }}</label>
          <div class="path-row">
            <input
              v-model="savePath"
              type="text"
              class="path-input"
              readonly
              :placeholder="t('maskMaker.export.noPath')"
            />
            <button class="browse-btn" @click="browseSavePath">
              {{ t('maskMaker.export.browse') }}
            </button>
          </div>
        </div>
      </div>

      <div class="dialog-footer">
        <button class="cancel-btn" @click="$emit('close')">
          {{ t('maskMaker.export.cancel') }}
        </button>
        <button
          class="export-btn"
          :disabled="!savePath || exporting"
          @click="doExport"
        >
          {{ exporting ? t('maskMaker.export.exporting') : t('maskMaker.export.export') }}
        </button>
      </div>

      <p v-if="error" class="error-msg">{{ error }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useTransport } from '@/lib/transport'
import { MASK_EXPORT_FORMATS, type MaskExportFormat } from '@/types/mask'

const { t } = useI18n()
const transport = useTransport()

defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  close: []
  export: [payload: { format: MaskExportFormat; savePath: string }]
}>()

const selectedFormat = ref<MaskExportFormat>('edf')
const savePath = ref('')
const exporting = ref(false)
const error = ref('')

async function browseSavePath(): Promise<void> {
  const fmt = MASK_EXPORT_FORMATS.find((f) => f.value === selectedFormat.value)
  const filters = fmt
    ? [{ name: fmt.label, extensions: fmt.extensions }]
    : undefined

  try {
    const result = await transport.selectSavePath({
      filters,
      defaultPath: `mask.${selectedFormat.value}`,
    })
    if (result) {
      savePath.value = result
    }
  } catch {
    // User cancelled
  }
}

function doExport(): void {
  if (!savePath.value) return
  error.value = ''
  exporting.value = true
  emit('export', {
    format: selectedFormat.value,
    savePath: savePath.value,
  })
}
</script>

<style scoped>
.dialog-backdrop {
  position: fixed;
  inset: 0;
  z-index: var(--z-modal);
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(15, 23, 42, 0.5);
  backdrop-filter: blur(4px);
}

.dialog-panel {
  width: min(480px, 90vw);
  padding: 24px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.96);
  border: 1px solid rgba(226, 232, 240, 0.9);
  box-shadow: 0 24px 48px rgba(15, 23, 42, 0.15);
}

.dialog-title {
  font-size: 1.15rem;
  font-weight: 700;
  margin: 0 0 20px;
  color: var(--text-primary);
}

.dialog-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-label {
  font-size: 0.8rem;
  font-weight: 700;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.format-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 6px;
}

.format-btn {
  padding: 8px 6px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.7);
  color: var(--text-primary);
  font-size: 0.78rem;
  font-weight: 600;
  cursor: pointer;
  transition: all var(--transition-fast);
  text-align: center;
}

.format-btn:hover {
  background: var(--primary-bg);
  border-color: var(--primary);
}

.format-btn.active {
  background: var(--primary);
  color: var(--text-inverse);
  border-color: var(--primary);
}

.path-row {
  display: flex;
  gap: 8px;
}

.path-input {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: 10px;
  font-size: 0.85rem;
  background: rgba(248, 250, 252, 0.8);
  color: var(--text-primary);
}

.path-input::placeholder {
  color: var(--text-secondary);
  opacity: 0.5;
}

.browse-btn {
  padding: 8px 16px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.8);
  color: var(--text-primary);
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  transition: all var(--transition-fast);
}

.browse-btn:hover {
  background: var(--primary-bg);
  border-color: var(--primary);
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 20px;
}

.cancel-btn {
  padding: 10px 20px;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.8);
  color: var(--text-primary);
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.cancel-btn:hover {
  background: rgba(241, 245, 249, 0.9);
}

.export-btn {
  padding: 10px 20px;
  border: none;
  border-radius: 12px;
  background: var(--primary);
  color: var(--text-inverse);
  font-size: 0.9rem;
  font-weight: 700;
  cursor: pointer;
  transition: opacity var(--transition-fast);
}

.export-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.error-msg {
  margin: 12px 0 0;
  color: #ef4444;
  font-size: 0.8rem;
}
</style>
