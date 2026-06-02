<template>
  <section class="cg-page">
    <header class="cg-header">
      <h1>{{ t('cellCalibrantGenerator.title') }}</h1>
      <p class="cg-subtitle">{{ t('cellCalibrantGenerator.subtitle') }}</p>
      <!-- Mode tabs / 模式切换 -->
      <div class="cg-tabs">
        <button
          type="button"
          :class="['cg-tab', { active: mode === 'cif' }]"
          @click="mode = 'cif'"
        >{{ t('cellCalibrantGenerator.cifMode') }}</button>
        <button
          type="button"
          :class="['cg-tab', { active: mode === 'cell' }]"
          @click="mode = 'cell'"
        >{{ t('cellCalibrantGenerator.cellMode') }}</button>
        <button
          type="button"
          :class="['cg-tab', { active: mode === 'manual' }]"
          @click="mode = 'manual'"
        >{{ t('cellCalibrantGenerator.manualMode') }}</button>
      </div>
    </header>

    <div class="cg-layout">
      <aside class="cg-sidebar">
        <!-- ── CIF mode / CIF 文件模式 ── -->
        <template v-if="mode === 'cif'">
          <div class="cg-section">
            <h2 class="cg-section-title">{{ t('calibrantGenerator.uploadFile') }}</h2>
            <button
              type="button"
              class="cg-file-btn"
              :disabled="state === 'running'"
              @click="handleSelectCifFile"
            >
              {{ t('calibrantGenerator.selectFile') }}
            </button>
            <div v-if="cifFilePath" class="cg-file-info">
              <span class="cg-file-name">{{ cifFileName }}</span>
              <button type="button" class="cg-clear-btn" @click="clearCifFile">×</button>
            </div>
          </div>

          <div class="cg-section">
            <h2 class="cg-section-title">{{ t('calibrantGenerator.intensityThreshold') }}</h2>
            <div class="cg-slider-group">
              <input type="range" class="cg-slider" min="0" max="10" step="0.1" v-model.number="intensityThreshold" />
              <span class="cg-slider-value">{{ intensityThreshold.toFixed(1) }}%</span>
            </div>
            <p class="cg-hint">{{ t('calibrantGenerator.thresholdHint') }}</p>
          </div>

          <div class="cg-action">
            <button
              type="button"
              class="cg-run-btn"
              :disabled="!cifFilePath || state === 'running'"
              @click="handleGenerateCif"
            >
              {{ state === 'running' ? t('business.taskProgress.processing') : t('calibrantGenerator.peaksPreview') }}
            </button>
          </div>
        </template>

        <!-- ── Cell params mode / 晶胞参数模式 ── -->
        <template v-if="mode === 'cell'">
        <!-- Crystal system / 晶系 -->
        <div class="cg-section">
          <h2 class="cg-section-title">{{ t('cellCalibrantGenerator.crystalSystem') }}</h2>
          <select class="cg-select" v-model="crystalSystem" @change="onCrystalSystemChange">
            <option v-for="(label, key) in CRYSTAL_SYSTEM_LABELS" :key="key" :value="key">
              {{ label }}
            </option>
          </select>
        </div>

        <!-- Lattice type / 点阵类型 -->
        <div class="cg-section">
          <h2 class="cg-section-title">{{ t('cellCalibrantGenerator.latticeType') }}</h2>
          <select class="cg-select" v-model="latticeType">
            <option v-for="lt in allowedLatticeTypes" :key="lt" :value="lt">
              {{ lt }} — {{ LATTICE_TYPE_NAMES[lt] || lt }}
            </option>
          </select>
        </div>

        <!-- Cell parameters / 晶胞参数 -->
        <div class="cg-section">
          <h2 class="cg-section-title">{{ t('cellCalibrantGenerator.cellParams') }}</h2>
          <div class="cg-params-grid">
            <div v-if="showParam('a')" class="cg-param">
              <label>{{ t('cellCalibrantGenerator.paramA') }}</label>
              <input type="number" class="cg-input" v-model.number="paramA" step="0.001" min="0.1" />
            </div>
            <div v-if="showParam('b')" class="cg-param">
              <label>{{ t('cellCalibrantGenerator.paramB') }}</label>
              <input type="number" class="cg-input" v-model.number="paramB" step="0.001" min="0.1" />
            </div>
            <div v-if="showParam('c')" class="cg-param">
              <label>{{ t('cellCalibrantGenerator.paramC') }}</label>
              <input type="number" class="cg-input" v-model.number="paramC" step="0.001" min="0.1" />
            </div>
            <div v-if="showParam('alpha')" class="cg-param">
              <label>{{ t('cellCalibrantGenerator.paramAlpha') }}</label>
              <input type="number" class="cg-input" v-model.number="paramAlpha" step="0.1" min="0" max="180" />
            </div>
            <div v-if="showParam('beta')" class="cg-param">
              <label>{{ t('cellCalibrantGenerator.paramBeta') }}</label>
              <input type="number" class="cg-input" v-model.number="paramBeta" step="0.1" min="0" max="180" />
            </div>
            <div v-if="showParam('gamma')" class="cg-param">
              <label>{{ t('cellCalibrantGenerator.paramGamma') }}</label>
              <input type="number" class="cg-input" v-model.number="paramGamma" step="0.1" min="0" max="180" />
            </div>
          </div>
        </div>

        <!-- Space group / 空间群 -->
        <div class="cg-section">
          <h2 class="cg-section-title">{{ t('cellCalibrantGenerator.spaceGroup') }}</h2>
          <div class="cg-combobox" ref="comboboxRef">
            <input
              type="text"
              class="cg-input"
              v-model="spaceGroupInput"
              :placeholder="spaceGroupNumber > 0 ? `${spaceGroupNumber} — ${selectedSpaceGroupLabel}` : 'Search...'"
              @focus="sgDropdownOpen = true"
              @input="onSgInput"
              @keydown.enter="confirmSgHighlighted"
              @keydown.escape="sgDropdownOpen = false"
              @keydown.down.prevent="sgHighlightNext(1)"
              @keydown.up.prevent="sgHighlightNext(-1)"
            />
            <div v-if="sgDropdownOpen && filteredSpaceGroups.length > 0" class="cg-combobox-list">
              <div
                v-for="(sg, idx) in filteredSpaceGroups"
                :key="sg.number"
                :class="['cg-combobox-item', { 'cg-combobox-item--active': idx === sgHighlightIdx, 'cg-combobox-item--selected': sg.number === spaceGroupNumber }]"
                @mousedown.prevent="selectSpaceGroup(sg)"
                @mouseenter="sgHighlightIdx = idx"
              >
                <span class="cg-sg-num">{{ sg.number }}</span>
                <span class="cg-sg-symbol">{{ sg.hmSymbol }}</span>
              </div>
            </div>
            <div v-if="!sgLoaded && spaceGroupsLoading" class="cg-combobox-hint">Loading...</div>
            <div v-if="!sgLoaded && !spaceGroupsLoading && allSpaceGroups.length === 0" class="cg-combobox-hint">No space groups loaded</div>
          </div>
        </div>

        <!-- Material name / 材料名称 -->
        <div class="cg-section">
          <h2 class="cg-section-title">{{ t('cellCalibrantGenerator.materialName') }}</h2>
          <input
            type="text"
            class="cg-input"
            v-model="materialName"
            :placeholder="t('cellCalibrantGenerator.materialNamePlaceholder')"
          />
        </div>

        <!-- dmin slider -->
        <div class="cg-section">
          <h2 class="cg-section-title">{{ t('cellCalibrantGenerator.dmin') }}</h2>
          <div class="cg-slider-group">
            <input
              type="range"
              class="cg-slider"
              min="0.3"
              max="6.0"
              step="0.05"
              v-model.number="dmin"
            />
            <span class="cg-slider-value">{{ dmin.toFixed(2) }} Å</span>
          </div>
          <p class="cg-hint">{{ t('cellCalibrantGenerator.dminHint') }}</p>
        </div>

        <!-- Generate button / 生成按钮 -->
        <div class="cg-action">
          <button
            type="button"
            class="cg-run-btn"
            :disabled="state === 'running'"
            @click="handleGenerate"
          >
            {{ state === 'running'
              ? t('cellCalibrantGenerator.generating')
              : t('cellCalibrantGenerator.generate') }}
          </button>
        </div>

        </template>

        <!-- ── Manual input mode / 手动列表模式 ── -->
        <template v-if="mode === 'manual'">
          <div class="cg-section">
            <h2 class="cg-section-title">{{ t('cellCalibrantGenerator.inputUnit') }}</h2>
            <div class="cg-unit-tabs">
              <button type="button" :class="['cg-unit-tab', { active: manualUnit === 'd' }]" @click="manualUnit = 'd'">d (Å)</button>
              <button type="button" :class="['cg-unit-tab', { active: manualUnit === 'q' }]" @click="manualUnit = 'q'">q (Å⁻¹)</button>
              <button type="button" :class="['cg-unit-tab', { active: manualUnit === '2theta' }]" @click="manualUnit = '2theta'">2θ (°)</button>
            </div>
          </div>

          <div v-if="manualUnit === '2theta'" class="cg-section">
            <h2 class="cg-section-title">{{ t('cellCalibrantGenerator.wavelength') }}</h2>
            <input type="number" class="cg-input" v-model.number="manualWavelength" step="0.001" min="0.1" />
          </div>

          <div class="cg-section cg-section--grow">
            <h2 class="cg-section-title">
              {{ t('cellCalibrantGenerator.inputValues') }}
              <span class="cg-unit-hint">{{ t('cellCalibrantGenerator.inputHint') }}</span>
            </h2>
            <textarea
              class="cg-textarea"
              v-model="manualInput"
              rows="12"
              placeholder="4.1569&#10;2.9394&#10;2.4000&#10;..."
            ></textarea>
          </div>

          <div class="cg-action">
            <button
              type="button"
              class="cg-run-btn"
              :disabled="!manualInput.trim() || state === 'running'"
              @click="handleManualGenerate"
            >
              {{ state === 'running' ? t('cellCalibrantGenerator.generating') : t('cellCalibrantGenerator.generate') }}
            </button>
          </div>
        </template>

        <TaskProgressBar
          v-if="state === 'running'"
          :task-id="taskId"
          :progress="progress"
          :message="progressMessage"
          @cancel="handleCancel"
        />
      </aside>

      <main class="cg-main">
        <div v-if="state === 'error'" class="cg-error">
          <p>{{ errorMessage }}</p>
        </div>

        <!-- CIF crystal info / CIF 晶体信息 -->
        <div v-if="mode === 'cif' && cifFormula" class="cg-crystal-info">
          <h2 class="cg-section-title">{{ t('calibrantGenerator.crystalInfo') }}</h2>
          <div class="cg-info-grid">
            <div class="cg-info-item">
              <span class="cg-info-label">{{ t('calibrantGenerator.formula') }}</span>
              <span class="cg-info-value">{{ cifFormula }}</span>
            </div>
            <div class="cg-info-item">
              <span class="cg-info-label">{{ t('calibrantGenerator.latticeParams') }}</span>
              <span class="cg-info-value cg-mono">
                a={{ cifLatticeParams.a }}  b={{ cifLatticeParams.b }}  c={{ cifLatticeParams.c }}<br>
                α={{ cifLatticeParams.alpha }}°  β={{ cifLatticeParams.beta }}°  γ={{ cifLatticeParams.gamma }}°
              </span>
            </div>
          </div>
        </div>

        <!-- XRD Peak Chart / 衍射峰位图 (CIF mode only) -->
        <div v-if="mode === 'cif' && allPeaks.length > 0" class="cg-chart-section">
          <div class="cg-chart-header">
            <h2 class="cg-section-title">{{ t('calibrantGenerator.xrdPattern') }}</h2>
            <div class="cg-scale-toggle">
              <button type="button" :class="['cg-scale-btn', { active: yScaleType === 'log' }]" @click="yScaleType = 'log'">Log</button>
              <button type="button" :class="['cg-scale-btn', { active: yScaleType === 'linear' }]" @click="yScaleType = 'linear'">Linear</button>
            </div>
          </div>
          <PlotlyChart :data="chartData" :layout="chartLayout" :dark-mode="true" />
        </div>

        <!-- Crystal info / 晶体信息 (cell mode) -->
        <div v-if="mode === 'cell' && peaks.length > 0" class="cg-crystal-info">
          <h2 class="cg-section-title">{{ t('cellCalibrantGenerator.crystalInfo') }}</h2>
          <div class="cg-info-grid">
            <div class="cg-info-item">
              <span class="cg-info-label">{{ t('cellCalibrantGenerator.crystalSystem') }}</span>
              <span class="cg-info-value">{{ crystalSystemLabel }}</span>
            </div>
            <div class="cg-info-item">
              <span class="cg-info-label">{{ t('cellCalibrantGenerator.latticeType') }}</span>
              <span class="cg-info-value">{{ latticeType }}</span>
            </div>
            <div class="cg-info-item">
              <span class="cg-info-label">{{ t('cellCalibrantGenerator.spaceGroup') }}</span>
              <span class="cg-info-value">{{ spaceGroupNumber }} — {{ selectedSpaceGroupLabel }}</span>
            </div>
            <div class="cg-info-item">
              <span class="cg-info-label">{{ t('cellCalibrantGenerator.cellParams') }}</span>
              <span class="cg-info-value cg-mono">{{ cellParamsDisplay }}</span>
            </div>
          </div>
        </div>

        <!-- Peaks table / 峰表 -->
        <div v-if="peaks.length > 0" class="cg-peaks-section">
          <h2 class="cg-section-title">
            {{ t('cellCalibrantGenerator.reflectionsPreview') }}
            <span class="cg-peaks-count">{{ t('cellCalibrantGenerator.peaksCount', { count: peaks.length }) }}</span>
          </h2>
          <div class="cg-table-wrapper">
            <table class="cg-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>{{ t('cellCalibrantGenerator.table.dSpacing') }}</th>
                  <th v-if="mode === 'cif'">{{ t('calibrantGenerator.table.intensity') }}</th>
                  <th v-if="mode === 'cif'">{{ t('calibrantGenerator.table.twoTheta') }}</th>
                  <th>{{ t('cellCalibrantGenerator.table.hkl') }}</th>
                  <th v-if="mode !== 'cif'">{{ t('cellCalibrantGenerator.table.multiplicity') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(peak, idx) in peaks" :key="idx">
                  <td class="cg-mono">{{ idx + 1 }}</td>
                  <td class="cg-mono">{{ peak.dSpacing.toFixed(6) }}</td>
                  <td v-if="mode === 'cif'" class="cg-mono">{{ peak.intensity }}%</td>
                  <td v-if="mode === 'cif'" class="cg-mono">{{ peak.twoTheta.toFixed(2) }}</td>
                  <td class="cg-mono">{{ peak.hkl }}</td>
                  <td v-if="mode !== 'cif'" class="cg-mono">{{ peak.multiplicity }}</td>
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
              {{ t('cellCalibrantGenerator.downloadFile') }}
            </button>
          </div>
        </div>

        <!-- Empty state -->
        <div v-if="state === 'idle' && peaks.length === 0 && !errorMessage" class="cg-empty">
          <p>{{ t('cellCalibrantGenerator.subtitle') }}</p>
        </div>
      </main>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useToast } from '@/lib/toast'
import TaskProgressBar from '@/components/business/TaskProgressBar.vue'
import PlotlyChart from '@/components/charts/PlotlyChart.vue'
import type { PlotData as PlotlyData, Layout as PlotlyLayout } from 'plotly.js-dist-min'
import { useTransport } from '@/lib/transport'

const { t } = useI18n()
const toast = useToast()
const transport = useTransport()

// ── Constants / 常量 ─────────────────────────────────────────────────────

interface SpaceGroup {
  number: number
  hmSymbol: string
  hmRaw: string
  crystalSystem: string
}

const CRYSTAL_SYSTEM_LABELS: Record<string, string> = {
  cubic: 'Cubic / 立方',
  tetragonal: 'Tetragonal / 四方',
  hexagonal: 'Hexagonal / 六方',
  rhombohedral: 'Rhombohedral / 菱方',
  orthorhombic: 'Orthorhombic / 正交',
  monoclinic: 'Monoclinic / 单斜',
  triclinic: 'Triclinic / 三斜',
}

const LATTICE_TYPE_NAMES: Record<string, string> = {
  P: 'Primitive / 简单',
  I: 'Body-centered / 体心',
  F: 'Face-centered / 面心',
  A: 'A-centered / A面带心',
  B: 'B-centered / B面带心',
  C: 'C-centered / C面带心',
  R: 'Rhombohedral / 菱方',
}

const CRYSTAL_SYSTEM_RANGES: Record<string, [number, number]> = {
  triclinic: [1, 2],
  monoclinic: [3, 15],
  orthorhombic: [16, 74],
  tetragonal: [75, 142],
  rhombohedral: [143, 167],
  hexagonal: [168, 194],
  cubic: [195, 230],
}

const LATTICE_TYPES_BY_SYSTEM: Record<string, string[]> = {
  triclinic: ['P'],
  monoclinic: ['P', 'B', 'A', 'C', 'I', 'F'],
  orthorhombic: ['P', 'C', 'A', 'B', 'I', 'F'],
  tetragonal: ['P', 'I'],
  rhombohedral: ['P', 'R'],
  hexagonal: ['P', 'R'],
  cubic: ['P', 'I', 'F'],
}

const CELL_PARAMS_BY_SYSTEM: Record<string, string[]> = {
  cubic: ['a'],
  tetragonal: ['a', 'c'],
  hexagonal: ['a', 'c'],
  rhombohedral: ['a', 'alpha'],
  orthorhombic: ['a', 'b', 'c'],
  monoclinic: ['a', 'b', 'c', 'beta'],
  triclinic: ['a', 'b', 'c', 'alpha', 'beta', 'gamma'],
}

/** Built-in space group symbols (Hermann-Mauguin) / 内建空间群符号表 */
const SG_SYMBOLS: string[] = [
  "P1","P-1","P2","P2₁","C2","Pm","Pc","Cm","Cc","P2/m","P2₁/m","C2/m","P2/c","P2₁/c","C2/c",
  "P222","P222₁","P2₁2₁2","P2₁2₁2₁","C222₁","C222","F222","I222","I2₁2₁2₁",
  "Pmm2","Pmc2₁","Pcc2","Pma2","Pca2₁","Pnc2","Pmn2₁","Pba2","Pna2₁","Pnn2","Cmm2","Cmc2₁","Ccc2","Amm2","Aem2","Ama2","Aea2","Fmm2","Fdd2","Imm2","Iba2","Ima2",
  "Pmmm","Pnnn","Pccm","Pban","Pmma","Pnma","Pmna","Pcca","Pbam","Pccn","Pbcm","Pnnm","Pmmn","Pbcn","Pbca","Pnma","Cmcm","Cmce","Cmmm","Cccm","Cmme","Ccce","Fmmm","Fddd","Immm","Ibam","Ibca","Imma",
  "P4","P4₁","P4₂","P4₃","I4","I4₁","P-4","I-4","P4/m","P4₂/m","P4/n","P4₂/n","I4/m","I4₁/a",
  "P422","P4₁22","P4₂22","P4₃22","P4₂2₁2","P4₁2₁2","P4₃2₁2","P4₂2₁2","I422","I4₁22",
  "P4mm","P4bm","P4₂cm","P4₂nm","P4cc","P4nc","P4₂mc","P4₂bc","I4mm","I4cm","I4₁md","I4₁cd",
  "P-42m","P-42c","P-42₁m","P-42₁c","P-4m2","P-4c2","P-4b2","P-4n2","I-4m2","I-4c2","I-42m","I-42d",
  "P4/mmm","P4/mcc","P4/nbm","P4/nnc","P4/mbm","P4/mnc","P4/nmm","P4/ncc","P4₂/mmc","P4₂/mcm","P4₂/nbc","P4₂/nnm","P4₂/mbc","P4₂/mnm","P4₂/nmc","P4₂/ncm","I4/mmm","I4/mcm","I4₁/amd","I4₁/acd",
  "P3","P3₁","P3₂","R3","P-3","R-3","P312","P321","P3₁12","P3₁21","P3₂12","P3₂21","R32","P3m1","P31m","P3c1","P31c","R3m","R3c","P-31m","P-31c","P-3m1","P-3c1","R-3m","R-3c",
  "P6","P6₁","P6₅","P6₂","P6₄","P6₃","P-6","P6/m","P6₃/m","P622","P6₁22","P6₅22","P6₂22","P6₄22","P6₃22",
  "P6mm","P6cc","P6₃cm","P6₃mc","P-6m2","P-6c2","P-62m","P-62c","P6/mmm","P6/mcc","P6₃/mcm","P6₃/mmc",
  "P23","F23","I23","P2₁3","I2₁3","Pm-3","Pn-3","Fm-3","Fd-3","Im-3","Pa-3","Ia-3",
  "P432","P4₂32","F432","F4₁32","I432","P4₃32","P4₁32","I4₁32",
  "P-43m","F-43m","I-43m","P-43n","F-43c","I-43d","Pm-3m","Pn-3n","Pm-3n","Pn-3m","Fm-3m","Fm-3c","Fd-3m","Fd-3c","Im-3m","Ia-3d",
]
const DEFAULT_SPACE_GROUPS: SpaceGroup[] = SG_SYMBOLS.map((sym, i) => {
  const n = i + 1
  let cs = 'triclinic'
  for (const [sys, [lo, hi]] of Object.entries(CRYSTAL_SYSTEM_RANGES)) {
    if (n >= lo && n <= hi) { cs = sys; break }
  }
  return { number: n, hmSymbol: sym, hmRaw: sym, crystalSystem: cs }
})

// ── State / 状态 ─────────────────────────────────────────────────────────

type PageState = 'idle' | 'running' | 'done' | 'error'

const state = ref<PageState>('idle')
const taskId = ref<string | null>(null)
const progress = ref(0)
const progressMessage = ref<string | null>(null)
const errorMessage = ref('')

// Mode toggle / 模式切换
const mode = ref<'cif' | 'cell' | 'manual'>('cif')
// CIF mode / CIF 文件模式
const cifFilePath = ref<string | null>(null)
const intensityThreshold = ref(1.0)
const cifFormula = ref('')
const cifLatticeParams = ref({ a: 0, b: 0, c: 0, alpha: 0, beta: 0, gamma: 0 })
const allPeaks = ref<Array<{ dSpacing: number; intensity: number; twoTheta: number; hkl: string; multiplicity: number }>>([])
const yScaleType = ref<'log' | 'linear'>('linear')
// Manual input / 手动输入
const manualInput = ref('')
const manualUnit = ref<'d' | 'q' | '2theta'>('d')
const manualWavelength = ref(1.5406)  // Cu Kα

const crystalSystem = ref('triclinic')
const latticeType = ref('P')
const spaceGroupNumber = ref(1)
const materialName = ref('calibrate')
const dmin = ref(1.0)

const paramA = ref(4.1569)
const paramB = ref(4.1569)
const paramC = ref(4.1569)
const paramAlpha = ref(90)
const paramBeta = ref(90)
const paramGamma = ref(90)

const allSpaceGroups = ref<SpaceGroup[]>([])
const sgLoaded = ref(false)
const spaceGroupsLoading = ref(true)
const peaks = ref<Array<{ dSpacing: number; hkl: string; multiplicity: number }>>([])
const dFileContent = ref('')

// Combobox state / 组合框状态
const comboboxRef = ref<HTMLElement | null>(null)
const spaceGroupInput = ref('')
const sgDropdownOpen = ref(false)
const sgHighlightIdx = ref(0)
const sgSearch = ref('')

// ── Computed / 计算属性 ──────────────────────────────────────────────────

const cifFileName = computed(() => {
  if (!cifFilePath.value) return ''
  const sep = cifFilePath.value.includes('/') ? '/' : '\\'
  const parts = cifFilePath.value.split(sep)
  return parts[parts.length - 1] || cifFilePath.value
})

const chartData = computed<PlotlyData[]>(() => {
  if (allPeaks.value.length === 0) return []
  const sorted = [...allPeaks.value].sort((a, b) => a.twoTheta - b.twoTheta)
  const floorVal = 0.01
  const xVals: number[] = []
  const yVals: number[] = []
  sorted.forEach(p => {
    xVals.push(p.twoTheta, p.twoTheta, null)
    yVals.push(floorVal, p.intensity, null)
  })
  const stickTrace: PlotlyData = {
    x: xVals, y: yVals,
    type: 'scatter' as const, mode: 'lines',
    line: { color: '#3b82f6', width: 2 },
    name: 'Peaks',
  }
  const thr = intensityThreshold.value
  const xMin = sorted[0].twoTheta
  const xMax = sorted[sorted.length - 1].twoTheta
  const thresholdTrace: PlotlyData = {
    x: [xMin, xMax], y: [thr, thr],
    type: 'scatter' as const, mode: 'lines',
    line: { dash: 'dash', color: '#ef4444', width: 1.5 },
    name: `Threshold: ${thr}%`,
  }
  return [stickTrace, thresholdTrace]
})

const chartLayout = computed<Partial<PlotlyLayout>>(() => {
  const isLog = yScaleType.value === 'log'
  const yaxis: Partial<PlotlyLayout['yaxis']> = {
    type: yScaleType.value,
    title: { text: 'Relative Intensity (%)' },
  }
  if (isLog) {
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

const allowedLatticeTypes = computed(() => {
  return LATTICE_TYPES_BY_SYSTEM[crystalSystem.value] || ['P']
})

const filteredSpaceGroups = computed(() => {
  const [lo, hi] = CRYSTAL_SYSTEM_RANGES[crystalSystem.value] || [1, 230]
  let list = allSpaceGroups.value.filter(sg => sg.number >= lo && sg.number <= hi)
  const q = sgSearch.value.trim().toLowerCase()
  if (q) {
    list = list.filter(sg =>
      String(sg.number).includes(q) ||
      sg.hmSymbol.toLowerCase().includes(q)
    )
  }
  return list
})

const selectedSpaceGroupLabel = computed(() => {
  const found = allSpaceGroups.value.find(sg => sg.number === spaceGroupNumber.value)
  return found ? found.hmSymbol : ''
})

const crystalSystemLabel = computed(() => {
  return CRYSTAL_SYSTEM_LABELS[crystalSystem.value] || crystalSystem.value
})

const cellParamsDisplay = computed(() => {
  const parts: string[] = []
  if (showParam('a')) parts.push(`a=${paramA.value.toFixed(4)}`)
  if (showParam('b')) parts.push(`b=${paramB.value.toFixed(4)}`)
  if (showParam('c')) parts.push(`c=${paramC.value.toFixed(4)}`)
  if (showParam('alpha')) parts.push(`α=${paramAlpha.value.toFixed(1)}°`)
  if (showParam('beta')) parts.push(`β=${paramBeta.value.toFixed(1)}°`)
  if (showParam('gamma')) parts.push(`γ=${paramGamma.value.toFixed(1)}°`)
  return parts.join('  ')
})

function showParam(name: string): boolean {
  const params = CELL_PARAMS_BY_SYSTEM[crystalSystem.value]
  return params ? params.includes(name) : true
}

// ── Lifecycle / 生命周期 ─────────────────────────────────────────────────

onMounted(() => {
  allSpaceGroups.value = DEFAULT_SPACE_GROUPS
  sgLoaded.value = true
  spaceGroupsLoading.value = false
  spaceGroupNumber.value = 1
})

// ── Click-outside / 点击外部关闭 ──────────────────────────────────────────

function onSgDocumentClick(e: MouseEvent): void {
  if (comboboxRef.value && !comboboxRef.value.contains(e.target as Node)) {
    sgDropdownOpen.value = false
  }
}

onMounted(() => document.addEventListener('click', onSgDocumentClick))
onUnmounted(() => document.removeEventListener('click', onSgDocumentClick))

// Clear results when switching modes / 切换模式时清空结果
watch(mode, () => {
  peaks.value = []
  allPeaks.value = []
  dFileContent.value = ''
  cifFormula.value = ''
  state.value = 'idle'
  errorMessage.value = ''
})

// ── Combobox handlers / 组合框事件 ──────────────────────────────────────

function onSgInput(): void {
  sgSearch.value = spaceGroupInput.value
  sgDropdownOpen.value = true
  sgHighlightIdx.value = 0
}

function sgHighlightNext(dir: number): void {
  const len = filteredSpaceGroups.value.length
  if (len === 0) return
  sgHighlightIdx.value = (sgHighlightIdx.value + dir + len) % len
}

function confirmSgHighlighted(): void {
  if (filteredSpaceGroups.value.length === 0) return
  const idx = Math.min(sgHighlightIdx.value, filteredSpaceGroups.value.length - 1)
  selectSpaceGroup(filteredSpaceGroups.value[idx])
}

function selectSpaceGroup(sg: SpaceGroup): void {
  spaceGroupNumber.value = sg.number
  spaceGroupInput.value = ''
  sgSearch.value = ''
  sgDropdownOpen.value = false
}

// ── Handlers / 事件处理 ──────────────────────────────────────────────────

function onCrystalSystemChange(): void {
  const types = LATTICE_TYPES_BY_SYSTEM[crystalSystem.value] || ['P']
  if (!types.includes(latticeType.value)) {
    latticeType.value = types[0]
  }
  const filtered = filteredSpaceGroups.value
  if (filtered.length > 0 && !filtered.some(sg => sg.number === spaceGroupNumber.value)) {
    spaceGroupNumber.value = filtered[0].number
  }
  // Reset params to sensible defaults
  if (crystalSystem.value === 'cubic') {
    paramB.value = paramA.value
    paramC.value = paramA.value
    paramAlpha.value = 90
    paramBeta.value = 90
    paramGamma.value = 90
  }
}

// ── CIF handlers / CIF 文件处理 ─────────────────────────────────────────

async function handleSelectCifFile(): Promise<void> {
  const result = await transport.selectFiles({
    filters: [{ name: 'CIF Files', extensions: ['cif'] }],
    multiSelections: false,
  })
  if (!result) return
  const filePath = Array.isArray(result) ? result[0] : result
  if (!filePath) return

  cifFilePath.value = filePath
  clearCifResults()
}

function clearCifFile(): void {
  cifFilePath.value = null
  clearCifResults()
}

function clearCifResults(): void {
  cifFormula.value = ''
  peaks.value = []
  allPeaks.value = []
  dFileContent.value = ''
  state.value = 'idle'
  errorMessage.value = ''
}

async function handleGenerateCif(): Promise<void> {
  if (!cifFilePath.value || state.value === 'running') return

  state.value = 'running'
  progress.value = 0
  progressMessage.value = null
  errorMessage.value = ''
  cifFormula.value = ''
  peaks.value = []
  allPeaks.value = []
  dFileContent.value = ''

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
        message?: string
      }

      if (data?.status === 'error') {
        state.value = 'error'
        errorMessage.value = data.message || 'Generation failed.'
        toast.push({ title: t('calibrantGenerator.error.parseError'), message: errorMessage.value, tone: 'error' })
        return
      }

      if (data?.formula) cifFormula.value = data.formula
      if (data?.latticeParams) cifLatticeParams.value = data.latticeParams
      if (data?.peaks) peaks.value = data.peaks
      if (data?.allPeaks) allPeaks.value = data.allPeaks
      if (data?.dFileContent) dFileContent.value = data.dFileContent

      taskId.value = null
      state.value = 'done'
      progress.value = 1
    })

    cleanupError = transport.onTaskError(response.taskId, (payload) => {
      taskId.value = null
      errorMessage.value = payload.error
      state.value = 'error'
      toast.push({ title: t('calibrantGenerator.error.parseError'), message: payload.error, tone: 'error' })
    })
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : String(err)
    state.value = 'error'
    toast.push({ title: t('calibrantGenerator.error.parseError'), message: errorMessage.value, tone: 'error' })
  }
}

