<template>
  <section class="im-page">
    <!-- Header / 页头 -->
    <header class="im-header">
      <h1>{{ t('imageMath.title') }}</h1>
      <p class="im-subtitle">{{ t('imageMath.subtitle') }}</p>
      <div class="im-formula">
        <span class="im-formula-label">{{ t('imageMath.formula') }}:</span>
        <span class="im-formula-expr">
          result = image1 &times; {{ factor1 }}
          <template v-if="operation === 'subtract'"> &minus; </template>
          <template v-else> + </template>
          image2 &times; {{ factor2 }}
        </span>
      </div>
    </header>

    <div class="im-layout">
      <!-- ===== Sidebar: controls / 侧边栏：控制面板 ===== -->
      <aside class="im-sidebar">
        <!-- Operation mode / 运算模式 -->
        <div class="im-card">
          <h3 class="im-card-title">{{ t('imageMath.operation') }}</h3>
          <div class="im-radio-row">
            <label class="im-radio-label">
              <input v-model="operation" type="radio" value="add" />
              <span>{{ t('imageMath.opAdd') }}</span>
            </label>
            <label class="im-radio-label">
              <input v-model="operation" type="radio" value="subtract" />
              <span>{{ t('imageMath.opSubtract') }}</span>
            </label>
          </div>
        </div>

        <!-- Image 1 / 图像 1 -->
        <div class="im-card">
          <h3 class="im-card-title">{{ t('imageMath.image1') }}</h3>
          <FileDialogButton
            v-model="image1Path"
            mode="openFile"
            :label="t('imageMath.selectFile')"
            :filters="dataFileFilters"
          />
          <div class="im-field">
            <label class="im-label">{{ t('imageMath.factor') }}</label>
            <input
              v-model.number="factor1"
              type="number"
              class="im-input"
              step="0.1"
            />
          </div>
        </div>

        <!-- Image 2 / 图像 2 -->
        <div class="im-card">
          <h3 class="im-card-title">{{ t('imageMath.image2') }}</h3>
          <FileDialogButton
            v-model="image2Path"
            mode="openFile"
            :label="t('imageMath.selectFile')"
            :filters="dataFileFilters"
          />
          <div class="im-field">
            <label class="im-label">{{ t('imageMath.factor') }}</label>
            <input
              v-model.number="factor2"
              type="number"
              class="im-input"
              step="0.1"
            />
          </div>
        </div>

        <!-- Export / 导出 -->
        <div class="im-card">
          <h3 class="im-card-title">{{ t('imageMath.export') }}</h3>
          <FileDialogButton
            v-model="outputDir"
            mode="openFolder"
            :label="t('imageMath.outputDir')"
          />
          <div class="im-field">
            <label class="im-label">{{ t('imageMath.outputFormat') }}</label>
            <select v-model="outputFormat" class="im-select">
              <option value="h5">HDF5</option>
              <option value="edf">EDF</option>
              <option value="tif">TIFF</option>
            </select>
          </div>
          <button
            type="button"
            class="im-btn"
            :disabled="!canSave"
            @click="handleSave"
          >
            {{ t('imageMath.saveResult') }}
          </button>
        </div>

        <!-- Execute / 执行 -->
        <div class="im-card">
          <button
            type="button"
            class="im-btn im-btn-primary"
            :disabled="!canCompute"
            @click="handleCompute"
          >
            {{ t('imageMath.execute') }}
          </button>
        </div>
      </aside>

      <!-- ===== Main area / 主区域 ===== -->
      <main class="im-main">
        <!-- Row 1: Image1 + Image2 side by side / 图像1与图像2并列 -->
        <div class="im-two-row">
          <!-- Image 1 panel / 图像1面板 -->
          <div class="im-panel">
            <div class="im-panel-header">
              <span class="im-panel-title">{{ t('imageMath.tabImage1') }}</span>
              <span v-if="image1Path" class="im-panel-file-hint">{{ extractFileName(image1Path) }}</span>
            </div>
            <div v-if="image1PreviewLoading" class="im-preview-loading">
              {{ t('imageMath.loading') }}
            </div>
            <div v-else-if="image1PreviewUrl" class="im-panel-image">
              <ImagePreview
                :image-b64="image1PreviewUrl"
                :show-colorbar="false"
                :placeholder="t('imageMath.noImage')"
                :render-min="climMode === 'manual' ? climMin : undefined"
                :render-max="climMode === 'manual' ? climMax : undefined"
                :use-log-scale="useLog"
              />
            </div>
            <div v-else class="im-preview-empty">
              {{ t('imageMath.noPreview') }}
            </div>
            <div v-if="image1PreviewStats" class="im-panel-stats">
              <span>Min: {{ formatSci(image1PreviewStats.min) }}</span>
              <span>Max: {{ formatSci(image1PreviewStats.max) }}</span>
              <span>Mean: {{ formatSci(image1PreviewStats.mean) }}</span>
            </div>
          </div>

          <!-- Image 2 panel / 图像2面板 -->
          <div class="im-panel">
            <div class="im-panel-header">
              <span class="im-panel-title">{{ t('imageMath.tabImage2') }}</span>
              <span v-if="image2Path" class="im-panel-file-hint">{{ extractFileName(image2Path) }}</span>
            </div>
            <div v-if="image2PreviewLoading" class="im-preview-loading">
              {{ t('imageMath.loading') }}
            </div>
            <div v-else-if="image2PreviewUrl" class="im-panel-image">
              <ImagePreview
                :image-b64="image2PreviewUrl"
                :show-colorbar="false"
                :placeholder="t('imageMath.noImage')"
                :render-min="climMode === 'manual' ? climMin : undefined"
                :render-max="climMode === 'manual' ? climMax : undefined"
                :use-log-scale="useLog"
              />
            </div>
            <div v-else class="im-preview-empty">
              {{ t('imageMath.noPreview') }}
            </div>
            <div v-if="image2PreviewStats" class="im-panel-stats">
              <span>Min: {{ formatSci(image2PreviewStats.min) }}</span>
              <span>Max: {{ formatSci(image2PreviewStats.max) }}</span>
              <span>Mean: {{ formatSci(image2PreviewStats.mean) }}</span>
            </div>
          </div>
        </div>

        <!-- Display settings / 显示设置 -->
        <div class="im-card im-display-bar">
          <div class="im-display-row">
            <div class="im-field" style="min-width:140px">
              <label class="im-label">{{ t('imageMath.colormap') }}</label>
              <select v-model="colormap" class="im-select">
                <option v-for="cm in colormapOptions" :key="cm" :value="cm">{{ cm }}</option>
              </select>
            </div>
            <label class="im-toggle-label" style="white-space:nowrap">
              <input v-model="useLog" type="checkbox" />
              <span>{{ t('imageMath.logScale') }}</span>
            </label>
            <div class="im-radio-row">
              <label class="im-radio-label">
                <input v-model="climMode" type="radio" value="auto" />
                <span>{{ t('imageMath.contrastAuto') }}</span>
              </label>
              <label class="im-radio-label">
                <input v-model="climMode" type="radio" value="manual" />
                <span>{{ t('imageMath.contrastManual') }}</span>
              </label>
            </div>
            <template v-if="climMode === 'manual'">
              <div class="im-field">
                <label class="im-label">Min</label>
                <input v-model.number="climMin" type="number" class="im-input im-input-sm" step="any" />
              </div>
              <div class="im-field">
                <label class="im-label">Max</label>
                <input v-model.number="climMax" type="number" class="im-input im-input-sm" step="any" />
              </div>
            </template>
          </div>
        </div>

        <!-- Result panel / 结果面板 -->
        <div v-if="resultPreviewUrl || resultPreviewLoading" class="im-panel im-result-panel">
          <div class="im-panel-header">
            <span class="im-panel-title">{{ t('imageMath.tabResult') }}</span>
          </div>
          <div v-if="resultPreviewLoading" class="im-preview-loading">
            {{ t('imageMath.loading') }}
          </div>
          <div v-else-if="resultPreviewUrl" class="im-panel-image">
            <ImagePreview
              :image-b64="resultPreviewUrl"
              :show-colorbar="false"
              :placeholder="t('imageMath.noImage')"
              :render-min="climMode === 'manual' ? climMin : undefined"
              :render-max="climMode === 'manual' ? climMax : undefined"
              :use-log-scale="useLog"
            />
          </div>
          <div v-if="resultPreviewStats" class="im-panel-stats">
            <span>Min: {{ formatSci(resultPreviewStats.min) }}</span>
            <span>Max: {{ formatSci(resultPreviewStats.max) }}</span>
            <span>Mean: {{ formatSci(resultPreviewStats.mean) }}</span>
          </div>
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
        <div v-if="state === 'error'" class="im-error">
          <p>{{ t('imageMath.errorPrefix') }} {{ errorMessage }}</p>
        </div>

        <!-- Empty state / 空状态 -->
        <div v-if="state === 'idle' && !image1PreviewUrl && !image2PreviewUrl" class="im-empty">
          <p>{{ t('imageMath.emptyState') }}</p>
        </div>
      </main>
    </div>
  </section>
