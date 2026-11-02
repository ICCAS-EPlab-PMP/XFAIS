<template>
  <section class="trans-page">
    <!-- Header / 页头 -->
    <header class="trans-header">
      <h1>{{ t('transmission.title') }}</h1>
      <p class="trans-subtitle">{{ t('transmission.subtitle') }}</p>
      <div class="trans-notice">
        <span class="trans-notice-icon">ℹ</span>
        <span>{{ t('transmission.notice') }}</span>
      </div>
    </header>

    <div class="trans-layout">
      <!-- ===== Sidebar: controls / 侧边栏：控制面板 ===== -->
      <aside class="trans-sidebar">
        <!-- Files / 文件 -->
        <div class="trans-card">
          <h3 class="trans-card-title">{{ t('transmission.files') }}</h3>

          <div
            class="trans-file-actions"
            :class="{ 'trans-file-actions--drop': fileDrop.isDragging.value }"
            @dragenter="fileDrop.onDragEnter"
            @dragover="fileDrop.onDragOver"
            @dragleave="fileDrop.onDragLeave"
            @drop="fileDrop.onDrop"
          >
            <button
              type="button"
              class="trans-btn"
              data-ai-id="trans:files"
              data-testid="trans-files"
              @click="handleChooseFiles"
            >
              {{ t('transmission.selectFiles') }}
            </button>
            <span v-if="files.length" class="trans-file-summary" data-testid="trans-file-count">
              {{ t('transmission.fileCount', { count: files.length }) }}
            </span>
            <span v-else class="trans-file-summary trans-file-summary--muted">
              {{ t('transmission.noFilesSelected') }}
            </span>
            <span class="trans-file-summary trans-file-summary--muted trans-drop-hint">
              {{ t('business.fileSelection.dropZoneHint') }}
            </span>
          </div>

          <!-- File list (click = preview, star = reference) / 文件列表（点击预览，星标设为参考） -->
          <div v-if="files.length > 0" class="trans-file-list-wrap">
            <div class="trans-file-list-header">
              <span class="trans-file-list-title">{{ t('transmission.fileList') }}</span>
            </div>
            <div class="trans-file-list">
              <div
                v-for="(fp, idx) in files"
                :key="fp"
                class="trans-file-list-item"
                :class="{ 'trans-file-list-item--active': idx === currentIndex }"
                data-testid="trans-file-item"
                @click="currentIndex = idx"
              >
                <button
                  type="button"
                  class="trans-ref-btn"
                  :class="{ 'trans-ref-btn--on': fp === referencePath }"
                  :title="t('transmission.setReference')"
                  :data-ai-id="`trans:ref:${idx}`"
                  data-testid="trans-ref-toggle"
                  @click.stop="referencePath = fp"
                >{{ fp === referencePath ? '★' : '☆' }}</button>
                <span class="trans-file-list-name" :title="fp">{{ extractFileName(fp) }}</span>
                <span v-if="fp === referencePath" class="trans-ref-badge" data-testid="trans-ref-badge">
                  {{ t('transmission.reference') }}
                </span>
                <button
                  type="button"
                  class="trans-file-list-remove"
                  :title="t('transmission.removeFile')"
                  data-testid="trans-file-remove"
                  @click.stop="removeFile(idx)"
                >✕</button>
              </div>
            </div>
          </div>
        </div>

        <!-- Integration region / 积分区域 -->
        <div class="trans-card">
          <h3 class="trans-card-title">{{ t('transmission.region') }}</h3>
          <div class="trans-btn-row">
            <button
              type="button"
              class="trans-btn"
              :class="{ 'trans-btn--armed': regionMode === 'rect' }"
              :disabled="!previewUrl"
              data-ai-id="trans:rect"
              data-testid="trans-region-rect"
              @click="toggleRegionMode('rect')"
            >
              {{ t('transmission.regionRect') }}
            </button>
            <button
              type="button"
              class="trans-btn"
              :class="{ 'trans-btn--armed': regionMode === 'poly' }"
              :disabled="!previewUrl"
              data-ai-id="trans:poly"
              data-testid="trans-region-poly"
              @click="toggleRegionMode('poly')"
            >
              {{ t('transmission.regionPoly') }}
            </button>
          </div>
          <p v-if="regionMode" class="trans-hint">{{ t('transmission.regionArmedHint') }}</p>
          <p class="trans-region-summary" data-testid="trans-region-summary">{{ regionSummary }}</p>
          <button
            type="button"
            class="trans-btn"
            :disabled="!region"
            data-testid="trans-region-clear"
            @click="clearRegion"
          >
            {{ t('transmission.clearRegion') }}
          </button>

          <details class="trans-advanced">
            <summary>{{ t('transmission.advanced') }}</summary>
            <label class="trans-toggle-label">
              <input v-model="subtractBorder" type="checkbox" data-testid="trans-subtract-border" />
              <span>{{ t('transmission.subtractBorder') }}</span>
            </label>
            <p class="trans-hint">{{ t('transmission.subtractBorderHint') }}</p>
          </details>
        </div>

        <!-- Compute / 计算 -->
        <div class="trans-card">
          <h3 class="trans-card-title">{{ t('transmission.compute') }}</h3>
          <button
            type="button"
            class="trans-btn trans-btn-primary"
            :disabled="!canRun"
            data-ai-id="trans:run"
            data-testid="trans-run"
            @click="handleCompute"
          >
            {{ state === 'running' ? t('transmission.computing') : t('transmission.compute') }}
          </button>
          <TaskProgressBar
            v-if="state === 'running'"
            :task-id="taskId"
            :progress="progress"
            :message="progressMessage"
            @cancel="handleCancel"
          />
          <p v-if="state === 'error'" class="trans-error" data-testid="trans-error">
            {{ t('transmission.errorPrefix') }} {{ errorMessage }}
          </p>
        </div>

        <!-- Results / 结果 -->
        <div class="trans-card">
          <h3 class="trans-card-title">{{ t('transmission.results') }}</h3>
          <p v-if="displayRows.length === 0" class="trans-muted" data-testid="trans-results-empty">
            {{ region ? t('transmission.computeFirst') : t('transmission.noResults') }}
          </p>
          <div v-else class="trans-table-wrap">
            <table class="trans-table" data-testid="trans-results-table">
              <thead>
                <tr>
                  <th>{{ t('transmission.colFile') }}</th>
                  <th>{{ t('transmission.colIntensity') }}</th>
                  <th>{{ t('transmission.colTransmission') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="row in displayRows"
                  :key="row.file"
                  :class="{ 'trans-row-failed': row.error }"
                  data-testid="trans-result-row"
                >
                  <td :title="row.file">
                    {{ extractFileName(row.file) }}
                    <span v-if="row.isReference" class="trans-ref-badge">{{ t('transmission.refBadge') }}</span>
                  </td>
                  <td v-if="row.error" :title="`${t('transmission.failedRow')}: ${row.error}`" class="trans-error-cell">
                    {{ t('transmission.failedRow') }}
                  </td>
                  <td v-else>{{ formatSci(row.intensity) }}</td>
                  <td>{{ row.error ? '—' : formatPercent(row.transmission) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Export / 导出 -->
        <div class="trans-card">
          <h3 class="trans-card-title">{{ t('transmission.export') }}</h3>
          <!-- Web mode cannot browse server folders: files auto-download. -->
          <div v-if="!transport.isDesktop()" class="trans-warning">
            {{ t('transmission.webExportNote') }}
          </div>
          <FileDialogButton
            v-else
            v-model="outputDir"
            mode="openFolder"
            :label="t('transmission.outputDir')"
          />
          <div class="trans-btn-row">
            <button
              type="button"
              class="trans-btn"
              :disabled="!hasResults || exporting"
              data-ai-id="trans:export-csv"
              data-testid="trans-export-csv"
              @click="handleExport('csv')"
            >
              {{ t('transmission.exportCsv') }}
            </button>
            <button
              type="button"
              class="trans-btn"
              :disabled="!hasResults || exporting"
              data-ai-id="trans:export-json"
              data-testid="trans-export-json"
              @click="handleExport('json')"
            >
              {{ t('transmission.exportJson') }}
            </button>
          </div>
        </div>
      </aside>

      <!-- ===== Main area: preview canvas / 主区域：预览画布 ===== -->
      <main class="trans-main">
        <div class="trans-panel">
          <div class="trans-panel-header">
            <span class="trans-panel-title">{{ t('transmission.title') }}</span>
            <span v-if="currentFile" class="trans-panel-file-hint">{{ extractFileName(currentFile) }}</span>
          </div>

          <div v-if="previewLoading" class="trans-preview-loading">
            {{ t('transmission.loading') }}
          </div>
          <div v-else-if="previewUrl" class="trans-canvas-wrap" data-testid="trans-canvas">
            <CalibCanvas
              :image-src="previewUrl"
              :image-width="imageWidth"
              :image-height="imageHeight"
              :rings="canvasRings"
              :peaks="canvasPeaks"
              :interactive="false"
              :region-mode="regionMode"
              :com-region="region"
              :hint="regionMode ? t('transmission.regionArmedHint') : ''"
              @region-selected="onRegionSelected"
            />
          </div>
          <div v-else-if="currentFile" class="trans-preview-empty">
            {{ t('transmission.noPreview') }}
          </div>
          <div v-else class="trans-preview-empty" data-testid="trans-empty-state">
            {{ t('transmission.emptyState') }}
          </div>

          <div v-if="previewStats" class="trans-panel-stats" data-testid="trans-stats">
            <span>Min: {{ formatSci(previewStats.min) }}</span>
            <span>Max: {{ formatSci(previewStats.max) }}</span>
            <span>Mean: {{ formatSci(previewStats.mean) }}</span>
          </div>
        </div>

        <!-- Thumbnail strip: visual file switching / 缩略图条：可视化切换文件 -->
        <div
          v-if="files.length > 1 && (thumbnailItems.length > 0 || thumbnailsLoading)"
          class="trans-thumb-strip"
          data-testid="trans-thumb-strip"
        >
          <ThumbnailStrip
            :items="thumbnailItems"
            :selected-index="currentIndex"
            :current-page="1"
            :total-pages="1"
            :page-size="100"
            :loading="thumbnailsLoading"
            :sync-with-main="false"
            :columns-per-row="6"
            @select="onThumbnailSelect"
          />
        </div>

        <!-- Display settings / 显示设置 -->
        <div class="trans-card trans-display-bar">
          <div class="trans-display-row">
            <div class="trans-field" style="min-width:140px">
              <label class="trans-label">{{ t('bgSubtract.colormap') }}</label>
              <select v-model="colormap" class="trans-select" data-testid="trans-colormap">
                <option v-for="cm in colormapOptions" :key="cm" :value="cm">{{ cm }}</option>
              </select>
            </div>
            <label class="trans-toggle-label">
              <input v-model="useLog" type="checkbox" data-testid="trans-log-scale" />
              <span>{{ t('bgSubtract.logScale') }}</span>
            </label>
          </div>
        </div>
      </main>
    </div>
  </section>
</template>

<script setup lang="ts">
/**
 * TransmissionView.vue — 直通光透过率测量页面
 * Direct-beam transmission measurement: pick a region on the image (rect /
 * polygon), integrate every listed image inside it, use one file (usually the
 * direct beam) as the reference, then T = I / I_ref; export CSV / JSON for the
 * background-subtraction page.
 * 直通光透过率测量：在图上圈出积分区域（方形框 / 多折框），逐个积分全部文件，
 * 指定一个参考文件（通常为直通光图），T = I / I_ref；导出 CSV / JSON 供背景
 * 扣除页面按文件名匹配。
 *
 * Backend contract (snake_case, same style as bg_subtract — no task-adapter
 * normalization):
 *   {action:'preview', file_path, cmap?, use_log?, clim_min?, clim_max?}
 *     → binary PNG frame + {width, height, stats}
 *   {action:'integrate', files, region, subtract_border?, reference?}
 *     → {rows:[{file,intensity,pixel_count,mean,transmission?}], failed:[{file,error}]}
 *   {action:'export', rows, format:'csv'|'json', output_dir?}
 *     → {output_files, output_dir}
 *   {action:'scan_folder', folder} → {files, count}
 */
import { ref, computed, watch, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useToast } from '@/lib/toast'
import { useTransport } from '@/lib/transport'
import { clearWorkspace, reportWorkspace } from '@/lib/workspace-state'
import type { TaskBinaryPayload } from '@/lib/transport'
import { createImportDropZone, extensionsFromFilters } from '@/lib/fileDrop'
import { COLORMAP_PRESETS } from '@/lib/chart-utils'

import CalibCanvas from '@/components/calibration/CalibCanvas.vue'
import type { CalibPeak, CalibRegion, CalibRing } from '@/components/calibration/CalibCanvas.vue'
import FileDialogButton from '@/components/business/FileDialogButton.vue'
import TaskProgressBar from '@/components/business/TaskProgressBar.vue'
import ThumbnailStrip from '@/components/business/ThumbnailStrip.vue'
import type { ThumbnailItem } from '@/components/business/ThumbnailStrip.vue'

// === Type definitions / 类型定义 ===

interface PreviewStats {
  min: number
  max: number
  mean: number
}

/** One integrated file as returned by the backend / 后端返回的逐文件积分行。 */
interface IntegrateRow {
  file: string
  intensity?: number
  pixel_count?: number
  mean?: number
  transmission?: number
}

interface IntegrateFailure {
  file: string
  error: string
}

/** Row as displayed in the result table (merged with the file-list order). */
interface DisplayRow {
  file: string
  intensity: number | null
  transmission: number | null
  error: string | null
  isReference: boolean
}

type PageState = 'idle' | 'running' | 'done' | 'error'
type RegionMode = 'rect' | 'poly'

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

// === File selection / 文件选择 ===

const files = ref<string[]>([])
const currentIndex = ref(0)
const referencePath = ref<string | null>(null)

const dataFileFilters = [
  { name: 'Detector Images', extensions: ['edf', 'tif', 'tiff', 'h5', 'hdf5'] },
]

const currentFile = computed<string | null>(() => files.value[currentIndex.value] ?? null)

// === Region / 积分区域 ===

const regionMode = ref<RegionMode | null>(null)
const region = ref<CalibRegion | null>(null)
const subtractBorder = ref(false)

// CalibCanvas requires these props; this page has no rings/peaks.
// CalibCanvas 必填属性；本页面没有环/峰。常量引用避免每次渲染触发叠加层重绘。
const canvasRings: CalibRing[] = []
const canvasPeaks: CalibPeak[] = []

// === Preview / 预览 ===

const previewUrl = ref<string | null>(null)
const previewStats = ref<PreviewStats | null>(null)

// === Thumbnails / 缩略图条（多文件可视切换，镜像背景扣除页） ===

const thumbnailItems = ref<ThumbnailItem[]>([])
const thumbnailsLoading = ref(false)
/** Token guard: a file-list change mid-loop discards the stale batch. */
/** 竞态令牌：循环中文件列表再变时丢弃过期批次。 */
let thumbnailToken = 0
const previewLoading = ref(false)
const imageWidth = ref(0)
const imageHeight = ref(0)

const colormap = ref('smooth_WAXS_foxtrot')
const useLog = ref(false)

// === Task state / 任务状态 ===

const state = ref<PageState>('idle')
const taskId = ref<string | null>(null)
const progress = ref(0)
const progressMessage = ref<string | null>(null)
const errorMessage = ref('')

// === Results / 结果 ===

const integrateRows = ref<IntegrateRow[]>([])
const integrateFailed = ref<IntegrateFailure[]>([])
const hasResults = ref(false)

// === Export / 导出 ===

const outputDir = ref<string | null>(null)
const exporting = ref(false)

// === Cleanup handles / 清理句柄 ===

let unsubPreviewBinary: (() => void) | null = null
let unsubPreviewResult: (() => void) | null = null
let unsubPreviewError: (() => void) | null = null
let previewToken = 0
let computeToken = 0
let cleanupProgress: (() => void) | null = null
let cleanupResult: (() => void) | null = null
let cleanupError: (() => void) | null = null

// === Computed / 计算属性 ===

const canRun = computed(() =>
  files.value.length > 0
  && referencePath.value != null
  && region.value != null
  && state.value !== 'running'
)

const regionSummary = computed<string>(() => {
  const r = region.value
  if (!r) return t('transmission.regionNone')
  if (r.kind === 'rect') {
    // Localized row/column phrasing (visual review 2026-10-25: the raw
    // "y a–b, x c–d" read as untranslated debug text in the zh UI).
    // 行/列措辞本地化（视觉审查 2026-10-25：裸 "y a–b, x c–d" 在中文界面
    // 里像未翻译的调试串）。
    return `${t('transmission.regionRect')} · ${t('transmission.regionRectRange', {
      y0: Math.round(r.y0),
      y1: Math.round(r.y1),
      x0: Math.round(r.x0),
      x1: Math.round(r.x1),
    })}`
  }
  return `${t('transmission.regionPoly')} · ${t('transmission.vertexCount', { count: r.points.length })}`
})

/** Result rows in FILE LIST ORDER, merged with backend rows / failures. */
const displayRows = computed<DisplayRow[]>(() => {
  if (!hasResults.value) return []
  const rowByFile = new Map<string, IntegrateRow>()
  const rowByBase = new Map<string, IntegrateRow>()
  for (const r of integrateRows.value) {
    rowByFile.set(r.file, r)
    rowByBase.set(baseName(r.file).toLowerCase(), r)
  }
  const failByFile = new Map<string, IntegrateFailure>()
  const failByBase = new Map<string, IntegrateFailure>()
  for (const f of integrateFailed.value) {
    failByFile.set(f.file, f)
    failByBase.set(baseName(f.file).toLowerCase(), f)
  }

  const consumed = new Set<string>()
  const out: DisplayRow[] = []
  for (const fp of files.value) {
    const base = baseName(fp).toLowerCase()
    const row = rowByFile.get(fp) ?? rowByBase.get(base)
    const fail = failByFile.get(fp) ?? failByBase.get(base)
    if (row) {
      consumed.add(row.file)
      out.push({
        file: fp,
        intensity: finiteOrNull(row.intensity),
        transmission: fp === referencePath.value ? 1 : finiteOrNull(row.transmission),
        error: null,
        isReference: fp === referencePath.value,
      })
    } else if (fail) {
      out.push({
        file: fp,
        intensity: null,
        transmission: null,
        error: fail.error || t('transmission.failedRow'),
        isReference: fp === referencePath.value,
      })
    } else {
      out.push({
        file: fp,
        intensity: null,
        transmission: null,
        error: null,
        isReference: fp === referencePath.value,
      })
    }
  }
  // Any backend row whose path was not in the list: append so nothing is lost.
  for (const r of integrateRows.value) {
    if (consumed.has(r.file)) continue
    if (files.value.includes(r.file)) continue
    out.push({
      file: r.file,
      intensity: finiteOrNull(r.intensity),
      transmission: finiteOrNull(r.transmission),
      error: null,
      isReference: false,
    })
  }
  return out
})

// === Workspace-state bridge / 工作区状态上报 ===

watch(
  [files, region, referencePath, state, canRun],
  () => {
    reportWorkspace('transmission', {
      filesCount: files.value.length,
      hasPoni: false,
      canRun: canRun.value,
      phase: state.value,
      extras: {
        hasRegion: region.value != null,
        hasReference: referencePath.value != null,
      },
    })
  },
  { immediate: true, deep: true }
)
onUnmounted(() => clearWorkspace('transmission'))

// === Invalidations / 失效 ===

/**
 * Any input change invalidates the displayed results; a run in flight is
 * cancelled because its answer would describe the OLD inputs.
 * 任何输入变化都会让已显示的结果失效；在途计算一并取消——它的结果对应旧输入。
 */
function invalidateResults(): void {
  integrateRows.value = []
  integrateFailed.value = []
  hasResults.value = false
  errorMessage.value = ''
  if (state.value === 'running') {
    void handleCancel()
  } else if (state.value === 'error') {
    state.value = 'idle'
  }
}

watch([files, region, referencePath, subtractBorder], invalidateResults, { deep: true })

// === File handling / 文件处理 ===

function baseName(filePath: string): string {
  const sep = filePath.includes('/') ? '/' : '\\'
  const parts = filePath.split(sep)
  return parts[parts.length - 1] || filePath
}

const extractFileName = baseName

function formatSci(value: number | null): string {
  if (value == null || !Number.isFinite(value)) return '—'
  if (value === 0) return '0'
  return value.toExponential(3)
}

function formatPercent(value: number | null): string {
  if (value == null || !Number.isFinite(value)) return '—'
  return `${(value * 100).toFixed(2)}%`
}

function finiteOrNull(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

/** Append selected/dropped paths (deduplicated) and repair the reference. */
function applyFilePaths(paths: string[]): void {
  const existing = new Set(files.value)
  const next = [...files.value]
  for (const p of paths) {
    if (p && !existing.has(p)) {
      existing.add(p)
      next.push(p)
    }
  }
  if (next.length === files.value.length) return
  files.value = next
  if (!referencePath.value || !next.includes(referencePath.value)) {
    referencePath.value = next[0] ?? null
  }
  if (currentIndex.value >= next.length) currentIndex.value = Math.max(0, next.length - 1)
}

async function handleChooseFiles(): Promise<void> {
  const result = await transport.selectFiles({
    filters: dataFileFilters,
    multiSelections: true,
  })
  if (!result) return
  applyFilePaths(Array.isArray(result) ? result : [result])
}

function removeFile(index: number): void {
  const removed = files.value[index]
  files.value = files.value.filter((_, i) => i !== index)
  if (removed && referencePath.value === removed) {
    referencePath.value = files.value[0] ?? null
  }
  if (currentIndex.value >= files.value.length) {
    currentIndex.value = Math.max(0, files.value.length - 1)
  }
}

// Drag & drop mirrors the select-files button; a dropped folder is scanned
// through the backend's scan_folder action (desktop only).
// 拖放与选择按钮等价；拖入文件夹时经后端 scan_folder 展开（仅桌面）。
const fileDrop = createImportDropZone({
  transport,
  extensions: () => extensionsFromFilters(dataFileFilters),
  onFiles: (paths) => applyFilePaths(paths),
  onFolder: (folder) => { void scanFolderAndAppend(folder) },
})

async function scanFolderAndAppend(folder: string): Promise<void> {
  try {
    const response = await transport.submitTask('transmission', {
      action: 'scan_folder',
      folder,
    })
    const unsubResult = transport.onTaskResult(response.taskId, (payload) => {
      const data = payload.data as { files?: string[] }
      if (Array.isArray(data.files) && data.files.length > 0) {
        applyFilePaths(data.files)
      }
      unsubResult()
      unsubError()
    })
    const unsubError = transport.onTaskError(response.taskId, (payload) => {
      toast.push({
        title: t('transmission.errorTitle'),
        message: payload.error,
        tone: 'error',
      })
      unsubResult()
      unsubError()
    })
  } catch (err) {
    toast.push({
      title: t('transmission.errorTitle'),
      message: err instanceof Error ? err.message : String(err),
      tone: 'error',
    })
  }
}

// === Preview / 预览 ===

function revokePreviewUrl(): void {
  if (previewUrl.value?.startsWith('blob:')) URL.revokeObjectURL(previewUrl.value)
  previewUrl.value = null
}

// === Thumbnails / 缩略图生成 ===

/**
 * Render one small preview per listed file (same backend 'preview' action the
 * main canvas uses) so multi-file sessions can be switched visually — mirrors
 * BgSubtractView's strip. Single-file lists show no strip (the sidebar list
 * would be a duplicate). A token discards batches whose file list changed
 * mid-loop.
 * 为每个已列文件渲染一张小预览（与主画布同一 preview 动作），多文件会话可
 * 视化切换——镜像背景扣除页的缩略图条。单文件不显示（与侧栏列表重复）。
 * 令牌丢弃循环中途文件列表已变化的过期批次。
 */
async function generateThumbnails(): Promise<void> {
  const paths = [...files.value]
  if (paths.length <= 1) {
    thumbnailToken++
    thumbnailItems.value = []
    thumbnailsLoading.value = false
    return
  }

  const token = ++thumbnailToken
  thumbnailsLoading.value = true
  const items: ThumbnailItem[] = []

  for (let i = 0; i < paths.length; i++) {
    if (token !== thumbnailToken) return  // superseded / 已被更新批次取代
    const path = paths[i]
    try {
      const b64 = await new Promise<string>((resolve, reject) => {
        transport.submitTask('transmission', {
          action: 'preview',
          file_path: path,
          cmap: colormap.value,
          use_log: useLog.value,
        }).then((response) => {
          let b64Data = ''
          const unsubBinary = transport.onTaskBinaryData(response.taskId, (payload: TaskBinaryPayload) => {
            if (!payload.data) return
            const bytes = new Uint8Array(payload.data)
            let binary = ''
            for (let j = 0; j < bytes.byteLength; j++) {
              binary += String.fromCharCode(bytes[j])
            }
            b64Data = btoa(binary)
          })
          const unsubResult = transport.onTaskResult(response.taskId, () => {
            unsubBinary()
            unsubResult()
            unsubError()
            resolve(b64Data)
          })
          const unsubError = transport.onTaskError(response.taskId, (p) => {
            unsubBinary()
            unsubResult()
            unsubError()
            reject(new Error(p.error))
          })
        }).catch(reject)
      })
      if (token !== thumbnailToken) return
      items.push({ index: i, b64: b64 || '', label: baseName(path) })
    } catch {
      if (token !== thumbnailToken) return
      items.push({ index: i, b64: '', label: baseName(path) })
    }
  }

  if (token !== thumbnailToken) return
  thumbnailItems.value = items
  thumbnailsLoading.value = false
}

/** Thumbnail click → switch the main canvas file (watcher reloads preview). */
/** 缩略图点击 → 切换主画布文件（既有 watcher 重载预览）。 */
function onThumbnailSelect(index: number): void {
  currentIndex.value = index
}

// Regenerate whenever the file list grows or shrinks (imports, drops, folder
// scans, removals). Length-only: there is no reordering UI.
// 文件列表增删（导入/拖放/文件夹/移除）时重新生成。仅监听长度：没有重排 UI。
watch(() => files.value.length, () => {
  void generateThumbnails()
})

function cleanupPreviewListeners(): void {
  unsubPreviewBinary?.()
  unsubPreviewBinary = null
  cleanupPreviewSettled()
}

/** Result/error unsubs only — the PNG frame may arrive AFTER the result.
 *  仅注销结果/错误监听——PNG 二进制帧可能晚于结果到达。 */
function cleanupPreviewSettled(): void {
  unsubPreviewResult?.()
  unsubPreviewResult = null
  unsubPreviewError?.()
  unsubPreviewError = null
}

/**
 * Load the preview PNG for one file. Only the LATEST request is consumed —
 * a stale binary/result/error callback is ignored (file switching + colormap
 * changes can overlap).
 * 加载某个文件的预览 PNG。只消费最新一次请求——过期的二进制/结果/错误回调
 * 直接忽略（切换文件与色图变化可能重叠）。
 */
async function loadPreview(filePath: string): Promise<void> {
  const token = ++previewToken
  cleanupPreviewListeners()
  previewLoading.value = true
  previewStats.value = null
  imageWidth.value = 0
  imageHeight.value = 0
  revokePreviewUrl()

  const params: Record<string, unknown> = {
    action: 'preview',
    file_path: filePath,
    cmap: colormap.value,
    use_log: useLog.value,
  }

  try {
    const response = await transport.submitTask('transmission', params)
    if (token !== previewToken) return

    unsubPreviewBinary = transport.onTaskBinaryData(response.taskId, (payload: TaskBinaryPayload) => {
      if (token !== previewToken) return
      if (!payload.data) return
      revokePreviewUrl()
      const blob = new Blob([payload.data], { type: payload.mime || 'image/png' })
      previewUrl.value = URL.createObjectURL(blob)
      previewLoading.value = false
    })

    unsubPreviewResult = transport.onTaskResult(response.taskId, (payload) => {
      if (token !== previewToken) return
      // Binary-path results carry the ORIGINAL frame dims as origWidth/
      // origHeight (the established convention — CalibrationView reads the
      // same fields; the server's binary header width/height feeds the
      // fallback). Top-level width/height only exist on non-binary payloads.
      // 二进制路径的结果以 origWidth/origHeight 携带原始帧尺寸（既有惯例，
      // CalibrationView 同源；服务端 binary 头的 width/height 落入兜底）。
      // 顶层 width/height 仅存在于非二进制载荷。
      const data = (payload.data ?? {}) as {
        width?: number
        height?: number
        origWidth?: number
        origHeight?: number
        stats?: PreviewStats
      }
      const w = finiteOrNull(data.origWidth) ?? finiteOrNull(data.width)
      const h = finiteOrNull(data.origHeight) ?? finiteOrNull(data.height)
      if (w != null && w > 0) imageWidth.value = w
      if (h != null && h > 0) imageHeight.value = h
      if (data.stats) previewStats.value = data.stats
      previewLoading.value = false
      cleanupPreviewSettled()
    })

    unsubPreviewError = transport.onTaskError(response.taskId, (payload) => {
      if (token !== previewToken) return
      previewLoading.value = false
      toast.push({
        title: t('transmission.errorTitle'),
        message: payload.error,
        tone: 'error',
      })
      cleanupPreviewSettled()
    })
  } catch (err) {
    if (token !== previewToken) return
    previewLoading.value = false
    toast.push({
      title: t('transmission.errorTitle'),
      message: err instanceof Error ? err.message : String(err),
      tone: 'error',
    })
  }
}

// Current file change → new preview / 当前文件变化 → 重新预览
watch(currentFile, (fp) => {
  if (fp) {
    void loadPreview(fp)
  } else {
    previewToken += 1
    cleanupPreviewListeners()
    previewLoading.value = false
    previewStats.value = null
    imageWidth.value = 0
    imageHeight.value = 0
    revokePreviewUrl()
  }
})

// Display settings change → re-render the same file (region/results untouched).
// 显示设置变化 → 重渲染同一文件（区域/结果不受影响）。
watch([colormap, useLog], () => {
  const fp = currentFile.value
  if (fp) void loadPreview(fp)
})

// === Region selection / 区域选择 ===

function toggleRegionMode(mode: RegionMode): void {
  if (!previewUrl.value) return
  regionMode.value = regionMode.value === mode ? null : mode
}

/** Region confirmed on the canvas → disarm, echo, remember (plain object). */
function onRegionSelected(selected: CalibRegion): void {
  if (selected.kind === 'rect') {
    region.value = {
      kind: 'rect',
      y0: Math.min(selected.y0, selected.y1),
      y1: Math.max(selected.y0, selected.y1),
      x0: Math.min(selected.x0, selected.x1),
      x1: Math.max(selected.x0, selected.x1),
    }
  } else {
    region.value = {
      kind: 'poly',
      points: selected.points.map(p => ({ y: p.y, x: p.x })),
    }
  }
  regionMode.value = null
  toast.push({
    title: t('transmission.region'),
    message: t('transmission.regionSet'),
    tone: 'success',
  })
}

function clearRegion(): void {
  region.value = null
  regionMode.value = null
  toast.push({
    title: t('transmission.region'),
    message: t('transmission.regionCleared'),
    tone: 'info',
  })
}

/** Plain-clone the region — Vue proxies cannot cross Electron's IPC clone. */
function plainRegion(): CalibRegion | null {
  const r = region.value
  if (!r) return null
  return r.kind === 'rect'
    ? { kind: 'rect', y0: r.y0, y1: r.y1, x0: r.x0, x1: r.x1 }
    : { kind: 'poly', points: r.points.map(p => ({ y: p.y, x: p.x })) }
}

// === Compute / 计算 ===

async function handleCompute(): Promise<void> {
  if (!canRun.value) return
  const regionPayload = plainRegion()
  const reference = referencePath.value
  if (!regionPayload || !reference) return

  const token = ++computeToken
  invalidateResults()
  state.value = 'running'
  progress.value = 0
  progressMessage.value = null
  errorMessage.value = ''

  try {
    const response = await transport.submitTask('transmission', {
      action: 'integrate',
      // Spread reactive arrays/objects → plain structures for the IPC clone.
      // 展开响应式数组/对象为普通结构，避免 IPC 结构化克隆失败。
      files: [...files.value],
      region: regionPayload,
      subtract_border: subtractBorder.value,
      reference,
    })
    taskId.value = response.taskId

    cleanupProgress = transport.onTaskProgress(response.taskId, (payload) => {
      if (token !== computeToken) return
      progress.value = payload.progress
      progressMessage.value = payload.message ?? null
    })

    cleanupResult = transport.onTaskResult(response.taskId, (payload) => {
      if (token !== computeToken) return
      const data = (payload.data ?? {}) as {
        rows?: IntegrateRow[]
        failed?: IntegrateFailure[]
      }
      integrateRows.value = Array.isArray(data.rows) ? data.rows : []
      integrateFailed.value = Array.isArray(data.failed) ? data.failed : []
      hasResults.value = true
      taskId.value = null
      state.value = 'done'
      progress.value = 1
      const success = integrateRows.value.length
      const failed = integrateFailed.value.length
      toast.push({
        title: t('transmission.compute'),
        message: t('transmission.computeDone', { success, failed }),
        tone: failed > 0 ? 'warning' : 'success',
      })
      cleanupTaskListeners()
    })

    cleanupError = transport.onTaskError(response.taskId, (payload) => {
      if (token !== computeToken) return
      taskId.value = null
      errorMessage.value = payload.error
      state.value = 'error'
      toast.push({
        title: t('transmission.errorTitle'),
        message: payload.error,
        tone: 'error',
      })
      cleanupTaskListeners()
    })
  } catch (err) {
    if (token !== computeToken) return
    taskId.value = null
    errorMessage.value = err instanceof Error ? err.message : String(err)
    state.value = 'error'
    toast.push({
      title: t('transmission.errorTitle'),
      message: errorMessage.value,
      tone: 'error',
    })
  }
}

function cleanupTaskListeners(): void {
  cleanupProgress?.()
  cleanupProgress = null
  cleanupResult?.()
  cleanupResult = null
  cleanupError?.()
  cleanupError = null
}

async function handleCancel(): Promise<void> {
  const tid = taskId.value
  computeToken += 1
  taskId.value = null
  state.value = 'idle'
  progress.value = 0
  progressMessage.value = null
  cleanupTaskListeners()
  if (tid) {
    try { await transport.cancelTask(tid) } catch { /* already finished */ }
  }
}

// === Export / 导出 ===

async function handleExport(format: 'csv' | 'json'): Promise<void> {
  if (!hasResults.value || exporting.value) return
  exporting.value = true
  const rows = integrateRows.value.map(r => ({
    file: r.file,
    intensity: r.intensity,
    transmission: r.transmission,
  }))

  try {
    const response = await transport.submitTask('transmission', {
      action: 'export',
      rows,
      format,
      output_dir: outputDir.value ?? undefined,
    })

    const unsubResult = transport.onTaskResult(response.taskId, (payload) => {
      const data = (payload.data ?? {}) as {
        output_files?: string[]
        output_dir?: string
      }
      const outputFiles = Array.isArray(data.output_files) ? data.output_files : []
      if (transport.isDesktop()) {
        toast.push({
          title: t('transmission.export'),
          message: t('transmission.exportDone', {
            dir: data.output_dir ?? outputDir.value ?? '',
          }),
          tone: 'success',
        })
      } else {
        // Web mode: the browser cannot browse server folders — download.
        for (const serverPath of outputFiles) {
          transport.downloadFile(serverPath, extractFileName(serverPath)).catch(() => {
            toast.push({
              title: t('transmission.errorTitle'),
              message: `${extractFileName(serverPath)}: download failed`,
              tone: 'error',
            })
          })
        }
        toast.push({
          title: t('transmission.export'),
          message: t('bgSubtract.exportedDownload', { count: outputFiles.length }),
          tone: 'success',
        })
      }
      exporting.value = false
      unsubResult()
      unsubError()
    })

    const unsubError = transport.onTaskError(response.taskId, (payload) => {
      exporting.value = false
      toast.push({
        title: t('transmission.errorTitle'),
        message: payload.error,
        tone: 'error',
      })
      unsubResult()
      unsubError()
    })
  } catch (err) {
    exporting.value = false
    toast.push({
      title: t('transmission.errorTitle'),
      message: err instanceof Error ? err.message : String(err),
      tone: 'error',
    })
  }
}

// === Cleanup / 清理 ===

// AI assistant option application (llm build only; inert in the main build —
// nothing dispatches the event there and no AI module is imported here).
// Applies the assistant-decided region shape / border mode ONLY while a
// preview is loaded (the region buttons are gated on it); values come from
// decideOptionsViaRules's transmission vocabulary.
// AI 助手选项应用（仅 llm 构建；主线构建无人派发此事件，此处也不导入任何
// AI 模块）。仅在预览已加载时应用助手判定的区域形状/扣背景模式（区域按钮
// 以此为门槛）；取值来自 decideOptionsViaRules 的 transmission 词汇表。
function onAiApplyOptions(event: Event): void {
  const detail = (event as CustomEvent).detail as
    | { routeName?: string; options?: Record<string, unknown> }
    | undefined
  if (detail?.routeName !== 'transmission') return
  if (!previewUrl.value) return
  const shape = detail.options?.shape
  if (shape === 'rect' || shape === 'poly') {
    regionMode.value = shape
  }
  if (detail.options?.subtractBorder === 'on') {
    subtractBorder.value = true
  }
}

window.addEventListener('xfaos:ai-apply-options', onAiApplyOptions)

onUnmounted(() => {
  window.removeEventListener('xfaos:ai-apply-options', onAiApplyOptions)
  previewToken += 1
  computeToken += 1
  cleanupPreviewListeners()
  cleanupTaskListeners()
  revokePreviewUrl()
})
</script>

<style scoped>
.trans-page {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.trans-header {
  padding-bottom: 8px;
}

.trans-header h1 {
  font-size: 1.5rem;
  font-weight: 700;
  margin: 0 0 6px;
  color: var(--text-primary);
}

.trans-subtitle {
  font-size: 0.9375rem;
  color: var(--text-secondary);
  margin: 0;
}

.trans-layout {
  display: grid;
  grid-template-columns: minmax(300px, 400px) minmax(0, 1fr);
  gap: 24px;
  align-items: start;
}

/* Sidebar / 侧边栏 */
.trans-sidebar {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* Card / 卡片 */
.trans-card {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  background: var(--bg-surface);
}

.trans-card-title {
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

/* Main area / 主区域 */
.trans-main {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
}

/* Panel / 面板 */
.trans-panel {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background: var(--bg-surface);
}

.trans-panel-header {
  padding: 8px 12px;
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border);
}

.trans-panel-title {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--text-primary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.trans-panel-file-hint {
  font-weight: 400;
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-left: 8px;
}

/* Thumbnail strip below the canvas (mirror of the bg-subtract strip).
 * 画布下方缩略图条（与背景扣除页同款）。 */
.trans-thumb-strip {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: auto;
  background: var(--bg-surface);
  max-height: 320px;
}

.trans-canvas-wrap {
  position: relative;
  height: clamp(420px, calc(100vh - 320px), 760px);
  min-height: 420px;
}

.trans-canvas-wrap :deep(.calib-canvas) {
  height: 100%;
}

.trans-panel-stats {
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

.trans-preview-loading,
.trans-preview-empty {
  padding: 48px 24px;
  text-align: center;
  color: var(--text-muted);
  font-size: 0.9375rem;
}

/* Notice banner / 提示横幅 */
.trans-notice {
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

.trans-notice-icon {
  font-size: 1rem;
  flex-shrink: 0;
}

/* File actions / 文件操作 */
.trans-file-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  border-radius: var(--radius-md);
  padding: 2px;
  transition: background var(--transition-fast), box-shadow var(--transition-fast);
}

.trans-file-actions--drop {
  background: var(--primary-bg);
  box-shadow: 0 0 0 2px var(--primary-light);
}

.trans-drop-hint {
  font-size: 0.75rem;
  /* --text-muted measured ~2.56:1 on white (visual review 2026-10-25);
   * slate-500 clears the 4.5:1 text bar. Same fix as BgSubtractView.
   * 继承的 --text-muted 白底实测约 2.56:1（视觉审查 2026-10-25）；
   * slate-500 达到 4.5:1 文本线。与背景扣除页同步修。 */
  color: #64748b;
}

.trans-file-summary {
  font-size: 0.8125rem;
  color: var(--text-primary);
  font-weight: 500;
}

.trans-file-summary--muted {
  color: var(--text-muted);
  font-style: italic;
}

/* File list / 文件列表 */
.trans-file-list-wrap {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.trans-file-list-header {
  padding: 6px 10px;
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border);
}

.trans-file-list-title {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.trans-file-list {
  max-height: 200px;
  overflow-y: auto;
}

.trans-file-list-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  cursor: pointer;
  transition: background var(--transition-fast);
  border-bottom: 1px solid var(--border);
}

.trans-file-list-item:last-child {
  border-bottom: none;
}

.trans-file-list-item:hover {
  background: var(--bg-hover);
}

.trans-file-list-item--active {
  background: rgba(59, 130, 246, 0.1);
}

.trans-file-list-name {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.trans-ref-btn {
  border: none;
  background: transparent;
  color: var(--text-muted);
  font-size: 0.875rem;
  cursor: pointer;
  padding: 0 2px;
  line-height: 1;
  flex-shrink: 0;
}

.trans-ref-btn:hover {
  color: var(--primary);
}

.trans-ref-btn--on {
  color: var(--primary);
}

.trans-ref-badge {
  font-size: 0.625rem;
  font-weight: 600;
  color: var(--primary);
  border: 1px solid var(--primary-light);
  border-radius: 999px;
  padding: 0 6px;
  flex-shrink: 0;
  white-space: nowrap;
}

.trans-file-list-remove {
  border: none;
  background: transparent;
  color: var(--text-muted);
  font-size: 0.75rem;
  cursor: pointer;
  padding: 2px 4px;
  line-height: 1;
  flex-shrink: 0;
}

.trans-file-list-remove:hover {
  color: var(--error);
}

/* Buttons / 按钮 */
.trans-btn {
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

.trans-btn:hover:not(:disabled) {
  border-color: var(--border-hover);
  box-shadow: var(--shadow-sm);
}

.trans-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.trans-btn--armed {
  border-color: var(--primary);
  color: var(--primary);
  background: var(--primary-bg);
  font-weight: 600;
}

.trans-btn-primary {
  padding: 12px 32px;
  border: none;
  background: var(--primary);
  color: var(--text-inverse);
  font-size: 0.9375rem;
  font-weight: 600;
}

.trans-btn-primary:hover:not(:disabled) {
  opacity: 0.9;
  box-shadow: none;
}

.trans-btn-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

/* Fields / 字段 */
.trans-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.trans-label {
  font-size: 0.8125rem;
  color: var(--text-secondary);
  font-weight: 500;
}

.trans-select {
  padding: 8px 10px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: 0.875rem;
}

.trans-select:focus {
  outline: none;
  border-color: var(--border-focus);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}

.trans-toggle-label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-size: 0.8125rem;
  color: var(--text-primary);
}

.trans-toggle-label input[type="checkbox"] {
  accent-color: var(--primary);
  width: 14px;
  height: 14px;
}

.trans-display-bar {
  padding: 10px 14px;
}

.trans-display-row {
  display: flex;
  align-items: flex-end;
  gap: 16px;
  flex-wrap: wrap;
}

/* Hints / 提示 */
.trans-hint {
  font-size: 0.75rem;
  color: var(--text-secondary);
  line-height: 1.5;
  margin: 0;
}

.trans-muted {
  font-size: 0.8125rem;
  color: var(--text-muted);
  font-style: italic;
  margin: 0;
}

.trans-region-summary {
  font-size: 0.8125rem;
  font-family: var(--font-mono);
  color: var(--text-primary);
  margin: 0;
}

.trans-warning {
  padding: 8px 12px;
  border-radius: var(--radius-md);
  background: rgba(245, 158, 11, 0.1);
  border: 1px solid rgba(245, 158, 11, 0.3);
  /* amber-700 on the pale amber strip: the amber-600 default measured
   * ~2.9:1 (visual review 2026-10-25), amber-700 clears 4.5:1.
   * 浅琥珀条上用 amber-700：默认 amber-600 实测约 2.9:1（视觉审查
   * 2026-10-25），amber-700 达标。 */
  color: #b45309;
  font-size: 0.75rem;
  font-weight: 500;
}

.trans-advanced {
  font-size: 0.8125rem;
  color: var(--text-secondary);
}

.trans-advanced summary {
  cursor: pointer;
  font-weight: 500;
  margin-bottom: 6px;
}

/* Result table / 结果表 */
.trans-table-wrap {
  max-height: 260px;
  overflow: auto;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
}

.trans-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.75rem;
}

.trans-table th {
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

.trans-table td {
  padding: 4px 8px;
  border-bottom: 1px solid var(--border);
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: 0.6875rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 160px;
}

.trans-row-failed td {
  color: var(--error);
  font-weight: 500;
}

.trans-error-cell {
  color: var(--error) !important;
}

/* Error banner / 错误横幅 */
.trans-error {
  font-size: 0.8125rem;
  color: var(--error);
  margin: 0;
  line-height: 1.5;
}

/* Responsive / 响应式 */
@media (max-width: 960px) {
  .trans-layout {
    grid-template-columns: 1fr;
  }
}
</style>
