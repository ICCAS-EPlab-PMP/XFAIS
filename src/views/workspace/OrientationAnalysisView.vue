<template>
  <section class="or-page" :data-testid="testIds.orientationPage">
    <!-- Header / 页头 -->
    <header class="or-header">
      <h1>{{ t('orientationAnalysis.title') }}</h1>
      <p class="or-subtitle">{{ t('orientationAnalysis.subtitle') }}</p>
    </header>

    <div class="or-layout">
      <!-- ===== Sidebar: controls / 侧边栏：控制面板 ===== -->
      <aside class="or-sidebar">
        <!-- Input mode / 输入模式 -->
        <div class="or-card">
          <h3 class="or-card-title">{{ t('orientationAnalysis.inputMode') }}</h3>
          <div class="or-radio-row">
            <label class="or-radio-label">
              <input v-model="inputMode" type="radio" value="image" />
              <span>{{ t('orientationAnalysis.modeImage') }}</span>
            </label>
            <label class="or-radio-label">
              <input v-model="inputMode" type="radio" value="curves" />
              <span>{{ t('orientationAnalysis.modeCurves') }}</span>
            </label>
          </div>
        </div>

        <!-- Image-mode inputs / 图像模式输入 -->
        <template v-if="inputMode === 'image'">
          <div class="or-card">
            <h3 class="or-card-title">{{ t('orientationAnalysis.selectFile') }}</h3>
            <FileDialogButton
              v-model="filePath"
              mode="openFile"
              :label="t('orientationAnalysis.selectFile')"
              :filters="dataFileFilters"
            />
            <H5Selector
              v-if="filePath"
              v-model="h5Selection"
              :datasets="h5Datasets"
              class="or-h5"
            />
          </div>

          <details class="or-card or-details">
            <summary>{{ t('orientationAnalysis.geometry') }}</summary>
            <GeometryForm v-model="geometry" />
          </details>

          <details class="or-card or-details">
            <summary>{{ t('orientationAnalysis.mask') }}</summary>
            <MaskBuilderForm v-model="maskConfig" :bare="true" />
          </details>

          <div class="or-card">
            <h3 class="or-card-title">{{ t('orientationAnalysis.radialRange') }}</h3>
            <div class="or-field">
              <label class="or-label">{{ t('orientationAnalysis.radialUnitLabel') }}</label>
              <select v-model="radialUnit" class="or-select">
                <option v-for="u in radialUnitOptions" :key="u.value" :value="u.value">{{ u.label }}</option>
              </select>
            </div>
            <div class="or-field-row">
              <div class="or-field">
                <label class="or-label">{{ t('orientationAnalysis.min') }}</label>
                <input v-model.number="radialMin" type="number" class="or-input" step="any" />
              </div>
              <div class="or-field">
                <label class="or-label">{{ t('orientationAnalysis.max') }}</label>
                <input v-model.number="radialMax" type="number" class="or-input" step="any" />
              </div>
            </div>
            <div class="or-field-row">
              <div class="or-field">
                <label class="or-label">{{ t('orientationAnalysis.npt') }}</label>
                <input v-model.number="npt" type="number" class="or-input" min="2" step="1" />
              </div>
              <div class="or-field">
                <label class="or-label">{{ t('orientationAnalysis.nptRad') }}</label>
                <input v-model.number="nptRad" type="number" class="or-input" min="1" step="1" />
              </div>
            </div>
          </div>
        </template>

        <!-- Curves-mode inputs / 曲线模式输入 -->
        <div v-else class="or-card">
          <h3 class="or-card-title">{{ t('orientationAnalysis.curvesInput') }}</h3>
          <p class="or-hint">{{ t('orientationAnalysis.curvesHint') }}</p>
          <textarea
            v-model="curvesText"
            class="or-textarea"
            :placeholder="t('orientationAnalysis.curvesPlaceholder')"
            rows="6"
          ></textarea>
          <div class="or-btn-row">
            <button type="button" class="or-btn or-btn-sm" @click="parseCurves">
              {{ t('orientationAnalysis.parse') }}
            </button>
            <FileDialogButton
              v-model="curvesFilePath"
              mode="openFile"
              :label="t('orientationAnalysis.loadFile')"
              :filters="[{ name: 'Data', extensions: ['csv', 'txt', 'dat'] }]"
              @update:model-value="loadCurvesFile"
            />
          </div>
          <p v-if="parsedChi.length > 0" class="or-hint or-hint-ok">
            {{ t('orientationAnalysis.parsedN', { n: parsedChi.length }) }}
          </p>
        </div>

        <!-- Preprocessing / 预处理（默认折叠，可选开启）-->
        <details class="or-card or-details">
          <summary>{{ t('orientationAnalysis.preprocessing') }}</summary>
          <div class="or-field">
            <label class="or-label">{{ t('orientationAnalysis.scatteringGeometry') }}</label>
            <select v-model="scatteringGeometry" class="or-select">
              <option value="transmission">{{ t('orientationAnalysis.geomTransmission') }}</option>
              <option value="reflection">{{ t('orientationAnalysis.geomReflection') }}</option>
            </select>
          </div>
          <div class="or-field">
            <label class="or-label">{{ t('orientationAnalysis.symmetry') }}</label>
            <select v-model="symmetry" class="or-select">
              <option value="auto">{{ t('orientationAnalysis.symAuto') }}</option>
              <option value="friedel">Friedel</option>
              <option value="meridional_mirror">{{ t('orientationAnalysis.symMeridional') }}</option>
              <option value="equatorial_mirror">{{ t('orientationAnalysis.symEquatorial') }}</option>
              <option value="none">{{ t('orientationAnalysis.symNone') }}</option>
            </select>
          </div>
          <div class="or-field">
            <label class="or-label">{{ t('orientationAnalysis.missingStrategy') }}</label>
            <select v-model="missing" class="or-select">
              <option value="interp">{{ t('orientationAnalysis.missInterp') }}</option>
              <option value="mirror">{{ t('orientationAnalysis.missMirror') }}</option>
              <option value="drop">{{ t('orientationAnalysis.missDrop') }}</option>
            </select>
          </div>
          <div class="or-field">
            <label class="or-label">{{ t('orientationAnalysis.background') }}</label>
            <select v-model="bgMode" class="or-select">
              <option value="constant">{{ t('orientationAnalysis.bgConstant') }}</option>
              <option value="linear">{{ t('orientationAnalysis.bgLinear') }}</option>
              <option value="none">{{ t('orientationAnalysis.bgNone') }}</option>
            </select>
          </div>
          <label class="or-toggle-label">
            <input v-model="bgAutoEstimate" type="checkbox" :disabled="bgMode === 'none'" />
            <span>{{ t('orientationAnalysis.bgAutoEstimate') }}</span>
          </label>
        </details>

        <!-- Methods / 方法 -->
        <div class="or-card">
          <h3 class="or-card-title">{{ t('orientationAnalysis.methods') }}</h3>
          <label class="or-toggle-label">
            <input type="checkbox" :checked="methods.includes('hermans')" @change="toggleMethod('hermans')" />
            <span>Hermans</span>
          </label>
          <label class="or-toggle-label">
            <input type="checkbox" :checked="methods.includes('fwhm')" @change="toggleMethod('fwhm')" />
            <span>FWHM</span>
          </label>
          <label class="or-toggle-label">
            <input type="checkbox" :checked="methods.includes('wilchinsky')" @change="toggleMethod('wilchinsky')" />
            <span>Wilchinsky</span>
          </label>

          <template v-if="methods.includes('hermans')">
            <div class="or-field">
              <label class="or-label">{{ t('orientationAnalysis.chiZero') }}</label>
              <select v-model="chiZero" class="or-select">
                <option value="meridian">{{ t('orientationAnalysis.czMeridian') }}</option>
                <option value="equator">{{ t('orientationAnalysis.czEquator') }}</option>
              </select>
            </div>
            <div class="or-field">
              <label class="or-label">{{ t('orientationAnalysis.meridianChi') }}</label>
              <input
                v-model.number="meridianChiDeg"
                type="number"
                class="or-input"
                step="any"
                :placeholder="t('orientationAnalysis.meridianChiPlaceholder')"
              />
              <p class="or-hint">{{ t('orientationAnalysis.meridianChiHint') }}</p>
            </div>
            <label class="or-toggle-label">
              <input v-model="equatorialToChain" type="checkbox" />
              <span>{{ t('orientationAnalysis.equatorialToChain') }}</span>
            </label>
          </template>
        </div>

        <!-- Wilchinsky cell + reflections / Wilchinsky 晶胞 + 反射 -->
        <div v-if="methods.includes('wilchinsky')" class="or-card">
          <h3 class="or-card-title">{{ t('orientationAnalysis.cellParams') }}</h3>
          <div class="or-field-row">
            <div class="or-field">
              <label class="or-label">a (Å)</label>
              <input v-model.number="cellA" type="number" class="or-input" step="any" min="0" />
            </div>
            <div class="or-field">
              <label class="or-label">b (Å)</label>
              <input v-model.number="cellB" type="number" class="or-input" step="any" min="0" />
            </div>
          </div>
          <div class="or-field-row">
            <div class="or-field">
              <label class="or-label">c (Å)</label>
              <input v-model.number="cellC" type="number" class="or-input" step="any" min="0" />
            </div>
            <div class="or-field">
              <label class="or-label">β (°)</label>
              <input v-model.number="cellBeta" type="number" class="or-input" step="any" min="0" max="180" />
            </div>
          </div>

          <h4 class="or-subtitle-sm">{{ t('orientationAnalysis.reflections') }}</h4>
          <div v-for="(refl, idx) in reflections" :key="idx" class="or-refl-row">
            <input v-model.number="refl.h" type="number" class="or-input or-input-sm" placeholder="h" />
            <input v-model.number="refl.k" type="number" class="or-input or-input-sm" placeholder="k" />
            <input v-model.number="refl.l" type="number" class="or-input or-input-sm" placeholder="l" />
            <input v-model.number="refl.cos2" type="number" class="or-input" step="any" placeholder="⟨cos²χ⟩" />
            <button type="button" class="or-btn-icon" :title="t('orientationAnalysis.removeReflection')" @click="removeReflection(idx)">&times;</button>
          </div>
          <button type="button" class="or-btn or-btn-sm" @click="addReflection">
            + {{ t('orientationAnalysis.addReflection') }}
          </button>
        </div>

        <!-- Crystallinity / 结晶度 -->
        <div class="or-card">
          <h3 class="or-card-title">{{ t('orientationAnalysis.crystallinity') }}</h3>
          <div class="or-field">
            <label class="or-label">{{ t('orientationAnalysis.xcLabel') }}</label>
            <input v-model.number="crystallinityInput" type="number" class="or-input" step="any" min="0" max="100" placeholder="0–100" />
            <p class="or-hint">{{ t('orientationAnalysis.xcHint') }}</p>
          </div>
        </div>
      </aside>

      <!-- ===== Main: run + results / 主区：运行 + 结果 ===== -->
      <main class="or-main">
        <div class="or-run-row">
          <button
            type="button"
            class="or-btn or-btn-primary"
            :disabled="!canRun || isRunning"
            :data-testid="testIds.orientationRunBtn"
            @click="handleRun"
          >
            {{ isRunning ? t('orientationAnalysis.running') : t('orientationAnalysis.run') }}
          </button>
          <button v-if="isRunning" type="button" class="or-btn" @click="handleCancel">
            {{ t('orientationAnalysis.cancel') }}
          </button>
          <button
            v-if="resultData"
            type="button"
            class="or-btn"
            :data-testid="testIds.orientationExport"
            @click="exportCsv"
          >
            {{ t('orientationAnalysis.exportCsv') }}
          </button>
        </div>

        <TaskProgressBar v-if="isRunning || progress > 0" :progress="progress" :message="progressMessage ?? ''" />

        <div v-if="errorMessage" class="or-error">
          <strong>{{ t('orientationAnalysis.errorTitle') }}:</strong> {{ errorMessage }}
        </div>

        <!-- Warnings / 警告 -->
        <div v-if="resultData?.warnings?.length" class="or-warnings">
          <h3 class="or-card-title">{{ t('orientationAnalysis.warnings') }}</h3>
          <ul>
            <li v-for="(w, idx) in resultData.warnings" :key="idx">{{ w }}</li>
          </ul>
        </div>

        <!-- Chart / 曲线图 -->
        <div v-if="chartTraces.length > 0" class="or-chart" :data-testid="testIds.orientationChart">
          <h2 class="or-section-title">{{ t('orientationAnalysis.chartTitle') }}</h2>
          <LineChart
            :traces="chartTraces"
            :x-label="t('orientationAnalysis.chiAxis')"
            :y-label="t('orientationAnalysis.intensityAxis')"
            :title="t('orientationAnalysis.chartTitle')"
          />
        </div>

        <!-- Results cards / 结果卡片 -->
        <div v-if="resultData?.results?.length" class="or-results">
          <h2 class="or-section-title">{{ t('orientationAnalysis.resultsTitle') }}</h2>
          <div class="or-result-grid">
            <div v-for="(r, idx) in resultData.results" :key="idx" class="or-result-card">
              <h3 class="or-result-method">{{ r.method }}</h3>
              <div class="or-result-row">
                <span class="or-result-key">f</span>
                <span class="or-result-val">{{ formatNum(r.f) }}</span>
              </div>
              <div v-if="r.cos2_phi !== undefined" class="or-result-row">
                <span class="or-result-key">⟨cos²φ⟩</span>
                <span class="or-result-val">{{ formatNum(r.cos2_phi) }}</span>
              </div>
              <div v-if="r.fwhm_deg !== undefined" class="or-result-row">
                <span class="or-result-key">FWHM</span>
                <span class="or-result-val">{{ formatNum(r.fwhm_deg) }}°</span>
              </div>
              <div v-if="r.pi_pct !== undefined" class="or-result-row">
                <span class="or-result-key">Π%</span>
                <span class="or-result-val">{{ formatNum(r.pi_pct) }}%</span>
              </div>
              <div v-if="r.residual !== undefined" class="or-result-row">
                <span class="or-result-key">{{ t('orientationAnalysis.residual') }}</span>
                <span class="or-result-val">{{ formatNum(r.residual) }}</span>
              </div>
              <div v-if="r.condition_number !== undefined && r.condition_number !== null" class="or-result-row">
                <span class="or-result-key">cond</span>
                <span class="or-result-val">{{ formatNum(r.condition_number) }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Crystallinity hint / 结晶度提示 -->
        <div v-if="resultData?.crystallinityHint && Object.keys(resultData.crystallinityHint).length" class="or-conf">
          <h3 class="or-card-title">{{ t('orientationAnalysis.confidence') }}</h3>
          <p class="or-hint">{{ resultData.crystallinityHint.note }}</p>
          <p v-if="resultData.crystallinityHint.correction_factor_guess" class="or-hint">
            {{ t('orientationAnalysis.correctionFactor') }}: ×{{ resultData.crystallinityHint.correction_factor_guess }}
          </p>
        </div>
      </main>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref, computed, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useToast } from '@/lib/toast'
