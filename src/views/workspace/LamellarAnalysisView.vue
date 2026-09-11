<template>
  <section class="lm-page">
    <!-- Header / 页头 -->
    <header class="lm-header">
      <h1>{{ t('lamellar.title') }}</h1>
      <p class="lm-subtitle">{{ t('lamellar.subtitle') }}</p>
    </header>

    <div class="lm-layout">
      <!-- ===== Sidebar: controls / 侧边栏：控制面板 ===== -->
      <aside class="lm-sidebar">
        <!-- Input mode / 输入模式 -->
        <div class="lm-card">
          <h3 class="lm-card-title">{{ t('lamellar.inputMode') }}</h3>
          <div class="lm-radio-row">
            <label class="lm-radio-label">
              <input v-model="inputMode" type="radio" value="image" />
              <span>{{ t('lamellar.modeImage') }}</span>
            </label>
            <label class="lm-radio-label">
              <input v-model="inputMode" type="radio" value="curves" />
              <span>{{ t('lamellar.modeCurves') }}</span>
            </label>
          </div>
        </div>

        <!-- Image-mode inputs / 图像模式输入 -->
        <template v-if="inputMode === 'image'">
          <div class="lm-card">
            <h3 class="lm-card-title">{{ t('lamellar.selectFile') }}</h3>
            <FileDialogButton
              v-model="filePath"
              mode="openFile"
              :label="t('lamellar.selectFile')"
              :filters="dataFileFilters"
            />
          </div>

          <details class="lm-card lm-details">
            <summary>{{ t('lamellar.geometry') }}</summary>
            <GeometryForm v-model="geometry" />
          </details>

          <details class="lm-card lm-details">
            <summary>{{ t('lamellar.mask') }}</summary>
            <MaskBuilderForm v-model="maskConfig" :bare="true" />
          </details>

          <div class="lm-card">
            <h3 class="lm-card-title">{{ t('lamellar.qRange') }}</h3>
            <div class="lm-field">
              <label class="lm-label">{{ t('lamellar.qUnitLabel') }}</label>
              <select v-model="qUnit" class="lm-select">
                <option value="nm^-1">q (nm⁻¹)</option>
                <option value="A^-1">q (Å⁻¹)</option>
              </select>
            </div>
            <div class="lm-field-row">
              <div class="lm-field">
                <label class="lm-label">{{ t('lamellar.qMin') }}</label>
                <input v-model.number="radialMin" type="number" class="lm-input" step="any" />
              </div>
              <div class="lm-field">
                <label class="lm-label">{{ t('lamellar.qMax') }}</label>
                <input v-model.number="radialMax" type="number" class="lm-input" step="any" />
              </div>
            </div>
            <p class="lm-hint">{{ t('lamellar.qRangeHint') }}</p>
            <div class="lm-field">
              <label class="lm-label">{{ t('lamellar.npt') }}</label>
              <input v-model.number="npt" type="number" class="lm-input" min="64" step="1" />
            </div>
          </div>
        </template>

        <!-- Curves-mode inputs / 曲线模式输入 -->
        <div v-else class="lm-card">
          <h3 class="lm-card-title">{{ t('lamellar.curvesInput') }}</h3>
          <p class="lm-hint">{{ t('lamellar.curvesHint') }}</p>
          <textarea
            v-model="curvesText"
            class="lm-textarea"
            :placeholder="t('lamellar.curvesPlaceholder')"
            rows="6"
          ></textarea>
          <div class="lm-btn-row">
            <button type="button" class="lm-btn lm-btn-sm" @click="parseCurves">
              {{ t('lamellar.parse') }}
            </button>
            <FileDialogButton
              v-model="curvesFilePath"
              mode="openFile"
              :label="t('lamellar.loadFile')"
              :filters="[{ name: 'Data', extensions: ['csv', 'txt', 'dat'] }]"
              @update:model-value="loadCurvesFile"
            />
          </div>
          <div class="lm-field">
            <label class="lm-label">{{ t('lamellar.qUnitLabel') }}</label>
            <select v-model="qUnit" class="lm-select">
              <option value="nm^-1">q (nm⁻¹)</option>
              <option value="A^-1">q (Å⁻¹)</option>
            </select>
          </div>
          <p v-if="parsedQ.length > 0" class="lm-hint lm-hint-ok">
            {{ t('lamellar.parsedN', { n: parsedQ.length }) }}
          </p>
        </div>

        <!-- Background / 背景 -->
        <div class="lm-card">
          <h3 class="lm-card-title">{{ t('lamellar.background') }}</h3>
          <div class="lm-field">
            <select v-model="bgMode" class="lm-select">
              <option value="auto">{{ t('lamellar.bgAuto') }}</option>
              <option value="constant">{{ t('lamellar.bgConstant') }}</option>
              <option value="none">{{ t('lamellar.bgNone') }}</option>
            </select>
          </div>
          <div v-if="bgMode === 'constant'" class="lm-field">
            <label class="lm-label">{{ t('lamellar.bgLevel') }}</label>
            <input v-model.number="bgConstant" type="number" class="lm-input" step="any" />
          </div>
          <p class="lm-hint">{{ t('lamellar.bgHint') }}</p>
        </div>

        <!-- Methods / 方法 -->
        <div class="lm-card">
          <h3 class="lm-card-title">{{ t('lamellar.methods') }}</h3>
          <label class="lm-toggle-label">
            <input type="checkbox" :checked="methods.includes('bragg')" @change="toggleMethod('bragg')" />
            <span>{{ t('lamellar.mBragg') }}</span>
          </label>
          <label class="lm-toggle-label">
            <input type="checkbox" :checked="methods.includes('correlation')" @change="toggleMethod('correlation')" />
            <span>{{ t('lamellar.mCorrelation') }}</span>
          </label>

          <template v-if="methods.includes('bragg')">
            <div class="lm-field-row">
              <div class="lm-field">
                <label class="lm-label">{{ t('lamellar.peakQMin') }}</label>
                <input v-model.number="peakQMin" type="number" class="lm-input" step="any" placeholder="—" />
              </div>
              <div class="lm-field">
                <label class="lm-label">{{ t('lamellar.peakQMax') }}</label>
                <input v-model.number="peakQMax" type="number" class="lm-input" step="any" placeholder="—" />
              </div>
            </div>
            <p class="lm-hint">{{ t('lamellar.peakWindowHint') }}</p>
          </template>

          <template v-if="methods.includes('correlation')">
            <div class="lm-field">
              <label class="lm-label">{{ t('lamellar.minorityPhase') }}</label>
              <select v-model="minorityPhase" class="lm-select">
                <option value="crystalline">{{ t('lamellar.minorityCrystalline') }}</option>
                <option value="amorphous">{{ t('lamellar.minorityAmorphous') }}</option>
              </select>
              <p class="lm-hint">{{ t('lamellar.minorityHint') }}</p>
            </div>
          </template>
        </div>
      </aside>

      <!-- ===== Main: run + results / 主区：运行 + 结果 ===== -->
      <main class="lm-main">
        <div class="lm-run-row">
          <button
            type="button"
            class="lm-btn lm-btn-primary"
            :disabled="!canRun || isRunning"
            @click="handleRun"
          >
            {{ isRunning ? t('lamellar.running') : t('lamellar.run') }}
          </button>
          <button v-if="isRunning" type="button" class="lm-btn" @click="handleCancel">
            {{ t('lamellar.cancel') }}
          </button>
          <button v-if="resultData" type="button" class="lm-btn" @click="exportCsv">
            {{ t('lamellar.exportCsv') }}
          </button>
        </div>

        <TaskProgressBar v-if="isRunning || progress > 0" :progress="progress" :message="progressMessage ?? ''" />

        <div v-if="errorMessage" class="lm-error">
          <strong>{{ t('lamellar.errorTitle') }}:</strong> {{ errorMessage }}
        </div>

        <!-- Warnings / 警告 -->
        <div v-if="resultData?.warnings?.length" class="lm-warnings">
          <h3 class="lm-card-title">{{ t('lamellar.warnings') }}</h3>
          <ul>
            <li v-for="(w, idx) in resultData.warnings" :key="idx">{{ w }}</li>
          </ul>
        </div>

        <!-- SAXS profile chart / SAXS 曲线 -->
        <div v-if="profileTraces.length > 0" class="lm-chart">
          <h2 class="lm-section-title">{{ t('lamellar.profileChartTitle') }}</h2>
          <LineChart
            :traces="profileTraces"
            :x-label="qAxisLabel"
            :y-label="t('lamellar.intensityAxis')"
            :title="t('lamellar.profileChartTitle')"
          />
        </div>

        <!-- Correlation function chart / 相关函数 -->
        <div v-if="gammaTraces.length > 0" class="lm-chart">
          <h2 class="lm-section-title">{{ t('lamellar.gammaChartTitle') }}</h2>
          <LineChart
            :traces="gammaTraces"
            :x-label="t('lamellar.rAxis')"
            :y-label="t('lamellar.gammaAxis')"
            :title="t('lamellar.gammaChartTitle')"
          />
        </div>

        <!-- Results cards / 结果卡片 -->
        <div v-if="resultData?.results?.length" class="lm-results">
          <h2 class="lm-section-title">{{ t('lamellar.resultsTitle') }}</h2>
          <div class="lm-result-grid">
            <div v-for="(r, idx) in resultData.results" :key="idx" class="lm-result-card">
              <h3 class="lm-result-method">{{ r.method === 'bragg' ? t('lamellar.mBragg') : t('lamellar.mCorrelation') }}</h3>
              <div class="lm-result-row">
                <span class="lm-result-key">{{ t('lamellar.longPeriod') }}</span>
                <span class="lm-result-val">{{ fmt(r.long_period_nm) }} nm</span>
              </div>
              <div v-if="r.q_star_nm !== undefined && r.q_star_nm !== null" class="lm-result-row">
                <span class="lm-result-key">q*</span>
                <span class="lm-result-val">{{ fmt(r.q_star_nm) }} nm⁻¹</span>
              </div>
              <div v-if="r.fwhm_nm_inv !== undefined && r.fwhm_nm_inv !== null" class="lm-result-row">
                <span class="lm-result-key">Δq (FWHM)</span>
                <span class="lm-result-val">{{ fmt(r.fwhm_nm_inv) }} nm⁻¹</span>
              </div>
              <div v-if="r.n_repeats_estimate !== undefined && r.n_repeats_estimate !== null" class="lm-result-row">
                <span class="lm-result-key">{{ t('lamellar.nRepeats') }}</span>
                <span class="lm-result-val">{{ fmt(r.n_repeats_estimate) }}</span>
              </div>
              <div v-if="r.l_crystalline_nm !== undefined && r.l_crystalline_nm !== null" class="lm-result-row">
                <span class="lm-result-key">{{ t('lamellar.lc') }}</span>
                <span class="lm-result-val">{{ fmt(r.l_crystalline_nm) }} nm</span>
              </div>
              <div v-if="r.l_amorphous_nm !== undefined && r.l_amorphous_nm !== null" class="lm-result-row">
                <span class="lm-result-key">{{ t('lamellar.la') }}</span>
                <span class="lm-result-val">{{ fmt(r.l_amorphous_nm) }} nm</span>
              </div>
              <div v-if="r.crystallinity_stack !== undefined && r.crystallinity_stack !== null" class="lm-result-row">
                <span class="lm-result-key">{{ t('lamellar.phiC') }}</span>
                <span class="lm-result-val">{{ (r.crystallinity_stack * 100).toFixed(1) }}%</span>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  </section>
