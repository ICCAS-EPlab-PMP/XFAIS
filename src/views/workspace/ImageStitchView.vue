<template>
  <section class="is-page">
    <!-- Header / 页头 -->
    <header class="is-header">
      <h1>{{ t('imageStitch.title') }}</h1>
      <p class="is-subtitle">{{ t('imageStitch.subtitle') }}</p>
    </header>

    <div class="is-layout">
      <!-- ===== Sidebar: controls / 侧边栏：控制面板 ===== -->
      <aside class="is-sidebar">
        <!-- Images list / 图像列表 -->
        <div class="is-card">
          <div class="is-card-header">
            <h3 class="is-card-title">{{ t('imageStitch.images') }}</h3>
            <button type="button" class="is-btn is-btn-sm" @click="addImage">
              + {{ t('imageStitch.addImage') }}
            </button>
          </div>

          <div
            v-for="(img, idx) in images"
            :key="img.id"
            class="is-image-row"
          >
            <div class="is-image-row-head">
              <span class="is-image-index">#{{ idx + 1 }}</span>
              <button
                v-if="images.length > 2"
                type="button"
                class="is-btn-icon"
                :title="t('imageStitch.removeImage')"
                @click="removeImage(idx)"
              >
                &times;
              </button>
            </div>

            <FileDialogButton
              v-model="img.path"
              mode="openFile"
              :label="t('imageStitch.selectFile')"
              :filters="dataFileFilters"
            />

            <div class="is-image-fields">
              <div class="is-field">
                <label class="is-label">{{ t('imageStitch.pixelSize') }} (µm)</label>
                <input
                  v-model.number="img.pixelSizeUm"
                  type="number"
                  class="is-input"
                  step="any"
                  min="0"
                />
              </div>
              <div class="is-field">
                <label class="is-label">{{ t('imageStitch.offsetX') }}</label>
                <input
                  v-model.number="img.offsetX"
                  type="number"
                  class="is-input"
                  step="any"
                />
              </div>
              <div class="is-field">
                <label class="is-label">{{ t('imageStitch.offsetY') }}</label>
                <input
                  v-model.number="img.offsetY"
                  type="number"
                  class="is-input"
                  step="any"
                />
              </div>
            </div>
          </div>

          <p v-if="offsetMode === 'relative'" class="is-hint">
            {{ t('imageStitch.relativeHint') }}
          </p>
        </div>

        <!-- Stitch options / 拼接选项 -->
        <div class="is-card">
          <h3 class="is-card-title">{{ t('imageStitch.options') }}</h3>

          <div class="is-field">
            <label class="is-label">{{ t('imageStitch.offsetMode') }}</label>
            <div class="is-radio-row">
              <label class="is-radio-label">
                <input v-model="offsetMode" type="radio" value="absolute" />
                <span>{{ t('imageStitch.modeAbsolute') }}</span>
              </label>
              <label class="is-radio-label">
                <input v-model="offsetMode" type="radio" value="relative" />
                <span>{{ t('imageStitch.modeRelative') }}</span>
              </label>
            </div>
          </div>

          <div class="is-field">
            <label class="is-label">{{ t('imageStitch.offsetUnit') }}</label>
            <select v-model="offsetUnit" class="is-select">
              <option value="um">µm</option>
              <option value="mm">mm</option>
            </select>
          </div>

          <div class="is-field">
            <label class="is-label">{{ t('imageStitch.strategy') }}</label>
            <select v-model="strategy" class="is-select">
              <option value="mean">{{ t('imageStitch.strategyMean') }}</option>
              <option value="sum">{{ t('imageStitch.strategySum') }}</option>
              <option value="max">{{ t('imageStitch.strategyMax') }}</option>
              <option value="first">{{ t('imageStitch.strategyFirst') }}</option>
            </select>
          </div>
        </div>

        <!-- Display settings / 显示设置 -->
        <div class="is-card">
          <h3 class="is-card-title">{{ t('imageStitch.display') }}</h3>
          <div class="is-field">
            <label class="is-label">{{ t('imageStitch.colormap') }}</label>
            <select v-model="colormap" class="is-select">
              <option v-for="cm in colormapOptions" :key="cm" :value="cm">{{ cm }}</option>
            </select>
          </div>
          <label class="is-toggle-label">
            <input v-model="useLog" type="checkbox" />
            <span>{{ t('imageStitch.logScale') }}</span>
          </label>
          <div class="is-radio-row">
            <label class="is-radio-label">
              <input v-model="climMode" type="radio" value="auto" />
              <span>{{ t('imageStitch.contrastAuto') }}</span>
            </label>
            <label class="is-radio-label">
              <input v-model="climMode" type="radio" value="manual" />
              <span>{{ t('imageStitch.contrastManual') }}</span>
            </label>
          </div>
          <template v-if="climMode === 'manual'">
            <div class="is-field-row">
              <div class="is-field">
                <label class="is-label">Min</label>
                <input v-model.number="climMin" type="number" class="is-input is-input-sm" step="any" />
              </div>
              <div class="is-field">
                <label class="is-label">Max</label>
                <input v-model.number="climMax" type="number" class="is-input is-input-sm" step="any" />
              </div>
            </div>
          </template>
        </div>

        <!-- Export / 导出 -->
        <div class="is-card">
          <h3 class="is-card-title">{{ t('imageStitch.export') }}</h3>
          <FileDialogButton
            v-model="outputDir"
            mode="openFolder"
            :label="t('imageStitch.outputDir')"
          />
          <div class="is-field">
            <label class="is-label">{{ t('imageStitch.outputFormat') }}</label>
            <select v-model="outputFormat" class="is-select">
              <option value="tif">TIFF</option>
              <option value="edf">EDF</option>
              <option value="h5">HDF5</option>
            </select>
          </div>
          <button
            type="button"
            class="is-btn"
            :disabled="!canSave"
            @click="handleSave"
          >
            {{ t('imageStitch.saveResult') }}
          </button>
        </div>

        <!-- Execute / 执行 -->
        <div class="is-card">
          <button
            type="button"
            class="is-btn is-btn-primary"
            :disabled="!canCompute"
            @click="handleCompute"
          >
            {{ t('imageStitch.execute') }}
          </button>
        </div>
      </aside>

      <!-- ===== Main area / 主区域 ===== -->
      <main class="is-main">
        <!-- Result panel / 结果面板 -->
        <div class="is-panel is-result-panel">
          <div class="is-panel-header">
            <span class="is-panel-title">{{ t('imageStitch.tabResult') }}</span>
            <span v-if="stitchMeta" class="is-panel-meta">
              {{ stitchMeta.canvas_width }} × {{ stitchMeta.canvas_height }} px
              <template v-if="stitchMeta.overlaps"> · {{ t('imageStitch.hasOverlap') }}</template>
            </span>
          </div>
          <div v-if="resultPreviewLoading" class="is-preview-loading">
            {{ t('imageStitch.loading') }}
          </div>
          <div v-else-if="resultPreviewUrl" class="is-panel-image">
            <ImagePreview
              :image-b64="resultPreviewUrl"
              :show-colorbar="true"
              :placeholder="t('imageStitch.noImage')"
            />
          </div>
          <div v-else class="is-preview-empty">
            {{ t('imageStitch.noResult') }}
          </div>
          <div v-if="resultPreviewStats" class="is-panel-stats">
            <span>Min: {{ formatSci(resultPreviewStats.min) }}</span>
            <span>Max: {{ formatSci(resultPreviewStats.max) }}</span>
            <span v-if="stitchMeta">
              {{ t('imageStitch.coverage') }}: {{ (stitchMeta.coverage_ratio * 100).toFixed(1) }}%
            </span>
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
        <div v-if="state === 'error'" class="is-error">
          <p>{{ t('imageStitch.errorPrefix') }} {{ errorMessage }}</p>
        </div>

        <!-- Empty state / 空状态 -->
        <div v-if="state === 'idle' && !resultPreviewUrl" class="is-empty">
          <p>{{ t('imageStitch.emptyState') }}</p>
        </div>
      </main>
    </div>
  </section>
