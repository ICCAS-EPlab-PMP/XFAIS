<template>
  <div class="calib-refine-panel">
    <!-- Step-3 title: 精修中心位点 / Refine center & geometry (renamed — inline
         bilingual; see final report for the missing-i18n-keys list).
         第 3 步标题：精修中心位点（内联双语，见最终报告缺失键清单）。 -->
    <h4 class="crp-title">{{ titleLabel }}</h4>

    <!-- Free / fixed flags per parameter / 各参数自由/固定 -->
    <div class="crp-flags">
      <label
        v-for="param in PARAMS"
        :key="param.key"
        class="crp-flag"
        :class="{ 'crp-flag--fixed': !free[param.key] }"
        :title="paramTip(param.key)"
      >
        <input
          type="checkbox"
          :checked="free[param.key]"
          @change="onToggle(param.key, ($event.target as HTMLInputElement).checked)"
        />
        <span class="crp-flag-name">{{ param.key }}</span>
        <span class="crp-flag-desc">{{ paramMeaning(param.key) }}</span>
        <span class="crp-flag-state">
          {{ free[param.key] ? t('calibration.refine.free') : t('calibration.refine.fixed') }}
        </span>
      </label>
    </div>

    <!-- Refinement passes / 精化轮数 -->
    <div class="crp-field">
      <label class="crp-label">{{ t('calibration.refine.passes') }}</label>
      <select v-model.number="passes" class="crp-select">
        <option :value="1">1</option>
        <option :value="2">2</option>
        <option :value="3">3</option>
      </select>
    </div>

    <!-- Run / 运行精化 -->
    <button
      type="button"
      class="crp-btn crp-btn--primary"
      data-ai-id="calibration:refine"
      :disabled="running || canRun === false"
      @click="run"
    >
      {{ running ? t('calibration.refine.running') : t('calibration.refine.run') }}
    </button>
    <p v-if="canRun === false" class="crp-hint crp-hint--warn">{{ t('calibration.refine.needPeaks') }}</p>
    <p v-else-if="converged === false" class="crp-hint crp-hint--warn">{{ t('calibration.refine.notConverged') }}</p>

    <!-- χ² -->
    <div v-if="chi2 != null" class="crp-chi2">
      <span class="crp-chi2-label">{{ t('calibration.refine.chi2') }}</span>
      <span class="crp-chi2-value">{{ formatSci(chi2) }}</span>
    </div>

    <!-- Geometry readout (mm / deg / px) / 几何参数读数 -->
    <div v-if="geometry" class="crp-geometry">
      <h5 class="crp-subtitle">{{ t('calibration.refine.geometry') }}</h5>
      <!-- Refined beam center, PROMINENT (最终中心): the headline result of the
           精修中心位点 step — larger, highlighted row above the full parameter
           list; identical values to the magenta crosshair on the canvas.
           精修后的光束中心（最终中心）——本步骤的核心结果，置顶高亮显示，与画布
           洋红十字一致。 -->
      <div class="crp-final-center" :title="finalCenterTitle">
        <span class="crp-final-center-label">{{ finalCenterLabel }}</span>
        <span class="crp-final-center-value">{{ finalCenterValue }}</span>
      </div>
      <dl class="crp-readout">
        <div class="crp-readout-row" :title="paramTip('dist')">
          <dt>dist <em>{{ paramMeaning('dist') }}</em></dt>
          <dd>{{ formatVal(geometry.distMm, 'mm') }}</dd>
        </div>
        <div class="crp-readout-row" :title="paramTip('poni1')">
          <dt>poni1 <em>{{ paramMeaning('poni1') }}</em></dt>
          <dd>{{ formatVal(geometry.poni1Mm, 'mm') }}</dd>
        </div>
        <div class="crp-readout-row" :title="paramTip('poni2')">
          <dt>poni2 <em>{{ paramMeaning('poni2') }}</em></dt>
          <dd>{{ formatVal(geometry.poni2Mm, 'mm') }}</dd>
        </div>
        <div class="crp-readout-row" :title="paramTip('rot1')">
          <dt>rot1 <em>{{ paramMeaning('rot1') }}</em></dt>
          <dd>{{ formatVal(geometry.rot1Deg, '°') }}</dd>
        </div>
        <div class="crp-readout-row" :title="paramTip('rot2')">
          <dt>rot2 <em>{{ paramMeaning('rot2') }}</em></dt>
          <dd>{{ formatVal(geometry.rot2Deg, '°') }}</dd>
        </div>
        <div class="crp-readout-row" :title="paramTip('rot3')">
          <dt>rot3 <em>{{ paramMeaning('rot3') }}</em></dt>
          <dd>{{ formatVal(geometry.rot3Deg, '°') }}</dd>
        </div>
        <div class="crp-readout-row" :title="paramTip('wavelength')">
          <dt>wavelength <em>{{ paramMeaning('wavelength') }}</em></dt>
          <dd>{{ formatVal(geometry.wavelengthA, 'Å') }}</dd>
        </div>
      </dl>
    </div>

    <!-- Residual scatter (x = ring, y = Δ2θ) / 残差散点图 -->
    <div class="crp-residuals">
      <h5 class="crp-subtitle">{{ t('calibration.refine.residuals') }}</h5>
      <PlotlyChart
        v-if="residuals.length > 0"
        :data="residualTraces"
        :layout="residualLayout"
        :dark-mode="true"
        class="crp-chart"
      />
      <p v-else class="crp-empty">—</p>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * CalibRefinePanel.vue — 标定向导第 3 步：精化控制 + 结果读数 + 残差图
 * Calibration wizard step 3: free/fixed flags, passes, χ², geometry readout
 * (mm / deg / px) and a per-peak residual scatter chart (x = ring, y = Δ2θ).
 */
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import PlotlyChart from '@/components/charts/PlotlyChart.vue'
import type { PlotData, PlotLayout } from 'plotly.js-dist-min'

