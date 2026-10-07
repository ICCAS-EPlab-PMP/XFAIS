<template>
  <div class="calib-ring-standard">
    <h4 class="crs-title">{{ t('calibration.ring.title') }}</h4>
    <p class="crs-hint">{{ t('calibration.ring.hint') }}</p>

    <!-- FIT2D-style zoomed second pick / FIT2D 式放大二次选点 -->
    <label class="crs-zoom">
      <input
        type="checkbox"
        :checked="zoomEnabled"
        data-ai-id="calibration:ring-zoom"
        @change="$emit('toggle-zoom', ($event.target as HTMLInputElement).checked)"
      />
      <span class="crs-zoom-text">
        <span class="crs-zoom-label">{{ t('calibration.ring.zoomLabel') }}</span>
        <span class="crs-zoom-hint">{{ t('calibration.ring.zoomHint') }}</span>
      </span>
    </label>

    <!-- Point count + fit RMS / 点数与拟合 RMS -->
    <div class="crs-stats">
      <span class="crs-stat">{{ t('calibration.ring.points') }}: {{ pointCount }}</span>
      <span v-if="rmsPx != null" class="crs-stat">
        {{ t('calibration.ring.rms') }}: {{ rmsPx.toFixed(2) }} px
      </span>
      <span v-if="fit" class="crs-stat crs-stat--fit">
        ({{ fit.cx.toFixed(1) }}, {{ fit.cy.toFixed(1) }}) r={{ fit.radiusPx.toFixed(1) }} px
      </span>
    </div>

    <button
      type="button"
      class="crs-btn"
      data-ai-id="calibration:ring-clear"
      :disabled="pointCount === 0"
      @click="$emit('clear')"
    >
      {{ t('calibration.ring.clear') }}
    </button>

    <!-- Known ring value + unit. The RAW text is owned by the parent (v-model
         via value-text) so the canvas Enter / double-click shortcut can submit
         the same value; keeping the raw string (not a number) means interim
         states like "0." are never rewritten mid-typing.
         已知环数值 + 单位。原始文本由父组件持有（value-text 双向绑定），使画布
         回车 / 双击快捷提交用的是同一个值；存文本（而非数字）保证 “0.” 之类
         的中间输入不会被改写。 -->
    <div class="crs-value-field">
      <label class="crs-label">{{ t('calibration.ring.valueLabel') }}</label>
      <div class="crs-value-row">
        <input
          :value="valueText"
          type="number"
          step="any"
          min="0"
          class="crs-input"
          data-ai-id="calibration:ring-value"
          placeholder="0.0"
          @input="$emit('update:valueText', ($event.target as HTMLInputElement).value)"
          @keydown.enter="apply"
        />
        <select
          :value="unit"
          class="crs-select"
          data-ai-id="calibration:ring-unit"
          @change="$emit('update:unit', ($event.target as HTMLSelectElement).value as CalibRingUnit)"
        >
          <option v-for="opt in RING_UNITS" :key="opt.value" :value="opt.value">
            {{ t(opt.labelKey) }}
          </option>
        </select>
      </div>
      <!-- The value is OPTIONAL: empty → the distance defaults to the session's
           initial guess (internal mode: 200 mm) and only the centre is
           calibrated. / 数值可选：留空则距离取会话初始猜测（内标模式 200 mm），
           仅中心参与标定。 -->
      <p class="crs-value-hint">
        {{ t('calibration.ring.valueOptionalHint', { mm: defaultDistMmText }) }}
      </p>
    </div>

    <button
      type="button"
      class="crs-btn crs-btn--primary"
      data-ai-id="calibration:ring-fit-apply"
      :disabled="!canApply"
      @click="apply"
    >
      {{ applying ? t('calibration.refine.running') : t('calibration.ring.apply') }}
    </button>

    <!-- Result of the LAST successful ring_standard call / 上次成功标定结果 -->
    <div v-if="result" class="crs-result">
      <h5 class="crs-result-title">{{ t('calibration.ring.resultTitle') }}</h5>
      <dl class="crs-readout">
        <div class="crs-readout-row">
          <dt>{{ t('calibration.ring.resultCenter') }}</dt>
          <dd>{{ formatPair(result.centerXPx, result.centerYPx) }}</dd>
        </div>
        <div class="crs-readout-row">
          <dt>{{ t('calibration.ring.resultRadius') }}</dt>
          <dd>{{ formatVal(result.radiusPx, 2) }}</dd>
        </div>
        <div class="crs-readout-row">
          <dt>{{ t('calibration.ring.resultTth') }}</dt>
          <dd>{{ formatVal(result.tthDeg, 4) }}</dd>
        </div>
        <div class="crs-readout-row">
          <dt>{{ t('calibration.ring.resultSd') }}</dt>
          <dd>{{ formatVal(result.distMm, 3) }}</dd>
        </div>
      </dl>
      <!-- Default-distance warning (user request): when the fit ran WITHOUT a
           ring value, the SD is the initial guess and the exported .poni will
           carry the Dist-default annotation.
           默认距离警示（用户要求）：拟合未提供环数值时 SD 即初始猜测，导出的
           .poni 将写入 Dist-default 标注。 -->
      <p v-if="result.distDefaulted" class="crs-default-warn">
        {{ t('calibration.ring.resultDefaultDist', { mm: defaultResultDistText }) }}
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * CalibRingStandardPanel.vue — 标定向导 · 内标定标第 2 步面板
 * Calibration wizard, internal-standard mode, step 2:
 * the user clicks ≥3 points on ONE ring (canvas) and MAY enter the ring's
 * known value in one of six units — with a value, the backend's
 * `ring_standard` action computes the full geometry (centre + sample-detector
 * distance) from the circle fit; with the value LEFT EMPTY the centre still
 * comes from the fit while the distance defaults to the session's initial
 * guess (internal mode: 200 mm), flagged via `distDefaulted` and annotated in
 * the exported .poni. / 用户在同一个环上点 ≥3 点（画布），可填写该环已知数值
 * （六种单位之一）——提供数值时后端 `ring_standard` 由圆拟合直接算出完整几何
 * （中心 + 样品-探测器距离）；数值留空时中心仍来自拟合，距离取会话初始猜测
 * （内标模式 200 mm），以 `distDefaulted` 标记并在导出的 .poni 中注明。
 *
 * This panel owns the ring-value input + unit; the parent owns the picked
 * points / the apply call.
 * 本面板持有环数值输入与单位；点选与调用由父组件负责。
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