</template>

<script setup lang="ts">
/**
 * ImageStitchView.vue — 多探测器位置图像拼接页面
 * Image Stitch page: stitch multiple detector images taken at different
 * spatial positions into a single large canvas using pixel offsets.
 */
import { ref, computed, onUnmounted } from 'vue'
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
  mean?: number
}

interface StitchMeta {
  canvas_width: number
  canvas_height: number
  n_images: number
  strategy: string
  coverage_ratio: number
  overlaps: boolean
}

interface ImageEntry {
  id: number
  path: string | null
  pixelSizeUm: number
  offsetX: number
  offsetY: number
}

type PageState = 'idle' | 'running' | 'done' | 'error'
type OffsetMode = 'absolute' | 'relative'
type OffsetUnit = 'um' | 'mm'

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

// === Images list / 图像列表 ===

let nextImageId = 1
function makeImageEntry(): ImageEntry {
  return {
    id: nextImageId++,
    path: null,
    pixelSizeUm: 172,
    offsetX: 0,
    offsetY: 0,
  }
}

// Start with 2 empty entries / 初始 2 个空条目
const images = ref<ImageEntry[]>([makeImageEntry(), makeImageEntry()])

function addImage(): void {
  images.value.push(makeImageEntry())
}

function removeImage(idx: number): void {
  if (images.value.length <= 2) return
  images.value.splice(idx, 1)
}