/** Refinable parameter keys — defaults: all free except wavelength. */
export type CalibParamKey = 'dist' | 'poni1' | 'poni2' | 'rot1' | 'rot2' | 'rot3' | 'wavelength'

export type CalibFreeFlags = Record<CalibParamKey, boolean>

/** Normalized geometry readout in display units (mm / deg / px / Å). */
export interface CalibGeometry {
  distMm: number | null
  poni1Mm: number | null
  poni2Mm: number | null
  rot1Deg: number | null
  rot2Deg: number | null
  rot3Deg: number | null
  wavelengthA: number | null
  centerXPx: number | null
  centerYPx: number | null
}

/** One per-peak residual point: ring index vs angular deviation in degrees. */
export interface CalibResidualPoint {
  ring: number
  deltaDeg: number
}

const PARAMS: Array<{ key: CalibParamKey }> = [
  { key: 'dist' },
  { key: 'poni1' },
  { key: 'poni2' },
  { key: 'rot1' },
  { key: 'rot2' },
  { key: 'rot3' },
  { key: 'wavelength' },
]

/**
 * Plain-language meaning of each refinable parameter (REQ 精修中心位点：把中文
 * 含义给用户). Inline bilingual like the step-3 title — pyFAI's raw names
 * (dist/poni1/…) stay visible for poni-file cross-reference, with the Chinese
 * meaning beside them and the full explanation on hover.
 * 各可精修参数的中文含义：pyFAI 原名保留（便于与 .poni 文件对照），旁注中文
 * 含义，悬停显示完整解释。
 */
const PARAM_MEANING: Record<CalibParamKey, { zh: string; en: string; zhTip: string; enTip: string }> = {
  dist: {
    zh: '样品距离',
    en: 'distance',
    zhTip: '样品到探测器的距离 dist（mm）。与中心一起默认参与精修。',
    enTip: 'Sample-to-detector distance (mm). Free by default.',
  },
  poni1: {
    zh: '中心 y (行)',
    en: 'beam center y',
    zhTip: '光束中心纵向位置 poni1（沿图像行方向 y，显示为 mm；px 值见上方“最终中心”的 Y）。',
    enTip: 'Beam-center position along image rows (y), shown in mm; pixel value is the Y of the final center above.',
  },
  poni2: {
    zh: '中心 x (列)',
    en: 'beam center x',
    zhTip: '光束中心横向位置 poni2（沿图像列方向 x，显示为 mm；px 值见上方“最终中心”的 X）。',
    enTip: 'Beam-center position along image columns (x), shown in mm; pixel value is the X of the final center above.',
  },
  rot1: {
    zh: '俯仰角（绕 x 轴）',
    en: 'tilt around x',
    zhTip: '探测器绕水平轴（x）的倾角 rot1。默认固定：实验室探测器近似正对光束，环数不多时放开倾角易导致拟合退化；确有倾斜时再勾选放开。',
    enTip: 'Detector tilt around the horizontal (x) axis. Fixed by default — free it only when the detector is visibly tilted.',
  },
  rot2: {
    zh: '偏摆角（绕 y 轴）',
    en: 'tilt around y',
    zhTip: '探测器绕竖直轴（y）的倾角 rot2。默认固定（同 rot1）。',
    enTip: 'Detector tilt around the vertical (y) axis. Fixed by default (same as rot1).',
  },
  rot3: {
    zh: '面内旋转（绕光轴）',
    en: 'in-plane roll',
    zhTip: '探测器绕入射光轴（z）的面内旋转角 rot3。默认固定；只有需要校正图像方位角零点时才放开。',
    enTip: 'In-plane rotation of the detector around the beam axis (z). Fixed by default.',
  },
  wavelength: {
    zh: '波长',
    en: 'wavelength',
    zhTip: 'X 射线波长（Å）。默认固定为已知光源值；只有波长未知且环数足够多时才建议放开。',
    enTip: 'X-ray wavelength (Å). Fixed to the known source value by default.',
  },
}

