<template>
  <section class="cake-page" :data-testid="testIds.integrateCakePage">
    <header class="cake-header">
      <h1>{{ t('integrateCake.title') }}</h1>
      <p class="cake-subtitle">{{ t('integrateCake.description') }}</p>
    </header>

    <div class="cake-layout">
      <!-- ── Sidebar / 侧边栏 ───────────────────────────────────────── -->
      <aside class="cake-sidebar">
        <GeometryForm v-model="geometry" />

        <!-- Mask Import (collapsible, collapsed by default) / 掩膜导入（可折叠，默认收起） -->
        <div class="cake-collapsible">
          <div class="cake-section-toggle" @click="maskExpanded = !maskExpanded">
            <span class="cake-toggle-icon">{{ maskExpanded ? '▾' : '▸' }}</span>
            <span>{{ t('business.sections.maskImport') }}</span>
          </div>
          <div v-show="maskExpanded" class="cake-collapsible-body">
            <MaskBuilderForm v-model="maskConfig" :bare="true" />
          </div>
        </div>

        <PolarizationForm v-model="polarizationFactor" />

        <!-- Azimuth sector range / 方位角扇区范围 -->
        <fieldset class="cake-fieldset">
          <legend class="cake-fieldset-legend">{{ t('integrateCake.azimuthRange.title') }}</legend>
          <p class="cake-fieldset-hint">{{ t('integrateCake.azimuthRange.hint') }}</p>
          <div class="cake-fieldset-grid">
            <label class="cake-field">
              <span class="cake-field-label">{{ t('integrateCake.azimuthRange.min') }}</span>
              <input
                type="number"
                class="cake-input"
                min="-360"
                max="360"
                step="5"
                :value="azimuthMin"
                :data-testid="testIds.cakeAzimuthMin"
                @input="onAzimuthInput('min', ($event.target as HTMLInputElement).value)"
              />
            </label>
            <label class="cake-field">
              <span class="cake-field-label">{{ t('integrateCake.azimuthRange.max') }}</span>
              <input
                type="number"
                class="cake-input"
                min="-360"
                max="360"
                step="5"
                :value="azimuthMax"
                :data-testid="testIds.cakeAzimuthMax"
                @input="onAzimuthInput('max', ($event.target as HTMLInputElement).value)"
              />
            </label>
          </div>
          <p v-if="azimuthError" class="cake-error">{{ azimuthError }}</p>
        </fieldset>

        <!-- Output Unit (standalone, pulled out of Advanced Options) / 输出单位（独立于高级选项） -->
        <div class="cake-output-unit">
          <label class="cake-field">
            <span class="cake-field-label">{{ t('business.sections.outputUnit') }}</span>
            <select
              class="cake-select"
              :value="advancedOptions.unit"
              @change="onUnitChange"
            >
              <option v-for="u in unitOptions" :key="u.value" :value="u.value">
                {{ u.label }}
              </option>
            </select>
          </label>
        </div>

        <!-- Advanced Options (collapsible, collapsed by default) / 高级选项（可折叠，默认收起） -->
        <div class="cake-collapsible">
          <div class="cake-section-toggle" @click="advancedExpanded = !advancedExpanded">
            <span class="cake-toggle-icon">{{ advancedExpanded ? '▾' : '▸' }}</span>
            <span>{{ t('business.advancedOptions.title') }}</span>
          </div>
          <div v-show="advancedExpanded" class="cake-collapsible-body">
            <AdvancedOptionsForm
              v-model="advancedOptions"
              :hide-unit="true"
              :bare="true"
            />
          </div>
        </div>

        <!-- Display settings (collapsible, default collapsed) / 显示设置（可折叠，默认收起） -->
        <div class="cake-collapsible">
          <div class="cake-section-toggle" @click="displayExpanded = !displayExpanded">
            <span class="cake-toggle-icon">{{ displayExpanded ? '▾' : '▸' }}</span>
            <span>{{ t('business.sections.displaySettings') }}</span>
          </div>
          <div v-show="displayExpanded" class="cake-collapsible-body">
            <div class="cake-field">
              <label class="cake-field-label">{{ t('business.display.colormap') }}</label>
              <select v-model="colormap" class="cake-select">
                <option v-for="cm in colormapOptions" :key="cm" :value="cm">
                  {{ getColormapDisplayName(cm) }}
                </option>
              </select>
            </div>
            <label class="cake-toggle-label">
              <input v-model="useLog" type="checkbox" />
              <span>{{ t('business.display.logScale') }}</span>
            </label>
          </div>
        </div>
      </aside>

      <!-- ── Main content / 主内容区 ──────────────────────────────────── -->
      <div class="cake-main">
        <!-- File selection / 文件选择 -->
        <div class="cake-file-section">
          <h2 class="cake-section-title">{{ t('integrate1d.dataFiles') }}</h2>
          <div class="cake-file-buttons">
            <button
              type="button"
              class="cake-file-btn"
              @click="handleChooseFiles"
            >
              {{ t('business.fileSelection.selectFiles') }}
            </button>
            <button
              type="button"
              class="cake-file-btn"
              :disabled="!transport.isDesktop()"
              :title="!transport.isDesktop() ? t('business.fileSelection.folderNotAvailableInWeb') : ''"
              @click="handleImportFolder"
            >
              {{ t('business.fileSelection.importFolder') }}
            </button>
            <label class="cake-toggle-label">
              <input v-model="isRecursive" type="checkbox" />
              <span>{{ t('business.fileSelection.recursive') }}</span>
            </label>
            <div class="cake-import-mode">
              <span class="cake-import-mode-label">{{ t('business.fileSelection.importMode') }}</span>
              <label class="cake-radio-label" :title="t('business.fileSelection.replaceTooltip')">
                <input v-model="importMode" type="radio" value="replace" />
                <span>{{ t('business.fileSelection.replace') }}</span>
              </label>
              <label class="cake-radio-label" :title="t('business.fileSelection.appendTooltip')">
                <input v-model="importMode" type="radio" value="append" />
                <span>{{ t('business.fileSelection.append') }}</span>
              </label>
            </div>
          </div>

          <!-- File count indicator / 文件计数指示器 -->
          <div v-if="files.length > 0" class="cake-file-info">
            <span class="cake-file-count">
              {{ t('business.fileSelection.filesSelected', { count: files.length }) }}
            </span>
            <button type="button" class="cake-clear-btn" @click="clearAllFiles">
              {{ t('business.fileSelection.clearAll') }}
            </button>
          </div>
          <div v-else class="cake-file-info cake-file-info--muted">
            <span>{{ t('business.fileSelection.noFiles') }}</span>
          </div>
        </div>

        <!-- Image preview (collapsible) / 图像预览（可折叠） -->
        <div class="cake-collapsible">
          <div class="cake-section-toggle" @click="onPreviewToggle">
            <span class="cake-toggle-icon">{{ previewExpanded ? '▾' : '▸' }}</span>
            <span>{{ t('business.sections.imagePreview') }}</span>
          </div>
          <div v-show="previewExpanded" class="cake-collapsible-body">
            <div v-if="previewLoading" class="cake-preview-loading">
              {{ t('business.sections.loading') }}
            </div>
            <div v-else-if="previewB64" class="cake-preview-area">
              <div class="cake-preview-image">
                <ImagePreview
                  :image-b64="previewB64"
                  :overlays="imageOverlays"
                  :show-colorbar="true"
                  :colorbar-gradient="colorbarGradient"
                  :colorbar-min-label="colorbarMinLabel"
                  :colorbar-max-label="colorbarMaxLabel"
                  :title="t('integrateCake.imagePreview.chartTitle')"
                  :placeholder="t('business.sections.noImage')"
                />
              </div>
              <div class="cake-preview-info">
                <h4 class="cake-info-title">{{ t('business.sections.imageInfo') }}</h4>
                <div v-if="currentPreviewFileName" class="cake-info-item">
                  <span class="cake-info-label">{{ t('business.sections.fileName') }}</span>
                  <span class="cake-info-value">{{ currentPreviewFileName }}</span>
                </div>
                <template v-if="previewStats">
                  <div class="cake-info-item">
                    <span class="cake-info-label">Min</span>
                    <span class="cake-info-value">{{ formatSci(previewStats.min) }}</span>
                  </div>
                  <div class="cake-info-item">
                    <span class="cake-info-label">Max</span>
                    <span class="cake-info-value">{{ formatSci(previewStats.max) }}</span>
                  </div>
                  <div class="cake-info-item">
                    <span class="cake-info-label">Std</span>
                    <span class="cake-info-value">{{ formatSci(previewStats.std) }}</span>
                  </div>
                </template>
                <template v-if="autoContrast">
                  <div class="cake-info-item">
                    <span class="cake-info-label">Auto range</span>
                    <span class="cake-info-value">{{ formatSci(autoContrast.autoMin) }} – {{ formatSci(autoContrast.autoMax) }}</span>
                  </div>
                </template>
                <div v-if="resolvedBeamCenter" class="cake-info-item">
                  <span class="cake-info-label">{{ t('business.sections.beamCenter') }}</span>
                  <span class="cake-info-value">{{ beamCenterLabel }}</span>
                </div>
                <div class="cake-info-item">
                  <span class="cake-info-label">{{ t('integrateCake.imagePreview.sector') }}</span>
                  <span class="cake-info-value">{{ azimuthMin.toFixed(1) }}° → {{ azimuthMax.toFixed(1) }}°</span>
                </div>
              </div>
            </div>
            <div v-else class="cake-preview-empty">
              {{ t('business.fileSelection.expandAfterSelect') }}
            </div>
          </div>
        </div>

        <!-- Thumbnail strip (collapsible, default collapsed) / 缩略图（可折叠，默认收起） -->
        <div class="cake-collapsible">
          <div class="cake-section-toggle" @click="onThumbToggle">
            <span class="cake-toggle-icon">{{ thumbExpanded ? '▾' : '▸' }}</span>
            <span>{{ t('business.sections.thumbnails') }}</span>
          </div>
          <div v-show="thumbExpanded" class="cake-collapsible-body">
            <ThumbnailStrip
              :items="thumbnailItems"
              :selected-index="selectedPreviewIndex"
              :current-page="thumbCurrentPage"
              :total-pages="thumbTotalPages"
              :page-size="thumbPageSize"
              :loading="thumbLoading"
              :sync-with-main="false"
              :columns-per-row="thumbColsPerRow"
              @select="handleThumbSelect"
              @prev-page="handleThumbPrevPage"
              @next-page="handleThumbNextPage"
              @jump-to-page="handleThumbJumpToPage"
              @page-size-change="handleThumbPageSizeChange"
              @update:columns-per-row="thumbColsPerRow = $event"
            />
          </div>
        </div>

        <!-- Error state / 错误状态 -->
        <div v-if="runError" class="cake-error-box">
          <p>{{ runError }}</p>
        </div>

        <!-- Run button / 运行按钮 -->
        <div class="cake-run-section">
          <button
            type="button"
            class="cake-run-btn"
            :disabled="!canRun"
            :data-testid="testIds.cakeRunButton"
            @click="handleRun"
          >
            {{ t('integrateCake.run') }}
          </button>
        </div>

        <!-- Progress / 进度 -->
        <TaskProgressBar
          v-if="taskId"
          :task-id="taskId"
          :progress="progress"
          :message="progressMessage"
          @cancel="handleCancel"
        />

        <!-- Result chart / 结果图表 -->
        <div v-if="resultTraces.length > 0" class="cake-result">
          <h2 class="cake-section-title">{{ t('integrateCake.resultChart.title') }}</h2>
          <LineChart
            :traces="resultTraces"
            :x-label="unitLabel"
            :y-label="t('integrateCake.resultChart.yLabel')"
            :title="resultChartTitle"
          />
        </div>

        <!-- Export / 导出 -->
        <ExportDialog
          v-if="resultTraces.length > 0"
          :result="resultData"
          :formats="exportFormats"
          @export="handleExport"
        />
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
/**
 * IntegrateCakeView.vue — CAKE 方位角窗口 1D 积分页面
 * CAKE azimuthal-window 1-D integration page
 *
 * Performs 1-D radial integration restricted to a user-defined azimuthal
 * (CAKE) range. Useful for anisotropic samples where only a sector
 * of the Debye–Scherrer ring is of interest.
 * 执行限制在用户定义方位角（CAKE）范围内的1D径向积分。
 * 适用于各向异性样品，只关注 Debye-Scherrer 环某个扇区时使用。
 */
