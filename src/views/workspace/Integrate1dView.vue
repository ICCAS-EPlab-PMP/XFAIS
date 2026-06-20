<template>
  <section class="integrate-1d-page" :data-testid="testIds.integrate1dPage">
    <!-- Header / 页头 -->
    <header class="i1d-header">
      <h1>{{ t('integrate1d.title') }}</h1>
      <p class="i1d-subtitle">{{ t('integrate1d.subtitle') }}</p>
    </header>

    <div class="i1d-layout">
      <!-- Sidebar: parameter forms / 侧边栏：参数表单 -->
      <aside class="i1d-sidebar">
        <GeometryForm v-model="geometryParams" />

        <!-- Output Unit (standalone, pulled out of Advanced Options) / 输出单位（独立于高级选项） -->
        <div class="i1d-output-unit">
          <label class="i1d-field">
            <span class="i1d-label">{{ t('business.sections.outputUnit') }}</span>
            <select
              class="i1d-select"
              :value="advancedOptions.unit"
              @change="onUnitChange"
            >
              <option v-for="u in unitOptions" :key="u.value" :value="u.value">
                {{ u.label }}
              </option>
            </select>
          </label>
        </div>

        <!-- Mask Import (collapsible, collapsed by default) / 掩膜导入（可折叠，默认收起） -->
        <div class="i1d-collapsible">
          <div class="i1d-section-toggle" @click="maskExpanded = !maskExpanded">
            <span class="i1d-toggle-icon">{{ maskExpanded ? '▾' : '▸' }}</span>
            <span>{{ t('business.sections.maskImport') }}</span>
          </div>
          <div v-show="maskExpanded" class="i1d-collapsible-body">
            <MaskBuilderForm v-model="maskConfig" :bare="true" />
          </div>
        </div>

        <PolarizationForm v-model="polarizationFactor" />

        <!-- Advanced Options (collapsible, collapsed by default) / 高级选项（可折叠，默认收起） -->
        <div class="i1d-collapsible">
          <div class="i1d-section-toggle" @click="advancedExpanded = !advancedExpanded">
            <span class="i1d-toggle-icon">{{ advancedExpanded ? '▾' : '▸' }}</span>
            <span>{{ t('business.advancedOptions.title') }}</span>
          </div>
          <div v-show="advancedExpanded" class="i1d-collapsible-body">
            <AdvancedOptionsForm v-model="advancedOptions" :show-integration-method="true" :hide-unit="true" :bare="true" />
          </div>
        </div>

        <!-- Display settings (collapsible, default collapsed) / 显示设置（可折叠，默认收起） -->
        <div class="i1d-collapsible">
          <div class="i1d-section-toggle" @click="displayExpanded = !displayExpanded">
            <span class="i1d-toggle-icon">{{ displayExpanded ? '▾' : '▸' }}</span>
            <span>{{ t('business.sections.displaySettings') }}</span>
          </div>
          <div v-show="displayExpanded" class="i1d-collapsible-body">
            <div class="i1d-field">
              <label class="i1d-label">{{ t('business.display.colormap') }}</label>
              <select v-model="colormap" class="i1d-select">
                <option v-for="cm in colormapOptions" :key="cm" :value="cm">
                  {{ getColormapDisplayName(cm) }}
                </option>
              </select>
            </div>
            <label class="i1d-toggle-label">
              <input v-model="useLog" type="checkbox" />
              <span>{{ t('business.display.logScale') }}</span>
            </label>
            </div>
          </div>

          <div class="i1d-import-mode">
            <span class="i1d-import-mode-label">{{ t('business.fileSelection.importMode') }}</span>
            <label class="i1d-radio-label" :title="t('business.fileSelection.replaceTooltip')">
              <input v-model="importMode" type="radio" value="replace" />
              <span>{{ t('business.fileSelection.replace') }}</span>
            </label>
            <label class="i1d-radio-label" :title="t('business.fileSelection.appendTooltip')">
              <input v-model="importMode" type="radio" value="append" />
              <span>{{ t('business.fileSelection.append') }}</span>
            </label>
          </div>
        </aside>

        <!-- ===== Main area / 主区域 ===== -->
        <main class="i1d-main">
          <!-- File selection / 文件选择 -->
          <div class="i1d-file-section">
            <h2 class="i1d-section-title">{{ t('integrate1d.dataFiles') }}</h2>
            <div class="i1d-file-buttons">
              <button
                type="button"
                class="i1d-file-btn"
                @click="handleChooseFiles"
              >
                {{ t('business.fileSelection.selectFiles') }}
              </button>
              <button
                type="button"
                class="i1d-file-btn"
                :disabled="!transport.isDesktop()"
                :title="!transport.isDesktop() ? t('business.fileSelection.folderNotAvailableInWeb') : ''"
                @click="handleImportFolder"
              >
                {{ t('business.fileSelection.importFolder') }}
              </button>
              <label class="i1d-toggle-label">
                <input v-model="isRecursive" type="checkbox" />
                <span>{{ t('business.fileSelection.recursive') }}</span>
              </label>
              <div class="i1d-import-mode">
                <span class="i1d-import-mode-label">{{ t('business.fileSelection.importMode') }}</span>
                <label class="i1d-radio-label" :title="t('business.fileSelection.replaceTooltip')">
                  <input v-model="importMode" type="radio" value="replace" />
                  <span>{{ t('business.fileSelection.replace') }}</span>
                </label>
                <label class="i1d-radio-label" :title="t('business.fileSelection.appendTooltip')">
                  <input v-model="importMode" type="radio" value="append" />
                  <span>{{ t('business.fileSelection.append') }}</span>
                </label>
              </div>
            </div>

            <!-- File count indicator / 文件计数指示器 -->
            <div v-if="files.length > 0" class="i1d-file-info">
              <span class="i1d-file-count">
                {{ t('business.fileSelection.filesSelected', { count: files.length }) }}
              </span>
              <button type="button" class="i1d-clear-all-btn" @click="clearAllFiles">
                {{ t('business.fileSelection.clearAll') }}
              </button>
            </div>
            <div v-else class="i1d-file-info i1d-file-info--muted">
              <span>{{ t('business.fileSelection.noFiles') }}</span>
            </div>
          </div>

        <!-- HDF5 dataset/channel/frame selector (only for .h5 with image datasets) / HDF5 选择器 -->
        <H5Selector
          v-model="h5Selection"
          :datasets="h5Datasets"
          @change="onH5SelectionChange"
        />

        <!-- Image preview (collapsible, default collapsed) / 图像预览（可折叠，默认收起） -->
        <div class="i1d-collapsible">
          <div class="i1d-section-toggle" @click="onPreviewToggle">
            <span class="i1d-toggle-icon">{{ previewExpanded ? '▾' : '▸' }}</span>
            <span>{{ t('business.sections.imagePreview') }}</span>
          </div>
          <div v-show="previewExpanded" class="i1d-collapsible-body">
            <div v-if="previewLoading" class="i1d-preview-loading">
              {{ t('business.sections.loading') }}
            </div>
            <div v-else-if="previewB64" class="i1d-preview-area">
              <div class="i1d-preview-image">
                <ImagePreview
                  :image-b64="previewB64"
                  :overlays="beamCenterOverlay"
                  :show-colorbar="true"
                  :colorbar-gradient="colorbarGradient"
                  :colorbar-min-label="colorbarMinLabel"
                  :colorbar-max-label="colorbarMaxLabel"
                  :placeholder="t('business.sections.noImage')"
                />
              </div>
              <div class="i1d-preview-info">
                <h4 class="i1d-info-title">{{ t('business.sections.imageInfo') }}</h4>
                <div v-if="currentPreviewFileName" class="i1d-info-item">
                  <span class="i1d-info-label">{{ t('business.sections.fileName') }}</span>
                  <span class="i1d-info-value">{{ currentPreviewFileName }}</span>
                </div>
                <template v-if="previewStats">
                  <div class="i1d-info-item">
                    <span class="i1d-info-label">Min</span>
                    <span class="i1d-info-value">{{ formatSci(previewStats.min) }}</span>
                  </div>
                  <div class="i1d-info-item">
                    <span class="i1d-info-label">Max</span>
                    <span class="i1d-info-value">{{ formatSci(previewStats.max) }}</span>
                  </div>
                  <div class="i1d-info-item">
                    <span class="i1d-info-label">Std</span>
                    <span class="i1d-info-value">{{ formatSci(previewStats.std) }}</span>
                  </div>
                </template>
                <template v-if="autoContrast">
                  <div class="i1d-info-item">
                    <span class="i1d-info-label">Auto range</span>
                    <span class="i1d-info-value">{{ formatSci(autoContrast.autoMin) }} – {{ formatSci(autoContrast.autoMax) }}</span>
                  </div>
                </template>
                <div v-if="resolvedBeamCenter" class="i1d-info-item">
                  <span class="i1d-info-label">{{ t('business.sections.beamCenter') }}</span>
                  <span class="i1d-info-value">{{ beamCenterLabel }}</span>
                </div>
              </div>
            </div>
            <div v-else class="i1d-preview-empty">
              {{ t('business.fileSelection.expandAfterSelect') }}
            </div>
          </div>
        </div>

        <!-- Thumbnail strip (collapsible, default collapsed) / 缩略图（可折叠，默认收起） -->
        <div class="i1d-collapsible">
          <div class="i1d-section-toggle" @click="onThumbToggle">
            <span class="i1d-toggle-icon">{{ thumbExpanded ? '▾' : '▸' }}</span>
            <span>{{ t('business.sections.thumbnails') }}</span>
          </div>
          <div v-show="thumbExpanded" class="i1d-collapsible-body">
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

        <!-- Run button / 运行按钮 -->
        <div class="i1d-run-section">
          <button
            type="button"
            class="i1d-run-btn"
            :disabled="!canRun"
            :data-testid="testIds.integrate1dRunBtn"
            @click="handleRun"
          >
            {{ t('integrate1d.runIntegration') }}
          </button>
        </div>

        <!-- Progress bar / 进度条 -->
        <TaskProgressBar
          v-if="state === 'running'"
          :task-id="taskId"
          :progress="progress"
          :message="progressMessage"
          @cancel="handleCancel"
        />

        <!-- Error state / 错误状态 -->
        <div v-if="state === 'error'" class="i1d-error" :data-testid="testIds.integrate1dError">
          <p>{{ t('integrate1d.errorPrefix') }} {{ errorMessage }}</p>
        </div>

        <!-- Empty state / 空状态 -->
        <div v-if="state === 'idle' && !resultCurves.length" class="i1d-empty">
          <p>{{ t('integrate1d.emptyState') }}</p>
        </div>

        <!-- Result chart / 结果图表 -->
        <div v-if="resultCurves.length" class="i1d-result" :data-testid="testIds.integrate1dResult">
          <h2 class="i1d-section-title">{{ t('integrate1d.resultTitle') }}</h2>
          <LineChart
            :traces="resultCurves"
            :x-label="xAxisLabel"
            :y-label="t('integrate1d.intensityLabel')"
            :x-unit="xAxisUnit"
            y-unit="a.u."
            :title="t('integrate1d.chartTitle')"
          />
        </div>

        <!-- Export dialog / 导出对话框 -->
        <ExportDialog
          v-if="resultCurves.length"
          :result="resultData"
          :formats="exportFormats"
          :data-testid="testIds.integrate1dExport"
          @export="handleExport"
        />
      </main>
    </div>
  </section>
