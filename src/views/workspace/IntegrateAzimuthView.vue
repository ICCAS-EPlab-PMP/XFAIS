<template>
  <section class="azimuth-page" :data-testid="testIds.integrateAzimuthPage">
    <header class="az-header">
      <h1>{{ t('integrateAzimuth.title') }}</h1>
      <p class="az-subtitle">{{ t('integrateAzimuth.subtitle') }}</p>
    </header>

    <div class="az-layout">
      <!-- ===== Sidebar / 侧边栏 ===== -->
      <aside class="az-sidebar">
        <GeometryForm v-model="geometry" />

        <!-- Mask Import (collapsible, collapsed by default) / 掩膜导入（可折叠，默认收起） -->
        <div class="az-collapsible">
          <div class="az-section-toggle" @click="maskExpanded = !maskExpanded">
            <span class="az-toggle-icon">{{ maskExpanded ? '▾' : '▸' }}</span>
            <span>{{ t('business.sections.maskImport') }}</span>
          </div>
          <div v-show="maskExpanded" class="az-collapsible-body">
            <MaskBuilderForm v-model="maskConfig" :bare="true" />
          </div>
        </div>

        <PolarizationForm v-model="polarizationFactor" />

        <!-- Radial range / 径向范围 -->
        <fieldset class="az-fieldset">
          <legend class="az-legend">{{ t('integrateAzimuth.radialRange.title') }}</legend>
          <div class="az-grid">
            <label class="az-field">
              <span class="az-field-label">{{ t('integrateAzimuth.radialRange.unit') }}</span>
              <select
                class="az-select"
                :data-testid="testIds.azimuthRadialUnit"
                :value="radialUnit"
                @change="onRadialUnitChange"
              >
                <option v-for="u in radialUnitOptions" :key="u.value" :value="u.value">
                  {{ u.label }}
                </option>
              </select>
            </label>
            <label class="az-field">
              <span class="az-field-label">{{ t('integrateAzimuth.radialRange.min') }}</span>
              <input
                type="number"
                class="az-input"
                step="0.1"
                :value="radialMin"
                :data-testid="testIds.azimuthRadialMin"
                @input="onRadialInput('min', ($event.target as HTMLInputElement).value)"
              />
            </label>
            <label class="az-field">
              <span class="az-field-label">{{ t('integrateAzimuth.radialRange.max') }}</span>
              <input
                type="number"
                class="az-input"
                step="0.1"
                :value="radialMax"
                :data-testid="testIds.azimuthRadialMax"
                @input="onRadialInput('max', ($event.target as HTMLInputElement).value)"
              />
            </label>
            <p v-if="radialValidationError" class="az-error">
              {{ radialValidationError }}
            </p>
          </div>
        </fieldset>

        <!-- Azimuth range / 方位角范围 -->
        <fieldset class="az-fieldset">
          <legend class="az-legend">{{ t('integrateAzimuth.azimuthRange.title') }}</legend>
          <p class="az-fieldset-hint">{{ t('integrateAzimuth.azimuthRange.hint') }}</p>
          <div class="az-grid">
            <label class="az-field">
              <span class="az-field-label">{{ t('integrateAzimuth.azimuthRange.min') }}</span>
              <input
                type="number"
                class="az-input"
                min="-360"
                max="360"
                step="5"
                :value="azimuthMin"
                :data-testid="testIds.azimuthAzimuthMin"
                @input="onAzimuthInput('min', ($event.target as HTMLInputElement).value)"
              />
            </label>
            <label class="az-field">
              <span class="az-field-label">{{ t('integrateAzimuth.azimuthRange.max') }}</span>
              <input
                type="number"
                class="az-input"
                min="-360"
                max="360"
                step="5"
                :value="azimuthMax"
                :data-testid="testIds.azimuthAzimuthMax"
                @input="onAzimuthInput('max', ($event.target as HTMLInputElement).value)"
              />
            </label>
            <p v-if="azimuthValidationError" class="az-error">
              {{ azimuthValidationError }}
            </p>
          </div>
        </fieldset>

        <!-- Chi output unit / 方位角输出单位 -->
        <fieldset class="az-fieldset">
          <legend class="az-legend">{{ t('integrateAzimuth.chiUnit.title') }}</legend>
          <div class="az-radio-group">
            <label class="az-radio">
              <input
                type="radio"
                name="chi-unit"
                value="chi_deg"
                :checked="chiUnit === 'chi_deg'"
                :data-testid="testIds.azimuthChiUnitDeg"
                @change="chiUnit = 'chi_deg'"
              />
              <span>{{ t('integrateAzimuth.chiUnit.deg') }}</span>
            </label>
            <label class="az-radio">
              <input
                type="radio"
                name="chi-unit"
                value="chi_rad"
                :checked="chiUnit === 'chi_rad'"
                :data-testid="testIds.azimuthChiUnitRad"
                @change="chiUnit = 'chi_rad'"
              />
              <span>{{ t('integrateAzimuth.chiUnit.rad') }}</span>
            </label>
          </div>
        </fieldset>

        <!-- Integration params / 积分参数 -->
        <fieldset class="az-fieldset">
          <legend class="az-legend">{{ t('integrateAzimuth.params.title') }}</legend>
          <div class="az-grid">
            <label class="az-field">
              <span class="az-field-label">{{ t('integrateAzimuth.params.npt') }}</span>
              <input
                type="number"
                class="az-input"
                min="10"
                step="10"
                :value="npt"
                :data-testid="testIds.azimuthNpt"
                @input="npt = parseInt(($event.target as HTMLInputElement).value) || 360"
              />
            </label>
            <label class="az-field">
              <span class="az-field-label">{{ t('integrateAzimuth.params.nptRad') }}</span>
              <input
                type="number"
                class="az-input"
                min="1"
                step="10"
                :value="nptRad"
                :data-testid="testIds.azimuthNptRad"
                @input="nptRad = parseInt(($event.target as HTMLInputElement).value) || 100"
              />
            </label>
          </div>
          <label class="az-toggle-label" :title="t('business.advancedOptions.dropEmptyBinsHint')">
            <input v-model="dropEmptyBins" type="checkbox" :data-testid="testIds.azimuthDropEmptyBins" />
            <span>{{ t('business.advancedOptions.dropEmptyBins') }}</span>
          </label>
        </fieldset>

        <!-- Display settings (collapsible, default collapsed) / 显示设置（可折叠，默认收起） -->
        <div class="az-collapsible">
          <div class="az-section-toggle" @click="displayExpanded = !displayExpanded">
            <span class="az-toggle-icon">{{ displayExpanded ? '▾' : '▸' }}</span>
            <span>{{ t('business.sections.displaySettings') }}</span>
          </div>
          <div v-show="displayExpanded" class="az-collapsible-body">
            <div class="az-field">
              <label class="az-field-label">{{ t('business.display.colormap') }}</label>
              <select v-model="colormap" class="az-select">
                <option v-for="cm in colormapOptions" :key="cm" :value="cm">
                  {{ getColormapDisplayName(cm) }}
                </option>
              </select>
            </div>
            <label class="az-toggle-label">
              <input v-model="useLog" type="checkbox" />
              <span>{{ t('business.display.logScale') }}</span>
            </label>
          </div>
        </div>
      </aside>

      <!-- ===== Main area / 主区域 ===== -->
      <main class="az-main">
        <!-- File selection / 文件选择 -->
        <div class="az-file-section">
          <h2 class="az-section-title">{{ t('integrate1d.dataFiles') }}</h2>
          <div class="az-file-buttons">
            <button
              type="button"
              class="az-file-btn"
              @click="handleChooseFiles"
            >
              {{ t('business.fileSelection.selectFiles') }}
            </button>
            <button
              type="button"
              class="az-file-btn"
              :disabled="!transport.isDesktop()"
              :title="!transport.isDesktop() ? t('business.fileSelection.folderNotAvailableInWeb') : ''"
              @click="handleImportFolder"
            >
              {{ t('business.fileSelection.importFolder') }}
            </button>
            <label class="az-toggle-label">
              <input v-model="isRecursive" type="checkbox" />
              <span>{{ t('business.fileSelection.recursive') }}</span>
            </label>
            <div class="az-import-mode">
              <span class="az-import-mode-label">{{ t('business.fileSelection.importMode') }}</span>
              <label class="az-radio-label" :title="t('business.fileSelection.replaceTooltip')">
                <input v-model="importMode" type="radio" value="replace" />
                <span>{{ t('business.fileSelection.replace') }}</span>
              </label>
              <label class="az-radio-label" :title="t('business.fileSelection.appendTooltip')">
                <input v-model="importMode" type="radio" value="append" />
                <span>{{ t('business.fileSelection.append') }}</span>
              </label>
            </div>
          </div>

          <!-- File count indicator / 文件计数指示器 -->
          <div v-if="files.length > 0" class="az-file-info">
            <span class="az-file-count">
              {{ t('business.fileSelection.filesSelected', { count: files.length }) }}
            </span>
            <button type="button" class="az-clear-btn" @click="clearAllFiles">
              {{ t('business.fileSelection.clearAll') }}
            </button>
          </div>
          <div v-else class="az-file-info az-file-info--muted">
            <span>{{ t('business.fileSelection.noFiles') }}</span>
          </div>
        </div>

        <!-- HDF5 dataset/channel/frame selector (only for .h5 with image datasets) / HDF5 选择器 -->
        <H5Selector
          v-model="h5Selection"
          :datasets="h5Datasets"
          @change="onH5SelectionChange"
        />

        <!-- Image preview (collapsible) / 图像预览（可折叠） -->
        <div class="az-collapsible">
          <div class="az-section-toggle" @click="onPreviewToggle">
            <span class="az-toggle-icon">{{ previewExpanded ? '▾' : '▸' }}</span>
            <span>{{ t('business.sections.imagePreview') }}</span>
          </div>
          <div v-show="previewExpanded" class="az-collapsible-body">
            <div v-if="previewLoading" class="az-preview-loading">
              {{ t('business.sections.loading') }}
            </div>
            <div v-else-if="previewB64" class="az-preview-area">
              <div class="az-preview-image">
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
              <div class="az-preview-info">
                <h4 class="az-info-title">{{ t('business.sections.imageInfo') }}</h4>
                <div v-if="currentPreviewFileName" class="az-info-item">
                  <span class="az-info-label">{{ t('business.sections.fileName') }}</span>
                  <span class="az-info-value">{{ currentPreviewFileName }}</span>
                </div>
                <template v-if="previewStats">
                  <div class="az-info-item">
                    <span class="az-info-label">Min</span>
                    <span class="az-info-value">{{ formatSci(previewStats.min) }}</span>
                  </div>
                  <div class="az-info-item">
                    <span class="az-info-label">Max</span>
                    <span class="az-info-value">{{ formatSci(previewStats.max) }}</span>
                  </div>
                  <div class="az-info-item">
                    <span class="az-info-label">Std</span>
                    <span class="az-info-value">{{ formatSci(previewStats.std) }}</span>
                  </div>
                </template>
                <template v-if="autoContrast">
                  <div class="az-info-item">
                    <span class="az-info-label">Auto range</span>
                    <span class="az-info-value">{{ formatSci(autoContrast.autoMin) }} – {{ formatSci(autoContrast.autoMax) }}</span>
                  </div>
                </template>
                <div v-if="resolvedBeamCenter" class="az-info-item">
                  <span class="az-info-label">{{ t('business.sections.beamCenter') }}</span>
                  <span class="az-info-value">{{ beamCenterLabel }}</span>
                </div>
              </div>
            </div>
            <div v-else class="az-preview-empty">
              {{ t('business.fileSelection.expandAfterSelect') }}
            </div>
          </div>
        </div>

        <!-- Thumbnail strip (collapsible, default collapsed) / 缩略图（可折叠，默认收起） -->
        <div class="az-collapsible">
          <div class="az-section-toggle" @click="onThumbToggle">
            <span class="az-toggle-icon">{{ thumbExpanded ? '▾' : '▸' }}</span>
            <span>{{ t('business.sections.thumbnails') }}</span>
          </div>
          <div v-show="thumbExpanded" class="az-collapsible-body">
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

        <!-- Validation message / 校验消息 -->
        <p v-if="radialValidationError || azimuthValidationError" class="az-error-main">
          {{ radialValidationError || azimuthValidationError }}
        </p>

        <!-- Run button / 运行按钮 -->
        <div class="az-run-section">
          <button
            type="button"
            class="az-run-btn"
            :disabled="isRunning || !!radialValidationError || !!azimuthValidationError || files.length === 0"
            :data-testid="testIds.azimuthRunBtn"
            @click="handleRun"
          >
            {{ isRunning ? t('integrateAzimuth.running') : t('integrateAzimuth.run') }}
          </button>
        </div>

        <!-- Progress bar / 进度条 -->
        <TaskProgressBar
          v-if="isRunning"
          :task-id="taskId"
          :progress="progress"
          :message="progressMessage"
          @cancel="handleCancel"
        />

        <!-- Error message / 错误消息 -->
        <div v-if="errorMessage" class="az-error-box">
          <p>{{ errorMessage }}</p>
        </div>

        <!-- Chart result / 图表结果 -->
        <div v-if="chartTraces.length > 0" class="az-chart" :data-testid="testIds.azimuthChart">
          <h2 class="az-section-title">{{ t('integrateAzimuth.chartTitle') }}</h2>
          <LineChart
            :traces="chartTraces"
            :x-label="chiAxisLabel"
            :y-label="t('integrateAzimuth.axisLabels.intensity')"
            :title="t('integrateAzimuth.chartTitle')"
          />
        </div>

        <!-- Export / 导出 -->
        <ExportDialog
          v-if="chartTraces.length > 0"
          :result="exportData"
          :formats="['txt', 'csv', 'hdf5']"
          :data-testid="testIds.azimuthExport"
          @export="handleExport"
        />
      </main>
    </div>
  </section>