import { ref, computed, watch, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useToast } from '@/lib/toast'
import { useTransport } from '@/lib/transport'
import { testIds } from '@/lib/testIds'
import { COLORMAP_PRESETS, COLORMAP_DISPLAY_NAMES, resolveColorbarGradient } from '@/lib/chart-utils'
import type { ColormapName } from '@/lib/chart-utils'

import GeometryForm from '@/components/business/GeometryForm.vue'
import type { GeometryParams } from '@/components/business/GeometryForm.vue'
import MaskBuilderForm from '@/components/business/MaskBuilderForm.vue'
import type { MaskConfig } from '@/components/business/MaskBuilderForm.vue'
import AdvancedOptionsForm from '@/components/business/AdvancedOptionsForm.vue'
import { UNIT_OPTIONS } from '@/components/business/AdvancedOptionsForm.vue'
import type { AdvancedOptions, IntegrationUnit } from '@/components/business/AdvancedOptionsForm.vue'
import PolarizationForm from '@/components/business/PolarizationForm.vue'
import TaskProgressBar from '@/components/business/TaskProgressBar.vue'
import ExportDialog from '@/components/business/ExportDialog.vue'
import type { ExportFormat, ExportMode } from '@/components/business/ExportDialog.vue'
import ImagePreview from '@/components/charts/ImagePreview.vue'
import type { Overlay } from '@/components/charts/ImagePreview.vue'
import LineChart from '@/components/charts/LineChart.vue'
import type { LineTrace } from '@/components/charts/LineChart.vue'
import ThumbnailStrip from '@/components/business/ThumbnailStrip.vue'
import type { ThumbnailItem } from '@/components/business/ThumbnailStrip.vue'