</template>

<script setup lang="ts">
/**
 * Integrate1dView.vue — 1D径向积分页面 + 图像预览
 * 1-D Radial Integration page with image preview
 *
 * 使用pyFAI对探测器图像执行标准1D方位角积分（径向平均），并支持图像预览和缩略图浏览。
 * Performs standard 1-D azimuthal integration using pyFAI, with image preview and thumbnail browsing.
 */
import { ref, reactive, computed, onUnmounted, watch } from 'vue'
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
import PolarizationForm from '@/components/business/PolarizationForm.vue'
import H5Selector from '@/components/business/H5Selector.vue'
import type { H5DatasetInfo, H5Selection } from '@/components/business/H5Selector.vue'
import AdvancedOptionsForm from '@/components/business/AdvancedOptionsForm.vue'
import { UNIT_OPTIONS } from '@/components/business/AdvancedOptionsForm.vue'
import type { AdvancedOptions, IntegrationUnit, IntegrationAlgorithm, IntegratorType } from '@/components/business/AdvancedOptionsForm.vue'
import TaskProgressBar from '@/components/business/TaskProgressBar.vue'
import ExportDialog from '@/components/business/ExportDialog.vue'
import type { ExportFormat, ExportMode } from '@/components/business/ExportDialog.vue'
import FileDialogButton from '@/components/business/FileDialogButton.vue'
import LineChart from '@/components/charts/LineChart.vue'
import type { LineTrace } from '@/components/charts/LineChart.vue'
import ImagePreview from '@/components/charts/ImagePreview.vue'
import type { Overlay } from '@/components/charts/ImagePreview.vue'
import ThumbnailStrip from '@/components/business/ThumbnailStrip.vue'
import type { ThumbnailItem } from '@/components/business/ThumbnailStrip.vue'

