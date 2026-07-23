<template>
  <section class="poni-importer-page">
    <!-- Header / 页头 -->
    <header class="pi-header">
      <h1>{{ t('poniImporter.title') }}</h1>
      <p class="pi-subtitle">{{ t('poniImporter.subtitle') }}</p>
    </header>

    <div class="pi-layout">
      <!-- ===== SIDEBAR: create form / 侧边栏：创建表单 ===== -->
      <aside class="pi-sidebar">
        <!-- ── 导入参考图像（自动探测器匹配） / Import reference image ── -->
        <div class="pi-card">
          <h3 class="pi-card-title">{{ t('poniImporter.importImageTitle') }}</h3>
          <p class="pi-card-hint">{{ t('poniImporter.importImageSubtitle') }}</p>

          <button
            type="button"
            class="pi-btn pi-btn-primary"
            :disabled="imageLoading"
            @click="handleChooseImage"
          >
            {{ imageLoading ? t('poniImporter.importImageLoading') : t('poniImporter.importImageBtn') }}
          </button>

          <p v-if="currentImageName" class="pi-file-info">
            <span class="pi-file-info-label">{{ t('poniImporter.importImageFileLabel') }}:</span>
            <code class="pi-file-info-value">{{ currentImageName }}</code>
          </p>
          <p v-else class="pi-field-hint">{{ t('poniImporter.importImageNoImage') }}</p>

          <!-- H5 dataset / channel selector / H5 数据集与通道选择 -->
          <H5Selector
            v-if="h5Datasets.length > 0"
            v-model="h5Selection"
            :datasets="h5Datasets"
            @change="onH5SelectionChange"
          />
        </div>

        <!-- ── 核心参数（始终展开）/ Core parameters ── -->
        <div class="pi-card">
          <h3 class="pi-card-title">{{ t('poniImporter.sectionsCore') }}</h3>

          <div class="pi-field">
            <label class="pi-label">{{ t('poniImporter.detectorDistance') }} (mm)</label>
            <input v-model.number="createForm.distance" type="number" class="pi-input" step="1" min="0.1" />
          </div>

          <!-- Beam center X with unit toggle + origin hint / 光斑中心 X（单位切换 + 起始点提示） -->
          <div class="pi-field">
            <div class="pi-label-row">
              <label class="pi-label">
                {{ t('poniImporter.beamCenterX') }}
                <span
                  class="pi-info-tip"
                  :title="t('poniImporter.beamCenterOriginHint')"
                  @click="showOriginHint = !showOriginHint"
                >ⓘ</span>
              </label>
              <div class="pi-unit-toggle">
                <button
                  type="button"
                  :class="['pi-unit-btn', { 'pi-unit-btn--active': beamCenterUnit === 'px' }]"
                  @click="onBeamCenterUnitToggle('px')"
                >px</button>
                <button
                  type="button"
                  :class="['pi-unit-btn', { 'pi-unit-btn--active': beamCenterUnit === 'um' }]"
                  @click="onBeamCenterUnitToggle('um')"
                >µm</button>
                <button
                  type="button"
                  :class="['pi-unit-btn', { 'pi-unit-btn--active': beamCenterUnit === 'm' }]"
                  @click="onBeamCenterUnitToggle('m')"
                >m</button>
              </div>
            </div>
            <input v-model.number="createForm.beamCenterX" type="number" class="pi-input" step="any" min="0" />
          </div>

          <div class="pi-field">
            <div class="pi-label-row">
              <label class="pi-label">{{ t('poniImporter.beamCenterY') }}</label>
            </div>
            <input v-model.number="createForm.beamCenterY" type="number" class="pi-input" step="any" min="0" />
          </div>

          <!-- Origin hint (collapsible) / 起始点说明（可展开） -->
          <p v-if="showOriginHint" class="pi-origin-hint">
            {{ t('poniImporter.beamCenterOriginHint') }}
            <a
              class="pi-origin-link"
              href="https://www.silx.org/doc/pyFAI/latest/geometry.html"
              target="_blank"
              rel="noopener noreferrer"
            >{{ t('poniImporter.beamCenterOriginLearnMore') }}</a>
          </p>
        </div>

        <!-- ── 展开区：波长与能量 / Expanded: Wavelength & Energy ── -->
        <div class="pi-card">
          <h3 class="pi-card-title">{{ t('poniImporter.sectionsWavelengthUnits') }}</h3>
          <p class="pi-field-hint">{{ t('poniImporter.wavelengthHint') }}</p>

          <div class="pi-field">
            <label class="pi-label">{{ t('poniImporter.wavelength') }} (Å)</label>
            <input
              :value="createForm.wavelength"
              @input="onWavelengthInput(($event.target as HTMLInputElement).value)"
              type="number"
              class="pi-input"
              step="any"
              min="0"
            />
          </div>

          <div class="pi-field">
            <label class="pi-label">{{ t('poniImporter.energy') }} (keV)</label>
            <input
              :value="createForm.energy"
              @input="onEnergyInput(($event.target as HTMLInputElement).value)"
              type="number"
              class="pi-input"
              step="any"
              min="0"
            />
          </div>

          <div class="pi-field">
            <div class="pi-label-row">
              <span class="pi-label">{{ t('poniImporter.pixelSize') }}</span>
              <div class="pi-unit-toggle">
                <button
                  type="button"
                  :class="['pi-unit-btn', { 'pi-unit-btn--active': pixelSizeUnit === 'um' }]"
                  @click="onPixelSizeUnitToggle('um')"
                >µm</button>
                <button
                  type="button"
                  :class="['pi-unit-btn', { 'pi-unit-btn--active': pixelSizeUnit === 'mm' }]"
                  @click="onPixelSizeUnitToggle('mm')"
                >mm</button>
              </div>
            </div>
            <input v-model.number="createForm.pixel_size" type="number" class="pi-input" :step="pixelSizeUnit === 'um' ? 1 : 0.001" :min="pixelSizeUnit === 'um' ? 1 : 0.001" />
          </div>

          <!-- Pixel origin orientation / 像素原点方向 -->
          <div class="pi-field">
            <label class="pi-label">{{ t('poniImporter.pixelOrigin') }}</label>
            <select v-model.number="createForm.orientation" class="pi-select">
              <option :value="3">{{ t('poniImporter.pixelOriginTopLeft') }}</option>
              <option :value="1">{{ t('poniImporter.pixelOriginBottomRight') }}</option>
              <option :value="2">{{ t('poniImporter.pixelOriginTopRight') }}</option>
              <option :value="4">{{ t('poniImporter.pixelOriginBottomLeft') }}</option>
            </select>
            <p class="pi-field-hint">{{ t('poniImporter.pixelOriginHint') }}</p>
          </div>
        </div>

        <!-- ── 折叠区：高级参数（旋转 + 探测器）/ Collapsible: Advanced ── -->
        <div class="pi-collapsible">
          <div class="pi-section-toggle" @click="advancedExpanded = !advancedExpanded">
            <span class="pi-toggle-icon">{{ advancedExpanded ? '▾' : '▸' }}</span>
            <span>{{ t('poniImporter.sectionsAdvanced') }}</span>
          </div>
          <div v-show="advancedExpanded" class="pi-collapsible-body">
            <p v-if="autoMatchedFromImage" class="pi-auto-hint">{{ t('poniImporter.autoMatchManualHint') }}</p>

            <!-- Rotation parameters (degrees) / 旋转参数（度） -->
            <div class="pi-field">
              <label class="pi-label">{{ t('poniImporter.rot1') }} (°)</label>
              <input v-model.number="createForm.rot1" type="number" class="pi-input" step="any" />
            </div>
            <div class="pi-field">
              <label class="pi-label">{{ t('poniImporter.rot2') }} (°)</label>
              <input v-model.number="createForm.rot2" type="number" class="pi-input" step="any" />
            </div>
            <div class="pi-field">
              <label class="pi-label">{{ t('poniImporter.rot3') }} (°)</label>
              <input v-model.number="createForm.rot3" type="number" class="pi-input" step="any" />
            </div>

            <!-- Detector preset / 探测器预设 -->
            <div class="pi-field">
              <label class="pi-label">{{ t('poniImporter.detectorPreset') }}</label>
              <select v-model="selectedPreset" class="pi-select">
                <option value="Custom">{{ t('poniImporter.detectorCustom') }}</option>
                <option v-for="p in detectorPresets" :key="p.name" :value="p.name">{{ p.name }}</option>
              </select>
              <p class="pi-field-hint">{{ isCustomDetector ? t('poniImporter.detectorCustomHint') : t('poniImporter.detectorPresetHint') }}</p>
            </div>

            <!-- Preset mode: resolved pyFAI name (read-only) / 预设模式 -->
            <div v-if="!isCustomDetector" class="pi-field">
              <label class="pi-label">{{ t('poniImporter.detectorName') }}</label>
              <input :value="createForm.detector_name" type="text" class="pi-input" readonly />
            </div>

            <!-- Custom mode: friendly label + array shape / 自定义模式 -->
            <template v-else>
              <div class="pi-field">
                <label class="pi-label">{{ t('poniImporter.detectorCustomLabel') }}</label>
                <input
                  v-model="createForm.detector_label"
                  type="text"
                  class="pi-input"
                  :placeholder="t('poniImporter.detectorCustomPlaceholder')"
                />
              </div>
              <div class="pi-field">
                <label class="pi-label">{{ t('poniImporter.detectorShape') }}</label>
                <div class="pi-shape-row">
                  <input v-model.number="createForm.shape_rows" type="number" class="pi-input" min="1" step="1" placeholder="rows" />
                  <span class="pi-shape-x">×</span>
                  <input v-model.number="createForm.shape_cols" type="number" class="pi-input" min="1" step="1" placeholder="cols" />
                </div>
                <p class="pi-field-hint">{{ t('poniImporter.detectorShapeHint') }}</p>
              </div>
            </template>
          </div>
        </div>
      </aside>

      <!-- ===== MAIN AREA / 主区域 ===== -->
      <main class="pi-main">
        <!-- ── 图像预览（光斑中心）+ 对比度 / Image preview (beam center) + contrast ── -->
        <div class="pi-card">
          <div class="pi-preview-header">
            <h3 class="pi-card-title">{{ t('poniImporter.previewTitle') }}</h3>
            <div class="pi-preview-legend">
              <span class="pi-legend-item"><span class="pi-legend-dot pi-legend-dot--yellow"></span>{{ t('poniImporter.previewBeamCenterLabel') }}</span>
              <span class="pi-legend-item"><span class="pi-legend-corner"></span>{{ t('poniImporter.previewOriginLabel') }}</span>
            </div>
          </div>

          <div v-if="imageLoading" class="pi-preview-loading">{{ t('poniImporter.importImageLoading') }}</div>
          <div v-else-if="previewB64" class="pi-preview-area">
            <div class="pi-preview-image">
              <ImagePreview
                :image-b64="previewB64"
                :overlays="previewOverlays"
                :show-colorbar="true"
                :colorbar-gradient="colorbarGradient"
                :colorbar-min-label="colorbarMinLabel"
                :colorbar-max-label="colorbarMaxLabel"
                :data-width="previewImageSize?.origWidth"
                :data-height="previewImageSize?.origHeight"
                :placeholder="t('poniImporter.importImageNoImage')"
              />
            </div>
          </div>
          <div v-else class="pi-preview-empty">{{ t('poniImporter.importImageNoImage') }}</div>

          <!-- Display settings (colormap / log / contrast) / 显示设置 -->
          <div v-if="previewB64" class="pi-contrast-section">
            <h4 class="pi-contrast-title">{{ t('poniImporter.contrastTitle') }}</h4>
            <div class="pi-contrast-row">
              <div class="pi-field pi-field--inline">
                <label class="pi-label">{{ t('poniImporter.contrastColormap') }}</label>
                <select v-model="colormap" class="pi-select">
                  <option v-for="cm in colormapOptions" :key="cm" :value="cm">{{ cm }}</option>
                </select>
              </div>
              <label class="pi-toggle-label">
                <input v-model="useLog" type="checkbox" />
                <span>{{ t('poniImporter.contrastLogScale') }}</span>
              </label>
            </div>
            <div class="pi-contrast-row">
              <span class="pi-label">{{ t('poniImporter.contrastMode') }}</span>
              <label class="pi-radio-label">
                <input v-model="climMode" type="radio" value="auto" />
                <span>{{ t('poniImporter.contrastAuto') }}</span>
              </label>
              <label class="pi-radio-label">
                <input v-model="climMode" type="radio" value="manual" />
                <span>{{ t('poniImporter.contrastManual') }}</span>
              </label>
            </div>
            <div v-if="climMode === 'manual'" class="pi-contrast-sliders">
              <div class="pi-clim-field">
                <label class="pi-label-sm">{{ t('poniImporter.contrastMin') }}</label>
                <input
                  type="range"
                  class="pi-slider"
                  :min="climSliderMin"
                  :max="climSliderMax"
                  :step="climStep"
                  :value="climMin"
                  @input="updateClimMin(Number(($event.target as HTMLInputElement).value))"
                />
                <input
                  :value="climMin"
                  type="number"
                  class="pi-input pi-input--sm"
                  step="any"
                  @input="updateClimMin(Number(($event.target as HTMLInputElement).value))"
                />
              </div>
              <div class="pi-clim-field">
                <label class="pi-label-sm">{{ t('poniImporter.contrastMax') }}</label>
                <input
                  type="range"
                  class="pi-slider"
                  :min="climSliderMin"
                  :max="climSliderMax"
                  :step="climStep"
                  :value="climMax"
                  @input="updateClimMax(Number(($event.target as HTMLInputElement).value))"
                />
                <input
                  :value="climMax"
                  type="number"
                  class="pi-input pi-input--sm"
                  step="any"
                  @input="updateClimMax(Number(($event.target as HTMLInputElement).value))"
                />
              </div>
            </div>
          </div>

          <!-- Preview stats (shape / beam center) / 预览统计 -->
          <div v-if="previewB64 && (previewShape || resolvedBeamCenterDisplay)" class="pi-preview-stats">
            <span v-if="previewShape" class="pi-stat">
              <span class="pi-stat-label">{{ t('poniImporter.previewStatsShape') }}:</span>
              <code class="pi-stat-value">{{ previewShape[0] }} × {{ previewShape[1] }}</code>
            </span>
            <span v-if="resolvedBeamCenterDisplay" class="pi-stat">
              <span class="pi-stat-label">{{ t('poniImporter.previewStatsBeamCenter') }}:</span>
              <code class="pi-stat-value">{{ resolvedBeamCenterDisplay }}</code>
            </span>
          </div>
        </div>

        <!-- ── PONI 实时预览 + 导出 / PONI preview + export ── -->
        <div class="pi-card">
          <h3 class="pi-card-title">{{ t('poniImporter.createSuccessTitle') }}</h3>

          <div v-if="!poniData" class="pi-empty-hint">
            <p>请填写必要参数</p>
          </div>

          <template v-if="poniData">
            <div class="pi-section">
              <h4 class="pi-section-title">{{ t('poniSections.geometry') }}</h4>
              <div class="pi-param-grid">
                <div class="pi-param-item">
                  <span class="pi-param-label">{{ t('poniParams.detectorDistance') }}:</span>
                  <span class="pi-param-value">{{ formatValue(poniData.distance, 'mm') }}</span>
                </div>
                <div class="pi-param-item">
                  <span class="pi-param-label">{{ t('poniParams.wavelength') }}:</span>
                  <span class="pi-param-value">{{ formatValue(poniData.wavelength, 'Å') }}</span>
                </div>
                <div class="pi-param-item">
                  <span class="pi-param-label">{{ t('poniParams.pixelSize') }}:</span>
                  <span class="pi-param-value">{{ formatValue(poniData.pixel_size, 'µm') }}</span>
                </div>
                <div class="pi-param-item">
                  <span class="pi-param-label">{{ t('poniParams.detectorName') }}:</span>
                  <span class="pi-param-value">{{ detectorDisplay }}</span>
                </div>
                <div class="pi-param-item">
                  <span class="pi-param-label">{{ t('poniParams.beamCenterX') }}:</span>
                  <span class="pi-param-value">{{ formatBeamCenter(poniData.poni2) }}</span>
                </div>
                <div class="pi-param-item">
                  <span class="pi-param-label">{{ t('poniParams.beamCenterY') }}:</span>
                  <span class="pi-param-value">{{ formatBeamCenter(poniData.poni1) }}</span>
                </div>
              </div>
            </div>

            <div class="pi-section">
              <h4 class="pi-section-title">{{ t('poniSections.rotation') }}</h4>
              <div class="pi-param-grid">
                <div class="pi-param-item">
                  <span class="pi-param-label">{{ t('poniParams.rotation1') }}:</span>
                  <span class="pi-param-value">{{ formatValue(poniData.rot1, 'deg') }}</span>
                </div>
                <div class="pi-param-item">
                  <span class="pi-param-label">{{ t('poniParams.rotation2') }}:</span>
                  <span class="pi-param-value">{{ formatValue(poniData.rot2, 'deg') }}</span>
                </div>
                <div class="pi-param-item">
                  <span class="pi-param-label">{{ t('poniParams.rotation3') }}:</span>
                  <span class="pi-param-value">{{ formatValue(poniData.rot3, 'deg') }}</span>
                </div>
              </div>
            </div>

            <div class="pi-section">
              <h4 class="pi-section-title">{{ t('poniSections.rawJson') }}</h4>
              <pre class="pi-json">{{ JSON.stringify(poniData, null, 2) }}</pre>
            </div>
          </template>

          <!-- Export section / 导出 -->
          <div class="pi-section">
            <h3 class="pi-card-title">{{ t('poniImporter.exportOptions') }}</h3>
            <div class="pi-field">
              <label class="pi-label">{{ t('poniImporter.exportFormat') }}</label>
              <select v-model="exportFormat" class="pi-select">
                <option value="poni">PONI (.poni)</option>
                <option value="json">JSON</option>
              </select>
            </div>
            <button type="button" class="pi-btn pi-btn-primary" :disabled="!poniData" @click="doExport">
              {{ t('poniImporter.exportBtn') }}
            </button>
          </div>
        </div>
      </main>
    </div>
  </section>