</template>

<script setup lang="ts">
/**
 * LamellarAnalysisView.vue — SAXS 片晶结构分析 (v0.2.5)
 * Long period & lamellar thickness from I(q): Bragg peak + 1-D correlation
 * function (γ₁). Image mode integrates I(q) first; curves mode takes a pasted
 * or loaded profile.
 * 由 I(q) 提取长周期与片晶厚度：Bragg 峰法 + 一维相关函数（γ₁）。
 * 图像模式先积分得到 I(q)；曲线模式直接粘贴/加载曲线。
 */
import { ref, computed, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useToast } from '@/lib/toast'
import { useTransport } from '@/lib/transport'
import GeometryForm from '@/components/business/GeometryForm.vue'
import type { GeometryParams } from '@/components/business/GeometryForm.vue'
import MaskBuilderForm from '@/components/business/MaskBuilderForm.vue'
import type { MaskConfig } from '@/components/business/MaskBuilderForm.vue'
import FileDialogButton from '@/components/business/FileDialogButton.vue'
import TaskProgressBar from '@/components/business/TaskProgressBar.vue'
import LineChart from '@/components/charts/LineChart.vue'
import type { LineTrace } from '@/components/charts/LineChart.vue'

const { t } = useI18n()
const toast = useToast()
const transport = useTransport()

