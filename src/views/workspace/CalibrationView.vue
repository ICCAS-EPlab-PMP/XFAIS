<template>
  <section class="calibration-view">
    <!-- Header / 页头 -->
    <header class="cv-header">
      <h1>{{ t('calibration.title') }}</h1>
      <p class="cv-subtitle">{{ t('calibration.subtitle') }}</p>
    </header>

    <!-- Stepper: Setup → Peaks → Refine → Export / 四步向导 -->
    <nav class="cv-stepper">
      <button
        v-for="(s, i) in STEPS"
        :key="s.key"
        type="button"
        class="cv-step"
        :class="{
          'cv-step--active': step === s.key,
          'cv-step--done': i < stepIndex,
        }"
        :disabled="i > maxStep"
        @click="goStep(s.key)"
      >
        <span class="cv-step-num">{{ i < stepIndex ? '✓' : i + 1 }}</span>
        <span class="cv-step-label">{{ stepLabel(s) }}</span>
      </button>

      <!-- Prev / Next wizard navigation (next enabled once the step is complete)
           上一步/下一步：下一步在当前步骤完成后可用 -->
      <div class="cv-stepper-nav">
        <button
          type="button"
          class="cv-nav-btn"
          :disabled="stepIndex <= 0"
          @click="goPrev"
        >
          {{ prevLabel }}
        </button>
        <button
          type="button"
          class="cv-nav-btn cv-nav-btn--primary"
          :disabled="!canGoNext"
          data-ai-id="calibration:next-step"
          @click="goNext"
        >
          {{ nextLabel }}
        </button>
      </div>
    </nav>

    <div class="cv-layout">
      <!-- ===== Left: setup / controls column / 左侧：控制列 ===== -->
      <aside class="cv-controls">
        <div class="cv-card">
          <CalibSetupForm
            v-if="step === 'setup'"
            v-model="setupForm"
            :calibrants="calibrants"
            :detectors="detectors"
            :probe="probeResult"
            :probing="probing"
            :loading="setupLoading"
            :mask-stale="maskStale"
            @submit="handleSetup"
            @seed="handleSeedFromPoni"
            @probed="handleProbed"
          />

          <CalibPeakPanel
            v-else-if="step === 'peaks'"
            :peaks="peaks"
            :sensitivity="sensitivity"
            :current-ring="currentRing"
            :detecting="detecting"
            :guide-count="ringGuide.length"
            :ring-picking="ringPicking"
            :beyond-mask="beyondMask"
            :remove-existing="removeExisting"
            :refreshing="refreshingRings"
            @auto="handleAutoPeaks"
            @update:sensitivity="sensitivity = $event"
            @update:current-ring="currentRing = $event"
            @clear="handleClearPeaks"
            @finish-ring="finishRingPick"
            @clear-guides="ringGuide = []"
            @update:beyond-mask="beyondMask = $event"
            @update:remove-existing="removeExisting = $event"
            @refresh-rings="handleRefreshRings"
            @update-ring="handleRenameRing"
          />

          <CalibRefinePanel
            v-else-if="step === 'refine'"
            v-model:free="freeFlags"
            :geometry="geometry"
            :chi2="chi2"
            :residuals="residuals"
            :running="refining"
            :can-run="peaks.length > 0"
            :converged="converged"
            @run="handleRefine"
          />

          <div v-else class="cv-export">
            <button
              type="button"
              class="cv-btn cv-btn--primary"
              data-ai-id="calibration:export"
              @click="exportDialogOpen = true"
            >
              {{ t('calibration.export.savePoni') }}
            </button>
            <button
              type="button"
              class="cv-btn cv-btn--go"
              @click="goIntegrate"
            >
              {{ t('calibration.export.goIntegrate') }} →
            </button>
          </div>
        </div>
      </aside>

      <!-- ===== Center: canvas / 中央：画布 ===== -->
      <div class="cv-center">
        <!-- Render settings bar: ALWAYS visible, independent of wizard step.
             渲染设置条：始终可见，与向导步骤无关。 -->
        <div class="cv-render-bar">
          <label class="cv-rb-field">
            <span class="cv-rb-label">{{ t('maskMaker.display.colormap') }}</span>
            <select
              :value="colormap"
              class="cv-rb-select"
              @change="onRenderChange('colormap', ($event.target as HTMLSelectElement).value)"
            >
              <option v-for="cm in colormapOptions" :key="cm" :value="cm">{{ cm }}</option>
            </select>
          </label>
          <label class="cv-rb-toggle">
            <input
              type="checkbox"
              :checked="useLog"
              @change="onRenderChange('useLog', ($event.target as HTMLInputElement).checked)"
            />
            <span>{{ t('maskMaker.display.logScale') }}</span>
          </label>
          <div class="cv-rb-clim">
            <span class="cv-rb-label">{{ t('maskMaker.display.contrastMode') }}</span>
            <label class="cv-rb-radio">
              <input
                type="radio"
                value="auto"
                :checked="climMode === 'auto'"
                @change="onRenderChange('climMode', 'auto')"
              />
              <span>{{ t('maskMaker.display.contrastAuto') }}</span>
            </label>
            <label class="cv-rb-radio">
              <input
                type="radio"
                value="manual"
                :checked="climMode === 'manual'"
                @change="onRenderChange('climMode', 'manual')"
              />
              <span>{{ t('maskMaker.display.contrastManual') }}</span>
            </label>
          </div>
          <template v-if="climMode === 'manual'">
            <label class="cv-rb-field">
              <span class="cv-rb-label">{{ t('maskMaker.display.contrastMin') }}</span>
              <input
                :value="climMin"
                type="number"
                step="any"
                class="cv-rb-input"
                @change="onClimInput('min', $event)"
              />
            </label>
            <label class="cv-rb-field">
              <span class="cv-rb-label">{{ t('maskMaker.display.contrastMax') }}</span>
              <input
                :value="climMax"
                type="number"
                step="any"
                class="cv-rb-input"
                @change="onClimInput('max', $event)"
              />
            </label>
          </template>
          <button
            type="button"
            class="cv-rb-apply"
            :disabled="!displayFilePath"
            @click="reloadDisplay"
          >
            {{ applyLabel }}
          </button>
        </div>

        <CalibCanvas
          :image-src="imageSrc"
          :image-width="imageWidth"
          :image-height="imageHeight"
          :rings="rings"
          :peaks="peaks"
          :interactive="step === 'peaks'"
          :ring-guide="ringGuide"
          :ring-fit="ringFit"
          :mask-overlay="maskOverlay"
          :beam-center="refinedBeamCenter"
          @canvas-click="onCanvasClick"
          @canvas-remove="onCanvasRemove"
          @canvas-dblclick="onCanvasDblClick"
        />
        <div v-if="imageSrc" class="cv-canvas-legend">
          <span class="cv-legend-item">{{ t('calibration.canvas.peaks') }}: {{ peaks.length }}</span>
          <span class="cv-legend-item">{{ t('calibration.canvas.rings') }}: {{ rings.length }}</span>
          <span v-if="step === 'peaks'" class="cv-legend-item">{{ guideCountLabel }}</span>
          <span
            v-if="refinedBeamCenter"
            class="cv-legend-item cv-legend-item--center"
            :title="beamCenterLegendTitle"
          >
            {{ beamCenterLegendLabel }}
          </span>
          <span v-if="maskRatioLabel" class="cv-legend-item cv-legend-item--mask">{{ maskRatioLabel }}</span>
        </div>
        <!-- Per-ring peak color legend (matches canvas markers + summary table) /
             每环峰色图例（与画布标记、汇总表同色）。 -->
        <div v-if="step === 'peaks' && ringChips.length > 0" class="cv-ring-legend">
          <span
            v-for="chip in ringChips"
            :key="chip.ring"
            class="cv-ring-chip"
          >
            <span class="cv-ring-chip-dot" :style="{ background: chip.color }" />
            {{ chip.label }} ×{{ chip.count }}
          </span>
        </div>

        <!-- ===== Calibrant integration preview (step 3, calib2 Integration-task
             parity): 1-D curve + 2-D cake under the CURRENT refined geometry;
             auto-refreshed after every refine. / 标定图积分预览（第 3 步）：
             以当前精修几何做 1D 曲线 + 2D cake，每次精修后自动刷新。 ===== -->
        <div v-if="step === 'refine'" class="cv-integ-preview">
          <div class="cv-integ-head">
            <h3 class="cv-integ-title">{{ integTitleLabel }}</h3>
            <span v-if="integLoading" class="cv-integ-loading">{{ integLoadingLabel }}</span>
            <span v-else-if="integError" class="cv-integ-error">{{ integError }}</span>
            <span v-else-if="integ1d" class="cv-integ-meta">{{ integMetaLabel }}</span>
          </div>
          <div v-if="integ1d || integ2d" class="cv-integ-grid">
            <div class="cv-integ-cell">
              <PlotlyChart
                :data="integ1dTraces"
                :layout="integ1dLayout"
                :dark-mode="true"
                class="cv-integ-chart"
              />
            </div>
            <div class="cv-integ-cell">
              <PlotlyChart
                :data="integ2dTraces"
                :layout="integ2dLayout"
                :dark-mode="true"
                class="cv-integ-chart"
              />
            </div>
          </div>
        </div>
      </div>

      <!-- ===== Right: results column / 右侧：结果列 ===== -->
      <aside class="cv-results">
        <div class="cv-card">
          <div class="cv-info-grid">
            <span class="cv-info-label">{{ t('calibration.setup.imageFile') }}</span>
            <span class="cv-info-value">{{ imageFileName || '—' }}</span>
            <span class="cv-info-label">{{ t('calibration.setup.calibrant') }}</span>
            <span class="cv-info-value">{{ calibrantLabel || '—' }}</span>
            <span class="cv-info-label">{{ t('calibration.setup.detector') }}</span>
            <span class="cv-info-value">{{ detectorLabel }}</span>
            <span class="cv-info-label">{{ t('calibration.setup.wavelength') }}</span>
            <span class="cv-info-value">{{ setupForm.wavelengthA }} Å</span>
          </div>
        </div>

        <div v-if="chi2 != null" class="cv-card">
          <div class="cv-info-grid">
            <span class="cv-info-label">{{ t('calibration.refine.chi2') }}</span>
            <span class="cv-info-value">{{ chi2.toExponential(4) }}</span>
            <span class="cv-info-label">{{ t('calibration.refine.centerX') }}</span>
            <span class="cv-info-value">{{ formatPx(geometry?.centerXPx) }}</span>
            <span class="cv-info-label">{{ t('calibration.refine.centerY') }}</span>
            <span class="cv-info-value">{{ formatPx(geometry?.centerYPx) }}</span>
          </div>
        </div>
      </aside>
    </div>

    <!-- Export dialog / 导出对话框 -->
    <CalibExportDialog
      :open="exportDialogOpen"
      :result="exportResult"
      :saving="exporting"
      @close="exportDialogOpen = false"
      @save="handleExportPoni"
      @go-integrate="goIntegrate"
    />
  </section>
</template>