/** Value units accepted by the backend ring_standard action. / 后端接受的单位。 */
export type CalibRingUnit = 'q_A' | 'q_nm' | 'tth_deg' | 'd_A' | 'd_nm' | 'dist_mm'

/** Summary of the LAST ring_standard response (null = never fitted). */
export interface CalibRingStandardResult {
  centerXPx: number | null
  centerYPx: number | null
  radiusPx: number | null
  rmsPx: number | null
  tthDeg: number | null
  distMm: number | null
  /** True when the fit ran WITHOUT a ring value → SD is the initial guess
   *  (dist0), annotated in the exported .poni. / 未提供环数值拟合 → SD 为
   *  初始猜测（dist0），导出的 .poni 会写入标注。 */
  distDefaulted: boolean | null
}

/** Fitted preview circle through the picked points (parent's Kåsa fit). */
export interface CalibRingFitLike {
  cx: number
  cy: number
  radiusPx: number
}

const RING_UNITS: Array<{ value: CalibRingUnit; labelKey: string }> = [
  { value: 'q_nm', labelKey: 'calibration.ring.unitQN' },
  { value: 'q_A', labelKey: 'calibration.ring.unitQA' },
  { value: 'tth_deg', labelKey: 'calibration.ring.unitTth' },
  { value: 'd_A', labelKey: 'calibration.ring.unitDA' },
  { value: 'd_nm', labelKey: 'calibration.ring.unitDN' },
  { value: 'dist_mm', labelKey: 'calibration.ring.unitSd' },
]

const props = defineProps<{
  /** Number of points currently picked on the canvas. / 画布上已点选的点数。 */
  pointCount: number
  /** Circle through the picked points (null below 3 points / degenerate). */
  fit: CalibRingFitLike | null
  /** Fit RMS in px (null while fewer than 3 points). / 拟合 RMS（px）。 */
  rmsPx: number | null
  /** ring_standard request in flight. / ring_standard 请求进行中。 */
  applying: boolean
  /** Last successful result (null = none yet). / 上次成功结果。 */
  result: CalibRingStandardResult | null
  /** FIT2D-style zoomed second pick toggle state. / 放大二次选点开关状态。 */
  zoomEnabled: boolean
  /** RAW ring-value text (parent-owned; never rewritten while typing). */
  valueText: string
  /** Selected value unit. / 当前单位。 */
  unit: CalibRingUnit
  /** Session's initial distance guess (mm) — shown as the default the empty
   *  value falls back to. / 会话初始距离猜测（mm）——留空数值时回退的默认值。 */
  defaultDistMm: number
}>()

const emit = defineEmits<{
  clear: []
  /** Apply / 拟合计算 — the parent reads valueText + unit from its own state. */
  apply: []
  'toggle-zoom': [enabled: boolean]
  'update:valueText': [value: string]
  'update:unit': [value: CalibRingUnit]
}>()

const { t } = useI18n()

