<template>
  <section class="png-generate-page" :data-testid="testIds.pngGeneratePage">
    <!-- Header / 页头 -->
    <header class="pg-header">
      <h1>{{ t('pngGenerate.title') }}</h1>
      <p class="pg-subtitle">{{ t('pngGenerate.subtitle') }}</p>
    </header>

    <div class="pg-layout">
      <!-- Sidebar: display / export settings / 侧边栏：显示与导出设置 -->
      <aside class="pg-sidebar">
        <!-- Source & output folders / 源文件夹与输出文件夹 -->
        <div class="pg-panel">
          <h2 class="pg-panel-title">{{ t('pngGenerate.folders.title') }}</h2>
          <FileDialogButton
            mode="openFolder"
            :label="t('pngGenerate.folders.source')"
            :placeholder="t('pngGenerate.folders.sourcePlaceholder')"
            :model-value="sourceFolder"
            @update:model-value="onSourceFolderChange"
          />
          <FileDialogButton
            mode="openFolder"
            :label="t('pngGenerate.folders.output')"
            :placeholder="t('pngGenerate.folders.outputPlaceholder')"
            :model-value="outputFolder"
            @update:model-value="outputFolder = $event"
          />
          <label class="pg-checkbox-row">
            <input
              v-model="recursive"
              type="checkbox"
              class="pg-checkbox"
              :data-testid="testIds.pngGenerateRecursive"
            />
            <span>{{ t('pngGenerate.folders.recursive') }}</span>
          </label>
        </div>

        <!-- JSON config load/save / JSON 配置导入导出 -->
        <div class="pg-panel">
          <h2 class="pg-panel-title">{{ t('pngGenerate.jsonConfig.title') }}</h2>
          <div class="pg-btn-row">
            <button
              type="button"
              class="pg-btn pg-btn--secondary"
              :data-testid="testIds.pngGenerateLoadJson"
              @click="handleLoadJson"
            >
              {{ t('pngGenerate.jsonConfig.load') }}
            </button>
            <button
              type="button"
              class="pg-btn pg-btn--secondary"
              :data-testid="testIds.pngGenerateSaveJson"
              :disabled="!canSaveJson"
              @click="handleSaveJson"
            >
              {{ t('pngGenerate.jsonConfig.save') }}
            </button>
          </div>
          <!-- Hidden file input for JSON import / 隐藏的 JSON 导入文件输入 -->
          <input
            ref="jsonFileInput"
            type="file"
            accept=".json"
            class="pg-hidden-input"
            @change="onJsonFileSelected"
          />
        </div>

        <!-- Colormap & display settings / 色图与显示设置 -->
        <div class="pg-panel">
          <h2 class="pg-panel-title">{{ t('pngGenerate.display.title') }}</h2>

          <!-- Colormap / 色图 -->
          <label class="pg-field">
            <span class="pg-field-label">{{ t('pngGenerate.display.colormap') }}</span>
            <select
              v-model="template.colormap"
              class="pg-select"
              :data-testid="testIds.pngGenerateColormap"
            >
              <option v-for="cm in colormapOptions" :key="cm" :value="cm">
                {{ cm }}
              </option>
            </select>
          </label>

          <!-- Log / Linear toggle / 对数/线性切换 -->
          <label class="pg-checkbox-row">
            <input
              v-model="template.use_log"
              type="checkbox"
              class="pg-checkbox"
              :data-testid="testIds.pngGenerateLog"
            />
            <span>{{ t('pngGenerate.display.useLog') }}</span>
          </label>

          <!-- CLIM mode / 对比度范围模式 -->
          <div class="pg-clim-section">
            <span class="pg-field-label">{{ t('pngGenerate.display.clim') }}</span>
            <div class="pg-radio-row">
              <label class="pg-radio">
                <input
                  v-model="template.clim_mode"
                  type="radio"
                  value="auto"
                  class="pg-radio-input"
                />
                <span>{{ t('pngGenerate.display.climAuto') }}</span>
              </label>
              <label class="pg-radio">
                <input
                  v-model="template.clim_mode"
                  type="radio"
                  value="manual"
                  class="pg-radio-input"
                />
                <span>{{ t('pngGenerate.display.climManual') }}</span>
              </label>
            </div>
            <div v-if="template.clim_mode === 'manual'" class="pg-clim-inputs">
              <label class="pg-field pg-field--inline">
                <span class="pg-field-label pg-field-label--sm">Min</span>
                <input
                  v-model.number="climMinInput"
                  type="number"
                  class="pg-input"
                  :data-testid="testIds.pngGenerateClimMin"
                />
              </label>
              <label class="pg-field pg-field--inline">
                <span class="pg-field-label pg-field-label--sm">Max</span>
                <input
                  v-model.number="climMaxInput"
                  type="number"
                  class="pg-input"
                  :data-testid="testIds.pngGenerateClimMax"
                />
              </label>
            </div>
          </div>

          <!-- Layout: flat / per-file / 输出布局 -->
          <label class="pg-field">
            <span class="pg-field-label">{{ t('pngGenerate.display.layout') }}</span>
            <div class="pg-radio-row">
              <label class="pg-radio">
                <input
                  v-model="template.layout"
                  type="radio"
                  value="flat"
                  class="pg-radio-input"
                />
                <span>{{ t('pngGenerate.display.layoutFlat') }}</span>
              </label>
              <label class="pg-radio">
                <input
                  v-model="template.layout"
                  type="radio"
                  value="per_file"
                  class="pg-radio-input"
                />
                <span>{{ t('pngGenerate.display.layoutPerFile') }}</span>
              </label>
            </div>
          </label>

          <!-- DPI / 分辨率 -->
          <label class="pg-field">
            <span class="pg-field-label">{{ t('pngGenerate.display.dpi') }}</span>
            <input
              v-model.number="template.dpi"
              type="number"
              min="72"
              max="1200"
              class="pg-input"
              :data-testid="testIds.pngGenerateDpi"
            />
          </label>

          <!-- Show axes / 显示坐标轴 -->
          <label class="pg-checkbox-row">
            <input
              v-model="template.show_axes"
              type="checkbox"
              class="pg-checkbox"
              :data-testid="testIds.pngGenerateAxes"
            />
            <span>{{ t('pngGenerate.display.showAxes') }}</span>
          </label>

          <!-- Show colorbar / 显示色标 -->
          <label class="pg-checkbox-row">
            <input
              v-model="template.show_colorbar"
              type="checkbox"
              class="pg-checkbox"
              :data-testid="testIds.pngGenerateColorbar"
            />
            <span>{{ t('pngGenerate.display.showColorbar') }}</span>
          </label>
        </div>

        <!-- File type toggles / 文件类型开关 -->
        <div class="pg-panel">
          <h2 class="pg-panel-title">{{ t('pngGenerate.fileTypes.title') }}</h2>
          <label class="pg-checkbox-row">
            <input v-model="template.tiff.enabled" type="checkbox" class="pg-checkbox" />
            <span>TIFF / TIF</span>
          </label>
          <label class="pg-checkbox-row">
            <input v-model="template.edf.enabled" type="checkbox" class="pg-checkbox" />
            <span>EDF / CBF</span>
          </label>
          <label class="pg-checkbox-row">
            <input v-model="template.h5.enabled" type="checkbox" class="pg-checkbox" />
            <span>H5 / HDF5</span>
          </label>
        </div>
      </aside>

      <!-- Main area: scan results, run, progress / 主区域 -->
      <main class="pg-main">
        <!-- Scan section / 扫描区域 -->
        <div class="pg-scan-section">
          <button
            type="button"
            class="pg-btn pg-btn--secondary"
            :disabled="!sourceFolder"
            :data-testid="testIds.pngGenerateScanBtn"
            @click="handleScan"
          >
            {{ t('pngGenerate.scan.btn') }}
          </button>
          <span v-if="scanInfo" class="pg-scan-info" :data-testid="testIds.pngGenerateScanInfo">
            {{ scanInfo }}
          </span>
        </div>

        <!-- File list / 文件列表 -->
        <div v-if="fileCounts.h5 > 0 || fileCounts.tiff > 0 || fileCounts.edf > 0" class="pg-file-list">
          <h2 class="pg-section-title">{{ t('pngGenerate.discoveredFiles') }}</h2>
          <div class="pg-file-groups">
            <div v-if="fileCounts.h5 > 0" class="pg-file-group">
              <span class="pg-file-group-label">H5 ({{ fileCounts.h5 }})</span>
              <ul class="pg-file-list-items">
                <li v-for="f in fileListSummary.h5" :key="f">{{ f }}</li>
              </ul>
            </div>
            <div v-if="fileCounts.tiff > 0" class="pg-file-group">
              <span class="pg-file-group-label">TIFF ({{ fileCounts.tiff }})</span>
              <ul class="pg-file-list-items">
                <li v-for="f in fileListSummary.tiff" :key="f">{{ f }}</li>
              </ul>
            </div>
            <div v-if="fileCounts.edf > 0" class="pg-file-group">
              <span class="pg-file-group-label">EDF ({{ fileCounts.edf }})</span>
              <ul class="pg-file-list-items">
                <li v-for="f in fileListSummary.edf" :key="f">{{ f }}</li>
              </ul>
            </div>
          </div>
        </div>

        <!-- Run button / 运行按钮 -->
        <div class="pg-run-section">
          <button
            type="button"
            class="pg-btn pg-btn--primary"
            :disabled="!canRun"
            :data-testid="testIds.pngGenerateRunBtn"
            @click="handleRun"
          >
            {{ t('pngGenerate.run') }}
          </button>
        </div>

        <!-- Progress bar / 进度条 -->
        <TaskProgressBar
          v-if="pageState === 'running'"
          :task-id="taskId"
          :progress="progress"
          :message="progressMessage"
          @cancel="handleCancel"
        />

        <!-- Error state / 错误状态 -->
        <div v-if="pageState === 'error'" class="pg-error" :data-testid="testIds.pngGenerateError">
          <p>{{ errorMessage }}</p>
        </div>

        <!-- Result summary / 结果摘要 -->
        <ResultSummary
          v-if="pageState === 'done' && resultSummary"
          :summary="resultSummary"
        />

        <!-- JSON preview / JSON 预览 -->
        <div v-if="pageState === 'done' && resultSummary" class="pg-json-preview">
          <h2 class="pg-section-title">{{ t('pngGenerate.jsonPreview.title') }}</h2>
          <pre class="pg-json-pre">{{ jsonPreview }}</pre>
        </div>

        <!-- Empty state / 空状态 -->
        <div v-if="pageState === 'idle' && !scanInfo" class="pg-empty">
          <p>{{ t('pngGenerate.emptyState') }}</p>
        </div>
      </main>
    </div>
  </section>
