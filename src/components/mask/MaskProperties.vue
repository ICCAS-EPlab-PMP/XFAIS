<template>
  <aside class="mask-properties">
    <!-- Image info -->
    <div class="props-group">
      <h4 class="group-title">{{ t('maskMaker.properties.imageInfo') }}</h4>
      <div v-if="imageInfo" class="info-grid">
        <span class="info-label">{{ t('maskMaker.properties.fileName') }}</span>
        <span class="info-value">{{ imageInfo.fileName }}</span>
        <span class="info-label">{{ t('maskMaker.properties.dimensions') }}</span>
        <span class="info-value">{{ imageInfo.width }} × {{ imageInfo.height }}</span>
        <span class="info-label">{{ t('maskMaker.properties.format') }}</span>
        <span class="info-value">{{ imageInfo.fileType.toUpperCase() }}</span>
        <template v-if="imageInfo.stats">
          <span class="info-label">{{ t('maskMaker.properties.min') }}</span>
          <span class="info-value">{{ formatNumber(imageInfo.stats.min) }}</span>
          <span class="info-label">{{ t('maskMaker.properties.max') }}</span>
          <span class="info-value">{{ formatNumber(imageInfo.stats.max) }}</span>
          <span class="info-label">{{ t('maskMaker.properties.std') }}</span>
          <span class="info-value">{{ formatNumber(imageInfo.stats.std) }}</span>
        </template>
      </div>
      <p v-else class="empty-hint">{{ t('maskMaker.properties.noImage') }}</p>
    </div>

    <!-- Mask stats -->
    <div class="props-group">
      <h4 class="group-title">{{ t('maskMaker.properties.maskStats') }}</h4>
      <div v-if="maskStats" class="info-grid">
        <span class="info-label">{{ t('maskMaker.properties.maskedPixels') }}</span>
        <span class="info-value">{{ maskStats.maskedPixels.toLocaleString() }}</span>
        <span class="info-label">{{ t('maskMaker.properties.totalPixels') }}</span>
        <span class="info-value">{{ maskStats.totalPixels.toLocaleString() }}</span>
        <span class="info-label">{{ t('maskMaker.properties.percentage') }}</span>
        <span class="info-value">{{ maskStats.percentage.toFixed(2) }}%</span>
      </div>
      <p v-else class="empty-hint">—</p>
    </div>

    <!-- Contrast adjustment -->
    <div class="props-group">
      <h4 class="group-title">{{ t('maskMaker.properties.contrast') }}</h4>
      <div class="contrast-form">
        <div class="contrast-row">
          <input
            type="range"
            class="contrast-slider"
            :min="0.2"
            :max="5"
            :step="0.05"
            :value="contrast"
            :disabled="!imageLoaded"
            @input="onContrastInput(($event.target as HTMLInputElement).value)"
          />
          <span class="contrast-value">{{ contrast.toFixed(2) }}×</span>
        </div>
        <div class="contrast-presets">
          <button
            v-for="preset in contrastPresets"
            :key="preset.value"
            class="preset-btn"
            :class="{ active: Math.abs(contrast - preset.value) < 0.01 }"
            :disabled="!imageLoaded"
            @click="onContrastInput(String(preset.value))"
          >
            {{ preset.label }}
          </button>
        </div>
      </div>
    </div>

    <!-- Threshold tools -->
    <div class="props-group">
      <h4 class="group-title">{{ t('maskMaker.properties.threshold') }}</h4>
      <div class="threshold-form">
        <label class="field-label">
          {{ t('maskMaker.properties.thresholdMin') }}
          <input
            v-model.number="localThreshold.min"
            type="number"
            class="field-input"
            :disabled="!imageLoaded"
            step="any"
          />
        </label>
        <label class="field-label">
          {{ t('maskMaker.properties.thresholdMax') }}
          <input
            v-model.number="localThreshold.max"
            type="number"
            class="field-input"
            :disabled="!imageLoaded"
            step="any"
          />
        </label>
        <div class="threshold-actions">
          <button
            class="action-btn"
            :disabled="!imageLoaded"
            @click="$emit('apply-threshold', { mode: 'below', threshold: localThreshold.min })"
          >
            {{ t('maskMaker.properties.belowMin') }}
          </button>
          <button
            class="action-btn"
            :disabled="!imageLoaded"
            @click="$emit('apply-threshold', { mode: 'above', threshold: localThreshold.max })"
          >
            {{ t('maskMaker.properties.aboveMax') }}
          </button>
          <button
            class="action-btn"
            :disabled="!imageLoaded"
            @click="$emit('apply-threshold', {
              mode: 'between',
              threshold_min: localThreshold.min,
              threshold_max: localThreshold.max
            })"
          >
            {{ t('maskMaker.properties.between') }}
          </button>
          <button
            class="action-btn"
            :disabled="!imageLoaded"
            @click="$emit('apply-threshold', { mode: 'not_finite' })"
          >
            {{ t('maskMaker.properties.notFinite') }}
          </button>
        </div>
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { reactive } from 'vue'
import { useI18n } from 'vue-i18n'
import type { MaskImageInfo, MaskStats, ThresholdMode } from '@/types/mask'

