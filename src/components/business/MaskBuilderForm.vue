<template>
  <fieldset
    :data-testid="testIds.maskBuilderForm"
    :class="['mask-builder-form', { 'mbf-bare': bare }]"
  >
    <legend v-if="!bare" class="mbf-legend">{{ t('business.mask.title') }}</legend>

    <div class="mbf-grid">
      <!-- Value range / 值范围 -->
      <label class="mbf-field">
        <span class="mbf-field-label">{{ t('business.mask.valueRangeMin') }}</span>
        <input
          type="number"
          class="mbf-input"
          :value="model.valueRangeMin"
          :data-testid="testIds.maskValueRangeMin"
          @input="onFieldInput('valueRangeMin', ($event.target as HTMLInputElement).value)"
        />
      </label>
      <label class="mbf-field">
        <span class="mbf-field-label">{{ t('business.mask.valueRangeMax') }}</span>
        <input
          type="number"
          class="mbf-input"
          :value="model.valueRangeMax"
          :data-testid="testIds.maskValueRangeMax"
          @input="onFieldInput('valueRangeMax', ($event.target as HTMLInputElement).value)"
        />
      </label>

      <!-- Dead pixel threshold / 死像素阈值 -->
      <label class="mbf-field">
        <span class="mbf-field-label">{{ t('business.mask.deadPixelThreshold') }}</span>
        <input
          type="number"
          class="mbf-input"
          step="1"
          min="0"
          :value="model.deadPixelThreshold"
          :data-testid="testIds.maskDeadPixelThreshold"
          @input="onFieldInput('deadPixelThreshold', ($event.target as HTMLInputElement).value)"
        />
      </label>
    </div>

    <!-- Custom mask file / 自定义掩膜文件 -->
    <div class="mbf-custom">
      <FileDialogButton
        mode="openFile"
        :label="t('business.mask.customMaskFile')"
        :placeholder="t('business.mask.noCustomMask')"
        :filters="[{ name: 'Mask', extensions: ['npy', 'npz', 'tif', 'tiff', 'edf'] }]"
        :model-value="model.customMaskPath"
        :data-testid="testIds.maskCustomFile"
        @update:model-value="onMaskPathChange"
      />
    </div>
  </fieldset>
</template>

<script setup lang="ts">
/**
 * MaskBuilderForm.vue — 掩膜构建器表单，支持值范围、死像素阈值和自定义掩膜
 * Mask builder form with value range, dead pixel threshold, and custom mask
 */
import { useI18n } from 'vue-i18n'
import { testIds } from '@/lib/testIds'
import FileDialogButton from './FileDialogButton.vue'

/** Mask configuration shape / 掩膜配置结构 */
export interface MaskConfig {
  /** Minimum intensity value / 最小强度值 */
  valueRangeMin: number
  /** Maximum intensity value / 最大强度值 */
  valueRangeMax: number
  /** Dead pixel threshold / 死像素阈值 */
  deadPixelThreshold: number
  /** Custom mask file path / 自定义掩膜文件路径 */
  customMaskPath: string | null
}

withDefaults(defineProps<{
  /** Bare mode: no border, padding, or legend / 裸模式：无边框、内边距或标题 */
  bare?: boolean
}>(), {
  bare: false,
})

const model = defineModel<MaskConfig>('modelValue', {
  default: () => ({
    valueRangeMin: 0,
    valueRangeMax: 1e10,
    deadPixelThreshold: 0,
    customMaskPath: null,
  }),
})

const { t } = useI18n()

function onFieldInput(field: keyof MaskConfig, raw: string): void {
  const num = parseFloat(raw)
  if (isNaN(num)) return
  model.value = { ...model.value, [field]: num }
}

function onMaskPathChange(path: string | null): void {
  model.value = { ...model.value, customMaskPath: path }
}
</script>

<style scoped>
.mask-builder-form {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

/* Bare mode: stripped down for embedding in external wrappers */
/* 裸模式：去除边框和内边距，用于嵌入外部折叠容器 */
.mask-builder-form.mbf-bare {
  border: none;
  padding: 0;
  border-radius: 0;
}

.mbf-legend {
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--text-primary);
  padding: 0 6px;
}

.mbf-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.mbf-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.mbf-field-label {
  font-size: 0.8125rem;
  color: var(--text-secondary);
  font-weight: 500;
}

.mbf-input {
  padding: 8px 10px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: 0.8125rem;
  transition: border-color var(--transition-fast);
}

.mbf-input:focus {
  outline: none;
  border-color: var(--border-focus);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}

.mbf-custom {
  margin-top: 4px;
}
</style>