</template>

<script setup lang="ts">
/**
 * PngGenerateView.vue — 批量 PNG 生成页面
 * Batch PNG Generation page
 *
 * 从 H5/TIFF/EDF 源文件夹批量生成色图映射的 PNG 图像。
 * Generates colormap-mapped PNG images in batch from H5/TIFF/EDF source folders.
 *
 * JSON 配置与 Viewer 页面完全兼容。
 * JSON config is fully compatible with the Viewer page schema.
 */
import { ref, reactive, computed, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useToast } from '@/lib/toast'
import { testIds } from '@/lib/testIds'

import FileDialogButton from '@/components/business/FileDialogButton.vue'
import TaskProgressBar from '@/components/business/TaskProgressBar.vue'
import ResultSummary from '@/components/business/ResultSummary.vue'
import type { ResultSummaryData } from '@/components/business/ResultSummary.vue'
import { useTransport } from '@/lib/transport'

// === Type definitions / 类型定义 ===

/** Viewer-compatible JSON template schema / 与 Viewer 兼容的 JSON 模板结构 */
interface PngTemplate {
  colormap: string
  use_log: boolean
  clim_mode: 'auto' | 'manual'
  clim: [number | null, number | null]
  layout: 'flat' | 'per_file'
  show_axes: boolean
  show_colorbar: boolean
  dpi: number
  h5: { enabled: boolean; datasets: H5DatasetConfig[] }
  tiff: { enabled: boolean }
  edf: { enabled: boolean }
}

