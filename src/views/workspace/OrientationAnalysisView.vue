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
            <!-- Multi-file batch selection (same experimental conditions) -->
            <!-- 多文件批量选择（同一实验条件） -->
            <div class="or-btn-row">
              <button type="button" class="or-btn" @click="handleAddFiles">
                {{ t('orientationAnalysis.files.add') }}
              </button>
              <button v-if="files.length" type="button" class="or-btn or-btn-sm" @click="clearFiles">
                {{ t('orientationAnalysis.files.clear') }}
              </button>
            </div>
            <p v-if="files.length" class="or-hint">
              {{ t('orientationAnalysis.files.count', { n: files.length }) }}
            </p>
            <p v-if="files.length > 1" class="or-hint or-hint-warn">
              {{ t('orientationAnalysis.files.singleFirstHint') }}
            </p>
            <ul v-if="files.length" class="or-file-list">
              <li v-for="(f, idx) in files" :key="f" class="or-file-item" :class="{ 'or-file-item--active': idx === selectedFileIndex }">
                <label class="or-radio-label" :title="f">
                  <input
                    v-model="selectedFileIndex"
                    type="radio"
                    :value="idx"
                    name="or-preview-file"
                  />
                  <span class="or-file-name">{{ fileName(f) }}</span>
                </label>
                <button type="button" class="or-btn-icon" :title="t('orientationAnalysis.files.remove')" @click="removeFile(idx)">&times;</button>
              </li>
            </ul>
            <H5Selector
              v-if="activeFilePath && h5Datasets.length"
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
            <p class="or-hint">{{ t('orientationAnalysis.selectionHint') }}</p>
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

      <!-- ===== Main: preview + run + results / 主区：预览 + 运行 + 结果 ===== -->
      <main class="or-main">
        <!-- Image preview with beam center + radial selection / 图像预览（中心 + 选区） -->
        <div v-if="inputMode === 'image' && activeFilePath" class="or-card">
          <h3 class="or-card-title">{{ t('orientationAnalysis.files.previewTitle') }}</h3>
          <p class="or-hint">
            {{ t('orientationAnalysis.files.previewFile') }}: {{ fileName(activeFilePath) }}
            <template v-if="beamCenterLabel"> · {{ t('orientationAnalysis.files.beamCenter') }}: {{ beamCenterLabel }}</template>
          </p>
          <div v-if="previewLoading" class="or-preview-loading">{{ t('orientationAnalysis.files.loading') }}</div>
          <ImagePreview
            v-else-if="previewSrc"
            :image-b64="previewSrc"
            :overlays="previewOverlays"
            :show-colorbar="true"
          />
          <p v-else class="or-hint">{{ t('orientationAnalysis.files.noPreview') }}</p>
        </div>

        <div class="or-run-row">
          <button
            type="button"
            class="or-btn or-btn-primary"
            :disabled="!canRun || isRunning"
            :data-testid="testIds.orientationRunBtn"
            @click="handleRun()"
          >
            {{ isRunning ? t('orientationAnalysis.running') : runButtonLabel }}
          </button>
          <button
            v-if="inputMode === 'image' && files.length > 1 && activeFilePath"
            type="button"
            class="or-btn"
            :disabled="isRunning"
            :title="t('orientationAnalysis.files.runSingleHint')"
            @click="handleRunSingle"
          >
            {{ t('orientationAnalysis.files.runSingle') }}
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
            {{ exportButtonLabel }}
          </button>
        </div>

        <TaskProgressBar v-if="isRunning || progress > 0" :progress="progress" :message="progressMessage ?? ''" />

        <div v-if="errorMessage" class="or-error">
          <strong>{{ t('orientationAnalysis.errorTitle') }}:</strong> {{ errorMessage }}
        </div>

        <!-- Batch summary / 批量汇总 -->
        <template v-if="batchItems">
          <div class="or-card">
            <h3 class="or-card-title">
              {{ t('orientationAnalysis.batch.title') }}
              <span class="or-batch-meta">
                {{ t('orientationAnalysis.batch.okCount', { n: batchItems.length }) }}
                <template v-if="failedFiles.length">
                  · {{ t('orientationAnalysis.batch.failCount', { m: failedFiles.length }) }}
                </template>
              </span>
            </h3>
            <p class="or-hint">{{ t('orientationAnalysis.batch.hint') }}</p>
            <div class="or-table-wrap">
              <table class="or-table">
                <thead>
                  <tr>
                    <th>{{ t('orientationAnalysis.batch.file') }}</th>
                    <th v-if="methods.includes('hermans')">f (Hermans)</th>
                    <th v-if="methods.includes('hermans')">⟨cos²φ⟩</th>
                    <th v-if="methods.includes('fwhm')">f (FWHM)</th>
                    <th v-if="methods.includes('fwhm')">FWHM (°)</th>
                    <th>{{ t('orientationAnalysis.batch.warningsCol') }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="(item, idx) in batchItems"
                    :key="idx"
                    :class="{ 'or-row--active': idx === selectedResultIndex }"
                    @click="selectedResultIndex = idx"
                  >
                    <td class="or-file-name" :title="item.sourceLabel ?? ''">{{ fileName(item.sourceLabel ?? '') }}</td>
                    <td v-if="methods.includes('hermans')">{{ fmt(metric(item, 'hermans', 'f')) }}</td>
                    <td v-if="methods.includes('hermans')">{{ fmt(metric(item, 'hermans', 'cos2_phi')) }}</td>
                    <td v-if="methods.includes('fwhm')">{{ fmt(metric(item, 'fwhm', 'f')) }}</td>
                    <td v-if="methods.includes('fwhm')">{{ fmt(metric(item, 'fwhm', 'fwhm_deg')) }}°</td>
                    <td>{{ item.warnings?.length ?? 0 }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div v-if="failedFiles.length" class="or-failed">
              <strong>{{ t('orientationAnalysis.batch.failed') }}:</strong>
              <ul>
                <li v-for="(f, idx) in failedFiles" :key="idx">
                  <code>{{ f.file }}</code> — {{ f.reason }}
                </li>
              </ul>
            </div>
          </div>
        </template>

        <!-- Selected-detail view (single result or chosen batch row) -->
        <template v-if="detailData">
          <div v-if="detailLabel" class="or-detail-label">{{ detailLabel }}</div>

          <div v-if="detailData.warnings?.length" class="or-warnings">
            <h3 class="or-card-title">{{ t('orientationAnalysis.warnings') }}</h3>
            <ul>
              <li v-for="(w, idx) in detailData.warnings" :key="idx">{{ w }}</li>
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
          <div v-if="detailData.results?.length" class="or-results">
            <h2 class="or-section-title">{{ t('orientationAnalysis.resultsTitle') }}</h2>
            <div class="or-result-grid">
              <div v-for="(r, idx) in detailData.results" :key="idx" class="or-result-card">
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
          <div v-if="detailData.crystallinityHint && Object.keys(detailData.crystallinityHint).length" class="or-conf">
            <h3 class="or-card-title">{{ t('orientationAnalysis.confidence') }}</h3>
            <p class="or-hint">{{ detailData.crystallinityHint.note }}</p>
            <p v-if="detailData.crystallinityHint.correction_factor_guess" class="or-hint">
              {{ t('orientationAnalysis.correctionFactor') }}: ×{{ detailData.crystallinityHint.correction_factor_guess }}
            </p>
          </div>
        </template>
      </main>
    </div>
  </section>
</template>

<script setup lang="ts">
/**
 * OrientationAnalysisView.vue — 聚合物取向度分析
 * v0.2.5: multi-file batch under identical conditions + image preview showing
 * the beam center and the exact radial-selection ring (backend azimuth_mask).
 * v0.2.5：同一实验条件下的多文件批量分析 + 图像预览（光束中心 + 径向选区圆环蒙版）。
 */
import { ref, computed, watch, onUnmounted } from 'vue'
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
import ImagePreview from '@/components/charts/ImagePreview.vue'
import type { Overlay } from '@/components/charts/ImagePreview.vue'

const { t } = useI18n()
const toast = useToast()
const transport = useTransport()

// --- Input mode / 输入模式 ---
const inputMode = ref<'image' | 'curves'>('image')

// --- Image-mode state / 图像模式状态 ---
const files = ref<string[]>([])
const selectedFileIndex = ref(0)
const activeFilePath = computed(() => files.value[selectedFileIndex.value] ?? null)

const h5Datasets = ref<H5DatasetInfo[]>([])
const h5Selection = ref<H5Selection>({ dataset: '', channel: 0, frame: 0 })
const geometry = ref<GeometryParams>({
  pixel1: 172, pixel2: 172, distance: 200,
  wavelength: 1.5418, centerX: 512, centerY: 512,
})
const maskConfig = ref<MaskConfig>({
  valueRangeMin: 0, valueRangeMax: 2147483647,
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

// --- Preprocessing / 预处理 ---
const scatteringGeometry = ref<'transmission' | 'reflection'>('transmission')
const symmetry = ref<'auto' | 'friedel' | 'meridional_mirror' | 'equatorial_mirror' | 'none'>('none')
const missing = ref<'interp' | 'drop' | 'mirror'>('interp')
const bgMode = ref<'none' | 'constant' | 'linear'>('none')
const bgAutoEstimate = ref(true)

// --- Methods / 方法 ---
const methods = ref<string[]>(['hermans', 'fwhm'])
const chiZero = ref<'meridian' | 'equator'>('meridian')
const equatorialToChain = ref(true)
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
// Single-result payload, or {batch:true, items, failed} in batch mode.
// 单文件结果，或批量模式下的 {batch:true, items, failed}。
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const resultData = ref<any>(null)
const selectedResultIndex = ref(0)

// --- Image preview state (beam center + selection ring) / 图像预览状态 ---
const previewSrc = ref<string | null>(null)
const previewLoading = ref(false)
const previewSize = ref<{ width: number; height: number } | null>(null)
const beamCenter = ref<{ x: number; y: number } | null>(null)
const selectionMaskSrc = ref<string | null>(null)
const selectionMaskSize = ref<{ width: number; height: number } | null>(null)

let cleanupProgress: (() => void) | null = null
let cleanupResult: (() => void) | null = null
let cleanupError: (() => void) | null = null
let cleanupPreviewBinary: (() => void) | null = null
let cleanupPreviewResult: (() => void) | null = null
let cleanupPreviewError: (() => void) | null = null
let cleanupMaskBinary: (() => void) | null = null
let cleanupMaskResult: (() => void) | null = null
let cleanupMaskError: (() => void) | null = null
let maskDebounceTimer: ReturnType<typeof setTimeout> | undefined

function cleanupAll(): void {
  cleanupProgress?.()
  cleanupResult?.()
  cleanupError?.()
  cleanupProgress = cleanupResult = cleanupError = null
}

function cleanupPreviewListeners(): void {
  cleanupPreviewBinary?.()
  cleanupPreviewResult?.()
  cleanupPreviewError?.()
  cleanupPreviewBinary = cleanupPreviewResult = cleanupPreviewError = null
}

function cleanupMaskListeners(): void {
  cleanupMaskBinary?.()
  cleanupMaskResult?.()
  cleanupMaskError?.()
  cleanupMaskBinary = cleanupMaskResult = cleanupMaskError = null
}

const canRun = computed(() => {
  if (isRunning.value) return false
  if (methods.value.length === 0) return false
  if (inputMode.value === 'image') return files.value.length > 0
  return parsedChi.value.length >= 2
})

const runButtonLabel = computed(() =>
  inputMode.value === 'image' && files.value.length > 1
    ? t('orientationAnalysis.batch.runBtn', { n: files.value.length })
    : t('orientationAnalysis.run'),
)

const exportButtonLabel = computed(() =>
  batchItems.value
    ? t('orientationAnalysis.batch.exportSummary')
    : t('orientationAnalysis.exportCsv'),
)

const batchItems = computed<Record<string, any>[] | null>(() => {
  const d = resultData.value
  return d?.batch && Array.isArray(d.items) ? d.items : null
})

const failedFiles = computed<{ file: string; reason: string }[]>(() => {
  const d = resultData.value
  return Array.isArray(d?.failed) ? d.failed : []
})

/** Detail payload: the single result, or the selected batch row. */
const detailData = computed(() => {
  if (batchItems.value) {
    return batchItems.value[selectedResultIndex.value] ?? null
  }
  return resultData.value ?? null
})

const detailLabel = computed(() => {
  if (!batchItems.value || !detailData.value) return ''
  return detailData.value.sourceLabel ?? ''
})

const beamCenterLabel = computed(() => {
  if (!beamCenter.value) return ''
  return `(${beamCenter.value.x.toFixed(1)}, ${beamCenter.value.y.toFixed(1)}) px`
})

/** Preview overlays: selection ring mask + beam-center crosshair. */
const previewOverlays = computed<Overlay[]>(() => {
  const overlays: Overlay[] = []
  const size = selectionMaskSize.value ?? previewSize.value
  if (selectionMaskSrc.value && size) {
    overlays.push({
      type: 'imageMask',
      src: selectionMaskSrc.value,
      width: size.width,
      height: size.height,
    })
  }
  if (beamCenter.value) {
    overlays.push({ type: 'beamCenter', x: beamCenter.value.x, y: beamCenter.value.y })
  }
  return overlays
})

function fileName(path: string): string {
  if (!path) return ''
  const sep = path.includes('/') ? '/' : '\\'
  return path.split(sep).pop() ?? path
}

function toggleMethod(m: string): void {
  const i = methods.value.indexOf(m)
  if (i >= 0) methods.value.splice(i, 1)
  else methods.value.push(m)
}

/** Extract a metric from an analysis item's per-method results. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function metric(item: Record<string, any>, method: string, key: string): number | null {
  const entry = (item.results ?? []).find((r: Record<string, unknown>) => r.method === method)
  const v = entry?.[key]
  return typeof v === 'number' ? v : null
}

function fmt(v: number | null): string {
  if (v === null || !Number.isFinite(v)) return '—'
  return Math.abs(v) >= 100 || Math.abs(v) < 0.001 ? v.toExponential(3) : v.toFixed(4)
}

// ── File list management / 文件列表管理 ──

async function handleAddFiles(): Promise<void> {
  try {
    const result = await transport.selectFiles({
      filters: dataFileFilters,
      multiSelections: true,
    })
    if (!result) return
    const picked = Array.isArray(result) ? result : [result]
    const existing = new Set(files.value)
    const added = picked.filter(p => p && !existing.has(p))
    if (!added.length) return
    files.value = [...files.value, ...added]
    selectedFileIndex.value = files.value.length - added.length
  } catch (err) {
    toast.push({ title: t('orientationAnalysis.errorTitle'), message: String(err), tone: 'error' })
  }
}

function removeFile(idx: number): void {
  files.value.splice(idx, 1)
  if (selectedFileIndex.value >= files.value.length) {
    selectedFileIndex.value = Math.max(0, files.value.length - 1)
  }
}

function clearFiles(): void {
  files.value = []
  selectedFileIndex.value = 0
  revokePreview()
  selectionMaskSrc.value = null
  selectionMaskSize.value = null
  beamCenter.value = null
}

// ── Curves parsing / 曲线解析 ──

function parseCurves(): void {
  const chi: number[] = []
  const inten: number[] = []
  const lines = curvesText.value.trim().split(/\r?\n/)
  for (const line of lines) {
    const parts = line.trim().split(/[\s,;\t]+/).filter(Boolean)
    if (parts.length < 2) continue
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

async function loadCurvesFile(path: string | null): Promise<void> {
  if (!path) return
  try {
    const desktop = (window as unknown as { desktop?: { readTextFile?: (p: string) => Promise<string> } }).desktop
    if (desktop?.readTextFile) {
      curvesText.value = await desktop.readTextFile(path)
      parseCurves()
    }
  } catch (err) {
    toast.push({ title: t('orientationAnalysis.errorTitle'), message: String(err), tone: 'error' })
  }
}

// ── Image preview + selection mask / 图像预览 + 选区蒙版 ──

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

function submitAndWait(route: string, params: Record<string, unknown>): Promise<unknown> {
  return new Promise((resolve, reject) => {
    transport.submitTask(route, params).then(response => {
      transport.onTaskResult(response.taskId, (p) => resolve(p.data))
      transport.onTaskError(response.taskId, (p) => reject(new Error(p.error)))
    }).catch(reject)
  })
}

function revokePreview(): void {
  if (previewSrc.value?.startsWith('blob:')) {
    URL.revokeObjectURL(previewSrc.value)
  }
  previewSrc.value = null
}

async function resolveBeamCenter(): Promise<void> {
  try {
    const result = await submitAndWait('viewer_config', {
      action: 'resolve_geometry_center',
      geometry: buildGeometryPayload(),
    })
    const center = result as { centerX?: number; centerY?: number }
    if (typeof center.centerX === 'number' && typeof center.centerY === 'number') {
      beamCenter.value = { x: center.centerX, y: center.centerY }
      return
    }
  } catch {
    // Fall back to the form values below. / 失败时回退到表单值。
  }
  beamCenter.value = { x: geometry.value.centerX, y: geometry.value.centerY }
}

async function loadPreview(path: string): Promise<void> {
  previewLoading.value = true
  revokePreview()
  previewSize.value = null
  cleanupPreviewListeners()
  try {
    await resolveBeamCenter()
    const isH5 = h5Datasets.value.length > 0
    const response = await transport.submitTask('viewer_config', {
      action: 'open_file',
      filePath: path,
      frame: h5Selection.value.frame,
      ...(isH5 ? {
        dataset: h5Selection.value.dataset || undefined,
        channel: h5Selection.value.channel,
      } : {}),
      settings: {
        cmap: 'smooth_WAXS_foxtrot',
        use_log: false,
        clim_mode: 'auto',
        clim: [null, null],
        preview_scale: 1.0,
      },
    })

    cleanupPreviewBinary = transport.onTaskBinaryData(response.taskId, (payload) => {
      if (!payload.data) return
      revokePreview()
      const blob = new Blob([payload.data], { type: payload.mime || 'image/png' })
      previewSrc.value = URL.createObjectURL(blob)
      if (payload.width && payload.height) {
        previewSize.value = { width: payload.width, height: payload.height }
      }
    })

    cleanupPreviewResult = transport.onTaskResult(response.taskId, (payload) => {
      previewLoading.value = false
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const data = payload.data as any
      if (!previewSize.value) {
        const w = data?.metadata?.width ?? data?.width
        const h = data?.metadata?.height ?? data?.height
        if (w && h) previewSize.value = { width: w, height: h }
      }
      const h5 = data?.metadata?.h5Datasets
      if (Array.isArray(h5) && h5.length && !h5Datasets.value.length) {
        h5Datasets.value = h5
      }
    })

    cleanupPreviewError = transport.onTaskError(response.taskId, () => {
      previewLoading.value = false
    })
  } catch {
    previewLoading.value = false
  }
}

/** Backend azimuth_mask: per-pixel gray ring of the current radial range. */
async function loadSelectionMask(): Promise<void> {
  if (!activeFilePath.value || !previewSize.value) return
  const rMin = Number(radialMin.value)
  const rMax = Number(radialMax.value)
  if (!(Number.isFinite(rMin) && Number.isFinite(rMax) && rMin < rMax)) return

  cleanupMaskListeners()
  try {
    const response = await transport.submitTask('viewer_config', {
      action: 'azimuth_mask',
      filePath: activeFilePath.value,
      geometry: buildGeometryPayload(),
      radial_unit: radialUnit.value,
      radial_min: rMin,
      radial_max: rMax,
    })

    cleanupMaskBinary = transport.onTaskBinaryData(response.taskId, (payload) => {
      if (!payload.data) return
      if (selectionMaskSrc.value?.startsWith('blob:')) {
        URL.revokeObjectURL(selectionMaskSrc.value)
      }
      const blob = new Blob([payload.data], { type: payload.mime || 'image/png' })
      selectionMaskSrc.value = URL.createObjectURL(blob)
      const size = previewSize.value
      if (size) {
        selectionMaskSize.value = { width: size.width, height: size.height }
      }
    })

    cleanupMaskResult = transport.onTaskResult(response.taskId, (payload) => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const data = payload.data as any
      if (data?.status === 'error') {
        selectionMaskSrc.value = null
      }
    })

    cleanupMaskError = transport.onTaskError(response.taskId, () => {
      selectionMaskSrc.value = null
    })
  } catch {
    selectionMaskSrc.value = null
  }
}

function scheduleSelectionMask(): void {
  if (maskDebounceTimer) clearTimeout(maskDebounceTimer)
  maskDebounceTimer = setTimeout(() => {
    maskDebounceTimer = undefined
    void resolveBeamCenter()
    void loadSelectionMask()
  }, 300)
}

// Reload preview when the active file changes (image mode only).
watch(activeFilePath, (path) => {
  if (inputMode.value !== 'image' || !path) return
  h5Datasets.value = []
  h5Selection.value = { dataset: '', channel: 0, frame: 0 }
  selectionMaskSrc.value = null
  void loadPreview(path).then(() => scheduleSelectionMask())
})

// Refresh center + ring when geometry / radial range / unit changes (debounced).
watch(
  [geometry, radialMin, radialMax, radialUnit],
  () => {
    if (inputMode.value !== 'image' || !activeFilePath.value) return
    scheduleSelectionMask()
  },
  { deep: true },
)

// ── Task submission / 任务提交 ──

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
    p.files = [...files.value]
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

async function handleRun(overrideFiles?: string[]): Promise<void> {
  if (!canRun.value || isRunning.value) return
  isRunning.value = true
  progress.value = 0
  progressMessage.value = null
  errorMessage.value = null
  resultData.value = null
  chartTraces.value = []
  selectedResultIndex.value = 0

  try {
    const params = buildParams()
    if (overrideFiles) {
      params.files = [...overrideFiles]
    }
    const response = await transport.submitTask('orientation_analysis', params)
    taskId.value = response.taskId

    cleanupProgress = transport.onTaskProgress(response.taskId, (payload) => {
      progress.value = payload.progress
      progressMessage.value = payload.message ?? null
    })
    cleanupResult = transport.onTaskResult(response.taskId, (payload) => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const data = payload.data as Record<string, any>
      resultData.value = data
      // Charts show the single result, or the first batch item until a row is picked.
      buildChartTraces(data?.batch ? (data.items?.[0] ?? {}) : (data ?? {}))
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

// Row selection in batch mode drives the detail chart/cards.
watch(selectedResultIndex, () => {
  if (batchItems.value) {
    buildChartTraces(detailData.value ?? {})
  }
})

/** Run the analysis on ONLY the currently selected (previewed) file — the
 *  recommended workflow is to validate parameters on one frame first, then
 *  batch the whole list. / 仅对当前选中（预览中）的文件运行分析——推荐流程：
 *  先用单张验证参数效果，再批量处理整个列表。 */
function handleRunSingle(): void {
  if (!activeFilePath.value) return
  void handleRun([activeFilePath.value])
}

function handleCancel(): void {
  if (taskId.value) transport.cancelTask(taskId.value)
}

function formatNum(v: unknown): string {
  if (typeof v !== 'number' || !Number.isFinite(v)) return '—'
  return Math.abs(v) >= 100 || Math.abs(v) < 0.001 ? v.toExponential(3) : v.toFixed(4)
}

function downloadBlob(content: string, filename: string, mime = 'text/csv'): void {
  const blob = new Blob([content], { type: mime })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function exportCsv(): void {
  if (!resultData.value) return

  if (batchItems.value) {
    // Batch summary CSV / 批量汇总 CSV
    const cols: string[] = ['file']
    if (methods.value.includes('hermans')) cols.push('hermans_f', 'hermans_cos2_phi')
    if (methods.value.includes('fwhm')) cols.push('fwhm_f', 'fwhm_deg')
    cols.push('warnings')
    const lines = [cols.join(',')]
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    for (const item of batchItems.value as Record<string, any>[]) {
      const row: string[] = [JSON.stringify(item.sourceLabel ?? '')]
      if (methods.value.includes('hermans')) {
        row.push(String(metric(item, 'hermans', 'f') ?? ''), String(metric(item, 'hermans', 'cos2_phi') ?? ''))
      }
      if (methods.value.includes('fwhm')) {
        row.push(String(metric(item, 'fwhm', 'f') ?? ''), String(metric(item, 'fwhm', 'fwhm_deg') ?? ''))
      }
      row.push(JSON.stringify((item.warnings ?? []).join(' | ')))
      lines.push(row.join(','))
    }
    for (const f of failedFiles.value) {
      lines.push([JSON.stringify(f.file), '#FAILED', JSON.stringify(f.reason)].join(','))
    }
    downloadBlob(lines.join('\n'), 'orientation_batch_summary.csv')
    return
  }

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
  downloadBlob(lines.join('\n'), 'orientation_analysis.csv')
}

onUnmounted(() => {
  cleanupAll()
  cleanupPreviewListeners()
  cleanupMaskListeners()
  if (maskDebounceTimer) clearTimeout(maskDebounceTimer)
  revokePreview()
  if (selectionMaskSrc.value?.startsWith('blob:')) URL.revokeObjectURL(selectionMaskSrc.value)
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
.or-batch-meta { margin-left: 8px; font-size: 0.8rem; font-weight: 400; color: var(--color-text-muted, #6b7280); }
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
.or-hint-warn { color: #b45309; }
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
.or-file-list {
  list-style: none;
  margin: 0;
  padding: 0;
  max-height: 220px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.or-file-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  padding: 3px 6px;
  border-radius: 4px;
}
.or-file-item--active { background: rgba(37, 99, 235, 0.08); }
.or-file-name {
  font-family: monospace;
  font-size: 0.78rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 260px;
}
.or-preview-loading {
  padding: 40px 0;
  text-align: center;
  color: var(--color-text-muted, #6b7280);
  font-size: 0.88rem;
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
.or-detail-label {
  font-family: monospace;
  font-size: 0.8rem;
  color: var(--color-text-muted, #6b7280);
  word-break: break-all;
}
.or-table-wrap { overflow-x: auto; }
.or-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.84rem;
}
.or-table th, .or-table td {
  border-bottom: 1px solid var(--color-border, #e5e7eb);
  padding: 6px 8px;
  text-align: left;
}
.or-table th { font-weight: 600; color: var(--color-text-muted, #6b7280); white-space: nowrap; }
.or-table td { font-variant-numeric: tabular-nums; }
.or-table tbody tr { cursor: pointer; }
.or-table tbody tr:hover { background: rgba(37, 99, 235, 0.05); }
.or-row--active { background: rgba(37, 99, 235, 0.1); }
.or-failed {
  margin-top: 10px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 6px;
  padding: 8px 12px;
  font-size: 0.8rem;
}
.or-failed ul { margin: 4px 0 0; padding-left: 16px; }
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