// === Type definitions / 类型定义 ===

interface IntegrationResultItem {
  radial: number[]
  intensity: number[]
  label: string
  sigma?: number[] | null
}

interface PreviewMetadata {
  stats?: { min: number; max: number; adjustedMax: number; std: number }
  contrast?: { autoMin: number; autoMax: number; logMin: number; logMax: number }
  shape?: [number, number]
  width?: number
  height?: number
  metadata?: {
    width?: number
    height?: number
    h5Datasets?: H5DatasetInfo[]
    selectedDataset?: string
    selectedChannel?: number
    nChannels?: number
    totalFrames?: number
    frameIndex?: number
  }
}

interface ScanFolderResult {
  files?: string[]
}

interface GeometryCenterResult {
  centerX?: number
  centerY?: number
}

type PageState = 'idle' | 'running' | 'done' | 'error'

// === Composables / 组合函数 ===

const { t } = useI18n()
const toast = useToast()
const transport = useTransport()

// === Colormap options / 色图选项 ===

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

// === Unit options (imported from AdvancedOptionsForm) / 单位选项（从 AdvancedOptionsForm 导入） ===

const unitOptions = UNIT_OPTIONS

function onUnitChange(event: Event): void {
  const val = (event.target as HTMLSelectElement).value as IntegrationUnit
  Object.assign(advancedOptions, { unit: val })
}

// === Form state / 表单状态 ===