// === Type definitions / 类型定义 ===

interface PreviewMetadata {
  stats?: { min: number; max: number; adjustedMax: number; std: number }
  contrast?: { autoMin: number; autoMax: number; logMin: number; logMax: number }
  shape?: [number, number]
  width?: number
  height?: number
  metadata?: {
    width?: number
    height?: number
  }
}

interface GeometryCenterResult {
  centerX?: number
  centerY?: number
}

interface ScanFolderResult {
  files?: string[]
}

const { t } = useI18n()
const toast = useToast()
const transport = useTransport()

// ── Colormap options / 色图选项 ──

const colormapOptions = [
  'smooth_WAXS_foxtrot',
  'smooth_WAXS_fit2D',
  ...Object.keys(COLORMAP_PRESETS),
] as string[]

function getColormapDisplayName(key: string): string {
  if (key === 'smooth_WAXS_foxtrot') return 'Foxtrot (WAXS)'
  if (key === 'smooth_WAXS_fit2D') return 'FIT2D (WAXS)'
  if (key in COLORMAP_DISPLAY_NAMES) return COLORMAP_DISPLAY_NAMES[key as ColormapName]
  return key
}

// ── Unit options (imported from AdvancedOptionsForm) / 单位选项 ──

const unitOptions = UNIT_OPTIONS

function onUnitChange(event: Event): void {
  const val = (event.target as HTMLSelectElement).value as IntegrationUnit
  Object.assign(advancedOptions, { unit: val })
}

// ── State / 状态 ────────────────────────────────────────────────────────────

const geometry = ref<GeometryParams>({
  pixel1: 172,
  pixel2: 172,
  distance: 200,
  wavelength: 1.5418,
  centerX: 512,
  centerY: 512,
})

const maskConfig = ref<MaskConfig>({
  valueRangeMin: 0,
  valueRangeMax: 1e10,
  deadPixelThreshold: 0,
  customMaskPath: null,
})

const advancedOptions = ref<AdvancedOptions>({
  nptRad: 1000,
  nptAzim: 360,
  radialMin: null,
  radialMax: null,
  unit: 'q_A',
  correctSolidAngle: true,
  dropEmptyBins: true,
})

const polarizationFactor = ref<number | null>(null)

const azimuthMin = ref(-180)
const azimuthMax = ref(180)

const selectedFilePath = ref<string | null>(null)