</template>

<script setup lang="ts">
/**
 * IntegrateAzimuthView.vue — 方位角 χ 积分页面
 * Azimuthal χ integration page
 *
 * 在指定径向范围内对方位角 χ 积分，输出强度随 χ 角的分布。
 * Integrates diffraction intensity as a function of azimuthal angle χ
 * within a specified radial range.
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
import PolarizationForm from '@/components/business/PolarizationForm.vue'
import H5Selector from '@/components/business/H5Selector.vue'
import type { H5DatasetInfo, H5Selection } from '@/components/business/H5Selector.vue'
import TaskProgressBar from '@/components/business/TaskProgressBar.vue'
import ExportDialog from '@/components/business/ExportDialog.vue'
import type { ExportFormat, ExportMode } from '@/components/business/ExportDialog.vue'
import LineChart from '@/components/charts/LineChart.vue'
import type { LineTrace } from '@/components/charts/LineChart.vue'
import ImagePreview from '@/components/charts/ImagePreview.vue'
import type { Overlay } from '@/components/charts/ImagePreview.vue'
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
    h5Datasets?: H5DatasetInfo[]
    selectedDataset?: string
    selectedChannel?: number
    nChannels?: number
    totalFrames?: number
    frameIndex?: number
  }
}

interface GeometryCenterResult {
  centerX?: number
  centerY?: number
}

interface ScanFolderResult {
  files?: string[]
}

// === Composables / 组合函数 ===

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

// ── Radial unit options / 径向单位选项 ──

const radialUnitOptions = [
  { value: 'q_nm^-1', label: 'q (nm⁻¹)' },
  { value: 'q_A^-1', label: 'q (Å⁻¹)' },
  { value: '2th_deg', label: '2θ (°)' },
  { value: 'r_mm', label: 'r (mm)' },
] as const

// ── State / 状态 ──

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

const polarizationFactor = ref<number | null>(null)

const radialUnit = ref('q_A^-1')
const radialMin = ref(0.98)
const radialMax = ref(1.02)
const chiUnit = ref<'chi_deg' | 'chi_rad'>('chi_deg')
const npt = ref(360)
const nptRad = ref(100)
/** Drop fully-masked empty bins from the result (default on). / 剔除完全遮蔽的空 bin（默认开）。 */
const dropEmptyBins = ref(true)
/** Azimuth integration range in degrees. Default -180..180 = full 360°. */
const azimuthMin = ref(-180)
const azimuthMax = ref(180)

