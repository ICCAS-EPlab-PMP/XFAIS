<template>
  <section class="pyfai-calib-page">
    <header class="pc-header">
      <h1>{{ t('pyfaiCalib.title') }}</h1>
      <p class="pc-subtitle">{{ t('pyfaiCalib.subtitle') }}</p>
    </header>

    <!-- Status check button -->
    <div class="pc-check-section">
      <button
        type="button"
        class="pc-check-btn"
        :disabled="checking"
        @click="handleCheck"
      >
        {{ checking ? t('pyfaiCalib.checking') : t('pyfaiCalib.checkStatus') }}
      </button>

      <div v-if="statusResult" class="pc-status-summary">
        <span
          class="pc-status-badge"
          :class="statusBadgeClass"
        >
          {{ statusBadgeText }}
        </span>
        <p class="pc-status-text">{{ statusText }}</p>
      </div>
    </div>

    <!-- Status detail cards -->
    <div v-if="statusResult" class="pc-detail-grid">
      <!-- Embedded Python -->
      <div class="pc-detail-card">
        <h3 class="pc-detail-title">{{ t('pyfaiCalib.embeddedPython') }}</h3>
        <div class="pc-detail-rows">
          <div class="pc-detail-row">
            <span class="pc-detail-label">{{ t('pyfaiCalib.version') }}</span>
            <span class="pc-detail-value">
              <template v-if="statusResult.embedded.available">
                {{ statusResult.embedded.version ?? '-' }}
              </template>
              <template v-else>
                <span class="pc-na">—</span>
              </template>
            </span>
          </div>
          <div class="pc-detail-row">
            <span class="pc-detail-label">{{ t('pyfaiCalib.calib2Path') }}</span>
            <span class="pc-detail-value pc-path">
              <template v-if="statusResult.embedded.calib2Path">
                <code>{{ statusResult.embedded.calib2Path }}</code>
              </template>
              <template v-else>
                <span class="pc-na">—</span>
              </template>
            </span>
          </div>
          <div class="pc-detail-row">
            <span class="pc-detail-label">{{ t('pyfaiCalib.available') }}</span>
            <span class="pc-detail-value">
              <span
                class="pc-badge"
                :class="statusResult.embedded.available ? 'pc-badge--ok' : 'pc-badge--missing'"
              >
                {{ statusResult.embedded.available ? t('pyfaiCalib.detectedBadge') : t('pyfaiCalib.notDetectedBadge') }}
              </span>
            </span>
          </div>
          <div v-if="statusResult.embedded.calib2Path" class="pc-detail-row">
            <span class="pc-detail-label">{{ t('pyfaiCalib.qtBinding') }}</span>
            <span class="pc-detail-value">
              <span
                class="pc-badge"
                :class="statusResult.embedded.hasQtBinding ? 'pc-badge--ok' : 'pc-badge--missing'"
              >
                {{ statusResult.embedded.hasQtBinding ? t('pyfaiCalib.qtAvailable') : t('pyfaiCalib.qtMissing') }}
              </span>
            </span>
          </div>
        </div>
      </div>

      <!-- System Python -->
      <div class="pc-detail-card">
        <h3 class="pc-detail-title">{{ t('pyfaiCalib.systemPython') }}</h3>
        <div class="pc-detail-rows">
          <div class="pc-detail-row">
            <span class="pc-detail-label">{{ t('pyfaiCalib.version') }}</span>
            <span class="pc-detail-value">
              <template v-if="statusResult.system.available">
                {{ statusResult.system.version ?? '-' }}
              </template>
              <template v-else>
                <span class="pc-na">—</span>
              </template>
            </span>
          </div>
          <div class="pc-detail-row">
            <span class="pc-detail-label">{{ t('pyfaiCalib.calib2Path') }}</span>
            <span class="pc-detail-value pc-path">
              <template v-if="statusResult.system.calib2Path">
                <code>{{ statusResult.system.calib2Path }}</code>
              </template>
              <template v-else>
                <span class="pc-na">—</span>
              </template>
            </span>
          </div>
          <div class="pc-detail-row">
            <span class="pc-detail-label">{{ t('pyfaiCalib.available') }}</span>
            <span class="pc-detail-value">
              <span
                class="pc-badge"
                :class="statusResult.system.available ? 'pc-badge--ok' : 'pc-badge--missing'"
              >
                {{ statusResult.system.available ? t('pyfaiCalib.detectedBadge') : t('pyfaiCalib.notDetectedBadge') }}
              </span>
            </span>
          </div>
          <div v-if="statusResult.system.calib2Path" class="pc-detail-row">
            <span class="pc-detail-label">{{ t('pyfaiCalib.qtBinding') }}</span>
            <span class="pc-detail-value">
              <span
                class="pc-badge"
                :class="statusResult.system.hasQtBinding ? 'pc-badge--ok' : 'pc-badge--missing'"
              >
                {{ statusResult.system.hasQtBinding ? t('pyfaiCalib.qtAvailable') : t('pyfaiCalib.qtMissing') }}
              </span>
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- Export bat script section (replaces launch section) -->
    <div v-if="canLaunch" class="pc-action-section">
      <hr class="pc-divider">
      <p class="pc-export-hint">{{ t('pyfaiCalib.exportBatHint') }}</p>
      <button
        type="button"
        class="pc-export-btn"
        :disabled="exporting"
        @click="handleExportBat"
      >
        {{ exporting ? t('pyfaiCalib.exporting') : t('pyfaiCalib.exportBat') }}
      </button>
      <p v-if="exportMessage" class="pc-export-message" :class="exportSuccess ? 'pc-export-message--ok' : 'pc-export-message--error'">
        {{ exportMessage }}
      </p>
    </div>

    <!-- Install instructions -->
    <div v-if="showInstallInfo" class="pc-install-section">
      <hr class="pc-divider">
      <h3>{{ t('pyfaiCalib.installInstructions') }}</h3>

      <div v-if="statusResult && statusResult.embedded.available" class="pc-already">
        <p>{{ t('pyfaiCalib.alreadyEmbedded') }}</p>
      </div>

      <div v-if="needsQtBinding" class="pc-pip-card">
        <p>{{ t('pyfaiCalib.qtMissing') }}</p>
        <div class="pc-pip-cmd">
          <code class="pc-code">pip install PySide6</code>
          <button type="button" class="pc-copy-btn" @click="handleCopyQt">
            {{ copiedQt ? t('pyfaiCalib.copied') : t('pyfaiCalib.copyCommand') }}
          </button>
        </div>
      </div>

      <div v-if="!statusResult?.embedded.available || !statusResult?.system.available" class="pc-pip-card">
        <p>{{ t('pyfaiCalib.pipCommand') }}</p>
        <div class="pc-pip-cmd">
          <code class="pc-code">pip install pyfai</code>
          <button type="button" class="pc-copy-btn" @click="handleCopyPip">
            {{ copied ? t('pyfaiCalib.copied') : t('pyfaiCalib.copyCommand') }}
          </button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useTransport } from '@/lib/transport'

