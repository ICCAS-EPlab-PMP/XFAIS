<template>
  <section class="calibrant-generator-page">
    <header class="cg-header">
      <h1>{{ t('calibrantGenerator.title') }}</h1>
      <p class="cg-subtitle">{{ t('calibrantGenerator.subtitle') }}</p>
    </header>

    <div class="cg-layout">
      <aside class="cg-sidebar">
        <!-- File selection / 文件选择 -->
        <div class="cg-section">
          <h2 class="cg-section-title">{{ t('calibrantGenerator.uploadFile') }}</h2>
          <button
            type="button"
            class="cg-file-btn"
            :disabled="state === 'running'"
            @click="handleSelectFile"
          >
            {{ t('calibrantGenerator.selectFile') }}
          </button>
          <div v-if="cifFilePath" class="cg-file-info">
            <span class="cg-file-name">{{ cifFileName }}</span>
            <button type="button" class="cg-clear-btn" @click="clearFile">
              ×
            </button>
          </div>
        </div>

        <!-- Intensity threshold / 强度阈值 -->
        <div class="cg-section">
          <h2 class="cg-section-title">{{ t('calibrantGenerator.intensityThreshold') }}</h2>
          <div class="cg-slider-group">
            <input
              type="range"
              class="cg-slider"
              min="0"
              max="10"
              step="0.1"
              v-model.number="intensityThreshold"
            />
            <span class="cg-slider-value">{{ intensityThreshold.toFixed(1) }}%</span>
          </div>
          <p class="cg-hint">{{ t('calibrantGenerator.thresholdHint') }}</p>
        </div>

        <!-- Generate button / 生成按钮 -->
        <div class="cg-action">
          <button
            type="button"
            class="cg-run-btn"
            :disabled="!canGenerate || state === 'running'"
            @click="handleGenerate"
          >
            {{ state === 'running' ? t('business.taskProgress.processing') : t('calibrantGenerator.peaksPreview') }}
          </button>
        </div>

        <!-- Progress / 进度 -->
        <TaskProgressBar
          v-if="state === 'running'"
          :task-id="taskId"
          :progress="progress"
          :message="progressMessage"
          @cancel="handleCancel"
        />
      </aside>

      <main class="cg-main">
        <!-- Error / 错误 -->
        <div v-if="state === 'error'" class="cg-error">
          <p>{{ errorMessage }}</p>
        </div>

        <!-- Crystal info / 晶体信息 -->
        <div v-if="formula" class="cg-crystal-info">
          <h2 class="cg-section-title">{{ t('calibrantGenerator.crystalInfo') }}</h2>
          <div class="cg-info-grid">
            <div class="cg-info-item">
              <span class="cg-info-label">{{ t('calibrantGenerator.formula') }}</span>
              <span class="cg-info-value">{{ formula }}</span>
            </div>
            <div class="cg-info-item">
              <span class="cg-info-label">{{ t('calibrantGenerator.latticeParams') }}</span>
              <span class="cg-info-value cg-mono">
                a={{ lp.a }}  b={{ lp.b }}  c={{ lp.c }}<br>
                α={{ lp.alpha }}°  β={{ lp.beta }}°  γ={{ lp.gamma }}°
              </span>
            </div>
          </div>
        </div>

        <!-- XRD Peak Chart / 衍射峰位图 -->
        <div v-if="allPeaks.length > 0" class="cg-chart-section">
          <div class="cg-chart-header">
            <h2 class="cg-section-title">{{ t('calibrantGenerator.xrdPattern') }}</h2>
            <div class="cg-scale-toggle">
              <button
                type="button"
                :class="['cg-scale-btn', { active: yScaleType === 'log' }]"
                @click="yScaleType = 'log'"
              >Log</button>
              <button
                type="button"
                :class="['cg-scale-btn', { active: yScaleType === 'linear' }]"
                @click="yScaleType = 'linear'"
              >Linear</button>
            </div>
          </div>
          <PlotlyChart
            :data="chartData"
            :layout="chartLayout"
            :dark-mode="true"
          />
        </div>

        <!-- Peaks table / 峰表 -->
        <div v-if="peaks.length > 0" class="cg-peaks-section">
          <h2 class="cg-section-title">
            {{ t('calibrantGenerator.peaksPreview') }}
            <span class="cg-peaks-count">{{ t('calibrantGenerator.peaksCount', { count: peaks.length }) }}</span>
          </h2>
          <div class="cg-table-wrapper">
            <table class="cg-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>{{ t('calibrantGenerator.table.dSpacing') }}</th>
                  <th>{{ t('calibrantGenerator.table.intensity') }}</th>
                  <th>{{ t('calibrantGenerator.table.twoTheta') }}</th>
                  <th>{{ t('calibrantGenerator.table.hkl') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(peak, idx) in peaks" :key="idx">
                  <td class="cg-mono">{{ idx + 1 }}</td>
                  <td class="cg-mono">{{ peak.dSpacing.toFixed(4) }}</td>
                  <td class="cg-mono">{{ peak.intensity.toFixed(1) }}%</td>
                  <td class="cg-mono">{{ peak.twoTheta.toFixed(2) }}</td>
                  <td class="cg-mono">{{ peak.hkl }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Download / 下载 -->
          <div class="cg-download">
            <button
              type="button"
              class="cg-download-btn"
              @click="handleDownload"
            >
              {{ t('calibrantGenerator.downloadFile') }}
            </button>
          </div>
        </div>

        <!-- Empty state / 空状态 -->
        <div v-if="state === 'idle' && !formula && !errorMessage" class="cg-empty">
          <p>{{ t('calibrantGenerator.uploadFile') }}</p>
        </div>
      </main>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref, computed, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useToast } from '@/lib/toast'
import TaskProgressBar from '@/components/business/TaskProgressBar.vue'
import PlotlyChart from '@/components/charts/PlotlyChart.vue'
import type { PlotData, PlotLayout } from 'plotly.js-dist-min'
import { useTransport } from '@/lib/transport'

const { t } = useI18n()
const toast = useToast()
const transport = useTransport()

type PageState = 'idle' | 'running' | 'done' | 'error'

const state = ref<PageState>('idle')
const taskId = ref<string | null>(null)
const progress = ref(0)
const progressMessage = ref<string | null>(null)
const errorMessage = ref('')

  const cifFilePath = ref<string | null>(null)
const intensityThreshold = ref(1.0)

const formula = ref('')
const latticeParams = ref({ a: 0, b: 0, c: 0, alpha: 0, beta: 0, gamma: 0 })
const peaks = ref<Array<{ dSpacing: number; intensity: number; twoTheta: number; hkl: string; multiplicity: number }>>([])
const allPeaks = ref<Array<{ dSpacing: number; intensity: number; twoTheta: number; hkl: string; multiplicity: number }>>([])
const dFileContent = ref('')
const patternTwoTheta = ref<number[]>([])
const patternIntensity = ref<number[]>([])
const yScaleType = ref<'log' | 'linear'>('linear')

const lp = computed(() => latticeParams.value)

const chartData = computed<PlotData[]>(() => {
  if (allPeaks.value.length === 0) return []
  const sorted = [...allPeaks.value].sort((a, b) => a.twoTheta - b.twoTheta)
  const floorVal = 0.01
  const xVals: number[] = []
  const yVals: number[] = []
  sorted.forEach(p => {
    xVals.push(p.twoTheta, p.twoTheta, null)
    yVals.push(floorVal, p.intensity, null)
  })
  const stickTrace: PlotData = {
    x: xVals, y: yVals,
    type: 'scatter' as const, mode: 'lines',
    line: { color: '#3b82f6', width: 2 },
    name: 'Peaks',
  }
  const thr = intensityThreshold.value
  const xMin = sorted[0].twoTheta
  const xMax = sorted[sorted.length - 1].twoTheta
  const thresholdTrace: PlotData = {
    x: [xMin, xMax], y: [thr, thr],
    type: 'scatter' as const, mode: 'lines',
    line: { dash: 'dash', color: '#ef4444', width: 1.5 },
    name: `Threshold: ${thr}%`,
  }
  return [stickTrace, thresholdTrace]
})

const chartLayout = computed<Partial<PlotLayout>>(() => {
  const isLog = yScaleType.value === 'log'
  const yaxis: Partial<PlotLayout['yaxis']> = {
    type: yScaleType.value,
    title: { text: 'Relative Intensity (%)' },
  }
  if (isLog) {
    // Log axis range in log10 space: start from 0.1% to show all low-intensity peaks
    // log scale range 使用 log10 值：从 0.1% 开始确保所有峰可见
    const maxY = Math.max(...allPeaks.value.map(p => p.intensity), intensityThreshold.value)
    yaxis.range = [-1, Math.ceil(Math.log10(maxY * 1.2))]
    yaxis.dtick = 1
  }
  return {
    title: { text: 'XRD Peak Positions / 衍射峰位图' },
    xaxis: { title: { text: '2θ (°)' } },
    yaxis,
    height: 300,
    margin: { t: 32, r: 16, b: 48, l: 60 },
    showlegend: true,
  }
})

const cifFileName = computed(() => {
  if (!cifFilePath.value) return ''
  const sep = cifFilePath.value.includes('/') ? '/' : '\\'
  const parts = cifFilePath.value.split(sep)
  return parts[parts.length - 1] || cifFilePath.value
})

const canGenerate = computed(() => cifFilePath.value !== null && state.value !== 'running')

let cleanupProgress: (() => void) | null = null
let cleanupResult: (() => void) | null = null
let cleanupError: (() => void) | null = null

function clearFile(): void {
  cifFilePath.value = null
  formula.value = ''
  peaks.value = []
  allPeaks.value = []
  dFileContent.value = ''
  patternTwoTheta.value = []
  patternIntensity.value = []
  state.value = 'idle'
  errorMessage.value = ''
}

async function handleSelectFile(): Promise<void> {
  const result = await transport.selectFiles({
    filters: [{ name: 'CIF Files', extensions: ['cif'] }],
    multiSelections: false,
  })
  if (!result) return
  const filePath = Array.isArray(result) ? result[0] : result
  if (!filePath) return

  cifFilePath.value = filePath
  state.value = 'idle'
  formula.value = ''
  peaks.value = []
  allPeaks.value = []
  dFileContent.value = ''
  patternTwoTheta.value = []
  patternIntensity.value = []
}

async function handleGenerate(): Promise<void> {
  if (!cifFilePath.value || state.value === 'running') return

  state.value = 'running'
  progress.value = 0
  progressMessage.value = null
  errorMessage.value = ''
  formula.value = ''
  peaks.value = []
  allPeaks.value = []
  dFileContent.value = ''
  patternTwoTheta.value = []
  patternIntensity.value = []

  cleanupListeners()

  try {
    const response = await transport.submitTask('calibrant_generate', {
      filePath: cifFilePath.value,
      intensityThreshold: intensityThreshold.value,
    })
    taskId.value = response.taskId

    cleanupProgress = transport.onTaskProgress(response.taskId, (payload) => {
      progress.value = payload.progress
      progressMessage.value = payload.message ?? null
    })

    cleanupResult = transport.onTaskResult(response.taskId, (payload) => {
      const data = payload.data as {
        status?: string
        formula?: string
        latticeParams?: { a: number; b: number; c: number; alpha: number; beta: number; gamma: number }
        peaks?: Array<{ dSpacing: number; intensity: number; twoTheta: number; hkl: string; multiplicity: number }>
        allPeaks?: Array<{ dSpacing: number; intensity: number; twoTheta: number; hkl: string; multiplicity: number }>
        dFileContent?: string
        twoTheta?: number[]
        intensity?: number[]
        message?: string
      }

      if (data?.status === 'error') {
        state.value = 'error'
        errorMessage.value = data.message || 'Generation failed.'
        toast.push({
          title: t('calibrantGenerator.error.parseError'),
          message: errorMessage.value,
          tone: 'error',
        })
        return
      }

      if (data?.formula) formula.value = data.formula
      if (data?.latticeParams) latticeParams.value = data.latticeParams
      if (data?.peaks) peaks.value = data.peaks
      if (data?.allPeaks) allPeaks.value = data.allPeaks
      if (data?.dFileContent) dFileContent.value = data.dFileContent
      if (data?.twoTheta) patternTwoTheta.value = data.twoTheta
      if (data?.intensity) patternIntensity.value = data.intensity

      taskId.value = null
      state.value = 'done'
      progress.value = 1
    })

    cleanupError = transport.onTaskError(response.taskId, (payload) => {
      taskId.value = null
      errorMessage.value = payload.error
      state.value = 'error'
      toast.push({
        title: t('calibrantGenerator.error.parseError'),
        message: payload.error,
        tone: 'error',
      })
    })
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : String(err)
    state.value = 'error'
    toast.push({
      title: t('calibrantGenerator.error.parseError'),
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

function handleDownload(): Promise<void> {
  return new Promise((resolve) => {
    if (!dFileContent.value) {
      toast.push({
        title: t('calibrantGenerator.error.noPeaks'),
        message: '',
        tone: 'warning',
      })
      resolve()
      return
    }

    const blob = new Blob([dFileContent.value], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    const baseName = formula.value ? formula.value.replace(/\s+/g, '_') : 'calibrant'
    a.download = `${baseName}.d`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    resolve()
  })
}

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
.calibrant-generator-page {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.cg-header {
  padding-bottom: 8px;
}

.cg-header h1 {
  font-size: 1.5rem;
  font-weight: 700;
  margin: 0 0 6px;
  color: var(--text-primary);
}

.cg-subtitle {
  font-size: 0.9375rem;
  color: var(--text-secondary);
  margin: 0;
}

.cg-layout {
  display: grid;
  grid-template-columns: minmax(280px, 340px) minmax(0, 1fr);
  gap: 24px;
  align-items: start;
}

.cg-sidebar {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.cg-main {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.cg-section {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.cg-section-title {
  font-size: 0.875rem;
  font-weight: 600;
  margin: 0;
  color: var(--text-primary);
}

.cg-file-btn {
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

.cg-file-btn:hover:not(:disabled) {
  border-color: var(--border-hover);
  box-shadow: var(--shadow-sm);
}

.cg-file-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.cg-file-info {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: var(--radius-md);
  background: var(--bg-surface-alt);
}

.cg-file-name {
  flex: 1;
  font-family: var(--font-mono);
  font-size: 0.8125rem;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cg-clear-btn {
  border: none;
  background: none;
  color: var(--text-muted);
  font-size: 1.25rem;
  cursor: pointer;
  padding: 0 4px;
  line-height: 1;
  transition: color var(--transition-fast);
}

.cg-clear-btn:hover {
  color: var(--error);
}

.cg-select {
  padding: 8px 10px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: 0.875rem;
  transition: border-color var(--transition-fast);
}

.cg-select:focus {
  outline: none;
  border-color: var(--border-focus);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}

.cg-slider-group {
  display: flex;
  align-items: center;
  gap: 12px;
}

.cg-slider {
  flex: 1;
  accent-color: var(--primary);
  height: 4px;
}

.cg-slider-value {
  font-family: var(--font-mono);
  font-size: 0.875rem;
  color: var(--text-primary);
  min-width: 48px;
  text-align: right;
}

.cg-hint {
  font-size: 0.75rem;
  color: var(--text-muted);
  margin: 0;
  line-height: 1.4;
}

.cg-action {
  display: flex;
}

.cg-run-btn {
  width: 100%;
  padding: 12px 24px;
  border-radius: var(--radius-md);
  border: none;
  background: var(--primary);
  color: var(--text-inverse);
  font-size: 0.9375rem;
  font-weight: 600;
  cursor: pointer;
  transition: opacity var(--transition-fast);
}

.cg-run-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.cg-run-btn:not(:disabled):hover {
  opacity: 0.9;
}

.cg-error {
  padding: 14px 18px;
  border-radius: var(--radius-md);
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: var(--error);
  font-size: 0.875rem;
}

.cg-error p {
  margin: 0;
}

.cg-crystal-info {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.cg-info-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.cg-info-item {
  display: flex;
  gap: 8px;
  font-size: 0.875rem;
}

.cg-info-label {
  color: var(--text-secondary);
  font-weight: 500;
  min-width: 120px;
}

.cg-info-value {
  color: var(--text-primary);
}

.cg-mono {
  font-family: var(--font-mono);
  font-size: 0.8125rem;
}

.cg-peaks-section {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.cg-peaks-count {
  font-weight: 400;
  font-size: 0.8125rem;
  color: var(--text-muted);
  margin-left: 8px;
}

.cg-table-wrapper {
  overflow-x: auto;
  overflow-y: auto;
  max-height: 360px;
}

.cg-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8125rem;
}

.cg-table th {
  text-align: left;
  padding: 8px 10px;
  border-bottom: 2px solid var(--border);
  color: var(--text-secondary);
  font-weight: 600;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  white-space: nowrap;
}

.cg-table td {
  padding: 6px 10px;
  border-bottom: 1px solid var(--border);
  color: var(--text-primary);
  vertical-align: middle;
}

.cg-table tbody tr:hover {
  background: var(--bg-surface-alt);
}

.cg-chart-section {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.cg-chart-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.cg-scale-toggle {
  display: flex;
  gap: 0;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.cg-scale-btn {
  padding: 4px 12px;
  border: none;
  background: var(--bg-surface);
  color: var(--text-secondary);
  font-size: 0.75rem;
  font-weight: 500;
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast);
}

.cg-scale-btn:not(:last-child) {
  border-right: 1px solid var(--border);
}

.cg-scale-btn.active {
  background: var(--primary);
  color: var(--text-inverse);
}

.cg-download {
  display: flex;
  justify-content: flex-end;
  padding-top: 8px;
}

.cg-download-btn {
  padding: 10px 24px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.cg-download-btn:hover {
  border-color: var(--primary);
  box-shadow: var(--shadow-sm);
}

.cg-empty {
  padding: 60px 24px;
  text-align: center;
  color: var(--text-muted);
  font-size: 0.9375rem;
}

.cg-empty p {
  margin: 0;
}

@media (max-width: 960px) {
  .cg-layout {
    grid-template-columns: 1fr;
  }
}
</style>