const paramMeaning = (key: CalibParamKey): string =>
  isZh.value ? PARAM_MEANING[key].zh : PARAM_MEANING[key].en

const paramTip = (key: CalibParamKey): string =>
  isZh.value ? PARAM_MEANING[key].zhTip : PARAM_MEANING[key].enTip

const props = defineProps<{
  geometry: CalibGeometry | null
  chi2: number | null
  residuals: CalibResidualPoint[]
  /** v-model:free — per-parameter free flags. */
  free: CalibFreeFlags
  /** Whether a refinement run is in flight. */
  running?: boolean
  /** Whether refinement is possible (needs picked peaks). */
  canRun?: boolean
  /** Tri-state convergence flag from the last run (null = not yet run). */
  converged?: boolean | null
}>()

const emit = defineEmits<{
  run: [payload: { passes: number }]
  'update:free': [value: CalibFreeFlags]
}>()

const { t, locale } = useI18n()

const isZh = computed(() => locale.value.startsWith('zh'))

// Step-3 title (renamed): zh 精修中心位点 / en Refine center & geometry.
// Inline bilingual — no i18n key yet (see final report's missing-keys list).
// 第 3 步标题（改名）：内联双语（暂无 i18n 键，见最终报告缺失键清单）。
const titleLabel = computed(() => (isZh.value ? '精修中心位点' : 'Refine center & geometry'))
const finalCenterLabel = computed(() => (isZh.value ? '最终中心 (px)' : 'Final center (px)'))
const finalCenterTitle = computed(() =>
  isZh.value
    ? '精修后的光束中心（poni2/pixel2, poni1/pixel1）——画布上以洋红十字标出，随每次精修更新'
    : 'Refined beam center (poni2/pixel2, poni1/pixel1) — the magenta crosshair on the canvas; updates with each refine',
)

const finalCenterValue = computed(() => {
  const x = props.geometry?.centerXPx
  const y = props.geometry?.centerYPx
  if (x == null || y == null || !Number.isFinite(x) || !Number.isFinite(y)) return '—'
  return `(${x.toFixed(2)}, ${y.toFixed(2)})`
})

// Internal passes selector (1/2/3), forwarded with the 'run' payload.
const passes = ref(1)

function onToggle(key: CalibParamKey, checked: boolean): void {
  emit('update:free', { ...props.free, [key]: checked })
}

function run(): void {
  if (props.running || props.canRun === false) return
  emit('run', { passes: passes.value })
}

function formatSci(value: number): string {
  if (!Number.isFinite(value)) return '—'
  if (value === 0) return '0'
  return value.toExponential(4)
}

function formatVal(value: number | null, unit: string): string {
  if (value == null || !Number.isFinite(value)) return '—'
  return `${value.toFixed(unit === 'px' ? 2 : 4)} ${unit}`
}

// ── Residual scatter chart / 残差散点图 ──────────────────────────────────────

const residualTraces = computed<PlotData[]>(() => {
  if (props.residuals.length === 0) return []
  const trace: PlotData = {
    type: 'scatter',
    mode: 'markers',
    x: props.residuals.map(r => r.ring),
    y: props.residuals.map(r => r.deltaDeg),
    marker: {
      size: 6,
      color: '#38bdf8',
    },
    hovertemplate: 'ring %{x}<br>Δ2θ = %{y:.4f}°<extra></extra>',
  }
  return [trace]
})

