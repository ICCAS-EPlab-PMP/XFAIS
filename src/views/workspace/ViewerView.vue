<template>
  <section class="viewer-page" :data-testid="testIds.viewerPage">
    <!-- Header / 页头 -->
    <header class="vw-header">
      <h1>{{ t('viewer.title') }}</h1>
      <p class="vw-subtitle">{{ t('viewer.subtitle') }}</p>
    </header>

    <div class="vw-layout">
      <!-- Sidebar: controls / 侧边栏：控制面板 -->
      <aside class="vw-sidebar">
        <!-- File selection / 文件选择 -->
        <div class="vw-card">
          <h3 class="vw-card-title">{{ t('viewer.fileSection') }}</h3>
          <div class="vw-file-actions">
            <button
              type="button"
              class="vw-export-btn vw-export-btn--secondary"
              @click="handleChooseFiles"
            >
              {{ t('viewer.selectFile') }}
            </button>

            <div class="vw-or-divider">— or —</div>

            <button
              type="button"
              class="vw-export-btn vw-export-btn--secondary"
              @click="handleImportFolder"
            >
              {{ t('viewer.selectFolder') }}
            </button>
            <span v-if="importFolder" class="vw-file-summary vw-file-summary--path">
              {{ importFolderDisplay }}
            </span>
            <label v-if="importFolder" class="vw-toggle">
              <input v-model="importRecursive" type="checkbox" />
              <span>{{ t('viewer.recursiveScan') }}</span>
            </label>
            <div class="vw-import-mode">
              <span class="vw-import-mode-label">{{ t('business.fileSelection.importMode') }}</span>
              <label class="vw-radio-label" :title="t('business.fileSelection.replaceTooltip')">
                <input v-model="importMode" type="radio" value="replace" />
                <span>{{ t('business.fileSelection.replace') }}</span>
              </label>
              <label class="vw-radio-label" :title="t('business.fileSelection.appendTooltip')">
                <input v-model="importMode" type="radio" value="append" />
                <span>{{ t('business.fileSelection.append') }}</span>
              </label>
            </div>

            <span v-if="selectedFiles.length" class="vw-file-summary">
              {{ selectedFiles.length }} files selected
            </span>
            <span v-else class="vw-file-summary vw-file-summary--muted">
              No files selected
            </span>
          </div>

          <!-- H5 dataset selector / H5 数据集选择器 -->
          <div v-if="h5Datasets.length" class="vw-field">
            <label class="vw-label">{{ t('viewer.dataset') }}</label>
            <select
              v-model="selectedDataset"
              class="vw-select"
              :data-testid="testIds.viewerDatasetSelect"
              @change="onDatasetChange"
            >
              <option v-for="ds in h5Datasets" :key="ds.path" :value="ds.path">
                {{ ds.path }} ({{ ds.ndim }}D)
              </option>
            </select>
          </div>

          <!-- Channel selector for 4D data / 4D 数据通道选择 -->
          <div v-if="channelCount > 1" class="vw-field">
            <label class="vw-label">{{ t('viewer.channel') }}</label>
            <select
              v-model="selectedChannel"
              class="vw-select"
              :data-testid="testIds.viewerChannelSelect"
              @change="onChannelChange"
            >
              <option v-for="i in channelCount" :key="i - 1" :value="i - 1">
                Ch{{ i - 1 }}
              </option>
            </select>
          </div>
        </div>

        <!-- Frame navigator / 帧导航 -->
        <div v-if="viewerFrameCount > 1" class="vw-card">
          <h3 class="vw-card-title">{{ t('viewer.frameNav') }}</h3>
          <div class="vw-frame-row">
            <button
              type="button"
              class="vw-frame-btn"
              :disabled="currentFrame <= 0"
              @click="prevFrame"
            >
              &#9664;
            </button>
            <input
              type="range"
              class="vw-slider vw-slider--frame"
              min="0"
              :max="viewerFrameCount - 1"
              :value="currentFrame"
              :data-testid="testIds.viewerFrameSlider"
              @input="onFrameInput"
              @change="onFrameChange"
            />
            <button
              type="button"
              class="vw-frame-btn"
              :disabled="currentFrame >= viewerFrameCount - 1"
              @click="nextFrame"
            >
              &#9654;
            </button>
          </div>
          <span class="vw-frame-info">{{ currentFrame + 1 }} / {{ viewerFrameCount }}</span>
        </div>

        <!-- Display settings / 显示设置 -->
        <div class="vw-card">
          <h3 class="vw-card-title">{{ t('viewer.displaySettings') }}</h3>

          <!-- Colormap / 色图 -->
          <div class="vw-field">
            <label class="vw-label">{{ t('viewer.colormap') }}</label>
            <select
              v-model="colormap"
              class="vw-select"
              :data-testid="testIds.viewerColormapSelect"
            >
              <option v-for="cm in colormapOptions" :key="cm" :value="cm">{{ cm }}</option>
            </select>
          </div>

          <!-- Log / Linear toggle / 对数/线性切换 -->
          <label class="vw-toggle" :data-testid="testIds.viewerLogToggle">
            <input v-model="useLog" type="checkbox" />
            <span>{{ t('viewer.logScale') }}</span>
          </label>

          <!-- Preview quality / 预览画质 -->
          <div class="vw-field">
            <label class="vw-label">{{ t('viewer.previewQuality') }}</label>
            <div class="vw-radio-row">
              <label class="vw-radio">
                <input v-model="previewMode" type="radio" value="rough" />
                <span>{{ t('viewer.previewFast') }}</span>
              </label>
              <label class="vw-radio">
                <input v-model="previewMode" type="radio" value="full" />
                <span>{{ t('viewer.previewFull') }}</span>
              </label>
            </div>
            <p class="vw-hint">低质量预览切图更快；导出时再用高 DPI 保证清晰度。</p>
          </div>

          <!-- Contrast controls / 对比度控制 -->
          <div class="vw-contrast-section">
            <div class="vw-contrast-header">
              <label class="vw-label">{{ t('viewer.climMode') }}</label>
              <div class="vw-radio-row">
                <label class="vw-radio">
                  <input v-model="climMode" type="radio" value="auto" />
                  <span>{{ t('viewer.climAuto') }}</span>
                </label>
                <label class="vw-radio">
                  <input v-model="climMode" type="radio" value="manual" />
                  <span>{{ t('viewer.climManual') }}</span>
                </label>
              </div>
            </div>

            <!-- Manual contrast: slider + number bidirectional sync / 手动对比度：滑块与数字双向同步 -->
            <div v-if="climMode === 'manual'" class="vw-contrast-sliders">
              <div class="vw-clim-field">
                <label class="vw-label-sm">{{ t('viewer.climMin') }}</label>
                <input
                  type="range"
                  class="vw-slider vw-slider--contrast"
                  :min="climSliderMin"
                  :max="climSliderMax"
                  :step="climStep"
                  :value="climMin"
                  :data-testid="testIds.viewerClimMin"
                  @input="updateClimMin(Number(($event.target as HTMLInputElement).value))"
                />
                <input
                  :value="climMin"
                  type="number"
                  class="vw-input vw-input--sm"
                  step="any"
                  @input="updateClimMin(Number(($event.target as HTMLInputElement).value))"
                />
              </div>
              <div class="vw-clim-field">
                <label class="vw-label-sm">{{ t('viewer.climMax') }}</label>
                <input
                  type="range"
                  class="vw-slider vw-slider--contrast"
                  :min="climSliderMin"
                  :max="climSliderMax"
                  :step="climStep"
                  :value="climMax"
                  :data-testid="testIds.viewerClimMax"
                  @input="updateClimMax(Number(($event.target as HTMLInputElement).value))"
                />
                <input
                  :value="climMax"
                  type="number"
                  class="vw-input vw-input--sm"
                  step="any"
                  @input="updateClimMax(Number(($event.target as HTMLInputElement).value))"
                />
              </div>
            </div>
          </div>

          <!-- Show colorbar / 显示色条 -->
          <label class="vw-toggle">
            <input v-model="showColorbar" type="checkbox" />
            <span>{{ t('viewer.showColorbar') }}</span>
          </label>
        </div>

        <!-- PNG Export / PNG 导出 -->
        <div class="vw-card">
          <h3 class="vw-card-title">{{ t('viewer.pngExport') }}</h3>

          <div class="vw-field">
            <label class="vw-label">{{ t('viewer.pngExportMode') }}</label>
            <select v-model="pngExportMode" class="vw-select">
              <option value="single">{{ t('viewer.exportSingle') }}</option>
              <option value="batch">{{ t('viewer.exportBatch') }}</option>
            </select>
          </div>

          <!-- Export DPI / 导出 DPI -->
          <div class="vw-field">
            <label class="vw-label">{{ t('viewer.dpi') }}: {{ dpi }}</label>
            <input
              v-model.number="dpi"
              type="range"
              class="vw-slider"
              min="72"
              max="600"
              step="1"
              :data-testid="testIds.viewerDpiSlider"
            />
            <p class="vw-hint">预览画质只影响当前查看速度；这里的 DPI 只用于导出 PNG。</p>
          </div>

          <button
            v-if="pngExportMode === 'single'"
            type="button"
            class="vw-export-btn"
            :disabled="!fullImageB64 || pngExporting"
            @click="handleExportSinglePng"
          >
            {{ pngExporting ? t('viewer.exporting') : t('viewer.exportSingle') }}
          </button>

          <template v-if="pngExportMode === 'batch'">
            <FileDialogButton
              mode="openFolder"
              :label="t('viewer.batchOutputFolder')"
              :model-value="pngBatchOutputFolder"
              @update:model-value="pngBatchOutputFolder = $event"
            />
            <button
              type="button"
              class="vw-export-btn"
              :disabled="!pngBatchOutputFolder || selectedFiles.length === 0 || pngExporting"
              @click="handleExportBatchPng"
            >
              {{ pngExporting ? t('viewer.exporting') : t('viewer.exportBatch') }}
            </button>
            <div v-if="pngExporting" class="vw-export-progress">
              <div class="vw-export-progress-bar">
                <div class="vw-export-progress-fill" :style="{ width: `${(pngExportProgress / pngExportTotal) * 100}%` }" />
              </div>
              <span class="vw-export-progress-text">{{ pngExportProgress }} / {{ pngExportTotal }}</span>
            </div>
          </template>
        </div>
      </aside>

      <!-- Main area: image display + stats / 主区域 -->
      <main class="vw-main">
        <!-- Empty state / 空状态 -->
        <div v-if="!hasDisplayImage && state === 'idle'" class="vw-empty">
          <p>{{ t('viewer.emptyState') }}</p>
        </div>

        <!-- Loading / 加载中 -->
        <div v-if="state === 'running'" class="vw-loading">
          <TaskProgressBar
            :task-id="taskId ?? ''"
            :progress="progress"
            :message="progressMessage"
            @cancel="handleCancel"
          />
        </div>

        <!-- Error / 错误 -->
        <div v-if="state === 'error'" class="vw-error" :data-testid="testIds.viewerError">
          <p>{{ t('viewer.errorPrefix') }} {{ errorMessage }}</p>
        </div>

        <!-- Main display area / 主显示区域 -->
        <div v-if="hasDisplayImage" class="vw-display" :data-testid="testIds.viewerDisplay">

          <!-- Full-resolution image + stats / 全分辨率图像 + 统计 -->
          <div class="vw-image-section">
            <div class="vw-image-main" :data-testid="testIds.viewerFullImage">
              <ImagePreview
                :image-b64="previewB64 || fullImageB64"
                :title="imageTitle"
                :placeholder="t('viewer.loadingImage')"
                :show-colorbar="showColorbar"
                :colorbar-gradient="colorbarGradient"
                :colorbar-min-label="colorbarMinLabel"
                :colorbar-max-label="colorbarMaxLabel"
              />
              <div v-if="isLoadingFullRes && previewB64" class="vw-fullres-loading">
                <span>{{ t('viewer.loadingFullRes') }}</span>
              </div>
            </div>

            <!-- Statistics panel / 统计面板 -->
            <div v-if="frameStats" class="vw-stats" :data-testid="testIds.viewerStats">
              <h4 class="vw-stats-title">{{ t('viewer.statsTitle') }}</h4>
              <dl class="vw-stats-list">
                <div class="vw-stat-item">
                  <dt>{{ t('viewer.statMin') }}</dt>
                  <dd>{{ formatSci(frameStats.min) }}</dd>
                </div>
                <div class="vw-stat-item">
                  <dt>{{ t('viewer.statMax') }}</dt>
                  <dd>{{ formatSci(frameStats.max) }}</dd>
                </div>
                <div class="vw-stat-item">
                  <dt>{{ t('viewer.statAdjMax') }}</dt>
                  <dd>{{ formatSci(frameStats.adjustedMax) }}</dd>
                </div>
                <div class="vw-stat-item">
                  <dt>{{ t('viewer.statStd') }}</dt>
                  <dd>{{ formatSci(frameStats.std) }}</dd>
                </div>
              </dl>
              <div class="vw-meta-info">
                <div v-if="selectedDataset" class="vw-meta-item">
                  <span class="vw-meta-label">Dataset:</span>
                  <span class="vw-meta-value">{{ selectedDataset }}</span>
                </div>
                <div v-if="channelCount > 1" class="vw-meta-item">
                  <span class="vw-meta-label">Channel:</span>
                  <span class="vw-meta-value">Ch{{ selectedChannel }}</span>
                </div>
              </div>
            </div>
          </div>

          <!-- Frame navigator bar / 帧导航条 -->
          <div v-if="viewerFrameCount > 1" class="vw-frame-nav" :data-testid="testIds.viewerFrameNav">
            <button
              type="button"
              class="vw-frame-btn"
              :disabled="currentFrame <= 0"
              @click="prevFrame"
            >
              &#9664;
            </button>
            <input
              type="range"
              class="vw-slider vw-slider--frame"
              min="0"
              :max="viewerFrameCount - 1"
              :value="currentFrame"
              @input="onFrameInput"
              @change="onFrameChange"
            />
            <button
              type="button"
              class="vw-frame-btn"
              :disabled="currentFrame >= viewerFrameCount - 1"
              @click="nextFrame"
            >
              &#9654;
            </button>
            <span class="vw-frame-info">{{ currentFrame + 1 }} / {{ viewerFrameCount }}</span>
          </div>

          <div
            v-if="viewerFrameCount > 1 && (thumbnailItems.length || isLoadingThumbnails)"
            class="vw-thumb-strip"
            :data-testid="testIds.viewerThumbnailStrip"
          >
            <ThumbnailStrip
              v-if="thumbnailItems.length || isLoadingThumbnails"
              :items="thumbnailItems"
              :selected-index="currentFrame"
              :current-page="thumbCurrentPage"
              :total-pages="thumbTotalPages"
              :page-size="thumbPageSize"
              :loading="isLoadingThumbnails"
              :sync-with-main="thumbSyncWithMain"
              :columns-per-row="thumbColsPerRow"
              @select="navigateToFrame"
              @prev-page="handleThumbPrevPage"
              @next-page="handleThumbNextPage"
              @jump-to-page="handleThumbJumpToPage"
              @page-size-change="handleThumbPageSizeChange"
              @update:sync-with-main="onSyncToggle"
              @update:columns-per-row="thumbColsPerRow = $event"
            />
          </div>
        </div>
      </main>
    </div>
  </section>