const { t } = useI18n()
const transport = useTransport()

interface PyfaiCheckResult {
  embedded: { available: boolean; version: string | null; calib2Path: string | null; hasQtBinding: boolean }
  system: { available: boolean; version: string | null; calib2Path: string | null; hasQtBinding: boolean }
  overall: 'available' | 'embedded_only' | 'system_only' | 'not_found'
}

const checking = ref(false)
const copied = ref(false)
const copiedQt = ref(false)
const exporting = ref(false)
const exportMessage = ref('')
const exportSuccess = ref(false)
const statusResult = ref<PyfaiCheckResult | null>(null)

const canLaunch = computed(() => {
  if (!statusResult.value) return false
  const r = statusResult.value
  return r.embedded.available || r.system.available
})

const showInstallInfo = computed(() => {
  if (!statusResult.value) return true
  const r = statusResult.value
  return r.overall !== 'available'
})

const needsQtBinding = computed(() => {
  if (!statusResult.value) return false
  const r = statusResult.value
  return (r.embedded.available && !r.embedded.hasQtBinding) || (r.system.available && !r.system.hasQtBinding)
})

const statusBadgeClass = computed(() => {
  if (!statusResult.value) return ''
  switch (statusResult.value.overall) {
    case 'available': return 'pc-badge--ok'
    case 'embedded_only': return 'pc-badge--warn'
    case 'system_only': return 'pc-badge--warn'
    case 'not_found': return 'pc-badge--missing'
    default: return ''
  }
})