</template>

<script setup lang="ts">
/**
 * PoniImporterView.vue — PONI文件转化页面 (v0.2.3)
 * PONI file conversion page: import a reference image to auto-match the detector,
 * preview the beam center on the image with adjustable contrast, then export.
 */
import { ref, reactive, computed, watch, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useToast } from '@/lib/toast'
import { useTransport } from '@/lib/transport'
import { COLORMAP_PRESETS, resolveColorbarGradient } from '@/lib/chart-utils'
import ImagePreview from '@/components/charts/ImagePreview.vue'
import type { Overlay } from '@/components/charts/ImagePreview.vue'
import H5Selector from '@/components/business/H5Selector.vue'
import type { H5DatasetInfo, H5Selection } from '@/components/business/H5Selector.vue'

// === Type definitions / 类型定义 ===

interface PoniData {
  distance: number      // Detector distance in meters
  wavelength: number    // Wavelength in meters
  pixel_size: number    // Pixel size in meters
  poni1: number         // Beam center Y direction (meters, = center_y_px * pixel_size)
  poni2: number         // Beam center X direction (meters, = center_x_px * pixel_size)
  rot1?: number         // Rotation 1 (radians)
  rot2?: number         // Rotation 2 (radians)
  rot3?: number         // Rotation 3 (radians)
  detector_name?: string // Detector name (pyFAI-registered name preferred)
  detector_config?: string // Detector config (JSON, no surrounding quotes)
  detector_label?: string // Custom detector friendly name (comment only)
  detector_shape?: [number, number] // Custom detector max_shape
  orientation?: number // pyFAI detector orientation (0-4)
  [key: string]: any
}