interface H5DatasetConfig {
  path: string
  ndim: number
  dtype_kind: string
  n_frames: number | null
  n_channels: number | null
  frames_to_export: number[] | null
  channels_to_export: number[] | null
  export_subfolder: string
  enabled: boolean
}

interface ScanResult {
  h5: string[]
  tiff: string[]
  edf: string[]
}

type PageState = 'idle' | 'running' | 'done' | 'error'

/** Colormap options matching Python service / 与 Python 服务匹配的色图选项 */
const COLORMAP_OPTIONS = [
  'viridis', 'plasma', 'inferno', 'magma', 'cividis',
  'jet', 'gray', 'hot', 'cool', 'turbo',
] as const

// === Default template / 默认模板 ===

function createDefaultTemplate(): PngTemplate {
  return {
    colormap: 'viridis',
    use_log: false,
    clim_mode: 'auto',
    clim: [null, null],
    layout: 'flat',
    show_axes: false,
    show_colorbar: false,
    dpi: 300,
    h5: { enabled: true, datasets: [] },
    tiff: { enabled: true },
    edf: { enabled: true },
  }
}

// === Composables / 组合函数 ===

const { t } = useI18n()
const toast = useToast()
const transport = useTransport()

// === Folder state / 文件夹状态 ===

const sourceFolder = ref<string | null>(null)
const outputFolder = ref<string | null>(null)
const recursive = ref(false)

