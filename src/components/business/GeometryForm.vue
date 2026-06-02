<template>
  <fieldset :data-testid="testIds.geometryForm" class="geometry-form">
    <legend class="gf-legend">{{ t('business.geometry.title') }}</legend>

    <!-- Mode toggle / 模式切换 -->
    <div class="gf-mode-toggle">
      <button
        type="button"
        :class="['gf-mode-btn', { active: mode === 'poni' }]"
        :data-testid="testIds.geometryModePoni"
        @click="mode = 'poni'"
      >
        {{ t('business.geometry.poniMode') }}
      </button>
      <button
        type="button"
        :class="['gf-mode-btn', { active: mode === 'manual' }]"
        :data-testid="testIds.geometryModeManual"
        @click="mode = 'manual'"
      >
        {{ t('business.geometry.manualMode') }}
      </button>
    </div>

    <!-- PONI file mode / PONI 文件模式 -->
    <div v-if="mode === 'poni'" class="gf-poni-section">
      <FileDialogButton
        mode="openFile"
        :label="t('business.geometry.poniFile')"
        :filters="[{ name: 'PONI', extensions: ['poni'] }]"
        :model-value="poniPath"
        :data-testid="testIds.geometryPoniInput"
        @update:model-value="onPoniPathChange"
      />
    </div>

    <!-- Manual params mode / 手动参数模式 -->
    <div v-else class="gf-manual-section">
      <div class="gf-grid">
        <label class="gf-field">
          <span class="gf-field-label">{{ t('business.geometry.pixelSize') }}</span>
          <input
            type="number"
            class="gf-input"
            step="1"
            min="0.1"
            :value="modelValue.pixel1"
            :data-testid="testIds.geometryPixel1"
            @input="onFieldInput('pixel1', ($event.target as HTMLInputElement).value)"
          />
        </label>
        <label class="gf-field">
          <span class="gf-field-label">{{ t('business.geometry.distance') }}</span>
          <input
            type="number"
            class="gf-input"
            step="1"
            min="0.1"
            :value="modelValue.distance"
            :data-testid="testIds.geometryDistance"
            @input="onFieldInput('distance', ($event.target as HTMLInputElement).value)"
          />
        </label>
        <label class="gf-field">
          <span class="gf-field-label">{{ t('business.geometry.wavelength') }}</span>
          <input
            type="number"
            class="gf-input"
            step="0.0001"
            min="0.001"
            :value="modelValue.wavelength"
            :data-testid="testIds.geometryWavelength"
            @input="onFieldInput('wavelength', ($event.target as HTMLInputElement).value)"
          />
        </label>
        <label class="gf-field">
          <span class="gf-field-label">{{ t('business.geometry.centerX') }}</span>
          <input
            type="number"
            class="gf-input"
            step="1"
            min="0"
            :value="modelValue.centerX"
            :data-testid="testIds.geometryCenterX"
            @input="onFieldInput('centerX', ($event.target as HTMLInputElement).value)"
          />
        </label>
        <label class="gf-field">
          <span class="gf-field-label">{{ t('business.geometry.centerY') }}</span>
          <input
            type="number"
            class="gf-input"
            step="1"
            min="0"
            :value="modelValue.centerY"
            :data-testid="testIds.geometryCenterY"
            @input="onFieldInput('centerY', ($event.target as HTMLInputElement).value)"
          />
        </label>
      </div>
    </div>
  </fieldset>
</template>

<script setup lang="ts">
/**
 * GeometryForm.vue — 几何参数表单，支持 PONI 文件或手动输入双模式
 * Geometry parameter form with PONI file or manual entry dual mode
 */
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { testIds } from '@/lib/testIds'
import FileDialogButton from './FileDialogButton.vue'

/** Geometry parameters shape / 几何参数结构 */
export interface GeometryParams {
  /** PONI file path (poni mode) / PONI 文件路径 */
  poniPath?: string | null
  /** Pixel size in µm / 像素尺寸（µm） */
  pixel1: number
  pixel2: number
  /** Sample-detector distance in mm / 样品-探测器距离（mm） */
  distance: number
  /** Wavelength in Å / 波长（Å） */
  wavelength: number
  /** Beam centre X in pixels / 光束中心 X（像素） */
  centerX: number
  /** Beam centre Y in pixels / 光束中心 Y（像素） */
  centerY: number
}

type GeometryMode = 'poni' | 'manual'

const props = withDefaults(defineProps<{
  /** Geometry params (v-model) / 几何参数 */
  modelValue?: GeometryParams
}>(), {
  modelValue: () => ({
    pixel1: 172,
    pixel2: 172,
    distance: 200,
    wavelength: 1.5418,
    centerX: 512,
    centerY: 512,
  }),
})

const emit = defineEmits<{
  'update:modelValue': [value: GeometryParams]
}>()

const { t } = useI18n()

const mode = ref<GeometryMode>(props.modelValue.poniPath ? 'poni' : 'manual')
const poniPath = ref<string | null>(props.modelValue.poniPath ?? null)

watch(() => props.modelValue.poniPath, (val) => {
  poniPath.value = val ?? null
  if (val) mode.value = 'poni'
})

function onPoniPathChange(path: string | null): void {
  poniPath.value = path
  emit('update:modelValue', { ...props.modelValue, poniPath: path })
}

function onFieldInput(field: keyof GeometryParams, raw: string): void {
  const num = parseFloat(raw)
  if (isNaN(num)) return
  const updated = { ...props.modelValue, [field]: num }
  // Keep pixel1 and pixel2 in sync / 保持 pixel1/pixel2 同步
  if (field === 'pixel1') updated.pixel2 = num
  emit('update:modelValue', updated)
}
</script>

<style scoped>
.geometry-form {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.gf-legend {
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--text-primary);
  padding: 0 6px;
}

.gf-mode-toggle {
  display: inline-flex;
  gap: 0;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
  width: fit-content;
}

.gf-mode-btn {
  padding: 7px 18px;
  border: none;
  background: var(--bg-surface);
  color: var(--text-secondary);
  font-size: 0.8125rem;
  font-weight: 500;
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast);
}

.gf-mode-btn.active {
  background: var(--primary-bg);
  color: var(--primary);
  font-weight: 600;
}

.gf-mode-btn:not(:last-child) {
  border-right: 1px solid var(--border);
}

.gf-poni-section,
.gf-manual-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.gf-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.gf-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.gf-field-label {
  font-size: 0.8125rem;
  color: var(--text-secondary);
  font-weight: 500;
}

.gf-input {
  padding: 8px 10px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: 0.8125rem;
  transition: border-color var(--transition-fast);
}

.gf-input:focus {
  outline: none;
  border-color: var(--border-focus);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}
</style>