<script setup lang="ts">
/**
 * CalibrationView.vue — pyFAI 标定向导（Setup → 峰拾取 → 精化 → 导出）
 * Calibration wizard (Setup → Peak picking → Refine → Export).
 *
 * All backend work goes through `transport.submitTask('calibration', { action, ... })`;
 * the calibrant image is rendered for display via the `viewer_config` open_file
 * flow (binary PNG frame → blob URL), mirroring ViewerView / MaskMakerView.
 */
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useToast } from '@/lib/toast'
import { useTransport } from '@/lib/transport'
import { COLORMAP_PRESETS } from '@/lib/chart-utils'
import { clearWorkspace, reportWorkspace } from '@/lib/workspace-state'

import CalibCanvas from '@/components/calibration/CalibCanvas.vue'
import type { CalibPeak, CalibRing, CalibRingFit, CalibMaskOverlay } from '@/components/calibration/CalibCanvas.vue'
import { calibPeakRingColor } from '@/components/calibration/CalibCanvas.vue'
import CalibSetupForm from '@/components/calibration/CalibSetupForm.vue'
import type { CalibSetupModel, CalibSetupPayload, CalibProbeInfo } from '@/components/calibration/CalibSetupForm.vue'
import CalibPeakPanel from '@/components/calibration/CalibPeakPanel.vue'
import CalibRefinePanel from '@/components/calibration/CalibRefinePanel.vue'
import type { CalibFreeFlags, CalibGeometry, CalibResidualPoint } from '@/components/calibration/CalibRefinePanel.vue'
import CalibExportDialog from '@/components/calibration/CalibExportDialog.vue'
import type { CalibExportResult, CalibCitation } from '@/components/calibration/CalibExportDialog.vue'
import PlotlyChart from '@/components/charts/PlotlyChart.vue'
import type { PlotData, PlotLayout } from 'plotly.js-dist-min'

// === Wizard steps / 向导步骤 ===

type CalibStep = 'setup' | 'peaks' | 'refine' | 'export'

const STEPS: Array<{ key: CalibStep; labelKey: string }> = [
  { key: 'setup', labelKey: 'calibration.setup.load' },
  { key: 'peaks', labelKey: 'calibration.peaks.title' },
  { key: 'refine', labelKey: 'calibration.refine.title' },
  { key: 'export', labelKey: 'calibration.export.title' },
]

const { t, locale } = useI18n()
const toast = useToast()
const transport = useTransport()
const router = useRouter()

/** Stepper label: step 3 was RENAMED (精修中心位点 / Refine center & geometry —
 *  inline bilingual, no i18n key yet); other steps keep their keys.
 *  步骤条文案：第 3 步已改名（内联双语，暂无 i18n 键）；其余沿用现有键。 */
function stepLabel(s: { key: CalibStep; labelKey: string }): string {
  if (s.key === 'refine') return isZh.value ? '精修中心位点' : 'Refine center & geometry'
  return t(s.labelKey)
}

// === State / 状态 ===

const step = ref<CalibStep>('setup')
const stepIndex = computed(() => STEPS.findIndex(s => s.key === step.value))
/** Highest step index unlocked by a completed action. */
const maxStep = ref(0)

/** True after a successful 'setup' action — required by every later action. */
const sessionActive = ref(false)
/**
 * Backend calibration session id returned by 'setup' — required by EVERY
 * session action (detect_peaks / pick_peak / ring_pick / update_peaks /
 * refine / ring_overlay / export_poni). BUG D fix (完成环选报
 * "sessionId not found or expired: None"): the wizard never captured this id
 * from the setup result and no action attached it, so every session action
 * hit the backend with sessionId=None and was rejected — ring_pick/pick_peak
 * died silently after harvest, which is also why one ring pick could never
 * yield multiple peaks. / 后端标定会话 id（setup 返回）——所有会话 action 都
 * 必须携带。此前前端从未保存该 id，所有会话 action 均以 sessionId=None 被
 * 后端拒绝（环选报 “sessionId not found or expired: None”），环选因此一次
 * 也收不到峰。
 */
const sessionId = ref<string | null>(null)

const calibrants = ref<string[]>([])
const detectors = ref<string[]>([])
const probeResult = ref<CalibProbeInfo | null>(null)
const probing = ref(false)
const setupLoading = ref(false)
const setupForm = ref<CalibSetupModel>({
  imagePath: '',
  calibrant: '',
  calibrantPath: '',
  detector: '',
  pixelSizeUm: 172,
  wavelengthA: 1.5418,
  distGuessMm: 200,
  maskPath: '',
  maskMin: null,
  maskMax: null,
})
/** Beam center (px) from seed_from_poni; forwarded with the setup payload. */
const seededCenter = ref<{ x: number; y: number } | null>(null)

// === Mask state (REQ 1) / 掩膜状态 ===
/**
 * Coarse session-mask grid from the setup response — drawn by CalibCanvas as
 * translucent red tiles at every step. / setup 返回的会话掩膜粗网格，画布
 * 每一步都以半透明红块绘制。
 */
const maskOverlay = ref<CalibMaskOverlay | null>(null)
/** Pixel-level mask statistics from the setup response. / 像素级掩膜统计。 */
const maskStats = ref<{ maskedPixels: number; ratio: number } | null>(null)
/** Mask inputs applied by the last successful setup (staleness reference). */
let appliedMaskSig: string | null = null

/** Current mask inputs, serialized — compared against appliedMaskSig. */
const maskSignature = computed(() =>
  JSON.stringify([setupForm.value.maskPath.trim(), setupForm.value.maskMin, setupForm.value.maskMax]),
)

/**
 * REQ 1 “应用 mask”: changing any mask input after the session started marks
 * the setup stale — a badge shows on the form and Next stays disabled until
 * the user re-runs 载入并开始 (the same setup action re-applies the mask and
 * refreshes the overlay). Chosen over auto re-setup: no surprise backend calls
 * while typing in the bound inputs.
 * mask 任一输入在会话建立后变化即标记过期：表单显示徽标、下一步禁用，直到
 * 重新“载入并开始”（同一 setup 动作重新应用掩膜并刷新叠加）。相比自动重跑
 * setup，此方式不会在输入框打字途中意外触发后端调用。
 */
const maskStale = computed(() => sessionActive.value && maskSignature.value !== appliedMaskSig)

// Display image state (mask_maker load_preview open flow) / 显示图像状态
const imageSrc = ref<string | null>(null)
const imageWidth = ref(0)
const imageHeight = ref(0)
const imageFileName = ref('')
/** Path of the image currently shown — settings changes re-render it. */
const displayFilePath = ref('')
/**
 * ORIGINAL frame dimensions (from load_preview's metadata, which reports the
 * pre-downsample size). PERFORMANCE (大图响应过慢): the rendered preview PNG is
 * capped to ≤1600 px on its longest side, so contrast/colormap tweaks re-render
 * a much smaller texture while imageWidth/Height (the overlay coordinate space
 * and zoom-fit reference) stay at the true frame size. CalibCanvas stretches
 * the capped PNG back to the original dims via explicit CSS sizing.
 * 原始帧尺寸（来自 load_preview 元数据，为降采样前的尺寸）。性能：预览 PNG
 * 最长边限制 ≤1600px，对比度/色图调整只需重渲染小纹理；imageWidth/Height
 * （叠加层坐标系与适配缩放基准）保持真实尺寸，画布按 CSS 尺寸拉伸回原尺寸。
 */
const origImageSize = ref<{ w: number; h: number } | null>(null)
const PREVIEW_MAX_PX = 1600

// Render settings (colormap / log / clim) — mirrors MaskMakerView exactly.
// The `mask_maker` load_preview action re-renders the preview PNG honoring
// these via the backend's _build_render_settings, so changing them simply
// re-submits the same load. / 渲染设置（色图/对数/clim）—— 与 MaskMakerView 完全一致。
const colormap = ref('smooth_WAXS_foxtrot')
const useLog = ref(true)
const climMode = ref<'auto' | 'manual'>('auto')
const climMin = ref(0)
// Default upper bound follows int32 — detector data may exceed uint16.
// 默认上限按 int32 设置 —— 探测器数据可能超过 uint16 范围。
const climMax = ref(2147483647)
const autoContrast = ref<{ autoMin: number; autoMax: number; logMin: number; logMax: number } | null>(null)
const climInitialized = ref(false)

// Same option list as MaskProperties / the viewer. / 与 MaskProperties 一致的色图选项。
const colormapOptions = [
  'smooth_WAXS_foxtrot',
  'smooth_WAXS_fit2D',
  ...Object.keys(COLORMAP_PRESETS),
]

// Peak state / 峰状态
const peaks = ref<CalibPeak[]>([])
const sensitivity = ref(0.5)
const detecting = ref(false)
const rings = ref<CalibRing[]>([])

// REQ 2: ring-by-ring picking — the CURRENT ring number (calib2-style 1-based
// UI; sent to the backend as the 0-based assignRing = currentRing - 1).
// Canvas clicks ALWAYS collect guide points for this ring; 完成本环 harvests
// it and the spinner auto-advances to max(existing)+1.
// 逐一环选：当前环号（界面 1 起；发往后端时换算为 0 起的 assignRing）。
// 画布点击始终为该环收集引导点；完成本环收环后自动跳到 max+1。
const currentRing = ref(1)

// calib2-parity extraction options (STEP 0 study of pyFAI PeakPickingTask.py).
// calib2 对标的提取选项（对 PeakPickingTask.py 的源码调研）。
/** "Extract peaks, beyond masked values" — calib2 Ring tool (line 1247). */
const beyondMask = ref(false)
/** "Remove a set of already identified peaks" — calib2 Rubber tool (line 1281),
 *  applied to the extraction region before merging harvested peaks. */
const removeExisting = ref(false)
/** 刷新环号/自检 in flight. */
const refreshingRings = ref(false)

// Ring-guide points (owned here; drawn by CalibCanvas) / 环引导点
const ringGuide = ref<Array<{ y: number; x: number }>>([])
const ringPicking = ref(false)

// Refine state / 精化状态
// Defaults mirror the backend _DEFAULT_FREE: distance + beam centre free,
// rot1–3 fixed (lab detectors sit near-normal; freeing tilts with few rings
// degenerates the fit), wavelength fixed (known source).
// 默认与后端一致：距离/中心自由，rot1–3 固定，波长固定。
const freeFlags = ref<CalibFreeFlags>({
  dist: true,
  poni1: true,
  poni2: true,
  rot1: false,
  rot2: false,
  rot3: false,
  wavelength: false,
})
const refining = ref(false)
const chi2 = ref<number | null>(null)
const geometry = ref<CalibGeometry | null>(null)
const residuals = ref<CalibResidualPoint[]>([])
const converged = ref<boolean | null>(null)

// Export state / 导出状态
const exportDialogOpen = ref(false)
const exporting = ref(false)
const exportResult = ref<CalibExportResult | null>(null)

