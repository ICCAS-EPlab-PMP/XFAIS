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
          <!-- Setup form is reused TWICE in the com mode: step 'setup' renders
               the direct-beam image phase, step 'setup2' the standard image
               phase (which also picks the branch). / 设置表单在 com 模式复用两次：
               setup = 直通光图阶段；setup2 = 标样图阶段（同时选择支路）。 -->
          <CalibSetupForm
            v-if="step === 'setup' || step === 'setup2'"
            v-model="setupForm"
            :calibrants="calibrants"
            :detectors="detectors"
            :probe="probeResult"
            :probing="probing"
            :loading="setupLoading"
            :mask-stale="maskStale"
            :phase="step === 'setup2' ? 'standard' : (setupForm.mode === 'com' ? 'beam' : 'single')"
            :standard-mode="comStandardMode ?? 'calibrant'"
            @submit="handleSetup"
            @seed="handleSeedFromPoni"
            @probed="handleProbed"
            @update:standard-mode="onStandardModeChange"
          />

          <!-- com mode step 2: box the direct-beam spot → intensity-weighted
               centroid, which then FIXES the centre for the standard branch.
               com 模式第 2 步：框出直通光斑 → 强度加权质心，随后固定为该标定
               中心。 -->
          <CalibComPanel
            v-else-if="step === 'com'"
            :com-mode="comPickMode"
            :center="comCenter"
            :busy="comBusy"
            @update:com-mode="comPickMode = $event"
            @clear-com="clearComCenter"
          />

          <CalibPeakPanel
            v-else-if="step === 'peaks'"
            :peaks="peaks"
            :sensitivity="sensitivity"
            :band-tol="bandTolPx"
            :current-ring="currentRing"
            :detecting="detecting"
            :guide-count="ringGuide.length"
            :ring-picking="ringPicking"
            :center-picking="centerPicking"
            :beyond-mask="beyondMask"
            :remove-existing="removeExisting"
            :refreshing="refreshingRings"
            @auto="handleAutoPeaks"
            @update:sensitivity="sensitivity = $event"
            @update:band-tol="bandTolPx = $event"
            @update:current-ring="currentRing = $event"
            @clear="handleClearPeaks"
            @finish-ring="finishRingPick"
            @clear-guides="ringGuide = []"
            @toggle-center-pick="toggleCenterPick"
            @update:beyond-mask="beyondMask = $event"
            @update:remove-existing="removeExisting = $event"
            @refresh-rings="handleRefreshRings"
            @update-ring="handleRenameRing"
          />

          <!-- Internal-standard step 2: pick ONE known ring + enter its value
               → the backend computes the geometry directly (no calibrant, no
               refinement). / 内标第 2 步：点选一个已知环 + 填数值 → 后端直接
               算出几何（无标样、无精修）。 -->
          <CalibRingStandardPanel
            v-else-if="step === 'ring'"
            :point-count="centerPoints.length"
            :fit="centerFit"
            :rms-px="centerRmsPx"
            :applying="ringApplying"
            :result="ringResult"
            :zoom-enabled="zoomEnabled"
            :value-text="ringValueText"
            :unit="ringUnit"
            :default-dist-mm="setupForm.distGuessMm"
            :fixed-center="comFixedCenter"
            @update:value-text="ringValueText = $event"
            @update:unit="ringUnit = $event"
            @clear="centerPoints = []"
            @apply="applyRingStandard"
            @toggle-zoom="zoomEnabled = $event"
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
            :center-locked="comFixedCenter"
            @run="handleRefine"
          />

          <!-- Internal-standard step 3: read-only geometry readout (the
               geometry is computed, never refined — no χ²). Mirrors
               CalibRefinePanel's crp-geometry layout without touching that
               component. / 内标第 3 步：只读几何读数（几何是算出来的、无精修
               ——不显示 χ²）。版式对标 CalibRefinePanel 但不动其本体。 -->
          <div v-else-if="step === 'preview'" class="cv-geo">
            <h4 class="cv-geo-title">{{ t('calibration.ring.previewTitle') }}</h4>
            <template v-if="geometry">
              <div class="cv-geo-final-center">
                <span class="cv-geo-final-label">{{ t('calibration.ring.resultCenter') }}</span>
                <span class="cv-geo-final-value">{{ previewCenterText }}</span>
              </div>
              <dl class="cv-geo-readout">
                <div class="cv-geo-row" :title="geoMeaning('dist')">
                  <dt>dist <em>{{ geoMeaning('dist') }}</em></dt>
                  <dd>{{ formatGeo(geometry.distMm, 'mm') }}</dd>
                </div>
                <div class="cv-geo-row" :title="geoMeaning('poni1')">
                  <dt>poni1 <em>{{ geoMeaning('poni1') }}</em></dt>
                  <dd>{{ formatGeo(geometry.poni1Mm, 'mm') }}</dd>
                </div>
                <div class="cv-geo-row" :title="geoMeaning('poni2')">
                  <dt>poni2 <em>{{ geoMeaning('poni2') }}</em></dt>
                  <dd>{{ formatGeo(geometry.poni2Mm, 'mm') }}</dd>
                </div>
                <div class="cv-geo-row" :title="geoMeaning('rot1')">
                  <dt>rot1 <em>{{ geoMeaning('rot1') }}</em></dt>
                  <dd>{{ formatGeo(geometry.rot1Deg, '°') }}</dd>
                </div>
                <div class="cv-geo-row" :title="geoMeaning('rot2')">
                  <dt>rot2 <em>{{ geoMeaning('rot2') }}</em></dt>
                  <dd>{{ formatGeo(geometry.rot2Deg, '°') }}</dd>
                </div>
                <div class="cv-geo-row" :title="geoMeaning('rot3')">
                  <dt>rot3 <em>{{ geoMeaning('rot3') }}</em></dt>
                  <dd>{{ formatGeo(geometry.rot3Deg, '°') }}</dd>
                </div>
                <div class="cv-geo-row" :title="geoMeaning('wavelength')">
                  <dt>wavelength <em>{{ geoMeaning('wavelength') }}</em></dt>
                  <dd>{{ formatGeo(geometry.wavelengthA, 'Å') }}</dd>
                </div>
              </dl>
              <!-- Default-distance warning in the preview readout: the SD row
                   above is the initial guess, not a fitted value.
                   预览读数中的默认距离警示：上方 SD 行是初始猜测而非拟合值。 -->
              <p v-if="ringDistDefaulted" class="cv-geo-default-warn">
                {{ t('calibration.ring.resultDefaultDist', { mm: ringDefaultDistText }) }}
              </p>
            </template>
            <p v-else class="cv-geo-empty">{{ t('calibration.ring.noGeometry') }}</p>
            <p class="cv-geo-hint">{{ t('calibration.ring.previewHint') }}</p>
          </div>

          <div v-else class="cv-export">
            <!-- Pre-export warning (user request): a default-distance geometry
                 must be announced BEFORE the .poni leaves the wizard.
                 导出前警示（用户要求）：默认距离几何必须在 .poni 离开向导之前
                 明确告知。 -->
            <div
              v-if="ringDistDefaulted"
              class="cv-export-warning"
              data-ai-id="calibration:default-dist-warning"
            >
              {{ t('calibration.ring.exportDefaultDistWarning', { mm: ringDefaultDistText }) }}
            </div>
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

        <!-- Canvas interaction follows the step: peaks = ring guides, ring
             (internal standard) = the ring-standard points; preview keeps
             drawing the fitted circle only. / 画布交互随步骤切换：峰拾取 =
             环引导点；内标定标 = 内标环点选；几何预览仅继续画拟合圆。 -->
        <CalibCanvas
          :image-src="imageSrc"
          :image-width="imageWidth"
          :image-height="imageHeight"
          :rings="rings"
          :peaks="peaks"
          :interactive="step === 'peaks' || step === 'ring' || (step === 'com' && comPickMode != null)"
          :ring-guide="canvasGuide"
          :ring-fit="canvasFit"
          :hint="step === 'com'
            ? (comPickMode === 'rect' ? t('calibration.com.canvasRect')
              : comPickMode === 'poly' ? t('calibration.com.canvasPoly')
                : t('calibration.com.canvasIdle'))
            : (step === 'ring'
                ? t('calibration.ring.canvasHint')
                : (step === 'peaks' && centerPicking ? centerPickHint : undefined))"
          :mask-overlay="maskOverlay"
          :beam-center="refinedBeamCenter"
          :region-mode="step === 'com' ? comPickMode : null"
          :com-region="comRegion"
          :com-center="comCenter"
          @canvas-click="onCanvasClick"
          @canvas-remove="onCanvasRemove"
          @canvas-dblclick="onCanvasDblClick"
          @region-selected="onRegionSelected"
        />
        <div v-if="imageSrc" class="cv-canvas-legend">
          <span class="cv-legend-item">{{ t('calibration.canvas.peaks') }}: {{ peaks.length }}</span>
          <span class="cv-legend-item">{{ t('calibration.canvas.rings') }}: {{ rings.length }}</span>
          <span v-if="step === 'peaks'" class="cv-legend-item">{{ guideCountLabel }}</span>
          <span v-if="step === 'ring'" class="cv-legend-item">{{ ringPointsLabel }}</span>
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

        <!-- ===== Calibrant integration preview (calib2 Integration-task
             parity): 1-D curve + 2-D cake under the CURRENT geometry —
             refined in calibrant mode, computed by ring_standard in
             internal-standard mode (step 3). Auto-refreshed after every refine
             and on entering the preview step. / 标定图积分预览：以当前几何做
             1D 曲线 + 2D cake——标样模式为精修几何，内标模式为 ring_standard
             算出的几何（第 3 步）。精修后与进入预览步时自动刷新。 ===== -->
        <div v-if="step === 'refine' || step === 'preview'" class="cv-integ-preview">
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

    <!-- FIT2D-style zoomed second pick (internal-standard step, zoom on):
         the first canvas click opens this window, the second (inside) pick
         lands the point at sub-pixel precision. One at a time. /
         FIT2D 式放大二次选点（内标步开启放大时）：画布第一次点击打开此窗，
         窗内二次点选以亚像素精度落点。同一时间只开一个。 -->
    <CalibZoomPicker
      v-if="zoomOpen && zoomAnchor"
      :image-src="imageSrc"
      :image-width="imageWidth"
      :image-height="imageHeight"
      :anchor="zoomAnchor"
      @confirm="onZoomConfirm"
      @cancel="onZoomCancel"
    />

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
import type { CalibPeak, CalibRing, CalibRingFit, CalibMaskOverlay, CalibRegion } from '@/components/calibration/CalibCanvas.vue'
import { calibPeakRingColor } from '@/components/calibration/CalibCanvas.vue'
import CalibSetupForm from '@/components/calibration/CalibSetupForm.vue'
import type { CalibSetupModel, CalibSetupPayload, CalibProbeInfo } from '@/components/calibration/CalibSetupForm.vue'
import CalibPeakPanel from '@/components/calibration/CalibPeakPanel.vue'
import CalibRefinePanel from '@/components/calibration/CalibRefinePanel.vue'
import type { CalibFreeFlags, CalibGeometry, CalibResidualPoint } from '@/components/calibration/CalibRefinePanel.vue'
import CalibExportDialog from '@/components/calibration/CalibExportDialog.vue'
import type { CalibExportResult, CalibCitation } from '@/components/calibration/CalibExportDialog.vue'
import CalibRingStandardPanel from '@/components/calibration/CalibRingStandardPanel.vue'
import type { CalibRingStandardResult, CalibRingUnit } from '@/components/calibration/CalibRingStandardPanel.vue'
import CalibComPanel from '@/components/calibration/CalibComPanel.vue'
import CalibZoomPicker from '@/components/calibration/CalibZoomPicker.vue'
import PlotlyChart from '@/components/charts/PlotlyChart.vue'
import type { PlotData, PlotLayout } from 'plotly.js-dist-min'

