<template>
  <div class="calib-peak-panel">
    <!-- Header + count / 头部 + 数量 -->
    <div class="cpp-head">
      <h4 class="cpp-title">{{ t('calibration.peaks.title') }}</h4>
      <span class="cpp-count">{{ t('calibration.peaks.count', { count: peaks.length }) }}</span>
    </div>

    <!-- REQ 2: ring-by-ring picking (逐一环选). The mode toolbar (单峰/环选/
         自动) is GONE — canvas clicks always collect guide points for the
         CURRENT ring, calib2 "+" spinner semantics.
         逐一环选：模式工具栏已移除——画布点击始终为“当前环号”收集引导点，
         数字框对标 calib2 的 “+” 环号语义（1 起）。 -->
    <div class="cpp-ringbar">
      <span class="cpp-ringbar-label" :title="currentRingTitle">{{ currentRingLabel }}</span>
      <div class="cpp-spinner">
        <button
          type="button"
          class="cpp-spinner-btn"
          :disabled="currentRing <= 1"
          :title="decRingTitle"
          @click="stepRing(-1)"
        >
          −
        </button>
        <input
          type="number"
          class="cpp-spinner-input"
          min="1"
          step="1"
          :value="currentRing"
          data-ai-id="calibration:current-ring"
          @change="onRingInput"
        />
        <button
          type="button"
          class="cpp-spinner-btn"
          :title="incRingTitle"
          @click="stepRing(1)"
        >
          +
        </button>
      </div>
    </div>

    <p class="cpp-hint">{{ ringHint }}</p>

    <!-- Ring-band half-width ±dr (2026-10-23 user feedback: the harvest band
         was a hidden 15 px constant AND the sensitivity slider had no effect
         on ring picking). Both now live here in the open. /
         环带半宽 ±dr（2026-10-23 用户反馈：收峰环带此前是隐藏的 15px 常量，
         且灵敏度对环选毫无作用）。两项设置都放在明处。 -->
    <div class="cpp-row cpp-band-row" :title="t('calibration.peaks.bandTolHint')">
      <label class="cpp-band-label">{{ t('calibration.peaks.bandTol') }}</label>
      <input
        type="number"
        class="cpp-band-input"
        min="2"
        max="80"
        step="1"
        :value="bandTol"
        data-ai-id="calibration:band-tol"
        @change="onBandTolInput"
      />
    </div>

    <!-- Ring-picking controls / 环选控制 -->
    <div class="cpp-row">
      <button
        type="button"
        class="cpp-btn cpp-btn--primary"
        :disabled="guideCount < 3 || ringPicking"
        data-ai-id="calibration:finish-ring"
        @click="$emit('finish-ring')"
      >
        {{ finishRingLabel }} ({{ guideCount }})
      </button>
      <button
        type="button"
        class="cpp-btn"
        :disabled="guideCount === 0 || ringPicking"
        @click="$emit('clear-guides')"
      >
        {{ clearGuidesLabel }}
      </button>
    </div>

    <!-- Pick initial centre (2026-10-20): arms a SINGLE-SHOT canvas mode that
         sends the next click to set_center (centre seed + auto ring
         re-derivation under the new coordinate system). /
         点选初猜中心（2026-10-20）：武装一次性画布模式——下一次点击发送给
         set_center（中心种子 + 自动环号按新坐标系重排）。 -->
    <div class="cpp-row">
      <button
        type="button"
        class="cpp-btn"
        :class="{ 'cpp-btn--armed': centerPicking }"
        :disabled="ringPicking"
        :title="centerPickTitle"
        @click="$emit('toggle-center-pick')"
      >
        {{ centerPickLabel }}
      </button>
    </div>

    <!-- Extraction options (calib2 parity): beyond mask = calib2 "Ring" tool
         tooltip "Extract peaks, beyond masked values"; remove existing =
         calib2 "Rubber" tool semantics applied to the harvested band/arc.
         提取选项（对标 calib2）：越过掩码 / 移除拾取区已有点。 -->
    <div class="cpp-options">
      <label class="cpp-check" :title="beyondMaskTitle">
        <input
          type="checkbox"
          :checked="beyondMask"
          data-ai-id="calibration:opt-beyond-mask"
          @change="$emit('update:beyondMask', ($event.target as HTMLInputElement).checked)"
        />
        <span>{{ beyondMaskLabel }}</span>
      </label>
      <label class="cpp-check" :title="removeExistingTitle">
        <input
          type="checkbox"
          :checked="removeExisting"
          data-ai-id="calibration:opt-remove-existing"
          @change="$emit('update:removeExisting', ($event.target as HTMLInputElement).checked)"
        />
        <span>{{ removeExistingLabel }}</span>
      </label>
    </div>

    <!-- Advanced (open by default since 2026-10-22, user request: peak
         recognition was too wide at the old default sensitivity and the knob
         was hidden in the collapsed area): full-image auto detection only /
         高级（2026-10-22 起默认展开，用户要求：原默认灵敏度下峰识别偏宽，
         而旋钮藏在折叠区）：仅保留全图自动拾取，先按理论环分配再重新分组 -->
    <details class="cpp-advanced" open>
      <summary class="cpp-advanced-summary">{{ advancedLabel }}</summary>
      <div class="cpp-advanced-body">
        <div class="cpp-field">
          <label class="cpp-label">{{ t('calibration.peaks.sensitivity') }}: {{ sensitivity.toFixed(2) }}</label>
          <input
            type="range"
            class="cpp-slider"
            min="0"
            max="1"
            step="0.05"
            :value="sensitivity"
            @input="$emit('update:sensitivity', Number(($event.target as HTMLInputElement).value))"
          />
        </div>
        <button
          type="button"
          class="cpp-btn"
          :disabled="detecting"
          data-ai-id="calibration:auto-peaks"
          :title="autoTitle"
          @click="$emit('auto')"
        >
          {{ detecting ? detectingLabel : autoLabel }}
        </button>
      </div>
    </details>

    <!-- Clear peaks + ring refresh/self-check (calib2 peak table parity) /
         清空峰 + 刷新环号/自检（对标 calib2 峰表） -->
    <div class="cpp-row">
      <button
        type="button"
        class="cpp-btn"
        :disabled="peaks.length === 0"
        @click="$emit('clear')"
      >
        {{ t('calibration.peaks.clear') }}
      </button>
      <button
        type="button"
        class="cpp-btn"
        :disabled="peaks.length === 0 || refreshing"
        data-ai-id="calibration:refresh-rings"
        :title="refreshTitle"
        @click="$emit('refresh-rings')"
      >
        {{ refreshing ? refreshRunningLabel : refreshLabel }}
      </button>
    </div>
    <!-- Caution (user request 2026-10-13): refresh renumbers from the CURRENT
         geometry — with a weak signal or unconfirmed initial guesses that can
         scramble ring numbers. Refine re-assigns automatically before fitting,
         so clicking refresh manually is mainly to INSPECT the table. /
         告诫（2026-10-13 用户要求）：刷新按当前几何重排环号——信号不好或初值
         未确认时可能打乱环号；精修前已自动重排，手动点击主要为检视峰表。 -->
    <p class="cpp-hint cpp-hint--caution">{{ refreshCaution }}</p>

    <!-- Per-ring summary table (REQ: one row per ring, not per peak) /
         每环汇总表：一行一环（而非一行一峰）。
         环号带色块（与画布峰标记同色，环号可直接编辑=整环改号）｜峰数｜
         平均Δ2θ°｜可疑数（>0 时整行标红）。再次拾取同一环自动并入该环统计；
         右键删峰自动从该环计数扣减。 -->
    <div class="cpp-table-wrap">
      <table v-if="ringRows.length > 0" class="cpp-table">
        <thead>
          <tr>
            <th :title="ringColTitle">{{ t('calibration.peaks.colRing') }}</th>
            <th>{{ countColLabel }}</th>
            <th :title="deltaColTitle">平均Δ2θ°</th>
            <th :title="suspectColTitle">⚠</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in ringRows"
            :key="row.ring == null ? 'none' : row.ring"
            :class="{ 'cpp-row--suspect': row.suspects > 0 }"
          >
            <td class="cpp-ringcell">
              <template v-if="row.ring != null">
                <span class="cpp-swatch" :style="{ background: calibPeakRingColor(row.ring) }" />
                <!-- ★ = user-owned ring number (survives refine's refresh). /
                     ★ = 用户指定的环号（精修重排中保留）。 -->
                <span
                  v-if="row.userOwned"
                  class="cpp-ring-user"
                  :title="ringUserTitle"
                >★</span>
                <!-- calib2's ring-number spin box applied to the WHOLE ring:
                     editing moves every peak of this ring to the new number
                     (UI 1-based; emitted value converted to 0-based backend
                     index). / 整环改号：编辑把该环全部峰移到新环号（界面
                     1 起，发出时转 0 起后端环号）。 -->
                <input
                  type="number"
                  class="cpp-ring-input"
                  min="1"
                  step="1"
                  :value="row.ring + 1"
                  :title="ringEditTitle"
                  @change="onRingEdit(row.ring!, $event)"
                />
              </template>
              <span v-else class="cpp-unassigned">—</span>
            </td>
            <td>{{ row.count }}</td>
            <td :class="{ 'cpp-delta--suspect': row.suspects > 0 }">
              {{ row.meanDtheta == null ? '—' : row.meanDtheta.toFixed(2) }}
            </td>
            <td :class="{ 'cpp-delta--suspect': row.suspects > 0 }">
              {{ row.suspects > 0 ? row.suspects : '·' }}
            </td>
          </tr>
        </tbody>
      </table>
      <p v-else class="cpp-empty">{{ t('calibration.peaks.empty') }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * CalibPeakPanel.vue — 标定向导第 2 步：逐一环选 + 峰拾取控制 + 峰列表
 * Calibration wizard step 2: ring-by-ring picking controls + peak table.
 *
 * REQ 2 (ring-by-ring ONLY, 逐一环选): the 单峰/环选/自动 mode toolbar is
 * removed. The workflow is: set the CURRENT ring number in the spinner
 * (calib2 "+" semantics, 1-based, defaults to max(existing)+1) → click ≥3
 * guide points on that ring on the canvas → 完成本环 / Enter / double-click
 * harvests the ring via ring_pick with `assignRing` → the spinner advances to
 * max+1. Full-image auto detection survives ONLY as a collapsed 高级 action.
 * 逐一环选：先在数字框设定当前环号（1 起，默认 = 现有最大环号 +1），在画布上
 * 该环点 ≥3 个引导点，“完成本环 / 回车 / 双击”以 assignRing 收环，随后数字框
 * 自动跳到 max+1；全图自动拾取仅保留为折叠的“高级”动作。
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { CalibPeak } from '@/components/calibration/CalibCanvas.vue'
import { calibPeakRingColor } from '@/components/calibration/CalibCanvas.vue'

const props = withDefaults(defineProps<{
  peaks: CalibPeak[]
  sensitivity: number
  /**
   * Ring-band half-width ±dr (px) sent to ring_pick's tolPx. 2026-10-23:
   * previously a hidden backend constant (15 px). / 环带半宽 ±dr（px），
   * 此前是后端隐藏常量。
   */
  bandTol?: number
  /**
   * Current ring number (calib2-style, 1-based in the UI; the parent converts
   * to the 0-based backend index for ring_pick's assignRing).
   * 当前环号（界面 1 起；父组件换算为 0 起的后端 assignRing）。
   */
  currentRing: number
  /** Whether automatic detection is in flight (高级 action). */
  detecting?: boolean
  /** Number of ring-guide points collected so far. */
  guideCount?: number
  /** Whether ring_pick is in flight (disables the ring controls). */
  ringPicking?: boolean
  /** Whether the SINGLE-SHOT pick-initial-centre canvas mode is armed. */
  centerPicking?: boolean
  /** calib2 "Ring" tool parity: extract peaks beyond masked values. */
  beyondMask?: boolean
  /** calib2 "Rubber" parity: remove existing points inside the extraction area. */
  removeExisting?: boolean
  /** Whether the ring refresh/self-check (刷新环号/自检) call is in flight. */
  refreshing?: boolean
}>(), {
  detecting: false,
  guideCount: 0,
  ringPicking: false,
  centerPicking: false,
  beyondMask: false,
  removeExisting: false,
  refreshing: false,
  bandTol: 15,
})

const emit = defineEmits<{
  auto: []
  'update:sensitivity': [value: number]
  'update:bandTol': [value: number]
  'update:currentRing': [value: number]
  clear: []
  'finish-ring': []
  'clear-guides': []
  'toggle-center-pick': []
  'update:beyondMask': [value: boolean]
  'update:removeExisting': [value: boolean]
  'refresh-rings': []
  /**
   * User renumbered a ring in the summary table: every peak currently on
   * `oldRing` (0-based backend index) moves to `newRing` (0-based).
   * 汇总表中整环改号：该环全部峰移到新环号（均 0 起后端环号）。
   */
  'update-ring': [oldRing: number, newRing: number]
}>()

const { t, locale } = useI18n()

const isZh = computed(() => locale.value.startsWith('zh'))

// Inline bilingual labels — no dedicated i18n keys yet (see final report).
// 内联双语文案 —— 暂无 i18n 键（见最终报告缺失键清单）。
const currentRingLabel = computed(() => (isZh.value ? '当前环号' : 'Current ring'))
const currentRingTitle = computed(() =>
  isZh.value
    ? '引导点将拾取到该环；完成后自动进入下一环（calib2 “+” 语义，可手动改号）'
    : 'Guide points harvest into this ring; advances automatically (calib2 "+" semantics)',
)
const decRingTitle = computed(() => (isZh.value ? '上一环' : 'Previous ring'))
const incRingTitle = computed(() => (isZh.value ? '下一环（新建）' : 'Next ring (new)'))
const ringHint = computed(() =>
  isZh.value
    ? '在当前环上点击 ≥3 个引导点，然后点击 完成本环 / 双击 / 回车 收环；右键删除最近峰'
    : 'Click ≥3 guide points on the current ring, then Finish / double-click / Enter harvests it; right-click removes the nearest peak',
)
const finishRingLabel = computed(() => (isZh.value ? '完成本环' : 'Finish ring'))
const clearGuidesLabel = computed(() => (isZh.value ? '清除引导点' : 'Clear guides'))
const centerPickLabel = computed(() =>
  isZh.value
    ? (props.centerPicking ? '点选初猜中心中…（点击图像）' : '点选初猜中心')
    : (props.centerPicking ? 'Picking centre… (click the image)' : 'Pick initial centre'),
)
const centerPickTitle = computed(() =>
  isZh.value
    ? '在图像上单击光束中心的大致位置：作为初猜中心（poni 种子），自动环号会立即按新坐标系重排，您指定的环号保持不变；设置后自动退出该模式'
    : 'Click the approximate beam centre on the image: it seeds the geometry centre; auto ring numbers re-derive under the new coordinate system (your picked rings stay). The mode disarms after one set',
)
const advancedLabel = computed(() => (isZh.value ? '高级' : 'Advanced'))
const autoLabel = computed(() => (isZh.value ? '高级：全图自动拾取' : 'Advanced: full-image auto pick'))
const detectingLabel = computed(() => (isZh.value ? '自动拾取中…' : 'Detecting…'))
const autoTitle = computed(() =>
  isZh.value
    ? '全图 Massif 自动拾取：按理论环分配环号后重新分组（替换现有峰列表）'
    : 'Full-image Massif detection: assigns theoretical rings then re-groups (replaces the list)',
)

const beyondMaskLabel = computed(() => (isZh.value ? '越过掩码提取' : 'Beyond mask'))
const beyondMaskTitle = computed(() =>
  isZh.value
    ? 'calib2 Ring 工具：越过掩码值提取——收整环且掩码/死像素不阻断提取'
    : 'calib2 Ring tool: "Extract peaks, beyond masked values" — full-ring harvest never blocked by masked positions',
)
const removeExistingLabel = computed(() => (isZh.value ? '移除拾取区已有点' : 'Remove existing pts'))
const removeExistingTitle = computed(() =>
  isZh.value
    ? 'calib2 Rubber 工具语义：环选提取前，先移除提取区域内的已有峰点'
    : 'calib2 Rubber semantics: remove already-identified peaks inside the extraction area before merging',
)
const refreshLabel = computed(() => (isZh.value ? '刷新环号 / 自检' : 'Refresh rings / check'))
const refreshRunningLabel = computed(() => (isZh.value ? '自检中…' : 'Checking…'))
const refreshTitle = computed(() =>
  isZh.value
    ? '按当前几何重新分配全部环号，并标记偏离理论环的可疑峰'
    : 'Re-assign every ring number from the current geometry and flag deviating peaks',
)
/** Caution under the refresh button (user request 2026-10-13; wording
 *  updated 2026-10-20: refine now KEEPS user-picked ring numbers, only auto
 *  ones refresh). */
/** 刷新按钮下的告诫文案（2026-10-13 用户要求；2026-10-20 更新措辞：精修保留
 *  用户点选的环号，仅自动分配者刷新）。 */
const refreshCaution = computed(() =>
  isZh.value
    ? '提示：「刷新环号」会把全部环号（含手工环号）按当前几何重排，信号不好或初值未确认时慎用；精修前的自动重排只刷新自动环号，您点选/改过的环号（标 ★）保持不变。'
    : 'Tip: "Refresh rings" re-derives EVERY ring (manual ones included) from the current geometry — use with care. The automatic refresh before refining only touches auto-assigned rings; the ones you picked/renumbered (marked ★) stay.',
)
const ringColTitle = computed(() =>
  isZh.value ? '环号可直接编辑（整环改号，界面 1 起）' : 'Ring number is editable (renumbers the whole ring, 1-based)',
)
const ringEditTitle = computed(() =>
  isZh.value ? '输入新环号并回车：该环全部峰移动到新环' : 'Type a new ring number: every peak of this ring moves to it',
)
const countColLabel = computed(() => (isZh.value ? '峰数' : 'Peaks'))
const ringUserTitle = computed(() =>
  isZh.value
    ? '用户指定的环号：精修前的自动重排会保留它（「刷新环号/自检」仍会重排全部）'
    : 'User-set ring number: kept by refine\'s automatic refresh ("Refresh rings / check" still re-derives everything)',
)
const suspectColTitle = computed(() =>
  isZh.value ? '可疑峰数（偏离所分配理论环）' : 'Suspect peaks (deviating from their assigned ring)',
)
const deltaColTitle = computed(() =>
  isZh.value ? '该环各峰与理论环 2θ 偏差的均值（度）' : 'Mean per-peak 2θ deviation of the ring (deg)',
)

/** Spinner −/+ steps (floor at 1, calib2 rejects ring numbers < 1). */
function stepRing(delta: number): void {
  const next = Math.max(1, Math.floor(props.currentRing) + delta)
  emit('update:currentRing', next)
}

/** Typed spinner input — any integer ≥ 1; invalid input is ignored. */
function onRingInput(e: Event): void {
  const raw = Number.parseInt((e.target as HTMLInputElement).value, 10)
  if (!Number.isFinite(raw) || raw < 1) {
    // Snap the field back to the current value.
    ;(e.target as HTMLInputElement).value = String(Math.max(1, Math.floor(props.currentRing)))
    return
  }
  emit('update:currentRing', raw)
}

/** Ring-band ±dr input: clamp to 2..80 px; invalid snaps back. / 环带 ±dr
 *  输入：钳制在 2–80 px，非法输入回弹。 */
function onBandTolInput(e: Event): void {
  const raw = Number.parseFloat((e.target as HTMLInputElement).value)
  if (!Number.isFinite(raw)) {
    ;(e.target as HTMLInputElement).value = String(props.bandTol ?? 15)
    return
  }
  emit('update:bandTol', Math.min(80, Math.max(2, Math.round(raw))))
}

/**
 * One summary row per ring: ring number (null = unassigned), peak count,
 * mean signed Δ2θ (null when no peak of the ring carries one) and the
 * suspect count (刷新环号/自检 self-check). Display-only aggregation over
 * the full peak list — the backend still receives every individual peak.
 * 每环一行汇总：环号（null=未分配）、峰数、平均Δ2θ、可疑数。仅显示层聚合，
 * 后端仍接收完整逐峰列表。
 */
interface CalibRingRow {
  ring: number | null
  count: number
  meanDtheta: number | null
  suspects: number
  /** True when ≥1 peak of the ring carries a user-set ring number (★). */
  userOwned: boolean
}

const ringRows = computed<CalibRingRow[]>(() => {
  const byRing = new Map<number | null, CalibPeak[]>()
  for (const p of props.peaks) {
    const key = p.ring
    const bucket = byRing.get(key)
    if (bucket) bucket.push(p)
    else byRing.set(key, [p])
  }
  const rows: CalibRingRow[] = []
  for (const [ring, bucket] of byRing) {
    const dthetas = bucket.map(p => p.dthetaDeg).filter((d): d is number => d != null)
    rows.push({
      ring,
      count: bucket.length,
      meanDtheta: dthetas.length > 0
        ? dthetas.reduce((a, b) => a + b, 0) / dthetas.length
        : null,
      suspects: bucket.filter(p => p.suspect).length,
      userOwned: bucket.some(p => p.ringUser === true),
    })
  }
  // Ascending ring order; unassigned (null) last.
  // 环号升序；未分配（null）居末。
  rows.sort((a, b) => {
    if (a.ring == null) return 1
    if (b.ring == null) return -1
    return a.ring - b.ring
  })
  return rows
})

/** Ring-number cell edit (1-based UI) → forward (oldRing, newRing) 0-based. */
function onRingEdit(oldRing: number, e: Event): void {
  const raw = Number.parseInt((e.target as HTMLInputElement).value, 10)
  if (!Number.isFinite(raw) || raw < 1) return
  const newRing = raw - 1
  if (newRing === oldRing) return
  emit('update-ring', oldRing, newRing)
}
</script>

<style scoped>
.calib-peak-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.cpp-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}

.cpp-title {
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.cpp-count {
  font-size: 0.8rem;
  color: var(--text-secondary);
  font-family: var(--font-mono);
  white-space: nowrap;
}

.cpp-hint {
  margin: 0;
  font-size: 0.75rem;
  color: var(--text-muted);
  line-height: 1.4;
}

/* Amber caution variant (refresh-rings tip, 2026-10-13). / 琥珀色告诫变体。 */
.cpp-hint--caution {
  color: #b45309;
}

/* Ring-number spinner bar (REQ 2) / 当前环号数字框 */
.cpp-ringbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 6px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
}

.cpp-ringbar-label {
  font-size: 0.8125rem;
  color: var(--text-secondary);
  font-weight: 600;
  white-space: nowrap;
}

.cpp-spinner {
  display: flex;
  align-items: center;
  gap: 4px;
}

.cpp-spinner-btn {
  width: 26px;
  height: 26px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: 0.9rem;
  font-weight: 700;
  cursor: pointer;
}

.cpp-spinner-btn:hover:not(:disabled) {
  border-color: var(--primary);
  color: var(--primary);
}

.cpp-spinner-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.cpp-spinner-input {
  width: 58px;
  padding: 3px 6px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--bg-surface);
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: 0.82rem;
  font-weight: 600;
  text-align: center;
}