const { t } = useI18n()

defineProps<{
  imageInfo: MaskImageInfo | null
  maskStats: MaskStats | null
  imageLoaded: boolean
  contrast: number
}>()

const emit = defineEmits<{
  'apply-threshold': [params: {
    mode: ThresholdMode
    threshold?: number
    threshold_min?: number
    threshold_max?: number
  }]
  'update:contrast': [value: number]
}>()

const localThreshold = reactive({
  min: 0,
  max: 65535,
})

const contrastPresets = [
  { value: 0.5, label: '0.5×' },
  { value: 1, label: '1×' },
  { value: 2, label: '2×' },
  { value: 3, label: '3×' },
  { value: 5, label: '5×' },
]

function onContrastInput(val: string): void {
  emit('update:contrast', parseFloat(val))
}

function formatNumber(value: number): string {
  if (!Number.isFinite(value)) return '—'
  if (Math.abs(value) < 0.001 || Math.abs(value) > 1e6) {
    return value.toExponential(3)
  }
  return value.toFixed(3)
}
</script>

<style scoped>
.mask-properties {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px;
  background: rgba(255, 255, 255, 0.84);
  border: 1px solid rgba(226, 232, 240, 0.9);
  border-radius: 16px;
  box-shadow: var(--shadow-card);
  min-width: 200px;
  max-width: 240px;
}

.props-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
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

.info-grid {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 4px 12px;
  font-size: 0.8rem;
}

.info-label {
  color: var(--text-secondary);
  font-weight: 600;
}

.info-value {
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: 0.78rem;
  word-break: break-all;
}

.empty-hint {
  color: var(--text-secondary);
  font-size: 0.8rem;
  margin: 0;
  opacity: 0.7;
}

/* Threshold form */
.threshold-form {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field-label {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 0.75rem;
  color: var(--text-secondary);
  font-weight: 600;
}

.field-input {
  padding: 6px 8px;
  border: 1px solid var(--border);
  border-radius: 8px;
  font-size: 0.8rem;
  font-family: var(--font-mono);
  background: rgba(255, 255, 255, 0.8);
  color: var(--text-primary);
  transition: border-color var(--transition-fast);
}

.field-input:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.15);
}

.field-input:disabled {
  opacity: 0.4;
}

.threshold-actions {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: 4px;
}

.action-btn {
  padding: 6px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.7);
  color: var(--text-primary);
  font-size: 0.78rem;
  font-weight: 600;
  cursor: pointer;
  transition: all var(--transition-fast);
  text-align: left;
}

.action-btn:hover:not(:disabled) {
  background: var(--primary-bg);
  border-color: var(--primary);
}

.action-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* Contrast controls */
.contrast-form {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.contrast-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.contrast-slider {
  flex: 1;
  -webkit-appearance: none;
  appearance: none;
  height: 6px;
  border-radius: 3px;
  background: rgba(0, 0, 0, 0.12);
  outline: none;
}

.contrast-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: var(--primary);
  cursor: pointer;
  border: 2px solid #fff;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.2);
}

.contrast-slider:disabled::-webkit-slider-thumb {
  opacity: 0.4;
}

.contrast-value {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--text-primary);
  min-width: 40px;
  text-align: right;
}

.contrast-presets {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.preset-btn {
  padding: 4px 8px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.7);
  color: var(--text-primary);
  font-size: 0.7rem;
  font-weight: 600;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.preset-btn:hover:not(:disabled) {
  background: var(--primary-bg);
  border-color: var(--primary);
}

.preset-btn.active {
  background: var(--primary);
  color: var(--text-inverse);
  border-color: var(--primary);
}

.preset-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
</style>