// --- Input mode / 输入模式 ---
const inputMode = ref<'image' | 'curves'>('curves')

// --- Image-mode state / 图像模式状态 ---
const filePath = ref<string | null>(null)
const geometry = ref<GeometryParams>({
  pixel1: 172, pixel2: 172, distance: 200,
  wavelength: 1.5418, centerX: 512, centerY: 512,
})
const maskConfig = ref<MaskConfig>({
  valueRangeMin: 0, valueRangeMax: 2147483647,
  deadPixelThreshold: 0, customMaskPath: null,
})
const qUnit = ref<'nm^-1' | 'A^-1'>('nm^-1')
const radialMin = ref<number | null>(null)
const radialMax = ref<number | null>(null)
const npt = ref(1000)
const dataFileFilters = [
  { name: 'Detector Images', extensions: ['edf', 'tif', 'tiff', 'h5', 'hdf5'] },
]

// --- Curves-mode state / 曲线模式状态 ---
const curvesText = ref('')
const curvesFilePath = ref<string | null>(null)
const parsedQ = ref<number[]>([])
const parsedIntensity = ref<number[]>([])

// --- Background / 背景 ---
const bgMode = ref<'auto' | 'constant' | 'none'>('auto')
const bgConstant = ref<number | null>(null)

// --- Methods / 方法 ---
const methods = ref<string[]>(['bragg', 'correlation'])
const peakQMin = ref<number | null>(null)
const peakQMax = ref<number | null>(null)
const minorityPhase = ref<'crystalline' | 'amorphous'>('crystalline')