async function handleGenerate(): Promise<void> {
  state.value = 'running'
  progress.value = 0
  progressMessage.value = null
  errorMessage.value = ''
  peaks.value = []
  dFileContent.value = ''

  cleanupListeners()

  // Build params dict based on crystal system
  const params: Record<string, unknown> = {
    lattice: crystalSystem.value,
    latticeType: latticeType.value,
    spaceGroupNumber: spaceGroupNumber.value,
    longName: materialName.value || 'User Calibrant',
    dmin: dmin.value,
    a: paramA.value,
    b: showParam('b') ? paramB.value : paramA.value,
    c: showParam('c') ? paramC.value : paramA.value,
    alpha: showParam('alpha') ? paramAlpha.value : 90,
    beta: showParam('beta') ? paramBeta.value : 90,
    gamma: showParam('gamma') ? paramGamma.value : 90,
  }

  try {
    const response = await transport.submitTask('cell_calibrant_generate', params)
    taskId.value = response.taskId

    cleanupProgress = transport.onTaskProgress(response.taskId, (payload) => {
      progress.value = payload.progress
      progressMessage.value = payload.message ?? null
    })

    cleanupResult = transport.onTaskResult(response.taskId, (payload) => {
      const data = payload.data as {
        status?: string
        peaks?: Array<{ dSpacing: number; hkl: string; multiplicity: number }>
        dFileContent?: string
        peaksCount?: number
        message?: string
      }

      if (data?.status === 'error') {
        state.value = 'error'
        errorMessage.value = data.message || 'Generation failed.'
        toast.push({ title: t('cellCalibrantGenerator.generateError'), message: errorMessage.value, tone: 'error' })
        return
      }

      if (data?.peaks) peaks.value = data.peaks
      if (data?.dFileContent) dFileContent.value = data.dFileContent

      taskId.value = null

      if (peaks.value.length === 0) {
        state.value = 'error'
        errorMessage.value = t('cellCalibrantGenerator.noReflectionsWarning')
        toast.push({ title: t('cellCalibrantGenerator.generateError'), message: errorMessage.value, tone: 'warning' })
        return
      }

      state.value = 'done'
      progress.value = 1
    })

    cleanupError = transport.onTaskError(response.taskId, (payload) => {
      taskId.value = null
      errorMessage.value = payload.error
      state.value = 'error'
      toast.push({ title: t('cellCalibrantGenerator.generateError'), message: payload.error, tone: 'error' })
    })
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : String(err)
    state.value = 'error'
    toast.push({ title: t('cellCalibrantGenerator.generateError'), message: errorMessage.value, tone: 'error' })
  }
}