const statusBadgeText = computed(() => {
  if (!statusResult.value) return ''
  const r = statusResult.value
  switch (r.overall) {
    case 'available': return t('pyfaiCalib.detectedBadge')
    case 'embedded_only': return t('pyfaiCalib.detectedBadge')
    case 'system_only': return t('pyfaiCalib.detectedBadge')
    case 'not_found': return t('pyfaiCalib.notDetectedBadge')
    default: return ''
  }
})

const statusText = computed(() => {
  if (!statusResult.value) return ''
  const r = statusResult.value
  switch (r.overall) {
    case 'available': return t('pyfaiCalib.statusAvailable')
    case 'embedded_only': return t('pyfaiCalib.statusEmbeddedOnly')
    case 'system_only': return t('pyfaiCalib.statusSystemOnly')
    case 'not_found': return t('pyfaiCalib.statusNotFound')
    default: return ''
  }
})

const handleCheck = async (): Promise<void> => {
  checking.value = true
  statusResult.value = null
  exportMessage.value = ''
  try {
    const result = await transport.checkPyfai()
    statusResult.value = result as unknown as PyfaiCheckResult
  } catch (error) {
    statusResult.value = {
      embedded: { available: false, version: null, calib2Path: null, hasQtBinding: false },
      system: { available: false, version: null, calib2Path: null, hasQtBinding: false },
      overall: 'not_found'
    }
  } finally {
    checking.value = false
  }
}

const handleCopyPip = async (): Promise<void> => {
  try {
    await navigator.clipboard.writeText('pip install pyfai')
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  } catch {
    // Fallback for environments without clipboard API
  }
}

const handleCopyQt = async (): Promise<void> => {
  try {
    await navigator.clipboard.writeText('pip install PySide6')
    copiedQt.value = true
    setTimeout(() => { copiedQt.value = false }, 2000)
  } catch {
    // Fallback for environments without clipboard API
  }
}

const handleExportBat = async (): Promise<void> => {
  exporting.value = true
  exportMessage.value = ''
  try {
    const result = await transport.exportBatPyfai()
    if (result.success) {
      exportMessage.value = t('pyfaiCalib.exportBatSuccess')
      exportSuccess.value = true
    } else {
      exportMessage.value = result.error || t('pyfaiCalib.exportBatError')
      exportSuccess.value = false
    }
  } catch (err) {
    exportMessage.value = t('pyfaiCalib.exportBatError')
    exportSuccess.value = false
  } finally {
    exporting.value = false
    setTimeout(() => { exportMessage.value = '' }, 5000)
  }
}

// Auto-check on mount
handleCheck()
</script>

