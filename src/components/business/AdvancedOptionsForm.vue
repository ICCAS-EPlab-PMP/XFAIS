<template>
  <fieldset
    :data-testid="testIds.advancedOptionsForm"
    :class="['advanced-options-form', { 'aof-bare': bare }]"
  >
    <legend v-if="!bare" class="aof-legend">{{ t('business.advancedOptions.title') }}</legend>

    <div class="aof-grid">
      <!-- NPT radial / 径向点数 -->
      <label class="aof-field">
        <span class="aof-field-label">{{ t('business.advancedOptions.nptRad') }}</span>
        <input
          type="number"
          class="aof-input"
          min="10"
          step="100"
          :value="modelValue.nptRad"
          :data-testid="testIds.advancedNptRad"
          @input="onFieldInput('nptRad', ($event.target as HTMLInputElement).value)"
        />
      </label>

      <!-- NPT azimuthal / 方位角点数 -->
      <label class="aof-field">
        <span class="aof-field-label">{{ t('business.advancedOptions.nptAzim') }}</span>
        <input
          type="number"
          class="aof-input"
          min="1"
          step="1"
          :value="modelValue.nptAzim"
          :data-testid="testIds.advancedNptAzim"
          @input="onFieldInput('nptAzim', ($event.target as HTMLInputElement).value)"
        />
      </label>

      <!-- Radial range / 径向范围 -->
      <label class="aof-field">
        <span class="aof-field-label">{{ t('business.advancedOptions.radialMin') }}</span>
        <input
          type="number"
          class="aof-input"
          step="0.1"
          :value="modelValue.radialMin"
          :data-testid="testIds.advancedRadialMin"
          @input="onFieldInput('radialMin', ($event.target as HTMLInputElement).value)"
        />
      </label>
      <label class="aof-field">
        <span class="aof-field-label">{{ t('business.advancedOptions.radialMax') }}</span>
        <input
          type="number"
          class="aof-input"
          step="0.1"
          :value="modelValue.radialMax"
          :data-testid="testIds.advancedRadialMax"
          @input="onFieldInput('radialMax', ($event.target as HTMLInputElement).value)"
        />
      </label>

      <!-- Unit selection (hidden when hideUnit is true) / 单位选择（hideUnit 时隐藏） -->
      <label v-if="!hideUnit" class="aof-field">
        <span class="aof-field-label">{{ t('business.advancedOptions.unit') }}</span>
        <select
          class="aof-select"
          :value="modelValue.unit"
          :data-testid="testIds.advancedUnit"
          @change="onUnitChange"
        >
          <option v-for="u in unitOptions" :key="u.value" :value="u.value">
            {{ u.label }}
          </option>
        </select>
      </label>

      <!-- Algorithm method (1D only) / 积分算法方法（仅1D） -->
      <label v-if="showIntegrationMethod" class="aof-field">
        <span class="aof-field-label">{{ t('business.advancedOptions.algorithm') }}</span>
        <select
          class="aof-select"
          :value="modelValue.algorithm ?? 'splitpixel'"
          :data-testid="testIds.advancedAlgorithm"
          @change="onAlgorithmChange"
        >
          <option v-for="a in algorithmOptions" :key="a.value" :value="a.value">
            {{ a.label }}
          </option>
        </select>
      </label>

      <!-- Integrator engine (1D only) / 积分器引擎（仅1D） -->
      <label v-if="showIntegrationMethod" class="aof-field">
        <span class="aof-field-label">{{ t('business.advancedOptions.integrator') }}</span>
        <select
          class="aof-select"
          :value="modelValue.integrator ?? 'ng'"
          :data-testid="testIds.advancedIntegrator"
          @change="onIntegratorChange"
        >
          <option v-for="ig in integratorOptions" :key="ig.value" :value="ig.value">
            {{ ig.label }}
          </option>
        </select>
      </label>

      <!-- Solid angle correction / 立体角校正 -->
      <label class="aof-toggle">
        <input
          type="checkbox"
          :checked="modelValue.correctSolidAngle"
          :data-testid="testIds.advancedSolidAngle"
          @change="onCheckboxToggle"
        />
        <span class="aof-toggle-label">{{ t('business.advancedOptions.correctSolidAngle') }}</span>
      </label>
    </div>
  </fieldset>
</template>

<script lang="ts">
/**
 * Runtime exports that cannot live inside <script setup>.
 * 运行时导出，不能放在 <script setup> 中。
 */
export const UNIT_OPTIONS: Array<{ value: string; label: string }> = [
  { value: 'q_nm', label: 'q (nm⁻¹)' },
  { value: 'q_A', label: 'q (Å⁻¹)' },
  { value: '2th_deg', label: '2θ (deg)' },
  { value: '2th_rad', label: '2θ (rad)' },
]
</script>

<script setup lang="ts">
/**
 * AdvancedOptionsForm.vue — 高级积分选项表单
 * Advanced integration options form
 */
import { useI18n } from 'vue-i18n'
import { testIds } from '@/lib/testIds'