import { useTransport } from '@/lib/transport'
import { testIds } from '@/lib/testIds'
import GeometryForm from '@/components/business/GeometryForm.vue'
import type { GeometryParams } from '@/components/business/GeometryForm.vue'
import MaskBuilderForm from '@/components/business/MaskBuilderForm.vue'
import type { MaskConfig } from '@/components/business/MaskBuilderForm.vue'
import H5Selector from '@/components/business/H5Selector.vue'
import type { H5DatasetInfo, H5Selection } from '@/components/business/H5Selector.vue'
import FileDialogButton from '@/components/business/FileDialogButton.vue'
import TaskProgressBar from '@/components/business/TaskProgressBar.vue'
import LineChart from '@/components/charts/LineChart.vue'
import type { LineTrace } from '@/components/charts/LineChart.vue'

const { t } = useI18n()
const toast = useToast()
const transport = useTransport()

// --- Input mode / 输入模式 ---
const inputMode = ref<'image' | 'curves'>('image')

// --- Image-mode state / 图像模式状态 ---
const filePath = ref<string | null>(null)
const h5Datasets = ref<H5DatasetInfo[]>([])
const h5Selection = ref<H5Selection>({ dataset: '', channel: 0, frame: 0 })
const geometry = ref<GeometryParams>({
  pixel1: 172, pixel2: 172, distance: 200,
  wavelength: 1.5418, centerX: 512, centerY: 512,
})
const maskConfig = ref<MaskConfig>({
  valueRangeMin: 0, valueRangeMax: 1e10,
  deadPixelThreshold: 0, customMaskPath: null,
})
const radialUnit = ref('q_A^-1')
const radialMin = ref(0.98)
const radialMax = ref(1.02)
const npt = ref(360)
const nptRad = ref(100)
const dropEmptyBins = ref(true)
const dataFileFilters = [
  { name: 'Detector Images', extensions: ['edf', 'tif', 'tiff', 'h5', 'hdf5'] },
]
const radialUnitOptions = [
  { value: 'q_A^-1', label: 'q (Å⁻¹)' },
  { value: 'q_nm^-1', label: 'q (nm⁻¹)' },
  { value: '2th_deg', label: '2θ (°)' },
  { value: 'r_mm', label: 'r (mm)' },
]