/**
 * ≥3 points suffice to apply: an EMPTY value now means "default distance"
 * (the backend falls back to the session's initial guess). A NON-empty value
 * that does not parse to a positive number is rejected by the PARENT with a
 * warning toast (the backend re-validates regardless).
 * ≥3 点即可拟合：数值留空现在表示「使用默认距离」（后端回退会话初始猜测）。
 * 非空但不是正数的值由父组件以 warning toast 拒绝（后端无论如何会再校验）。
 */
const canApply = computed(() => props.pointCount >= 3 && !props.applying)

/** {mm} figure for the value-optional hint. / 提示文案中的 {mm} 数值。 */
const defaultDistMmText = computed(() =>
  Number.isFinite(props.defaultDistMm) ? props.defaultDistMm.toFixed(1) : '?',
)

/** {mm} figure for the default-distance warning (last response's SD). */
const defaultResultDistText = computed<string>(() => {
  const mm = props.result?.distMm
  return mm != null && Number.isFinite(mm) ? mm.toFixed(1) : '?'
})

function apply(): void {
  if (!canApply.value) return
  emit('apply')
}

function formatVal(value: number | null, digits: number): string {
  if (value == null || !Number.isFinite(value)) return '—'
  return value.toFixed(digits)
}

function formatPair(x: number | null, y: number | null): string {
  if (x == null || y == null || !Number.isFinite(x) || !Number.isFinite(y)) return '—'
  return `(${x.toFixed(2)}, ${y.toFixed(2)})`
}
</script>

<style scoped>
.calib-ring-standard {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.crs-title {
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.crs-hint {
  margin: 0;
  font-size: 0.75rem;
  color: var(--text-muted);
  line-height: 1.45;
}

/* FIT2D-style zoom toggle / FIT2D 式放大开关 */
.crs-zoom {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 6px 8px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  cursor: pointer;
  user-select: none;
}

.crs-zoom input[type='checkbox'] {
  accent-color: var(--primary);
  width: 14px;
  height: 14px;
  margin-top: 2px;
  flex-shrink: 0;
}

.crs-zoom-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.crs-zoom-label {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-primary);
}

.crs-zoom-hint {
  font-size: 0.68rem;
  color: var(--text-muted);
  line-height: 1.35;
}

.crs-stats {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.crs-stat {
  font-size: 0.72rem;
  color: var(--text-secondary);
  font-family: var(--font-mono);
}

.crs-stat--fit {
  color: var(--text-muted);
}

.crs-value-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.crs-label {
  font-size: 0.8125rem;
  color: var(--text-secondary);
  font-weight: 500;
}

.crs-value-row {
  display: flex;
  gap: 8px;
}

/* Optional-value hint / 数值可选提示 */
.crs-value-hint {
  margin: 0;
  font-size: 0.68rem;
  color: var(--text-muted);
  line-height: 1.35;
}

.crs-input {
  flex: 1;
  min-width: 0;
  padding: 7px 9px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: 0.8rem;
  font-family: var(--font-mono);
}

.crs-select {
  padding: 7px 8px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: 0.78rem;
  max-width: 46%;
}

.crs-input:focus,
.crs-select:focus {
  outline: none;
  border-color: var(--border-focus);
}

.crs-btn {
  padding: 8px 14px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: 0.85rem;
  font-weight: 500;
  cursor: pointer;
}

.crs-btn:hover:not(:disabled) {
  border-color: var(--border-hover);
  box-shadow: var(--shadow-sm);
}

.crs-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.crs-btn--primary {
  border: none;
  background: var(--primary);
  color: var(--text-inverse);
  font-weight: 600;
}

.crs-btn--primary:hover:not(:disabled) {
  opacity: 0.9;
  box-shadow: none;
}

/* Result readout / 结果读数 */
.crs-result {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.crs-result-title {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-secondary);
  margin: 0;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.crs-readout {
  margin: 0;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  overflow: hidden;
}

.crs-readout-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 8px;
  padding: 4px 10px;
}

.crs-readout-row:nth-child(odd) {
  background: var(--bg-hover);
}

.crs-readout-row dt {
  font-size: 0.75rem;
  color: var(--text-secondary);
  min-width: 0;
}

.crs-readout-row dd {
  margin: 0;
  font-family: var(--font-mono);
  font-size: 0.78rem;
  color: var(--text-primary);
  font-weight: 600;
  white-space: nowrap;
}

/* Default-distance warning row (amber, mirrors CalibRefinePanel's warn hint)
   / 默认距离警示行（琥珀色，对标 CalibRefinePanel 的警示提示） */
.crs-default-warn {
  margin: 0;
  padding: 6px 10px;
  border-radius: var(--radius-sm);
  background: rgba(234, 179, 8, 0.12);
  color: #a16207;
  font-size: 0.72rem;
  line-height: 1.4;
}
</style>