// === Wizard steps / 向导步骤 ===

/** Steps of the THREE mutually-exclusive modes:
 *  - calibrant: setup → peaks → refine → export;
 *  - internal:  setup → ring → preview → export;
 *  - com (直通光定心): setup (direct-beam image) → com (box → centroid) →
 *    setup2 (standard image + branch choice) → then EITHER the calibrant
 *    (peaks/refine) OR the internal-standard (ring/preview) branch, both with
 *    the centre FIXED — only the distance is optimised.
 *  三种互斥模式的步骤：标样校正 / 内标定标 / 直通光定心（直通光图 → 框选质心 →
 *  标样图 + 支路选择 → 标样或内标支路，中心固定、只优化距离）。 */
type CalibStep = 'setup' | 'com' | 'setup2' | 'peaks' | 'refine' | 'ring' | 'preview' | 'export'

interface CalibStepDef {
  key: CalibStep
  labelKey: string
}

/** Stepper is MODE-DEPENDENT — recomputed when the setup form's mode flips or
 *  the com branch is chosen. / 步骤随模式与 com 支路选择变化。 */
const STEPS = computed<CalibStepDef[]>(() => {
  const mode = setupForm.value.mode
  if (mode === 'internal') {
    return [
      { key: 'setup', labelKey: 'calibration.steps.load' },
      { key: 'ring', labelKey: 'calibration.steps.ring' },
      { key: 'preview', labelKey: 'calibration.steps.preview' },
      { key: 'export', labelKey: 'calibration.export.title' },
    ]
  }
  if (mode === 'com') {
    const head: CalibStepDef[] = [
      { key: 'setup', labelKey: 'calibration.steps.beamImage' },
      { key: 'com', labelKey: 'calibration.steps.com' },
      { key: 'setup2', labelKey: 'calibration.steps.standardImage' },
    ]
    if (comStandardMode.value === 'internal') {
      return [
        ...head,
        { key: 'ring', labelKey: 'calibration.steps.ring' },
        { key: 'preview', labelKey: 'calibration.steps.preview' },
        { key: 'export', labelKey: 'calibration.export.title' },
      ]
    }
    if (comStandardMode.value === 'calibrant') {
      return [
        ...head,
        { key: 'peaks', labelKey: 'calibration.peaks.title' },
        { key: 'refine', labelKey: 'calibration.steps.refineFixed' },
        { key: 'export', labelKey: 'calibration.export.title' },
      ]
    }
    return head
  }
  return [
    { key: 'setup', labelKey: 'calibration.setup.load' },
    { key: 'peaks', labelKey: 'calibration.peaks.title' },
    { key: 'refine', labelKey: 'calibration.refine.title' },
    { key: 'export', labelKey: 'calibration.export.title' },
  ]
})

const { t, locale } = useI18n()
const toast = useToast()
const transport = useTransport()
const router = useRouter()

/** Stepper label: step 3 was RENAMED (精修中心位点 / Refine center & geometry —
 *  inline bilingual, no i18n key yet); other steps keep their keys.
 *  步骤条文案：第 3 步已改名（内联双语，暂无 i18n 键）；其余沿用现有键。 */
function stepLabel(s: CalibStepDef): string {
  // The refine step is titled differently per flow: with a direct-beam fixed
  // centre only the DISTANCE is optimised, so say so. / 精修步按流程命名：
  // 直通光固定中心时只优化距离。
  if (s.key === 'refine') {
    return setupForm.value.mode === 'com' && comStandardMode.value === 'calibrant'
      ? t('calibration.steps.refineFixed')
      : (isZh.value ? '精修中心位点' : 'Refine center & geometry')
  }
  return t(s.labelKey)
}

// === State / 状态 ===

const step = ref<CalibStep>('setup')
const stepIndex = computed(() => STEPS.value.findIndex(s => s.key === step.value))
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
  mode: 'calibrant',
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
  centerXPx: null,
  centerYPx: null,
})

// === Internal standard: picked ring + computed geometry / 内标：环点选与几何 ===
/**
 * Ring-standard points (internal-standard step 2): canvas clicks collect
 * `centerPoints` on ONE known ring; Enter / double-click / the panel's 拟合并
 * 计算几何 button submits them to the backend's `ring_standard` action, which
 * returns the full geometry. Also reused by the preview step (its fit circle
 * stays on the canvas). / 内标环点选（第 2 步）：画布点击在同一已知环上收集
 * centerPoints；回车 / 双击 / 面板「拟合并计算几何」提交给后端 ring_standard，
 * 返回完整几何。预览步继续复用（拟合圆继续显示在画布上）。
 */
const centerPoints = ref<Array<{ y: number; x: number }>>([])
/** Circle through the picked points (null below 3 points / degenerate). */
const centerFit = computed<CalibRingFit | null>(() => fitCircle(centerPoints.value))

// ── Direct-beam centroid (2026-10-21) / 直通光质心定心 ────────────────────────
// The user boxes the direct-beam spot (rect drag / polygon) → the backend's
// beam_center_com returns its intensity-weighted centroid → ring_standard then
// runs with the centre FIXED (≥2 ring points suffice). User flow mirrors the
// wizard: box first (确定坐标), then the 内标定标 part.
// 用户框出直通光斑（拖矩形 / 多折框）→ 后端 beam_center_com 返回强度加权质心
// → ring_standard 以固定中心运行（环上 ≥2 点即可）。流程：先框选定坐标，
// 再进行内标定标部分。
/** Armed region mode on the canvas (null = off). / 画布已武装的框选模式。 */
const comPickMode = ref<'rect' | 'poly' | null>(null)
/** Confirmed direct-beam centroid (sub-pixel). / 已确认的直通光质心（亚像素）。 */
const comCenter = ref<{ y: number; x: number } | null>(null)
/** Confirmed region outline echo (dashed on the canvas). / 已确认区域轮廓回显。 */
const comRegion = ref<CalibRegion | null>(null)
/** beam_center_com request in flight. / beam_center_com 请求进行中。 */
const comBusy = ref(false)
/** Branch chosen on the com mode's SECOND image (null = not chosen yet). The
 *  standard step then continues as 标样校正 or 内标定标 — both with the centre
 *  fixed by the centroid. / com 模式第二张图上选择的支路（null = 尚未选择）：
 *  标样步骤随后回到标样校正或内标定标——两者中心都由质心固定。 */