// Publish progress to the workspace-state bridge for the AI guided tour
// (Jev build). filesCount here = calibrant image loaded (session active).
// 向状态桥上报进度供教学模式使用；filesCount 此处表示标样图像已加载。
watch(
  [step, sessionActive, rings, geometry, exportResult],
  () => {
    reportWorkspace('calibration', {
      filesCount: sessionActive.value ? 1 : 0,
      hasPoni: exportResult.value !== null,
      canRun: sessionActive.value,
      phase: 'idle',
      extras: {
        ringsCount: rings.value.length,
        refined: geometry.value !== null,
        exported: exportResult.value !== null,
      },
    })
  },
  { immediate: true, deep: true }
)
onUnmounted(() => clearWorkspace('calibration'))

// === Task helper (submit → single result/error, PoniImporterView idiom) ===

function submitAndWait(route: string, params: Record<string, unknown>): Promise<Record<string, unknown>> {
  return new Promise((resolve, reject) => {
    transport.submitTask(route, params).then(response => {
      let offResult: (() => void) | null = null
      let offError: (() => void) | null = null
      let settled = false
      const finish = (fn: () => void): void => {
        if (settled) return
        settled = true
        offResult?.()
        offError?.()
        fn()
      }
      offResult = transport.onTaskResult(response.taskId, p => finish(() => resolve(p.data as Record<string, unknown>)))
      offError = transport.onTaskError(response.taskId, p => finish(() => reject(new Error(p.error))))
    }).catch(reject)
  })
}

function toastError(title: string, err: unknown, fallback: string): void {
  const message = err instanceof Error && err.message ? err.message : fallback
  toast.push({ title, message, tone: 'error' })
}

/**
 * Build the payload of a SESSION action — always carries the current
 * sessionId (the backend rejects session actions without it). All of
 * detect_peaks / pick_peak / ring_pick / update_peaks / refine /
 * ring_overlay / export_poni must go through here.
 * 构造会话 action 的载荷——始终携带当前 sessionId（后端据此查会话）。
 */
function sessionPayload(action: string, extra: Record<string, unknown> = {}): Record<string, unknown> {
  return { action, sessionId: sessionId.value, ...extra }
}

// === Normalization helpers (defensive backend payload parsing) ===

function numberOrNull(v: unknown): number | null {
  return typeof v === 'number' && Number.isFinite(v) ? v : null
}

function stringOrNull(v: unknown): string | null {
  return typeof v === 'string' && v.trim() ? v : null
}

function normalizeStringList(raw: unknown): string[] {
  if (!Array.isArray(raw)) return []
  return raw
    .map(item => typeof item === 'string'
      ? item
      : stringOrNull((item as Record<string, unknown> | null)?.name))
    .filter((s): s is string => Boolean(s))
}

/** Peaks: [{y,x,ring,dtheta_deg,suspect}] objects or [y,x(,ring)] tuples.
 *  ring stays null when absent — an unassigned peak must NOT silently become
 *  ring 0 (the innermost ring) before the backend assigns it. */
function normalizePeaks(raw: unknown): CalibPeak[] {
  if (!Array.isArray(raw)) return []
  const out: CalibPeak[] = []
  for (const item of raw) {
    if (Array.isArray(item)) {
      const y = numberOrNull(item[0])
      const x = numberOrNull(item[1])
      const ring = numberOrNull(item[2])
      if (y != null && x != null) out.push({ y, x, ring })
    } else if (item && typeof item === 'object') {
      const o = item as Record<string, unknown>
      const y = numberOrNull(o.y ?? o.row)
      const x = numberOrNull(o.x ?? o.col)
      const ring = numberOrNull(o.ring)
      if (y != null && x != null) {
        out.push({
          y,
          x,
          ring,
          dthetaDeg: numberOrNull(o.dtheta_deg ?? o.dthetaDeg),
          suspect: o.suspect === true,
        })
      }
    }
  }
  return out
}

/** Rings: [{ring, points: [y,x][]}] or bare polyline arrays. */
function normalizeRings(raw: unknown): CalibRing[] {
  if (!Array.isArray(raw)) return []
  const out: CalibRing[] = []
  raw.forEach((item, idx) => {
    if (Array.isArray(item)) {
      out.push({ ring: idx, points: item.filter(Array.isArray) as number[][] })
    } else if (item && typeof item === 'object') {
      const o = item as Record<string, unknown>
      const pts = Array.isArray(o.points) ? (o.points.filter(Array.isArray) as number[][]) : []
      out.push({ ring: numberOrNull(o.ring) ?? idx, points: pts })
    }
  })
  return out.filter(r => r.points.length > 1)
}

/** Geometry: accepts display-unit fields or pyFAI SI units (m / rad). */
function normalizeGeometry(raw: unknown): CalibGeometry | null {
  if (!raw || typeof raw !== 'object') return null
  const o = raw as Record<string, unknown>
  const pick = (...keys: string[]): unknown => {
    for (const k of keys) {
      if (o[k] !== undefined && o[k] !== null) return o[k]
    }
    return null
  }
  const scale = (v: unknown, factor: number): number | null => {
    const n = numberOrNull(v)
    return n == null ? null : n * factor
  }
  const m2mm = (v: unknown): number | null => scale(v, 1000)
  const m2A = (v: unknown): number | null => scale(v, 1e10)
  const rad2deg = (v: unknown): number | null => scale(v, 180 / Math.PI)

  const result: CalibGeometry = {
    distMm: numberOrNull(pick('dist_mm', 'distance_mm')) ?? m2mm(pick('dist', 'distance')),
    poni1Mm: numberOrNull(pick('poni1_mm')) ?? m2mm(pick('poni1')),
    poni2Mm: numberOrNull(pick('poni2_mm')) ?? m2mm(pick('poni2')),
    rot1Deg: numberOrNull(pick('rot1_deg')) ?? rad2deg(pick('rot1')),
    rot2Deg: numberOrNull(pick('rot2_deg')) ?? rad2deg(pick('rot2')),
    rot3Deg: numberOrNull(pick('rot3_deg')) ?? rad2deg(pick('rot3')),
    wavelengthA: numberOrNull(pick('wavelength_a')) ?? m2A(pick('wavelength')),
    centerXPx: numberOrNull(pick('center_x', 'centerX')),
    centerYPx: numberOrNull(pick('center_y', 'centerY')),
  }
  return result
}

/** Residuals: [{ring, delta_deg}] points or parallel arrays {ring[], delta_deg[]}. */
function normalizeResiduals(raw: unknown): CalibResidualPoint[] {
  if (Array.isArray(raw)) {
    const out: CalibResidualPoint[] = []
    for (const item of raw) {
      if (Array.isArray(item)) {
        const ring = numberOrNull(item[0])
        const d = numberOrNull(item[1])
        if (ring != null && d != null) out.push({ ring, deltaDeg: d })
      } else if (item && typeof item === 'object') {
        const o = item as Record<string, unknown>
        const ring = numberOrNull(o.ring ?? o.ring_index)
        const d = numberOrNull(o.delta_deg ?? o.deltaDeg ?? o.delta)
        if (ring != null && d != null) out.push({ ring, deltaDeg: d })
      }
    }
    return out
  }
  if (raw && typeof raw === 'object') {
    const o = raw as Record<string, unknown>
    const ringArr = Array.isArray(o.ring) ? o.ring : (Array.isArray(o.rings) ? o.rings : null)
    const deltaArr = Array.isArray(o.delta_deg) ? o.delta_deg
      : (Array.isArray(o.deltaDeg) ? o.deltaDeg : (Array.isArray(o.delta) ? o.delta : null))
    if (ringArr && deltaArr) {
      const out: CalibResidualPoint[] = []
      for (let i = 0; i < Math.min(ringArr.length, deltaArr.length); i++) {
        const ring = numberOrNull(ringArr[i])
        const d = numberOrNull(deltaArr[i])
        if (ring != null && d != null) out.push({ ring, deltaDeg: d })
      }
      return out
    }
  }
  return []
}

function normalizeCitation(raw: unknown): CalibCitation | null {
  if (!raw || typeof raw !== 'object') return null
  const o = raw as Record<string, unknown>
  const toUrl = (v: unknown): string | undefined => {
    const s = stringOrNull(v)
    if (!s) return undefined
    return s.startsWith('http') ? s : `https://doi.org/${s}`
  }
  return {
    calib2Url: toUrl(o.calib2Url ?? o.calib2 ?? o.calib2_doi),
    pyfaiUrl: toUrl(o.pyfaiUrl ?? o.pyfai ?? o.pyfai_doi),
    note: stringOrNull(o.note) ?? undefined,
  }
}

// === Step navigation / 步骤导航 ===

function unlockStep(index: number): void {
  if (index > maxStep.value) maxStep.value = index
}

function goStep(target: CalibStep): void {
  const idx = STEPS.findIndex(s => s.key === target)
  if (idx < 0 || idx > maxStep.value) return
  // Entering refine requires at least one peak.
  if (target === 'refine' && peaks.value.length === 0) {
    toast.push({
      title: t('calibration.refine.title'),
      message: t('calibration.refine.needPeaks'),
      tone: 'warning',
    })
    return
  }
  step.value = target
}

/**
 * Next is enabled only when the CURRENT step is complete:
 * setup = session created AND the mask inputs are applied (not stale);
 * peaks = ≥4 peaks; refine = a finished refine run.
 * 下一步仅在当前步骤完成时可用：setup=会话已建且掩膜输入已应用（未过期）；
 * peaks=≥4 峰；refine=精化完成。
 */
const canGoNext = computed<boolean>(() => {
  switch (step.value) {
    case 'setup': return sessionActive.value && !maskStale.value
    case 'peaks': return peaks.value.length >= 4
    case 'refine': return chi2.value != null
    default: return false
  }
})

function goPrev(): void {
  const idx = stepIndex.value
  if (idx > 0) step.value = STEPS[idx - 1].key
}

function goNext(): void {
  if (!canGoNext.value) return
  const idx = stepIndex.value
  if (idx < 0 || idx >= STEPS.length - 1) return
  unlockStep(idx + 1)
  step.value = STEPS[idx + 1].key
}

// No existing i18n keys for the wizard nav buttons — inline bilingual for now.
// 向导导航按钮暂无 i18n 键 —— 内联双语（见最终报告缺失键清单）。
const isZh = computed(() => locale.value.startsWith('zh'))
const prevLabel = computed(() => (isZh.value ? '上一步' : 'Back'))
const nextLabel = computed(() => (isZh.value ? '下一步' : 'Next'))
const guideCountLabel = computed(() =>
  `${isZh.value ? '引导点' : 'guide pts'}: ${ringGuide.value.length}`,
)

// === Calibrant list / 校准物列表 ===

onMounted(() => {
  void loadCalibrants()
  void loadDetectors()
  window.addEventListener('keydown', onKeydown)
})

async function loadCalibrants(): Promise<void> {
  try {
    const data = await submitAndWait('calibration', { action: 'list_calibrants' })
    calibrants.value = normalizeStringList(data.calibrants ?? data.names ?? data)
  } catch {
    // Non-fatal: the user can still supply a .D file manually.
    // 非致命错误：用户仍可手动提供 .D 文件。
  }
}

async function loadDetectors(): Promise<void> {
  try {
    const data = await submitAndWait('calibration', { action: 'list_detectors' })
    detectors.value = normalizeStringList(data.detectors ?? data.names ?? data)
  } catch {
    // Non-fatal: the manual pixel-size input remains available.
    // 非致命错误：仍可手动输入像素尺寸。
  }
}