</template>

<script setup lang="ts">
/**
 * ImageMathView.vue — 图像运算页面
 * Image Math page: perform arithmetic operations on two images.
 * result = image1 * factor1 ± image2 * factor2
 */
import { ref, computed, watch, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useToast } from '@/lib/toast'
import { useTransport } from '@/lib/transport'
import type { TaskBinaryPayload } from '@/lib/transport'
import { COLORMAP_PRESETS } from '@/lib/chart-utils'

import FileDialogButton from '@/components/business/FileDialogButton.vue'
import TaskProgressBar from '@/components/business/TaskProgressBar.vue'
import ImagePreview from '@/components/charts/ImagePreview.vue'

// === Type definitions / 类型定义 ===

interface PreviewStats {
  min: number
  max: number
  mean: number
  shape?: [number, number]
}

type PageState = 'idle' | 'running' | 'done' | 'error'
type Operation = 'add' | 'subtract'

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

// === State / 状态 ===

const state = ref<PageState>('idle')
const taskId = ref<string | null>(null)
const progress = ref(0)
const progressMessage = ref<string | null>(null)
const errorMessage = ref('')

// === File selection / 文件选择 ===

const image1Path = ref<string | null>(null)
const image2Path = ref<string | null>(null)
const factor1 = ref(1.0)
const factor2 = ref(1.0)
const operation = ref<Operation>('subtract')