const comStandardMode = ref<'calibrant' | 'internal' | null>(null)
/** Session of the FIRST (direct-beam) image — the CoM runs against it. / 第一张
 *  （直通光）图的会话——质心针对它计算。 */
const comSessionId = ref<string | null>(null)
/** Dimensions of the direct-beam image, used to warn when the standard image
 *  has a different shape (pixel coordinates would not transfer). / 直通光图
 *  尺寸，用于在标样图尺寸不同时告警（像素坐标不再通用）。 */
const comBeamShape = ref<{ h: number; w: number } | null>(null)
/** Path of the FIRST (direct-beam) image — restored when going back. / 第一张
 *  （直通光）图路径——返回该步骤时恢复显示。 */
const comBeamPath = ref<string | null>(null)
/** The direct-beam session exists (its 载入并开始 succeeded). / 直通光会话已建立。 */
const beamReady = ref(false)
/** The standard session exists (setup2's 载入并开始 succeeded). / 标样会话已建立。 */
const standardReady = ref(false)

/** TRUE once the com flow owns a fixed centre for the standard branch. */
const comFixedCenter = computed(() =>
  setupForm.value.mode === 'com' && comCenter.value != null && comStandardMode.value != null,
)

/** Drop the confirmed centroid + outline (panel 清除). / 清除已确认质心与轮廓。 */
function clearComCenter(): void {
  comCenter.value = null
  comRegion.value = null
}

/**
 * A region was drawn on the canvas → ask the backend for its centre of mass;
 * on success the centroid becomes the fixed centre for ring_standard and the
 * armed mode disarms (one region at a time). Plain-clone the region — Vue
 * proxies cannot cross Electron IPC's structured clone (BUG C idiom).
 * 画布上画好区域 → 请求后端算质心；成功后质心成为 ring_standard 的固定中心，
 * 武装模式解除（一次一个区域）。区域逐字段浅拷贝——Vue 代理过不了 IPC
 * 结构化克隆（BUG C 惯用法）。
 */
async function onRegionSelected(region: CalibRegion): Promise<void> {
  const sid = comSessionId.value
  if (!sid) {
    toast.push({ title: t('calibration.com.title'), message: t('calibration.errors.noSession'), tone: 'error' })
    return
  }
  if (comBusy.value) return
  const plain: CalibRegion = region.kind === 'rect'
    ? {
        kind: 'rect',
        y0: region.y0, y1: region.y1, x0: region.x0, x1: region.x1,
      }
    : {
        kind: 'poly',
        points: region.points.map(p => ({ y: p.y, x: p.x })),
      }
  comBusy.value = true
  try {
    const data = await submitAndWait('calibration', {
      action: 'beam_center_com',
      sessionId: sid,
      region: plain,
    })
    const cy = numberOrNull(data.centerY)
    const cx = numberOrNull(data.centerX)
    if (cy == null || cx == null) throw new Error('beam_center_com returned no centre')
    comCenter.value = { y: cy, x: cx }
    comRegion.value = plain
    comPickMode.value = null
    if (origImageSize.value) {
      comBeamShape.value = { h: origImageSize.value.h, w: origImageSize.value.w }
    }
    toast.push({
      title: t('calibration.com.title'),
      message: t('calibration.com.done', { x: cx.toFixed(2), y: cy.toFixed(2) }),
      tone: 'success',
    })
  } catch (err) {
    toastError(t('calibration.com.title'), err, t('calibration.com.failed'))
  } finally {
    comBusy.value = false
  }
}

/**
 * Fit RMS of the picked points in px: mean of |distance_i − radius| (≥3 points
 * only, null otherwise). / 点选拟合 RMS（px）：各点到圆心的距离与半径之差的
 * 绝对值均值（仅 ≥3 点，否则 null）。
 */
const centerRmsPx = computed<number | null>(() => {
  const fit = centerFit.value
  if (!fit || centerPoints.value.length < 3) return null
  let sum = 0
  for (const p of centerPoints.value) {
    sum += Math.abs(Math.hypot(p.y - fit.cy, p.x - fit.cx) - fit.radiusPx)
  }
  return sum / centerPoints.value.length
})

/** True once ring_standard has produced a geometry → the ring step is done.
 *  ring_standard 成功产出几何后为 true → 内标步骤完成。 */
const ringApplied = ref(false)
/** ring_standard request in flight. / ring_standard 请求进行中。 */
const ringApplying = ref(false)
/** Summary of the LAST ring_standard response (panel result block). */
const ringResult = ref<CalibRingStandardResult | null>(null)
/** Known value of the picked ring — RAW text (parent-owned so the canvas
 *  Enter / double-click shortcut submits the same value). / 环已知数值原始文本。 */
const ringValueText = ref('')
/** Unit of the entered value (default q in nm⁻¹). / 数值单位（默认 q nm⁻¹）。 */
const ringUnit = ref<CalibRingUnit>('q_nm')
/**
 * True when the LAST ring_standard ran WITHOUT a ring value → the distance is
 * the session's initial guess (dist0), not a fitted one. Drives the warning in
 * the panel result, the preview readout and the export card, and is echoed
 * into the export toast. / 上次 ring_standard 未提供环数值 → 距离为会话初始
 * 猜测（dist0）而非拟合值。驱动面板结果、预览读数与导出卡片的警示，并回显到
 * 导出 toast。
 */
const ringDistDefaulted = ref(false)
/** Monotonic sequence guarding stale ring_standard responses (mode switch /
 *  new session must not let an old response write geometry into the wizard).
 *  递增序号，防陈旧 ring_standard 响应（切模式/换会话后旧响应不得写入几何）。 */
let ringSeq = 0

// === FIT2D-style zoomed second pick / FIT2D 式放大二次选点 ===
/** Zoom toggle (panel switch): when on, canvas clicks open the zoom window. */
const zoomEnabled = ref(false)
/** Zoom window visibility + the anchor click that opened it. */
const zoomOpen = ref(false)
const zoomAnchor = ref<{ row: number; col: number } | null>(null)

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
// 2026-10-22 用户反馈：默认 0.5 时 massif 峰识别容易过宽（cutoff 偏低、keep
// 偏多），默认降为 0.2，高级区（CalibPeakPanel 的 <details>）也已默认展开，
// 便于直接调灵敏度。
const sensitivity = ref(0.2)
// Ring-band half-width ±dr for ring_pick (2026-10-23 user feedback: it was a
// hidden 15 px backend constant; now user-settable in the peak panel).
// ring_pick 的环带半宽 ±dr（2026-10-23 用户反馈：原为后端隐藏常量 15px，
// 现在峰拾取面板里可调）。
const bandTolPx = ref(15)
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
/**
 * 点选初猜中心 mode (2026-10-20 feature): one canvas click sends the pixel to
 * the backend set_center action — it becomes the session's centre seed (and
 * the live geometry's poni1/poni2 once a refinement exists) while AUTO ring
 * numbers re-derive under the new coordinate system (user rings stay).
 * The mode is SINGLE-SHOT: after a successful set it disarms, so ring-guide
 * clicks resume immediately.
 * 点选初猜中心（2026-10-20 新功能）：画布单击把像素发给后端 set_center——
 * 写入会话中心种子（已有精修器时同时改其 poni1/poni2），自动环号按新坐标系
 * 立即重排（用户环号保留）。模式为一次性：设置成功即自动退出，画布点击
 * 恢复收集环引导点。
 */
const centerPicking = ref(false)
let centerSeq = 0

function toggleCenterPick(): void {
  centerPicking.value = !centerPicking.value
}

const centerPickHint = computed(() =>
  isZh.value ? '在图像上单击光束中心的大致位置（设置后自动退出该模式）' : 'Click the approximate beam centre on the image (the mode disarms after one set)',
)

/**
 * Send the clicked pixel as the initial-guess beam centre. The backend
 * re-derives AUTO ring numbers under the new centre (the centre defines the
 * 2θ coordinate system) and returns the refreshed geometry + peak table.
 * 把点击像素作为初猜光束中心发给后端。后端按新中心（中心决定 2θ 坐标系）
 * 重排自动环号，并返回刷新后的几何与峰表。
 */
async function setCenterAt(row: number, col: number): Promise<void> {
  if (!sessionActive.value) {
    toast.push({ title: t('calibration.title'), message: t('calibration.errors.noSession'), tone: 'error' })
    centerPicking.value = false
    return
  }
  const seq = ++centerSeq
  try {
    const data = await submitAndWait('calibration', sessionPayload('set_center', {
      y: row,
      x: col,
    }))
    if (seq !== centerSeq) return // superseded / 已被取代
    geometry.value = normalizeGeometry(data.geometry)
    if (Array.isArray(data.peaks) && data.peaks.length > 0) applyPeaksResponse(data)
    void refreshRingOverlay()
    const refreshed = numberOrNull(data.rings_refreshed) ?? 0
    const pos = `(${row.toFixed(0)}, ${col.toFixed(0)}) px`
    toast.push({
      title: isZh.value ? '初猜中心' : 'Initial centre',
      message: isZh.value
        ? `初猜中心已设为 ${pos}` + (refreshed > 0 ? `；${refreshed} 个自动环号已按新中心重排（您指定的环号保留）` : '')
        : `Initial centre set to ${pos}` + (refreshed > 0 ? `; ${refreshed} auto ring number(s) re-derived under the new centre (your picked rings kept)` : ''),
      tone: 'success',
    })
  } catch (err) {
    if (seq === centerSeq) toastError(t('calibration.title'), err, t('calibration.errors.loadFailed'))
  } finally {
    if (seq === centerSeq) centerPicking.value = false
  }
}

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
          ringUser: o.ring_user === true || o.ringUser === true,
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