type PageState = 'idle' | 'loading' | 'error' | 'success'
type ExportFormat = 'json' | 'poni'
type PixelSizeUnit = 'um' | 'mm'
type BeamCenterUnit = 'px' | 'um' | 'm'

interface ProbeImageResult {
  status: string
  isH5: boolean
  shape?: [number, number]
  height?: number
  width?: number
  n_frames?: number
  datasets?: Array<{ path: string; ndim: number; shape: number[]; height?: number; width?: number; nFrames?: number; nChannels?: number }>
  default_path?: string
  message?: string
}

interface MatchDetectorResult {
  status: string
  matched: {
    name: string
    label: string
    pixel1_m: number
    pixel2_m: number
    max_shape: [number, number]
  } | null
  message?: string
}

interface PreviewMetadata {
  stats?: { min: number; max: number; adjustedMax: number; std: number }
  contrast?: { autoMin: number; autoMax: number; logMin: number; logMax: number }
  metadata?: {
    width?: number
    height?: number
    h5Datasets?: H5DatasetInfo[]
    selectedDataset?: string
    selectedChannel?: number
    nChannels?: number
  }
}

// === Composables / 组合函数 ===

const { t } = useI18n()
const toast = useToast()
const transport = useTransport()

// === State / 状态 ===

const state = ref<PageState>('idle')
const errorMessage = ref('')
const exportFormat = ref<ExportFormat>('poni')

const createForm = reactive({
  distance: 100,        // mm
  wavelength: 1.5418,   // Å
  energy: 8.048,        // keV (Cu Kα, auto-synced with wavelength)
  pixel_size: 172,      // µm (or mm depending on pixelSizeUnit)
  beamCenterX: 512,     // px, µm, or m depending on beamCenterUnit
  beamCenterY: 512,
  rot1: 0,              // degrees
  rot2: 0,
  rot3: 0,
  orientation: 3,       // pyFAI detector orientation: 3=top-left (default), 1=bottom-right, 2=top-right, 4=bottom-left
  detector_name: '',     // pyFAI name (preset mode, auto-filled)
  detector_label: '',    // friendly name (custom mode only)
  shape_rows: null as number | null,  // custom detector rows  → max_shape[0]
  shape_cols: null as number | null,  // custom detector cols  → max_shape[1]
})