const filePath = ref<string | null>(null)

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

/** Legacy compat: filePath tracks the first / active file / 兼容：filePath 追踪第一个/活动文件 */
watch(activeFilePath, (v) => { filePath.value = v }, { immediate: true })

const fileName = computed(() => {
  const path = filePath.value
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

// ── Preview state / 预览状态 ──

const previewB64 = ref<string | null>(null)
const previewStats = ref<{ min: number; max: number; adjustedMax: number; std: number } | null>(null)
const autoContrast = ref<{ autoMin: number; autoMax: number; logMin: number; logMax: number } | null>(null)
const previewLoading = ref(false)
const resolvedBeamCenter = ref<{ x: number; y: number } | null>(
  { x: geometry.value.centerX, y: geometry.value.centerY }
)
const previewImageSize = ref<{ width: number; height: number; origWidth: number; origHeight: number } | null>(null)

// ── H5 dataset/channel/frame selection / H5 数据集/通道/帧选择 ──

const h5Datasets = ref<H5DatasetInfo[]>([])
const h5Selection = ref<H5Selection>({ dataset: '', channel: 0, frame: 0 })

// ── Display settings / 显示设置 ──

const colormap = ref('smooth_WAXS_foxtrot')
const useLog = ref(true)

// ── Collapsible section state / 折叠区域状态 ──

const previewExpanded = ref(true)
const thumbExpanded = ref(false)
const displayExpanded = ref(false)
const maskExpanded = ref(false)

// ── Thumbnail state / 缩略图状态 ──

const thumbnailItems = ref<ThumbnailItem[]>([])
const thumbCurrentPage = ref(1)
const thumbPageSize = ref(10)
const thumbColsPerRow = ref(10)
const thumbLoading = ref(false)

// ── Task state / 任务状态 ──

const isRunning = ref(false)
const taskId = ref<string | null>(null)
const progress = ref(0)
const progressMessage = ref<string | null>(null)
const errorMessage = ref<string | null>(null)

// ── Result state / 结果状态 ──

const chartTraces = ref<LineTrace[]>([])
const exportData = ref<unknown>(null)

// Cleanup functions / 清理函数
let cleanupPreviewBinary: (() => void) | null = null
let cleanupPreviewResult: (() => void) | null = null
let cleanupPreviewError: (() => void) | null = null

// ── Validation / 校验 ──

const radialValidationError = computed<string | null>(() => {
  if (radialMin.value >= radialMax.value) {
    return t('integrateAzimuth.errors.radialRange')
  }
  return null
})

const azimuthValidationError = computed<string | null>(() => {
  if (azimuthMin.value >= azimuthMax.value) {
    return t('integrateAzimuth.azimuthRange.errorMinMax')
  }
  return null
})

// ── Computed / 计算属性 ──

const thumbTotalPages = computed(() =>
  Math.max(1, Math.ceil(files.value.length / thumbPageSize.value))
)

const chiAxisLabel = computed(() => {
  return chiUnit.value === 'chi_deg'
    ? t('integrateAzimuth.axisLabels.chiDeg')
    : t('integrateAzimuth.axisLabels.chiRad')
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

const beamCenterOverlay = computed<Overlay[]>(() => {
  if (!resolvedBeamCenter.value || !previewImageSize.value) return []
  const px = resolvedBeamCenter.value.x
  const py = resolvedBeamCenter.value.y
  if (!Number.isFinite(px) || !Number.isFinite(py)) return []
  return [{ type: 'beamCenter', x: px, y: py }]
})

const beamCenterLabel = computed(() => {
  if (!resolvedBeamCenter.value) return '—'
  return `(${resolvedBeamCenter.value.x.toFixed(2)}, ${resolvedBeamCenter.value.y.toFixed(2)})`
})

// ── Helpers / 辅助函数 ──

function formatSci(value: number): string {
  if (!Number.isFinite(value)) return '—'
  if (value === 0) return '0'
  return value.toExponential(3)
}

function submitAndWait(route: string, params: Record<string, unknown>): Promise<unknown> {
  return new Promise((resolve, reject) => {
    transport.submitTask(route, params).then(response => {
      // Register both listeners, but unsubscribe whichever fires first so we
      // never leak handlers across a long session of preview/thumbnail calls.
      // 注册两个监听器，先触发的负责清理双方，避免预览/缩略图长会话中累积泄漏。
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
      offResult = transport.onTaskResult(response.taskId, p => finish(() => resolve(p.data)))
      offError = transport.onTaskError(response.taskId, p => finish(() => reject(new Error(p.error))))
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
      const existingSet = new Set(files.value)
      const newFiles = found.filter(p => !existingSet.has(p))
      files.value = [...files.value, ...newFiles]
    } else {
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
      title: t('integrateAzimuth.title'),
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
    // 4D h5: pass dataset/channel/frame so the preview reflects the user's selection.
    // On first load of a file h5Datasets is empty (reset by the file-change handler),
    // so no dataset is sent and the backend auto-detects the default.
    const isH5 = h5Datasets.value.length > 0
    const response = await transport.submitTask('viewer_config', {
      action: 'open_file',
      filePath: path,
      frame: h5Selection.value.frame,
      ...(isH5 ? {
        dataset: h5Selection.value.dataset || undefined,
        channel: h5Selection.value.channel,
      } : {}),
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
        title: t('integrateAzimuth.title'),
        message: payload.error,
        tone: 'error',
      })
    })
  } catch (err) {
    previewLoading.value = false
    toast.push({
      title: t('integrateAzimuth.title'),
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

/** Reload preview when the H5 dataset/channel/frame selection changes */
function onH5SelectionChange(): void {
  if (previewExpanded.value && activeFilePath.value) {
    loadPreview(activeFilePath.value)
  }
}

// ── Cleanup / 清理 ──

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

      try {
        const result = await submitAndWait('viewer_config', {
          action: 'preview',
          filePath: path,
          thumb_render_settings: buildThumbRenderSettings(),
        })

        const thumbData = result as { b64?: string; previewB64?: string }
        // Per-item try/catch: a single unreadable/corrupt file pushes a
        // placeholder instead of blanking the whole page. The previous
        // blanket catch made any one failure look like "no thumbnails".
        // 逐项捕获：单个不可读/损坏的文件仅占位，不再清空整页。
        items.push({
          index: start + i,
          b64: typeof thumbData?.b64 === 'string'
            ? thumbData.b64
            : (typeof thumbData?.previewB64 === 'string' ? thumbData.previewB64 : ''),
          label,
        })
      } catch (err) {
        console.error(`[IntegrateAzimuth] thumbnail render failed for "${label}":`, err)
        items.push({ index: start + i, b64: '', label })
      }
    }

    thumbnailItems.value = items
  } catch (err) {
    // Only catastrophic (non-render) failures reach here — keep whatever
    // items we have rather than wiping them silently.
    // 仅灾难性（非渲染）失败到达此处，保留已得项而非静默清空。
    console.error('[IntegrateAzimuth] loadThumbnailPage aborted:', err)
    if (items.length) thumbnailItems.value = items
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
    // Switching to a different file: reset H5 selection so a stale dataset isn't sent
    h5Datasets.value = []
    h5Selection.value = { dataset: '', channel: 0, frame: 0 }
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

// ── Handlers / 处理函数 ──

function onRadialUnitChange(event: Event): void {
  const val = (event.target as HTMLSelectElement).value
  radialUnit.value = val
  // Sensible defaults based on unit / 根据单位设置合理默认值
  const defaults: Record<string, [number, number]> = {
    'q_nm^-1': [1.0, 20.0],
    'q_A^-1': [0.98, 1.02],
    '2th_deg': [1.0, 30.0],
    'r_mm': [5.0, 100.0],
  }
  const [lo, hi] = defaults[val] ?? [1.0, 20.0]
  radialMin.value = lo
  radialMax.value = hi
}

function onRadialInput(field: 'min' | 'max', raw: string): void {
  const num = parseFloat(raw)
  if (isNaN(num)) return
  if (field === 'min') radialMin.value = num
  else radialMax.value = num
}

function onAzimuthInput(field: 'min' | 'max', raw: string): void {
  const num = parseFloat(raw)
  if (isNaN(num)) return
  if (field === 'min') azimuthMin.value = num
  else azimuthMax.value = num
}

async function handleRun(): Promise<void> {
  if (!activeFilePath.value) return
  if (radialValidationError.value) return
  if (azimuthValidationError.value) return

  isRunning.value = true
  progress.value = 0
  progressMessage.value = null
  errorMessage.value = null
  chartTraces.value = []
  exportData.value = null

  try {
    const params: Record<string, unknown> = {
      filePath: activeFilePath.value,
      files: [...files.value],
      // 4D h5 selection — forwarded to the backend integration handler
      dataset: h5Selection.value.dataset || undefined,
      channel: h5Selection.value.channel,
      frame: h5Selection.value.frame,
      geometry: { ...geometry.value },
      mask: { ...maskConfig.value },
      polarizationFactor: polarizationFactor.value,
      radialUnit: radialUnit.value,
      radialMin: radialMin.value,
      radialMax: radialMax.value,
      azimuthMin: azimuthMin.value,
      azimuthMax: azimuthMax.value,
      chiUnit: chiUnit.value,
      npt: npt.value,
      nptRad: nptRad.value,
      dropEmptyBins: dropEmptyBins.value,
    }

    const response = await transport.submitTask('integrate_azimuth', params)
    taskId.value = response.taskId

    // Listen for progress / 监听进度
    const unsubProgress = transport.onTaskProgress(response.taskId, (payload) => {
      progress.value = payload.progress
      progressMessage.value = payload.message ?? null
    })

    // Listen for result / 监听结果
    const unsubResult = transport.onTaskResult(response.taskId, (payload) => {
      const result = payload.data as {
        results?: Array<{ chi: number[]; intensity: number[]; label?: string }>
        failed?: Array<{ file: string; reason: string }>
      } | null

      const results = Array.isArray(result?.results)
        ? result.results.filter((item) => (
          Array.isArray(item.chi)
          && Array.isArray(item.intensity)
          && item.chi.length > 0
          && item.intensity.length > 0
        ))
        : []

      const failedList = Array.isArray(result?.failed) ? result.failed : []
      if (failedList.length > 0) {
        toast.push({
          title: `${failedList.length} file(s) failed`,
          message: failedList.map(f => `${f.file}: ${f.reason}`).join('; '),
          tone: 'warning',
        })
      }

      if (results.length > 0) {
        chartTraces.value = results.map((item) => ({
          x: item.chi,
          y: item.intensity,
          name: item.label ?? '',
        }))
        exportData.value = { results }
      } else {
        errorMessage.value = 'Integration returned no displayable azimuth profile.'
      }

      unsubProgress()
      unsubResult()
      unsubError()
      isRunning.value = false
      taskId.value = null
    })

    // Listen for errors / 监听错误
    const unsubError = transport.onTaskError(response.taskId, (payload) => {
      errorMessage.value = payload.error
      unsubProgress()
      unsubResult()
      unsubError()
      isRunning.value = false
      taskId.value = null
    })
  } catch (err) {
    errorMessage.value = String(err)
    isRunning.value = false
    taskId.value = null
  }
}

async function handleCancel(): Promise<void> {
  if (taskId.value) {
    try {
      await transport.cancelTask(taskId.value)
    } catch {
      // Task may already be completed / 任务可能已完成
    }
  }
  isRunning.value = false
  taskId.value = null
}

async function handleExport(payload: { format: ExportFormat; path: string; mode: ExportMode }): Promise<void> {
  if (!exportData.value) return

  const src = exportData.value as { results?: Array<{ chi: number[]; intensity: number[]; label?: string }> }
  const results = JSON.parse(JSON.stringify(
    (src.results ?? []).map((item) => ({
      radial: item.chi,
      intensity: item.intensity,
      label: item.label || 'azimuth',
      unit: chiUnit.value || 'chi_deg',
    }))
  ))

  if (results.length === 0) return

  try {
      const response = await transport.submitTask('export_integration', {
        format: payload.format,
        outputPath: payload.path,
        dataType: 'azimuth',
        mode: payload.mode,
        results,
      })

    const removeOk = transport.onTaskResult(response.taskId, (r) => {
      const data = r.data as { success?: boolean; error?: string; path?: string }
      if (data?.success) {
        toast.push({
          title: t('integrateAzimuth.title'),
          message: `${payload.format.toUpperCase()} → ${data.path ?? payload.path}`,
          tone: 'success',
        })
      } else {
        toast.push({ title: t('integrateAzimuth.title'), message: data?.error ?? 'Export failed', tone: 'error' })
      }
      removeOk(); removeErr()
    })
    const removeErr = transport.onTaskError(response.taskId, (e) => {
      toast.push({ title: t('integrateAzimuth.title'), message: e.error ?? 'Export failed', tone: 'error' })
      removeOk(); removeErr()
    })
  } catch (err) {
    toast.push({ title: t('integrateAzimuth.title'), message: String(err), tone: 'error' })
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
.azimuth-page {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.az-header h1 {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 6px;
}

.az-subtitle {
  font-size: 0.9375rem;
  color: var(--text-secondary);
  margin: 0;
}

.az-layout {
  display: grid;
  grid-template-columns: minmax(280px, 380px) minmax(0, 1fr);
  gap: 24px;
  align-items: start;
}

.az-sidebar {
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow-y: auto;
  padding-right: 4px;
}

.az-main {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.az-section-title {
  font-size: 1rem;
  font-weight: 600;
  margin: 0 0 10px;
  color: var(--text-primary);
}

/* ── File section (1D-style) / 文件选择区（1D风格） ── */

.az-file-section {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.az-file-buttons {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.az-file-btn {
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

.az-file-btn:hover {
  border-color: var(--border-hover);
  box-shadow: var(--shadow-sm);
}

/* Import mode toggle / 导入模式切换 */
.az-import-mode {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  border-radius: var(--radius-md);
  background: var(--bg-surface-alt);
  font-size: 0.8125rem;
}

.az-import-mode-label {
  color: var(--text-secondary);
  font-weight: 500;
  white-space: nowrap;
}

.az-radio-label {
  display: flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  color: var(--text-primary);
  white-space: nowrap;
}

.az-radio-label input[type="radio"] {
  accent-color: var(--primary);
  width: 14px;
  height: 14px;
}

/* File info / 文件信息 */
.az-file-info {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 10px;
  border-radius: var(--radius-md);
  background: var(--bg-surface-alt);
}

.az-file-info--muted {
  background: transparent;
  padding: 4px 10px;
}

.az-file-count {
  flex: 1;
  font-family: var(--font-mono);
  font-size: 0.8125rem;
  color: var(--text-secondary);
}

.az-file-info--muted .az-file-count,
.az-file-info--muted span {
  color: var(--text-muted);
  font-style: italic;
}

.az-clear-btn {
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

.az-clear-btn:hover {
  border-color: var(--border-hover);
  color: var(--error);
}

/* ── Collapsible sections / 折叠区域 ── */

.az-collapsible {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.az-section-toggle {
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

.az-section-toggle:hover {
  background: var(--bg-surface-alt);
}

.az-toggle-icon {
  font-size: 0.75rem;
  color: var(--text-muted);
  width: 14px;
  text-align: center;
}

.az-collapsible-body {
  padding: 14px;
  border-top: 1px solid var(--border);
}

.az-toggle-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.875rem;
  color: var(--text-primary);
  cursor: pointer;
  user-select: none;
}

.az-toggle-label input[type="checkbox"] {
  accent-color: var(--primary);
  width: 16px;
  height: 16px;
}

/* ── Fieldset (azimuth-specific) / 方位角专用字段集 ── */

.az-fieldset {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.az-legend {
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--text-primary);
  padding: 0 6px;
}

.az-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 12px;
}

.az-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.az-field-label {
  font-size: 0.8125rem;
  color: var(--text-secondary);
  font-weight: 500;
}

.az-input,
.az-select {
  padding: 8px 10px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: 0.8125rem;
  transition: border-color var(--transition-fast);
}

.az-input:focus,
.az-select:focus {
  outline: none;
  border-color: var(--border-focus);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}

.az-radio-group {
  display: flex;
  gap: 20px;
}

.az-radio {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  font-size: 0.875rem;
  color: var(--text-primary);
}

.az-radio input[type="radio"] {
  accent-color: var(--primary);
  width: 16px;
  height: 16px;
}

.az-error {
  grid-column: 1 / -1;
  font-size: 0.8125rem;
  color: var(--error);
  margin: 0;
}

.az-error-main {
  font-size: 0.875rem;
  color: var(--error);
  margin: 0;
}

.az-error-box {
  padding: 14px 18px;
  border-radius: var(--radius-md);
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: var(--error);
  font-size: 0.875rem;
}

.az-error-box p {
  margin: 0;
}

/* ── Image preview area / 图像预览区域 ── */

.az-preview-loading {
  padding: 40px 24px;
  text-align: center;
  color: var(--text-muted);
  font-size: 0.9375rem;
}

.az-preview-area {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 200px;
  gap: 14px;
}

.az-preview-image {
  border-radius: var(--radius-md);
  overflow: hidden;
}

.az-preview-empty {
  padding: 24px;
  text-align: center;
  color: var(--text-muted);
  font-size: 0.875rem;
}

/* Preview info panel / 预览信息面板 */
.az-preview-info {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-self: start;
}

.az-info-title {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--text-secondary);
  margin: 0;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.az-info-item {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  font-size: 0.75rem;
  gap: 6px;
}

.az-info-label {
  color: var(--text-muted);
  font-weight: 500;
  white-space: nowrap;
}

.az-info-value {
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: 0.6875rem;
  text-align: right;
  word-break: break-all;
}

/* ── Run button / 运行按钮 ── */

.az-run-section {
  display: flex;
}

.az-run-btn {
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

.az-run-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.az-run-btn:not(:disabled):hover {
  opacity: 0.9;
}

.az-chart {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 16px;
  min-height: 360px;
}

/* ── Responsive / 响应式 ── */

@media (max-width: 960px) {
  .az-layout {
    grid-template-columns: 1fr;
  }

  .az-preview-area {
    grid-template-columns: 1fr;
  }
}
</style>