/** Geometry: accepts display-unit fields or pyFAI SI units (m / rad).
 *  KEY FIX: the backend `_geometry_summary` emits `center_x_px` / `center_y_px`
 *  and `wavelength_A` (capital A) — the old pick lists read `center_x` /
 *  `centerX` and `wavelength_a`, so the beam-centre readout, the canvas
 *  crosshair and the preview step's wavelength row were silently null. Both
 *  spellings are now accepted (the backend keys first).
 *  键名修复：后端 _geometry_summary 发出的是 center_x_px / center_y_px 与
 *  wavelength_A（大写 A），旧代码读 center_x / centerX 与 wavelength_a，
 *  导致中心读数、画布十字与预览步波长行静默为 null。现两种拼写都接受。 */
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
    wavelengthA: numberOrNull(pick('wavelength_A', 'wavelength_a')) ?? m2A(pick('wavelength')),
    centerXPx: numberOrNull(pick('center_x_px', 'center_x', 'centerX')),
    centerYPx: numberOrNull(pick('center_y_px', 'center_y', 'centerY')),
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
  const idx = STEPS.value.findIndex(s => s.key === target)
  if (idx < 0 || idx > maxStep.value) return
  // Entering refine requires at least one peak (calibrant mode only — the
  // internal-standard wizard has no refine step at all).
  // 进入精修需要至少一个峰（仅标样模式——内标向导根本没有精修步）。
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
 * peaks = ≥4 peaks; refine = a finished refine run;
 * ring (internal) = a successful ring_standard fit; preview (internal) = a
 * geometry exists.
 * 下一步仅在当前步骤完成时可用：setup=会话已建且掩膜输入已应用（未过期）；
 * peaks=≥4 峰；refine=精修完成；ring（内标）=ring_standard 拟合成功；
 * preview（内标）=已有几何。
 */
const canGoNext = computed<boolean>(() => {
  switch (step.value) {
    case 'setup':
      // com mode's FIRST image only has to create the direct-beam session.
      // com 模式第一张图只需建立直通光会话。
      return setupForm.value.mode === 'com'
        ? beamReady.value
        : sessionActive.value && !maskStale.value
    // com step: a confirmed centroid is required to move on. / 需确认质心。
    case 'com': return comCenter.value != null && beamReady.value
    // com mode's SECOND image: its own session + applied mask inputs.
    // com 模式第二张图：自己的会话 + 掩膜输入已应用。
    case 'setup2': return standardReady.value && !maskStale.value
    case 'peaks': return peaks.value.length >= 4
    case 'refine': return chi2.value != null
    case 'ring': return ringApplied.value
    case 'preview': return geometry.value != null
    default: return false
  }
})

function goPrev(): void {
  const idx = stepIndex.value
  if (idx > 0) step.value = STEPS.value[idx - 1].key
}

function goNext(): void {
  if (!canGoNext.value) return
  const idx = stepIndex.value
  if (idx < 0 || idx >= STEPS.value.length - 1) return
  const next = STEPS.value[idx + 1].key
  // Entering the com mode's SECOND image: the standard frame is a DIFFERENT
  // file, so clear the path (forces a fresh pick) and hand the centroid over
  // as the setup's centre seed. Going back to 'com' restores the beam image.
  // 进入 com 模式第二张图：标样图是另一个文件，故清空路径（强制重选），并把
  // 质心作为 setup 的中心种子；返回 'com' 时恢复直通光图。
  if (step.value === 'com' && next === 'setup2') {
    setupForm.value = {
      ...setupForm.value,
      imagePath: '',
      centerXPx: comCenter.value?.x ?? null,
      centerYPx: comCenter.value?.y ?? null,
    }
    // The form's branch toggle defaults to 标样校正 — adopt that default HERE
    // so the step rail already shows the branch's steps (otherwise the list
    // stays at the 3-step head and the peaks/ring step is unreachable).
    // 表单的支路开关默认「标样校正」——此处即采用该默认值，使步骤栏立刻展开
    // 支路步骤（否则列表停在 3 步头部，峰拾取/内标步不可达）。
    if (comStandardMode.value == null) comStandardMode.value = 'calibrant'
    standardReady.value = false
  }
  unlockStep(idx + 1)
  step.value = next
}

// No existing i18n keys for the wizard nav buttons — inline bilingual for now.
// 向导导航按钮暂无 i18n 键 —— 内联双语（见最终报告缺失键清单）。
const isZh = computed(() => locale.value.startsWith('zh'))
const prevLabel = computed(() => (isZh.value ? '上一步' : 'Back'))
const nextLabel = computed(() => (isZh.value ? '下一步' : 'Next'))
const guideCountLabel = computed(() =>
  `${isZh.value ? '引导点' : 'guide pts'}: ${ringGuide.value.length}`,
)
/** Ring-step legend entry: points picked on the standard ring. */
const ringPointsLabel = computed(() =>
  `${t('calibration.ring.points')}: ${centerPoints.value.length}`,
)

/**
 * Canvas guide/fit props per step: peaks → ring guides; ring (internal
 * standard) → the standard-ring points; preview → only the fitted circle of
 * the already-picked ring stays visible (guides cleared).
 * 各步骤的画布引导点/拟合圆：峰拾取 → 环引导点；内标定标 → 内标环点；
 * 预览 → 仅保留已点环的拟合圆（引导点不再显示）。
 */
const canvasGuide = computed<Array<{ y: number; x: number }>>(() => {
  if (step.value === 'peaks') return ringGuide.value
  if (step.value === 'ring') return centerPoints.value
  return []
})

const canvasFit = computed<CalibRingFit | null>(() => {
  if (step.value === 'peaks') return ringFit.value
  if (step.value === 'ring' || step.value === 'preview') return centerFit.value
  return null
})

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
  // Re-picking the SAME path must also (re)load: after a failed load
  // displayFilePath already points at it, and skipping the retry left the
  // canvas blank forever with no way to recover.
  // 选图即显示：无需先点“载入并开始”（该按钮仅创建标定会话）。
  // 重复选择同一路径也必须（重新）加载：加载失败后 displayFilePath 已指向
  // 该文件，跳过重试会让画布永远空白且无法恢复。
  imageFileName.value = path.split(/[/\\]/).pop() ?? path
  // Fresh pick → reset display caches so its auto-contrast seeds the clim bar.
  // 重新选图 → 重置显示缓存，使自动对比度作为 clim 初值。
  climInitialized.value = false
  autoContrast.value = null
  origImageSize.value = null
  void loadDisplayImage(path).catch((err) => {
    // Task-level failures surface via the onTaskError toast; this catch covers
    // submitTask itself rejecting (e.g. the Python service is not running) —
    // previously swallowed, leaving a blank canvas with no feedback.
    // 任务级失败由 onTaskError 提示；此处兜底 submitTask 本身被拒（如 Python
    // 服务未运行）——此前被静默吞掉，画布空白且无任何提示。
    toastError(t('calibration.title'), err, t('calibration.errors.loadFailed'))
  })
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
  const isBeamSetup = setupForm.value.mode === 'com' && step.value === 'setup'
  const isStandardSetup = setupForm.value.mode === 'com' && step.value === 'setup2'
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
      // Beam-centre seed (ring fit / .poni / direct-beam centroid) → backend
      // first-guess poni1/poni2. Both coordinates are required together.
      // 束流中心种子（圆环拟合 / .poni / 直通光质心）→ 后端首猜 poni1/poni2；
      // 两个坐标必须成对提供。
      ...(payload.centerX != null && payload.centerY != null
        ? { centerX: payload.centerX, centerY: payload.centerY }
        : {}),
      // com mode, SECOND image: pin the centre + rotations, optimise dist only.
      // com 模式第二张图：钉住中心与旋转角，只优化距离。
      ...(payload.fixedCenter ? { fixedCenter: true } : {}),
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
    // Ring picking (internal standard) is per-session state: a fresh session
    // starts with no points and no previous fit. ringSeq++ supersedes any
    // ring_standard still in flight against the PREVIOUS session.
    // 环点选（内标）是会话内状态：新会话不含任何点与既有拟合。ringSeq++
    // 作废仍在途、针对上一个会话的 ring_standard。
    ringSeq++
    centerPoints.value = []
    ringApplied.value = false
    ringResult.value = null
    ringDistDefaulted.value = false
    zoomOpen.value = false
    zoomAnchor.value = null

    if (isBeamSetup) {
      // DIRECT-BEAM image: this session only serves the CoM. The centroid,
      // the region and the branch choice all start over.
      // 直通光图：该会话只服务质心计算；质心、区域与支路选择全部重新开始。
      comSessionId.value = sid
      comBeamPath.value = payload.filePath
      beamReady.value = true
      standardReady.value = false
      comStandardMode.value = null
      comPickMode.value = null
      clearComCenter()
      step.value = 'com'
      return
    }
    if (isStandardSetup) {
      // STANDARD image: the centre came from the first image. A shape change
      // would silently shift that centre, so warn loudly (pixel coordinates
      // only transfer between frames of the same detector layout).
      // 标样图：中心来自第一张图。尺寸变化会让该中心悄悄偏移，故显著告警
      // （像素坐标仅在相同探测器布局的帧之间通用）。
      standardReady.value = true
      const shape = origImageSize.value
      if (shape && comBeamShape.value
          && (shape.h !== comBeamShape.value.h || shape.w !== comBeamShape.value.w)) {
        toast.push({
          title: t('calibration.com.title'),
          message: t('calibration.com.shapeMismatch', {
            bw: comBeamShape.value.w, bh: comBeamShape.value.h,
            sw: shape.w, sh: shape.h,
          }),
          tone: 'warning',
        })
      }
      const nextStep: CalibStep = comStandardMode.value === 'internal' ? 'ring' : 'peaks'
      // The chosen branch ADDS steps to the rail — unlock the one we land on.
      // 选定支路会扩展步骤栏——解除落地步骤的锁定。
      const nextIdx = STEPS.value.findIndex(s => s.key === nextStep)
      if (nextIdx >= 0) unlockStep(nextIdx)
      step.value = nextStep
      return
    }

    comPickMode.value = null
    clearComCenter()
    // The next step depends on the mode: calibrant mode goes peak picking,
    // internal-standard mode goes straight to 内标定标.
    // 下一步随模式分岔：标样模式去峰拾取，内标模式直接进「内标定标」。
    step.value = setupForm.value.mode === 'internal' ? 'ring' : 'peaks'
  } catch (err) {
    toastError(t('calibration.title'), err, t('calibration.errors.loadFailed'))
  } finally {
    setupLoading.value = false
  }
}