// --- Curves-mode state / 曲线模式状态 ---
const curvesText = ref('')
const curvesFilePath = ref<string | null>(null)
const parsedChi = ref<number[]>([])
const parsedIntensity = ref<number[]>([])

// --- Preprocessing / 预处理（默认全部关闭，按需在折叠区开启）---
const scatteringGeometry = ref<'transmission' | 'reflection'>('transmission')
const symmetry = ref<'auto' | 'friedel' | 'meridional_mirror' | 'equatorial_mirror' | 'none'>('none')
const missing = ref<'interp' | 'drop' | 'mirror'>('interp')
const bgMode = ref<'none' | 'constant' | 'linear'>('none')
const bgAutoEstimate = ref(true)

// --- Methods / 方法 ---
const methods = ref<string[]>(['hermans', 'fwhm'])
const chiZero = ref<'meridian' | 'equator'>('meridian')
const equatorialToChain = ref(true)
// Meridian / reference-axis angle in χ (set when the fiber axis is not at χ=0).
// 子午线/参考轴在 χ 中的角度（纤维轴不在 χ=0 时设置）。
const meridianChiDeg = ref<number | null>(null)

// --- Wilchinsky / Wilchinsky 晶胞 + 反射 ---
const cellA = ref(6.65)
const cellB = ref(20.96)
const cellC = ref(6.5)
const cellBeta = ref(99.62)
interface Reflection { h: number; k: number; l: number; cos2: number }
const reflections = ref<Reflection[]>([{ h: 1, k: 1, l: 0, cos2: 0.5 }])
function addReflection(): void {
  reflections.value.push({ h: 0, k: 0, l: 0, cos2: 0 })
}
function removeReflection(idx: number): void {
  reflections.value.splice(idx, 1)
}