// === Template state / 模板状态 ===

const template = reactive<PngTemplate>(createDefaultTemplate())

const climMinInput = computed({
  get: () => template.clim[0],
  set: (v: number | undefined) => {
    template.clim[0] = v ?? null
  },
})

const climMaxInput = computed({
  get: () => template.clim[1],
  set: (v: number | undefined) => {
    template.clim[1] = v ?? null
  },
})

// === Scan state / 扫描状态 ===

const scanInfo = ref<string | null>(null)
const fileLists = ref<ScanResult>({ h5: [], tiff: [], edf: [] })

const fileCounts = computed(() => ({
  h5: fileLists.value.h5.length,
  tiff: fileLists.value.tiff.length,
  edf: fileLists.value.edf.length,
}))

/** Show only file basenames in the UI / UI 中只显示文件名 */
const fileListSummary = computed(() => {
  const basename = (p: string) => {
    const sep = p.includes('/') ? '/' : '\\'
    return p.split(sep).pop() ?? p
  }
  return {
    h5: fileLists.value.h5.map(basename),
    tiff: fileLists.value.tiff.map(basename),
    edf: fileLists.value.edf.map(basename),
  }
})

// === Task execution state / 任务执行状态 ===

const pageState = ref<PageState>('idle')
const taskId = ref<string | null>(null)
const progress = ref(0)
const progressMessage = ref<string | null>(null)
const errorMessage = ref('')
const resultSummary = ref<ResultSummaryData | null>(null)

const colormapOptions = COLORMAP_OPTIONS

// JSON file input ref / JSON 文件输入引用
const jsonFileInput = ref<HTMLInputElement | null>(null)

// Cleanup functions for event listeners / 事件监听器清理函数
let cleanupProgress: (() => void) | null = null
let cleanupResult: (() => void) | null = null
let cleanupError: (() => void) | null = null

// === Computed / 计算属性 ===

const canRun = computed(() => {
  return (
    sourceFolder.value !== null &&
    outputFolder.value !== null &&
    pageState.value !== 'running'
  )
})

const canSaveJson = computed(() => {
  return sourceFolder.value !== null
})

const jsonPreview = computed(() => {
  return JSON.stringify(buildExportTemplate(), null, 2)
})

// === Helpers / 辅助函数 ===

/**
 * Build the export-ready template from current UI state
 * 从当前 UI 状态构建导出就绪的模板
 */
function buildExportTemplate(): Record<string, unknown> {
  return {
    colormap: template.colormap,
    use_log: template.use_log,
    clim_mode: template.clim_mode,
    clim: [...template.clim],
    layout: template.layout,
    show_axes: template.show_axes,
    show_colorbar: template.show_colorbar,
    dpi: template.dpi,
    h5: { ...template.h5 },
    tiff: { ...template.tiff },
    edf: { ...template.edf },
  }
}

/**
 * Merge loaded JSON into the reactive template
 * 将加载的 JSON 合并到响应式模板中
 */