// Unit toggles / 单位切换
const pixelSizeUnit = ref<PixelSizeUnit>('um')
const beamCenterUnit = ref<BeamCenterUnit>('px')

const HC_KEV_A = 12.39842 // h*c in keV·Å

/** When the user edits the wavelength (Å), auto-calculate energy (keV). */
function onWavelengthInput(raw: string): void {
  const num = parseFloat(raw)
  if (isNaN(num) || num <= 0) return
  createForm.wavelength = num
  createForm.energy = parseFloat((HC_KEV_A / num).toFixed(6))
}

/** When the user edits the energy (keV), auto-calculate wavelength (Å). */
function onEnergyInput(raw: string): void {
  const num = parseFloat(raw)
  if (isNaN(num) || num <= 0) return
  createForm.energy = num
  createForm.wavelength = parseFloat((HC_KEV_A / num).toFixed(6))
}

function onPixelSizeUnitToggle(newUnit: PixelSizeUnit): void {
  const oldUnit = pixelSizeUnit.value
  if (oldUnit === newUnit) return
  if (oldUnit === 'um' && newUnit === 'mm') {
    createForm.pixel_size = createForm.pixel_size / 1000
  } else if (oldUnit === 'mm' && newUnit === 'um') {
    createForm.pixel_size = createForm.pixel_size * 1000
  }
  pixelSizeUnit.value = newUnit
}

function getPixelSizeMeters(): number {
  return pixelSizeUnit.value === 'um' ? createForm.pixel_size * 1e-6 : createForm.pixel_size * 1e-3
}

function beamCenterToMeters(value: number, unit: BeamCenterUnit, pixelSizeM: number): number {
  if (unit === 'px') return value * pixelSizeM
  if (unit === 'um') return value * 1e-6
  return value  // already meters
}

function metersToBeamCenter(valueM: number, unit: BeamCenterUnit, pixelSizeM: number): number {
  if (unit === 'px') return pixelSizeM > 0 ? valueM / pixelSizeM : 0
  if (unit === 'um') return valueM * 1e6
  return valueM  // meters
}

function onBeamCenterUnitToggle(newUnit: BeamCenterUnit): void {
  const oldUnit = beamCenterUnit.value
  if (oldUnit === newUnit) return
  const pixelSizeM = getPixelSizeMeters()
  const beamXM = beamCenterToMeters(createForm.beamCenterX, oldUnit, pixelSizeM)
  const beamYM = beamCenterToMeters(createForm.beamCenterY, oldUnit, pixelSizeM)
  createForm.beamCenterX = metersToBeamCenter(beamXM, newUnit, pixelSizeM)
  createForm.beamCenterY = metersToBeamCenter(beamYM, newUnit, pixelSizeM)
  beamCenterUnit.value = newUnit
}

// === Real-time computed PONI data / 实时计算 PONI 数据 ===

const poniData = computed<PoniData | null>(() => {
  if (!Number.isFinite(createForm.distance) || createForm.distance <= 0) return null
  if (!Number.isFinite(createForm.wavelength) || createForm.wavelength <= 0) return null
  if (!Number.isFinite(createForm.pixel_size) || createForm.pixel_size <= 0) return null
  if (!Number.isFinite(createForm.beamCenterX)) return null
  if (!Number.isFinite(createForm.beamCenterY)) return null

  const pixelSizeM = getPixelSizeMeters()
  const distanceM = createForm.distance * 1e-3  // mm → m
  const wavelengthM = createForm.wavelength * 1e-10  // Å → m (always in Å now)

  const beamXM = beamCenterToMeters(createForm.beamCenterX, beamCenterUnit.value, pixelSizeM)
  const beamYM = beamCenterToMeters(createForm.beamCenterY, beamCenterUnit.value, pixelSizeM)

  const DEG2RAD = Math.PI / 180
  const data: PoniData = {
    distance: distanceM,
    wavelength: wavelengthM,
    pixel_size: pixelSizeM,
    poni1: beamYM,
    poni2: beamXM,
    rot1: createForm.rot1 * DEG2RAD,
    rot2: createForm.rot2 * DEG2RAD,
    rot3: createForm.rot3 * DEG2RAD,
    orientation: createForm.orientation,
  }
  if (isCustomDetector.value) {
    const label = (createForm.detector_label || '').trim()
    if (label) data.detector_label = label
    const r = createForm.shape_rows
    const c = createForm.shape_cols
    if (r != null && c != null && r > 0 && c > 0) {
      data.detector_shape = [Math.trunc(r), Math.trunc(c)]
    }
  } else {
    data.detector_name = createForm.detector_name || undefined
  }
  return data
})

// === Detector presets (pyFAI compatible) / 探测器预设 ===

interface DetectorPreset {
  name: string
  detector_name: string
  pixel_size: number  // in mm
}

const detectorPresets = ref<DetectorPreset[]>([
  // Dectris Pilatus series (172 µm = 0.172 mm)
  { name: 'Pilatus 100K', detector_name: 'Pilatus100k', pixel_size: 0.172 },
  { name: 'Pilatus 200K', detector_name: 'Pilatus200k', pixel_size: 0.172 },
  { name: 'Pilatus 300K', detector_name: 'Pilatus300k', pixel_size: 0.172 },
  { name: 'Pilatus 1M', detector_name: 'Pilatus1M', pixel_size: 0.172 },
  { name: 'Pilatus 2M', detector_name: 'Pilatus2M', pixel_size: 0.172 },
  { name: 'Pilatus 6M', detector_name: 'Pilatus6M', pixel_size: 0.172 },
  // Dectris Pilatus3 series
  { name: 'Pilatus3 100K', detector_name: 'Pilatus3_100k', pixel_size: 0.172 },
  { name: 'Pilatus3 200K', detector_name: 'Pilatus3_200k', pixel_size: 0.172 },
  { name: 'Pilatus3 300K', detector_name: 'Pilatus3_300k', pixel_size: 0.172 },
  { name: 'Pilatus3 1M', detector_name: 'Pilatus3_1M', pixel_size: 0.172 },
  { name: 'Pilatus3 2M', detector_name: 'Pilatus3_2M', pixel_size: 0.172 },
  { name: 'Pilatus3 6M', detector_name: 'Pilatus3_6M', pixel_size: 0.172 },
  // Dectris Eiger series (75 µm = 0.075 mm)
  { name: 'Eiger 1M', detector_name: 'Eiger1M', pixel_size: 0.075 },
  { name: 'Eiger 4M', detector_name: 'Eiger4M', pixel_size: 0.075 },
  { name: 'Eiger 9M', detector_name: 'Eiger9M', pixel_size: 0.075 },
  { name: 'Eiger 16M', detector_name: 'Eiger16M', pixel_size: 0.075 },
  // Dectris Eiger2 series
  { name: 'Eiger2 1M', detector_name: 'Eiger2_1M', pixel_size: 0.075 },
  { name: 'Eiger2 4M', detector_name: 'Eiger2_4M', pixel_size: 0.075 },
  { name: 'Eiger2 9M', detector_name: 'Eiger2_9M', pixel_size: 0.075 },
  { name: 'Eiger2 16M', detector_name: 'Eiger2_16M', pixel_size: 0.075 },
  // Other detectors
  { name: 'Perkin Elmer', detector_name: 'Perkin', pixel_size: 0.200 },
  { name: 'Mar345', detector_name: 'Mar345', pixel_size: 0.150 },
  { name: 'Rayonix MX225', detector_name: 'RayonixMX225', pixel_size: 0.0737 },
  { name: 'Rayonix MX300', detector_name: 'RayonixMX300', pixel_size: 0.148 },
])