const residualLayout = computed<Partial<PlotLayout>>(() => ({
  margin: { t: 10, r: 12, b: 34, l: 48 },
  height: 220,
  xaxis: {
    title: { text: 'ring' },
    zeroline: false,
    dtick: 1,
  },
  yaxis: {
    title: { text: 'Δ2θ (°)' },
    zeroline: true,
    zerolinecolor: 'rgba(148, 163, 184, 0.4)',
  },
  showlegend: false,
}))
</script>

<style scoped>
.calib-refine-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.crp-title {
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.crp-subtitle {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-secondary);
  margin: 0 0 6px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.crp-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.crp-label {
  font-size: 0.8125rem;
  color: var(--text-secondary);
  font-weight: 500;
}

.crp-select {
  padding: 8px 10px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: 0.875rem;
}

.crp-hint {
  margin: 0;
  font-size: 0.75rem;
  color: var(--text-muted);
  line-height: 1.4;
}

.crp-hint--warn {
  padding: 6px 10px;
  border-radius: var(--radius-sm);
  background: rgba(234, 179, 8, 0.12);
  color: #a16207;
}

/* Free / fixed flag rows */
.crp-flags {
  display: grid;
  grid-template-columns: 1fr;
  gap: 2px;
}

.crp-flag {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  user-select: none;
}

.crp-flag:hover {
  background: var(--bg-hover);
}

.crp-flag input[type='checkbox'] {
  accent-color: var(--primary);
  width: 14px;
  height: 14px;
  flex-shrink: 0;
}

.crp-flag-name {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  color: var(--text-primary);
  white-space: nowrap;
}

/* 中文含义（REQ 精修中心位点）— pyFAI 名旁的浅色注记 */
.crp-flag-desc {
  flex: 1;
  min-width: 0;
  font-size: 0.72rem;
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.crp-flag-state {
  font-size: 0.7rem;
  color: var(--primary);
  font-weight: 600;
}

.crp-flag--fixed .crp-flag-state {
  color: var(--text-muted);
  font-weight: 500;
}

/* χ² */
.crp-chi2 {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  background: var(--bg-hover);
}

.crp-chi2-label {
  font-size: 0.8rem;
  color: var(--text-secondary);
  font-weight: 500;
}

.crp-chi2-value {
  font-family: var(--font-mono);
  font-size: 0.85rem;
  color: var(--text-primary);
  font-weight: 600;
}

/* Prominent refined beam center (最终中心) — headline of step 3 */
.crp-final-center {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 6px;
  padding: 8px 10px;
  border: 1px solid rgba(232, 121, 249, 0.55);
  border-radius: var(--radius-sm);
  background: rgba(232, 121, 249, 0.10);
}

.crp-final-center-label {
  font-size: 0.8rem;
  font-weight: 700;
  color: #e879f9;
  white-space: nowrap;
}

.crp-final-center-value {
  font-family: var(--font-mono);
  font-size: 0.92rem;
  font-weight: 700;
  color: var(--text-primary);
}

/* Geometry readout */
.crp-readout {
  margin: 0;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  overflow: hidden;
}

.crp-readout-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: 4px 10px;
}

.crp-readout-row:nth-child(odd) {
  background: var(--bg-hover);
}

.crp-readout-row dt {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--text-secondary);
  display: flex;
  align-items: baseline;
  gap: 6px;
  min-width: 0;
}

.crp-readout-row dt em {
  font-family: inherit;
  font-style: normal;
  font-size: 0.68rem;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.crp-readout-row dd {
  margin: 0;
  font-family: var(--font-mono);
  font-size: 0.78rem;
  color: var(--text-primary);
  font-weight: 600;
}

/* Buttons */
.crp-btn {
  padding: 8px 16px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
}

.crp-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.crp-btn--primary {
  border: none;
  background: var(--primary);
  color: var(--text-inverse);
  font-weight: 600;
}

.crp-btn--primary:hover:not(:disabled) {
  opacity: 0.9;
}

/* Chart */
.crp-chart {
  min-height: 220px;
  height: 220px;
}

.crp-empty {
  margin: 0;
  padding: 12px;
  text-align: center;
  font-size: 0.8rem;
  color: var(--text-muted);
  border: 1px dashed var(--border);
  border-radius: var(--radius-sm);
}
</style>