function applyJsonConfig(raw: Record<string, unknown>): void {
  const tmpl = createDefaultTemplate()

  // New format: has h5/tiff/edf keys / 新格式：包含 h5/tiff/edl 键
  const knownKeys = [
    'colormap', 'use_log', 'clim_mode', 'clim',
    'layout', 'show_axes', 'show_colorbar', 'dpi',
  ] as const

  for (const key of knownKeys) {
    if (key in raw && raw[key] !== undefined) {
      (tmpl as unknown as Record<string, unknown>)[key] = raw[key]
    }
  }

  if (raw.h5 && typeof raw.h5 === 'object') {
    tmpl.h5 = raw.h5 as PngTemplate['h5']
  }
  if (raw.tiff && typeof raw.tiff === 'object') {
    tmpl.tiff = raw.tiff as PngTemplate['tiff']
  }
  if (raw.edf && typeof raw.edf === 'object') {
    tmpl.edf = raw.edf as PngTemplate['edf']
  }

  // Apply to reactive template / 应用到响应式模板
  Object.assign(template, tmpl)
}

// === Handlers / 处理函数 ===

function onSourceFolderChange(path: string | null): void {
  sourceFolder.value = path
  // Auto-set output to source + /export / 自动设置输出路径
  if (path && !outputFolder.value) {
    const sep = path.includes('/') ? '/' : '\\'
    outputFolder.value = path + sep + 'export'
  }
  scanInfo.value = null
  fileLists.value = { h5: [], tiff: [], edf: [] }
}

/** Scan source folder via task service / 通过任务服务扫描源文件夹 */
async function handleScan(): Promise<void> {
  if (!sourceFolder.value) return

  try {
    const params = {
      sourceFolder: sourceFolder.value,
      recursive: recursive.value,
      scanOnly: true,
    }
    const response = await transport.submitTask('png_generate', params)
    taskId.value = response.taskId

    cleanupResult = transport.onTaskResult(response.taskId, (payload) => {
      const data = payload.data as ScanResult & { h5_datasets?: H5DatasetConfig[] }
      fileLists.value = {
        h5: data.h5 ?? [],
        tiff: data.tiff ?? [],
        edf: data.edf ?? [],
      }

      // If H5 datasets detected, update template / 如果检测到 H5 数据集则更新模板
      if (data.h5_datasets && data.h5_datasets.length > 0 && template.h5.datasets.length === 0) {
        template.h5.datasets = data.h5_datasets
      }

      const nH5 = fileLists.value.h5.length
      const nTiff = fileLists.value.tiff.length
      const nEdf = fileLists.value.edf.length
      scanInfo.value = `H5: ${nH5}  TIFF: ${nTiff}  EDF: ${nEdf}`

      toast.push({
        title: t('pngGenerate.scan.successTitle'),
        message: t('pngGenerate.scan.successMessage', {
          total: nH5 + nTiff + nEdf,
        }),
        tone: 'success',
      })
    })

    cleanupError = transport.onTaskError(response.taskId, (payload) => {
      errorMessage.value = payload.error
      toast.push({
        title: t('pngGenerate.scan.errorTitle'),
        message: payload.error,
        tone: 'error',
      })
    })
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : String(err)
    toast.push({
      title: t('pngGenerate.scan.errorTitle'),
      message: errorMessage.value,
      tone: 'error',
    })
  }
}