async function handleManualGenerate(): Promise<void> {
  const text = manualInput.value.trim()
  if (!text) return

  state.value = 'running'
  progress.value = 0
  progressMessage.value = null
  errorMessage.value = ''
  peaks.value = []
  dFileContent.value = ''

  cleanupListeners()

  try {
    const response = await transport.submitTask('manual_calibrant_generate', {
      values: text,
      unit: manualUnit.value,
      wavelength: manualWavelength.value,
    })
    taskId.value = response.taskId

    cleanupProgress = transport.onTaskProgress(response.taskId, (payload) => {
      progress.value = payload.progress
      progressMessage.value = payload.message ?? null
    })

    cleanupResult = transport.onTaskResult(response.taskId, (payload) => {
      const data = payload.data as {
        status?: string
        peaks?: Array<{ dSpacing: number; hkl: string; multiplicity: number }>
        dFileContent?: string
        peaksCount?: number
        message?: string
      }

      if (data?.status === 'error') {
        state.value = 'error'
        errorMessage.value = data.message || 'Generation failed.'
        toast.push({ title: t('cellCalibrantGenerator.generateError'), message: errorMessage.value, tone: 'error' })
        return
      }

      if (data?.peaks) peaks.value = data.peaks
      if (data?.dFileContent) dFileContent.value = data.dFileContent

      taskId.value = null
      state.value = 'done'
      progress.value = 1
    })

    cleanupError = transport.onTaskError(response.taskId, (payload) => {
      taskId.value = null
      errorMessage.value = payload.error
      state.value = 'error'
      toast.push({ title: t('cellCalibrantGenerator.generateError'), message: payload.error, tone: 'error' })
    })
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : String(err)
    state.value = 'error'
    toast.push({ title: t('cellCalibrantGenerator.generateError'), message: errorMessage.value, tone: 'error' })
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
      toast.push({ title: t('cellCalibrantGenerator.noFile'), message: '', tone: 'warning' })
      resolve()
      return
    }

    const blob = new Blob([dFileContent.value], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    const stem = materialName.value?.replace(/\s+/g, '_') || 'calibrant'
    a.download = `${stem}.D`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    resolve()
  })
}