const selectedPreset = ref<string>('Pilatus 1M')

const isCustomDetector = computed(() => selectedPreset.value === 'Custom')

const detectorDisplay = computed(() => {
  if (isCustomDetector.value) {
    const label = (createForm.detector_label || '').trim() || t('poniImporter.detectorCustom')
    const r = createForm.shape_rows
    const c = createForm.shape_cols
    const hasShape = r != null && c != null && r > 0 && c > 0
    return hasShape ? `${label} (${Math.trunc(r)}×${Math.trunc(c)})` : label
  }
  return createForm.detector_name || '—'
})

// Watch preset selection and auto-fill form / 监听预设选择并自动填充表单
watch(selectedPreset, (presetName) => {
  if (!presetName) return
  const preset = detectorPresets.value.find(p => p.name === presetName)
  if (preset) {
    createForm.detector_name = preset.detector_name
    createForm.pixel_size = pixelSizeUnit.value === 'um' ? preset.pixel_size * 1000 : preset.pixel_size
  }
})

// Initialize form fields from the default preset on mount.
{
  const initial = detectorPresets.value.find(p => p.name === selectedPreset.value)
  if (initial) {
    createForm.detector_name = initial.detector_name
    createForm.pixel_size = pixelSizeUnit.value === 'um' ? initial.pixel_size * 1000 : initial.pixel_size
  }
}

// === Image import + auto detector match / 图像导入 + 自动探测器匹配 ===

const currentImagePath = ref<string | null>(null)
const currentImageName = ref<string>('')
const imageLoading = ref(false)
const autoMatchedFromImage = ref(false)
const showOriginHint = ref(false)

const imageFilters = [
  { name: 'Detector Images', extensions: ['edf', 'tif', 'tiff', 'h5', 'hdf5'] },
]

// H5 dataset state (4D support) / H5 数据集状态（支持 4D）
const h5Datasets = ref<H5DatasetInfo[]>([])
const h5Selection = ref<H5Selection>({ dataset: '', channel: 0, frame: 0 })

// Collapsible section state (advanced only collapsed by default).
// 折叠区状态（仅高级参数默认收起）。
const advancedExpanded = ref(false)

async function handleChooseImage(): Promise<void> {
  const result = await transport.selectFiles({ filters: imageFilters, multiSelections: false })
  if (!result) return
  const path = Array.isArray(result) ? result[0] : result
  if (!path) return
  currentImagePath.value = path
  currentImageName.value = path.split(/[/\\]/).pop() ?? path
  h5Datasets.value = []
  h5Selection.value = { dataset: '', channel: 0, frame: 0 }
  autoMatchedFromImage.value = false
  await probeAndMatch(path)
}

/** Probe image shape → call match_detector → apply result to the form. */
async function probeAndMatch(path: string): Promise<void> {
  imageLoading.value = true
  try {
    // 1. Probe the image (H5 returns multiple datasets).
    const probeRaw = await submitAndWait('poni_importer', { action: 'probe_image', filePath: path })
    const probe = probeRaw as ProbeImageResult
    if (probe.status !== 'ok') {
      toast.push({ title: t('poniImporter.errorTitle'), message: probe.message ?? 'probe failed', tone: 'error' })
      return
    }

    // Populate H5 selector datasets if applicable.
    if (probe.isH5 && Array.isArray(probe.datasets)) {
      h5Datasets.value = probe.datasets.map(d => ({
        path: d.path,
        ndim: d.ndim,
        shape: d.shape,
        nFrames: d.nFrames,
        nChannels: d.nChannels,
      }))
      if (probe.default_path) {
        h5Selection.value = { dataset: probe.default_path, channel: 0, frame: 0 }
      }
    }

    // 2. Pick the shape to match against. For H5, use the default dataset's
    //    last-two axes; for EDF/TIFF, use the returned shape directly.
    let shapeToMatch: [number, number] | null = null
    if (probe.isH5) {
      const ds = probe.datasets?.find(d => d.path === probe.default_path) ?? probe.datasets?.[0]
      if (ds?.height && ds?.width) shapeToMatch = [ds.height, ds.width]
    } else if (probe.shape) {
      shapeToMatch = [probe.shape[0], probe.shape[1]]
    }

    // 3. Load preview BEFORE matching so the user sees the image regardless.
    await loadPreview(path)

    if (!shapeToMatch) return

    // 4. Match detector by shape.
    const matchRaw = await submitAndWait('poni_importer', { action: 'match_detector', shape: shapeToMatch })
    const match = matchRaw as MatchDetectorResult
    if (match.status !== 'ok') {
      toast.push({ title: t('poniImporter.errorTitle'), message: match.message ?? 'match failed', tone: 'error' })
      return
    }
    applyDetectorMatch(match.matched, shapeToMatch)
  } catch (err) {
    toast.push({
      title: t('poniImporter.errorTitle'),
      message: err instanceof Error ? err.message : String(err),
      tone: 'error',
    })
  } finally {
    imageLoading.value = false
  }
}

/** Apply a detector match result to the form, or fall back to custom mode. */
function applyDetectorMatch(matched: MatchDetectorResult['matched'], shape: [number, number]): void {
  // Always populate the custom-detector shape from the image (useful in both branches).
  createForm.shape_rows = shape[0]
  createForm.shape_cols = shape[1]

  if (matched) {
    // Add the matched detector to the preset list (dedup by name) and select it.
    const friendlyName = matched.label || matched.name
    if (!detectorPresets.value.some(p => p.name === friendlyName)) {
      // pixel1_m == pixel2_m for these square-pixel detectors → use pixel1.
      const pixel_mm = (matched.pixel1_m ?? matched.pixel2_m ?? 0) * 1000
      detectorPresets.value = [
        { name: friendlyName, detector_name: matched.name, pixel_size: pixel_mm },
        ...detectorPresets.value,
      ]
    }
    selectedPreset.value = friendlyName
    // selectedPreset watcher fills detector_name + pixel_size automatically.
    autoMatchedFromImage.value = true
    toast.push({
      title: t('poniImporter.importImageTitle'),
      message: t('poniImporter.autoMatchedToast', {
        name: friendlyName,
        pixel: ((matched.pixel1_m ?? matched.pixel2_m ?? 0) * 1e6).toFixed(3),
      }),
      tone: 'success',
    })
  } else {
    // No match → switch to custom mode with the detected shape filled in.
    selectedPreset.value = 'Custom'
    if (!createForm.detector_label) createForm.detector_label = ''
    autoMatchedFromImage.value = true
    toast.push({
      title: t('poniImporter.importImageTitle'),
      message: t('poniImporter.autoUnmatchedToast'),
      tone: 'info',
    })
  }
}

function onH5SelectionChange(): void {
  // When the user picks a different dataset/channel, re-probe just the shape
  // for that dataset and re-match.
  if (!currentImagePath.value || h5Datasets.value.length === 0) return
  const ds = h5Datasets.value.find(d => d.path === h5Selection.value.dataset)
  if (!ds || ds.shape.length < 2) return
  const shape: [number, number] = [ds.shape[ds.shape.length - 2], ds.shape[ds.shape.length - 1]]
  void reloadPreviewAndMatch(currentImagePath.value, shape)
}