// --- Task state / 任务状态 ---
const isRunning = ref(false)
const taskId = ref<string | null>(null)
const progress = ref(0)
const progressMessage = ref<string | null>(null)
const errorMessage = ref<string | null>(null)
const profileTraces = ref<LineTrace[]>([])
const gammaTraces = ref<LineTrace[]>([])
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const resultData = ref<any>(null)

let cleanupProgress: (() => void) | null = null
let cleanupResult: (() => void) | null = null
let cleanupError: (() => void) | null = null

function cleanupAll(): void {
  cleanupProgress?.()
  cleanupResult?.()
  cleanupError?.()
  cleanupProgress = cleanupResult = cleanupError = null
}

const canRun = computed(() => {
  if (isRunning.value) return false
  if (methods.value.length === 0) return false
  if (inputMode.value === 'image') return !!filePath.value
  return parsedQ.value.length >= 8
})

const qAxisLabel = computed(() => (qUnit.value === 'nm^-1' ? 'q (nm⁻¹)' : 'q (Å⁻¹)'))

function toggleMethod(m: string): void {
  const i = methods.value.indexOf(m)
  if (i >= 0) methods.value.splice(i, 1)
  else methods.value.push(m)
}

function parseCurves(): void {
  const q: number[] = []
  const inten: number[] = []
  for (const line of curvesText.value.trim().split(/\r?\n/)) {
    const parts = line.trim().split(/[\s,;\t]+/).filter(Boolean)
    if (parts.length < 2) continue
    const x = parseFloat(parts[0])
    const y = parseFloat(parts[1])
    if (Number.isFinite(x) && Number.isFinite(y)) {
      q.push(x)
      inten.push(y)
    }
  }
  parsedQ.value = q
  parsedIntensity.value = inten
  if (q.length < 8) {
    toast.push({ title: t('lamellar.errorTitle'), message: t('lamellar.curvesParseFail'), tone: 'error' })
  }
}

async function loadCurvesFile(path: string | null): Promise<void> {
  if (!path) return
  try {
    const desktop = (window as unknown as { desktop?: { readTextFile?: (p: string) => Promise<string> } }).desktop
    if (desktop?.readTextFile) {
      curvesText.value = await desktop.readTextFile(path)
      parseCurves()
    }
  } catch (err) {
    toast.push({ title: t('lamellar.errorTitle'), message: String(err), tone: 'error' })
  }
}