// ── Cleanup / 清理 ───────────────────────────────────────────────────────

let cleanupProgress: (() => void) | null = null
let cleanupResult: (() => void) | null = null
let cleanupError: (() => void) | null = null

function cleanupListeners(): void {
  cleanupProgress?.()
  cleanupProgress = null
  cleanupResult?.()
  cleanupResult = null
  cleanupError?.()
  cleanupError = null
}

onUnmounted(() => { cleanupListeners() })
</script>

<style scoped>
.cg-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
  overflow-x: hidden;
}

.cg-header { padding-bottom: 8px; }

/* Mode tabs / 模式切换标签 */
.cg-tabs {
  display: flex;
  gap: 0;
  margin-top: 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
  align-self: flex-start;
}

.cg-tab {
  padding: 8px 20px;
  border: none;
  background: var(--bg-surface);
  color: var(--text-secondary);
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast);
}

.cg-tab:not(:last-child) {
  border-right: 1px solid var(--border);
}

.cg-tab.active {
  background: var(--primary);
  color: var(--text-inverse);
}

/* Unit selector / 单位选择 */
.cg-unit-tabs {
  display: flex;
  gap: 0;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.cg-unit-tab {
  flex: 1;
  padding: 8px 12px;
  border: none;
  background: var(--bg-surface);
  color: var(--text-secondary);
  font-size: 0.8125rem;
  font-weight: 500;
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast);
  text-align: center;
}