async function reloadPreviewAndMatch(path: string, shape: [number, number]): Promise<void> {
  imageLoading.value = true
  try {
    await loadPreview(path)
    const matchRaw = await submitAndWait('poni_importer', { action: 'match_detector', shape })
    const match = matchRaw as MatchDetectorResult
    if (match.status === 'ok') applyDetectorMatch(match.matched, shape)
  } finally {
    imageLoading.value = false
  }
}

// === Image preview (viewer_config open_file) / 图像预览 ===

const previewB64 = ref<string | null>(null)
const previewImageSize = ref<{ width: number; height: number; origWidth: number; origHeight: number } | null>(null)
const previewShape = ref<[number, number] | null>(null)
const autoContrast = ref<{ autoMin: number; autoMax: number; logMin: number; logMax: number } | null>(null)
const previewStats = ref<{ min: number; max: number; adjustedMax: number; std: number } | null>(null)

let cleanupPreviewBinary: (() => void) | null = null
let cleanupPreviewResult: (() => void) | null = null
let cleanupPreviewError: (() => void) | null = null

// Display settings / 显示设置
const colormapOptions = [
  'smooth_WAXS_foxtrot',
  'smooth_WAXS_fit2D',
  ...Object.keys(COLORMAP_PRESETS),
]
const colormap = ref('smooth_WAXS_foxtrot')
const useLog = ref(true)
const climMode = ref<'auto' | 'manual'>('auto')
const climMin = ref(0)
const climMax = ref(1)
const climInitialized = ref(false)

function buildRenderSettings(): Record<string, unknown> {
  const resolvedClim = climMode.value === 'manual'
    ? [climMin.value, climMax.value]
    : [
        useLog.value ? autoContrast.value?.logMin ?? 1e-6 : autoContrast.value?.autoMin ?? 0,
        useLog.value ? autoContrast.value?.logMax ?? 1 : autoContrast.value?.autoMax ?? 1,
      ]
  return {
    colormap: colormap.value,
    use_log: useLog.value,
    clim_mode: climMode.value,
    clim: resolvedClim,
    preview_scale: 1.0,
  }
}

async function loadPreview(filePath: string, isReload = false): Promise<void> {
  // When reloading (contrast/colormap change), keep the old image visible
  // until the new one arrives to prevent flicker. Only a brand-new file
  // load should clear the preview state upfront.
  // 重渲染（对比度/色图变化）时保留旧图直到新图到达，避免闪烁。
  // 仅加载全新文件时才清空预览状态。
  if (!isReload) {
    if (previewB64.value?.startsWith('blob:')) {
      URL.revokeObjectURL(previewB64.value)
    }
    previewB64.value = null
    previewImageSize.value = null
    previewStats.value = null
    autoContrast.value = null
  }
  cleanupPreviewListeners()

  const isH5 = h5Datasets.value.length > 0
  const response = await transport.submitTask('viewer_config', {
    action: 'open_file',
    filePath,
    frame: h5Selection.value.frame,
    ...(isH5 ? {
      dataset: h5Selection.value.dataset || undefined,
      channel: h5Selection.value.channel,
    } : {}),
    settings: buildRenderSettings(),
  })

  cleanupPreviewBinary = transport.onTaskBinaryData(response.taskId, (payload) => {
    if (payload.data) {
      const blob = new Blob([payload.data], { type: payload.mime || 'image/png' })
      const newUrl = URL.createObjectURL(blob)
      // Revoke the OLD url only after the new one is ready, so the <img>
      // never briefly loses its src mid-render.
      // 先创建新 URL 再撤销旧的，避免 <img> 在渲染中途短暂丢失 src。
      const oldUrl = previewB64.value
      previewB64.value = newUrl
      if (oldUrl?.startsWith('blob:')) URL.revokeObjectURL(oldUrl)
    }
  })

  cleanupPreviewResult = transport.onTaskResult(response.taskId, (payload) => {
    const data = payload.data as PreviewMetadata
    if (data.stats) previewStats.value = data.stats
    if (data.contrast) {
      autoContrast.value = data.contrast
      if (climMode.value === 'auto') {
        climMin.value = useLog.value ? data.contrast.logMin : data.contrast.autoMin
        climMax.value = useLog.value ? data.contrast.logMax : data.contrast.autoMax
      } else if (!climInitialized.value) {
        climMin.value = useLog.value ? data.contrast.logMin : data.contrast.autoMin
        climMax.value = useLog.value ? data.contrast.logMax : data.contrast.autoMax
        climInitialized.value = true
      }
    }
    const w = data.metadata?.width ?? 0
    const h = data.metadata?.height ?? 0
    if (w > 0 && h > 0) {
      previewImageSize.value = { width: 0, height: 0, origWidth: w, origHeight: h }
      previewShape.value = [h, w]
    }
  })

  cleanupPreviewError = transport.onTaskError(response.taskId, (payload) => {
    toast.push({ title: t('poniImporter.errorTitle'), message: payload.error, tone: 'error' })
  })
}

function cleanupPreviewListeners(): void {
  cleanupPreviewBinary?.()
  cleanupPreviewBinary = null
  cleanupPreviewResult?.()
  cleanupPreviewResult = null
  cleanupPreviewError?.()
  cleanupPreviewError = null
}

// Contrast slider bounds, mirroring ViewerView. / 对比度滑块范围，镜像 ViewerView。
const climSliderMin = computed(() => {
  const auto = (useLog.value ? autoContrast.value?.logMin : autoContrast.value?.autoMin) ?? 0
  return auto <= 0 ? auto * 2 : auto * 0.1
})
const climSliderMax = computed(() => {
  const auto = (useLog.value ? autoContrast.value?.logMax : autoContrast.value?.autoMax) ?? (previewStats.value?.adjustedMax ?? 1)
  return auto * 3
})
const climStep = computed(() => {
  const range = climSliderMax.value - climSliderMin.value
  return range === 0 ? 1 : range / 1000
})

function updateClimMin(value: number): void {
  if (!Number.isFinite(value)) return
  climMin.value = value
  if (climMin.value > climMax.value) climMax.value = climMin.value
}
function updateClimMax(value: number): void {
  if (!Number.isFinite(value)) return
  climMax.value = value
  if (climMax.value < climMin.value) climMin.value = climMax.value
}

// Re-render when display settings change (debounced to prevent flicker).
// 显示设置变化时重新渲染（防抖以避免闪烁）。
let rerenderTimer: ReturnType<typeof setTimeout> | null = null

function scheduleRerender(): void {
  if (!currentImagePath.value || !previewB64.value) return
  if (rerenderTimer) clearTimeout(rerenderTimer)
  rerenderTimer = setTimeout(() => {
    rerenderTimer = null
    void loadPreview(currentImagePath.value, true)
  }, 120)
}

watch([colormap, useLog, climMode, climMin, climMax], () => {
  scheduleRerender()
})

// === Beam center overlay (yellow crosshair) / 光斑中心叠加（黄色十字） ===

const colorbarGradient = computed(() => resolveColorbarGradient(colormap.value))
const colorbarMinLabel = computed(() => {
  if (!autoContrast.value) return '0'
  return useLog.value ? autoContrast.value.logMin.toExponential(3) : autoContrast.value.autoMin.toExponential(3)
})
const colorbarMaxLabel = computed(() => {
  if (!autoContrast.value) return '1'
  return useLog.value ? autoContrast.value.logMax.toExponential(3) : autoContrast.value.autoMax.toExponential(3)
})