/** Integration unit type / 积分单位类型 */
export type IntegrationUnit = 'q_nm' | 'q_A' | '2th_deg' | '2th_rad'

/** Integration algorithm method / 积分算法方法 */
export type IntegrationAlgorithm = 'splitpixel' | 'csr' | 'lut' | 'bbox' | 'numpy'

/** Integrator engine selection / 积分器引擎选择 */
export type IntegratorType = 'ng' | 'legacy'

/** Advanced options shape / 高级选项结构 */
export interface AdvancedOptions {
  /** Radial bin count / 径向 bin 数 */
  nptRad: number
  /** Azimuthal bin count / 方位角 bin 数 */
  nptAzim: number
  /** Radial range minimum / 径向范围最小值 */
  radialMin: number | null
  /** Radial range maximum / 径向范围最大值 */
  radialMax: number | null
  /** Integration unit / 积分单位 */
  unit: IntegrationUnit
  /** Correct solid angle / 立体角校正 */
  correctSolidAngle: boolean
  /** Integration algorithm method (1D only) / 积分算法方法（仅1D） */
  algorithm?: IntegrationAlgorithm
  /** Integrator engine (1D only) / 积分器引擎（仅1D） */
  integrator?: IntegratorType
}

const props = withDefaults(defineProps<{
  /** Advanced options (v-model) / 高级选项 */
  modelValue?: AdvancedOptions
  /** Show algorithm & integrator selects (1D page only) / 显示算法和积分器选择（仅1D页面） */
  showIntegrationMethod?: boolean
  /** Hide unit field (when rendered externally) / 隐藏单位字段（外部独立渲染时） */
  hideUnit?: boolean
  /** Bare mode: no border, padding, or legend / 裸模式：无边框、内边距或标题 */
  bare?: boolean
}>(), {
  modelValue: () => ({
    nptRad: 1000,
    nptAzim: 360,
    radialMin: null,
    radialMax: null,
    unit: 'q_nm',
    correctSolidAngle: true,
  }),
  showIntegrationMethod: false,
  hideUnit: false,
  bare: false,
})

const emit = defineEmits<{
  'update:modelValue': [value: AdvancedOptions]
}>()

const { t } = useI18n()

/** Reuse exported constant in template / 在模板中复用导出的常量 */
const unitOptions = UNIT_OPTIONS

const algorithmOptions: Array<{ value: IntegrationAlgorithm; label: string }> = [
  { value: 'splitpixel', label: 'SplitPixel (most accurate)' },
  { value: 'csr', label: 'CSR (fast)' },
  { value: 'lut', label: 'LUT (fast)' },
  { value: 'bbox', label: 'BBox (approx.)' },
  { value: 'numpy', label: 'NumPy (fallback)' },
]

const integratorOptions: Array<{ value: IntegratorType; label: string }> = [
  { value: 'ng', label: 'NG (recommended)' },
  { value: 'legacy', label: 'Legacy' },
]

function onFieldInput(field: keyof AdvancedOptions, raw: string): void {
  const num = parseFloat(raw)
  if (isNaN(num)) return
  emit('update:modelValue', { ...props.modelValue, [field]: num })
}

function onUnitChange(event: Event): void {
  const val = (event.target as HTMLSelectElement).value as IntegrationUnit
  emit('update:modelValue', { ...props.modelValue, unit: val })
}

function onAlgorithmChange(event: Event): void {
  const val = (event.target as HTMLSelectElement).value as IntegrationAlgorithm
  emit('update:modelValue', { ...props.modelValue, algorithm: val })
}

function onIntegratorChange(event: Event): void {
  const val = (event.target as HTMLSelectElement).value as IntegratorType
  emit('update:modelValue', { ...props.modelValue, integrator: val })
}

function onCheckboxToggle(): void {
  emit('update:modelValue', {
    ...props.modelValue,
    correctSolidAngle: !props.modelValue.correctSolidAngle,
  })
}
</script>

<style scoped>
.advanced-options-form {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

/* Bare mode: stripped down for embedding in external wrappers */
/* 裸模式：去除边框和内边距，用于嵌入外部折叠容器 */
.advanced-options-form.aof-bare {
  border: none;
  padding: 0;
  border-radius: 0;
}

.aof-legend {
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--text-primary);
  padding: 0 6px;
}

.aof-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
  align-items: start;
}

.aof-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.aof-field-label {
  font-size: 0.8125rem;
  color: var(--text-secondary);
  font-weight: 500;
}

.aof-input,
.aof-select {
  padding: 8px 10px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: 0.8125rem;
  transition: border-color var(--transition-fast);
}

.aof-input:focus,
.aof-select:focus {
  outline: none;
  border-color: var(--border-focus);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}

.aof-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding-top: 22px;
}

.aof-toggle input[type="checkbox"] {
  accent-color: var(--primary);
  width: 16px;
  height: 16px;
}

.aof-toggle-label {
  font-size: 0.875rem;
  color: var(--text-primary);
  font-weight: 500;
}
</style>