/**
 * Branch switch on the com mode's SECOND image (标样校正 ↔ 内标定标): the two
 * branches open DIFFERENT backend sessions (a calibrant session vs a bare
 * internal-standard one), so an existing standard session is invalidated and
 * the user re-runs 载入并开始 — the direct-beam centre is preserved.
 * com 模式第二张图的支路切换（标样校正 ↔ 内标定标）：两支路的后端会话类型不同
 * （含标样 vs 纯内标），既有标样会话作废，需重新「载入并开始」——直通光中心
 * 保留。
 */
function onStandardModeChange(mode: 'calibrant' | 'internal'): void {
  if (comStandardMode.value === mode) return
  comStandardMode.value = mode
  if (standardReady.value) {
    ringSeq++
    sessionId.value = null
    sessionActive.value = false
    standardReady.value = false
    resetSessionResults()
    // The step list changes with the branch — keep the user on setup2 and
    // lock the branch-specific steps until the standard image is reloaded.
    // 步骤列表随支路变化——保持在 setup2，并在重新载入标样图前锁住支路步骤。
    maxStep.value = Math.min(maxStep.value, STEPS.value.findIndex(s => s.key === 'setup2'))
    step.value = 'setup2'
    toast.push({
      title: t('calibration.com.title'),
      message: t('calibration.com.branchChanged'),
      tone: 'info',
    })
  }
}

/**
 * Mode switch (标样校正 ↔ 内标定标 ↔ 直通光定心) is MUTUALLY EXCLUSIVE: the
 * wizards have different steps and different backends, so an existing
 * session/geometry from the other mode is meaningless. Reset everything and
 * require a fresh 载入并开始.
 * 模式切换（标样校正 ↔ 内标定标 ↔ 直通光定心）互斥：向导步骤与后端路径不同，
 * 另一模式的会话/几何毫无意义。全部重置，需重新「载入并开始」。
 */