</template>

<script setup lang="ts">
/**
 * ViewerView.vue — EDF / TIFF / HDF5 图像查看器页面
 * EDF / TIFF / HDF5 Image Viewer Page
 *
 * Fast probe (metadata) + single-frame load flow.
 */
import { ref, computed, onUnmounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useToast } from '@/lib/toast'
import { useTransport } from '@/lib/transport'
import { testIds } from '@/lib/testIds'
import { COLORMAP_PRESETS, resolveColorbarGradient } from '@/lib/chart-utils'

import FileDialogButton from '@/components/business/FileDialogButton.vue'
import TaskProgressBar from '@/components/business/TaskProgressBar.vue'
import ThumbnailStrip from '@/components/business/ThumbnailStrip.vue'
import type { ThumbnailItem } from '@/components/business/ThumbnailStrip.vue'
import ImagePreview from '@/components/charts/ImagePreview.vue'

// === Types / 类型定义 ===

interface H5DatasetInfo {
  path: string
  ndim: number
  shape: number[]
  nFrames?: number
  nChannels?: number
}

interface ViewerLoadResult {
  imageData: (number | null)[][] | null
  fullImageB64?: string
  previewB64?: string
  metadata: {
    totalFrames: number
    height: number
    width: number
    fileType: string
    h5Datasets?: H5DatasetInfo[]
    nChannels?: number
    selectedDataset?: string
    selectedChannel?: number
    frameIndex?: number
  }
  stats?: { min: number; max: number; adjustedMax: number; std: number }
  contrast?: { autoMin: number; autoMax: number; logMin: number; logMax: number }
  thumbnails?: ThumbnailItem[]
  nextStart?: number | null
  chunkSize?: number
}