/**
 * probe_image result pushed down into CalibSetupForm: auto-selects a recognized
 * detector or prefills the pixel size. Best-effort — never blocks the wizard.
 * 探测结果下发到表单：自动选择识别出的探测器或预填像素尺寸；尽力而为，不阻塞向导。
 */
async function handleProbed(imagePath: string): Promise<void> {
  const path = imagePath.trim()
  if (!path) {
    probeResult.value = null
    return
  }
  // BUG A fix (导入图像后内置标样下拉无法选择): the built-in calibrant /
  // detector dropdown options come from one-shot fetches in onMounted. On
  // desktop the embedded Python service is often still starting when the
  // wizard first opens → those fetches fail silently → the <select> keeps a
  // single "—" option and nothing can be chosen. Picking an image proves the
  // backend is now reachable, so backfill any still-empty registry list right
  // here — the dropdown becomes usable exactly when the user needs it.
  // 修复：标样/探测器下拉的选项来自 onMounted 的一次性拉取；桌面端 Python
  // 服务未就绪时拉取静默失败，下拉只剩 “—” 无法选择。选图即证明后端可达，
  // 在此补拉仍为空的列表，使图像导入后下拉立即可用。
  if (calibrants.value.length === 0) void loadCalibrants()
  if (detectors.value.length === 0) void loadDetectors()
  // Auto-load on image pick: show the picture from the moment of selection —
  // no need to click 载入并开始 first (that button only creates the session).
  // 选图即显示：无需先点“载入并开始”（该按钮仅创建标定会话）。
  if (displayFilePath.value !== path) {
    imageFileName.value = path.split(/[/\\]/).pop() ?? path
    // Fresh file → reset display caches so its auto-contrast seeds the clim bar.
    // 新文件 → 重置显示缓存，使自动对比度作为 clim 初值。
    climInitialized.value = false
    autoContrast.value = null
    origImageSize.value = null
    void loadDisplayImage(path).catch(() => {
      // Render failures surface via the onTaskError toast; the wizard continues.
      // 渲染失败已由 onTaskError 提示；向导仍可继续。
    })
  }
  probing.value = true
  try {
    const data = await submitAndWait('calibration', { action: 'probe_image', filePath: path })
    probeResult.value = {
      imagePath: path,
      detector: stringOrNull(data.detector),
      pixelSizeUm: numberOrNull(data.pixelSizeUm ?? data.pixel_size_um ?? data.pixel_um),
    }
  } catch {
    probeResult.value = null
  } finally {
    probing.value = false
  }
}

// === Setup / 加载 ===

async function handleSetup(payload: CalibSetupPayload): Promise<void> {
  setupLoading.value = true
  try {
    const data = await submitAndWait('calibration', {
      action: 'setup',
      filePath: payload.filePath,
      calibrant: payload.calibrant,
      calibrantFile: payload.calibrantFile,
      detector: payload.detector,
      pixelSizeUm: payload.pixelSizeUm,
      wavelengthA: payload.wavelengthA,
      distGuessMm: payload.distGuessMm,
      // REQ 1: mask file + intensity bounds → session mask + overlay.
      maskPath: payload.maskPath,
      maskMin: payload.maskMin,
      maskMax: payload.maskMax,
      ...(seededCenter.value ? { centerX: seededCenter.value.x, centerY: seededCenter.value.y } : {}),
    })
    // The backend hands back the session id every later action must carry.
    // 后端返回会话 id，后续所有会话 action 都必须携带。
    const sid = stringOrNull(data.sessionId)
    if (!sid) throw new Error('setup returned no sessionId / setup 未返回 sessionId')
    sessionId.value = sid

    sessionActive.value = true
    resetSessionResults()
    // Mask response: stats for the legend, coarse grid for the canvas overlay.
    // 掩膜响应：统计进图例，粗网格进画布叠加。
    const stats = data.maskStats as { maskedPixels?: unknown; ratio?: unknown } | null | undefined
    maskStats.value = stats && typeof stats === 'object'
      ? {
          maskedPixels: numberOrNull(stats.maskedPixels) ?? 0,
          ratio: numberOrNull(stats.ratio) ?? 0,
        }
      : null
    const overlay = data.maskOverlay as { rows?: unknown; cols?: unknown; grid?: unknown } | null | undefined
    const overlayRows = numberOrNull(overlay?.rows)
    const overlayCols = numberOrNull(overlay?.cols)
    const overlayGrid = Array.isArray(overlay?.grid) ? overlay!.grid : null
    maskOverlay.value = overlay && overlayRows != null && overlayCols != null && overlayGrid
      ? { rows: overlayRows, cols: overlayCols, grid: overlayGrid.filter(n => n === 0 || n === 1) as number[] }
      : null
    appliedMaskSig = maskSignature.value
    imageFileName.value = payload.filePath.split(/[/\\]/).pop() ?? payload.filePath

    toast.push({
      title: t('calibration.title'),
      message: t('calibration.setup.loadOk'),
      tone: 'success',
    })

    // Load the SAME image for display (mask_maker load_preview flow, binary PNG).
    // 加载同一图像用于显示（mask_maker load_preview 流程，二进制 PNG）。
    // The pick auto-load usually already displayed this file; only (re)load and
    // reset the clim caches when the setup path differs from what is on screen.
    // 选图自动加载通常已显示该文件；仅当 setup 路径与当前显示不同才重新加载。
    if (displayFilePath.value !== payload.filePath) {
      climInitialized.value = false
      autoContrast.value = null
      origImageSize.value = null
      await loadDisplayImage(payload.filePath)
    }

    unlockStep(1)
    step.value = 'peaks'
  } catch (err) {
    toastError(t('calibration.title'), err, t('calibration.errors.loadFailed'))
  } finally {
    setupLoading.value = false
  }
}

/** Clear peaks/results from a previous session before a new setup. */
function resetSessionResults(): void {
  peaks.value = []
  rings.value = []
  currentRing.value = 1
  ringGuide.value = []
  maskOverlay.value = null
  maskStats.value = null
  chi2.value = null
  geometry.value = null
  residuals.value = []
  converged.value = null
  exportResult.value = null
}

async function handleSeedFromPoni(poniPath: string): Promise<void> {
  try {
    const data = await submitAndWait('calibration', { action: 'seed_from_poni', filePath: poniPath })
    const patch: Partial<CalibSetupModel> = {}
    const distMm = numberOrNull(data.dist_mm) ?? numberOrNull(data.distance_mm)
    const wavelengthA = numberOrNull(data.wavelength_a)
    const pixelUm = numberOrNull(data.pixel_um) ?? numberOrNull(data.pixel_size_um)
    if (distMm != null) patch.distGuessMm = distMm
    if (wavelengthA != null) patch.wavelengthA = wavelengthA
    if (pixelUm != null) {
      patch.pixelSizeUm = pixelUm
      // An explicit pixel size from the PONI overrides the detector preset.
      // PONI 提供的像素尺寸优先于探测器预设。
      patch.detector = ''
    }
    if (patch.distGuessMm != null || patch.wavelengthA != null || patch.pixelSizeUm != null) {
      setupForm.value = { ...setupForm.value, ...patch }
    }
    const cx = numberOrNull(data.center_x ?? data.centerX)
    const cy = numberOrNull(data.center_y ?? data.centerY)
    if (cx != null && cy != null) {
      seededCenter.value = { x: cx, y: cy }
    }
  } catch (err) {
    toastError(t('calibration.title'), err, t('calibration.errors.loadFailed'))
  }
}

// === Display image (mask_maker load_preview) / 显示图像 ===

let cleanupDisplayBinary: (() => void) | null = null
let cleanupDisplayResult: (() => void) | null = null
let cleanupDisplayError: (() => void) | null = null

/** Exactly MaskMakerView.buildRenderSettings — consumed by the backend renderer.
 *  PERFORMANCE: preview_scale caps the rendered PNG at ≤1600 px on the longest
 *  side for large frames (backend: data[::step, ::step] before PNG encoding),
 *  so contrast tweaks stay snappy on 大图; unknown size (first load) renders
 *  full-size once and records the true dims from the result metadata. */
function buildRenderSettings(): Record<string, unknown> {
  const resolvedClim = climMode.value === 'manual'
    ? [climMin.value, climMax.value]
    : [
        useLog.value ? autoContrast.value?.logMin ?? 1e-6 : autoContrast.value?.autoMin ?? 0,
        useLog.value ? autoContrast.value?.logMax ?? 1 : autoContrast.value?.autoMax ?? 1,
      ]
  const longest = origImageSize.value ? Math.max(origImageSize.value.w, origImageSize.value.h) : 0
  const previewScale = longest > PREVIEW_MAX_PX ? PREVIEW_MAX_PX / longest : 1.0
  return {
    colormap: colormap.value,
    use_log: useLog.value,
    clim_mode: climMode.value,
    clim: resolvedClim,
    preview_scale: previewScale,
  }
}

function cleanupDisplayListeners(): void {
  cleanupDisplayBinary?.()
  cleanupDisplayBinary = null
  cleanupDisplayResult?.()
  cleanupDisplayResult = null
  cleanupDisplayError?.()
  cleanupDisplayError = null
}

/**
 * Load the calibrant image for display — EXACT mirror of MaskMakerView.loadImage,
 * the proven-working viewer pipeline: `mask_maker` + `load_preview` action with
 * `settings`, PNG delivered as a binary WebSocket frame → blob URL, base64
 * fallback in the result, auto-contrast captured for the clim bar.
 * 加载标定图像 —— 逐字镜像 MaskMakerView.loadImage 的可用路径。
 */