watch(() => setupForm.value.mode, () => {
  // Supersede any in-flight ring_standard: its response belongs to the other
  // mode's session. / 作废在途的 ring_standard：响应属于另一模式的会话。
  ringSeq++
  sessionId.value = null
  sessionActive.value = false
  resetSessionResults()
  step.value = 'setup'
  maxStep.value = 0
  centerPoints.value = []
  ringApplied.value = false
  ringApplying.value = false
  ringResult.value = null
  ringDistDefaulted.value = false
  ringValueText.value = ''
  zoomOpen.value = false
  zoomAnchor.value = null
  comPickMode.value = null
  clearComCenter()
  comStandardMode.value = null
  comSessionId.value = null
  comBeamPath.value = null
  comBeamShape.value = null
  beamReady.value = false
  standardReady.value = false
})

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
    // BUG fix (键位不匹配): the backend returns {"status":"ok","seed":{…}} —
    // the wizard used to read the keys off the TOP level, so dist/wavelength/
    // pixel/centre were all silently dropped. Read the nested seed (falling
    // back to the flat shape for robustness).
    // 修复键位不匹配：后端返回的是嵌套的 "seed" 对象，此前向导按顶层读取，
    // 距离/波长/像素/中心全部静默丢失。此处读 seed（并兼容扁平结构）。
    const seed = (((data as Record<string, unknown>)?.seed ?? data) ?? {}) as Record<string, unknown>
    const patch: Partial<CalibSetupModel> = {}
    const distMm = numberOrNull(seed.dist_mm) ?? numberOrNull(seed.distance_mm)
    const wavelengthA = numberOrNull(seed.wavelength_A) ?? numberOrNull(seed.wavelength_a)
    const pixelUm = numberOrNull(seed.pixel_um) ?? numberOrNull(seed.pixel_size_um)
    if (distMm != null) patch.distGuessMm = distMm
    if (wavelengthA != null) patch.wavelengthA = wavelengthA
    if (pixelUm != null) {
      patch.pixelSizeUm = pixelUm
      // An explicit pixel size from the PONI overrides the detector preset.
      // PONI 提供的像素尺寸优先于探测器预设。
      patch.detector = ''
    }
    // Centre from the .poni (px, x = poni2/pixel2 column, y = poni1/pixel1
    // row) → setupForm.centerXPx/YPx, forwarded with the setup payload as the
    // backend's first-guess centre. It describes the DETECTOR geometry, not
    // the picture, so it deliberately survives an image change.
    // PONI 中的中心（像素）→ setupForm.centerXPx/YPx，随 setup 载荷下发为后端
    // 首猜中心。它描述的是探测器几何而非图像，故换图时特意保留。
    const cx = numberOrNull(seed.center_x_px) ?? numberOrNull(seed.center_x) ?? numberOrNull(seed.centerX)
    const cy = numberOrNull(seed.center_y_px) ?? numberOrNull(seed.center_y) ?? numberOrNull(seed.centerY)
    if (cx != null) patch.centerXPx = cx
    if (cy != null) patch.centerYPx = cy
    if (Object.keys(patch).length > 0) {
      setupForm.value = { ...setupForm.value, ...patch }
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

  // A NEW file replaces whatever is on screen: once its load is accepted, drop
  // the previous picture — and if the load FAILS, drop it as well, so the
  // canvas never keeps showing the old file under the new file's name.
  // 换新文件即替换屏幕上的旧图：加载被接受后先清旧图；加载失败同样清掉，
  // 画布绝不能顶着新文件名继续显示旧文件。
  const isNewFile = displayFilePath.value !== filePath
  const dropDisplayedPicture = (): void => {
    if (imageSrc.value?.startsWith('blob:')) URL.revokeObjectURL(imageSrc.value)
    imageSrc.value = null
  }

  const { taskId } = await transport.submitTask('mask_maker', {
    action: 'load_preview',
    filePath,
    frame: 0,
    settings: buildRenderSettings(),
    // PERFORMANCE (大图加载慢): the wizard consumes the PNG (binary frame →
    // blob URL) and the metadata only — the raw imageData matrix would double
    // the payload for nothing. Explicit false; the backend default is NOT
    // changed (unknown consumers keep it). / 性能：向导只消费 PNG（二进制帧 →
    // blob URL）与元数据，原始 imageData 矩阵白白翻倍负载。显式 false；不改
    // 后端默认值（未知消费方不受影响）。
    includeImageData: false,
  })
  displayFilePath.value = filePath
  if (isNewFile) dropDisplayedPicture()

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
    if (isNewFile) dropDisplayedPicture()
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
    void loadDisplayImage(displayFilePath.value).catch((err) => {
      toastError(t('calibration.title'), err, t('calibration.errors.loadFailed'))
    })
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
  if (displayFilePath.value) {
    void loadDisplayImage(displayFilePath.value).catch((err) => {
      toastError(t('calibration.title'), err, t('calibration.errors.loadFailed'))
    })
  }
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
    // ringUser travels BOTH ways: user-owned rings (完成本环 / 整环改号)
    // survive refine's automatic refresh on the backend.
    // ringUser 随载荷往返：用户所有的环号在后端精修的自动重排中被保留。
    peaks: peaks.value.map(p => ({ y: p.y, x: p.x, ring: p.ring ?? null, ringUser: p.ringUser === true })),
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
    peaks.value.map(p => (p.ring === oldRing ? { ...p, ring: newRing, ringUser: true } : p)),
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
// INTERNAL STANDARD (ring step): clicks collect the standard-ring points
// instead — through the FIT2D-style zoom window when the zoom toggle is on.
// 内标（ring 步）：点击改为收集内标环点——开启放大时先经 FIT2D 式放大窗。
function onCanvasClick(pixel: { row: number; col: number }): void {
  // The com step owns the canvas for region drawing only — a stray click must
  // never become a guide point. / com 步骤的画布只用于框选——散点绝不当引导点。
  if (step.value === 'com') return
  if (step.value === 'ring') {
    if (zoomEnabled.value) {
      // One zoom window at a time. / 同一时间只开一个放大窗。
      zoomAnchor.value = { row: pixel.row, col: pixel.col }
      zoomOpen.value = true
      return
    }
    pushRingPoint(pixel.row, pixel.col)
    return
  }
  // 点选初猜中心 armed: this click sets the centre instead of a guide point.
  // 点选初猜中心激活时：本击设置中心，而非收集引导点。
  if (centerPicking.value) {
    void setCenterAt(pixel.row, pixel.col)
    return
  }
  ringGuide.value = [...ringGuide.value, { y: pixel.row, x: pixel.col }]
}

/**
 * Append a standard-ring point, ignoring a click that lands on (nearly) the
 * previous one. A double-click without the zoom window fires click twice at
 * the same pixel, which would silently double that point's weight in the
 * circle fit — this collapses the duplicate (deliberate manual picks are never
 * within 0.5 px of each other). / 追加内标环点；与上一点（几乎）重合的点击
 * 直接忽略：未开放大时双击会各触发一次 click、产生重合点，使该点在圆拟合中
 * 权重翻倍；此处去重（人工点选不会落在 0.5 px 内）。
 */
function pushRingPoint(row: number, col: number): void {
  const last = centerPoints.value[centerPoints.value.length - 1]
  if (last && Math.hypot(last.y - row, last.x - col) < 0.5) return
  centerPoints.value = [...centerPoints.value, { y: row, x: col }]
}

/** Second pick inside the zoom window → push the sub-pixel coordinate. */
function onZoomConfirm(pick: { row: number; col: number }): void {
  pushRingPoint(pick.row, pick.col)
  zoomOpen.value = false
  zoomAnchor.value = null
}

function onZoomCancel(): void {
  zoomOpen.value = false
  zoomAnchor.value = null
}

/** Double-click finishes the current ring (its clicks already added points);
 *  on the internal-standard step it applies the ring fit once ≥3 points exist.
 *  双击完成本环（点击已添加引导点）；内标步 ≥3 点时执行内标拟合。 */
function onCanvasDblClick(_pixel: { row: number; col: number }): void {
  if (step.value === 'ring') {
    if (centerPoints.value.length >= 3) void applyRingStandard()
    return
  }
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
      // 2026-10-23: the band half-width and the sensitivity slider now BOTH
      // reach the band harvest (they were invisible to ring_pick before).
      // 环带半宽与灵敏度现在都传入环带收峰（此前 ring_pick 看不到它们）。
      tolPx: bandTolPx.value,
      sensitivity: sensitivity.value,
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
      // The stamp is USER-OWNED: refine's refresh must keep it (0.3.3 bug).
      // 直接打上当前环号（后端已回带，此处兜底强制）；该环号为用户所有，
      // 精修的自动重排必须保留（0.3.3 缺陷修复）。
      p.ring = assignRing
      p.ringUser = true
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

// === Internal standard: fit one known ring → full geometry / 内标：单环算几何 ===

/**
 * Parsed ring value. null now carries TWO meanings the caller must separate:
 * an EMPTY input → default distance (submit without a value); a NON-empty but
 * unparseable / non-positive input → invalid, warn the user.
 * 解析后的环数值。null 有两种含义，调用方必须区分：输入为空 → 使用默认距离
 * （不带 value 提交）；非空但无法解析 / 非正数 → 非法，提示用户。
 */
function parsedRingValue(): number | null {
  const num = parseFloat(ringValueText.value)
  return Number.isFinite(num) ? num : null
}

/**
 * {mm} figure for the default-distance warning texts: prefers the last
 * ring_standard response's SD, falls back to the current geometry readout.
 * 警示文案中的 {mm} 数值：优先取上次 ring_standard 响应的 SD，回退到当前
 * 几何读数。
 */
const ringDefaultDistText = computed<string>(() => {
  const mm = numberOrNull(ringResult.value?.distMm) ?? numberOrNull(geometry.value?.distMm)
  return mm != null && Number.isFinite(mm) ? mm.toFixed(1) : '?'
})

/**
 * Submit the picked ring (+ its OPTIONAL known value) to the backend's
 * `ring_standard` action: the backend Kåsa-fits the points and, with a value,
 * converts it to the ring's 2θ and derives the sample-detector distance; with
 * the value LEFT EMPTY only the beam centre is calibrated and the distance
 * defaults to the session's initial guess (dist0) — the response flags it via
 * `distDefaulted` and the exported .poni carries a Dist-default annotation.
 * The WHOLE geometry comes back (session["gr"] included), so export_poni and
 * integrate_preview work unchanged. On success the returned geometry feeds the
 * preview step's readout, the canvas crosshair and canGoNext; failure only
 * toasts.
 * 把点选环（及其可选已知数值）提交后端 ring_standard：后端做 Kåsa 拟合，提供
 * 数值时换算为该环 2θ 并反算样品-探测器距离；数值留空时仅标定束流中心，距离
 * 取会话初始猜测（dist0）——响应以 `distDefaulted` 标记，导出的 .poni 附
 * Dist-default 注释。完整几何回传（含 session["gr"]），export_poni 与
 * integrate_preview 无需改动即可用。成功后回传几何供预览步读数、画布十字与
 * canGoNext；失败仅提示。
 */
async function applyRingStandard(): Promise<void> {
  if (ringApplying.value) return
  if (!sessionActive.value) {
    toast.push({ title: t('calibration.ring.title'), message: t('calibration.errors.noSession'), tone: 'error' })
    return
  }
  // With the direct-beam centroid FIXED, ≥2 ring points suffice (the centre
  // no longer comes from the circle fit). / 直通光质心固定中心后环上 ≥2 点
  // 即可（中心不再来自圆拟合）。
  const fixedCom = comFixedCenter.value ? comCenter.value : null
  const minRingPoints = fixedCom ? 2 : 3
  if (centerPoints.value.length < minRingPoints || (!fixedCom && !centerFit.value)) {
    toast.push({
      title: t('calibration.ring.title'),
      message: fixedCom ? t('calibration.ring.needPointsCom') : t('calibration.ring.needPoints'),
      tone: 'warning',
    })
    return
  }
  // Empty input → default distance (submit WITHOUT a value); a non-empty
  // value that is not a positive number is refused here.
  // 输入为空 → 使用默认距离（不带 value 提交）；非空但非正数在此拒绝。
  const value = parsedRingValue()
  if (ringValueText.value.trim() !== '' && (value == null || !(value > 0))) {
    toast.push({
      title: t('calibration.ring.title'),
      message: t('calibration.ring.needValue'),
      tone: 'warning',
    })
    return
  }
  // Plain-clone the points: Vue reactive proxies cannot cross Electron's IPC
  // structured clone (BUG C). / 逐点浅拷贝为普通对象（BUG C：代理无法过 IPC）。
  const pts = centerPoints.value.map(p => ({ y: p.y, x: p.x }))
  // No value → omit BOTH keys: the backend treats a missing value as the
  // default-distance branch and skips unit validation.
  // 无数值 → 两个键都省略：后端将缺失的 value 视为默认距离分支并跳过单位校验。
  const extra: Record<string, unknown> = value != null
    ? { value, unit: ringUnit.value }
    : {}
  // Fixed direct-beam centre (2026-10-21): ring_standard keeps the centroid
  // and derives only the radius from the points. / 固定直通光中心：ring_standard
  // 保留质心，仅由点选推半径。
  if (fixedCom) extra.center = { y: fixedCom.y, x: fixedCom.x }
  // Sequence guard (same idiom as integSeq): a response that comes back after
  // the mode was switched / a new session was started must NOT write its
  // geometry into the current wizard. Bumped only when the request really is
  // sent, so a rejected call can never orphan an in-flight spinner.
  // 序号守卫（与 integSeq 同法）：切模式 / 换会话之后才回来的旧响应绝不写入
  // 当前向导的几何。仅在真正发出请求时自增，被拒的调用不会让在途请求的
  // 进行中标志悬空。
  const seq = ++ringSeq
  ringApplying.value = true
  try {
    const data = await submitAndWait('calibration', sessionPayload('ring_standard', {
      points: pts,
      ...extra,
    }))
    if (seq !== ringSeq) return // superseded / 已被取代
    const distDefaulted = data.distDefaulted === true
    ringApplied.value = true
    ringDistDefaulted.value = distDefaulted
    ringResult.value = {
      centerXPx: numberOrNull(data.centerXPx),
      centerYPx: numberOrNull(data.centerYPx),
      radiusPx: numberOrNull(data.radiusPx),
      rmsPx: numberOrNull(data.rmsPx),
      tthDeg: numberOrNull(data.tthDeg),
      distMm: numberOrNull(data.distMm),
      distDefaulted,
    }
    // The computed geometry takes the same slot a refine result would: the
    // preview readout, the magenta canvas crosshair and the export path all
    // read `geometry`. / 算得的几何占用与精修相同的位置：预览读数、画布洋红
    // 十字与导出路径都读 geometry。
    geometry.value = normalizeGeometry(data.geometry)
    toast.push({
      title: t('calibration.ring.title'),
      // Defaulted → append the default-distance note so the user cannot miss
      // that the SD was never calibrated from a ring value.
      // 默认距离时追加提示，确保用户不会漏看「SD 未经环数值标定」。
      message: distDefaulted
        ? `${t('calibration.ring.done')} ${t('calibration.ring.doneDefaultDist', { mm: ringDefaultDistText.value })}`
        : t('calibration.ring.done'),
      tone: 'success',
    })
  } catch (err) {
    if (seq === ringSeq) {
      toastError(t('calibration.ring.title'), err, t('calibration.errors.loadFailed'))
    }
  } finally {
    // Never clear a newer request's spinner / 不清除更新请求的进行中标志。
    if (seq === ringSeq) ringApplying.value = false
  }
}

// ── Ring-fit invalidation / 内标拟合失效 ─────────────────────────────────────
// The fitted geometry is only meaningful for the EXACT ring and value it came
// from: adding / removing a point or editing the value or its unit re-opens
// the step (Next disabled, the panel's result block cleared) until the user
// runs 拟合并计算几何 again. Every point-set mutation replaces the whole ref,
// so a shallow watch fires on all of them.
// 拟合出的几何只对当初那个环与那个数值成立：增删点、改数值或改单位都重新
// 打开该步骤（Next 禁用、面板结果区清空），直到再次「拟合并计算几何」。
// 点集的任何变更都是整体替换 ref，浅 watch 即可覆盖。
watch(centerPoints, invalidateRingFit)
watch([ringValueText, ringUnit], invalidateRingFit)
// A new/removed direct-beam centroid redefines the centre the fit would use —
// the previous fit result is stale either way. / 质心新增或清除都改变了拟合
// 所用中心——既有拟合结果一律失效。
watch(comCenter, invalidateRingFit)

function invalidateRingFit(): void {
  ringApplied.value = false
  ringResult.value = null
  ringDistDefaulted.value = false
}

// A new image invalidates the PICKED RING (its points, its value and any
// previous fit — the invalidation watcher above clears the fit state). The
// .poni-seeded centre in setupForm.centerXPx/YPx belongs to the detector
// geometry, not to the picture, and survives an image change.
// 换图后旧圆环作废（点选、数值与既有拟合——拟合状态由上面的失效 watcher
// 清理）。setupForm.centerXPx/YPx 里的 .poni 种子中心属于探测器几何而非图像，
// 换图保留。
watch(() => setupForm.value.imagePath, () => {
  centerPoints.value = []
  ringValueText.value = ''
  // Only the FIRST (direct-beam) image owns the centroid; the standard image
  // on setup2 must keep it (its whole purpose is to be reused there).
  // 只有第一张（直通光）图拥有质心；setup2 的标样图必须保留它（复用它正是
  // 该步骤的目的）。
  if (setupForm.value.mode !== 'com' || step.value === 'setup') {
    clearComCenter()
    comPickMode.value = null
  }
})

// Entering the internal-standard preview step refreshes the 1D/2D integration
// preview once (mirror of the refine step's refresh-on-refine) — the backend
// has session["gr"] since ring_standard succeeded. / 进入内标预览步时刷新一次
// 1D/2D 积分预览（对标精修步的刷新）；ring_standard 成功后后端已持有
// session["gr"]。
watch(step, (s) => {
  if (s === 'preview') void refreshIntegrationPreview()
  // Region selection only exists on the com step — leaving it disarms any
  // pending draft. / 区域框选只属于 com 步骤——离开即解除武装。
  if (s !== 'com') comPickMode.value = null
  // Going BACK to the com step must show the direct-beam frame again (the
  // standard image may have replaced it on screen). / 返回 com 步骤时必须重新
  // 显示直通光图（屏幕上可能已换成标样图）。
  if (s === 'com' && comBeamPath.value && displayFilePath.value !== comBeamPath.value) {
    void loadDisplayImage(comBeamPath.value).catch(() => { /* toast inside */ })
  }
})

/**
 * A NEW/CHANGED direct-beam centroid invalidates an already-created standard
 * session: that session baked the OLD centre into poni1/poni2, and the whole
 * point of this mode is "centre fixed, distance optimised". Send the user back
 * to setup2 for a reload (their centre is preserved).
 * 直通光质心新增/改变会使已建立的标样会话失效：该会话已把旧中心写进
 * poni1/poni2，而本模式的全部意义就是「中心固定、只优化距离」。把用户带回
 * setup2 重新载入（质心保留）。
 */
watch(comCenter, (cur, prev) => {
  if (!standardReady.value) return
  if (cur?.x === prev?.x && cur?.y === prev?.y) return
  ringSeq++
  sessionId.value = null
  sessionActive.value = false
  standardReady.value = false
  resetSessionResults()
  if (step.value !== 'com' && step.value !== 'setup' && step.value !== 'setup2') {
    step.value = 'setup2'
  }
  toast.push({
    title: t('calibration.com.title'),
    message: t('calibration.com.centerChanged'),
    tone: 'info',
  })
})

/** Remove radius in image pixels — generous enough for zoomed-out clicking. */
const REMOVE_RADIUS_PX = 15

function onCanvasRemove(pixel: { row: number; col: number }): void {
  // Internal-standard step: right-click / Alt removes the NEAREST ring point.
  // 内标步：右键 / Alt 删除最近的环点。
  if (step.value === 'ring') {
    let cIdx = -1
    let cD2 = REMOVE_RADIUS_PX * REMOVE_RADIUS_PX
    centerPoints.value.forEach((p, i) => {
      const d2 = (p.y - pixel.row) ** 2 + (p.x - pixel.col) ** 2
      if (d2 <= cD2) {
        cD2 = d2
        cIdx = i
      }
    })
    if (cIdx < 0) return
    centerPoints.value = centerPoints.value.filter((_, i) => i !== cIdx)
    return
  }
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
    // FIXED-CENTRE session (com mode): the direct-beam centroid owns the
    // centre and the rotations, so ONLY dist may be free — enforced here as
    // well as visually in the panel (and again in the backend).
    // 固定中心会话（com 模式）：中心与旋转角归直通光质心所有，只有 dist 可
    // 放开——界面与后端各再兜一层。
    const free = comFixedCenter.value
      ? { dist: true, poni1: false, poni2: false, rot1: false, rot2: false, rot3: false, wavelength: false }
      : { ...freeFlags.value }
    const data = await submitAndWait('calibration', sessionPayload('refine', {
      free,
      passes: payload.passes,
    }))

    chi2.value = numberOrNull(data.chi2 ?? data.chi_square)
    geometry.value = normalizeGeometry(data.geometry)
    residuals.value = normalizeResiduals(data.residuals)
    converged.value = typeof data.converged === 'boolean' ? data.converged : null
    exportResult.value = null

    // Refine re-assigns ring numbers from the CURRENT geometry before fitting
    // (BUGFIX 2026-10-13): apply the refreshed peak table and tell the user how
    // many were corrected, so a stale assignment (no 刷新环号 clicked) can no
    // longer silently poison the refinement. / 精修前已按当前几何自动重排环号：
    // 应用刷新后的峰表并提示修正数量——未点「刷新环号」的旧分配不会再悄悄
    // 毁掉精修。
    if (Array.isArray(data.peaks)) applyPeaksResponse(data)
    const refreshed = numberOrNull(data.rings_refreshed) ?? 0
    if (refreshed > 0) {
      toast.push({
        title: t('calibration.peaks.title'),
        message: isZh.value
          ? `精修前已按当前几何自动刷新环号（修正 ${refreshed} 个峰），详见峰表`
          : `Ring numbers auto-refreshed before refining (${refreshed} peaks corrected); see the peak table`,
        tone: 'info',
      })
    }

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
  // Theoretical rings need a calibrant — internal-standard sessions have none
  // (the canvas draws the wizard's own fit circle instead, also on the
  // preview step). / 理论环来自标样——内标会话没有（画布改为画向导自身的
  // 拟合圆，预览步同样如此）。
  if (setupForm.value.mode === 'internal') return
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
// The internal-standard geometry is COMPUTED (ring_standard), never refined —
// the title says which geometry the preview shows.
// 内标几何是算出来的（ring_standard）而非精修——标题区分当前来源。
const integTitleLabel = computed(() =>
  setupForm.value.mode === 'internal'
    ? (isZh.value ? '标定图积分预览（内标几何）' : 'Calibrant integration preview (internal-standard geometry)')
    : (isZh.value ? '标定图积分预览（当前精修几何）' : 'Calibrant integration preview (current geometry)'),
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
      // savePath first: the backend appends a missing .poni extension, so the
      // echoed path is where the file ACTUALLY landed, not the raw input.
      // savePath 优先：后端会补全缺失的 .poni 后缀，回显路径是文件真实落盘
      // 位置，而非原始输入。
      path: stringOrNull(data.savePath) ?? stringOrNull(data.path) ?? stringOrNull(data.saved_path) ?? savePath,
      citation: normalizeCitation(data.citation),
    }
    toast.push({
      title: t('calibration.export.title'),
      // Default-distance geometry (internal standard, no ring value) → the
      // success toast must repeat the annotation note (user request).
      // 默认距离几何（内标、无环数值）→ 成功 toast 须重复标注提示（用户要求）。
      message: ringDistDefaulted.value
        ? `${t('calibration.export.saved')} ${t('calibration.ring.exportToastNote', { mm: ringDefaultDistText.value })}`
        : t('calibration.export.saved'),
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
 * route to /workspace/integrate-1d?poni=<encoded path> with a freshly
 * exported .poni. When the user already exported under their own name, that
 * SAME path is re-exported (backend truncates, so it holds the current
 * geometry) — the produced poni keeps the user's naming. Only a never-named
 * session falls back to export_poni autoSave (unique temp file).
 * 无精修结果或自动保存失败时退回普通跳转。
 */
async function goIntegrate(): Promise<void> {
  if (!sessionActive.value || geometry.value == null || exporting.value) {
    void router.push('/workspace/integrate-1d')
    return
  }
  exporting.value = true
  try {
    const namedPath = stringOrNull(exportResult.value?.path)
    const data = await submitAndWait(
      'calibration',
      sessionPayload(
        'export_poni',
        namedPath ? { savePath: namedPath } : { autoSave: true },
      ),
    )
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

/** Right-column calibrant readout: '—' in internal-standard mode (no
 *  calibrant exists there). / 右列标样名：内标模式显示 '—'（无标样）。 */
const calibrantLabel = computed(() =>
  setupForm.value.mode === 'internal'
    ? ''
    : (setupForm.value.calibrantPath.trim() || setupForm.value.calibrant || ''),
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

// === Internal-standard preview readout helpers / 内标预览读数辅助 ===
// The preview step shows a COMPACT read-only geometry block (no refinement, no
// χ²), mirroring CalibRefinePanel's crp-geometry rows without touching it.
// 预览步显示精简只读几何块（无精修、无 χ²），版式对标 CalibRefinePanel 的
// crp-geometry，但不改动该组件。

/** Highlighted final centre (px), same value as the canvas crosshair. */
const previewCenterText = computed(() => {
  const g = geometry.value
  if (!g || g.centerXPx == null || g.centerYPx == null
      || !Number.isFinite(g.centerXPx) || !Number.isFinite(g.centerYPx)) return '—'
  return `(${g.centerXPx.toFixed(2)}, ${g.centerYPx.toFixed(2)})`
})

/** Plain-language meaning per geometry row (inline bilingual, mirrors
 *  CalibRefinePanel's wording). / 每行读数的中文释义（内联双语）。 */
function geoMeaning(key: 'dist' | 'poni1' | 'poni2' | 'rot1' | 'rot2' | 'rot3' | 'wavelength'): string {
  const zh: Record<string, string> = {
    dist: '样品距离',
    poni1: '中心 y (行)',
    poni2: '中心 x (列)',
    rot1: '俯仰角（绕 x 轴）',
    rot2: '偏摆角（绕 y 轴）',
    rot3: '面内旋转（绕光轴）',
    wavelength: '波长',
  }
  const en: Record<string, string> = {
    dist: 'distance',
    poni1: 'beam center y',
    poni2: 'beam center x',
    rot1: 'tilt around x',
    rot2: 'tilt around y',
    rot3: 'in-plane roll',
    wavelength: 'wavelength',
  }
  return isZh.value ? zh[key] : en[key]
}

/** Numeric row formatter (mm / ° keep 4 decimals like CalibRefinePanel). */
function formatGeo(value: number | null | undefined, unit: string): string {
  if (value == null || !Number.isFinite(value)) return '—'
  return `${value.toFixed(unit === 'px' ? 2 : 4)} ${unit}`
}

// === Lifecycle ===

/** Enter finishes the CURRENT ring — or, on the internal-standard step,
 *  applies the ring-standard fit — and is ignored while typing in a form
 *  control. / 回车完成本环；内标步则执行内标拟合；在表单控件内输入时不拦截。 */
function onKeydown(e: KeyboardEvent): void {
  if (e.key !== 'Enter' || e.repeat) return
  // The FIT2D zoom window owns Enter/Esc while it is open. This window-level
  // listener registers FIRST (the modal adds its own on mount), so without
  // this guard Enter during a zoom pick would run applyRingStandard on the
  // STALE point set before the modal's own Enter ever appends the new point.
  // 放大窗打开时 Enter/Esc 归其所有。本监听先于弹窗注册（弹窗在其挂载时才
  // 加监听），缺此守卫会让回车先用旧点集 applyRingStandard，弹窗自己的回车
  // 才追加新点——顺序错乱。
  if (zoomOpen.value) return
  const target = e.target as HTMLElement | null
  if (target && ['INPUT', 'SELECT', 'TEXTAREA', 'BUTTON'].includes(target.tagName)) return
  if (step.value === 'ring') {
    if (centerPoints.value.length < 3) return
    e.preventDefault()
    void applyRingStandard()
    return
  }
  if (step.value !== 'peaks') return
  if (ringPicking.value || ringGuide.value.length < 3) return
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
  /* Win10 矮视口修复（2026-10-22）：中栏原先没有滚动容器，画布下方的
     1D/2D 积分预览被 .app-shell 的 overflow:hidden 直接裁掉（文档级滚动
     条永不出现）。与左右栏对齐改为可滚动，子项不被压扁；画布可伸缩但
     保底 420px，矮视口下滚动即可看到积分结果。 */
  overflow-y: auto;
  min-height: 0;
  padding-right: 4px;
}

.cv-center > * {
  flex-shrink: 0;
}

.cv-center > :deep(.calib-canvas) {
  flex: 1 1 auto;
  height: auto;
  min-height: 420px;
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

/* Internal-standard geometry preview block (step 3, read-only) — mirrors the
   CalibRefinePanel crp-geometry layout. / 内标几何预览块（第 3 步，只读）——
   版式对标 CalibRefinePanel 的 crp-geometry。 */
.cv-geo {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.cv-geo-title {
  margin: 0;
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--text-primary);
}

/* Final centre highlight (same look as crp-final-center) / 最终中心高亮 */
.cv-geo-final-center {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 10px;
  border: 1px solid rgba(232, 121, 249, 0.55);
  border-radius: var(--radius-sm);
  background: rgba(232, 121, 249, 0.10);
}

.cv-geo-final-label {
  font-size: 0.8rem;
  font-weight: 700;
  color: #e879f9;
  white-space: nowrap;
}

.cv-geo-final-value {
  font-family: var(--font-mono);
  font-size: 0.92rem;
  font-weight: 700;
  color: var(--text-primary);
}

.cv-geo-readout {
  margin: 0;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  overflow: hidden;
}

.cv-geo-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 8px;
  padding: 4px 10px;
}

.cv-geo-row:nth-child(odd) {
  background: var(--bg-hover);
}

.cv-geo-row dt {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--text-secondary);
  display: flex;
  align-items: baseline;
  gap: 6px;
  min-width: 0;
}

.cv-geo-row dt em {
  font-family: inherit;
  font-style: normal;
  font-size: 0.68rem;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.cv-geo-row dd {
  margin: 0;
  font-family: var(--font-mono);
  font-size: 0.78rem;
  color: var(--text-primary);
  font-weight: 600;
  white-space: nowrap;
}

.cv-geo-hint {
  margin: 0;
  font-size: 0.72rem;
  color: var(--text-muted);
  line-height: 1.45;
}

.cv-geo-empty {
  margin: 0;
  padding: 12px;
  text-align: center;
  font-size: 0.8rem;
  color: var(--text-muted);
  border: 1px dashed var(--border);
  border-radius: var(--radius-sm);
}

/* Default-distance warning in the preview readout (amber, mirrors
   CalibRefinePanel's warn hint) / 预览读数中的默认距离警示（琥珀色，
   对标 CalibRefinePanel 的警示提示） */
.cv-geo-default-warn {
  margin: 0;
  padding: 6px 10px;
  border-radius: var(--radius-sm);
  background: rgba(234, 179, 8, 0.12);
  color: #a16207;
  font-size: 0.72rem;
  line-height: 1.4;
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

/* Pre-export warning bar: the .poni is about to carry a default (not fitted)
   sample-detector distance — the user must see this BEFORE exporting.
   导出前警示横条：.poni 即将携带默认（非拟合）样品-探测器距离——导出前
   必须让用户看到。 */
.cv-export-warning {
  padding: 8px 12px;
  border-radius: var(--radius-sm);
  background: rgba(234, 179, 8, 0.12);
  color: #a16207;
  font-size: 0.75rem;
  line-height: 1.45;
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