type PageState = 'idle' | 'running' | 'done' | 'error'
type ViewerTaskParams = Record<string, unknown>
type ViewerSubmitResponse = { taskId: string }
type ViewerTaskSubmitInterceptor = (context: {
  route: string
  params: ViewerTaskParams
  submit: (route: string, params: ViewerTaskParams) => Promise<ViewerSubmitResponse>
}) => Promise<ViewerSubmitResponse | undefined> | ViewerSubmitResponse | undefined

// === Composables / 组合函数 ===

const { t } = useI18n()
const toast = useToast()
const transport = useTransport()

// === Colormap options / 色图选项 ===

const colormapOptions = [
  'smooth_WAXS_foxtrot',
  'smooth_WAXS_fit2D',
  ...Object.keys(COLORMAP_PRESETS).filter(k => k !== 'foxtrot' && k !== 'fit2d'),
] as string[]

// === File state / 文件状态 ===

const filePath = ref<string | null>(null)
const selectedFiles = ref<string[]>([])
const currentFileIndex = ref(0)
const importFolder = ref<string | null>(null)
const importRecursive = ref(false)
type ImportMode = 'replace' | 'append'
const importMode = ref<ImportMode>('replace')

const fileFilters = [
  { name: 'X-ray Images', extensions: ['edf', 'tif', 'tiff', 'h5', 'hdf5'] },
]

const fileName = computed(() => {
  if (!filePath.value) return ''
  const sep = filePath.value.includes('/') ? '/' : '\\'
  const parts = filePath.value.split(sep)
  return parts[parts.length - 1] || filePath.value
})