async function loadDisplayImage(filePath: string): Promise<void> {
  cleanupDisplayListeners()

  const { taskId } = await transport.submitTask('mask_maker', {
    action: 'load_preview',
    filePath,
    frame: 0,
    settings: buildRenderSettings(),
  })
  displayFilePath.value = filePath

  // Receive PNG image as binary data (desktop binary WebSocket frame).
  // 通过二进制数据通道接收 PNG 图像（桌面端二进制 WebSocket 帧）。
  // NOTE: payload.width/height are the RENDERED (possibly capped) PNG dims —
  // the overlay coordinate space must use the ORIGINAL frame size instead
  // (set from the result metadata below), or peaks/rings would misalign.
  // 注意：payload 的宽高是渲染后（可能已限幅）的 PNG 尺寸——叠加层坐标系必须
  // 用原始帧尺寸（由下方结果元数据设置），否则环/峰会错位。
  cleanupDisplayBinary = transport.onTaskBinaryData(taskId, (payload) => {
    if (payload.data) {
      if (imageSrc.value?.startsWith('blob:')) URL.revokeObjectURL(imageSrc.value)
      const blob = new Blob([payload.data], { type: payload.mime || 'image/png' })
      imageSrc.value = URL.createObjectURL(blob)
    }
  })

  cleanupDisplayResult = transport.onTaskResult(taskId, (p) => {
    const data = (p.data ?? {}) as Record<string, unknown>

    // If the image was not set via binary data channel, fall back to base64.
    // Skip __binary_blob__ placeholders that indicate binary delivery.
    // 如果二进制通道未设置图像，回退到 base64；跳过二进制占位符。
    if (!imageSrc.value) {
      const previewB64 = data.previewB64
      const displayB64 = data.displayB64
      if (typeof previewB64 === 'string' && previewB64 !== '__binary_blob__') {
        imageSrc.value = `data:image/png;base64,${previewB64}`
      } else if (typeof displayB64 === 'string' && displayB64 !== '__binary_blob__') {
        imageSrc.value = `data:image/png;base64,${displayB64}`
      }
    }

    // ORIGINAL frame dims: metadata.width/height are captured before the
    // preview_scale downsampling; top-level width/height are post-downsample.
    // 原始帧尺寸：metadata 里的宽高在降采样之前记录；顶层宽高是降采样后的。
    const meta = data.metadata as { width?: unknown; height?: unknown } | undefined
    const origW = numberOrNull(meta?.width) ?? numberOrNull(data.origWidth)
    const origH = numberOrNull(meta?.height) ?? numberOrNull(data.origHeight)
    if (origW && origH) {
      origImageSize.value = { w: origW, h: origH }
      imageWidth.value = origW
      imageHeight.value = origH
    } else {
      const w = numberOrNull(data.width) ?? 0
      const h = numberOrNull(data.height) ?? 0
      if (w > 0 && h > 0 && !origImageSize.value) {
        origImageSize.value = { w, h }
        imageWidth.value = w
        imageHeight.value = h
      }
    }

    // Capture auto-contrast so the render bar can seed manual clim values and
    // keep auto-mode in sync. Mirrors MaskMakerView's result handler.
    // 捕获自动对比度，渲染条据此初始化手动值并保持 auto 模式同步。
    const contrast = data.contrast as { autoMin: number; autoMax: number; logMin: number; logMax: number } | undefined
    if (contrast) {
      autoContrast.value = contrast
      if (climMode.value === 'auto') {
        climMin.value = useLog.value ? contrast.logMin : contrast.autoMin
        climMax.value = useLog.value ? contrast.logMax : contrast.autoMax
      } else if (!climInitialized.value) {
        climMin.value = useLog.value ? contrast.logMin : contrast.autoMin
        climMax.value = useLog.value ? contrast.logMax : contrast.autoMax
        climInitialized.value = true
      }
    }
  })

  cleanupDisplayError = transport.onTaskError(taskId, (p) => {
    toast.push({ title: t('calibration.title'), message: p.error, tone: 'error' })
  })
}

// === Render settings bar / 渲染设置条 ===

/** Update a render field, then re-render the preview if an image is loaded. */
type RenderField = 'colormap' | 'useLog' | 'climMode'

function onRenderChange(field: RenderField, value: number | boolean | string): void {
  switch (field) {
    case 'colormap': colormap.value = String(value); break
    case 'useLog': useLog.value = Boolean(value); break
    case 'climMode': climMode.value = (value === 'manual' ? 'manual' : 'auto'); break
  }
  // Auto-mode syncs min/max from the backend's auto-contrast; in manual mode
  // we send the user's values verbatim (MaskMakerView.onDisplayChange idiom).
  if (climMode.value === 'auto' && autoContrast.value) {
    climMin.value = useLog.value ? autoContrast.value.logMin : autoContrast.value.autoMin
    climMax.value = useLog.value ? autoContrast.value.logMax : autoContrast.value.autoMax
  }
  if (displayFilePath.value) {
    void loadDisplayImage(displayFilePath.value)
  }
}

/** Manual clim inputs update state only — the Apply button re-renders. */
function onClimInput(bound: 'min' | 'max', e: Event): void {
  const num = parseFloat((e.target as HTMLInputElement).value)
  if (Number.isFinite(num)) {
    if (bound === 'min') climMin.value = num
    else climMax.value = num
  }
}

/** Apply button: re-render the current image with the pending settings. */
function reloadDisplay(): void {
  if (displayFilePath.value) void loadDisplayImage(displayFilePath.value)
}

// No existing i18n key for an "Apply" action — bilingual inline for now.
// 暂无现成 i18n 键 —— 内联双语（见最终报告的缺失键清单）。
const applyLabel = computed(() => (locale.value.startsWith('zh') ? '应用' : 'Apply'))

// === Peaks / 峰拾取 ===

async function handleAutoPeaks(): Promise<void> {
  if (!sessionActive.value) {
    toast.push({ title: t('calibration.title'), message: t('calibration.errors.noSession'), tone: 'error' })
    return
  }
  detecting.value = true
  try {
    const data = await submitAndWait('calibration', sessionPayload('detect_peaks', {
      sensitivity: sensitivity.value,
      beyondMask: beyondMask.value,
    }))
    // 高级：全图自动拾取 REPLACES the list, assigns theoretical rings via the
    // keep-mode push (all rings null → backend assigns), then re-groups the
    // table by ring. / 全图自动拾取整表替换，经 keep 推送分配理论环号后按环
    // 重新分组。
    peaks.value = normalizePeaks(data.peaks)
    pushPeaksUpdate()
  } catch (err) {
    toastError(t('calibration.title'), err, t('calibration.errors.loadFailed'))
  } finally {
    detecting.value = false
  }
}

function handleClearPeaks(): void {
  peaks.value = []
  // Explicit clear — tell the backend too. The backend now treats an EMPTY
  // peak list as a no-op clear (STEP 1 fix), so this can no longer produce
  // the old “peaks must be a non-empty list” error toast.
  // 显式清空——同步后端。后端已把空列表视为清空（STEP 1 修复），不再报错。
  pushPeaksUpdate({ allowEmpty: true })
}

// Monotonic sequence guarding stale update_peaks responses: a slow earlier
// push must not overwrite a newer local edit. / 递增序号防陈旧响应覆盖新编辑。
let peaksUpdateSeq = 0

/** Apply an update_peaks response (assigned rings + self-check fields).
 *  Stale responses (a newer push happened meanwhile) are dropped by the
 *  caller's seq guard. The table is (re-)grouped by ring: ascending ring
 *  numbers, unassigned peaks last. / 应用 update_peaks 响应（环号 + 自检
 *  字段），并按环号升序重新分组（未分配者居后）。 */
function applyPeaksResponse(data: Record<string, unknown>): void {
  if (!Array.isArray(data.peaks)) return
  peaks.value = sortPeaksByRing(normalizePeaks(data.peaks))
}

/** Group peaks by ring (ascending; unassigned last) — the peak table layout
 *  for the ring-by-ring workflow. / 按环分组排序（升序，未分配居后）。 */
function sortPeaksByRing(list: CalibPeak[]): CalibPeak[] {
  return [...list].sort((a, b) => {
    const ra = a.ring ?? Number.POSITIVE_INFINITY
    const rb = b.ring ?? Number.POSITIVE_INFINITY
    if (ra !== rb) return ra - rb
    return a.y - b.y || a.x - b.x
  })
}

/** Send the full peak list to the backend after any edit.
 *  Peaks are plain-cloned: reactive proxies cannot cross Electron's
 *  ipcRenderer.invoke structured clone (BUG C). 峰列表逐项浅拷贝为普通对象，
 *  Vue 代理无法通过 ipcRenderer.invoke 的结构化克隆。
 *
 *  STEP 1 fix: an EMPTY list is never sent through the normal path — the old
 *  unconditional push after 完成环选 (harvest could yield nothing) was the
 *  “peaks must be a non-empty list of {'y','x'}” error. Only an explicit
 *  clear (allowEmpty) reaches the backend, which now no-ops it.
 *  正常路径绝不发送空列表（原“完成环选”后无条件推送空列表正是报错根源）；
 *  仅显式清空才发送，且后端已容忍。
 *
 *  mode: 'keep' (default) honors the table's ring numbers (calib2 peak-table
 *  semantics — user edits survive); 'assign' re-derives every ring from the
 *  current geometry (刷新环号/自检 path). */
function pushPeaksUpdate(opts: { mode?: 'assign' | 'keep'; allowEmpty?: boolean } = {}): void {
  if (!sessionActive.value) return
  const mode = opts.mode ?? 'keep'
  if (peaks.value.length === 0 && !opts.allowEmpty) return
  const seq = ++peaksUpdateSeq
  void submitAndWait('calibration', sessionPayload('update_peaks', {
    mode,
    peaks: peaks.value.map(p => ({ y: p.y, x: p.x, ring: p.ring ?? null })),
  })).then(data => {
    if (seq !== peaksUpdateSeq) return // stale / 已过期
    applyPeaksResponse(data)
  }).catch(err => {
    toastError(t('calibration.title'), err, t('calibration.errors.noSession'))
  })
}

// === Extraction-region + duplicate-handling helpers (calib2 parity) ===

/** Harvest region returned by ring_pick: the band (and contiguous arc) the
 *  backend actually harvested. / ring_pick 返回的实际收峰区域（环带/弧段）。 */
interface CalibHarvestRegion {
  cy: number
  cx: number
  radiusPx: number
  tolPx: number
  arc: { a0: number; a1: number } | null
}

function parseHarvestRegion(raw: unknown): CalibHarvestRegion | null {
  if (!raw || typeof raw !== 'object') return null
  const o = raw as Record<string, unknown>
  const cy = numberOrNull(o.cy)
  const cx = numberOrNull(o.cx)
  const radiusPx = numberOrNull(o.radiusPx)
  if (cy == null || cx == null || radiusPx == null) return null
  let arc: { a0: number; a1: number } | null = null
  if (o.arc && typeof o.arc === 'object') {
    const a = o.arc as Record<string, unknown>
    const a0 = numberOrNull(a.a0)
    const a1 = numberOrNull(a.a1)
    if (a0 != null && a1 != null && a1 > a0) arc = { a0, a1 }
  }
  return {
    cy, cx, radiusPx,
    tolPx: numberOrNull(o.tolPx) ?? 15,
    arc,
  }
}

/** Is a point inside the harvested ring band (and arc, when contiguous)? */
function inHarvestRegion(p: { y: number; x: number }, region: CalibHarvestRegion): boolean {
  const dr = Math.abs(Math.hypot(p.y - region.cy, p.x - region.cx) - region.radiusPx)
  if (dr > region.tolPx + 6) return false
  if (region.arc) {
    const TWO_PI = 2 * Math.PI
    const delta = (((Math.atan2(p.y - region.cy, p.x - region.cx) - region.arc.a0) % TWO_PI) + TWO_PI) % TWO_PI
    return delta <= region.arc.a1 - region.arc.a0
  }
  return true
}

/** calib2 "+" semantics with DISPLAY ring numbers (1-based): the next ring
 *  number is max(existing display ring)+1; 1 when the table is empty.
 *  以 1 起显示环号实现的 calib2 “+” 语义：下一环号 = 现有最大 +1，空表为 1。 */
function nextDisplayRing(): number {
  let max = 0
  for (const p of peaks.value) {
    if (p.ring != null && p.ring + 1 > max) max = p.ring + 1
  }
  return max + 1
}