/** Run batch PNG generation / 执行批量 PNG 生成 */
async function handleRun(): Promise<void> {
  if (!sourceFolder.value || !outputFolder.value || pageState.value === 'running') return

  // Reset state / 重置状态
  pageState.value = 'running'
  progress.value = 0
  progressMessage.value = null
  errorMessage.value = ''
  resultSummary.value = null

  const params: Record<string, unknown> = {
    sourceFolder: sourceFolder.value,
    outputFolder: outputFolder.value,
    recursive: recursive.value,
    template: buildExportTemplate(),
  }

  const startTime = Date.now()

  try {
    const response = await transport.submitTask('png_generate', params)
    taskId.value = response.taskId

    // Register progress listener / 注册进度监听器
    cleanupProgress = transport.onTaskProgress(response.taskId, (payload) => {
      progress.value = payload.progress
      progressMessage.value = payload.message ?? null
    })

    // Register result listener / 注册结果监听器
    cleanupResult = transport.onTaskResult(response.taskId, (payload) => {
      const data = payload.data as {
        images_generated: number
        errors: number
      }
      const elapsed = (Date.now() - startTime) / 1000
      const totalFiles = fileCounts.value.h5 + fileCounts.value.tiff + fileCounts.value.edf

      resultSummary.value = {
        total: totalFiles,
        success: data.images_generated ?? 0,
        failed: data.errors ?? 0,
        elapsed,
      }
      pageState.value = 'done'
      progress.value = 1

      toast.push({
        title: t('pngGenerate.successTitle'),
        message: t('pngGenerate.successMessage', {
          count: data.images_generated ?? 0,
        }),
        tone: 'success',
      })
    })

    // Register error listener / 注册错误监听器
    cleanupError = transport.onTaskError(response.taskId, (payload) => {
      errorMessage.value = payload.error
      pageState.value = 'error'
      toast.push({
        title: t('pngGenerate.errorTitle'),
        message: payload.error,
        tone: 'error',
      })
    })
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : String(err)
    pageState.value = 'error'
    toast.push({
      title: t('pngGenerate.errorTitle'),
      message: errorMessage.value,
      tone: 'error',
    })
  }
}

/**
 * Cancel the running task — completed files are kept, pending tasks stopped
 * 取消正在运行的任务 — 已完成的文件保留，未完成的任务停止
 */
function handleCancel(): void {
  // Keep resultSummary if partial results exist / 如果有部分结果则保留
  pageState.value = 'idle'
  taskId.value = null
  cleanupListeners()
}

/** Load JSON config from file / 从文件加载 JSON 配置 */
function handleLoadJson(): void {
  jsonFileInput.value?.click()
}

function onJsonFileSelected(event: Event): void {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return

  const reader = new FileReader()
  reader.onload = (e) => {
    try {
      const raw = JSON.parse(e.target?.result as string) as Record<string, unknown>
      applyJsonConfig(raw)
      toast.push({
        title: t('pngGenerate.jsonConfig.loadSuccessTitle'),
        message: t('pngGenerate.jsonConfig.loadSuccessMessage'),
        tone: 'success',
      })
    } catch (err) {
      toast.push({
        title: t('pngGenerate.jsonConfig.loadErrorTitle'),
        message: err instanceof Error ? err.message : String(err),
        tone: 'error',
      })
    }
  }
  reader.readAsText(file)
  // Reset input so the same file can be re-selected / 重置输入以便可以重复选择同一文件
  input.value = ''
}