const importFolderDisplay = computed(() => {
  if (!importFolder.value) return ''
  if (/^[A-Za-z]:[\\/]/.test(importFolder.value) || importFolder.value.startsWith('\\\\')) {
    return importFolder.value.replace(/\//g, '\\')
  }
  return importFolder.value
})

// === H5 metadata / H5 元数据 ===

const h5Datasets = ref<H5DatasetInfo[]>([])
const selectedDataset = ref<string>('')
const channelCount = ref(0)
const selectedChannel = ref(0)

// === Frame state / 帧状态 ===

const totalFrames = ref(1)
const currentFrame = ref(0)
const thumbnailItems = ref<ThumbnailItem[]>([])
const isLoadingThumbnails = ref(false)
const nextThumbnailStart = ref<number | null>(null)
let thumbnailRequestSerial = 0
let thumbnailPageRequestSerial = 0
let importScanRequestSerial = 0

// Pagination state / 分页状态
const thumbCurrentPage = ref(1)
const thumbPageSize = ref(20)
const thumbSyncWithMain = ref(false)
const thumbColsPerRow = ref(5)

const thumbTotalPages = computed(() =>
  Math.max(1, Math.ceil(viewerFrameCount.value / thumbPageSize.value))
)

// === Display settings / 显示设置 ===

const colormap = ref<string>('smooth_WAXS_foxtrot')
const useLog = ref(false)
const climMode = ref<'auto' | 'manual'>('manual')
const climMin = ref<number>(0)
const climMax = ref<number>(1)
const showColorbar = ref(false)
const dpi = ref(150)
const previewMode = ref<'rough' | 'full'>('rough')

// === Frame cache / 帧缓存 ===

const fullImageB64 = ref<string | null>(null)
const previewB64 = ref<string | null>(null)
const isLoadingFullRes = ref(false)
const frameStats = ref<{ min: number; max: number; adjustedMax: number; std: number } | null>(null)
const autoContrast = ref<{ autoMin: number; autoMax: number; logMin: number; logMax: number } | null>(null)
const climInitialized = ref(false)
const pendingRerender = ref(false)

// === Task execution state / 任务执行状态 ===

const state = ref<PageState>('idle')
const taskId = ref<string | null>(null)
const progress = ref(0)
const progressMessage = ref<string | null>(null)
const errorMessage = ref('')

let cleanupProgress: (() => void) | null = null
let cleanupResult: (() => void) | null = null
let cleanupError: (() => void) | null = null
let cleanupBinary: (() => void) | null = null

// === Computed / 计算属性 ===

const isBatchMode = computed(() => selectedFiles.value.length > 1)
const viewerFrameCount = computed(() => (isBatchMode.value ? selectedFiles.value.length : totalFrames.value))

const imageTitle = computed(() => {
  if (!fileName.value) return ''
  const parts = [fileName.value]
  if (viewerFrameCount.value > 1) {
    parts.push(`Frame ${currentFrame.value + 1}/${viewerFrameCount.value}`)
  }
  if (channelCount.value > 1) {
    parts.push(`Ch${selectedChannel.value}`)
  }
  return parts.join(' · ')
})

const hasDisplayImage = computed(() => Boolean(previewB64.value || fullImageB64.value))
const colorbarGradient = computed(() => resolveColorbarGradient(colormap.value))
const colorbarMinLabel = computed(() => formatSci(climMode.value === 'manual' ? climMin.value : (useLog.value ? autoContrast.value?.logMin ?? 0 : autoContrast.value?.autoMin ?? 0)))
const colorbarMaxLabel = computed(() => formatSci(climMode.value === 'manual' ? climMax.value : (useLog.value ? autoContrast.value?.logMax ?? 1 : autoContrast.value?.autoMax ?? 1)))
// 滑块范围放宽到 auto 范围的 0.5×~2×，允许超限渲染 / Slider range widened to 0.5×~2× auto range for over-limit rendering
const climSliderMin = computed(() => {
  const auto = (useLog.value ? autoContrast.value?.logMin : autoContrast.value?.autoMin) ?? 0
  return auto <= 0 ? auto * 2 : auto * 0.1
})
const climSliderMax = computed(() => {
  const auto = (useLog.value ? autoContrast.value?.logMax : autoContrast.value?.autoMax) ?? (frameStats.value?.adjustedMax ?? 1)
  return auto * 3
})
const climStep = computed(() => {
  const range = climSliderMax.value - climSliderMin.value
  return range === 0 ? 1 : range / 1000
})

// === Helpers / 辅助函数 ===

function isBinaryPlaceholder(value: string | null | undefined): boolean {
  return value === '__binary_blob__'
}

function hasRenderableFullImage(result?: Pick<ViewerLoadResult, 'fullImageB64'> | null): boolean {
  if (fullImageB64.value) return true
  return Boolean(result?.fullImageB64 && !isBinaryPlaceholder(result.fullImageB64))
}

function applyFrameResult(result: ViewerLoadResult): void {
  if (!fullImageB64.value?.startsWith('blob:') && result.fullImageB64 && !isBinaryPlaceholder(result.fullImageB64)) {
    fullImageB64.value = result.fullImageB64
  }

  if (result.metadata) {
    if (Array.isArray(result.metadata.h5Datasets)) {
      h5Datasets.value = result.metadata.h5Datasets
    }
    if (typeof result.metadata.selectedDataset === 'string' && result.metadata.selectedDataset) {
      selectedDataset.value = result.metadata.selectedDataset
    }
    if (typeof result.metadata.selectedChannel === 'number') {
      selectedChannel.value = result.metadata.selectedChannel
    }
    if (typeof result.metadata.nChannels === 'number') {
      channelCount.value = result.metadata.nChannels
    }
    if (!isBatchMode.value) {
      totalFrames.value = result.metadata.totalFrames || 1
      currentFrame.value = result.metadata.frameIndex ?? currentFrame.value
    }
  }

  frameStats.value = result.stats || null
  if (result.contrast) {
    autoContrast.value = result.contrast
    if (climMode.value === 'auto') {
      climMin.value = result.contrast.autoMin
      climMax.value = result.contrast.autoMax
    } else if (!climInitialized.value) {
      // 仅首次加载时从 auto contrast 初始化手动值 / Init manual clim from auto values only on first load
      climMin.value = useLog.value ? result.contrast.logMin : result.contrast.autoMin
      climMax.value = useLog.value ? result.contrast.logMax : result.contrast.autoMax
      climInitialized.value = true
    }
  }
}

function applyThumbnailItems(items: unknown[], replace = true): void {
  const normalized = items
    .filter((item: unknown) => {
      const candidate = item as { index?: unknown; b64?: unknown }
      return typeof candidate.index === 'number' && typeof candidate.b64 === 'string'
    })
    .map((item: unknown) => {
      const candidate = item as ThumbnailItem
      return {
        index: candidate.index,
        b64: candidate.b64,
        label: candidate.label,
        stats: candidate.stats,
      }
    })

  thumbnailItems.value = replace ? normalized : [...thumbnailItems.value, ...normalized]
}

function resetThumbnailStripState(): void {
  thumbnailRequestSerial += 1
  thumbnailItems.value = []
  isLoadingThumbnails.value = false
  nextThumbnailStart.value = null
  thumbCurrentPage.value = 1
}

async function buildFilePreviewItems(paths: string[], start: number, count: number): Promise<ThumbnailItem[]> {
  const slice = paths.slice(start, start + count)
  const items: ThumbnailItem[] = []

  for (let index = 0; index < slice.length; index += 1) {
    const path = slice[index]
    const normalizedIndex = start + index
    const sep = path.includes('/') ? '/' : '\\'
    const parts = path.split(sep)
    const label = parts[parts.length - 1] || path

    const params: Record<string, unknown> = {
      action: 'preview',
      filePath: path,
    }
    if (thumbSyncWithMain.value) {
      params.thumb_render_settings = buildThumbRenderSettings()
    }

    const result = await submitAndWait('viewer_config', params)
    items.push({
      index: normalizedIndex,
      b64: typeof result?.previewB64 === 'string' ? result.previewB64 : '',
      label,
    })
  }

  return items
}

function buildThumbRenderSettings(): Record<string, unknown> {
  const resolvedClim = climMode.value === 'manual'
    ? [climMin.value, climMax.value]
    : [
        useLog.value ? autoContrast.value?.logMin ?? 1e-6 : autoContrast.value?.autoMin ?? 0,
        useLog.value ? autoContrast.value?.logMax ?? 1 : autoContrast.value?.autoMax ?? 1,
      ]

  return {
    cmap: colormap.value,
    use_log: useLog.value,
    clim: resolvedClim,
  }
}

async function queueThumbnailLoad(options: {
  filePath: string | null
  dataset?: string
  channel?: number
  totalFrames: number
  startAt?: number | null
  replace?: boolean
}): Promise<void> {
  const path = options.filePath
  if (!path || options.totalFrames <= 1) {
    return
  }

  const requestSerial = ++thumbnailRequestSerial
  isLoadingThumbnails.value = true

  try {
    const start = Math.max(0, Number(options.startAt ?? 0))
    const params: Record<string, unknown> = {
      action: 'load_thumbnails_chunk',
      filePath: path,
      dataset: options.dataset,
      channel: options.channel,
      start,
      count: thumbPageSize.value,
    }
    if (thumbSyncWithMain.value) {
      params.thumb_render_settings = buildThumbRenderSettings()
    }

    const result = await submitAndWait('viewer_config', params)

    if (requestSerial !== thumbnailRequestSerial) {
      return
    }

    const nextItems = Array.isArray(result?.thumbnails) ? result.thumbnails : []
    if (nextItems.length) {
      applyThumbnailItems(nextItems, options.replace ?? start === 0)
    }
    nextThumbnailStart.value = typeof result?.nextStart === 'number' ? result.nextStart : null
  } catch {
    if (requestSerial === thumbnailRequestSerial && (options.replace ?? false)) {
      thumbnailItems.value = []
    }
  } finally {
    if (requestSerial === thumbnailRequestSerial) {
      isLoadingThumbnails.value = false
    }
  }
}

function buildViewerRenderSettings(): Record<string, unknown> {
  const resolvedClim = climMode.value === 'manual'
    ? [climMin.value, climMax.value]
    : [
        useLog.value ? autoContrast.value?.logMin ?? 1e-6 : autoContrast.value?.autoMin ?? 0,
        useLog.value ? autoContrast.value?.logMax ?? 1 : autoContrast.value?.autoMax ?? 1,
      ]

  return {
    colormap: colormap.value,
    use_log: useLog.value,
    clim_mode: climMode.value,
    clim: resolvedClim,
    preview_scale: previewMode.value === 'rough' ? 0.25 : 1.0,
  }
}

let rerenderTimer: ReturnType<typeof setTimeout> | null = null

function scheduleViewerRerender(): void {
  if (!filePath.value || !hasDisplayImage.value) return
  if (isLoadingFullRes.value) {
    // 加载进行中，标记 pending，等当前加载完成后重试 / Mark pending — retry when current load completes
    pendingRerender.value = true
    return
  }
  pendingRerender.value = false
  if (rerenderTimer) clearTimeout(rerenderTimer)
  rerenderTimer = setTimeout(() => {
    rerenderTimer = null
    const frameIdx = isBatchMode.value ? 0 : currentFrame.value
    void loadFrame(frameIdx)
  }, 120)
}

function triggerPendingRerenderIfNeeded(): void {
  if (pendingRerender.value) {
    pendingRerender.value = false
    scheduleViewerRerender()
  }
}

function handleLoadMoreThumbnails(): void {
  // Kept for backward compat — now handled by page-based loading
}

function getThumbnailPageForIndex(index: number): number {
  return Math.max(1, Math.floor(index / thumbPageSize.value) + 1)
}

function ensureThumbnailPageForIndex(index: number): void {
  const targetPage = getThumbnailPageForIndex(index)
  if (targetPage === thumbCurrentPage.value) return
  thumbCurrentPage.value = targetPage
  if (viewerFrameCount.value > 1) {
    void loadThumbnailPage(targetPage)
  }
}

async function loadThumbnailPage(page: number): Promise<void> {
  const start = (page - 1) * thumbPageSize.value
  const count = thumbPageSize.value

  if (isBatchMode.value) {
    const requestSerial = ++thumbnailPageRequestSerial
    isLoadingThumbnails.value = true
    try {
      const items = await buildFilePreviewItems(selectedFiles.value, start, count)
      if (requestSerial !== thumbnailPageRequestSerial) return
      thumbnailItems.value = items
      nextThumbnailStart.value = start + items.length >= selectedFiles.value.length ? null : start + items.length
    } catch {
      if (requestSerial !== thumbnailPageRequestSerial) return
      thumbnailItems.value = []
      nextThumbnailStart.value = null
    } finally {
      if (requestSerial === thumbnailPageRequestSerial) {
        isLoadingThumbnails.value = false
      }
    }
    return
  }

  await queueThumbnailLoad({
    filePath: filePath.value,
    dataset: selectedDataset.value || undefined,
    channel: channelCount.value > 1 ? selectedChannel.value : undefined,
    totalFrames: totalFrames.value,
    startAt: start,
    replace: true,
  })
}

function handleThumbPrevPage(): void {
  if (thumbCurrentPage.value <= 1) return
  thumbCurrentPage.value -= 1
  void loadThumbnailPage(thumbCurrentPage.value)
}

function handleThumbNextPage(): void {
  if (thumbCurrentPage.value >= thumbTotalPages.value) return
  thumbCurrentPage.value += 1
  void loadThumbnailPage(thumbCurrentPage.value)
}

function handleThumbJumpToPage(page: number): void {
  const clamped = Math.max(1, Math.min(thumbTotalPages.value, page))
  if (clamped === thumbCurrentPage.value) return
  thumbCurrentPage.value = clamped
  void loadThumbnailPage(clamped)
}

function handleThumbPageSizeChange(size: number): void {
  thumbPageSize.value = size
  thumbCurrentPage.value = 1
  if (viewerFrameCount.value > 1) {
    void loadThumbnailPage(1)
  }
}

function onSyncToggle(value: boolean): void {
  thumbSyncWithMain.value = value
  if (value && viewerFrameCount.value > 1) {
    void loadThumbnailPage(thumbCurrentPage.value)
  }
}

async function handleChooseFiles(): Promise<void> {
  const result = await transport.selectFiles({ filters: fileFilters, multiSelections: true })
  if (!result) return
  importFolder.value = null
  importRecursive.value = false
  const paths = Array.isArray(result) ? result : [result]
  if (importMode.value === 'append') {
    const existingSet = new Set(selectedFiles.value)
    const newFiles = paths.filter(p => !existingSet.has(p))
    await handleFileBatchSelected([...selectedFiles.value, ...newFiles])
  } else {
    await handleFileBatchSelected(paths)
  }
}

async function handleImportFolder(): Promise<void> {
  const folder = await transport.selectFolder()
  if (!folder) return
  importFolder.value = folder
  await rescanImportFolder()
}

async function rescanImportFolder(): Promise<void> {
  if (!importFolder.value) return
  const requestSerial = ++importScanRequestSerial
  try {
    const scanResult = await submitAndWait('viewer_config', {
      action: 'scan_folder',
      folder: importFolder.value,
      recursive: importRecursive.value,
    })
    if (requestSerial !== importScanRequestSerial) return
    const files = Array.isArray(scanResult?.files) ? scanResult.files.filter(Boolean) : []
    if (files.length === 0) {
      if (importMode.value !== 'append') {
        await handleFileBatchSelected([])
      }
      toast.push({ title: t('viewer.selectFolder'), message: t('viewer.noFilesInFolder'), tone: 'info' })
      return
    }
    if (importMode.value === 'append') {
      const existingSet = new Set(selectedFiles.value)
      const newFiles = files.filter(p => !existingSet.has(p))
      await handleFileBatchSelected([...selectedFiles.value, ...newFiles])
    } else {
      await handleFileBatchSelected(files)
    }
  } catch (err) {
    toast.push({
      title: t('viewer.errorTitle'),
      message: err instanceof Error ? err.message : String(err),
      tone: 'error',
    })
  }
}

async function handleFileBatchSelected(paths: string[] | null): Promise<void> {
  const normalized = Array.isArray(paths) ? paths.filter(Boolean) : []
  selectedFiles.value = normalized
  currentFileIndex.value = 0
  if (normalized.length === 0) {
    filePath.value = null
    resetThumbnailStripState()
    return
  }

  if (normalized.length > 1) {
    totalFrames.value = normalized.length
    currentFrame.value = 0
    thumbCurrentPage.value = 1
  }

  await handleFileSelected(normalized[0], false)

  if (normalized.length > 1) {
    void loadThumbnailPage(1)
  }
}

function getViewerTaskInterceptor(): ViewerTaskSubmitInterceptor | undefined {
  return (window as typeof window & {
    __viewerTestHooks__?: {
      interceptTaskSubmit?: ViewerTaskSubmitInterceptor
    }
  }).__viewerTestHooks__?.interceptTaskSubmit
}

function submitViewerLoadTask(params: ViewerTaskParams): Promise<ViewerSubmitResponse> {
  const submit = (route: string, nextParams: ViewerTaskParams) => transport.submitTask(route, nextParams)
  const interceptor = getViewerTaskInterceptor()
  if (!interceptor) {
    return submit('viewer_config', params)
  }

  return Promise.resolve(
    interceptor({ route: 'viewer_config', params, submit })
  ).then(intercepted => intercepted ?? submit('viewer_config', params))
}

function formatSci(value: number): string {
  if (!Number.isFinite(value)) return '—'
  if (value === 0) return '0'
  return value.toExponential(3)
}

function clampContrastValues(): void {
  // 仅保证 climMin ≤ climMax，不钳制到 auto 范围 / Only ensure climMin ≤ climMax, no clamping to auto range
  if (climMode.value !== 'manual') return
  if (climMin.value > climMax.value) {
    const mid = (climMin.value + climMax.value) / 2
    climMin.value = mid
    climMax.value = mid
  }
}

function updateClimMin(value: number): void {
  if (!Number.isFinite(value)) return
  climMin.value = value
  if (climMin.value > climMax.value) {
    climMax.value = climMin.value
  }
  clampContrastValues()
}

function updateClimMax(value: number): void {
  if (!Number.isFinite(value)) return
  climMax.value = value
  if (climMax.value < climMin.value) {
    climMin.value = climMax.value
  }
  clampContrastValues()
}

// === Task helpers / 任务辅助 ===

function submitAndWait(route: string, params: Record<string, unknown>): Promise<any> {
  return new Promise((resolve, reject) => {
    transport.submitTask(route, params).then(response => {
      transport.onTaskResult(response.taskId, (p) => resolve(p.data))
      transport.onTaskError(response.taskId, (p) => reject(new Error(p.error)))
    }).catch(reject)
  })
}

// === File handling / 文件处理 ===

async function handleFileSelected(path: string | null, resetBatch = true): Promise<void> {
  if (resetBatch) {
    selectedFiles.value = path ? [path] : []
    currentFileIndex.value = 0
  }
  filePath.value = path
  h5Datasets.value = []
  selectedDataset.value = ''
  channelCount.value = 0
  selectedChannel.value = 0
  totalFrames.value = 1
  currentFrame.value = 0
  fullImageB64.value = null
  previewB64.value = null
  frameStats.value = null
  autoContrast.value = null
  isLoadingFullRes.value = false
  pendingRerender.value = false

  if (resetBatch) {
    resetThumbnailStripState()
  }

  if (!resetBatch && selectedFiles.value.length > 1) {
    totalFrames.value = selectedFiles.value.length
    currentFrame.value = currentFileIndex.value
  }

  if (!path) return

  state.value = 'running'
  errorMessage.value = ''
  cleanupListeners()

  try {
    isLoadingFullRes.value = true
    await new Promise<void>((resolve, reject) => {
      submitViewerLoadTask({
        action: 'open_file',
        filePath: path,
        frame: 0,
        includeImageData: false,
        settings: buildViewerRenderSettings(),
      }).then(response => {
        taskId.value = response.taskId

        cleanupProgress = transport.onTaskProgress(response.taskId, (p) => {
          progress.value = p.progress
          progressMessage.value = p.message ?? null
        })

        cleanupBinary = transport.onTaskBinaryData(response.taskId, (payload) => {
          if (payload.data) {
            const blob = new Blob([payload.data], { type: payload.mime || 'image/png' })
            const url = URL.createObjectURL(blob)
            if (fullImageB64.value && fullImageB64.value.startsWith('blob:')) {
              URL.revokeObjectURL(fullImageB64.value)
            }
            fullImageB64.value = url
            previewB64.value = null
          }
        })

        cleanupResult = transport.onTaskResult(response.taskId, (p) => {
          const result = p.data as ViewerLoadResult
          applyFrameResult(result)
          totalFrames.value = selectedFiles.value.length > 1 ? selectedFiles.value.length : (result.metadata?.totalFrames || totalFrames.value || 1)
          currentFrame.value = selectedFiles.value.length > 1 ? currentFileIndex.value : (result.metadata?.frameIndex ?? 0)
          if (selectedFiles.value.length === 1) {
            nextThumbnailStart.value = typeof result.nextStart === 'number' ? result.nextStart : null
          }
          if (selectedFiles.value.length === 1 && nextThumbnailStart.value !== null) {
            thumbCurrentPage.value = 1
            void queueThumbnailLoad({
              filePath: path,
              dataset: result.metadata?.selectedDataset || selectedDataset.value || undefined,
              channel: (result.metadata?.nChannels || channelCount.value) > 1 ? (result.metadata?.selectedChannel ?? selectedChannel.value) : undefined,
              totalFrames: result.metadata?.totalFrames || totalFrames.value,
              startAt: 0,
              replace: true,
            })
          }
          state.value = 'done'
          progress.value = 1
          isLoadingFullRes.value = false
          triggerPendingRerenderIfNeeded()
          resolve()
        })

        cleanupError = transport.onTaskError(response.taskId, (p) => {
          isLoadingFullRes.value = false
          triggerPendingRerenderIfNeeded()
          state.value = 'error'
          errorMessage.value = p.error
          reject(new Error(p.error))
        })
      }).catch(reject)
    })
  } catch (err) {
    isLoadingFullRes.value = false
    errorMessage.value = err instanceof Error ? err.message : String(err)
    state.value = 'error'
    toast.push({ title: t('viewer.errorTitle'), message: errorMessage.value, tone: 'error' })
  }
}

// === Single frame loader / 单帧加载器 ===

async function loadFrame(frameIdx: number): Promise<void> {
  if (!filePath.value) return

  isLoadingFullRes.value = true
  progress.value = 0
  errorMessage.value = ''
  cleanupListeners()

  return new Promise<void>((resolve, reject) => {
    const params: ViewerTaskParams = {
      action: 'load',
      filePath: filePath.value,
      frame: frameIdx,
      frame_index: frameIdx,
      dataset: selectedDataset.value || undefined,
      channel: channelCount.value > 1 ? selectedChannel.value : undefined,
      includeImageData: false,
      settings: buildViewerRenderSettings(),
    }

    submitViewerLoadTask(params).then(response => {
      taskId.value = response.taskId

      cleanupProgress = transport.onTaskProgress(response.taskId, (p) => {
        progress.value = p.progress
        progressMessage.value = p.message ?? null
      })

      cleanupBinary = transport.onTaskBinaryData(response.taskId, (payload) => {
        if (payload.data) {
          const blob = new Blob([payload.data], { type: payload.mime || 'image/png' })
          const url = URL.createObjectURL(blob)
          if (fullImageB64.value && fullImageB64.value.startsWith('blob:')) {
            URL.revokeObjectURL(fullImageB64.value)
          }
          fullImageB64.value = url
          previewB64.value = null
          cleanupBinary?.()
          cleanupBinary = null
        }
      })

      cleanupResult = transport.onTaskResult(response.taskId, (p) => {
        const result = p.data as ViewerLoadResult
        const hasMatrixData = Array.isArray(result?.imageData)
        const hasFullImage = hasRenderableFullImage(result)

        if (hasMatrixData || hasFullImage) {
          applyFrameResult(result)

          // Full-res arrived — hide preview / 全分辨率到达时隐藏预览
          previewB64.value = null
          state.value = 'done'
          progress.value = 1
          isLoadingFullRes.value = false
          triggerPendingRerenderIfNeeded()
          resolve()
        } else {
          // Keep preview on partial failure / 部分失败时保留预览
          if (!previewB64.value) {
            isLoadingFullRes.value = false
            triggerPendingRerenderIfNeeded()
            state.value = 'error'
            errorMessage.value = 'No image data returned'
            reject(new Error(errorMessage.value))
          } else {
            state.value = 'done'
            resolve()
          }
        }
      })

      cleanupError = transport.onTaskError(response.taskId, (p) => {
        if (!previewB64.value) {
          isLoadingFullRes.value = false
          triggerPendingRerenderIfNeeded()
          state.value = 'error'
          errorMessage.value = p.error
          reject(new Error(p.error))
        } else {
          state.value = 'done'
          isLoadingFullRes.value = false
          triggerPendingRerenderIfNeeded()
          toast.push({ title: t('viewer.errorTitle'), message: p.error, tone: 'error' })
          resolve()
        }
      })
    }).catch((err) => {
      isLoadingFullRes.value = false
      triggerPendingRerenderIfNeeded()
      reject(err)
    })
  })
}

// === Frame navigation / 帧导航 ===

async function navigateToFrame(frameIdx: number): Promise<void> {
  ensureThumbnailPageForIndex(frameIdx)
  if (selectedFiles.value.length > 1) {
    if (frameIdx < 0 || frameIdx >= selectedFiles.value.length) return
    currentFileIndex.value = frameIdx
    await handleFileSelected(selectedFiles.value[frameIdx] ?? null, false)
    return
  }
  if (!filePath.value) return
  currentFrame.value = frameIdx

  try {
    isLoadingFullRes.value = true
    await loadFrame(frameIdx)
    isLoadingFullRes.value = false
  } catch (err) {
    isLoadingFullRes.value = false
    errorMessage.value = err instanceof Error ? err.message : String(err)
    state.value = 'error'
  }
}

function prevFrame(): void { if (currentFrame.value > 0) navigateToFrame(currentFrame.value - 1) }
function nextFrame(): void { if (currentFrame.value < viewerFrameCount.value - 1) navigateToFrame(currentFrame.value + 1) }

function onFrameInput(event: Event): void {
  const val = Number((event.target as HTMLInputElement).value)
  currentFrame.value = val
}

function onFrameChange(): void {
  navigateToFrame(currentFrame.value)
}

// === Dataset/Channel change / 数据集/通道切换 ===

function onDatasetChange(): void {
  const ds = h5Datasets.value.find(d => d.path === selectedDataset.value)
  if (ds) {
    totalFrames.value = ds.nFrames || 1
    channelCount.value = ds.nChannels || 0
    selectedChannel.value = 0
    currentFrame.value = 0
    frameStats.value = null
    resetThumbnailStripState()
    void navigateToFrame(0)
    void loadThumbnailPage(1)
  }
}

function onChannelChange(): void {
  currentFrame.value = 0
  frameStats.value = null
  resetThumbnailStripState()
  void navigateToFrame(0)
  void loadThumbnailPage(1)
}

// === PNG Export state / PNG 导出状态 ===

const pngExportMode = ref<'single' | 'batch'>('single')
const pngExporting = ref(false)
const pngBatchOutputFolder = ref<string | null>(null)
const pngExportProgress = ref(0)
const pngExportTotal = ref(0)

async function handleExportSinglePng(): Promise<void> {
  if (!filePath.value || pngExporting.value) return

  try {
    const savePath = await transport.selectSavePath({
      filters: [{ name: 'PNG', extensions: ['png'] }],
    })
    if (!savePath) return

    pngExporting.value = true
    const params: Record<string, unknown> = {
      action: 'png_export',
      filePath: filePath.value,
      frame: isBatchMode.value ? 0 : currentFrame.value,
      dataset: selectedDataset.value || undefined,
      channel: channelCount.value > 1 ? selectedChannel.value : undefined,
      settings: {
        colormap: colormap.value,
        use_log: useLog.value,
        clim_mode: climMode.value,
        clim: climMode.value === 'manual'
          ? [climMin.value, climMax.value]
          : [useLog.value ? autoContrast.value?.logMin ?? 1e-6 : autoContrast.value?.autoMin ?? 0,
             useLog.value ? autoContrast.value?.logMax ?? 1 : autoContrast.value?.autoMax ?? 1],
        show_colorbar: showColorbar.value,
        dpi: dpi.value,
      },
      output_path: savePath,
    }

    await new Promise<void>((resolve, reject) => {
      transport.submitTask('viewer_config', params).then(response => {
        taskId.value = response.taskId

        cleanupResult = transport.onTaskResult(response.taskId, () => {
          pngExporting.value = false
          toast.push({
            title: t('viewer.pngExport'),
            message: savePath,
            tone: 'success',
          })
          resolve()
        })

        cleanupError = transport.onTaskError(response.taskId, (payload) => {
          pngExporting.value = false
          toast.push({
            title: t('viewer.errorTitle'),
            message: payload.error,
            tone: 'error',
          })
          reject(new Error(payload.error))
        })
      }).catch(err => {
        pngExporting.value = false
        reject(err)
      })
    })
  } catch {
    pngExporting.value = false
  }
}

async function handleExportBatchPng(): Promise<void> {
  if (!pngBatchOutputFolder.value || selectedFiles.value.length === 0 || pngExporting.value) return

  pngExporting.value = true
  pngExportProgress.value = 0
  pngExportTotal.value = selectedFiles.value.length

  const files = selectedFiles.value.map(p => {
    const basename = p.replace(/^.*[\\/]/, '')
    const pngName = basename.replace(/\.[^.]+$/, '') + '.png'
    return { input: p, output: pngBatchOutputFolder.value!.replace(/[\\/]+$/, '') + '\\' + pngName }
  })

  const settings = {
    colormap: colormap.value,
    use_log: useLog.value,
    clim_mode: climMode.value,
    clim: climMode.value === 'manual'
      ? [climMin.value, climMax.value]
      : [useLog.value ? autoContrast.value?.logMin ?? 1e-6 : autoContrast.value?.autoMin ?? 0,
         useLog.value ? autoContrast.value?.logMax ?? 1 : autoContrast.value?.autoMax ?? 1],
    show_colorbar: showColorbar.value,
    dpi: dpi.value,
  }

  try {
    await new Promise<void>((resolve, reject) => {
      transport.submitTask('viewer_config', {
        action: 'batch_png_export',
        files,
        settings,
      }).then(response => {
        taskId.value = response.taskId

        cleanupProgress = transport.onTaskProgress(response.taskId, (p) => {
          pngExportProgress.value = Math.round(p.progress * pngExportTotal.value)
          progressMessage.value = p.message ?? null
        })

        cleanupResult = transport.onTaskResult(response.taskId, (p) => {
          const data = p.data as { generated?: number; errors?: string[] }
          pngExporting.value = false
          pngExportProgress.value = pngExportTotal.value
          cleanupListeners()
          const count = data.generated ?? pngExportTotal.value
          toast.push({
            title: t('viewer.pngExport'),
            message: `${count}/${pngExportTotal.value} files exported`,
            tone: 'success',
          })
          if (data.errors?.length) {
            toast.push({
              title: t('viewer.errorTitle'),
              message: `${data.errors.length} files failed`,
              tone: 'error',
            })
          }
          resolve()
        })

        cleanupError = transport.onTaskError(response.taskId, (payload) => {
          pngExporting.value = false
          cleanupListeners()
          toast.push({ title: t('viewer.errorTitle'), message: payload.error, tone: 'error' })
          reject(new Error(payload.error))
        })
      }).catch(err => {
        pngExporting.value = false
        reject(err)
      })
    })
  } catch {
    pngExporting.value = false
  }
}

// === Cancel / 取消 ===

function handleCancel(): void {
  state.value = 'idle'
  taskId.value = null
  progress.value = 0
  cleanupListeners()
}

// === Cleanup / 清理 ===

function cleanupListeners(): void {
  cleanupProgress?.()
  cleanupProgress = null
  cleanupResult?.()
  cleanupResult = null
  cleanupError?.()
  cleanupError = null
  cleanupBinary?.()
  cleanupBinary = null
}

watch([colormap, useLog, climMode, climMin, climMax, previewMode], () => {
  scheduleViewerRerender()
})

watch([colormap, useLog, climMode, climMin, climMax], () => {
  if (thumbSyncWithMain.value && viewerFrameCount.value > 1) {
    void loadThumbnailPage(thumbCurrentPage.value)
  }
})

watch([climMode, useLog, autoContrast], () => {
  clampContrastValues()
})

watch(importRecursive, () => {
  if (importFolder.value) {
    void rescanImportFolder()
  }
})

onUnmounted(() => {
  if (rerenderTimer) {
    clearTimeout(rerenderTimer)
    rerenderTimer = null
  }
  if (fullImageB64.value?.startsWith('blob:')) {
    URL.revokeObjectURL(fullImageB64.value)
  }
  cleanupListeners()
})
</script>

<style scoped>
.viewer-page {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.vw-header {
  padding-bottom: 8px;
}

.vw-header h1 {
  font-size: 1.5rem;
  font-weight: 700;
  margin: 0 0 6px;
  color: var(--text-primary);
}

.vw-subtitle {
  font-size: 0.9375rem;
  color: var(--text-secondary);
  margin: 0;
}

.vw-layout {
  display: grid;
  grid-template-columns: minmax(280px, 360px) minmax(0, 1fr);
  gap: 24px;
  align-items: start;
}

/* Sidebar / 侧边栏 */
.vw-sidebar {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.vw-card {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.vw-file-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* Import mode toggle / 导入模式切换 */
.vw-import-mode {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  border-radius: var(--radius-md);
  background: var(--bg-surface-alt);
  font-size: 0.8125rem;
}

.vw-import-mode-label {
  color: var(--text-secondary);
  font-weight: 500;
  white-space: nowrap;
}

.vw-radio-label {
  display: flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  color: var(--text-primary);
  white-space: nowrap;
}

.vw-radio-label input[type="radio"] {
  accent-color: var(--primary);
  width: 14px;
  height: 14px;
}

.vw-or-divider {
  text-align: center;
  color: var(--text-muted);
  font-size: 0.75rem;
  padding: 2px 0;
}

.vw-file-summary {
  font-size: 0.8125rem;
  color: var(--text-secondary);
  font-family: var(--font-mono);
}

.vw-file-summary--muted {
  color: var(--text-muted);
  font-style: italic;
}

.vw-card-title {
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.vw-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.vw-label {
  font-size: 0.8125rem;
  color: var(--text-secondary);
  font-weight: 500;
}

.vw-select {
  padding: 8px 10px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: 0.875rem;
  transition: border-color var(--transition-fast);
}

.vw-select:focus {
  outline: none;
  border-color: var(--border-focus);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}

.vw-input {
  padding: 8px 10px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: 0.875rem;
  font-family: var(--font-mono);
  transition: border-color var(--transition-fast);
}

.vw-input:focus {
  outline: none;
  border-color: var(--border-focus);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}

.vw-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.875rem;
  color: var(--text-primary);
  cursor: pointer;
  user-select: none;
}

.vw-toggle input[type="checkbox"] {
  accent-color: var(--primary);
  width: 16px;
  height: 16px;
}

.vw-radio-row {
  display: flex;
  gap: 16px;
}

.vw-radio {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.8125rem;
  color: var(--text-primary);
  cursor: pointer;
}

.vw-radio input[type="radio"] {
  accent-color: var(--primary);
}

.vw-clim-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.vw-contrast-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.vw-contrast-header {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.vw-contrast-sliders {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.vw-clim-field {
  display: flex;
  align-items: center;
  gap: 6px;
}

.vw-clim-field .vw-slider--contrast {
  flex: 1;
  min-width: 0;
}

.vw-input--sm {
  width: 72px;
  min-width: 72px;
  padding: 4px 6px;
  font-size: 0.75rem;
}

.vw-label-sm {
  font-size: 0.75rem;
  color: var(--text-muted);
  font-weight: 500;
  min-width: 28px;
  white-space: nowrap;
}

.vw-slider {
  width: 100%;
  accent-color: var(--primary);
}

.vw-slider--frame {
  flex: 1;
}

/* Frame navigation (sidebar) / 帧导航（侧边栏） */
.vw-frame-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.vw-frame-btn {
  padding: 4px 10px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: 0.75rem;
  cursor: pointer;
  transition: border-color var(--transition-fast);
}

.vw-frame-btn:hover:not(:disabled) {
  border-color: var(--border-hover);
}

.vw-frame-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.vw-frame-info {
  font-size: 0.8125rem;
  color: var(--text-secondary);
  text-align: center;
  font-family: var(--font-mono);
}

.vw-hint {
  font-size: 0.8125rem;
  color: var(--text-muted);
  margin: 0;
  line-height: 1.5;
}

.vw-export-btn {
  padding: 10px 24px;
  border-radius: var(--radius-md);
  border: none;
  background: var(--primary);
  color: var(--text-inverse);
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  transition: opacity var(--transition-fast);
}

.vw-export-btn--secondary {
  background: var(--bg-surface);
  color: var(--text-primary);
  border: 1px solid var(--border);
}

.vw-export-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.vw-export-btn:not(:disabled):hover {
  opacity: 0.9;
}

.vw-export-progress {
  margin-top: 6px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.vw-export-progress-bar {
  flex: 1;
  height: 6px;
  background: var(--bg-surface);
  border-radius: 3px;
  overflow: hidden;
}

.vw-export-progress-fill {
  height: 100%;
  background: var(--primary);
  border-radius: 3px;
  transition: width 0.15s ease;
}

.vw-export-progress-text {
  font-size: 0.75rem;
  font-family: var(--font-mono);
  color: var(--text-secondary);
  white-space: nowrap;
}

/* Main area / 主区域 */
.vw-main {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.vw-empty {
  padding: 60px 24px;
  text-align: center;
  color: var(--text-muted);
  font-size: 0.9375rem;
  border: 1px dashed var(--border);
  border-radius: var(--radius-md);
}

.vw-empty p {
  margin: 0;
}

.vw-loading {
  padding: 24px;
}

.vw-error {
  padding: 14px 18px;
  border-radius: var(--radius-md);
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: var(--error);
  font-size: 0.875rem;
}

.vw-error p {
  margin: 0;
}

.vw-display {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* Image section / 图像区域 */
.vw-image-section {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 240px;
  gap: 16px;
}

.vw-image-main {
  position: relative;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.vw-fullres-loading {
  position: absolute;
  bottom: 8px;
  right: 8px;
  padding: 4px 10px;
  border-radius: var(--radius-md);
  background: rgba(0, 0, 0, 0.7);
  color: var(--text-inverse);
  font-size: 0.75rem;
  z-index: 2;
}

/* Stats panel / 统计面板 */
.vw-stats {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  align-self: start;
}

.vw-stats-title {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--text-secondary);
  margin: 0;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.vw-stats-list {
  display: grid;
  gap: 4px;
}

.vw-stat-item {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  font-size: 0.75rem;
}

.vw-stat-item dt {
  color: var(--text-muted);
  font-weight: 500;
}

.vw-stat-item dd {
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: 0.6875rem;
  margin: 0;
}

.vw-meta-info {
  border-top: 1px solid var(--border);
  padding-top: 8px;
  display: grid;
  gap: 3px;
}

.vw-meta-item {
  font-size: 0.6875rem;
  display: flex;
  gap: 4px;
}

.vw-meta-label {
  color: var(--text-muted);
}

.vw-meta-value {
  color: var(--text-primary);
  font-family: var(--font-mono);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Frame navigator bar (main area) / 帧导航条（主区域） */
.vw-frame-nav {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
}

.vw-thumb-strip {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 12px;
  background: var(--bg-surface);
}

.vw-thumb-loading {
  margin: 0;
  font-size: 0.8125rem;
  color: var(--text-secondary);
}

/* Heatmap section / 热力图区域 */
.vw-chart-section {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 12px;
}

.vw-chart-label {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--text-secondary);
  margin: 0 0 8px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.vw-analysis-error {
  margin: 0;
  color: var(--error);
  font-size: 0.8125rem;
}

/* Responsive / 响应式 */
@media (max-width: 1100px) {
  .vw-layout {
    grid-template-columns: 1fr;
  }

  .vw-image-section {
    grid-template-columns: 1fr;
  }
}
</style>