// === File state / 文件状态 ===

const files = ref<string[]>([])
const isRecursive = ref(false)
const importFolderPath = ref<string | null>(null)
type ImportMode = 'replace' | 'append'
const importMode = ref<ImportMode>('replace')

const dataFileFilters = [
  { name: 'Detector Images', extensions: ['edf', 'tif', 'tiff', 'h5', 'hdf5'] },
]

/** Preview selection index — must be declared before activeFilePath / 预览选择索引 — 必须在 activeFilePath 之前声明 */
const selectedPreviewIndex = ref(0)

/** Current active file derived from selected preview index / 当前活动文件由预览选择索引派生 */
const activeFilePath = computed(() => files.value[selectedPreviewIndex.value] ?? null)

/** Keep selectedFilePath in sync for backward compat / 保持 selectedFilePath 同步以兼容 */
watch(activeFilePath, (v) => { selectedFilePath.value = v }, { immediate: true })

const selectedFileName = computed(() => {
  const path = selectedFilePath.value
  if (!path) return ''
  const sep = path.includes('/') ? '/' : '\\'
  return path.split(sep).pop() ?? path
})

const currentPreviewFileName = computed(() => {
  const path = files.value[selectedPreviewIndex.value] ?? files.value[0]
  if (!path) return ''
  const sep = path.includes('/') ? '/' : '\\'
  return path.split(sep).pop() ?? path
})

function clearAllFiles(): void {
  files.value = []
  importFolderPath.value = null
  if (previewB64.value?.startsWith('blob:')) {
    URL.revokeObjectURL(previewB64.value)
  }
  previewB64.value = null
  previewStats.value = null
  autoContrast.value = null
  previewImageSize.value = null
  selectedPreviewIndex.value = 0
  thumbnailItems.value = []
  resultTraces.value = []
  resultData.value = null
  runError.value = null
}

// ── Preview state / 预览状态 ──

const previewB64 = ref<string | null>(null)
const previewStats = ref<{ min: number; max: number; adjustedMax: number; std: number } | null>(null)
const autoContrast = ref<{ autoMin: number; autoMax: number; logMin: number; logMax: number } | null>(null)
const previewLoading = ref(false)
const resolvedBeamCenter = ref<{ x: number; y: number } | null>(
  { x: geometry.value.centerX, y: geometry.value.centerY }
)
const previewImageSize = ref<{ width: number; height: number; origWidth: number; origHeight: number } | null>(null)

// ── Display settings / 显示设置 ──

const colormap = ref('smooth_WAXS_foxtrot')
const useLog = ref(true)

// ── Collapsible section state / 折叠区域状态 ──

const previewExpanded = ref(true)
const thumbExpanded = ref(false)
const displayExpanded = ref(false)
const maskExpanded = ref(false)
const advancedExpanded = ref(false)

// ── Thumbnail state / 缩略图状态 ──

const thumbnailItems = ref<ThumbnailItem[]>([])
const thumbCurrentPage = ref(1)
const thumbPageSize = ref(10)
const thumbColsPerRow = ref(10)
const thumbLoading = ref(false)

// ── Task state / 任务状态 ──

const taskId = ref<string | null>(null)
const progress = ref(0)
const progressMessage = ref<string | null>(null)
const runError = ref<string | null>(null)
const resultTraces = ref<LineTrace[]>([])
const resultData = ref<unknown>(null)

const exportFormats: ExportFormat[] = ['txt', 'csv', 'xy', 'hdf5']

// Cleanup listeners / 清理监听器
let cleanupPreviewBinary: (() => void) | null = null
let cleanupPreviewResult: (() => void) | null = null
let cleanupPreviewError: (() => void) | null = null

// ── Computed / 计算属性 ──────────────────────────────────────────────────────

/** Validate azimuth range / 验证方位角范围 */
const azimuthError = computed<string | null>(() => {
  if (azimuthMin.value == null || azimuthMax.value == null) {
    return t('integrateCake.azimuthRange.errorEmpty')
  }
  if (azimuthMin.value >= azimuthMax.value) {
    return t('integrateCake.azimuthRange.errorMinMax')
  }
  return null
})

/** Whether the run button is enabled / 运行按钮是否可用 */
const canRun = computed(() => {
  return (
    files.value.length > 0 &&
    azimuthError.value === null &&
    taskId.value === null
  )
})

const thumbTotalPages = computed(() =>
  Math.max(1, Math.ceil(files.value.length / thumbPageSize.value))
)

/** Image overlay: beam center + sector boundary lines / 图像叠加：光束中心 + 扇区边界线 */
const imageOverlays = computed<Overlay[]>(() => {
  const overlays: Overlay[] = []

  // Beam center crosshair / 光束中心十字线
  if (resolvedBeamCenter.value) {
    overlays.push({
      type: 'beamCenter',
      x: resolvedBeamCenter.value.x,
      y: resolvedBeamCenter.value.y,
    })
  }

  // Sector boundary lines from center / 从中心出发的扇区边界线
  if (resolvedBeamCenter.value) {
    overlays.push({
      type: 'sectorBoundary',
      angles: [azimuthMin.value, azimuthMax.value],
      centerX: resolvedBeamCenter.value.x,
      centerY: resolvedBeamCenter.value.y,
    })
  }

  return overlays
})

const colorbarGradient = computed(() => resolveColorbarGradient(colormap.value))

const colorbarMinLabel = computed(() => {
  if (!autoContrast.value) return '0'
  return useLog.value
    ? autoContrast.value.logMin.toExponential(3)
    : autoContrast.value.autoMin.toExponential(3)
})

