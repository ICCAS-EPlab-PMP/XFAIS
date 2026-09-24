<template>
  <div v-if="open" class="ced-backdrop" @click.self="$emit('close')">
    <div class="ced-panel">
      <h3 class="ced-title">{{ t('calibration.export.title') }}</h3>

      <div class="ced-body">
        <!-- Save path / 保存路径 -->
        <div class="ced-group">
          <label class="ced-label">{{ t('calibration.export.pathLabel') }}</label>
          <div class="ced-path-row">
            <input
              v-model="savePath"
              type="text"
              class="ced-input"
              :placeholder="transport.isDesktop() ? 'calibration.poni' : '/output/calibration.poni'"
            />
            <button
              v-if="transport.isDesktop()"
              type="button"
              class="ced-btn ced-btn--browse"
              @click="browseSavePath"
            >
              …
            </button>
          </div>
        </div>

        <!-- Save action / 保存 -->
        <button
          type="button"
          class="ced-btn ced-btn--primary"
          :disabled="!savePath.trim() || saving"
          @click="doSave"
        >
          {{ t('calibration.export.savePoni') }}
        </button>

        <!-- Saved path / 已保存路径 -->
        <p v-if="result?.path" class="ced-saved">
          {{ t('calibration.export.saved') }}: <code>{{ result.path }}</code>
        </p>

        <!-- Citation panel / 引用面板 -->
        <div v-if="result" class="ced-citation">
          <h4 class="ced-citation-title">{{ t('calibration.export.citationTitle') }}</h4>
          <p class="ced-citation-body">{{ t('calibration.export.citationBody') }}</p>
          <div class="ced-doi-row">
            <button type="button" class="ced-btn ced-btn--doi" @click="openDoi('calib2')">
              {{ t('calibration.export.citationCalib2') }}
            </button>
            <button type="button" class="ced-btn ced-btn--doi" @click="openDoi('pyfai')">
              {{ t('calibration.export.citationPyfai') }}
            </button>
          </div>
          <p class="ced-license-note">{{ t('calibration.export.licenseNote') }}</p>
        </div>
      </div>

      <div class="ced-footer">
        <button type="button" class="ced-btn" @click="$emit('close')">
          ✕
        </button>
        <button
          v-if="result"
          type="button"
          class="ced-btn ced-btn--go"
          @click="onGoIntegrate"
        >
          {{ t('calibration.export.goIntegrate') }} →
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * CalibExportDialog.vue — 标定向导第 4 步：导出 .poni + 引用面板
 * Calibration wizard step 4: save the .poni (desktop save dialog / web path
 * input), then show the citation panel (calib2 + pyFAI papers, MIT note)
 * with DOI link buttons and a shortcut into 1-D integration.
 */
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useTransport } from '@/lib/transport'

/** Citation links returned by the backend 'export_poni' action (all optional). */
export interface CalibCitation {
  /** Full DOI URL for the pyFAI-calib2 paper. */
  calib2Url?: string
  /** Full DOI URL for the pyFAI paper. */
  pyfaiUrl?: string
  /** Optional license note override (defaults to the i18n text). */
  note?: string
  [key: string]: unknown
}

/** Result of the backend 'export_poni' action. */
export interface CalibExportResult {
  /** Absolute path of the written .poni file. */
  path?: string
  citation?: CalibCitation | null
  [key: string]: unknown
}

const props = defineProps<{
  open: boolean
  result: CalibExportResult | null
  /** Whether the export task is in flight (disables the save button). */
  saving?: boolean
}>()

const emit = defineEmits<{
  close: []
  save: [path: string]
  /**
   * 去积分: routed through the PARENT (CalibrationView.goIntegrate) so the
   * dialog footer shares the step-4 auto-export-to-temp + poni-query flow.
   * 由父组件统一处理（自动导出到临时目录 + ?poni 跳转）。
   */
  'go-integrate': []
}>()

const { t } = useI18n()
const transport = useTransport()

const savePath = ref('')

// Fallback DOI links, used when the backend citation omits them.
// 后端引用信息缺失时的兜底 DOI 链接。
const CALIB2_DOI = 'https://doi.org/10.1107/S1600577520000776'
const PYFAI_DOI = 'https://doi.org/10.1107/S1600576715004306'