const dataFileFilters = [
  { name: 'Detector Images', extensions: ['edf', 'tif', 'tiff', 'h5', 'hdf5'] },
]

// === Display settings / 显示设置 ===

const colormap = ref('smooth_WAXS_foxtrot')
const useLog = ref(false)
const climMode = ref<'auto' | 'manual'>('auto')
const climMin = ref(0)
const climMax = ref(1)

// Debounce timer for contrast changes / 对比度变化防抖定时器
let contrastDebounceTimer: ReturnType<typeof setTimeout> | null = null

// === Preview / 预览 ===

const image1PreviewUrl = ref<string | null>(null)
const image1PreviewStats = ref<PreviewStats | null>(null)
const image1PreviewLoading = ref(false)
const image2PreviewUrl = ref<string | null>(null)
const image2PreviewStats = ref<PreviewStats | null>(null)
const image2PreviewLoading = ref(false)
const resultPreviewUrl = ref<string | null>(null)
const resultPreviewStats = ref<PreviewStats | null>(null)
const resultPreviewLoading = ref(false)

// === Export / 导出 ===

const outputDir = ref<string | null>(null)
const outputFormat = ref<'h5' | 'edf' | 'tif'>('tif')

// === Cleanup functions / 清理函数 ===

let cleanupProgress: (() => void) | null = null
let cleanupResult: (() => void) | null = null
let cleanupError: (() => void) | null = null
let cleanupBinaryData: (() => void) | null = null

// === Computed / 计算属性 ===

const canCompute = computed(() => {
  if (state.value === 'running') return false
  return !!image1Path.value && !!image2Path.value
})