// === Options / 选项 ===

const offsetMode = ref<OffsetMode>('absolute')
const offsetUnit = ref<OffsetUnit>('um')
const strategy = ref<'mean' | 'sum' | 'max' | 'first'>('mean')

// === Display settings / 显示设置 ===

const colormap = ref('smooth_WAXS_foxtrot')
const useLog = ref(false)
const climMode = ref<'auto' | 'manual'>('auto')
const climMin = ref(0)
const climMax = ref(1)

// === Result preview / 结果预览 ===

const resultPreviewUrl = ref<string | null>(null)
const resultPreviewStats = ref<PreviewStats | null>(null)
const resultPreviewLoading = ref(false)
const stitchMeta = ref<StitchMeta | null>(null)

// === Export / 导出 ===

const outputDir = ref<string | null>(null)
const outputFormat = ref<'h5' | 'edf' | 'tif'>('tif')

// === File filters / 文件过滤器 ===

const dataFileFilters = [
  { name: 'Detector Images', extensions: ['edf', 'tif', 'tiff', 'h5', 'hdf5'] },
]

// === Cleanup functions / 清理函数 ===

let cleanupProgress: (() => void) | null = null
let cleanupResult: (() => void) | null = null
let cleanupError: (() => void) | null = null
let cleanupBinaryData: (() => void) | null = null

// === Computed / 计算属性 ===

const validImages = computed(() =>
  images.value.filter(img => !!img.path && img.pixelSizeUm > 0)
)

const canCompute = computed(() => {
  if (state.value === 'running') return false
  return validImages.value.length >= 2
})

const canSave = computed(() => {
  return state.value === 'done' && !!outputDir.value && validImages.value.length >= 2
})

// === Helpers / 辅助函数 ===

function formatSci(value: number): string {
  if (!Number.isFinite(value)) return '—'
  if (value === 0) return '0'
  return value.toExponential(3)
}

/**
 * Build the payload `images` array. Converts user-entered offsets to absolute
 * microns: (a) unit conversion (mm→µm), (b) relative→absolute accumulation.
 * 构建 payload 的 images 数组。将用户输入的偏移转换为绝对微米值：
 * (a) 单位换算（mm→µm）；(b) 相对偏移累加为绝对偏移。
 */