.cg-unit-tab:not(:last-child) {
  border-right: 1px solid var(--border);
}

.cg-unit-tab.active {
  background: var(--primary);
  color: var(--text-inverse);
}

.cg-unit-hint {
  font-weight: 400;
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-left: 6px;
}

/* Textarea / 文本输入 */
.cg-textarea {
  width: 100%;
  box-sizing: border-box;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: 0.8125rem;
  line-height: 1.6;
  resize: vertical;
  transition: border-color var(--transition-fast);
}

.cg-textarea:focus {
  outline: none;
  border-color: var(--border-focus);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}

.cg-section--grow {
  flex: 1;
}

.cg-section--grow .cg-textarea {
  min-height: 200px;
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
  grid-template-columns: minmax(0, 320px) minmax(0, 1fr);
  gap: 20px;
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
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.cg-section-title {
  font-size: 0.875rem;
  font-weight: 600;
  margin: 0;
  color: var(--text-primary);
}

.cg-params-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
}

.cg-param {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.cg-param label {
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--text-secondary);
}

.cg-param .cg-input {
  width: 100%;
  box-sizing: border-box;
}

.cg-param input[type="number"] {
  -moz-appearance: textfield;
}

.cg-param input[type="number"]::-webkit-inner-spin-button,
.cg-param input[type="number"]::-webkit-outer-spin-button {
  opacity: 0.3;
  height: 24px;
}