const canSave = computed(() => {
  return state.value === 'done' && !!outputDir.value
})

// === Watchers / 监听器 ===

// Auto-load image1 preview when path changes / 图像1路径变化时自动加载预览
watch(image1Path, (newPath) => {
  if (newPath) {
    loadImage1Panel()
  } else {
    if (image1PreviewUrl.value?.startsWith('blob:')) URL.revokeObjectURL(image1PreviewUrl.value)
    image1PreviewUrl.value = null
    image1PreviewStats.value = null
  }
})

// Auto-load image2 preview when path changes / 图像2路径变化时自动加载预览
watch(image2Path, (newPath) => {
  if (newPath) {
    loadImage2Panel()
  } else {
    if (image2PreviewUrl.value?.startsWith('blob:')) URL.revokeObjectURL(image2PreviewUrl.value)
    image2PreviewUrl.value = null
    image2PreviewStats.value = null
  }
})

// Reload preview when contrast settings change (debounced)
// 对比度设置变化时重新加载预览（防抖）
let suppressContrastReload = false

watch([climMode, climMin, climMax, useLog], () => {
  if (suppressContrastReload) return
  if (climMode.value === 'manual') {
    if (!Number.isFinite(climMin.value) || !Number.isFinite(climMax.value)) return
  }
  if (contrastDebounceTimer) clearTimeout(contrastDebounceTimer)
  contrastDebounceTimer = setTimeout(() => {
    contrastDebounceTimer = null
    if (state.value === 'idle' || state.value === 'done') {
      reloadAllPreviews()
    }
  }, 400)
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

// === Preview / 预览 ===

function cleanupPreviewListeners(): void {
  cleanupBinaryData?.()
  cleanupBinaryData = null
}

// Load preview into a specific panel's refs / 加载预览到指定面板的 ref
function loadPanelPreview(
  tab: 'image1' | 'image2' | 'result',
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

  let previewAction: string
  const params: Record<string, unknown> = {
    ...getRenderSettingsParams(),
  }

  switch (tab) {
    case 'image1':
      if (!image1Path.value) {
        loadingRef.value = false
        return
      }
      previewAction = 'preview_image1'
      params.action = previewAction
      params.image1_path = image1Path.value
      break
    case 'image2':
      if (!image2Path.value) {
        loadingRef.value = false
        return
      }
      previewAction = 'preview_image2'
      params.action = previewAction
      params.image2_path = image2Path.value
      break
    case 'result':
      if (!image1Path.value || !image2Path.value) {
        loadingRef.value = false
        return
      }
      previewAction = 'preview_result'
      params.action = previewAction
      params.image1_path = image1Path.value
      params.image2_path = image2Path.value
      params.factor1 = factor1.value
      params.factor2 = factor2.value
      params.operation = operation.value
      break
    default:
      loadingRef.value = false
      return
  }

  transport.submitTask('image_math', params).then((response) => {
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
        if (climMode.value === 'auto' && tab === 'image1') {
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
        title: t('imageMath.errorTitle'),
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
      title: t('imageMath.errorTitle'),
      message: err instanceof Error ? err.message : String(err),
      tone: 'error',
    })
  })
}

// Reload all visible panels / 重新加载所有可见面板
function reloadAllPreviews(): void {
  if (image1Path.value) {
    loadPanelPreview('image1', image1PreviewUrl, image1PreviewStats, image1PreviewLoading)
  }
  if (image2Path.value) {
    loadPanelPreview('image2', image2PreviewUrl, image2PreviewStats, image2PreviewLoading)
  }
  if (resultPreviewUrl.value || state.value === 'done') {
    loadPanelPreview('result', resultPreviewUrl, resultPreviewStats, resultPreviewLoading)
  }
}

// Load image1 panel / 加载图像1面板
function loadImage1Panel(): void {
  loadPanelPreview('image1', image1PreviewUrl, image1PreviewStats, image1PreviewLoading)
}

// Load image2 panel / 加载图像2面板
function loadImage2Panel(): void {
  loadPanelPreview('image2', image2PreviewUrl, image2PreviewStats, image2PreviewLoading)
}

// Load result panel / 加载结果面板
function loadResultPanel(): void {
  loadPanelPreview('result', resultPreviewUrl, resultPreviewStats, resultPreviewLoading)
}

// === Compute execution / 执行运算 ===

async function handleCompute(): Promise<void> {
  if (state.value === 'running') return

  state.value = 'running'
  progress.value = 0
  progressMessage.value = null
  errorMessage.value = ''

  const params: Record<string, unknown> = {
    action: 'compute',
    image1_path: image1Path.value,
    image2_path: image2Path.value,
    factor1: factor1.value,
    factor2: factor2.value,
    operation: operation.value,
  }

  try {
    const response = await transport.submitTask('image_math', params)
    taskId.value = response.taskId

    cleanupProgress = transport.onTaskProgress(response.taskId, (payload) => {
      progress.value = payload.progress
      progressMessage.value = payload.message ?? null
    })

    cleanupResult = transport.onTaskResult(response.taskId, () => {
      loadResultPanel()
      toast.push({
        title: t('imageMath.successTitle'),
        message: t('imageMath.computeComplete'),
        tone: 'success',
      })
      taskId.value = null
      state.value = 'done'
      progress.value = 1
    })

    cleanupError = transport.onTaskError(response.taskId, (payload) => {
      taskId.value = null
      errorMessage.value = payload.error
      state.value = 'error'
      toast.push({
        title: t('imageMath.errorTitle'),
        message: payload.error,
        tone: 'error',
      })
    })
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : String(err)
    state.value = 'error'
    toast.push({
      title: t('imageMath.errorTitle'),
      message: errorMessage.value,
      tone: 'error',
    })
  }
}

// === Save result / 保存结果 ===

async function handleSave(): Promise<void> {
  if (!outputDir.value || !image1Path.value || !image2Path.value) return

  const params: Record<string, unknown> = {
    action: 'save',
    image1_path: image1Path.value,
    image2_path: image2Path.value,
    factor1: factor1.value,
    factor2: factor2.value,
    operation: operation.value,
    output_dir: outputDir.value,
    output_format: outputFormat.value,
  }

  try {
    const response = await transport.submitTask('image_math', params)

    const unsubResult = transport.onTaskResult(response.taskId, () => {
      toast.push({
        title: t('imageMath.successTitle'),
        message: t('imageMath.computeComplete'),
        tone: 'success',
      })
      unsubResult()
      unsubError()
    })

    const unsubError = transport.onTaskError(response.taskId, (payload) => {
      toast.push({
        title: t('imageMath.errorTitle'),
        message: payload.error,
        tone: 'error',
      })
      unsubResult()
      unsubError()
    })
  } catch (err) {
    toast.push({
      title: t('imageMath.errorTitle'),
      message: err instanceof Error ? err.message : String(err),
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
  if (image1PreviewUrl.value?.startsWith('blob:')) URL.revokeObjectURL(image1PreviewUrl.value)
  if (image2PreviewUrl.value?.startsWith('blob:')) URL.revokeObjectURL(image2PreviewUrl.value)
  if (resultPreviewUrl.value?.startsWith('blob:')) URL.revokeObjectURL(resultPreviewUrl.value)
  cleanupListeners()
  if (contrastDebounceTimer) clearTimeout(contrastDebounceTimer)
})
</script>

<style scoped>
.im-page {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.im-header {
  padding-bottom: 8px;
}

.im-header h1 {
  font-size: 1.5rem;
  font-weight: 700;
  margin: 0 0 6px;
  color: var(--text-primary);
}

.im-subtitle {
  font-size: 0.9375rem;
  color: var(--text-secondary);
  margin: 0;
}

/* Formula display / 公式显示 */
.im-formula {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  margin-top: 12px;
  border-radius: var(--radius-md);
  background: rgba(59, 130, 246, 0.08);
  border: 1px solid rgba(59, 130, 246, 0.2);
  color: var(--primary, #3b82f6);
  font-size: 0.875rem;
  line-height: 1.5;
}

.im-formula-label {
  font-weight: 600;
  flex-shrink: 0;
}

.im-formula-expr {
  font-family: var(--font-mono);
  font-size: 0.875rem;
}

/* Layout / 布局 */
.im-layout {
  display: grid;
  grid-template-columns: minmax(280px, 380px) minmax(0, 1fr);
  gap: 24px;
  align-items: start;
}

/* Sidebar / 侧边栏 */
.im-sidebar {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* Card / 卡片 */
.im-card {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  background: var(--bg-surface);
}

.im-card-title {
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

/* Main area / 主区域 */
.im-main {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* Radio row / 单选行 */
.im-radio-row {
  display: flex;
  align-items: center;
  gap: 16px;
}

.im-radio-label {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  font-size: 0.875rem;
  color: var(--text-primary);
  white-space: nowrap;
}

.im-radio-label input[type="radio"] {
  accent-color: var(--primary);
  width: 14px;
  height: 14px;
}

/* Field / 字段 */
.im-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.im-label {
  font-size: 0.8125rem;
  color: var(--text-secondary);
  font-weight: 500;
}

.im-input {
  padding: 8px 10px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: 0.875rem;
  transition: border-color var(--transition-fast);
}

.im-input:focus {
  outline: none;
  border-color: var(--border-focus);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}

.im-select {
  padding: 8px 10px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: 0.875rem;
  transition: border-color var(--transition-fast);
}

.im-select:focus {
  outline: none;
  border-color: var(--border-focus);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}

/* Toggle / 切换 */
.im-toggle-label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-size: 0.875rem;
  color: var(--text-primary);
}

.im-toggle-label input[type="checkbox"] {
  accent-color: var(--primary);
  width: 14px;
  height: 14px;
}

/* Buttons / 按钮 */
.im-btn {
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

.im-btn:hover:not(:disabled) {
  border-color: var(--border-hover);
  box-shadow: var(--shadow-sm);
}

.im-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.im-btn-primary {
  padding: 12px 32px;
  border: none;
  background: var(--primary);
  color: var(--text-inverse);
  font-size: 0.9375rem;
  font-weight: 600;
}

.im-btn-primary:hover:not(:disabled) {
  opacity: 0.9;
  box-shadow: none;
}

/* Two-row layout: image1 + image2 side by side / 图像1与图像2并列 */
.im-two-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

/* Individual panel / 单个面板 */
.im-panel {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background: var(--bg-surface);
}

.im-panel-header {
  padding: 8px 12px;
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border);
}

.im-panel-title {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--text-primary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.im-panel-file-hint {
  font-weight: 400;
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-left: 8px;
}

.im-panel-image {
  flex: 1;
  min-height: 0;
}

.im-panel-stats {
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
.im-preview-loading {
  padding: 40px 24px;
  text-align: center;
  color: var(--text-muted);
  font-size: 0.9375rem;
}

.im-preview-empty {
  padding: 40px 24px;
  text-align: center;
  color: var(--text-muted);
  font-size: 0.9375rem;
}

/* Result panel / 结果面板 */
.im-result-panel {
  min-height: 280px;
}

/* Display bar below image / 图像下方显示栏 */
.im-display-bar {
  padding: 10px 14px;
}

.im-display-row {
  display: flex;
  align-items: flex-end;
  gap: 16px;
  flex-wrap: wrap;
}

.im-input-sm {
  width: 100px;
  padding: 4px 8px;
  font-size: 0.8125rem;
}

/* Error / 错误 */
.im-error {
  padding: 14px 18px;
  border-radius: var(--radius-md);
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: var(--error);
  font-size: 0.875rem;
}

.im-error p {
  margin: 0;
}

/* Empty state / 空状态 */
.im-empty {
  padding: 40px 24px;
  text-align: center;
  color: var(--text-muted);
  font-size: 0.9375rem;
}

.im-empty p {
  margin: 0;
}

/* Responsive / 响应式 */
@media (max-width: 1200px) {
  .im-two-row {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 960px) {
  .im-layout {
    grid-template-columns: 1fr;
  }

  .im-two-row {
    grid-template-columns: 1fr;
  }
}
</style>