const colorbarMaxLabel = computed(() => {
  if (!autoContrast.value) return '1'
  return useLog.value
    ? autoContrast.value.logMax.toExponential(3)
    : autoContrast.value.autoMax.toExponential(3)
})

const beamCenterLabel = computed(() => {
  if (!resolvedBeamCenter.value) return '—'
  return `(${resolvedBeamCenter.value.x.toFixed(2)}, ${resolvedBeamCenter.value.y.toFixed(2)})`
})

/** Unit label for chart axis / 图表轴的单位标签 */
const unitLabel = computed(() => {
  const map: Record<string, string> = {
    q_nm: 'q (nm⁻¹)',
    q_A: 'q (Å⁻¹)',
    '2th_deg': '2θ (deg)',
    '2th_rad': '2θ (rad)',
  }
  return map[advancedOptions.value.unit] ?? 'q (Å⁻¹)'
})

/** Chart title with azimuth range / 带方位角范围的图表标题 */
const resultChartTitle = computed(() =>
  t('integrateCake.resultChart.chartTitle', {
    min: azimuthMin.value.toFixed(0),
    max: azimuthMax.value.toFixed(0),
  })
)

// ── Helpers / 辅助函数 ──

function formatSci(value: number): string {
  if (!Number.isFinite(value)) return '—'
  if (value === 0) return '0'
  return value.toExponential(3)
}

function submitAndWait(route: string, params: Record<string, unknown>): Promise<unknown> {
  return new Promise((resolve, reject) => {
    transport.submitTask(route, params).then(response => {
      transport.onTaskResult(response.taskId, (p) => resolve(p.data))
      transport.onTaskError(response.taskId, (p) => reject(new Error(p.error)))
    }).catch(reject)
  })
}

function buildRenderSettings(): Record<string, unknown> {
  return {
    cmap: colormap.value,
    use_log: useLog.value,
    clim_mode: 'auto',
    clim: [null, null],
    preview_scale: 1.0,
  }
}

function buildGeometryPayload(): Record<string, unknown> {
  return {
    poniPath: geometry.value.poniPath ?? undefined,
    pixel1: geometry.value.pixel1,
    pixel2: geometry.value.pixel2,
    distance: geometry.value.distance,
    wavelength: geometry.value.wavelength,
    centerX: geometry.value.centerX,
    centerY: geometry.value.centerY,
  }
}

async function resolveBeamCenter(): Promise<void> {
  try {
    const result = await submitAndWait('viewer_config', {
      action: 'resolve_geometry_center',
      geometry: buildGeometryPayload(),
    })
    const center = result as GeometryCenterResult
    if (typeof center.centerX === 'number' && typeof center.centerY === 'number') {
      resolvedBeamCenter.value = { x: center.centerX, y: center.centerY }
      return
    }
  } catch {
    // Fallback to current form values / 失败时回退到当前表单值
  }
  resolvedBeamCenter.value = { x: geometry.value.centerX, y: geometry.value.centerY }
}

// ── File handlers / 文件处理 ──

async function handleChooseFiles(): Promise<void> {
  const result = await transport.selectFiles({
    filters: dataFileFilters,
    multiSelections: true,
  })
  if (!result) return
  const paths = Array.isArray(result) ? result : [result]
  if (importMode.value === 'append') {
    const existingSet = new Set(files.value)
    const newFiles = paths.filter(p => !existingSet.has(p))
    files.value = [...files.value, ...newFiles]
  } else {
    files.value = paths
  }
  importFolderPath.value = null
  selectedPreviewIndex.value = 0
  thumbnailItems.value = []
  resultTraces.value = []
  resultData.value = null
  runError.value = null
  await loadPreviewIfExpanded()
  loadThumbnailPageIfExpanded()
}

async function handleImportFolder(): Promise<void> {
  const folder = await transport.selectFolder()
  if (!folder) return
  importFolderPath.value = folder
  await rescanFolder()
}

async function rescanFolder(): Promise<void> {
  if (!importFolderPath.value) return
  try {
    const scanResult = await submitAndWait('viewer_config', {
      action: 'scan_folder',
      folder: importFolderPath.value,
      recursive: isRecursive.value,
    })
    const scanned = scanResult as ScanFolderResult
    const found = Array.isArray(scanned?.files) ? scanned.files.filter(Boolean) : []
    if (importMode.value === 'append') {
      const existingSet = new Set(files.value)
      const newFiles = found.filter(p => !existingSet.has(p))
      files.value = [...files.value, ...newFiles]
    } else {
      files.value = found
    }
    selectedPreviewIndex.value = 0
    thumbnailItems.value = []
    resultTraces.value = []
    resultData.value = null
    runError.value = null
    await loadPreviewIfExpanded()
    loadThumbnailPageIfExpanded()
  } catch (err) {
    toast.push({
      title: t('integrateCake.title'),
      message: err instanceof Error ? err.message : String(err),
      tone: 'error',
    })
  }
}

// ── Preview loading / 预览加载 ──