// --- Crystallinity / 结晶度 ---
const crystallinityInput = ref<number | null>(null)

// --- Task state / 任务状态 ---
const isRunning = ref(false)
const taskId = ref<string | null>(null)
const progress = ref(0)
const progressMessage = ref<string | null>(null)
const errorMessage = ref<string | null>(null)
const chartTraces = ref<LineTrace[]>([])
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
  return parsedChi.value.length >= 2
})

function toggleMethod(m: string): void {
  const i = methods.value.indexOf(m)
  if (i >= 0) methods.value.splice(i, 1)
  else methods.value.push(m)
}

function parseCurves(): void {
  const chi: number[] = []
  const inten: number[] = []
  const lines = curvesText.value.trim().split(/\r?\n/)
  for (const line of lines) {
    const parts = line.trim().split(/[\s,;\t]+/).filter(Boolean)
    if (parts.length < 2) continue
    // skip header lines / 跳过表头
    const x = parseFloat(parts[0])
    const y = parseFloat(parts[1])
    if (Number.isFinite(x) && Number.isFinite(y)) {
      chi.push(x)
      inten.push(y)
    }
  }
  parsedChi.value = chi
  parsedIntensity.value = inten
  if (chi.length < 2) {
    toast.push({ title: t('orientationAnalysis.errorTitle'), message: t('orientationAnalysis.curvesParseFail'), tone: 'error' })
  }
}