async function browseSavePath(): Promise<void> {
  try {
    const result = await transport.selectSavePath({
      filters: [{ name: 'PONI Files', extensions: ['poni'] }],
      defaultPath: 'calibration.poni',
    })
    if (result) {
      savePath.value = result
    }
  } catch {
    // User cancelled the dialog / 用户取消对话框
  }
}

function doSave(): void {
  const path = savePath.value.trim()
  if (!path) return
  emit('save', path)
}

function openDoi(which: 'calib2' | 'pyfai'): void {
  const citation = props.result?.citation as Record<string, unknown> | null | undefined
  const pick = (...keys: string[]): string | undefined => {
    for (const key of keys) {
      const value = citation?.[key]
      if (typeof value === 'string' && value.startsWith('http')) return value
    }
    return undefined
  }
  const url = which === 'calib2'
    ? pick('calib2Url', 'calib2_url') || CALIB2_DOI
    : pick('pyfaiUrl', 'pyfai_url') || PYFAI_DOI
  window.open(url, '_blank', 'noopener')
}

function onGoIntegrate(): void {
  emit('close')
  emit('go-integrate')
}
</script>

<style scoped>
.ced-backdrop {
  position: fixed;
  inset: 0;
  z-index: var(--z-modal, 100);
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(15, 23, 42, 0.5);
  backdrop-filter: blur(4px);
}

.ced-panel {
  width: min(520px, 90vw);
  max-height: 86vh;
  overflow-y: auto;
  padding: 24px;
  border-radius: 20px;
  background: var(--bg-surface, #fff);
  border: 1px solid var(--border);
  box-shadow: 0 24px 48px rgba(15, 23, 42, 0.2);
}

.ced-title {
  font-size: 1.15rem;
  font-weight: 700;
  margin: 0 0 20px;
  color: var(--text-primary);
}

.ced-body {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.ced-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.ced-label {
  font-size: 0.8rem;
  font-weight: 700;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.ced-path-row {
  display: flex;
  gap: 8px;
}

.ced-input {
  flex: 1;
  min-width: 0;
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: 10px;
  font-size: 0.85rem;
  font-family: var(--font-mono);
  background: var(--bg-hover, rgba(248, 250, 252, 0.8));
  color: var(--text-primary);
}

.ced-btn {
  padding: 8px 16px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--bg-surface, rgba(255, 255, 255, 0.8));
  color: var(--text-primary);
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  transition: all var(--transition-fast, 0.15s);
}

.ced-btn:hover:not(:disabled) {
  border-color: var(--border-hover);
  box-shadow: var(--shadow-sm);
}

.ced-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.ced-btn--browse {
  font-family: var(--font-mono);
}

.ced-btn--primary {
  border: none;
  background: var(--primary);
  color: var(--text-inverse);
  font-weight: 700;
}

.ced-btn--primary:hover:not(:disabled) {
  opacity: 0.9;
}

.ced-btn--doi {
  flex: 1;
  border-color: var(--primary);
  color: var(--primary);
}

.ced-saved {
  margin: 0;
  padding: 8px 12px;
  border-radius: var(--radius-sm);
  background: rgba(34, 197, 94, 0.12);
  color: #15803d;
  font-size: 0.8rem;
  word-break: break-all;
}

.ced-saved code {
  font-family: var(--font-mono);
}

/* Citation / 引用面板 */
.ced-citation {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px;
  border: 1px dashed var(--border-hover);
  border-radius: var(--radius-md);
  background: var(--primary-bg, rgba(37, 99, 235, 0.05));
}

.ced-citation-title {
  margin: 0;
  font-size: 0.875rem;
  font-weight: 700;
  color: var(--text-primary);
}

.ced-citation-body {
  margin: 0;
  font-size: 0.8rem;
  color: var(--text-secondary);
  line-height: 1.5;
}

.ced-doi-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.ced-license-note {
  margin: 0;
  font-size: 0.72rem;
  color: var(--text-muted);
  line-height: 1.4;
}

.ced-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  margin-top: 20px;
}

.ced-btn--go {
  border-color: var(--primary);
  color: var(--primary);
  font-weight: 700;
}
</style>