.cg-input, .cg-select {
  padding: 6px 8px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: 0.8125rem;
  transition: border-color var(--transition-fast);
}

.cg-input:focus, .cg-select:focus {
  outline: none;
  border-color: var(--border-focus);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}

.cg-select[size] {
  padding: 4px;
  font-size: 0.8125rem;
}

.cg-select[size] option {
  padding: 3px 6px;
}

.cg-hint {
  font-size: 0.75rem;
  color: var(--text-muted);
  margin: 0;
  line-height: 1.4;
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
  min-width: 52px;
  text-align: right;
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

.cg-file-btn:disabled { opacity: 0.5; cursor: not-allowed; }

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

.cg-clear-btn:hover { color: var(--error); }

/* Chart section (CIF mode) / 图表区 */
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

.cg-scale-btn:not(:last-child) { border-right: 1px solid var(--border); }
.cg-scale-btn.active { background: var(--primary); color: var(--text-inverse); }

.cg-action { display: flex; }

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

.cg-run-btn:not(:disabled):hover { opacity: 0.9; }

.cg-error {
  padding: 14px 18px;
  border-radius: var(--radius-md);
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: var(--error);
  font-size: 0.875rem;
}

.cg-error p { margin: 0; }

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

.cg-info-value { color: var(--text-primary); }

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
  max-height: 480px;
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

.cg-table tbody tr:hover { background: var(--bg-surface-alt); }

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

.cg-empty p { margin: 0; }

.cg-combobox {
  position: relative;
}

.cg-combobox .cg-input {
  width: 100%;
  box-sizing: border-box;
}

.cg-combobox-list {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  z-index: 100;
  max-height: 220px;
  overflow-y: auto;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  box-shadow: var(--shadow-md);
  margin-top: 2px;
}

.cg-combobox-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  cursor: pointer;
  font-size: 0.8125rem;
  color: var(--text-primary);
  transition: background var(--transition-fast);
}

.cg-combobox-item:hover,
.cg-combobox-item--active {
  background: var(--primary-bg);
}

.cg-combobox-item--selected {
  font-weight: 600;
  background: rgba(59, 130, 246, 0.08);
}

.cg-sg-num {
  font-family: var(--font-mono);
  color: var(--text-primary);
  font-weight: 600;
  min-width: 44px;
  flex-shrink: 0;
}

.cg-sg-symbol {
  flex: 1;
  color: var(--text-primary);
  font-weight: 500;
  white-space: nowrap;
}

.cg-combobox-hint {
  padding: 8px 10px;
  font-size: 0.75rem;
  color: var(--text-muted);
  text-align: center;
}

@media (max-width: 960px) {
  .cg-layout { grid-template-columns: 1fr; }
}
</style>