/** Resolve the beam center to pixel coords using the current pixel size. */
const resolvedBeamCenterPx = computed<{ x: number; y: number } | null>(() => {
  if (!Number.isFinite(createForm.beamCenterX) || !Number.isFinite(createForm.beamCenterY)) return null
  const pixelSizeM = getPixelSizeMeters()
  if (pixelSizeM <= 0) return null
  // Convert the form value (in beamCenterUnit) to meters, then to pixels.
  const xM = beamCenterToMeters(createForm.beamCenterX, beamCenterUnit.value, pixelSizeM)
  const yM = beamCenterToMeters(createForm.beamCenterY, beamCenterUnit.value, pixelSizeM)
  return { x: xM / pixelSizeM, y: yM / pixelSizeM }
})

/** Origin marker position based on orientation. / 根据方向计算原点标记位置。 */
const originMarkerPx = computed<{ x: number; y: number }>(() => {
  const w = previewImageSize.value?.origWidth ?? 0
  const h = previewImageSize.value?.origHeight ?? 0
  const o = createForm.orientation
  // orientation 1: bottom-right (rows, cols) → (w, h)
  // orientation 2: top-right (rows, 0) → (w, 0)
  // orientation 4: bottom-left (0, cols) → (0, h)
  // orientation 0, 3 (default): top-left (0, 0)
  const x = (o === 1 || o === 2) ? w : 0
  const y = (o === 1 || o === 4) ? h : 0
  return { x, y }
})

/** Combined overlays: origin marker + beam center. / 合并叠加：原点标记 + 光斑中心。 */
const previewOverlays = computed<Overlay[]>(() => {
  const overlays: Overlay[] = []
  if (previewImageSize.value) {
    const om = originMarkerPx.value
    overlays.push({ type: 'originMarker', x: om.x, y: om.y, color: '#22d3ee' })
  }
  const bc = resolvedBeamCenterPx.value
  if (bc && previewImageSize.value) {
    overlays.push({ type: 'beamCenter', x: bc.x, y: bc.y, color: '#eab308' })
  }
  return overlays
})

const resolvedBeamCenterDisplay = computed(() => {
  const bc = resolvedBeamCenterPx.value
  if (!bc) return ''
  return `(${bc.x.toFixed(2)}, ${bc.y.toFixed(2)}) px`
})

// === Helpers / 辅助函数 ===

function formatValue(value: any, unit: string): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'number') {
    if (unit === 'mm') return `${(value * 1000).toFixed(4)} ${unit}`
    if (unit === 'Å') return `${(value * 1e10).toFixed(6)} ${unit}`
    if (unit === 'µm') return `${(value * 1e6).toFixed(3)} ${unit}`
    if (unit === 'deg') return `${(value * 180 / Math.PI).toFixed(4)} ${unit}`
    return `${value} ${unit}`
  }
  return `${value} ${unit}`
}

function formatBeamCenter(valueMeters: number): string {
  if (!Number.isFinite(valueMeters)) return '—'
  const ps = poniData.value?.pixel_size
  if (beamCenterUnit.value === 'px') {
    if (ps && ps > 0) return `${(valueMeters / ps).toFixed(2)} px`
    return '—'
  }
  if (beamCenterUnit.value === 'm') return `${valueMeters.toFixed(6)} m`
  return `${(valueMeters * 1e6).toFixed(3)} µm`
}

function submitAndWait(route: string, params: Record<string, unknown>): Promise<unknown> {
  return new Promise((resolve, reject) => {
    transport.submitTask(route, params).then(response => {
      let offResult: (() => void) | null = null
      let offError: (() => void) | null = null
      let settled = false
      const finish = (fn: () => void): void => {
        if (settled) return
        settled = true
        offResult?.()
        offError?.()
        fn()
      }
      offResult = transport.onTaskResult(response.taskId, p => finish(() => resolve(p.data)))
      offError = transport.onTaskError(response.taskId, p => finish(() => reject(new Error(p.error))))
    }).catch(reject)
  })
}

// === Export / 导出 ===

async function doExport(): Promise<void> {
  if (!poniData.value) return
  if (!isCustomDetector.value && !poniData.value.detector_name) {
    toast.push({
      title: t('poniImporter.errorTitle'),
      message: t('poniImporter.detectorRequired'),
      tone: 'error',
    })
    return
  }
  try {
    const plainPoniData = JSON.parse(JSON.stringify(poniData.value)) as PoniData
    let outputPath: string | undefined
    const fmt = exportFormat.value
    if (fmt === 'poni' || fmt === 'json') {
      const ext = fmt === 'poni' ? 'poni' : 'json'
      const defaultName = `calibration.${ext}`
      const filters = fmt === 'poni'
        ? [{ name: 'PONI Files', extensions: ['poni'] }]
        : [{ name: 'JSON Files', extensions: ['json'] }]
      const savePath = await transport.selectSavePath({ defaultPath: defaultName, filters })
      if (!savePath) return
      outputPath = savePath
    }

    const response = await transport.submitTask('poni_importer', {
      action: 'export',
      poni_data: plainPoniData,
      format: fmt,
      ...(outputPath ? { output_path: outputPath } : {}),
    })

    const unsubResult = transport.onTaskResult(response.taskId, (payload) => {
      const data = payload.data as { exported_path?: string; exported_content?: string; exported_params?: unknown }
      if (data.exported_path) {
        toast.push({
          title: t('poniImporter.exportSuccessTitle'),
          message: t('poniImporter.exportSuccessWithPath', { path: data.exported_path }),
          tone: 'success',
        })
      } else if (data.exported_content) {
        toast.push({
          title: t('poniImporter.exportSuccessTitle'),
          message: t('poniImporter.exportSuccess'),
          tone: 'success',
        })
      }
      unsubResult()
      unsubError()
    })

    const unsubError = transport.onTaskError(response.taskId, (payload) => {
      toast.push({
        title: t('poniImporter.errorTitle'),
        message: payload.error,
        tone: 'error',
      })
      unsubResult()
      unsubError()
    })
  } catch (err) {
    toast.push({
      title: t('poniImporter.errorTitle'),
      message: err instanceof Error ? err.message : String(err),
      tone: 'error',
    })
  }
}

onUnmounted(() => {
  if (rerenderTimer) {
    clearTimeout(rerenderTimer)
    rerenderTimer = null
  }
  if (previewB64.value?.startsWith('blob:')) URL.revokeObjectURL(previewB64.value)
  cleanupPreviewListeners()
})
</script>