async function loadPreview(path: string): Promise<void> {
  previewLoading.value = true
  if (previewB64.value?.startsWith('blob:')) {
    URL.revokeObjectURL(previewB64.value)
  }
  previewB64.value = null
  previewStats.value = null
  autoContrast.value = null
  previewImageSize.value = null

  cleanupPreviewListeners()

  try {
    await resolveBeamCenter()
    const response = await transport.submitTask('viewer_config', {
      action: 'open_file',
      filePath: path,
      frame: 0,
      settings: buildRenderSettings(),
    })

    cleanupPreviewBinary = transport.onTaskBinaryData(response.taskId, (payload) => {
      if (payload.data) {
        const blob = new Blob([payload.data], { type: payload.mime || 'image/png' })
        if (previewB64.value?.startsWith('blob:')) {
          URL.revokeObjectURL(previewB64.value)
        }
        previewB64.value = URL.createObjectURL(blob)
      }
    })

    cleanupPreviewResult = transport.onTaskResult(response.taskId, (payload) => {
      const data = payload.data as PreviewMetadata
      if (data.stats) previewStats.value = data.stats
      if (data.contrast) autoContrast.value = data.contrast
      previewImageSize.value = {
        width: 0,
        height: 0,
        origWidth: data.metadata?.width ?? 0,
        origHeight: data.metadata?.height ?? 0,
      }
      previewLoading.value = false
    })

    cleanupPreviewError = transport.onTaskError(response.taskId, (payload) => {
      previewLoading.value = false
      toast.push({
        title: t('integrateCake.title'),
        message: payload.error,
        tone: 'error',
      })
    })
  } catch (err) {
    previewLoading.value = false
    toast.push({
      title: t('integrateCake.title'),
      message: err instanceof Error ? err.message : String(err),
      tone: 'error',
    })
  }
}

async function loadPreviewIfExpanded(): Promise<void> {
  if (previewExpanded.value && activeFilePath.value) {
    await loadPreview(activeFilePath.value)
  }
}

function onPreviewToggle(): void {
  previewExpanded.value = !previewExpanded.value
  if (previewExpanded.value && activeFilePath.value && !previewB64.value) {
    loadPreview(activeFilePath.value)
  }
}

function cleanupPreviewListeners(): void {
  cleanupPreviewBinary?.()
  cleanupPreviewBinary = null
  cleanupPreviewResult?.()
  cleanupPreviewResult = null
  cleanupPreviewError?.()
  cleanupPreviewError = null
}

// ── Thumbnail loading / 缩略图加载 ──

function buildThumbRenderSettings(): Record<string, unknown> {
  return {
    cmap: colormap.value,
    use_log: useLog.value,
  }
}

async function loadThumbnailPage(page?: number): Promise<void> {
  if (files.value.length === 0) return

  const currentPage = page ?? thumbCurrentPage.value
  const start = (currentPage - 1) * thumbPageSize.value
  const count = thumbPageSize.value
  const slice = files.value.slice(start, start + count)

  thumbLoading.value = true
  const items: ThumbnailItem[] = []

  try {
    for (let i = 0; i < slice.length; i++) {
      const path = slice[i]
      if (!path) continue

      const sep = path.includes('/') ? '/' : '\\'
      const parts = path.split(sep)
      const label = parts[parts.length - 1] || path

      const result = await submitAndWait('viewer_config', {
        action: 'preview',
        filePath: path,
        thumb_render_settings: buildThumbRenderSettings(),
      })

      const thumbData = result as { b64?: string; previewB64?: string }
      items.push({
        index: start + i,
        b64: typeof thumbData?.b64 === 'string'
          ? thumbData.b64
          : (typeof thumbData?.previewB64 === 'string' ? thumbData.previewB64 : ''),
        label,
      })
    }

    thumbnailItems.value = items
  } catch {
    thumbnailItems.value = []
  } finally {
    thumbLoading.value = false
  }
}

function loadThumbnailPageIfExpanded(): void {
  if (thumbExpanded.value && files.value.length > 0) {
    loadThumbnailPage()
  }
}

function onThumbToggle(): void {
  thumbExpanded.value = !thumbExpanded.value
  if (thumbExpanded.value && files.value.length > 0 && thumbnailItems.value.length === 0) {
    loadThumbnailPage()
  }
}

function handleThumbSelect(index: number): void {
  selectedPreviewIndex.value = index
  const fPath = files.value[index]
  if (fPath) {
    loadPreview(fPath)
  }
}

function handleThumbPrevPage(): void {
  if (thumbCurrentPage.value <= 1) return
  thumbCurrentPage.value -= 1
  loadThumbnailPage()
}

function handleThumbNextPage(): void {
  if (thumbCurrentPage.value >= thumbTotalPages.value) return
  thumbCurrentPage.value += 1
  loadThumbnailPage()
}

function handleThumbJumpToPage(page: number): void {
  const clamped = Math.max(1, Math.min(thumbTotalPages.value, page))
  if (clamped === thumbCurrentPage.value) return
  thumbCurrentPage.value = clamped
  loadThumbnailPage(clamped)
}

function handleThumbPageSizeChange(size: number): void {
  thumbPageSize.value = size
  thumbCurrentPage.value = 1
  if (files.value.length > 0) {
    loadThumbnailPage()
  }
}

// ── Handlers / 处理函数 ──────────────────────────────────────────────────────

function onAzimuthInput(field: 'min' | 'max', raw: string): void {
  const num = parseFloat(raw)
  if (isNaN(num)) return
  if (field === 'min') azimuthMin.value = num
  else azimuthMax.value = num
}