function buildParams(): Record<string, unknown> {
  const p: Record<string, unknown> = {
    inputMode: inputMode.value,
    qUnit: qUnit.value,
    methods: [...methods.value],
    background: {
      mode: bgMode.value,
      ...(bgMode.value === 'constant' && bgConstant.value !== null ? { constant: bgConstant.value } : {}),
    },
    minorityPhase: minorityPhase.value,
    bragg: {
      ...(peakQMin.value !== null ? { qMin: peakQMin.value } : {}),
      ...(peakQMax.value !== null ? { qMax: peakQMax.value } : {}),
    },
  }
  if (inputMode.value === 'image') {
    p.files = filePath.value ? [filePath.value] : []
    p.geometry = { ...geometry.value }
    p.mask = { ...maskConfig.value }
    p.radialUnit = qUnit.value === 'nm^-1' ? 'q_nm^-1' : 'q_A^-1'
    p.radialMin = radialMin.value
    p.radialMax = radialMax.value
    p.npt = npt.value
    p.dropEmptyBins = true
  } else {
    p.q = [...parsedQ.value]
    p.intensity = [...parsedIntensity.value]
  }
  return p
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function buildChartTraces(data: Record<string, any>): void {
  const q = Array.isArray(data.q) ? data.q as number[] : []
  profileTraces.value = q.length
    ? [
        { x: q, y: data.intensity ?? [], name: t('lamellar.rawCurve'), color: '#94a3b8' },
        { x: q, y: data.correctedIntensity ?? [], name: t('lamellar.correctedCurve'), color: '#2563eb' },
      ]
    : []

  const r = Array.isArray(data.gammaR) ? data.gammaR as number[] : []
  gammaTraces.value = r.length
    ? [{ x: r, y: data.gamma ?? [], name: 'γ₁(x)', color: '#7c3aed' }]
    : []
}

async function handleRun(): Promise<void> {
  if (!canRun.value || isRunning.value) return
  isRunning.value = true
  progress.value = 0
  progressMessage.value = null
  errorMessage.value = null
  resultData.value = null
  profileTraces.value = []
  gammaTraces.value = []

  try {
    const response = await transport.submitTask('lamellar_analysis', buildParams())
    taskId.value = response.taskId

    cleanupProgress = transport.onTaskProgress(response.taskId, (payload) => {
      progress.value = payload.progress
      progressMessage.value = payload.message ?? null
    })
    cleanupResult = transport.onTaskResult(response.taskId, (payload) => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      resultData.value = payload.data as Record<string, any>
      buildChartTraces(resultData.value ?? {})
      isRunning.value = false
      taskId.value = null
      cleanupAll()
    })
    cleanupError = transport.onTaskError(response.taskId, (payload) => {
      errorMessage.value = payload.error
      isRunning.value = false
      taskId.value = null
      cleanupAll()
    })
  } catch (err) {
    errorMessage.value = String(err)
    isRunning.value = false
    taskId.value = null
  }
}

function handleCancel(): void {
  if (taskId.value) transport.cancelTask(taskId.value)
}

function fmt(v: unknown): string {
  if (typeof v !== 'number' || !Number.isFinite(v)) return '—'
  return Math.abs(v) >= 100 || Math.abs(v) < 0.001 ? v.toExponential(3) : v.toFixed(3)
}