.cpp-spinner-input:focus {
  outline: none;
  border-color: var(--border-focus);
}

/* Ring-band ±dr row / 环带 ±dr 行 */
.cpp-band-row {
  align-items: center;
  gap: 8px;
}

.cpp-band-label {
  flex: 1;
  min-width: 0;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-secondary);
}

.cpp-band-input {
  width: 64px;
  padding: 3px 6px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: 0.78rem;
  text-align: center;
}

.cpp-band-input:focus {
  outline: none;
  border-color: var(--border-focus);
}

/* Advanced (collapsed) section / 高级折叠区 */
.cpp-advanced {
  border: 1px dashed var(--border);
  border-radius: var(--radius-md);
  padding: 6px 10px;
}

.cpp-advanced-summary {
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--text-secondary);
  cursor: pointer;
  user-select: none;
}

.cpp-advanced-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-top: 8px;
}

/* Extraction options (calib2 parity) / 提取选项 */
.cpp-options {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.cpp-check {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.75rem;
  color: var(--text-secondary);
  cursor: pointer;
  user-select: none;
}

.cpp-check input {
  accent-color: var(--primary);
  width: 13px;
  height: 13px;
  flex: none;
}

.cpp-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.cpp-label {
  font-size: 0.8125rem;
  color: var(--text-secondary);
  font-weight: 500;
}

.cpp-slider {
  width: 100%;
  accent-color: var(--primary);
}

.cpp-row {
  display: flex;
  gap: 8px;
}

.cpp-row .cpp-btn {
  flex: 1;
}

.cpp-btn {
  padding: 8px 14px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: 0.8125rem;
  font-weight: 500;
  cursor: pointer;
  white-space: nowrap;
  transition: border-color var(--transition-fast), background var(--transition-fast);
}

.cpp-btn:hover:not(:disabled) {
  border-color: var(--border-hover);
  box-shadow: var(--shadow-sm);
}

.cpp-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.cpp-btn--active {
  border-color: var(--primary);
  color: var(--primary);
  background: var(--primary-bg);
}

.cpp-btn--primary {
  border: none;
  background: var(--primary);
  color: var(--text-inverse);
  font-weight: 600;
}

.cpp-btn--primary:hover:not(:disabled) {
  opacity: 0.9;
}

/* Armed single-shot centre pick (点选初猜中心激活态) — magenta like the
   beam-centre crosshair it seeds. */
.cpp-btn--armed {
  border-color: #e879f9;
  color: #e879f9;
  background: rgba(232, 121, 249, 0.10);
}

/* ★ user-owned ring badge / 用户环号标记 */
.cpp-ring-user {
  color: #e879f9;
  font-size: 0.78rem;
  line-height: 1;
  cursor: help;
}

.cpp-table-wrap {
  max-height: 320px;
  overflow-y: auto;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}

.cpp-table {
  width: 100%;
  border-collapse: collapse;
  font-family: var(--font-mono);
  font-size: 0.78rem;
}

.cpp-table th {
  position: sticky;
  top: 0;
  background: var(--bg-surface-alt);
  color: var(--text-secondary);
  font-weight: 600;
  text-align: right;
  padding: 6px 10px;
  border-bottom: 1px solid var(--border);
}

.cpp-table td {
  padding: 4px 10px;
  text-align: right;
  color: var(--text-primary);
  border-bottom: 1px solid var(--border);
}

.cpp-table tbody tr:last-child td {
  border-bottom: none;
}

/* Editable ring-number cell / 可编辑环号单元格 */
.cpp-ringcell {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
}

.cpp-ringcell .cpp-ring-input {
  width: 52px;
}

/* Ring color swatch — matches the canvas peak markers for that ring /
 * 环色块——与画布上该环峰标记同色。 */
.cpp-swatch {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex: none;
  border: 1px solid rgba(255, 255, 255, 0.65);
  box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.35);
}

.cpp-unassigned {
  color: var(--text-muted);
}

.cpp-ring-input {
  width: 58px;
  padding: 2px 6px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--bg-surface);
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: 0.78rem;
  text-align: right;
}

.cpp-ring-input:focus {
  outline: none;
  border-color: var(--border-focus);
}

/* Suspect peak row (刷新环号/自检) / 可疑峰行 */
.cpp-row--suspect td {
  background: rgba(248, 113, 113, 0.10);
}

.cpp-delta--suspect {
  color: #f87171;
  font-weight: 700;
}

.cpp-empty {
  margin: 0;
  padding: 16px 12px;
  text-align: center;
  font-size: 0.8rem;
  /* --text-muted was 2.56:1 on white (2026-10-23 visual review) — the empty
     state is guidance copy, use the readable secondary colour. /
     空态是引导文案，用可读的次级色（原 muted 仅 2.56:1）。 */
  color: var(--text-secondary);
}
</style>