const geometryParams = ref<GeometryParams>({
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

const polarizationFactor = ref<number | null>(null)

const advancedOptions = reactive<AdvancedOptions>({
  nptRad: 1000,
  nptAzim: 360,
  radialMin: null,
  radialMax: null,
  unit: 'q_A',
  correctSolidAngle: true,
  dropEmptyBins: true,
  algorithm: 'splitpixel',
  integrator: 'ng',
})

// === File state / 文件状态 ===

const files = ref<string[]>([])
const isRecursive = ref(false)
const importFolderPath = ref<string | null>(null)
type ImportMode = 'replace' | 'append'
const importMode = ref<ImportMode>('replace')

const dataFileFilters = [
  { name: 'Detector Images', extensions: ['edf', 'tif', 'tiff', 'h5', 'hdf5'] },
]

/** First file path — used by integration task / 第一个文件路径 — 用于积分任务 */
const dataFilePath = computed(() => files.value[0] ?? null)

const fileName = computed(() => {
  const path = dataFilePath.value
  if (!path) return ''
  const sep = path.includes('/') ? '/' : '\\'
  const parts = path.split(sep)
  return parts[parts.length - 1] || path
})

const currentPreviewFileName = computed(() => {
  const path = files.value[selectedPreviewIndex.value] ?? files.value[0]
  if (!path) return ''
  const sep = path.includes('/') ? '/' : '\\'
  const parts = path.split(sep)
  return parts[parts.length - 1] || path
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
  h5Datasets.value = []
  h5Selection.value = { dataset: '', channel: 0, frame: 0 }
}

// === Preview state / 预览状态 ===

const previewB64 = ref<string | null>(null)
const previewStats = ref<{ min: number; max: number; adjustedMax: number; std: number } | null>(null)
const autoContrast = ref<{ autoMin: number; autoMax: number; logMin: number; logMax: number } | null>(null)
const previewLoading = ref(false)
const selectedPreviewIndex = ref(0)
const resolvedBeamCenter = ref<{ x: number; y: number } | null>({ x: geometryParams.value.centerX, y: geometryParams.value.centerY })
const previewImageSize = ref<{ width: number; height: number; origWidth: number; origHeight: number } | null>(null)

// === H5 dataset/channel/frame selection / H5 数据集/通道/帧选择 ===

const h5Datasets = ref<H5DatasetInfo[]>([])
const h5Selection = ref<H5Selection>({ dataset: '', channel: 0, frame: 0 })

// === Display settings / 显示设置 ===

const colormap = ref('smooth_WAXS_foxtrot')
const useLog = ref(true)

// === Thumbnail state / 缩略图状态 ===

const thumbnailItems = ref<ThumbnailItem[]>([])
const thumbCurrentPage = ref(1)
const thumbPageSize = ref(10)
const thumbColsPerRow = ref(10)
const thumbLoading = ref(false)

// === Collapsible section state / 折叠区域状态 ===

const previewExpanded = ref(true)
const thumbExpanded = ref(false)
const displayExpanded = ref(false)
const maskExpanded = ref(false)
const advancedExpanded = ref(false)

// === Task execution state / 任务执行状态 ===

const state = ref<PageState>('idle')
const taskId = ref<string | null>(null)
const progress = ref(0)
const progressMessage = ref<string | null>(null)
const errorMessage = ref('')
const resultData = ref<unknown>(null)
const resultCurves = ref<LineTrace[]>([])

const exportFormats: ExportFormat[] = ['txt', 'csv', 'hdf5']

// Cleanup functions for event listeners / 事件监听器清理函数
let cleanupProgress: (() => void) | null = null
let cleanupResult: (() => void) | null = null
let cleanupError: (() => void) | null = null
let cleanupBinaryData: (() => void) | null = null
let cleanupPreviewResult: (() => void) | null = null
let cleanupPreviewError: (() => void) | null = null

// === Computed / 计算属性 ===

const canRun = computed(() => {
  return files.value.length > 0 && state.value !== 'running'
})

const thumbTotalPages = computed(() =>
  Math.max(1, Math.ceil(files.value.length / thumbPageSize.value))
)

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

const beamCenterOverlay = computed<Overlay[]>(() => {
  if (!resolvedBeamCenter.value || !previewImageSize.value) return []
  // pyFAI: center_x = poni2/pixel2, center_y = poni1/pixel1
  // center_y 就是数据数组的行索引，PIL 显示 PNG 时行 0 在顶部，
  // 直接用作 display Y 坐标即可，无需翻转。
  // matplotlib origin="lower" 会同时翻转图像和坐标轴，所以 Streamlit 版
  // 直接 scatter(center_x, center_y) 也正确——但这并不意味着 PIL 版需要额外翻转。
  const px = resolvedBeamCenter.value.x
  const py = resolvedBeamCenter.value.y
  if (!Number.isFinite(px) || !Number.isFinite(py)) return []
  return [{ type: 'beamCenter', x: px, y: py }]
})

const beamCenterLabel = computed(() => {
  if (!resolvedBeamCenter.value) return '—'
  return `(${resolvedBeamCenter.value.x.toFixed(2)}, ${resolvedBeamCenter.value.y.toFixed(2)})`
})

/** Unit label mapping for x-axis / X轴单位标签映射 */
const UNIT_LABELS: Record<IntegrationUnit, string> = {
  'q_nm': 'q',
  'q_A': 'q',
  '2th_deg': '2θ',
  '2th_rad': '2θ',
}

/** Unit suffix for x-axis / X轴单位后缀 */
const UNIT_SUFFIXES: Record<IntegrationUnit, string> = {
  'q_nm': 'nm⁻¹',
  'q_A': 'Å⁻¹',
  '2th_deg': 'deg',
  '2th_rad': 'rad',
}

const xAxisLabel = computed(() => UNIT_LABELS[advancedOptions.unit])
const xAxisUnit = computed(() => UNIT_SUFFIXES[advancedOptions.unit])

// === Helpers / 辅助函数 ===

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

function buildThumbRenderSettings(): Record<string, unknown> {
  // 缩略图使用自动对比度：不传 clim 让 Python 用图像数据自动计算
  // Thumbnails use auto contrast: omit clim so Python computes from data
  return {
    cmap: colormap.value,
    use_log: useLog.value,
  }
}

function buildGeometryPayload(): Record<string, unknown> {
  return {
    poniPath: geometryParams.value.poniPath ?? undefined,
    pixel1: geometryParams.value.pixel1,
    pixel2: geometryParams.value.pixel2,
    distance: geometryParams.value.distance,
    wavelength: geometryParams.value.wavelength,
    centerX: geometryParams.value.centerX,
    centerY: geometryParams.value.centerY,
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
  resolvedBeamCenter.value = { x: geometryParams.value.centerX, y: geometryParams.value.centerY }
}

function isValidCurve(result: IntegrationResultItem): boolean {
  return (
    Array.isArray(result.radial) &&
    Array.isArray(result.intensity) &&
    result.radial.length > 0 &&
    result.intensity.length > 0
  )
}

// === File handlers / 文件处理 ===

async function handleChooseFiles(): Promise<void> {
  const result = await transport.selectFiles({
    filters: dataFileFilters,
    multiSelections: true,
  })
  if (!result) return
  const paths = Array.isArray(result) ? result : [result]
  if (importMode.value === 'append') {
    // Append mode: add new files to existing list, deduplicate
    const existingSet = new Set(files.value)
    const newFiles = paths.filter(p => !existingSet.has(p))
    files.value = [...files.value, ...newFiles]
  } else {
    // Replace mode: clear and set new files
    files.value = paths
  }
  importFolderPath.value = null
  selectedPreviewIndex.value = 0
  thumbnailItems.value = []
  h5Datasets.value = []
  h5Selection.value = { dataset: '', channel: 0, frame: 0 }
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
      // Append mode: add new files to existing list, deduplicate
      const existingSet = new Set(files.value)
      const newFiles = found.filter(p => !existingSet.has(p))
      files.value = [...files.value, ...newFiles]
    } else {
      // Replace mode: clear and set new files
      files.value = found
    }
    selectedPreviewIndex.value = 0
    thumbnailItems.value = []
    h5Datasets.value = []
    h5Selection.value = { dataset: '', channel: 0, frame: 0 }
    await loadPreviewIfExpanded()
    loadThumbnailPageIfExpanded()
  } catch (err) {
    toast.push({
      title: t('integrate1d.errorTitle'),
      message: err instanceof Error ? err.message : String(err),
      tone: 'error',
    })
  }
}

// === Preview loading / 预览加载 ===

async function loadPreview(filePath: string): Promise<void> {
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
    // 4D h5: pass dataset/channel/frame so the preview reflects the user's selection.
    // On first load of a file h5Datasets is empty (reset by the file-change handler),
    // so no dataset is sent and the backend auto-detects the default.
    const isH5 = h5Datasets.value.length > 0
    const response = await transport.submitTask('viewer_config', {
      action: 'open_file',
      filePath,
      frame: h5Selection.value.frame,
      ...(isH5 ? {
        dataset: h5Selection.value.dataset || undefined,
        channel: h5Selection.value.channel,
      } : {}),
      settings: buildRenderSettings(),
    })

    cleanupBinaryData = transport.onTaskBinaryData(response.taskId, (payload) => {
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
      // Use metadata dimensions (original image size) for beam center Y-flip
      previewImageSize.value = {
        width: 0,
        height: 0,
        origWidth: data.metadata?.width ?? 0,
        origHeight: data.metadata?.height ?? 0,
      }

      // Capture H5 dataset metadata for the selector / 同步 HDF5 数据集元数据
      const md = data.metadata
      h5Datasets.value = Array.isArray(md?.h5Datasets) ? md!.h5Datasets! : []
      if (h5Datasets.value.length > 0) {
        const sel = md?.selectedDataset ?? h5Datasets.value[0]?.path ?? ''
        // Sync selection to the backend-rendered dataset on new-file loads.
        // Selection-change reloads already request this dataset, so no reset (no loop).
        if (sel && h5Selection.value.dataset !== sel) {
          h5Selection.value = { dataset: sel, channel: 0, frame: 0 }
        }
      } else if (h5Selection.value.dataset) {
        h5Selection.value = { dataset: '', channel: 0, frame: 0 }
      }

      previewLoading.value = false
    })

    cleanupPreviewError = transport.onTaskError(response.taskId, (payload) => {
      previewLoading.value = false
      toast.push({
        title: t('integrate1d.errorTitle'),
        message: payload.error,
        tone: 'error',
      })
    })
  } catch (err) {
    previewLoading.value = false
    toast.push({
      title: t('integrate1d.errorTitle'),
      message: err instanceof Error ? err.message : String(err),
      tone: 'error',
    })
  }
}

async function loadPreviewIfExpanded(): Promise<void> {
  if (previewExpanded.value && files.value.length > 0) {
    const path = files.value[selectedPreviewIndex.value] ?? files.value[0]
    if (path) await loadPreview(path)
  }
}

function onPreviewToggle(): void {
  previewExpanded.value = !previewExpanded.value
  if (previewExpanded.value && files.value.length > 0 && !previewB64.value) {
    const path = files.value[selectedPreviewIndex.value] ?? files.value[0]
    if (path) loadPreview(path)
  }
}

/** Reload preview when the H5 dataset/channel/frame selection changes */
function onH5SelectionChange(): void {
  if (previewExpanded.value && files.value.length > 0) {
    const path = files.value[selectedPreviewIndex.value] ?? files.value[0]
    if (path) loadPreview(path)
  }
}

// === Thumbnail loading / 缩略图加载 ===

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
  const filePath = files.value[index]
  if (filePath) {
    // Switching to a different file: reset H5 selection so a stale dataset isn't sent
    h5Datasets.value = []
    h5Selection.value = { dataset: '', channel: 0, frame: 0 }
    loadPreview(filePath)
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

// === Integration run handler / 积分运行处理 ===

async function handleRun(): Promise<void> {
  if (files.value.length === 0 || state.value === 'running') return

  // Reset state / 重置状态
  state.value = 'running'
  progress.value = 0
  progressMessage.value = null
  errorMessage.value = ''
  resultCurves.value = []
  resultData.value = null

  // Build params payload / 构建参数载荷
  // 通过 main process 的 normalizeTaskParams 标准化后发送给 Python 后端
  // main process 从 filePath/files, geometry, mask, advanced, polarizationFactor 读取参数
  const params: Record<string, unknown> = {
    files: [...files.value],
    filePath: files.value[0] ?? undefined,
    // 4D h5 selection — forwarded to the backend integration handler
    dataset: h5Selection.value.dataset || undefined,
    channel: h5Selection.value.channel,
    frame: h5Selection.value.frame,
    geometry: {
      poniPath: geometryParams.value.poniPath ?? undefined,
      pixel1: geometryParams.value.pixel1,
      pixel2: geometryParams.value.pixel2,
      distance: geometryParams.value.distance,
      wavelength: geometryParams.value.wavelength,
      centerX: geometryParams.value.centerX,
      centerY: geometryParams.value.centerY,
    },
    mask: {
      valueRangeMin: maskConfig.value.valueRangeMin,
      valueRangeMax: maskConfig.value.valueRangeMax,
      deadPixelThreshold: maskConfig.value.deadPixelThreshold,
      customMaskPath: maskConfig.value.customMaskPath,
    },
    polarizationFactor: polarizationFactor.value,
    advanced: {
      nptRad: advancedOptions.nptRad,
      nptAzim: advancedOptions.nptAzim,
      radialMin: advancedOptions.radialMin,
      radialMax: advancedOptions.radialMax,
      unit: advancedOptions.unit,
      correctSolidAngle: advancedOptions.correctSolidAngle,
      dropEmptyBins: advancedOptions.dropEmptyBins,
      algorithm: advancedOptions.algorithm ?? 'splitpixel',
      integrator: advancedOptions.integrator ?? 'ng',
    },
  }

  try {
    const response = await transport.submitTask('integrate1d', params)
    taskId.value = response.taskId

    // Register progress listener / 注册进度监听器
    cleanupProgress = transport.onTaskProgress(response.taskId, (payload) => {
      progress.value = payload.progress
      progressMessage.value = payload.message ?? null
    })

    // Register result listener / 注册结果监听器
    // 后端返回 { status, results: [{ radial, intensity, filename }] }
    // 需要映射 filename → label 供 LineChart 使用
    cleanupResult = transport.onTaskResult(response.taskId, (payload) => {
      const rawResults = payload.data as { results?: IntegrationResultItem[] }
      const results = rawResults?.results ?? (Array.isArray(payload.data) ? payload.data as IntegrationResultItem[] : [])
      const validResults = results.filter(isValidCurve)

      if (validResults.length === 0) {
        taskId.value = null
        state.value = 'error'
        errorMessage.value = 'Integration returned no displayable curves.'
        toast.push({
          title: t('integrate1d.errorTitle'),
          message: errorMessage.value,
          tone: 'error',
        })
        return
      }

      resultCurves.value = validResults.map((r) => ({
          x: r.radial,
          y: r.intensity,
          name: r.label || (r as Record<string, unknown>).filename as string || '',
        }))
      resultData.value = validResults
      taskId.value = null
      state.value = 'done'
      progress.value = 1
      toast.push({
        title: t('integrate1d.successTitle'),
        message: t('integrate1d.successMessage', { count: resultCurves.value.length }),
        tone: 'success',
      })
    })

    // Register error listener / 注册错误监听器
    cleanupError = transport.onTaskError(response.taskId, (payload) => {
      taskId.value = null
      errorMessage.value = payload.error
      state.value = 'error'
      toast.push({
        title: t('integrate1d.errorTitle'),
        message: payload.error,
        tone: 'error',
      })
    })
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : String(err)
    state.value = 'error'
    toast.push({
      title: t('integrate1d.errorTitle'),
      message: errorMessage.value,
      tone: 'error',
    })
  }
}

function handleCancel(): void {
  state.value = 'idle'
  taskId.value = null
  progress.value = 0
  cleanupListeners()
}

async function handleExport(payload: { format: ExportFormat; path: string; mode: ExportMode }): Promise<void> {
  if (!resultData.value) return

  const unitMap: Record<string, string> = {
    q_nm: 'q_nm^-1', q_A: 'q_A^-1',
    '2th_deg': '2th_deg', '2th_rad': '2th_rad',
    r_mm: 'r_mm',
  }
  const unit = unitMap[advancedOptions.unit] || advancedOptions.unit || 'q_nm^-1'

  const results = JSON.parse(JSON.stringify(
    (resultData.value as IntegrationResultItem[]).map((r) => ({
      radial: r.radial,
      intensity: r.intensity,
      label: r.label || '',
      unit,
      sigma: r.sigma ?? null,
    }))
  ))

  try {
    const response = await transport.submitTask('export_integration', {
      format: payload.format,
      outputPath: payload.path,
      dataType: '1d',
      mode: payload.mode,
      results,
    })

    const removeOk = transport.onTaskResult(response.taskId, (r) => {
      const data = r.data as { success?: boolean; error?: string; path?: string }
      if (data?.success) {
        toast.push({
          title: t('integrate1d.exportTitle'),
          message: `${payload.format.toUpperCase()} → ${data.path ?? payload.path}`,
          tone: 'success',
        })
      } else {
        toast.push({
          title: t('integrate1d.errorTitle'),
          message: data?.error ?? 'Export failed',
          tone: 'error',
        })
      }
      removeOk()
      removeErr()
    })
    const removeErr = transport.onTaskError(response.taskId, (e) => {
      toast.push({
        title: t('integrate1d.errorTitle'),
        message: e.error ?? 'Export failed',
        tone: 'error',
      })
      removeOk()
      removeErr()
    })
  } catch (err) {
    toast.push({
      title: t('integrate1d.errorTitle'),
      message: String(err),
      tone: 'error',
    })
  }
}

// === Cleanup / 清理 ===

function cleanupPreviewListeners(): void {
  cleanupBinaryData?.()
  cleanupBinaryData = null
  cleanupPreviewResult?.()
  cleanupPreviewResult = null
  cleanupPreviewError?.()
  cleanupPreviewError = null
}

function cleanupListeners(): void {
  cleanupProgress?.()
  cleanupProgress = null
  cleanupResult?.()
  cleanupResult = null
  cleanupError?.()
  cleanupError = null
  cleanupPreviewListeners()
}

// === Watchers / 监听器 ===

/** Re-render preview when display settings change / 显示设置变更时重新渲染预览 */
watch([colormap, useLog], () => {
  if (files.value.length > 0 && previewExpanded.value) {
    const path = files.value[selectedPreviewIndex.value] ?? files.value[0]
    if (path) loadPreview(path)
  }
  if (files.value.length > 0 && thumbExpanded.value) {
    loadThumbnailPage()
  }
})

watch(
  () => [
    geometryParams.value.poniPath,
    geometryParams.value.pixel1,
    geometryParams.value.pixel2,
    geometryParams.value.distance,
    geometryParams.value.wavelength,
    geometryParams.value.centerX,
    geometryParams.value.centerY,
  ],
  () => {
    if (files.value.length > 0 && previewExpanded.value) {
      // 几何参数变化时，重新解析中心并刷新预览图
      // Re-resolve beam center AND reload preview image on geometry change
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
  cleanupListeners()
})
</script>

<style scoped>
.integrate-1d-page {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.i1d-header {
  padding-bottom: 8px;
}

.i1d-header h1 {
  font-size: 1.5rem;
  font-weight: 700;
  margin: 0 0 6px;
  color: var(--text-primary);
}

.i1d-subtitle {
  font-size: 0.9375rem;
  color: var(--text-secondary);
  margin: 0;
}

.i1d-layout {
  display: grid;
  grid-template-columns: minmax(280px, 380px) minmax(0, 1fr);
  gap: 24px;
  align-items: start;
}

/* Sidebar / 侧边栏 */
.i1d-sidebar {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* Main area / 主区域 */
.i1d-main {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.i1d-section-title {
  font-size: 1rem;
  font-weight: 600;
  margin: 0 0 10px;
  color: var(--text-primary);
}

/* File section / 文件选择区 */
.i1d-file-section {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.i1d-file-buttons {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.i1d-file-btn {
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

.i1d-file-btn:hover {
  border-color: var(--border-hover);
  box-shadow: var(--shadow-sm);
}

/* Import mode toggle / 导入模式切换 */
.i1d-import-mode {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  border-radius: var(--radius-md);
  background: var(--bg-surface-alt);
  font-size: 0.8125rem;
}

.i1d-import-mode-label {
  color: var(--text-secondary);
  font-weight: 500;
  white-space: nowrap;
}

.i1d-radio-label {
  display: flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  color: var(--text-primary);
  white-space: nowrap;
}

.i1d-radio-label input[type="radio"] {
  accent-color: var(--primary);
  width: 14px;
  height: 14px;
}

/* Output Unit standalone / 独立输出单位选择 */
.i1d-output-unit {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 12px 14px;
}

.i1d-file-info {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 10px;
  border-radius: var(--radius-md);
  background: var(--bg-surface-alt);
}

.i1d-file-info--muted {
  background: transparent;
  padding: 4px 10px;
}

.i1d-file-count {
  flex: 1;
  font-family: var(--font-mono);
  font-size: 0.8125rem;
  color: var(--text-secondary);
}

.i1d-file-info--muted .i1d-file-count,
.i1d-file-info--muted span {
  color: var(--text-muted);
  font-style: italic;
}

.i1d-clear-all-btn {
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

.i1d-clear-all-btn:hover {
  border-color: var(--border-hover);
  color: var(--error);
}

/* Collapsible sections / 折叠区域 */
.i1d-collapsible {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.i1d-section-toggle {
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

.i1d-section-toggle:hover {
  background: var(--bg-surface-alt);
}

.i1d-toggle-icon {
  font-size: 0.75rem;
  color: var(--text-muted);
  width: 14px;
  text-align: center;
}

.i1d-collapsible-body {
  padding: 14px;
  border-top: 1px solid var(--border);
}

/* Display settings fields / 显示设置字段 */
.i1d-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 10px;
}

.i1d-label {
  font-size: 0.8125rem;
  color: var(--text-secondary);
  font-weight: 500;
}

.i1d-select {
  padding: 8px 10px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: 0.875rem;
  transition: border-color var(--transition-fast);
}

.i1d-select:focus {
  outline: none;
  border-color: var(--border-focus);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}

.i1d-toggle-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.875rem;
  color: var(--text-primary);
  cursor: pointer;
  user-select: none;
}

.i1d-toggle-label input[type="checkbox"] {
  accent-color: var(--primary);
  width: 16px;
  height: 16px;
}

/* Image preview area / 图像预览区域 */
.i1d-preview-loading {
  padding: 40px 24px;
  text-align: center;
  color: var(--text-muted);
  font-size: 0.9375rem;
}

.i1d-preview-area {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 200px;
  gap: 14px;
}

.i1d-preview-image {
  border-radius: var(--radius-md);
  overflow: hidden;
}

.i1d-preview-empty {
  padding: 24px;
  text-align: center;
  color: var(--text-muted);
  font-size: 0.875rem;
}

/* Preview info panel / 预览信息面板 */
.i1d-preview-info {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-self: start;
}

.i1d-info-title {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--text-secondary);
  margin: 0;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.i1d-info-item {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  font-size: 0.75rem;
  gap: 6px;
}

.i1d-info-label {
  color: var(--text-muted);
  font-weight: 500;
  white-space: nowrap;
}

.i1d-info-value {
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: 0.6875rem;
  text-align: right;
  word-break: break-all;
}

/* Run button / 运行按钮 */
.i1d-run-section {
  display: flex;
}

.i1d-run-btn {
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

.i1d-run-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.i1d-run-btn:not(:disabled):hover {
  opacity: 0.9;
}

/* Error / 错误 */
.i1d-error {
  padding: 14px 18px;
  border-radius: var(--radius-md);
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: var(--error);
  font-size: 0.875rem;
}

.i1d-error p {
  margin: 0;
}

/* Empty state / 空状态 */
.i1d-empty {
  padding: 40px 24px;
  text-align: center;
  color: var(--text-muted);
  font-size: 0.9375rem;
}

.i1d-empty p {
  margin: 0;
}

/* Result / 结果区 */
.i1d-result {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* Responsive / 响应式 */
@media (max-width: 960px) {
  .i1d-layout {
    grid-template-columns: 1fr;
  }

  .i1d-preview-area {
    grid-template-columns: 1fr;
  }
}
</style>