function buildImagesPayload(): Array<{
  path: string
  pixel_size_um: number
  offset_x_um: number
  offset_y_um: number
}> {
  const unitFactor = offsetUnit.value === 'mm' ? 1000.0 : 1.0
  const valid = validImages.value

  // First entry's offset is always the origin anchor (its offset is taken as-is,
  // or zeroed in relative mode since it's the starting point).
  // 第一项的偏移恒为起点（相对模式下归零，绝对模式下按输入值）。
  let accX = 0
  let accY = 0
  const out: Array<{ path: string; pixel_size_um: number; offset_x_um: number; offset_y_um: number }> = []

  valid.forEach((img, idx) => {
    const rawX = (Number.isFinite(img.offsetX) ? img.offsetX : 0) * unitFactor
    const rawY = (Number.isFinite(img.offsetY) ? img.offsetY : 0) * unitFactor
    if (offsetMode.value === 'relative') {
      if (idx === 0) {
        accX = 0
        accY = 0
      } else {
        accX += rawX
        accY += rawY
      }
      out.push({
        path: img.path as string,
        pixel_size_um: img.pixelSizeUm,
        offset_x_um: accX,
        offset_y_um: accY,
      })
    } else {
      out.push({
        path: img.path as string,
        pixel_size_um: img.pixelSizeUm,
        offset_x_um: rawX,
        offset_y_um: rawY,
      })
    }
  })

  return out
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

// === Compute execution / 执行拼接 ===

async function handleCompute(): Promise<void> {
  if (state.value === 'running') return
  if (validImages.value.length < 2) {
    toast.push({
      title: t('imageStitch.errorTitle'),
      message: t('imageStitch.needTwoImages'),
      tone: 'error',
    })
    return
  }

  state.value = 'running'
  progress.value = 0
  progressMessage.value = null
  errorMessage.value = ''

  const params: Record<string, unknown> = {
    action: 'compute',
    images: buildImagesPayload(),
    strategy: strategy.value,
    ...getRenderSettingsParams(),
  }

  try {
    const response = await transport.submitTask('image_stitch', params)
    taskId.value = response.taskId

    cleanupProgress = transport.onTaskProgress(response.taskId, (payload) => {
      progress.value = payload.progress
      progressMessage.value = payload.message ?? null
    })

    cleanupBinaryData = transport.onTaskBinaryData(response.taskId, (payload: TaskBinaryPayload) => {
      if (payload.data) {
        const blob = new Blob([payload.data], { type: payload.mime || 'image/png' })
        if (resultPreviewUrl.value?.startsWith('blob:')) URL.revokeObjectURL(resultPreviewUrl.value)
        resultPreviewUrl.value = URL.createObjectURL(blob)
      }
    })

    cleanupResult = transport.onTaskResult(response.taskId, (payload) => {
      const data = payload.data as { stats?: PreviewStats; stitch_meta?: StitchMeta }
      if (data.stats) {
        resultPreviewStats.value = data.stats
        if (climMode.value === 'auto') {
          climMin.value = data.stats.min
          climMax.value = data.stats.max
        }
      }
      if (data.stitch_meta) {
        stitchMeta.value = data.stitch_meta
      }
      resultPreviewLoading.value = false
      taskId.value = null
      state.value = 'done'
      progress.value = 1
      toast.push({
        title: t('imageStitch.successTitle'),
        message: t('imageStitch.computeComplete'),
        tone: 'success',
      })
    })

    cleanupError = transport.onTaskError(response.taskId, (payload) => {
      taskId.value = null
      errorMessage.value = payload.error
      state.value = 'error'
      resultPreviewLoading.value = false
      toast.push({
        title: t('imageStitch.errorTitle'),
        message: payload.error,
        tone: 'error',
      })
    })
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : String(err)
    state.value = 'error'
    toast.push({
      title: t('imageStitch.errorTitle'),
      message: errorMessage.value,
      tone: 'error',
    })
  }
}

// === Save result / 保存结果 ===

async function handleSave(): Promise<void> {
  if (!outputDir.value || validImages.value.length < 2) return

  const params: Record<string, unknown> = {
    action: 'save',
    images: buildImagesPayload(),
    strategy: strategy.value,
    output_dir: outputDir.value,
    output_format: outputFormat.value,
  }

  try {
    const response = await transport.submitTask('image_stitch', params)

    const unsubResult = transport.onTaskResult(response.taskId, () => {
      toast.push({
        title: t('imageStitch.successTitle'),
        message: t('imageStitch.savedOk'),
        tone: 'success',
      })
      unsubResult()
      unsubError()
    })

    const unsubError = transport.onTaskError(response.taskId, (payload) => {
      toast.push({
        title: t('imageStitch.errorTitle'),
        message: payload.error,
        tone: 'error',
      })
      unsubResult()
      unsubError()
    })
  } catch (err) {
    toast.push({
      title: t('imageStitch.errorTitle'),
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
  cleanupBinaryData?.()
  cleanupBinaryData = null
}

onUnmounted(() => {
  if (resultPreviewUrl.value?.startsWith('blob:')) URL.revokeObjectURL(resultPreviewUrl.value)
  cleanupListeners()
})
</script>

<style scoped>
.is-page {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.is-header {
  padding-bottom: 8px;
}

.is-header h1 {
  font-size: 1.5rem;
  font-weight: 700;
  margin: 0 0 6px;
  color: var(--text-primary);
}

.is-subtitle {
  font-size: 0.9375rem;
  color: var(--text-secondary);
  margin: 0;
}

/* Layout / 布局 */
.is-layout {
  display: grid;
  grid-template-columns: minmax(300px, 420px) minmax(0, 1fr);
  gap: 24px;
  align-items: start;
}

/* Sidebar / 侧边栏 */
.is-sidebar {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* Card / 卡片 */
.is-card {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  background: var(--bg-surface);
}

.is-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.is-card-title {
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

/* Image row / 图像行 */
.is-image-row {
  border: 1px dashed var(--border);
  border-radius: var(--radius-md);
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  background: var(--bg-surface);
}

.is-image-row-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.is-image-index {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--primary, #3b82f6);
  font-family: var(--font-mono);
}

.is-image-fields {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 8px;
}

.is-field-row {
  display: flex;
  gap: 12px;
}

.is-hint {
  font-size: 0.75rem;
  color: var(--text-muted);
  margin: 0;
  line-height: 1.5;
  padding: 6px 10px;
  background: rgba(245, 158, 11, 0.08);
  border-radius: var(--radius-sm);
  border: 1px solid rgba(245, 158, 11, 0.2);
}

/* Main area / 主区域 */
.is-main {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* Field / 字段 */
.is-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.is-label {
  font-size: 0.8125rem;
  color: var(--text-secondary);
  font-weight: 500;
}

.is-input {
  padding: 8px 10px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: 0.875rem;
  width: 100%;
  box-sizing: border-box;
  transition: border-color var(--transition-fast);
}

.is-input:focus {
  outline: none;
  border-color: var(--border-focus);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}

.is-input-sm {
  width: 100px;
  padding: 4px 8px;
  font-size: 0.8125rem;
}

.is-select {
  padding: 8px 10px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: 0.875rem;
  transition: border-color var(--transition-fast);
}

.is-select:focus {
  outline: none;
  border-color: var(--border-focus);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}

/* Radio / 单选 */
.is-radio-row {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.is-radio-label {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  font-size: 0.875rem;
  color: var(--text-primary);
  white-space: nowrap;
}

.is-radio-label input[type="radio"] {
  accent-color: var(--primary);
  width: 14px;
  height: 14px;
}

/* Toggle / 切换 */
.is-toggle-label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-size: 0.875rem;
  color: var(--text-primary);
}

.is-toggle-label input[type="checkbox"] {
  accent-color: var(--primary);
  width: 14px;
  height: 14px;
}

/* Buttons / 按钮 */
.is-btn {
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

.is-btn:hover:not(:disabled) {
  border-color: var(--border-hover);
  box-shadow: var(--shadow-sm);
}

.is-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.is-btn-sm {
  padding: 4px 10px;
  font-size: 0.75rem;
}

.is-btn-primary {
  padding: 12px 32px;
  border: none;
  background: var(--primary);
  color: var(--text-inverse);
  font-size: 0.9375rem;
  font-weight: 600;
}

.is-btn-primary:hover:not(:disabled) {
  opacity: 0.9;
  box-shadow: none;
}

.is-btn-icon {
  border: none;
  background: transparent;
  color: var(--text-muted);
  font-size: 1.25rem;
  line-height: 1;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: var(--radius-sm);
}

.is-btn-icon:hover {
  color: var(--error);
  background: rgba(239, 68, 68, 0.1);
}

/* Panel / 面板 */
.is-panel {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background: var(--bg-surface);
}

.is-panel-header {
  padding: 8px 12px;
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  gap: 12px;
}

.is-panel-title {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--text-primary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.is-panel-meta {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--text-muted);
}

.is-panel-image {
  flex: 1;
  min-height: 0;
}

.is-panel-stats {
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
.is-preview-loading {
  padding: 40px 24px;
  text-align: center;
  color: var(--text-muted);
  font-size: 0.9375rem;
}

.is-preview-empty {
  padding: 40px 24px;
  text-align: center;
  color: var(--text-muted);
  font-size: 0.9375rem;
}

.is-result-panel {
  min-height: 320px;
}

/* Error / 错误 */
.is-error {
  padding: 14px 18px;
  border-radius: var(--radius-md);
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: var(--error);
  font-size: 0.875rem;
}

.is-error p {
  margin: 0;
}

/* Empty state / 空状态 */
.is-empty {
  padding: 40px 24px;
  text-align: center;
  color: var(--text-muted);
  font-size: 0.9375rem;
}

.is-empty p {
  margin: 0;
}

/* Responsive / 响应式 */
@media (max-width: 1100px) {
  .is-image-fields {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 960px) {
  .is-layout {
    grid-template-columns: 1fr;
  }
}
</style>