function exportCsv(): void {
  if (!resultData.value) return
  const q = resultData.value.q as number[] ?? []
  const lines: string[] = ['q_nm,intensity,corrected_intensity']
  for (let i = 0; i < q.length; i++) {
    lines.push([
      q[i],
      resultData.value.intensity?.[i] ?? '',
      resultData.value.correctedIntensity?.[i] ?? '',
    ].join(','))
  }
  const rg = resultData.value.gammaR as number[] ?? []
  if (rg.length) {
    lines.push('', 'r_nm,gamma')
    for (let i = 0; i < rg.length; i++) {
      lines.push([rg[i], resultData.value.gamma?.[i] ?? ''].join(','))
    }
  }
  lines.push('')
  for (const r of (resultData.value.results ?? []) as Array<Record<string, unknown>>) {
    lines.push(`# ${r.method}: L=${r.long_period_nm}, q*=${r.q_star_nm ?? ''}, l_c=${r.l_crystalline_nm ?? ''}, l_a=${r.l_amorphous_nm ?? ''}, phi_c=${r.crystallinity_stack ?? ''}`)
  }
  const blob = new Blob([lines.join('\n')], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'lamellar_analysis.csv'
  a.click()
  URL.revokeObjectURL(url)
}

onUnmounted(() => {
  cleanupAll()
})
</script>

<style scoped>
.lm-page {
  display: flex;
  flex-direction: column;
  gap: 24px;
  padding: 24px;
  max-width: 1400px;
  margin: 0 auto;
}
.lm-header h1 { margin: 0 0 4px; font-size: 1.5rem; }
.lm-subtitle { margin: 0; color: var(--color-text-muted, #6b7280); font-size: 0.92rem; }
.lm-layout {
  display: grid;
  grid-template-columns: minmax(300px, 380px) minmax(0, 1fr);
  gap: 24px;
  align-items: start;
}
.lm-sidebar { display: flex; flex-direction: column; gap: 16px; }
.lm-main { display: flex; flex-direction: column; gap: 20px; min-width: 0; }
.lm-card {
  background: var(--color-surface, #fff);
  border: 1px solid var(--color-border, #e5e7eb);
  border-radius: 8px;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.lm-details > summary { cursor: pointer; font-weight: 600; }
.lm-card-title { margin: 0; font-size: 0.95rem; font-weight: 600; }
.lm-field { display: flex; flex-direction: column; gap: 4px; flex: 1; }
.lm-field-row { display: flex; gap: 8px; }
.lm-label { font-size: 0.82rem; color: var(--color-text-muted, #6b7280); }
.lm-input, .lm-select, .lm-textarea {
  width: 100%;
  padding: 6px 8px;
  border: 1px solid var(--color-border, #d1d5db);
  border-radius: 4px;
  font-size: 0.88rem;
  background: var(--color-surface, #fff);
  box-sizing: border-box;
}
.lm-textarea { font-family: monospace; resize: vertical; }
.lm-radio-row, .lm-btn-row { display: flex; gap: 16px; flex-wrap: wrap; align-items: center; }
.lm-radio-label, .lm-toggle-label { display: flex; align-items: center; gap: 6px; font-size: 0.88rem; cursor: pointer; }
.lm-hint { margin: 0; font-size: 0.78rem; color: var(--color-text-muted, #6b7280); }
.lm-hint-ok { color: #16a34a; }
.lm-btn {
  padding: 7px 14px;
  border: 1px solid var(--color-border, #d1d5db);
  border-radius: 4px;
  background: var(--color-surface, #fff);
  cursor: pointer;
  font-size: 0.88rem;
}
.lm-btn:hover { background: var(--color-surface-hover, #f3f4f6); }
.lm-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.lm-btn-sm { padding: 4px 10px; font-size: 0.82rem; }
.lm-btn-primary { background: #2563eb; color: #fff; border-color: #2563eb; }
.lm-btn-primary:hover { background: #1d4ed8; }
.lm-run-row { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.lm-error {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #991b1b;
  padding: 10px 12px;
  border-radius: 6px;
  font-size: 0.88rem;
}
.lm-warnings {
  background: #fffbeb;
  border: 1px solid #fde68a;
  padding: 10px 14px;
  border-radius: 6px;
  font-size: 0.85rem;
}
.lm-warnings ul { margin: 6px 0 0; padding-left: 18px; }
.lm-warnings li { margin-bottom: 3px; }
.lm-chart { background: var(--color-surface, #fff); border: 1px solid var(--color-border, #e5e7eb); border-radius: 8px; padding: 14px; }
.lm-section-title { margin: 0 0 10px; font-size: 1.05rem; }
.lm-result-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; }
.lm-result-card {
  background: var(--color-surface, #fff);
  border: 1px solid var(--color-border, #e5e7eb);
  border-radius: 8px;
  padding: 12px 14px;
}
.lm-result-method { margin: 0 0 8px; font-size: 0.95rem; color: #2563eb; }
.lm-result-row { display: flex; justify-content: space-between; font-size: 0.88rem; padding: 2px 0; }
.lm-result-key { color: var(--color-text-muted, #6b7280); }
.lm-result-val { font-variant-numeric: tabular-nums; font-weight: 600; }
@media (max-width: 960px) {
  .lm-layout { grid-template-columns: 1fr; }
}
</style>