/** Per-ring renumber (summary-table ring edit, calib2 spin box semantics):
 *  EVERY peak currently on `oldRing` (0-based backend index) moves to
 *  `newRing`, the list is re-grouped, and a 'keep' push makes the edit
 *  authoritative. Merging into an existing ring number is exactly how a
 *  later re-pick of the same ring merges into its stats row.
 *  整环改号（汇总表环号编辑）：该环全部峰移到新环号，重新分组，并以 keep
 *  模式推送使编辑生效；改到已有环号即实现“再次拾取同一环并入其统计”。 */
function handleRenameRing(oldRing: number, newRing: number): void {
  if (oldRing === newRing || newRing < 0) return
  const touched = peaks.value.some(p => p.ring === oldRing)
  if (!touched) return
  peaks.value = sortPeaksByRing(
    peaks.value.map(p => (p.ring === oldRing ? { ...p, ring: newRing } : p)),
  )
  pushPeaksUpdate({ mode: 'keep' })
}

/** 刷新环号/自检: re-run ring assignment from the CURRENT geometry
 *  (update_peaks mode 'assign' reuses session.gr when present) and surface
 *  per-peak warnings for peaks deviating from their assigned theoretical
 *  ring — calib2's ring table + geometry residual check, per peak.
 *  按当前几何重新分配环号，并对偏离理论环的峰逐个告警。 */
async function handleRefreshRings(): Promise<void> {
  if (!sessionActive.value || peaks.value.length === 0) return
  refreshingRings.value = true
  const seq = ++peaksUpdateSeq
  try {
    const data = await submitAndWait('calibration', sessionPayload('update_peaks', {
      mode: 'assign',
      peaks: peaks.value.map(p => ({ y: p.y, x: p.x })),
    }))
    if (seq !== peaksUpdateSeq) return // stale / 已过期
    applyPeaksResponse(data)
    const suspects = peaks.value.filter(p => p.suspect)
    if (suspects.length > 0) {
      toast.push({
        title: t('calibration.peaks.title'),
        message: isZh.value
          ? `自检发现 ${suspects.length} 个可疑峰（偏离所属理论环，见表中红行）`
          : `${suspects.length} suspect peak(s) deviate from their assigned ring (red rows in the table)`,
        tone: 'warning',
      })
    } else {
      toast.push({
        title: t('calibration.peaks.title'),
        message: isZh.value
          ? `环号已按当前几何刷新，${peaks.value.length} 个峰全部通过自检`
          : `Ring numbers refreshed from the current geometry; all ${peaks.value.length} peaks pass the check`,
        tone: 'success',
      })
    }
  } catch (err) {
    toastError(t('calibration.peaks.title'), err, t('calibration.errors.loadFailed'))
  } finally {
    refreshingRings.value = false
  }
}

// REQ 2: canvas clicks ALWAYS place ring-guide points on the CURRENT ring —
// there is no pick-mode toolbar any more; ring_pick fires on 完成本环 /
// Enter / double-click. / 画布点击始终为当前环放置引导点（模式工具栏已移除）；
// 完成本环 / 回车 / 双击触发 ring_pick。
function onCanvasClick(pixel: { row: number; col: number }): void {
  ringGuide.value = [...ringGuide.value, { y: pixel.row, x: pixel.col }]
}

/** Double-click finishes the current ring (its clicks already added points). */
function onCanvasDblClick(_pixel: { row: number; col: number }): void {
  if (step.value === 'peaks') void finishRingPick()
}

const needRingPointsMessage = computed(() =>
  isZh.value
    ? '完成本环需要环上至少 3 个引导点'
    : 'Finishing a ring needs at least 3 guide points on it',
)

/**
 * REQ 2 ring-by-ring finish: ≥3 guide points → backend ring_pick (circle fit +
 * calib2 extraction) with ``assignRing`` = the CURRENT ring number (converted
 * from the 1-based spinner to the 0-based backend index) → harvested peaks are
 * stamped with exactly that ring (NOT theoretical nearest) → apply the Rubber
 * duplicate option → merge + dedupe → re-group the table by ring → clear
 * guides → spinner auto-advances to max+1 → update_peaks (keep mode honors the
 * stamped rings).
 *
 * Extraction variants (STEP 0, PeakPickingTask.py:1243-1265): default
 * extractMode="contiguous" is calib2's "Arc" tool ("Extract contiguous
 * peaks") — only the arc the guides span is harvested, continuously; with the
 * beyondMask option ("Ring" tool, "Extract peaks, beyond masked values") the
 * FULL ring is harvested and masked positions never block it.
 * 逐一环选完成：引导点 → ring_pick（携带 assignRing=当前环号，界面 1 起换算为
 * 0 起后端环号）→ 收到的峰直接打上该环号（而非理论最近环）→ Rubber 去重选项
 * → 并入去重 → 按环重新分组 → 清引导点 → 数字框自动跳到 max+1 → keep 模式
 * 推送（尊重已打环号）。默认连续提取（Arc 语义）；勾选越过掩码则整环提取。
 */
async function finishRingPick(): Promise<void> {
  if (ringPicking.value) return
  if (!sessionActive.value) {
    toast.push({ title: t('calibration.title'), message: t('calibration.errors.noSession'), tone: 'error' })
    return
  }
  // Collapse consecutive near-duplicate points (a double-click finish adds one).
  // 合并相邻近重复点（双击完成会多出一个重复点）。
  // BUG C fix (完成环选报 "An object could not be cloned"): entries read out of
  // the reactive ringGuide ref are Vue PROXIES — feeding them into submitTask
  // → ipcRenderer.invoke hits Electron's structured clone, which cannot clone
  // proxies, so ring_pick threw and 下一步 never unlocked. Plain-clone every
  // point into a fresh object so the payload is cloneable.
  // 修复：从响应式 ringGuide 读出的元素是 Vue 代理对象，直接进 submitTask 会让
  // ipcRenderer.invoke 的结构化克隆抛错（环选永远失败）。逐点浅拷贝为普通对象。
  const pts: Array<{ y: number; x: number }> = []
  for (const p of ringGuide.value) {
    const prev = pts[pts.length - 1]
    if (prev && Math.abs(prev.y - p.y) <= 1 && Math.abs(prev.x - p.x) <= 1) continue
    pts.push({ y: p.y, x: p.x })
  }
  if (pts.length < 3) {
    toast.push({
      title: t('calibration.peaks.title'),
      message: needRingPointsMessage.value,
      tone: 'warning',
    })
    return
  }
  // Spinner is 1-based (calib2 parity); the backend ring index is 0-based.
  // 数字框 1 起（calib2 习惯）；后端环号 0 起，此处换算。
  const assignRing = Math.max(0, Math.floor(currentRing.value) - 1)
  ringPicking.value = true
  try {
    const data = await submitAndWait('calibration', sessionPayload('ring_pick', {
      points: pts,
      extractMode: beyondMask.value ? 'beyond_mask' : 'contiguous',
      assignRing,
    }))
    const harvested = normalizePeaks(data.peaks)
    const region = parseHarvestRegion(data.region)

    // Rubber option: remove the old points inside the harvested band/arc
    // before merging the fresh harvest. / Rubber 选项：并入新收峰前，移除
    // 环带（弧段）内的已有点。
    if (removeExisting.value && region) {
      peaks.value = peaks.value.filter(p => !inHarvestRegion(p, region))
    }

    let added = false
    for (const p of harvested) {
      if (peaks.value.some(q => q.y === p.y && q.x === p.x)) continue
      // Stamp the CURRENT ring (backend echoes it; enforced here as a guard).
      // 直接打上当前环号（后端已回带，此处兜底强制）。
      p.ring = assignRing
      peaks.value = [...peaks.value, p]
      added = true
    }
    ringGuide.value = []

    // STEP 1 fix: an empty harvest is NOT an error to push — warn the user
    // and skip update_peaks while the list is still empty (pushPeaksUpdate
    // guards it too; the backend no-ops an explicit empty list).
    // 空收峰不是可推送的错误：提示用户；列表仍为空时跳过 update_peaks
    //（pushPeaksUpdate 亦有守卫；后端对显式空列表按清空处理）。
    if (harvested.length === 0) {
      const msg = stringOrNull(data.message) ?? (isZh.value
        ? '环带内未找到峰；请检查引导点或勾选“越过掩码提取”。'
        : 'No peaks found in the ring band; check the guide points or enable "Beyond mask".')
      toast.push({ title: t('calibration.peaks.title'), message: msg, tone: 'warning' })
      return
    }
    // Ring-by-ring: re-group by ring, then advance the spinner to max+1
    // (calib2 "+" semantics). / 按环重新分组，数字框跳到 max+1。
    peaks.value = sortPeaksByRing(peaks.value)
    if (added) currentRing.value = nextDisplayRing()
    pushPeaksUpdate()
  } catch (err) {
    toastError(t('calibration.title'), err, t('calibration.errors.loadFailed'))
  } finally {
    ringPicking.value = false
  }
}

/**
 * Kåsa algebraic least-squares circle fit (same as the backend's ring_pick).
 * Powers the dashed ring-guide preview circle. Null below 3 points.
 * 与后端 ring_pick 一致的 Kåsa 圆拟合，用于虚线预览圆；不足 3 点返回 null。
 */
function fitCircle(points: Array<{ y: number; x: number }>): CalibRingFit | null {
  const n = points.length
  if (n < 3) return null
  let sx = 0, sy = 0, sxx = 0, syy = 0, sxy = 0, sxz = 0, syz = 0, sz = 0
  for (const p of points) {
    const { x, y } = p
    const z = x * x + y * y
    sx += x
    sy += y
    sxx += x * x
    syy += y * y
    sxy += x * y
    sxz += x * z
    syz += y * z
    sz += z
  }
  // Normal equations for x²+y² = a·x + b·y + c (center a/2, b/2).
  const m: number[][] = [
    [sxx, sxy, sx, sxz],
    [sxy, syy, sy, syz],
    [sx, sy, n, sz],
  ]
  for (let col = 0; col < 3; col++) {
    let piv = col
    for (let r = col + 1; r < 3; r++) {
      if (Math.abs(m[r][col]) > Math.abs(m[piv][col])) piv = r
    }
    if (Math.abs(m[piv][col]) < 1e-12) return null // Collinear / degenerate points
    if (piv !== col) {
      const tmp = m[col]
      m[col] = m[piv]
      m[piv] = tmp
    }
    for (let r = 0; r < 3; r++) {
      if (r === col) continue
      const f = m[r][col] / m[col][col]
      for (let c = col; c < 4; c++) m[r][c] -= f * m[col][c]
    }
  }
  const a = m[0][3] / m[0][0]
  const b = m[1][3] / m[1][1]
  const c = m[2][3] / m[2][2]
  const cx = a / 2
  const cy = b / 2
  const r2 = c + cx * cx + cy * cy
  if (!Number.isFinite(r2) || r2 <= 0) return null
  return { cy, cx, radiusPx: Math.sqrt(r2) }
}

/** Dashed preview circle through the current guide points (≥3), for CalibCanvas. */
const ringFit = computed<CalibRingFit | null>(() => fitCircle(ringGuide.value))