// FileDialogButton only returns a path; for curves we still need to read it.
// We delegate the actual read to the backend in image mode; for curves the
// user pastes data or we attempt a text read via the transport layer later.
// For now, loading a curves file fills the textarea via a minimal fetch.
// FileDialogButton 只返回路径；曲线模式仍需读取内容。这里用最小化的方式填充文本框。
async function loadCurvesFile(path: string | null): Promise<void> {
  if (!path) return
  try {
    // Read via the desktop bridge if available; otherwise prompt the user to paste.
    // 若桌面桥可用则通过其读取；否则提示用户粘贴。
    const desktop = (window as unknown as { desktop?: { readTextFile?: (p: string) => Promise<string> } }).desktop
    if (desktop?.readTextFile) {
      curvesText.value = await desktop.readTextFile(path)
      parseCurves()
    }
  } catch (err) {
    toast.push({ title: t('orientationAnalysis.errorTitle'), message: String(err), tone: 'error' })
  }
}

function buildParams(): Record<string, unknown> {
  const p: Record<string, unknown> = {
    inputMode: inputMode.value,
    methods: [...methods.value],
    scatteringGeometry: scatteringGeometry.value,
    symmetry: symmetry.value,
    missing: missing.value,
    background: { mode: bgMode.value, autoEstimate: bgAutoEstimate.value },
    hermans: { chiZero: chiZero.value, equatorialToChain: equatorialToChain.value, referenceChiDeg: meridianChiDeg.value },
    crystallinity: crystallinityInput.value,
  }
  if (methods.value.includes('wilchinsky')) {
    p.wilchinsky = {
      cell: { a: cellA.value, b: cellB.value, c: cellC.value, beta: cellBeta.value },
      reflections: reflections.value.map((r) => ({ h: r.h, k: r.k, l: r.l, cos2: r.cos2 })),
      uniqueAxis: 'b',
    }
  }
  if (inputMode.value === 'image') {
    p.files = filePath.value ? [filePath.value] : []
    p.geometry = { ...geometry.value }
    p.mask = { ...maskConfig.value }
    p.radialUnit = radialUnit.value
    p.radialMin = radialMin.value
    p.radialMax = radialMax.value
    p.npt = npt.value
    p.nptRad = nptRad.value
    p.dropEmptyBins = dropEmptyBins.value
    p.dataset = h5Selection.value.dataset
    p.channel = h5Selection.value.channel
    p.frame = h5Selection.value.frame
  } else {
    p.chi = [...parsedChi.value]
    p.intensity = [...parsedIntensity.value]
  }
  return p
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function buildChartTraces(data: Record<string, any>): void {
  const traces: LineTrace[] = []
  const chi = Array.isArray(data.chi) ? data.chi as number[] : []
  if (chi.length) {
    traces.push({ x: chi, y: data.intensity ?? [], name: t('orientationAnalysis.rawCurve'), color: '#94a3b8' })
    traces.push({ x: chi, y: data.correctedIntensity ?? [], name: t('orientationAnalysis.correctedCurve'), color: '#2563eb' })
    if (Array.isArray(data.background) && data.background.length) {
      traces.push({ x: chi, y: data.background, name: t('orientationAnalysis.backgroundCurve'), color: '#dc2626' })
    }
  }
  chartTraces.value = traces
}

async function handleRun(): Promise<void> {
  if (!canRun.value || isRunning.value) return
  isRunning.value = true
  progress.value = 0
  progressMessage.value = null
  errorMessage.value = null
  resultData.value = null
  chartTraces.value = []

  try {
    const response = await transport.submitTask('orientation_analysis', buildParams())
    taskId.value = response.taskId

    cleanupProgress = transport.onTaskProgress(response.taskId, (payload) => {
      progress.value = payload.progress
      progressMessage.value = payload.message ?? null
    })
    cleanupResult = transport.onTaskResult(response.taskId, (payload) => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const data = payload.data as Record<string, any>
      resultData.value = data
      buildChartTraces(data)
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

function formatNum(v: unknown): string {
  if (typeof v !== 'number' || !Number.isFinite(v)) return '—'
  return Math.abs(v) >= 100 || Math.abs(v) < 0.001 ? v.toExponential(3) : v.toFixed(4)
}

function exportCsv(): void {
  if (!resultData.value) return
  const chi = resultData.value.chi as number[] ?? []
  const lines: string[] = ['chi,intensity,corrected_intensity,background']
  for (let i = 0; i < chi.length; i++) {
    lines.push([
      chi[i],
      resultData.value.intensity?.[i] ?? '',
      resultData.value.correctedIntensity?.[i] ?? '',
      resultData.value.background?.[i] ?? '',
    ].join(','))
  }
  // append metrics / 追加指标
  lines.push('')
  for (const r of (resultData.value.results ?? []) as Array<Record<string, unknown>>) {
    lines.push(`# ${r.method}: f=${r.f}, cos2_phi=${r.cos2_phi ?? ''}, fwhm_deg=${r.fwhm_deg ?? ''}`)
  }
  const blob = new Blob([lines.join('\n')], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'orientation_analysis.csv'
  a.click()
  URL.revokeObjectURL(url)
}

onUnmounted(() => {
  cleanupAll()
})
</script>

<style scoped>
.or-page {
  display: flex;
  flex-direction: column;
  gap: 24px;
  padding: 24px;
  max-width: 1400px;
  margin: 0 auto;
}
.or-header h1 { margin: 0 0 4px; font-size: 1.5rem; }
.or-subtitle { margin: 0; color: var(--color-text-muted, #6b7280); font-size: 0.92rem; }
.or-layout {
  display: grid;
  grid-template-columns: minmax(300px, 380px) minmax(0, 1fr);
  gap: 24px;
  align-items: start;
}
.or-sidebar { display: flex; flex-direction: column; gap: 16px; }
.or-main { display: flex; flex-direction: column; gap: 20px; min-width: 0; }
.or-card {
  background: var(--color-surface, #fff);
  border: 1px solid var(--color-border, #e5e7eb);
  border-radius: 8px;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.or-details > summary { cursor: pointer; font-weight: 600; }
.or-card-title { margin: 0; font-size: 0.95rem; font-weight: 600; }
.or-subtitle-sm { margin: 8px 0 4px; font-size: 0.85rem; font-weight: 600; color: var(--color-text-muted, #6b7280); }
.or-field { display: flex; flex-direction: column; gap: 4px; flex: 1; }
.or-field-row { display: flex; gap: 8px; }
.or-label { font-size: 0.82rem; color: var(--color-text-muted, #6b7280); }
.or-input, .or-select, .or-textarea {
  width: 100%;
  padding: 6px 8px;
  border: 1px solid var(--color-border, #d1d5db);
  border-radius: 4px;
  font-size: 0.88rem;
  background: var(--color-surface, #fff);
  box-sizing: border-box;
}
.or-input-sm { max-width: 56px; }
.or-textarea { font-family: monospace; resize: vertical; }
.or-radio-row, .or-btn-row { display: flex; gap: 16px; flex-wrap: wrap; align-items: center; }
.or-radio-label, .or-toggle-label { display: flex; align-items: center; gap: 6px; font-size: 0.88rem; cursor: pointer; }
.or-hint { margin: 0; font-size: 0.78rem; color: var(--color-text-muted, #6b7280); }
.or-hint-ok { color: #16a34a; }
.or-h5 { margin-top: 8px; }
.or-btn {
  padding: 7px 14px;
  border: 1px solid var(--color-border, #d1d5db);
  border-radius: 4px;
  background: var(--color-surface, #fff);
  cursor: pointer;
  font-size: 0.88rem;
}
.or-btn:hover { background: var(--color-surface-hover, #f3f4f6); }
.or-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.or-btn-sm { padding: 4px 10px; font-size: 0.82rem; }
.or-btn-primary { background: #2563eb; color: #fff; border-color: #2563eb; }
.or-btn-primary:hover { background: #1d4ed8; }
.or-btn-icon {
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 1.1rem;
  color: var(--color-text-muted, #6b7280);
  padding: 0 4px;
}
.or-refl-row { display: flex; gap: 4px; align-items: center; margin-bottom: 6px; }
.or-run-row { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.or-error {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #991b1b;
  padding: 10px 12px;
  border-radius: 6px;
  font-size: 0.88rem;
}
.or-warnings {
  background: #fffbeb;
  border: 1px solid #fde68a;
  padding: 10px 14px;
  border-radius: 6px;
  font-size: 0.85rem;
}
.or-warnings ul { margin: 6px 0 0; padding-left: 18px; }
.or-warnings li { margin-bottom: 3px; }
.or-chart { background: var(--color-surface, #fff); border: 1px solid var(--color-border, #e5e7eb); border-radius: 8px; padding: 14px; }
.or-section-title { margin: 0 0 10px; font-size: 1.05rem; }
.or-result-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px; }
.or-result-card {
  background: var(--color-surface, #fff);
  border: 1px solid var(--color-border, #e5e7eb);
  border-radius: 8px;
  padding: 12px 14px;
}
.or-result-method { margin: 0 0 8px; font-size: 0.95rem; text-transform: capitalize; color: #2563eb; }
.or-result-row { display: flex; justify-content: space-between; font-size: 0.88rem; padding: 2px 0; }
.or-result-key { color: var(--color-text-muted, #6b7280); }
.or-result-val { font-variant-numeric: tabular-nums; font-weight: 600; }
.or-conf { background: #f0f9ff; border: 1px solid #bae6fd; border-radius: 8px; padding: 12px 14px; }
@media (max-width: 960px) {
  .or-layout { grid-template-columns: 1fr; }
}
</style>
