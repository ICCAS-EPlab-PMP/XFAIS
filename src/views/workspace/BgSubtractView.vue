<template>
  <section class="bg-subtract-page">
    <!-- Header / 页头 -->
    <header class="bgs-header">
      <h1>{{ t('bgSubtract.title') }}</h1>
      <p class="bgs-subtitle">{{ t('bgSubtract.subtitle') }}</p>
      <div class="bgs-notice">
        <span class="bgs-notice-icon">ℹ</span>
        <span>{{ t('bgSubtract.simpleNotice') }}</span>
      </div>
    </header>

    <div class="bgs-layout">
      <!-- ===== Sidebar: controls / 侧边栏：控制面板 ===== -->
      <aside class="bgs-sidebar">
        <!-- Mode toggle / 模式切换 -->
        <div class="bgs-card">
          <h3 class="bgs-card-title">{{ t('bgSubtract.mode') }}</h3>
          <div class="bgs-radio-row">
            <label class="bgs-radio-label">
              <input v-model="mode" type="radio" value="single" />
              <span>{{ t('bgSubtract.modeSingle') }}</span>
            </label>
            <label class="bgs-radio-label">
              <input v-model="mode" type="radio" value="batch" />
              <span>{{ t('bgSubtract.modeBatch') }}</span>
            </label>
          </div>
        </div>

        <!-- File selection / 文件选择 -->
        <div class="bgs-card">
          <h3 class="bgs-card-title">{{ t('bgSubtract.fileSelection') }}</h3>

          <!-- Single mode: multi-file selection / 单文件模式：多文件选择 -->
          <template v-if="mode === 'single'">
            <div class="bgs-file-actions">
              <button type="button" class="bgs-btn" @click="handleChooseSampleFiles">
                {{ t('bgSubtract.selectFiles') }}
              </button>
              <div class="bgs-import-mode">
                <span class="bgs-import-mode-label">{{ t('bgSubtract.importMode') }}</span>
                <label class="bgs-radio-label">
                  <input v-model="importMode" type="radio" value="replace" />
                  <span>{{ t('bgSubtract.importReplace') }}</span>
                </label>
                <label class="bgs-radio-label">
                  <input v-model="importMode" type="radio" value="append" />
                  <span>{{ t('bgSubtract.importAppend') }}</span>
                </label>
              </div>
              <span v-if="samplePaths.length" class="bgs-file-summary">
                {{ t('bgSubtract.fileCount', { count: samplePaths.length }) }}
              </span>
              <span v-else class="bgs-file-summary bgs-file-summary--muted">
                {{ t('bgSubtract.noFilesSelected') }}
              </span>
            </div>

            <!-- File list / 文件列表 -->
            <div v-if="samplePaths.length > 0" class="bgs-file-list-wrap">
              <div class="bgs-file-list-header">
                <span class="bgs-file-list-title">{{ t('bgSubtract.fileList') }}</span>
              </div>
              <div class="bgs-file-list">
                <div
                  v-for="(fp, idx) in samplePaths"
                  :key="fp"
                  class="bgs-file-list-item"
                  :class="{ 'bgs-file-list-item--active': idx === currentSampleIndex }"
                  @click="currentSampleIndex = idx"
                >
                  <span class="bgs-file-list-name" :title="fp">{{ extractFileName(fp) }}</span>
                  <input
                    v-if="transmissionSource === 'per-file'"
                    v-model.number="perFileTransmissions[fp]"
                    type="number"
                    class="bgs-input bgs-input-tiny"
                    min="0"
                    max="100"
                    step="0.1"
                    placeholder="%"
                    @click.stop
                  />
                  <button
                    type="button"
                    class="bgs-file-list-remove"
                    :title="t('bgSubtract.removeFile')"
                    @click.stop="removeSampleFile(idx)"
                  >✕</button>
                </div>
              </div>
            </div>

            <FileDialogButton
              v-model="bgPath"
              mode="openFile"
              :label="t('bgSubtract.bgFile')"
              :filters="dataFileFilters"
            />
          </template>

          <!-- Batch mode: folder selection + scan / 批量模式：文件夹选择 + 扫描 -->
          <template v-else>
            <FileDialogButton
              v-model="sampleFolder"
              mode="openFolder"
              :label="t('bgSubtract.sampleFolder')"
            />
            <div v-if="batchFolderFiles.length > 0" class="bgs-folder-info">
              {{ t('bgSubtract.folderFileCount', { count: batchFolderFiles.length }) }}
            </div>
            <div v-if="batchFolderFiles.length > 0" class="bgs-file-list-wrap">
              <div class="bgs-file-list">
                <div
                  v-for="(fp, idx) in batchFolderFiles"
                  :key="fp"
                  class="bgs-file-list-item"
                  :class="{ 'bgs-file-list-item--active': idx === currentSampleIndex }"
                  @click="currentSampleIndex = idx"
                >
                  <span class="bgs-file-list-name" :title="fp">{{ extractFileName(fp) }}</span>
                </div>
              </div>
            </div>
            <FileDialogButton
              v-model="bgPath"
              mode="openFile"
              :label="t('bgSubtract.bgFile')"
              :filters="dataFileFilters"
            />
          </template>
        </div>

        <!-- Ionchamber section / 电离室部分 -->
        <div class="bgs-card">
          <h3 class="bgs-card-title">{{ t('bgSubtract.ionchamber') }}</h3>

          <div class="bgs-radio-row">
            <label class="bgs-radio-label">
              <input v-model="transmissionSource" type="radio" value="manual" />
              <span>{{ t('bgSubtract.transManual') }}</span>
            </label>
            <label class="bgs-radio-label" :class="{ 'bgs-radio-label--disabled': tooManyFilesForPerFile }">
              <input v-model="transmissionSource" type="radio" value="per-file" :disabled="tooManyFilesForPerFile" />
              <span>{{ t('bgSubtract.transPerFile') }}</span>
            </label>
            <label class="bgs-radio-label">
              <input v-model="transmissionSource" type="radio" value="ionchamber" />
              <span>{{ t('bgSubtract.transIonchamber') }}</span>
            </label>
          </div>

          <div v-if="transmissionSource === 'per-file' && tooManyFilesForPerFile" class="bgs-match-warning">
            ⚠ {{ t('bgSubtract.tooManyFilesWarning') }}
          </div>

          <!-- Manual transmission / 手动透射率 -->
          <div v-if="transmissionSource === 'manual'" class="bgs-field">
            <label class="bgs-label">{{ t('bgSubtract.transmissionValue') }} (%)</label>
            <input
              v-model.number="manualTransmission"
              type="number"
              class="bgs-input"
              min="0"
              max="100"
              step="0.1"
            />
          </div>

          <!-- Ionchamber folder + match + filters / 电离室文件夹 + 匹配 + 过滤 -->
          <template v-if="transmissionSource === 'ionchamber'">
            <FileDialogButton
              v-model="ionchamberFolder"
              mode="openFolder"
              :label="t('bgSubtract.ionchamberFolder')"
            />

            <!-- Background ionchamber file / 背景电离室文件 -->
            <FileDialogButton
              v-model="bgIonchamberPath"
              mode="openFile"
              :label="t('bgSubtract.bgIonchamberFile')"
              :filters="[{ name: 'All Files', extensions: ['*'] }]"
            />
            <div v-if="!bgIonchamberPath" class="bgs-match-warning">
              ⚠ {{ t('bgSubtract.noBgIonchamberWarning') }}
            </div>

            <!-- Ionchamber channel selector / 电离室通道选择 -->
            <div class="bgs-field">
              <label class="bgs-label">{{ t('bgSubtract.ionchamberChannel') }}</label>
              <select v-model="ionchamberChannel" class="bgs-select">
                <option value="Ionchamber0">Ionchamber0 (I₀)</option>
                <option value="Ionchamber1">Ionchamber1 (I₁)</option>
                <option value="Ionchamber2">Ionchamber2 (I₂)</option>
              </select>
            </div>

            <!-- Ionchamber method selector / 电离室计算方法 -->
            <div class="bgs-field">
              <label class="bgs-label">{{ t('bgSubtract.ionchamberMethod') }}</label>
              <select v-model="ionchamberMethod" class="bgs-select">
                <option value="median">{{ t('bgSubtract.methodMedian') }}</option>
                <option value="mean">{{ t('bgSubtract.methodMean') }}</option>
                <option value="trimmed_mean">{{ t('bgSubtract.methodTrimmedMean') }}</option>
              </select>
            </div>

            <!-- Match threshold slider / 匹配阈值滑块 -->
            <div class="bgs-field">
              <label class="bgs-label">
                {{ t('bgSubtract.matchThreshold') }}: {{ minScore.toFixed(2) }}
              </label>
              <input
                v-model.number="minScore"
                type="range"
                class="bgs-slider"
                min="0"
                max="1"
                step="0.05"
              />
            </div>

            <!-- Regex pattern / 正则表达式 -->
            <div class="bgs-field">
              <label class="bgs-label">{{ t('bgSubtract.matchRegex') }}</label>
              <input
                v-model="regexPattern"
                type="text"
                class="bgs-input"
                :placeholder="t('bgSubtract.matchRegexHint')"
              />
            </div>

            <button
              type="button"
              class="bgs-btn"
              :disabled="!canMatchIonchamber"
              @click="handleMatchIonchamber"
            >
              {{ matchingIonchamber ? t('bgSubtract.matching') : t('bgSubtract.matchBtn') }}
            </button>

            <!-- Match results table / 匹配结果表 -->
            <div v-if="ionchamberMatches.length > 0" class="bgs-match-table-wrap">
              <!-- Warning if no background ionchamber provided / 如果没有提供背景电离室文件 -->
              <div v-if="!bgIonchamberPath" class="bgs-match-warning">
                ⚠ {{ t('bgSubtract.noBgIonchamberWarning') }}
              </div>
              <table class="bgs-match-table">
                <thead>
                  <tr>
                    <th>{{ t('bgSubtract.matchColFile') }}</th>
                    <th>{{ t('bgSubtract.matchColIon') }}</th>
                    <th>{{ t('bgSubtract.matchColScore') }}</th>
                    <th>{{ t('bgSubtract.matchColTrans') }}</th>
                    <th>{{ t('bgSubtract.matchColNote') }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="m in ionchamberMatches" :key="m.data_file">
                    <td :title="m.data_file">{{ extractFileName(m.data_file) }}</td>
                    <td>{{ m.matched_ion ?? '—' }}</td>
                    <td>{{ typeof m.score === 'number' ? m.score.toFixed(3) : '—' }}</td>
                    <td>{{ typeof m.transmission === 'number' ? (m.transmission * 100).toFixed(2) + '%' : '—' }}</td>
                    <td :class="{ 'bgs-error-cell': m.error }">{{ m.note || m.error || '' }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </template>
        </div>

        <!-- Export settings / 导出设置 -->
        <div class="bgs-card">
          <h3 class="bgs-card-title">{{ t('bgSubtract.export') }}</h3>
          <FileDialogButton
            v-model="outputDir"
            mode="openFolder"
            :label="t('bgSubtract.outputDir')"
          />
          <div class="bgs-field">
            <label class="bgs-label">{{ t('bgSubtract.outputFormat') }}</label>
            <select v-model="outputFormat" class="bgs-select">
              <option value="h5">HDF5</option>
              <option value="edf">EDF</option>
              <option value="tif">TIFF</option>
            </select>
          </div>
        </div>

        <!-- Execute / 执行 -->
        <div class="bgs-card">
          <button
            type="button"
            class="bgs-btn bgs-btn-primary"
            :disabled="!canSubtract"
            @click="handleSubtract"
          >
            {{ mode === 'batch' ? t('bgSubtract.startBatch') : t('bgSubtract.execute') }}
          </button>
        </div>
      </aside>

      <!-- ===== Main area / 主区域 ===== -->
      <main class="bgs-main">
        <!-- Row 1: Sample + Background side by side / 样品与背景并列 -->
        <div class="bgs-two-row">
          <!-- Sample panel / 样品面板 -->
          <div class="bgs-panel">
            <div class="bgs-panel-header">
              <span class="bgs-panel-title">{{ t('bgSubtract.tabSample') }}</span>
            </div>
            <div v-if="samplePreviewLoading" class="bgs-preview-loading">
              {{ t('bgSubtract.loading') }}
            </div>
            <div v-else-if="samplePreviewUrl" class="bgs-panel-image">
              <ImagePreview
                :image-b64="samplePreviewUrl"
                :show-colorbar="false"
                :placeholder="t('bgSubtract.noImage')"
                :render-min="climMode === 'manual' ? climMin : undefined"
                :render-max="climMode === 'manual' ? climMax : undefined"
                :use-log-scale="useLog"
              />
            </div>
            <div v-else class="bgs-preview-empty">
              {{ t('bgSubtract.noPreview') }}
            </div>
            <div v-if="samplePreviewStats" class="bgs-panel-stats">
              <span>Min: {{ formatSci(samplePreviewStats.min) }}</span>
              <span>Max: {{ formatSci(samplePreviewStats.max) }}</span>
              <span>Mean: {{ formatSci(samplePreviewStats.mean) }}</span>
            </div>
          </div>

          <!-- Background panel / 背景面板 -->
          <div class="bgs-panel">
            <div class="bgs-panel-header">
              <span class="bgs-panel-title">{{ t('bgSubtract.tabBackground') }}</span>
              <span v-if="bgPath" class="bgs-panel-file-hint">{{ extractFileName(bgPath) }}</span>
            </div>
            <div v-if="bgPreviewLoading" class="bgs-preview-loading">
              {{ t('bgSubtract.loading') }}
            </div>
            <div v-else-if="bgPreviewUrl" class="bgs-panel-image">
              <ImagePreview
                :image-b64="bgPreviewUrl"
                :show-colorbar="false"
                :placeholder="t('bgSubtract.noImage')"
                :render-min="climMode === 'manual' ? climMin : undefined"
                :render-max="climMode === 'manual' ? climMax : undefined"
                :use-log-scale="useLog"
              />
            </div>
            <div v-else class="bgs-preview-empty">
              {{ t('bgSubtract.noPreview') }}
            </div>
            <div v-if="bgPreviewStats" class="bgs-panel-stats">
              <span>Min: {{ formatSci(bgPreviewStats.min) }}</span>
              <span>Max: {{ formatSci(bgPreviewStats.max) }}</span>
              <span>Mean: {{ formatSci(bgPreviewStats.mean) }}</span>
            </div>
          </div>
        </div>

        <!-- Display settings / 显示设置 -->
        <div class="bgs-card bgs-display-bar">
          <div class="bgs-display-row">
            <div class="bgs-field" style="min-width:140px">
              <label class="bgs-label">{{ t('bgSubtract.colormap') }}</label>
              <select v-model="colormap" class="bgs-select">
                <option v-for="cm in colormapOptions" :key="cm" :value="cm">{{ cm }}</option>
              </select>
            </div>
            <label class="bgs-toggle-label" style="white-space:nowrap">
              <input v-model="useLog" type="checkbox" />
              <span>{{ t('bgSubtract.logScale') }}</span>
            </label>
            <div class="bgs-radio-row">
              <label class="bgs-radio-label">
                <input v-model="climMode" type="radio" value="auto" />
                <span>{{ t('bgSubtract.contrastAuto') }}</span>
              </label>
              <label class="bgs-radio-label">
                <input v-model="climMode" type="radio" value="manual" />
                <span>{{ t('bgSubtract.contrastManual') }}</span>
              </label>
            </div>
            <template v-if="climMode === 'manual'">
              <div class="bgs-field">
                <label class="bgs-label">Min</label>
                <input v-model.number="climMin" type="number" class="bgs-input bgs-input-sm" step="any" />
              </div>
              <div class="bgs-field">
                <label class="bgs-label">Max</label>
                <input v-model.number="climMax" type="number" class="bgs-input bgs-input-sm" step="any" />
              </div>
            </template>
          </div>
        </div>

        <!-- Result panel / 结果面板 -->
        <div v-if="resultPreviewUrl || resultPreviewLoading" class="bgs-panel bgs-result-panel-single">
          <div class="bgs-panel-header">
            <span class="bgs-panel-title">{{ t('bgSubtract.tabResult') }}</span>
          </div>
          <div v-if="resultPreviewLoading" class="bgs-preview-loading">
            {{ t('bgSubtract.loading') }}
          </div>
          <div v-else-if="resultPreviewUrl" class="bgs-panel-image">
            <ImagePreview
              :image-b64="resultPreviewUrl"
              :show-colorbar="false"
              :placeholder="t('bgSubtract.noImage')"
              :render-min="climMode === 'manual' ? climMin : undefined"
              :render-max="climMode === 'manual' ? climMax : undefined"
              :use-log-scale="useLog"
            />
          </div>
          <div v-if="resultPreviewStats" class="bgs-panel-stats">
            <span>Min: {{ formatSci(resultPreviewStats.min) }}</span>
            <span>Max: {{ formatSci(resultPreviewStats.max) }}</span>
            <span>Mean: {{ formatSci(resultPreviewStats.mean) }}</span>
          </div>
        </div>

        <!-- Thumbnail strip below result / 缩略图在结果下方 -->
        <div
          v-if="currentSamplePaths.length > 1 && (thumbnailItems.length || thumbnailsLoading)"
          class="bgs-thumb-strip"
        >
          <ThumbnailStrip
            :items="thumbnailItems"
            :selected-index="currentSampleIndex"
            :current-page="1"
            :total-pages="1"
            :page-size="100"
            :loading="thumbnailsLoading"
            :sync-with-main="false"
            :columns-per-row="6"
            @select="onThumbnailSelect"
          />
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
        <div v-if="state === 'error'" class="bgs-error">
          <p>{{ t('bgSubtract.errorPrefix') }} {{ errorMessage }}</p>
        </div>

        <!-- Batch result summary / 批量结果摘要 -->
        <ResultSummary
          v-if="batchResultSummary"
          :summary="batchResultSummary"
        />

        <!-- Empty state / 空状态 -->
        <div v-if="state === 'idle' && !samplePreviewUrl && !batchResultSummary" class="bgs-empty">
          <p>{{ t('bgSubtract.emptyState') }}</p>
        </div>
      </main>
    </div>
  </section>
</template>

<script setup lang="ts">
/**
 * BgSubtractView.vue — 背景减除页面
 * Background subtraction page: single/batch processing with ionchamber matching,
 * multi-file selection, folder scanning, and image display controls.
 */
import { ref, computed, watch, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useToast } from '@/lib/toast'
import { useTransport } from '@/lib/transport'
import type { TaskBinaryPayload } from '@/lib/transport'
import { COLORMAP_PRESETS } from '@/lib/chart-utils'

import FileDialogButton from '@/components/business/FileDialogButton.vue'
import TaskProgressBar from '@/components/business/TaskProgressBar.vue'
import ResultSummary from '@/components/business/ResultSummary.vue'
import type { ResultSummaryData } from '@/components/business/ResultSummary.vue'
import ThumbnailStrip from '@/components/business/ThumbnailStrip.vue'
import type { ThumbnailItem } from '@/components/business/ThumbnailStrip.vue'
import ImagePreview from '@/components/charts/ImagePreview.vue'

// === Type definitions / 类型定义 ===

interface IonchamberMatch {
  data_file: string
  matched_ion: string | null
  score?: number
  method?: string
  transmission?: number
  note?: string
  error?: string
  transmission_computed?: boolean
}

interface BatchResult {
  success_count: number
  failed_count: number
  failed_files: string[]
  output_dir: string
  elapsed: number
}

interface PreviewStats {
  min: number
  max: number
  mean: number
  shape?: [number, number]
}

type PageState = 'idle' | 'running' | 'done' | 'error'
type Mode = 'single' | 'batch'
type TransmissionSource = 'manual' | 'per-file' | 'ionchamber'
type ImportMode = 'replace' | 'append'

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

// === Mode & state / 模式与状态 ===

const mode = ref<Mode>('single')
const state = ref<PageState>('idle')
const taskId = ref<string | null>(null)
const progress = ref(0)
const progressMessage = ref<string | null>(null)
const errorMessage = ref('')

// === File selection / 文件选择 ===

const samplePaths = ref<string[]>([])
const bgPath = ref<string | null>(null)
const sampleFolder = ref<string | null>(null)
const importMode = ref<ImportMode>('replace')
const currentSampleIndex = ref(0)
const batchFolderFiles = ref<string[]>([])

const dataFileFilters = [
  { name: 'Detector Images', extensions: ['edf', 'tif', 'tiff', 'h5', 'hdf5'] },
]

// === Ionchamber / 电离室 ===

const ionchamberFolder = ref<string | null>(null)
const bgIonchamberPath = ref<string | null>(null)
const ionchamberMatches = ref<IonchamberMatch[]>([])
const manualTransmission = ref(100)
const perFileTransmissions = ref<Record<string, number>>({})
const transmissionSource = ref<TransmissionSource>('manual')
const matchingIonchamber = ref(false)
const minScore = ref(0.4)
const regexPattern = ref('')
const ionchamberChannel = ref('Ionchamber0')
const ionchamberMethod = ref<'median' | 'mean' | 'trimmed_mean'>('median')

// === Display settings / 显示设置 ===

const colormap = ref('smooth_WAXS_foxtrot')
const useLog = ref(false)
const climMode = ref<'auto' | 'manual'>('auto')
const climMin = ref(0)
const climMax = ref(1)

// Debounce timer for contrast changes / 对比度变化防抖定时器
let contrastDebounceTimer: ReturnType<typeof setTimeout> | null = null

// === Preview / 预览 ===

// Per-panel preview data / 每栏独立预览数据
const samplePreviewUrl = ref<string | null>(null)
const samplePreviewStats = ref<PreviewStats | null>(null)
const samplePreviewLoading = ref(false)
const bgPreviewUrl = ref<string | null>(null)
const bgPreviewStats = ref<PreviewStats | null>(null)
const bgPreviewLoading = ref(false)
const resultPreviewUrl = ref<string | null>(null)
const resultPreviewStats = ref<PreviewStats | null>(null)
const resultPreviewLoading = ref(false)

// Thumbnail strip / 缩略图
const thumbnailItems = ref<ThumbnailItem[]>([])
const thumbnailsLoading = ref(false)

// === Batch result / 批量结果 ===

const batchResult = ref<BatchResult | null>(null)

// === Export / 导出 ===

const outputDir = ref<string | null>(null)
const outputFormat = ref<'h5' | 'edf' | 'tif'>('tif')

// === Cleanup functions / 清理函数 ===

let cleanupProgress: (() => void) | null = null
let cleanupResult: (() => void) | null = null
let cleanupError: (() => void) | null = null
let cleanupBinaryData: (() => void) | null = null

// === Computed / 计算属性 ===

const currentSamplePaths = computed(() => {
  if (mode.value === 'single') return samplePaths.value
  return batchFolderFiles.value
})

const canSubtract = computed(() => {
  if (state.value === 'running') return false
  if (mode.value === 'single') {
    return samplePaths.value.length > 0 && !!bgPath.value
  }
  return batchFolderFiles.value.length > 0 && !!bgPath.value && !!outputDir.value
})

const canMatchIonchamber = computed(() => {
  const hasFiles = mode.value === 'batch'
    ? batchFolderFiles.value.length > 0
    : samplePaths.value.length > 0
  return hasFiles && !!ionchamberFolder.value && !matchingIonchamber.value
})

const tooManyFilesForPerFile = computed(() => currentSamplePaths.value.length > 10)

const batchResultSummary = computed<ResultSummaryData | null>(() => {
  if (!batchResult.value) return null
  return {
    total: batchResult.value.success_count + batchResult.value.failed_count,
    success: batchResult.value.success_count,
    failed: batchResult.value.failed_count,
    elapsed: batchResult.value.elapsed,
  }
})

// === Watchers / 监听器 ===

// Reload preview when contrast settings change (debounced to prevent bounce)
// 对比度设置变化时重新加载预览（防抖以避免值弹回）
let suppressContrastReload = false

watch([climMode, climMin, climMax, useLog], () => {
  if (suppressContrastReload) return
  // Skip if values are invalid (e.g. user is mid-typing) / 跳过无效值
  if (climMode.value === 'manual') {
    if (!Number.isFinite(climMin.value) || !Number.isFinite(climMax.value)) return
  }
  // Debounce: wait for user to finish typing / 防抖：等待用户输入完毕
  if (contrastDebounceTimer) clearTimeout(contrastDebounceTimer)
  contrastDebounceTimer = setTimeout(() => {
    contrastDebounceTimer = null
    if (state.value === 'idle') {
      reloadAllPreviews()
    }
  }, 400)
})

watch(sampleFolder, (folder) => {
  batchFolderFiles.value = []
  currentSampleIndex.value = 0
  if (folder) {
    void scanFolder(folder)
  }
})

// Reload panels when current sample index changes / 样品索引变化时重新加载面板
watch(currentSampleIndex, () => {
  if (currentSamplePaths.value.length > 0) {
    loadSamplePanel()
    if (resultPreviewUrl.value || state.value === 'done') {
      loadResultPanel()
    }
  }
})

// Auto-load background panel when bgPath changes / 背景文件变化时自动加载
watch(bgPath, (newPath) => {
  if (newPath) {
    loadBgPanel()
  } else {
    if (bgPreviewUrl.value?.startsWith('blob:')) URL.revokeObjectURL(bgPreviewUrl.value)
    bgPreviewUrl.value = null
    bgPreviewStats.value = null
  }
})

// Force switch away from per-file when too many files / 文件过多时强制切离逐文件模式
watch(tooManyFilesForPerFile, (tooMany) => {
  if (tooMany && transmissionSource.value === 'per-file') {
    transmissionSource.value = 'manual'
  }
})

// === Helpers / 辅助函数 ===

function extractFileName(filePath: string): string {
  const sep = filePath.includes('/') ? '/' : '\\'
  const parts = filePath.split(sep)
  return parts[parts.length - 1] || filePath
}

function formatSci(value: number): string {
  if (!Number.isFinite(value)) return '—'
  if (value === 0) return '0'
  return value.toExponential(3)
}

function getMatchedTransmission(): number {
  if (ionchamberMatches.value.length > 0) {
    const first = ionchamberMatches.value[0]
    if (first) return first.transmission ?? manualTransmission.value / 100
  }
  return manualTransmission.value / 100
}

function getPerFileTransmissions(): Record<string, number> {
  const result: Record<string, number> = {}
  for (const fp of currentSamplePaths.value) {
    const pct = perFileTransmissions.value[fp] ?? manualTransmission.value
    result[fp] = pct / 100  // convert % to ratio
  }
  return result
}

function getRenderSettingsParams(): Record<string, unknown> {
  const params: Record<string, unknown> = {
    cmap: colormap.value,
    use_log: useLog.value,
  }
  if (climMode.value === 'manual') {
    params.clim_min = climMin.value
    params.clim_max = climMax.value
  }
  return params
}

function removeSampleFile(index: number): void {
  const fp = samplePaths.value[index]
  samplePaths.value.splice(index, 1)
  if (fp) delete perFileTransmissions.value[fp]
  if (currentSampleIndex.value >= samplePaths.value.length) {
    currentSampleIndex.value = Math.max(0, samplePaths.value.length - 1)
  }
}

// === Multi-file selection / 多文件选择 ===

async function handleChooseSampleFiles(): Promise<void> {
  const result = await transport.selectFiles({
    filters: dataFileFilters,
    multiSelections: true,
  })
  if (!result) return
  const paths = Array.isArray(result) ? result : [result]
  if (importMode.value === 'append') {
    const existingSet = new Set(samplePaths.value)
    const newFiles = paths.filter(p => !existingSet.has(p))
    samplePaths.value = [...samplePaths.value, ...newFiles]
  } else {
    samplePaths.value = paths
    currentSampleIndex.value = 0
  }
  // Initialize per-file transmission defaults / 初始化逐文件透射率默认值
  for (const p of paths) {
    if (perFileTransmissions.value[p] === undefined) {
      perFileTransmissions.value[p] = manualTransmission.value  // copy current manual value as default
    }
  }
  // Load sample panel after file selection / 选择文件后加载样品面板
  if (samplePaths.value.length > 0) {
    loadSamplePanel()
    generateThumbnails()
  }
}

// === Folder scanning / 文件夹扫描 ===

async function scanFolder(folder: string): Promise<void> {
  try {
    const response = await transport.submitTask('bg_subtract', {
      action: 'scan_folder',
      folder,
    })
    const unsubResult = transport.onTaskResult(response.taskId, (payload) => {
      const data = payload.data as { files: string[]; count: number }
      batchFolderFiles.value = data.files ?? []
      currentSampleIndex.value = 0
      if (batchFolderFiles.value.length > 0) {
        loadSamplePanel()
        generateThumbnails()
      }
      unsubResult()
      unsubError()
    })
    const unsubError = transport.onTaskError(response.taskId, (payload) => {
      toast.push({
        title: t('bgSubtract.errorTitle'),
        message: payload.error,
        tone: 'error',
      })
      unsubResult()
      unsubError()
    })
  } catch (err) {
    toast.push({
      title: t('bgSubtract.errorTitle'),
      message: err instanceof Error ? err.message : String(err),
      tone: 'error',
    })
  }
}

// === Ionchamber matching / 电离室匹配 ===

async function handleMatchIonchamber(): Promise<void> {
  const files = currentSamplePaths.value
  if (files.length === 0 || !ionchamberFolder.value) return

  matchingIonchamber.value = true
  ionchamberMatches.value = []

  try {
    const response = await transport.submitTask('bg_subtract', {
      action: 'ionchamber_match',
      sample_folder: mode.value === 'batch' ? sampleFolder.value : undefined,
      data_files: mode.value === 'single' ? files : undefined,
      ionchamber_folder: ionchamberFolder.value,
      bg_ionchamber_path: bgIonchamberPath.value || undefined,
      ionchamber_channel: ionchamberChannel.value,
      ionchamber_method: ionchamberMethod.value,
      min_score: minScore.value,
      regex_pattern: regexPattern.value || undefined,
    })

    const unsubResult = transport.onTaskResult(response.taskId, (payload) => {
      const data = payload.data as { matches: IonchamberMatch[] }
      ionchamberMatches.value = data.matches ?? []
      matchingIonchamber.value = false
      unsubResult()
      unsubError()
    })

    const unsubError = transport.onTaskError(response.taskId, (payload) => {
      matchingIonchamber.value = false
      toast.push({
        title: t('bgSubtract.errorTitle'),
        message: payload.error,
        tone: 'error',
      })
      unsubResult()
      unsubError()
    })
  } catch (err) {
    matchingIonchamber.value = false
    toast.push({
      title: t('bgSubtract.errorTitle'),
      message: err instanceof Error ? err.message : String(err),
      tone: 'error',
    })
  }
}

// === Preview / 预览 ===

function cleanupPreviewListeners(): void {
  cleanupBinaryData?.()
  cleanupBinaryData = null
}

// Load preview into a specific panel's refs / 加载预览到指定面板的 ref
function loadPanelPreview(
  tab: 'sample' | 'background' | 'result',
  urlRef: { value: string | null },
  statsRef: { value: PreviewStats | null },
  loadingRef: { value: boolean }
): void {
  loadingRef.value = true
  suppressContrastReload = true
  if (urlRef.value?.startsWith('blob:')) {
    URL.revokeObjectURL(urlRef.value)
  }
  urlRef.value = null
  statsRef.value = null
  cleanupPreviewListeners()

  let filePath: string | null = null
  let previewAction: string

  const files = currentSamplePaths.value

  switch (tab) {
    case 'sample':
      filePath = files.length > 0 ? files[currentSampleIndex.value] ?? files[0] ?? null : null
      previewAction = 'preview_sample'
      break
    case 'background':
      filePath = bgPath.value
      previewAction = 'preview_background'
      break
    case 'result':
      filePath = files.length > 0 ? files[currentSampleIndex.value] ?? files[0] ?? null : null
      previewAction = 'preview_result'
      break
    default:
      loadingRef.value = false
      return
  }

  if (!filePath) {
    loadingRef.value = false
    return
  }

  const params: Record<string, unknown> = {
    action: previewAction,
    sample_path: filePath,
    bg_path: bgPath.value,
    ...getRenderSettingsParams(),
  }

  if (tab === 'result') {
    if (transmissionSource.value === 'per-file') {
      const currentFile = files[currentSampleIndex.value]
      params.transmission = (perFileTransmissions.value[currentFile] ?? manualTransmission.value) / 100
    } else if (transmissionSource.value === 'manual') {
      params.transmission = manualTransmission.value / 100
    } else {
      params.transmission = getMatchedTransmission()
    }
  }

  transport.submitTask('bg_subtract', params).then((response) => {
    cleanupBinaryData = transport.onTaskBinaryData(response.taskId, (payload: TaskBinaryPayload) => {
      if (payload.data) {
        const blob = new Blob([payload.data], { type: payload.mime || 'image/png' })
        if (urlRef.value?.startsWith('blob:')) {
          URL.revokeObjectURL(urlRef.value)
        }
        urlRef.value = URL.createObjectURL(blob)
      }
    })

    const unsubResult = transport.onTaskResult(response.taskId, (payload) => {
      const data = payload.data as { stats?: PreviewStats }
      if (data.stats) {
        statsRef.value = data.stats
        if (climMode.value === 'auto' && tab === 'sample') {
          climMin.value = data.stats.min
          climMax.value = data.stats.max
        }
      }
      loadingRef.value = false
      suppressContrastReload = false
      unsubResult()
      unsubError()
    })

    const unsubError = transport.onTaskError(response.taskId, (payload) => {
      loadingRef.value = false
      suppressContrastReload = false
      toast.push({
        title: t('bgSubtract.errorTitle'),
        message: payload.error,
        tone: 'error',
      })
      unsubResult()
      unsubError()
    })
  }).catch((err: unknown) => {
    loadingRef.value = false
    suppressContrastReload = false
    toast.push({
      title: t('bgSubtract.errorTitle'),
      message: err instanceof Error ? err.message : String(err),
      tone: 'error',
    })
  })
}

// Reload all visible panels / 重新加载所有可见面板
function reloadAllPreviews(): void {
  loadPanelPreview('sample', samplePreviewUrl, samplePreviewStats, samplePreviewLoading)
  if (bgPath.value) {
    loadPanelPreview('background', bgPreviewUrl, bgPreviewStats, bgPreviewLoading)
  }
  if (resultPreviewUrl.value || state.value === 'done') {
    loadPanelPreview('result', resultPreviewUrl, resultPreviewStats, resultPreviewLoading)
  }
}

// Load sample panel (called when files are selected) / 加载样品面板
function loadSamplePanel(): void {
  loadPanelPreview('sample', samplePreviewUrl, samplePreviewStats, samplePreviewLoading)
}

// Load background panel / 加载背景面板
function loadBgPanel(): void {
  if (bgPath.value) {
    loadPanelPreview('background', bgPreviewUrl, bgPreviewStats, bgPreviewLoading)
  }
}

// Load result panel / 加载结果面板
function loadResultPanel(): void {
  loadPanelPreview('result', resultPreviewUrl, resultPreviewStats, resultPreviewLoading)
}

// Generate thumbnails for sample files / 为样品文件生成缩略图
async function generateThumbnails(): Promise<void> {
  const paths = currentSamplePaths.value
  if (paths.length <= 1) {
    thumbnailItems.value = []
    return
  }

  thumbnailsLoading.value = true
  const items: ThumbnailItem[] = []

  for (let i = 0; i < paths.length; i++) {
    const path = paths[i]
    const label = extractFileName(path)
    try {
      const result = await new Promise<any>((resolve, reject) => {
        transport.submitTask('bg_subtract', {
          action: 'preview_sample',
          sample_path: path,
          bg_path: bgPath.value,
          ...getRenderSettingsParams(),
        }).then((response) => {
          let b64Data = ''
          const unsubBinary = transport.onTaskBinaryData(response.taskId, (payload: TaskBinaryPayload) => {
            if (payload.data) {
              const bytes = new Uint8Array(payload.data)
              let binary = ''
              for (let j = 0; j < bytes.byteLength; j++) {
                binary += String.fromCharCode(bytes[j])
              }
              b64Data = btoa(binary)
            }
          })
          const unsubResult = transport.onTaskResult(response.taskId, () => {
            unsubBinary()
            unsubResult()
            unsubError()
            resolve({ b64: b64Data })
          })
          const unsubError = transport.onTaskError(response.taskId, (p) => {
            unsubBinary()
            unsubResult()
            unsubError()
            reject(new Error(p.error))
          })
        }).catch(reject)
      })
      items.push({ index: i, b64: result.b64 || '', label })
    } catch {
      items.push({ index: i, b64: '', label })
    }
  }

  thumbnailItems.value = items
  thumbnailsLoading.value = false
}

// Handle thumbnail click / 缩略图点击处理
function onThumbnailSelect(index: number): void {
  currentSampleIndex.value = index
  // Watcher on currentSampleIndex handles panel reloading
}

// === Subtraction execution / 执行减除 ===

async function handleSubtract(): Promise<void> {
  if (state.value === 'running') return

  state.value = 'running'
  progress.value = 0
  progressMessage.value = null
  errorMessage.value = ''
  batchResult.value = null

  const params: Record<string, unknown> = mode.value === 'single'
    ? {
        action: samplePaths.value.length > 1 ? 'batch' : 'subtract',
        sample_path: samplePaths.value.length === 1 ? samplePaths.value[0] : undefined,
        data_files: samplePaths.value.length > 1 ? samplePaths.value : undefined,
        bg_path: bgPath.value,
        output_dir: samplePaths.value.length > 1 ? outputDir.value : undefined,
        output_format: samplePaths.value.length > 1 ? outputFormat.value : undefined,
        ionchamber_folder: transmissionSource.value === 'ionchamber'
          ? ionchamberFolder.value ?? undefined
          : undefined,
        bg_ionchamber_path: transmissionSource.value === 'ionchamber'
          ? bgIonchamberPath.value || undefined
          : undefined,
        ionchamber_channel: transmissionSource.value === 'ionchamber'
          ? ionchamberChannel.value
          : undefined,
        ionchamber_method: transmissionSource.value === 'ionchamber'
          ? ionchamberMethod.value
          : undefined,
      }
    : {
        action: 'batch',
        folder_path: sampleFolder.value,
        bg_path: bgPath.value,
        ionchamber_folder: transmissionSource.value === 'ionchamber'
          ? ionchamberFolder.value ?? undefined
          : undefined,
        bg_ionchamber_path: transmissionSource.value === 'ionchamber'
          ? bgIonchamberPath.value || undefined
          : undefined,
        ionchamber_channel: transmissionSource.value === 'ionchamber'
          ? ionchamberChannel.value
          : undefined,
        ionchamber_method: transmissionSource.value === 'ionchamber'
          ? ionchamberMethod.value
          : undefined,
        output_dir: outputDir.value,
        output_format: outputFormat.value,
      }

  // Set transmission params / 设置透射率参数
  if (mode.value === 'single') {
    if (transmissionSource.value === 'per-file') {
      if (samplePaths.value.length === 1) {
        params.transmission = (perFileTransmissions.value[samplePaths.value[0]] ?? manualTransmission.value) / 100
      } else {
        params.transmissions = getPerFileTransmissions()
      }
    } else if (transmissionSource.value === 'manual') {
      params.transmission = manualTransmission.value / 100
    } else {
      params.transmission = getMatchedTransmission()
    }
  }

  try {
    const response = await transport.submitTask('bg_subtract', params)
    taskId.value = response.taskId

    cleanupProgress = transport.onTaskProgress(response.taskId, (payload) => {
      progress.value = payload.progress
      progressMessage.value = payload.message ?? null
    })

    cleanupResult = transport.onTaskResult(response.taskId, (payload) => {
      const isBatch = mode.value === 'batch' || samplePaths.value.length > 1
      if (isBatch) {
        const data = payload.data as BatchResult
        batchResult.value = data
        toast.push({
          title: t('bgSubtract.successTitle'),
          message: t('bgSubtract.batchComplete', {
            success: data.success_count,
            failed: data.failed_count,
          }),
          tone: 'success',
        })
      } else {
        loadResultPanel()
        generateThumbnails()
        toast.push({
          title: t('bgSubtract.successTitle'),
          message: t('bgSubtract.subtractComplete'),
          tone: 'success',
        })
      }
      taskId.value = null
      state.value = 'done'
      progress.value = 1
    })

    cleanupError = transport.onTaskError(response.taskId, (payload) => {
      taskId.value = null
      errorMessage.value = payload.error
      state.value = 'error'
      toast.push({
        title: t('bgSubtract.errorTitle'),
        message: payload.error,
        tone: 'error',
      })
    })
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : String(err)
    state.value = 'error'
    toast.push({
      title: t('bgSubtract.errorTitle'),
      message: errorMessage.value,
      tone: 'error',
    })
  }
}

// === Cancel / 取消 ===

async function handleCancel(): Promise<void> {
  const tid = taskId.value
  taskId.value = null
  state.value = 'idle'
  progress.value = 0
  cleanupListeners()
  if (tid) {
    try { await transport.cancelTask(tid) } catch { /* already finished */ }
  }
}

// === Cleanup / 清理 ===

function cleanupListeners(): void {
  cleanupProgress?.()
  cleanupProgress = null
  cleanupResult?.()
  cleanupResult = null
  cleanupError?.()
  cleanupError = null
  cleanupPreviewListeners()
}

onUnmounted(() => {
  if (samplePreviewUrl.value?.startsWith('blob:')) URL.revokeObjectURL(samplePreviewUrl.value)
  if (bgPreviewUrl.value?.startsWith('blob:')) URL.revokeObjectURL(bgPreviewUrl.value)
  if (resultPreviewUrl.value?.startsWith('blob:')) URL.revokeObjectURL(resultPreviewUrl.value)
  cleanupListeners()
  if (contrastDebounceTimer) clearTimeout(contrastDebounceTimer)
})
</script>

<style scoped>
.bg-subtract-page {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.bgs-header {
  padding-bottom: 8px;
}

.bgs-header h1 {
  font-size: 1.5rem;
  font-weight: 700;
  margin: 0 0 6px;
  color: var(--text-primary);
}

.bgs-subtitle {
  font-size: 0.9375rem;
  color: var(--text-secondary);
  margin: 0;
}

.bgs-layout {
  display: grid;
  grid-template-columns: minmax(280px, 380px) minmax(0, 1fr);
  gap: 24px;
  align-items: start;
}

/* Sidebar / 侧边栏 */
.bgs-sidebar {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* Card / 卡片 */
.bgs-card {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  background: var(--bg-surface);
}

.bgs-card-title {
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

/* Main area / 主区域 */
.bgs-main {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* Radio row / 单选行 */
.bgs-radio-row {
  display: flex;
  align-items: center;
  gap: 16px;
}

.bgs-radio-label {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  font-size: 0.875rem;
  color: var(--text-primary);
  white-space: nowrap;
}

.bgs-radio-label input[type="radio"] {
  accent-color: var(--primary);
  width: 14px;
  height: 14px;
}

/* Field / 字段 */
.bgs-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.bgs-label {
  font-size: 0.8125rem;
  color: var(--text-secondary);
  font-weight: 500;
}

.bgs-input {
  padding: 8px 10px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: 0.875rem;
  transition: border-color var(--transition-fast);
}

.bgs-input:focus {
  outline: none;
  border-color: var(--border-focus);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}

.bgs-select {
  padding: 8px 10px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: 0.875rem;
  transition: border-color var(--transition-fast);
}

.bgs-select:focus {
  outline: none;
  border-color: var(--border-focus);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}

.bgs-slider {
  width: 100%;
  accent-color: var(--primary);
}

/* Toggle / 切换 */
.bgs-toggle-label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-size: 0.875rem;
  color: var(--text-primary);
}

.bgs-toggle-label input[type="checkbox"] {
  accent-color: var(--primary);
  width: 14px;
  height: 14px;
}

/* File actions / 文件操作 */
.bgs-file-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.bgs-import-mode {
  display: flex;
  align-items: center;
  gap: 12px;
}

.bgs-import-mode-label {
  font-size: 0.8125rem;
  color: var(--text-secondary);
  font-weight: 500;
}

.bgs-file-summary {
  font-size: 0.8125rem;
  color: var(--text-primary);
  font-weight: 500;
}

.bgs-file-summary--muted {
  color: var(--text-muted);
  font-style: italic;
}

.bgs-folder-info {
  font-size: 0.8125rem;
  color: var(--accent-secondary, var(--primary));
  font-weight: 500;
}

/* File list / 文件列表 */
.bgs-file-list-wrap {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.bgs-file-list-header {
  padding: 6px 10px;
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border);
}

.bgs-file-list-title {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.bgs-file-list {
  max-height: 180px;
  overflow-y: auto;
}

.bgs-file-list-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 10px;
  cursor: pointer;
  transition: background var(--transition-fast);
  border-bottom: 1px solid var(--border);
}

.bgs-file-list-item:last-child {
  border-bottom: none;
}

.bgs-file-list-item:hover {
  background: var(--bg-hover);
}

.bgs-file-list-item--active {
  background: rgba(59, 130, 246, 0.1);
}

.bgs-file-list-name {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.bgs-file-list-remove {
  border: none;
  background: transparent;
  color: var(--text-muted);
  font-size: 0.75rem;
  cursor: pointer;
  padding: 2px 4px;
  line-height: 1;
  flex-shrink: 0;
}

.bgs-file-list-remove:hover {
  color: var(--error);
}

/* Buttons / 按钮 */
.bgs-btn {
  padding: 8px 16px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: 0.8125rem;
  font-weight: 500;
  cursor: pointer;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.bgs-btn:hover:not(:disabled) {
  border-color: var(--border-hover);
  box-shadow: var(--shadow-sm);
}

.bgs-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.bgs-btn-primary {
  padding: 12px 32px;
  border: none;
  background: var(--primary);
  color: var(--text-inverse);
  font-size: 0.9375rem;
  font-weight: 600;
}

.bgs-btn-primary:hover:not(:disabled) {
  opacity: 0.9;
  box-shadow: none;
}

/* Match table / 匹配表 */
.bgs-match-table-wrap {
  max-height: 200px;
  overflow-y: auto;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
}

.bgs-match-warning {
  padding: 8px 12px;
  background: rgba(245, 158, 11, 0.1);
  border-bottom: 1px solid rgba(245, 158, 11, 0.3);
  color: var(--warning, #d97706);
  font-size: 0.75rem;
  font-weight: 500;
}

.bgs-match-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.75rem;
}

.bgs-match-table th {
  position: sticky;
  top: 0;
  background: var(--bg-surface);
  font-weight: 600;
  text-align: left;
  padding: 6px 8px;
  border-bottom: 1px solid var(--border);
  z-index: 1;
  color: var(--text-secondary);
  white-space: nowrap;
}

.bgs-match-table td {
  padding: 4px 8px;
  border-bottom: 1px solid var(--border);
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: 0.6875rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 140px;
}

.bgs-error-cell {
  color: var(--error);
  font-weight: 500;
}

.bgs-match-table tr:hover td {
  background: var(--bg-hover);
}

/* Preview section / 预览区域 */
.bgs-preview-section {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
}

/* Notice banner / 提示横幅 */
.bgs-notice {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  margin-top: 12px;
  border-radius: var(--radius-md);
  background: rgba(59, 130, 246, 0.08);
  border: 1px solid rgba(59, 130, 246, 0.2);
  color: var(--primary, #3b82f6);
  font-size: 0.8125rem;
  line-height: 1.5;
}

.bgs-notice-icon {
  font-size: 1rem;
  flex-shrink: 0;
}

/* Two-row layout: sample + background side by side / 样品与背景并列 */
.bgs-two-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

/* Thumbnail strip below result / 缩略图在结果下方 */
.bgs-thumb-strip {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: auto;
  background: var(--bg-surface);
  max-height: 320px;
}

.bgs-result-panel-single {
  min-height: 280px;
}

.bgs-panel-file-hint {
  font-weight: 400;
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-left: 8px;
}

/* Individual panel / 单个面板 */
.bgs-panel {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background: var(--bg-surface);
}

.bgs-panel-header {
  padding: 8px 12px;
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border);
}

.bgs-panel-title {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--text-primary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.bgs-panel-image {
  flex: 1;
  min-height: 0;
}

.bgs-panel-stats {
  display: flex;
  gap: 12px;
  padding: 6px 10px;
  border-top: 1px solid var(--border);
  font-size: 0.6875rem;
  font-family: var(--font-mono);
  color: var(--text-secondary);
  background: var(--bg-surface);
  flex-wrap: wrap;
}

/* Preview loading & empty / 预览加载与空状态 */
.bgs-preview-loading {
  padding: 40px 24px;
  text-align: center;
  color: var(--text-muted);
  font-size: 0.9375rem;
}

.bgs-preview-empty {
  padding: 40px 24px;
  text-align: center;
  color: var(--text-muted);
  font-size: 0.9375rem;
}

/* Error / 错误 */
.bgs-error {
  padding: 14px 18px;
  border-radius: var(--radius-md);
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: var(--error);
  font-size: 0.875rem;
}

.bgs-error p {
  margin: 0;
}

/* Empty state / 空状态 */
.bgs-empty {
  padding: 40px 24px;
  text-align: center;
  color: var(--text-muted);
  font-size: 0.9375rem;
}

.bgs-empty p {
  margin: 0;
}

/* Display bar below image / 图像下方显示栏 */
.bgs-display-bar {
  padding: 10px 14px;
}

.bgs-display-row {
  display: flex;
  align-items: flex-end;
  gap: 16px;
  flex-wrap: wrap;
}

.bgs-input-sm {
  width: 100px;
  padding: 4px 8px;
  font-size: 0.8125rem;
}

.bgs-input-tiny {
  width: 60px;
  padding: 2px 6px;
  font-size: 0.6875rem;
  text-align: right;
  flex-shrink: 0;
}

.bgs-radio-label--disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.bgs-radio-label--disabled input[type="radio"] {
  cursor: not-allowed;
}

/* Responsive / 响应式 */
@media (max-width: 1200px) {
  .bgs-two-row {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 960px) {
  .bgs-layout {
    grid-template-columns: 1fr;
  }

  .bgs-two-row {
    grid-template-columns: 1fr;
  }
}
</style>