/** Remove radius in image pixels — generous enough for zoomed-out clicking. */
const REMOVE_RADIUS_PX = 15

function onCanvasRemove(pixel: { row: number; col: number }): void {
  let bestIdx = -1
  let bestD2 = REMOVE_RADIUS_PX * REMOVE_RADIUS_PX
  peaks.value.forEach((peak, i) => {
    const d2 = (peak.y - pixel.row) ** 2 + (peak.x - pixel.col) ** 2
    if (d2 <= bestD2) {
      bestD2 = d2
      bestIdx = i
    }
  })
  if (bestIdx < 0) return
  peaks.value = peaks.value.filter((_, i) => i !== bestIdx)
  pushPeaksUpdate()
}

// === Refine / 精化 ===

async function handleRefine(payload: { passes: number }): Promise<void> {
  if (!sessionActive.value) {
    toast.push({ title: t('calibration.refine.title'), message: t('calibration.errors.noSession'), tone: 'error' })
    return
  }
  if (peaks.value.length === 0) {
    toast.push({
      title: t('calibration.refine.title'),
      message: t('calibration.refine.needPeaks'),
      tone: 'warning',
    })
    return
  }

  refining.value = true
  try {
    const data = await submitAndWait('calibration', sessionPayload('refine', {
      free: { ...freeFlags.value },
      passes: payload.passes,
    }))

    chi2.value = numberOrNull(data.chi2 ?? data.chi_square)
    geometry.value = normalizeGeometry(data.geometry)
    residuals.value = normalizeResiduals(data.residuals)
    converged.value = typeof data.converged === 'boolean' ? data.converged : null
    exportResult.value = null

    if (converged.value === false) {
      toast.push({
        title: t('calibration.refine.title'),
        message: t('calibration.refine.notConverged'),
        tone: 'warning',
      })
    } else {
      toast.push({
        title: t('calibration.refine.title'),
        message: t('calibration.refine.done'),
        tone: 'success',
      })
    }

    unlockStep(3)
    // Refresh the ring overlay AND the calibrant integration preview with the
    // refined geometry (both decorative on failure — whatever is on screen
    // stays). / 以精修几何刷新理论环叠加与标定积分预览（失败时保留现状）。
    void refreshRingOverlay()
    void refreshIntegrationPreview()
  } catch (err) {
    toastError(t('calibration.errors.refineFailed'), err, t('calibration.errors.refineFailed'))
  } finally {
    refining.value = false
  }
}

async function refreshRingOverlay(): Promise<void> {
  if (!sessionActive.value) return
  try {
    const data = await submitAndWait('calibration', sessionPayload('ring_overlay'))
    rings.value = normalizeRings(data.rings)
  } catch {
    // Ring overlay is decorative — keep whatever is on screen.
    // 圆环叠加仅辅助显示，失败时保留现状。
  }
}

// === Calibrant integration preview (step 3, calib2 Integration parity) ===
// 标定图积分预览（第 3 步）：以当前精修几何做 1D 曲线 + 2D cake。
// 每次精修后自动刷新；2D 数据为后端降采样（≤400×360、3 位小数、行优先展平）
// 的强度，此处重排为 [azim][rad] 网格供 plotly heatmap。

interface CalibInteg1d { x: number[]; y: Array<number | null> }
interface CalibInteg2d {
  intensity: Array<number | null>
  nRad: number
  nAzim: number
  xRange: [number, number]
  yRange: [number, number]
}

const integ1d = ref<CalibInteg1d | null>(null)
const integ2d = ref<CalibInteg2d | null>(null)
const integLoading = ref(false)
const integError = ref<string | null>(null)
let integSeq = 0

function normalizeInteg1d(raw: unknown): CalibInteg1d | null {
  if (!raw || typeof raw !== 'object') return null
  const o = raw as Record<string, unknown>
  if (!Array.isArray(o.x) || !Array.isArray(o.y)) return null
  if (o.x.length === 0 || o.x.length !== o.y.length) return null
  const x = o.x.map(v => numberOrNull(v) ?? 0)
  const y = o.y.map(v => (v == null ? null : numberOrNull(v)))
  return { x, y }
}

function normalizeInteg2d(raw: unknown): CalibInteg2d | null {
  if (!raw || typeof raw !== 'object') return null
  const o = raw as Record<string, unknown>
  const nRad = numberOrNull(o.nRad)
  const nAzim = numberOrNull(o.nAzim)
  const flat = Array.isArray(o.intensity) ? o.intensity : []
  const xr = Array.isArray(o.xRange) ? o.xRange : []
  const yr = Array.isArray(o.yRange) ? o.yRange : []
  const x0 = numberOrNull(xr[0])
  const x1 = numberOrNull(xr[1])
  const y0 = numberOrNull(yr[0])
  const y1 = numberOrNull(yr[1])
  if (!nRad || !nAzim || flat.length !== nRad * nAzim
    || x0 == null || x1 == null || y0 == null || y1 == null) return null
  return {
    intensity: flat.map(v => (v == null ? null : numberOrNull(v))),
    nRad, nAzim,
    xRange: [x0, x1],
    yRange: [y0, y1],
  }
}

/** Fetch the 1D curve + 2D cake under the current refined geometry. */
async function refreshIntegrationPreview(): Promise<void> {
  if (!sessionActive.value || geometry.value == null) return
  const seq = ++integSeq
  integLoading.value = true
  integError.value = null
  try {
    const data = await submitAndWait('calibration', sessionPayload('integrate_preview'))
    if (seq !== integSeq) return // stale / 已过期
    integ1d.value = normalizeInteg1d(data['1d'] ?? data.integ1d)
    integ2d.value = normalizeInteg2d(data['2d'] ?? data.integ2d)
    if (!integ1d.value && !integ2d.value) {
      integError.value = isZh.value ? '积分预览无有效数据' : 'Integration preview returned no data'
    }
  } catch (err) {
    if (seq !== integSeq) return
    integ1d.value = null
    integ2d.value = null
    integError.value = err instanceof Error && err.message ? err.message : String(err)
  } finally {
    if (seq === integSeq) integLoading.value = false
  }
}

// Inline bilingual labels — no i18n keys yet (see final report).
// 内联双语文案 —— 暂无 i18n 键（见最终报告缺失键清单）。
const integTitleLabel = computed(() =>
  isZh.value ? '标定图积分预览（当前精修几何）' : 'Calibrant integration preview (current geometry)',
)
const integLoadingLabel = computed(() => (isZh.value ? '积分中…' : 'Integrating…'))
const integMetaLabel = computed(() => {
  const two = integ2d.value
  return two ? `${two.nRad}×${two.nAzim}` : ''
})

const integ1dTraces = computed<PlotData[]>(() => {
  const one = integ1d.value
  if (!one) return []
  const trace: PlotData = {
    type: 'scatter',
    mode: 'lines',
    x: one.x,
    y: one.y as number[],
    line: { width: 1.5, color: '#38bdf8' },
    connectgaps: false,
  }
  return [trace]
})

const integ1dLayout = computed<Partial<PlotLayout>>(() => ({
  margin: { t: 8, r: 10, b: 36, l: 52 },
  height: 240,
  xaxis: { title: { text: 'q (nm⁻¹)' }, zeroline: false },
  yaxis: { title: { text: 'I (a.u.)' }, zeroline: false },
  showlegend: false,
}))

/** Reshape the flattened row-major cake into rows-of-azimuth for plotly. */
const integ2dGrid = computed<Array<Array<number | null>> | null>(() => {
  const two = integ2d.value
  if (!two) return null
  const grid: Array<Array<number | null>> = []
  for (let r = 0; r < two.nAzim; r++) {
    grid.push(two.intensity.slice(r * two.nRad, (r + 1) * two.nRad))
  }
  return grid
})

const integ2dTraces = computed<PlotData[]>(() => {
  const two = integ2d.value
  const grid = integ2dGrid.value
  if (!two || !grid) return []
  const n = two.nRad
  const x: number[] = Array.from({ length: n }, (_, i) =>
    two.xRange[0] + ((two.xRange[1] - two.xRange[0]) * i) / Math.max(1, n - 1))
  const m = two.nAzim
  const y: number[] = Array.from({ length: m }, (_, i) =>
    two.yRange[0] + ((two.yRange[1] - two.yRange[0]) * i) / Math.max(1, m - 1))
  const trace: PlotData = {
    type: 'heatmap',
    z: grid as unknown as number[][],
    x,
    y,
    colorscale: 'Viridis',
    hovertemplate: 'q=%{x:.2f} χ=%{y:.0f}°<extra>I=%{z}</extra>',
  }
  return [trace]
})

const integ2dLayout = computed<Partial<PlotLayout>>(() => {
  const two = integ2d.value
  const layout: Partial<PlotLayout> = {
    margin: { t: 8, r: 10, b: 36, l: 52 },
    height: 240,
    xaxis: { title: { text: 'q (nm⁻¹)' }, zeroline: false },
    yaxis: { title: { text: 'χ (°)' }, zeroline: false },
    showlegend: false,
  }
  if (two && two.nRad > 1 && two.nAzim > 1) {
    // 'image' aspect: square cake cells via scaleanchor + the per-bin unit
    // ratio (one radial bin vs one azimuth bin).
    // 图像纵横比：scaleanchor + 每格单位比实现方形 cake 像素。
    const cellX = (two.xRange[1] - two.xRange[0]) / two.nRad
    const cellY = (two.yRange[1] - two.yRange[0]) / two.nAzim
    if (cellX > 0 && cellY > 0) {
      ;(layout.yaxis as { scaleanchor?: string; scaleratio?: number }).scaleanchor = 'x'
      ;(layout.yaxis as { scaleanchor?: string; scaleratio?: number }).scaleratio = cellX / cellY
    }
  }
  return layout
})

// === Export / 导出 ===

async function handleExportPoni(savePath: string): Promise<void> {
  if (!sessionActive.value) {
    toast.push({ title: t('calibration.export.title'), message: t('calibration.errors.noSession'), tone: 'error' })
    return
  }
  exporting.value = true
  try {
    const data = await submitAndWait('calibration', sessionPayload('export_poni', { savePath }))
    exportResult.value = {
      path: stringOrNull(data.path) ?? stringOrNull(data.saved_path) ?? savePath,
      citation: normalizeCitation(data.citation),
    }
    toast.push({
      title: t('calibration.export.title'),
      message: t('calibration.export.saved'),
      tone: 'success',
    })
  } catch (err) {
    toastError(t('calibration.export.title'), err, t('calibration.title'))
  } finally {
    exporting.value = false
  }
}

/**
 * 去积分 (step 4, both the card button and the export-dialog footer):
 * auto-save the refined .poni into the OS temp dir (export_poni autoSave —
 * the backend picks a unique temp path and returns it), then route to
 * /workspace/integrate-1d?poni=<encoded path>; Integrate1dView imports it
 * into geometryParams.poniPath on mount. Falls back to a plain navigation
 * (no query) when there is nothing refined or the auto-save fails.
 * 去积分（第 4 步）：先把精修 .poni 自动存入系统临时目录（export_poni 的
 * autoSave 由后端生成唯一临时路径并返回），再跳转
 * /workspace/integrate-1d?poni=<编码路径>；Integrate1dView 挂载时导入
 * geometryParams.poniPath。无精修结果或自动保存失败时退回普通跳转。
 */