async function handleRun(): Promise<void> {
  if (!canRun.value || !activeFilePath.value) return

  runError.value = null
  resultTraces.value = []
  resultData.value = null
  progress.value = 0
  progressMessage.value = null

  const params: Record<string, unknown> = {
    filePath: activeFilePath.value,
    files: [...files.value],
    geometry: { ...geometry.value },
    maskConfig: { ...maskConfig.value },
    advancedOptions: { ...advancedOptions.value },
    polarizationFactor: polarizationFactor.value,
    azimuthMin: azimuthMin.value,
    azimuthMax: azimuthMax.value,
  }

  try {
    const response = await transport.submitTask('integrate_cake', params)
    taskId.value = response.taskId

    const removeProgress = transport.onTaskProgress(
      response.taskId,
      (payload) => {
        progress.value = payload.progress
        if (payload.message) progressMessage.value = payload.message
      }
    )

    const removeResult = transport.onTaskResult(
      response.taskId,
      (payload) => {
        taskId.value = null
        const data = payload.data as {
          traces?: Array<{ x: number[]; y: number[]; name?: string }>
          failed?: Array<{ file: string; reason: string }>
        } | null
        const traces = Array.isArray(data?.traces)
          ? data.traces.filter((tr) => Array.isArray(tr.x) && tr.x.length > 0 && Array.isArray(tr.y) && tr.y.length > 0)
          : []

        const failedList = Array.isArray(data?.failed) ? data.failed : []
        if (failedList.length > 0) {
          toast.push({
            title: `${failedList.length} file(s) failed`,
            message: failedList.map(f => `${f.file}: ${f.reason}`).join('; '),
            tone: 'warning',
          })
        }

        if (traces.length > 0) {
          resultTraces.value = traces.map((tr) => ({
            x: tr.x,
            y: tr.y,
            name: tr.name,
          }))
          resultData.value = data
          runError.value = null
        } else {
          runError.value = 'Integration completed without any displayable CAKE curves.'
        }

        removeProgress()
        removeResult()
        removeError()
      }
    )

    const removeError = transport.onTaskError(
      response.taskId,
      (payload) => {
        taskId.value = null
        progressMessage.value = payload.error
        runError.value = payload.error
        removeProgress()
        removeResult()
        removeError()
      }
    )
  } catch (error) {
    taskId.value = null
    runError.value = error instanceof Error ? error.message : 'Failed to start CAKE integration.'
  }
}

async function handleCancel(): Promise<void> {
  if (taskId.value) {
    try {
      await transport.cancelTask(taskId.value)
    } catch {
      // Task may already be completed / 任务可能已完成
    }
    taskId.value = null
  }
}

async function handleExport(payload: { format: ExportFormat; path: string; mode: ExportMode }): Promise<void> {
  if (!resultData.value) return

  const unitMap: Record<string, string> = {
    q_nm: 'q_nm^-1', q_A: 'q_A^-1',
    '2th_deg': '2th_deg', '2th_rad': '2th_rad',
    r_mm: 'r_mm',
  }
  const unit = unitMap[advancedOptions.value.unit] || advancedOptions.value.unit || 'q_nm^-1'

  const data = resultData.value as {
    traces?: Array<{ x: number[]; y: number[]; name?: string }>
  }
  const traces = data?.traces ?? []
  const results = JSON.parse(JSON.stringify(
    traces.map((tr) => ({
      radial: tr.x,
      intensity: tr.y,
      label: tr.name || 'cake',
      unit,
    }))
  ))

  if (results.length === 0) return

  try {
    const response = await transport.submitTask('export_integration', {
      format: payload.format,
      outputPath: payload.path,
      dataType: '1d',
      mode: payload.mode,
      results,
    })

    const removeOk = transport.onTaskResult(response.taskId, (r) => {
      const d = r.data as { success?: boolean; error?: string; path?: string }
      if (d?.success) {
        toast.push({
          title: t('integrateCake.title'),
          message: `${payload.format.toUpperCase()} → ${d.path ?? payload.path}`,
          tone: 'success',
        })
      } else {
        toast.push({ title: t('integrateCake.title'), message: d?.error ?? 'Export failed', tone: 'error' })
      }
      removeOk(); removeErr()
    })
    const removeErr = transport.onTaskError(response.taskId, (e) => {
      toast.push({ title: t('integrateCake.title'), message: e.error ?? 'Export failed', tone: 'error' })
      removeOk(); removeErr()
    })
  } catch (err) {
    toast.push({ title: t('integrateCake.title'), message: String(err), tone: 'error' })
  }
}

// === Watchers / 监听器 ===

/** Re-render preview when display settings change / 显示设置变更时重新渲染预览 */
watch([colormap, useLog], () => {
  if (activeFilePath.value && previewExpanded.value) {
    loadPreview(activeFilePath.value)
  }
  if (files.value.length > 0 && thumbExpanded.value) {
    loadThumbnailPage()
  }
})

watch(
  () => [
    geometry.value.poniPath,
    geometry.value.pixel1,
    geometry.value.pixel2,
    geometry.value.distance,
    geometry.value.wavelength,
    geometry.value.centerX,
    geometry.value.centerY,
  ],
  () => {
    if (activeFilePath.value && previewExpanded.value) {
      void loadPreviewIfExpanded()
    }
  },
)

/** Re-scan folder when recursive toggle changes / 递归开关变更时重新扫描文件夹 */
watch(isRecursive, () => {
  if (importFolderPath.value) {
    rescanFolder()
  }
})

onUnmounted(() => {
  if (previewB64.value?.startsWith('blob:')) {
    URL.revokeObjectURL(previewB64.value)
  }
  cleanupPreviewListeners()
})
</script>