/** Save JSON config to file / 将 JSON 配置保存到文件 */
async function handleSaveJson(): Promise<void> {
  try {
    const path = await transport.selectSavePath({
      filters: [{ name: 'JSON', extensions: ['json'] }],
    })
    if (!path) return

    const content = JSON.stringify(buildExportTemplate(), null, 2)
    // Submit a write task to the Python backend / 提交写文件任务到 Python 后端
    await transport.submitTask('png_generate', {
      writeJson: true,
      path,
      content,
    })
    toast.push({
      title: t('pngGenerate.jsonConfig.saveSuccessTitle'),
      message: path,
      tone: 'success',
    })
  } catch (err) {
    toast.push({
      title: t('pngGenerate.jsonConfig.saveErrorTitle'),
      message: err instanceof Error ? err.message : String(err),
      tone: 'error',
    })
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
}

onUnmounted(() => {
  cleanupListeners()
})
</script>

<style scoped>
.png-generate-page {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.pg-header {
  padding-bottom: 8px;
}

.pg-header h1 {
  font-size: 1.5rem;
  font-weight: 700;
  margin: 0 0 6px;
  color: var(--text-primary);
}

.pg-subtitle {
  font-size: 0.9375rem;
  color: var(--text-secondary);
  margin: 0;
}

.pg-layout {
  display: grid;
  grid-template-columns: minmax(280px, 380px) minmax(0, 1fr);
  gap: 24px;
  align-items: start;
}

/* Sidebar / 侧边栏 */
.pg-sidebar {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* Panel / 面板 */
.pg-panel {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.pg-panel-title {
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

/* Field / 字段 */
.pg-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.pg-field--inline {
  flex-direction: row;
  align-items: center;
  gap: 8px;
}

.pg-field-label {
  font-size: 0.8125rem;
  color: var(--text-secondary);
  font-weight: 500;
}

.pg-field-label--sm {
  font-size: 0.75rem;
  min-width: 28px;
}

.pg-select,
.pg-input {
  padding: 8px 10px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: 0.875rem;
  transition: border-color var(--transition-fast);
}

.pg-select:focus,
.pg-input:focus {
  outline: none;
  border-color: var(--border-focus);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}

.pg-input {
  width: 100%;
}

.pg-input[type="number"] {
  max-width: 100px;
}

/* Checkbox row / 复选框行 */
.pg-checkbox-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.875rem;
  color: var(--text-primary);
  cursor: pointer;
}

.pg-checkbox {
  width: 16px;
  height: 16px;
  accent-color: var(--primary);
  cursor: pointer;
}

/* Radio row / 单选按钮行 */
.pg-radio-row {
  display: flex;
  gap: 16px;
}

.pg-radio {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.8125rem;
  color: var(--text-primary);
  cursor: pointer;
}

.pg-radio-input {
  accent-color: var(--primary);
  cursor: pointer;
}

/* CLIM section / 对比度范围区域 */
.pg-clim-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.pg-clim-inputs {
  display: flex;
  gap: 12px;
}

/* Button styles / 按钮样式 */
.pg-btn-row {
  display: flex;
  gap: 8px;
}

.pg-btn {
  padding: 8px 16px;
  border-radius: var(--radius-md);
  font-size: 0.8125rem;
  font-weight: 500;
  cursor: pointer;
  border: 1px solid var(--border);
  transition: opacity var(--transition-fast), border-color var(--transition-fast);
}

.pg-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.pg-btn--secondary {
  background: var(--bg-surface);
  color: var(--text-primary);
}

.pg-btn--secondary:not(:disabled):hover {
  border-color: var(--border-hover);
}

.pg-btn--primary {
  padding: 12px 32px;
  background: var(--primary);
  color: var(--text-inverse);
  border: none;
  font-size: 0.9375rem;
  font-weight: 600;
}

.pg-btn--primary:not(:disabled):hover {
  opacity: 0.9;
}

.pg-hidden-input {
  display: none;
}

/* Main area / 主区域 */
.pg-main {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* Scan section / 扫描区域 */
.pg-scan-section {
  display: flex;
  align-items: center;
  gap: 16px;
}

.pg-scan-info {
  font-family: var(--font-mono);
  font-size: 0.8125rem;
  color: var(--secondary);
}

/* File list / 文件列表 */
.pg-file-list {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 16px;
}

.pg-section-title {
  font-size: 1rem;
  font-weight: 600;
  margin: 0 0 10px;
  color: var(--text-primary);
}

.pg-file-groups {
  display: flex;
  gap: 20px;
  flex-wrap: wrap;
}

.pg-file-group {
  flex: 1;
  min-width: 160px;
}

.pg-file-group-label {
  display: block;
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 6px;
}

.pg-file-list-items {
  margin: 0;
  padding-left: 18px;
  font-size: 0.8125rem;
  color: var(--text-secondary);
  list-style: disc;
  max-height: 160px;
  overflow-y: auto;
}

/* Run section / 运行区域 */
.pg-run-section {
  display: flex;
}

/* Error / 错误 */
.pg-error {
  padding: 14px 18px;
  border-radius: var(--radius-md);
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: var(--error);
  font-size: 0.875rem;
}

.pg-error p {
  margin: 0;
}

/* Empty state / 空状态 */
.pg-empty {
  padding: 40px 24px;
  text-align: center;
  color: var(--text-muted);
  font-size: 0.9375rem;
}

.pg-empty p {
  margin: 0;
}

/* JSON preview / JSON 预览 */
.pg-json-preview {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 16px;
}

.pg-json-pre {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--text-secondary);
  background: var(--bg-surface-alt);
  border-radius: var(--radius-md);
  padding: 12px;
  margin: 0;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

/* Responsive / 响应式 */
@media (max-width: 960px) {
  .pg-layout {
    grid-template-columns: 1fr;
  }
}
</style>