async function goIntegrate(): Promise<void> {
  if (!sessionActive.value || geometry.value == null || exporting.value) {
    void router.push('/workspace/integrate-1d')
    return
  }
  exporting.value = true
  try {
    const data = await submitAndWait('calibration', sessionPayload('export_poni', { autoSave: true }))
    const poniPath = stringOrNull(data.savePath) ?? stringOrNull(data.path)
    void router.push(poniPath
      ? `/workspace/integrate-1d?poni=${encodeURIComponent(poniPath)}`
      : '/workspace/integrate-1d')
  } catch (err) {
    toastError(t('calibration.export.title'), err, t('calibration.errors.loadFailed'))
    void router.push('/workspace/integrate-1d')
  } finally {
    exporting.value = false
  }
}

// === Display helpers / 显示辅助 ===

const calibrantLabel = computed(() =>
  setupForm.value.calibrantPath.trim() || setupForm.value.calibrant || ''
)

/**
 * Refined beam center in ORIGINAL image pixels (x = poni2/pixel2 = column,
 * y = poni1/pixel1 = row) — drawn by CalibCanvas as the magenta crosshair and
 * echoed in the canvas legend; updates with every refine.
 * 精修后的光束中心（原始图像像素）——画布洋红十字 + 图例同步显示，随每次
 * 精修更新。
 */
const refinedBeamCenter = computed<{ x: number; y: number } | null>(() => {
  const g = geometry.value
  if (!g) return null
  const x = g.centerXPx
  const y = g.centerYPx
  if (x == null || y == null || !Number.isFinite(x) || !Number.isFinite(y)) return null
  return { x, y }
})

const beamCenterLegendLabel = computed(() =>
  refinedBeamCenter.value
    ? `${isZh.value ? '中心' : 'center'} (${refinedBeamCenter.value.x.toFixed(0)}, ${refinedBeamCenter.value.y.toFixed(0)})`
    : '',
)

const beamCenterLegendTitle = computed(() =>
  isZh.value
    ? '精修后的光束中心（与右侧“最终中心 (px)”一致）'
    : 'Refined beam center (same as "Final center (px)")',
)

/**
 * Per-ring color legend under the canvas (peaks step): ring number, the
 * stable marker color (calibPeakRingColor — same as canvas markers and the
 * summary-table swatches) and the peak count of that ring.
 * 画布下方每环颜色图例（峰拾取步）：环号 + 稳定标记色（与画布/汇总表一致）
 * + 该环峰数。
 */
const ringChips = computed<Array<{ ring: number; label: string; color: string; count: number }>>(() => {
  const counts = new Map<number, number>()
  for (const p of peaks.value) {
    if (p.ring == null) continue
    counts.set(p.ring, (counts.get(p.ring) ?? 0) + 1)
  }
  return [...counts.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([ring, count]) => ({
      ring,
      label: isZh.value ? `环 ${ring + 1}` : `ring ${ring + 1}`,
      color: calibPeakRingColor(ring),
      count,
    }))
})

/** Legend entry for the applied session mask (null = none/off). */
const maskRatioLabel = computed(() => {
  const stats = maskStats.value
  if (!stats || stats.maskedPixels <= 0) return null
  const pct = (stats.ratio * 100).toFixed(1)
  return isZh.value ? `掩膜 ${pct}%` : `Mask ${pct}%`
})

const detectorLabel = computed(() => {
  const m = setupForm.value
  return m.detector.trim() || (m.pixelSizeUm > 0 ? `${m.pixelSizeUm} µm` : '—')
})

function formatPx(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return '—'
  return `${value.toFixed(2)} px`
}

// === Lifecycle ===

/** Enter finishes the CURRENT ring (ignored while typing in a form control). */
function onKeydown(e: KeyboardEvent): void {
  if (e.key !== 'Enter' || e.repeat) return
  if (step.value !== 'peaks') return
  if (ringPicking.value || ringGuide.value.length < 3) return
  const target = e.target as HTMLElement | null
  if (target && ['INPUT', 'SELECT', 'TEXTAREA', 'BUTTON'].includes(target.tagName)) return
  e.preventDefault()
  void finishRingPick()
}

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
  if (imageSrc.value?.startsWith('blob:')) URL.revokeObjectURL(imageSrc.value)
  cleanupDisplayListeners()
})
</script>

<style scoped>
.calibration-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.cv-header h1 {
  font-size: 1.5rem;
  font-weight: 700;
  margin: 0 0 6px;
  color: var(--text-primary);
}

.cv-subtitle {
  font-size: 0.9375rem;
  color: var(--text-secondary);
  margin: 0;
}

/* Stepper / 步骤条 */
.cv-stepper {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.cv-step {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 14px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--bg-surface);
  color: var(--text-secondary);
  font-size: 0.8125rem;
  font-weight: 600;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.cv-step:hover:not(:disabled) {
  border-color: var(--border-hover);
  box-shadow: var(--shadow-sm);
}

.cv-step--active {
  border-color: var(--primary);
  color: var(--primary);
  background: var(--primary-bg);
}

.cv-step--done {
  color: var(--text-primary);
}

.cv-step:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.cv-step-num {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--bg-hover);
  color: var(--text-secondary);
  font-size: 0.72rem;
  font-weight: 700;
}

.cv-step--active .cv-step-num {
  background: var(--primary);
  color: var(--text-inverse);
}

/* Prev/Next wizard navigation / 向导上一步/下一步 */
.cv-stepper {
  align-items: center;
}

.cv-stepper-nav {
  margin-left: auto;
  display: flex;
  gap: 8px;
}

.cv-nav-btn {
  padding: 6px 16px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: 0.8125rem;
  font-weight: 600;
  cursor: pointer;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.cv-nav-btn:hover:not(:disabled) {
  border-color: var(--border-hover);
  box-shadow: var(--shadow-sm);
}

.cv-nav-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.cv-nav-btn--primary {
  border: none;
  background: var(--primary);
  color: var(--text-inverse);
}

.cv-nav-btn--primary:hover:not(:disabled) {
  opacity: 0.9;
  box-shadow: none;
}

/* Layout: controls / canvas / results (MaskMakerView proportions) */
.cv-layout {
  display: grid;
  grid-template-columns: 300px minmax(0, 1fr) 280px;
  gap: 16px;
  height: calc(100vh - 240px);
  min-height: 520px;
}

.cv-controls {
  min-width: 0;
  overflow-y: auto;
}

.cv-results {
  min-width: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.cv-card {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 14px 16px;
  background: var(--bg-surface);
}

.cv-center {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* Render settings bar / 渲染设置条 */
.cv-render-bar {
  display: flex;
  align-items: flex-end;
  gap: 14px;
  flex-wrap: wrap;
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
}

.cv-rb-field {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 0.72rem;
  color: var(--text-secondary);
  font-weight: 600;
}

.cv-rb-label {
  font-size: 0.72rem;
  color: var(--text-secondary);
  font-weight: 600;
}

.cv-rb-select,
.cv-rb-input {
  padding: 4px 8px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: 0.78rem;
  font-family: var(--font-mono);
  min-width: 90px;
}

.cv-rb-input {
  min-width: 72px;
  width: 90px;
}

.cv-rb-select:focus,
.cv-rb-input:focus {
  outline: none;
  border-color: var(--border-focus);
}

.cv-rb-toggle,
.cv-rb-radio {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 0.75rem;
  color: var(--text-primary);
  cursor: pointer;
  user-select: none;
  padding-bottom: 6px;
}

.cv-rb-toggle input,
.cv-rb-radio input {
  accent-color: var(--primary);
  width: 13px;
  height: 13px;
}

.cv-rb-clim {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  padding-bottom: 6px;
}

.cv-rb-apply {
  padding: 5px 14px;
  border-radius: 8px;
  border: none;
  background: var(--primary);
  color: var(--text-inverse);
  font-size: 0.78rem;
  font-weight: 600;
  cursor: pointer;
}

.cv-rb-apply:hover:not(:disabled) {
  opacity: 0.9;
}

.cv-rb-apply:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.cv-canvas-legend {
  display: flex;
  gap: 16px;
  justify-content: center;
  flex-wrap: wrap;
}

.cv-legend-item {
  font-size: 0.78rem;
  color: var(--text-secondary);
  font-family: var(--font-mono);
}

/* Masked-pixel legend entry (matches the canvas overlay tint) */
.cv-legend-item--mask {
  color: #f87171;
}

/* Refined beam-center legend entry (matches the magenta crosshair) */
.cv-legend-item--center {
  color: #e879f9;
  font-weight: 600;
}

/* Per-ring peak color legend / 每环峰色图例 */
.cv-ring-legend {
  display: flex;
  gap: 10px;
  justify-content: center;
  flex-wrap: wrap;
}

.cv-ring-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 0.72rem;
  color: var(--text-secondary);
  font-family: var(--font-mono);
}

.cv-ring-chip-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  border: 1px solid rgba(255, 255, 255, 0.65);
  box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.35);
}

/* Calibrant integration preview (step 3) / 标定积分预览（第 3 步） */
.cv-integ-preview {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.cv-integ-head {
  display: flex;
  align-items: baseline;
  gap: 10px;
  flex-wrap: wrap;
}

.cv-integ-title {
  margin: 0;
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-primary);
}

.cv-integ-loading,
.cv-integ-meta {
  font-size: 0.75rem;
  color: var(--text-muted);
  font-family: var(--font-mono);
}

.cv-integ-error {
  font-size: 0.75rem;
  color: #f87171;
  word-break: break-all;
}

.cv-integ-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 12px;
}

.cv-integ-cell {
  min-width: 0;
}

.cv-integ-chart {
  width: 100%;
  min-height: 240px;
  height: 240px;
}

/* Results info grid / 结果信息 */
.cv-info-grid {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 6px 12px;
  align-items: baseline;
}

.cv-info-label {
  font-size: 0.75rem;
  color: var(--text-muted);
  font-weight: 500;
  white-space: nowrap;
}

.cv-info-value {
  font-size: 0.8rem;
  color: var(--text-primary);
  font-family: var(--font-mono);
  word-break: break-all;
  text-align: right;
}

/* Export step card / 导出卡片 */
.cv-export {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.cv-btn {
  padding: 10px 18px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.cv-btn:hover:not(:disabled) {
  border-color: var(--border-hover);
  box-shadow: var(--shadow-sm);
}

.cv-btn--primary {
  border: none;
  background: var(--primary);
  color: var(--text-inverse);
  font-weight: 600;
}

.cv-btn--primary:hover:not(:disabled) {
  opacity: 0.9;
}

.cv-btn--go {
  border-color: var(--primary);
  color: var(--primary);
  font-weight: 600;
}

/* Responsive / 响应式 */
@media (max-width: 1100px) {
  .cv-layout {
    grid-template-columns: 1fr;
    grid-template-rows: auto minmax(420px, 60vh) auto;
    height: auto;
  }
}
</style>