<style scoped>
.cake-page {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.cake-header h1 {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 6px;
}

.cake-subtitle {
  font-size: 0.9375rem;
  color: var(--text-secondary);
  margin: 0;
  max-width: 72ch;
}

.cake-layout {
  display: grid;
  grid-template-columns: minmax(280px, 380px) minmax(0, 1fr);
  gap: 24px;
  align-items: start;
}

.cake-sidebar {
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow-y: auto;
  padding-right: 4px;
}

.cake-main {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.cake-section-title {
  font-size: 1rem;
  font-weight: 600;
  margin: 0 0 10px;
  color: var(--text-primary);
}

/* ── File section (1D-style) / 文件选择区（1D风格） ── */

.cake-file-section {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.cake-file-buttons {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.cake-file-btn {
  padding: 8px 16px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: 0.8125rem;
  font-weight: 500;
  cursor: pointer;
  white-space: nowrap;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.cake-file-btn:hover {
  border-color: var(--border-hover);
  box-shadow: var(--shadow-sm);
}

/* Import mode toggle / 导入模式切换 */
.cake-import-mode {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  border-radius: var(--radius-md);
  background: var(--bg-surface-alt);
  font-size: 0.8125rem;
}

.cake-import-mode-label {
  color: var(--text-secondary);
  font-weight: 500;
  white-space: nowrap;
}

.cake-radio-label {
  display: flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  color: var(--text-primary);
  white-space: nowrap;
}

.cake-radio-label input[type="radio"] {
  accent-color: var(--primary);
  width: 14px;
  height: 14px;
}

.cake-file-info {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 10px;
  border-radius: var(--radius-md);
  background: var(--bg-surface-alt);
}

.cake-file-info--muted {
  background: transparent;
  padding: 4px 10px;
}

.cake-file-count {
  flex: 1;
  font-family: var(--font-mono);
  font-size: 0.8125rem;
  color: var(--text-secondary);
}

.cake-file-info--muted .cake-file-count,
.cake-file-info--muted span {
  color: var(--text-muted);
  font-style: italic;
}

.cake-clear-btn {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  color: var(--text-secondary);
  font-size: 0.75rem;
  cursor: pointer;
  padding: 4px 10px;
  transition: border-color var(--transition-fast);
  white-space: nowrap;
}

.cake-clear-btn:hover {
  border-color: var(--border-hover);
  color: var(--error);
}

/* ── Collapsible sections / 折叠区域 ── */

.cake-collapsible {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.cake-section-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  cursor: pointer;
  user-select: none;
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--text-primary);
  background: var(--bg-surface);
  transition: background var(--transition-fast);
}

.cake-section-toggle:hover {
  background: var(--bg-surface-alt);
}

.cake-toggle-icon {
  font-size: 0.75rem;
  color: var(--text-muted);
  width: 14px;
  text-align: center;
}

.cake-collapsible-body {
  padding: 14px;
  border-top: 1px solid var(--border);
}

.cake-toggle-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.875rem;
  color: var(--text-primary);
  cursor: pointer;
  user-select: none;
}

.cake-toggle-label input[type="checkbox"] {
  accent-color: var(--primary);
  width: 16px;
  height: 16px;
}

/* ── Output Unit standalone / 独立输出单位选择 ── */

.cake-output-unit {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 12px 14px;
}

/* ── Fieldset for azimuth range / 方位角范围的 fieldset ── */

.cake-fieldset {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.cake-fieldset-legend {
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--text-primary);
  padding: 0 6px;
}

.cake-fieldset-hint {
  font-size: 0.75rem;
  color: var(--text-muted);
  margin: 0;
}

.cake-fieldset-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.cake-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.cake-field-label {
  font-size: 0.8125rem;
  color: var(--text-secondary);
  font-weight: 500;
}

.cake-input,
.cake-select {
  padding: 8px 10px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: 0.8125rem;
  transition: border-color var(--transition-fast);
}

.cake-input:focus,
.cake-select:focus {
  outline: none;
  border-color: var(--border-focus);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}

.cake-error {
  font-size: 0.75rem;
  color: var(--error);
  margin: 0;
}

.cake-error-box {
  padding: 14px 18px;
  border-radius: var(--radius-md);
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: var(--error);
  font-size: 0.875rem;
}

.cake-error-box p {
  margin: 0;
}

/* ── Image preview area / 图像预览区域 ── */

.cake-preview-loading {
  padding: 40px 24px;
  text-align: center;
  color: var(--text-muted);
  font-size: 0.9375rem;
}

.cake-preview-area {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 200px;
  gap: 14px;
}

.cake-preview-image {
  border-radius: var(--radius-md);
  overflow: hidden;
}

.cake-preview-empty {
  padding: 24px;
  text-align: center;
  color: var(--text-muted);
  font-size: 0.875rem;
}

/* Preview info panel / 预览信息面板 */
.cake-preview-info {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-self: start;
}

.cake-info-title {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--text-secondary);
  margin: 0;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.cake-info-item {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  font-size: 0.75rem;
  gap: 6px;
}

.cake-info-label {
  color: var(--text-muted);
  font-weight: 500;
  white-space: nowrap;
}

.cake-info-value {
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: 0.6875rem;
  text-align: right;
  word-break: break-all;
}

/* ── Run button / 运行按钮 ── */

.cake-run-section {
  display: flex;
}

.cake-run-btn {
  padding: 12px 32px;
  border-radius: var(--radius-md);
  border: none;
  background: var(--primary);
  color: var(--text-inverse);
  font-size: 0.9375rem;
  font-weight: 600;
  cursor: pointer;
  transition: opacity var(--transition-fast);
}

.cake-run-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.cake-run-btn:not(:disabled):hover {
  opacity: 0.9;
}

/* ── Result / 结果区 ── */

.cake-result {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* ── Responsive / 响应式 ── */

@media (max-width: 960px) {
  .cake-layout {
    grid-template-columns: 1fr;
  }

  .cake-preview-area {
    grid-template-columns: 1fr;
  }
}
</style>