<style scoped>
.poni-importer-page {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.pi-header {
  padding-bottom: 8px;
}

.pi-header h1 {
  font-size: 1.5rem;
  font-weight: 700;
  margin: 0 0 6px;
  color: var(--text-primary);
}

.pi-subtitle {
  font-size: 0.9375rem;
  color: var(--text-secondary);
  margin: 0;
}

.pi-layout {
  display: grid;
  grid-template-columns: minmax(280px, 380px) minmax(0, 1fr);
  gap: 24px;
  align-items: start;
}

/* Sidebar / 侧边栏 */
.pi-sidebar {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.pi-card {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  background: var(--bg-surface);
}

.pi-card-title {
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.pi-card-hint {
  font-size: 0.8125rem;
  color: var(--text-muted);
  margin: 0;
  line-height: 1.4;
}

.pi-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.pi-field--inline {
  flex: 1;
  min-width: 160px;
}

.pi-field-hint {
  margin: 2px 0 0;
  font-size: 0.75rem;
  color: var(--text-muted);
  line-height: 1.4;
}

.pi-label {
  font-size: 0.8125rem;
  color: var(--text-secondary);
  font-weight: 500;
}

.pi-label-sm {
  font-size: 0.75rem;
  color: var(--text-muted);
  font-weight: 500;
}

.pi-info-tip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  margin-left: 4px;
  border-radius: 50%;
  background: var(--bg-hover);
  color: var(--text-secondary);
  font-size: 0.7rem;
  cursor: help;
  user-select: none;
}

.pi-origin-hint {
  margin: 0;
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  background: var(--bg-hover);
  font-size: 0.75rem;
  color: var(--text-secondary);
  line-height: 1.5;
}

.pi-origin-link {
  display: inline-block;
  margin-top: 4px;
  color: var(--primary);
  font-size: 0.75rem;
  text-decoration: none;
}

.pi-origin-link:hover {
  text-decoration: underline;
}

.pi-auto-hint {
  margin: 0;
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  background: rgba(234, 179, 8, 0.12);
  color: #a16207;
  font-size: 0.75rem;
  line-height: 1.4;
}

.pi-input {
  padding: 8px 10px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: 0.875rem;
  transition: border-color var(--transition-fast);
}

.pi-input:focus {
  outline: none;
  border-color: var(--border-focus);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}

.pi-input--sm {
  padding: 4px 8px;
  font-size: 0.75rem;
  width: 110px;
}

.pi-select {
  padding: 8px 10px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: 0.875rem;
}

.pi-shape-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.pi-shape-x {
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: 0.85rem;
}

.pi-shape-row .pi-input {
  flex: 1;
  min-width: 0;
}

.pi-file-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin: 0;
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  background: var(--bg-hover);
}

.pi-file-info-label {
  font-size: 0.7rem;
  color: var(--text-muted);
  font-weight: 500;
}

.pi-file-info-value {
  font-size: 0.8rem;
  color: var(--text-primary);
  font-family: var(--font-mono);
  word-break: break-all;
}

/* Label row with inline unit toggle / 标签行含内联单位切换 */
.pi-label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.pi-unit-toggle {
  display: inline-flex;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  overflow: hidden;
  flex-shrink: 0;
}

.pi-unit-btn {
  padding: 2px 8px;
  border: none;
  background: var(--bg-surface);
  color: var(--text-muted);
  font-size: 0.6875rem;
  font-weight: 600;
  font-family: var(--font-mono);
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast);
  line-height: 1.4;
}

.pi-unit-btn:not(:last-child) {
  border-right: 1px solid var(--border);
}

.pi-unit-btn:hover {
  color: var(--text-primary);
  background: var(--bg-hover);
}

.pi-unit-btn--active {
  background: var(--primary-bg);
  color: var(--primary);
}

.pi-unit-btn--active:hover {
  background: var(--primary-bg);
  color: var(--primary);
}

/* Collapsible sections / 折叠区域 */
.pi-collapsible {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
  background: var(--bg-surface);
}

.pi-section-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  cursor: pointer;
  user-select: none;
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--text-primary);
  background: var(--bg-surface);
  transition: background var(--transition-fast);
}

.pi-section-toggle:hover {
  background: var(--bg-surface-alt);
}

.pi-toggle-icon {
  font-size: 0.75rem;
  color: var(--text-muted);
  width: 14px;
  text-align: center;
}

.pi-collapsible-body {
  padding: 14px;
  border-top: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* Buttons / 按钮 */
.pi-btn {
  padding: 10px 20px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
}

.pi-btn:hover:not(:disabled) {
  border-color: var(--border-hover);
  box-shadow: var(--shadow-sm);
}

.pi-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.pi-btn-primary {
  border: none;
  background: var(--primary);
  color: var(--text-inverse);
  font-weight: 600;
}

.pi-btn-primary:hover:not(:disabled) {
  opacity: 0.9;
}

/* Main area / 主区域 */
.pi-main {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.pi-empty-hint {
  padding: 20px 24px;
  text-align: center;
  color: var(--text-muted);
  font-size: 0.875rem;
}

.pi-empty-hint p {
  margin: 0;
}

.pi-error {
  padding: 20px 24px;
  border-radius: var(--radius-md);
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: var(--error);
  font-size: 0.875rem;
}

.pi-section {
  margin-bottom: 24px;
}

.pi-section:last-child {
  margin-bottom: 0;
}

.pi-section-title {
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--text-secondary);
  margin: 0 0 12px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.pi-param-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}

.pi-param-item {
  display: flex;
  justify-content: space-between;
  padding: 8px 12px;
  border-radius: var(--radius-sm);
  background: var(--bg-hover);
}

.pi-param-label {
  font-size: 0.8rem;
  color: var(--text-muted);
  font-weight: 500;
}

.pi-param-value {
  font-size: 0.8rem;
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-weight: 600;
}

.pi-json {
  padding: 16px;
  border-radius: var(--radius-sm);
  background: var(--bg-hover);
  font-size: 0.75rem;
  color: var(--text-primary);
  overflow-x: auto;
  font-family: var(--font-mono);
  line-height: 1.5;
  margin: 0;
}

/* Preview header + legend / 预览头部 + 图例 */
.pi-preview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.pi-preview-legend {
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
}

.pi-legend-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.pi-legend-dot {
  display: inline-block;
  width: 12px;
  height: 12px;
  border-radius: 50%;
}

.pi-legend-dot--yellow {
  background: #eab308;
  box-shadow: 0 0 0 1.5px #fff;
}

.pi-legend-corner {
  display: inline-block;
  width: 12px;
  height: 12px;
  border-left: 2px solid #22d3ee;
  border-top: 2px solid #22d3ee;
}

.pi-preview-loading,
.pi-preview-empty {
  padding: 40px 24px;
  text-align: center;
  color: var(--text-muted);
  font-size: 0.9375rem;
}

.pi-preview-area {
  position: relative;
  border-radius: var(--radius-md);
  overflow: hidden;
}

.pi-preview-image {
  position: relative;
}

/* (0,0) origin marker is now drawn on the overlay canvas / 原点标记已改为在叠加画布上绘制 */

/* Contrast controls / 对比度控件 */
.pi-contrast-section {
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.pi-contrast-title {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-secondary);
  margin: 0 0 4px;
}

.pi-contrast-row {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}

.pi-toggle-label,
.pi-radio-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.8125rem;
  color: var(--text-primary);
  cursor: pointer;
  user-select: none;
}

.pi-toggle-label input[type="checkbox"],
.pi-radio-label input[type="radio"] {
  accent-color: var(--primary);
  width: 14px;
  height: 14px;
}

.pi-contrast-sliders {
  display: grid;
  grid-template-columns: 1fr;
  gap: 10px;
}

.pi-clim-field {
  display: grid;
  grid-template-columns: 60px 1fr 110px;
  align-items: center;
  gap: 8px;
}

.pi-slider {
  width: 100%;
  accent-color: var(--primary);
}

.pi-preview-stats {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--border);
  display: flex;
  gap: 18px;
  flex-wrap: wrap;
}

.pi-stat {
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
  font-size: 0.8rem;
}

.pi-stat-label {
  color: var(--text-muted);
  font-weight: 500;
}

.pi-stat-value {
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: 0.78rem;
}

/* Responsive / 响应式 */
@media (max-width: 960px) {
  .pi-layout {
    grid-template-columns: 1fr;
  }
}
</style>