<style scoped>
.pyfai-calib-page {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.pc-header h1 {
  font-size: 1.6rem;
  margin-bottom: 6px;
}

.pc-subtitle {
  color: var(--text-secondary);
  font-size: 0.92rem;
  margin: 0;
}

/* Check section */
.pc-check-section {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.pc-check-btn {
  padding: 12px 22px;
  border: none;
  border-radius: 999px;
  background: var(--primary);
  color: #fff;
  font-weight: 700;
  cursor: pointer;
  transition: opacity var(--transition-fast);
}

.pc-check-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.pc-status-summary {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.pc-status-text {
  margin: 0;
  font-size: 0.92rem;
  color: var(--text-secondary);
}

/* Badge */
.pc-badge {
  display: inline-flex;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.02em;
}

.pc-badge--ok {
  background: rgba(34, 197, 94, 0.15);
  color: #16a34a;
}

.pc-badge--warn {
  background: rgba(234, 179, 8, 0.15);
  color: #ca8a04;
}

.pc-badge--missing {
  background: rgba(239, 68, 68, 0.12);
  color: #dc2626;
}

.pc-status-badge {
  display: inline-flex;
  padding: 5px 14px;
  border-radius: 999px;
  font-size: 0.82rem;
  font-weight: 700;
}

/* Detail grid */
.pc-detail-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 18px;
}

.pc-detail-card {
  padding: 20px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid rgba(226, 232, 240, 0.9);
  box-shadow: var(--shadow-card);
}

.pc-detail-title {
  font-size: 1rem;
  font-weight: 700;
  margin: 0 0 14px;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(226, 232, 240, 0.6);
}

.pc-detail-rows {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.pc-detail-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;
}

.pc-detail-label {
  font-size: 0.84rem;
  color: var(--text-secondary);
  white-space: nowrap;
  flex-shrink: 0;
}

.pc-detail-value {
  font-size: 0.84rem;
  text-align: right;
  word-break: break-all;
}

.pc-path code {
  font-size: 0.78rem;
  background: rgba(0, 0, 0, 0.04);
  padding: 2px 6px;
  border-radius: 4px;
  word-break: break-all;
}

.pc-na {
  color: var(--text-secondary);
  opacity: 0.5;
}

/* Action section */
.pc-action-section {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.pc-launch-btn {
  align-self: flex-start;
  padding: 12px 28px;
  border: none;
  border-radius: 999px;
  background: var(--primary);
  color: #fff;
  font-weight: 700;
  font-size: 1rem;
  cursor: pointer;
  transition: opacity var(--transition-fast);
}

.pc-launch-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.pc-launch-message {
  font-size: 0.9rem;
  margin: 0;
}

.pc-launch-message.pc-success {
  color: #16a34a;
}

.pc-launch-message.pc-error {
  color: #dc2626;
}

/* Install section */
.pc-install-section {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.pc-install-section h3 {
  font-size: 1.05rem;
  font-weight: 700;
  margin: 0;
}

.pc-already p {
  color: var(--text-secondary);
  font-size: 0.9rem;
  margin: 0;
  padding: 12px 16px;
  border-radius: 12px;
  background: rgba(34, 197, 94, 0.08);
  border: 1px solid rgba(34, 197, 94, 0.2);
}

.pc-pip-card {
  padding: 18px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid rgba(226, 232, 240, 0.9);
  box-shadow: var(--shadow-card);
}

.pc-pip-card p {
  margin: 0 0 12px;
  font-size: 0.9rem;
  color: var(--text-secondary);
}

.pc-pip-cmd {
  display: flex;
  align-items: center;
  gap: 10px;
}

.pc-code {
  flex: 1;
  padding: 10px 14px;
  border-radius: 10px;
  background: rgba(15, 23, 42, 0.06);
  font-family: var(--font-mono, monospace);
  font-size: 0.85rem;
  user-select: all;
}

.pc-copy-btn {
  padding: 8px 16px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  border-radius: 8px;
  background: #fff;
  font-size: 0.82rem;
  cursor: pointer;
  white-space: nowrap;
}

.pc-copy-btn:hover {
  background: rgba(15, 23, 42, 0.04);
}

/* Export section */
.pc-export-section {
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin-top: 18px;
}

.pc-export-section p {
  margin: 0;
  font-size: 0.9rem;
  color: var(--text-secondary);
}

.pc-export-hint {
  font-size: 0.9rem;
  color: var(--text-secondary);
  margin: 0;
  line-height: 1.5;
}

.pc-export-btn {
  align-self: flex-start;
  padding: 10px 24px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  border-radius: 8px;
  background: #fff;
  font-size: 0.9rem;
  cursor: pointer;
  white-space: nowrap;
}

.pc-export-btn:hover:not(:disabled) {
  background: rgba(15, 23, 42, 0.04);
}

.pc-export-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.pc-export-message {
  margin: 0;
  font-size: 0.85rem;
  padding: 8px 12px;
  border-radius: 8px;
}

.pc-export-message--ok {
  background: rgba(34, 197, 94, 0.1);
  color: #16a34a;
}

.pc-export-message--error {
  background: rgba(239, 68, 68, 0.1);
  color: #dc2626;
}

/* Divider */
.pc-divider {
  border: none;
  border-top: 1px solid rgba(226, 232, 240, 0.7);
  margin: 0;
}

@media (max-width: 700px) {
  .pc-detail-grid {
    grid-template-columns: 1fr;
  }
}
</style>
