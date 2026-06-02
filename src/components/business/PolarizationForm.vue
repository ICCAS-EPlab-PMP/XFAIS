<template>
  <fieldset :data-testid="testIds.polarizationForm" class="polarization-form">
    <legend class="pf-legend">{{ t('business.polarization.title') }}</legend>

    <label class="pf-toggle">
      <input
        type="checkbox"
        :checked="enabled"
        :data-testid="testIds.polarizationEnabled"
        @change="onToggle"
      />
      <span class="pf-toggle-label">{{ t('business.polarization.enable') }}</span>
    </label>

    <div v-if="enabled" class="pf-slider-row">
      <input
        type="range"
        class="pf-slider"
        min="-1"
        max="1"
        step="0.01"
        :value="modelValue ?? 0.99"
        :data-testid="testIds.polarizationSlider"
        @input="onSliderInput"
      />
      <output class="pf-value" :data-testid="testIds.polarizationValue">
        {{ formatFactor(modelValue ?? 0.99) }}
      </output>
    </div>

    <p v-if="!enabled" class="pf-hint">{{ t('business.polarization.disabledHint') }}</p>
    <p v-else class="pf-hint">{{ t('business.polarization.enabledHint') }}</p>
  </fieldset>
</template>

<script setup lang="ts">
/**
 * PolarizationForm.vue — 偏振校正因子输入表单
 * Polarization correction factor input form
 */
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { testIds } from '@/lib/testIds'

const props = withDefaults(defineProps<{
  /** Polarization factor (v-model), null = disabled / 偏振因子，null = 禁用 */
  modelValue?: number | null
}>(), {
  modelValue: null,
})

const emit = defineEmits<{
  'update:modelValue': [value: number | null]
}>()

const { t } = useI18n()

const enabled = ref(props.modelValue !== null)

watch(() => props.modelValue, (val) => {
  enabled.value = val !== null
})

function onToggle(): void {
  enabled.value = !enabled.value
  emit('update:modelValue', enabled.value ? 0.99 : null)
}

function onSliderInput(event: Event): void {
  const raw = (event.target as HTMLInputElement).value
  const num = parseFloat(raw)
  if (!isNaN(num)) {
    emit('update:modelValue', num)
  }
}

function formatFactor(val: number): string {
  return val.toFixed(2)
}
</script>

<style scoped>
.polarization-form {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.pf-legend {
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--text-primary);
  padding: 0 6px;
}

.pf-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.pf-toggle input[type="checkbox"] {
  accent-color: var(--primary);
  width: 16px;
  height: 16px;
}

.pf-toggle-label {
  font-size: 0.875rem;
  color: var(--text-primary);
  font-weight: 500;
}

.pf-slider-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.pf-slider {
  flex: 1;
  accent-color: var(--primary);
}

.pf-value {
  font-family: var(--font-mono);
  font-size: 0.875rem;
  color: var(--text-secondary);
  min-width: 3.5em;
  text-align: right;
}

.pf-hint {
  font-size: 0.75rem;
  color: var(--text-muted);
  margin: 0;
}
</style>
