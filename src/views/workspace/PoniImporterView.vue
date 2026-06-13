<template>
  <section class="poni-importer-page">
    <!-- Header / 页头 -->
    <header class="pi-header">
      <h1>{{ t('poniImporter.title') }}</h1>
      <p class="pi-subtitle">{{ t('poniImporter.subtitle') }}</p>
    </header>

    <!-- ===== CREATE MODE / 创建模式 ===== -->
    <div class="pi-layout">
      <!-- Sidebar: create form / 侧边栏：创建表单 -->
      <aside class="pi-sidebar">
        <div class="pi-card">
          <h3 class="pi-card-title">{{ t('poniImporter.createTitle') }}</h3>
          <p class="pi-card-hint">{{ t('poniImporter.createSubtitle') }}</p>

          <!-- Geometry parameters / 几何参数 -->
          <div class="pi-field">
            <label class="pi-label">{{ t('poniImporter.detectorDistance') }} (mm)</label>
            <input v-model.number="createForm.distance" type="number" class="pi-input" step="1" min="0.1" />
          </div>

          <!-- Wavelength with unit toggle / 波长（含单位切换） -->
          <div class="pi-field">
            <div class="pi-label-row">
              <span class="pi-label">{{ t('poniImporter.wavelength') }}</span>
              <div class="pi-unit-toggle">
                <button
                  type="button"
                  :class="['pi-unit-btn', { 'pi-unit-btn--active': wavelengthUnit === 'angstrom' }]"
                  @click="onWavelengthUnitToggle('angstrom')"
                >Å</button>
                <button
                  type="button"
                  :class="['pi-unit-btn', { 'pi-unit-btn--active': wavelengthUnit === 'keV' }]"
                  @click="onWavelengthUnitToggle('keV')"
                >keV</button>
              </div>
            </div>
            <input v-model.number="createForm.wavelength" type="number" class="pi-input" step="any" min="0" />
          </div>

          <!-- Pixel size with unit toggle / 像素尺寸（含单位切换） -->
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

          <!-- Beam center with unit toggle / 光斑中心（含单位切换） -->
          <div class="pi-field">
            <div class="pi-label-row">
              <span class="pi-label">{{ t('poniImporter.beamCenterX') }} / {{ t('poniImporter.beamCenterY') }}</span>
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
          </div>
          <div class="pi-field">
            <label class="pi-label">{{ t('poniImporter.beamCenterX') }}</label>
            <input v-model.number="createForm.beamCenterX" type="number" class="pi-input" step="any" min="0" />
          </div>
          <div class="pi-field">
            <label class="pi-label">{{ t('poniImporter.beamCenterY') }}</label>
            <input v-model.number="createForm.beamCenterY" type="number" class="pi-input" step="any" min="0" />
          </div>

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

          <!-- Detector preset (one-click import) / 探测器预设（一键导入） -->
          <div class="pi-field">
            <label class="pi-label">{{ t('poniImporter.detectorPreset') }}</label>
            <select v-model="selectedPreset" class="pi-select">
              <option value="">{{ t('poniImporter.detectorCustom') }}</option>
              <option v-for="p in detectorPresets" :key="p.name" :value="p.name">{{ p.name }}</option>
            </select>
          </div>
          <div class="pi-field">
            <label class="pi-label">{{ t('poniImporter.detectorName') }}</label>
            <input v-model="createForm.detector_name" type="text" class="pi-input" />
          </div>
        </div>
      </aside>

      <!-- Main area: real-time preview / 主区域：实时预览 -->
      <main class="pi-main">
        <div v-if="state === 'error'" class="pi-error">
          <p>{{ t('poniImporter.errorPrefix') }} {{ errorMessage }}</p>
        </div>

        <div class="pi-content">
          <h3 class="pi-content-title">{{ t('poniImporter.createSuccessTitle') }}</h3>

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
                  <span class="pi-param-label">{{ t('poniParams.beamCenterX') }}:</span>
                  <span class="pi-param-value">{{ formatBeamCenter(poniData.poni1) }}</span>
                </div>
                <div class="pi-param-item">
                  <span class="pi-param-label">{{ t('poniParams.beamCenterY') }}:</span>
                  <span class="pi-param-value">{{ formatBeamCenter(poniData.poni2) }}</span>
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
            <button type="button" class="pi-btn" :disabled="!poniData" @click="doExport">
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
 * PoniImporterView.vue — PONI文件转化页面
 * PONI file conversion page: create and export pyFAI .poni calibration files with real-time preview
 */
import { ref, reactive, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useToast } from '@/lib/toast'
import { useTransport } from '@/lib/transport'

// === Type definitions / 类型定义 ===

interface PoniData {
  distance: number      // Detector distance in meters
  wavelength: number    // Wavelength in meters
  pixel_size: number    // Pixel size in meters
  poni1: number         // Beam center X (meters, = center_y_px * pixel_size)
  poni2: number         // Beam center Y (meters, = center_x_px * pixel_size)
  rot1?: number         // Rotation 1 (radians)
  rot2?: number         // Rotation 2 (radians)
  rot3?: number         // Rotation 3 (radians)
  detector_name?: string // Detector name
  [key: string]: any    // Additional fields
}

type PageState = 'idle' | 'loading' | 'error' | 'success'
type ExportFormat = 'json' | 'poni'

// === Composables / 组合函数 ===

const { t } = useI18n()
const toast = useToast()
const transport = useTransport()

// === State / 状态 ===

const state = ref<PageState>('idle')
const errorMessage = ref('')
const exportFormat = ref<ExportFormat>('poni')

// Create form state (user-friendly units) / 创建表单状态（用户友好单位）
const createForm = reactive({
  distance: 100,        // mm
  wavelength: 1.5418,   // Å (or keV depending on wavelengthUnit)
  pixel_size: 172,      // µm (or mm depending on pixelSizeUnit)
  beamCenterX: 512,     // px, µm, or m depending on beamCenterUnit
  beamCenterY: 512,
  rot1: 0,              // degrees
  rot2: 0,
  rot3: 0,
  detector_name: '',
})

// Unit toggles / 单位切换
type WavelengthUnit = 'angstrom' | 'keV'
type PixelSizeUnit = 'um' | 'mm'
type BeamCenterUnit = 'px' | 'um' | 'm'
const wavelengthUnit = ref<WavelengthUnit>('angstrom')
const pixelSizeUnit = ref<PixelSizeUnit>('um')
const beamCenterUnit = ref<BeamCenterUnit>('px')

// Wavelength conversion: E(keV) = 12.39842 / λ(Å) / 波长转换
const HC_KEV_A = 12.39842 // h*c in keV·Å

function convertWavelengthValue(oldUnit: WavelengthUnit, newUnit: WavelengthUnit, value: number): number {
  if (oldUnit === newUnit) return value
  // Convert to Å first / 先转换为 Å
  const angstrom = oldUnit === 'angstrom' ? value : HC_KEV_A / value
  // Convert from Å to target / 从 Å 转换为目标单位
  return newUnit === 'angstrom' ? angstrom : HC_KEV_A / angstrom
}

function onWavelengthUnitToggle(newUnit: WavelengthUnit): void {
  const oldUnit = wavelengthUnit.value
  if (oldUnit === newUnit) return
  createForm.wavelength = convertWavelengthValue(oldUnit, newUnit, createForm.wavelength)
  wavelengthUnit.value = newUnit
}

// Pixel size conversion / 像素尺寸转换
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

// Helper: get current pixel size in meters / 辅助：获取当前像素尺寸（米）
function getPixelSizeMeters(): number {
  return pixelSizeUnit.value === 'um' ? createForm.pixel_size * 1e-6 : createForm.pixel_size * 1e-3
}

// Beam center conversion via meters intermediate / 光斑中心通过米中间值转换
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
  // Convert old value → meters → new unit
  const beamXM = beamCenterToMeters(createForm.beamCenterX, oldUnit, pixelSizeM)
  const beamYM = beamCenterToMeters(createForm.beamCenterY, oldUnit, pixelSizeM)
  createForm.beamCenterX = metersToBeamCenter(beamXM, newUnit, pixelSizeM)
  createForm.beamCenterY = metersToBeamCenter(beamYM, newUnit, pixelSizeM)
  beamCenterUnit.value = newUnit
}

// === Real-time computed PONI data / 实时计算 PONI 数据 ===

const poniData = computed<PoniData | null>(() => {
  // Validate all required fields
  if (!Number.isFinite(createForm.distance) || createForm.distance <= 0) return null
  if (!Number.isFinite(createForm.wavelength) || createForm.wavelength <= 0) return null
  if (!Number.isFinite(createForm.pixel_size) || createForm.pixel_size <= 0) return null
  if (!Number.isFinite(createForm.beamCenterX)) return null
  if (!Number.isFinite(createForm.beamCenterY)) return null

  const pixelSizeM = getPixelSizeMeters()
  const distanceM = createForm.distance * 1e-3  // mm → m

  let wavelengthM: number
  if (wavelengthUnit.value === 'angstrom') {
    wavelengthM = createForm.wavelength * 1e-10
  } else {
    wavelengthM = (HC_KEV_A / createForm.wavelength) * 1e-10
  }

  const beamXM = beamCenterToMeters(createForm.beamCenterX, beamCenterUnit.value, pixelSizeM)
  const beamYM = beamCenterToMeters(createForm.beamCenterY, beamCenterUnit.value, pixelSizeM)

  const DEG2RAD = Math.PI / 180
  return {
    distance: distanceM,
    wavelength: wavelengthM,
    pixel_size: pixelSizeM,
    poni1: beamYM,
    poni2: beamXM,
    rot1: createForm.rot1 * DEG2RAD,
    rot2: createForm.rot2 * DEG2RAD,
    rot3: createForm.rot3 * DEG2RAD,
    detector_name: createForm.detector_name || undefined,
  }
})

// === Detector presets (pyFAI compatible) / 探测器预设 ===

interface DetectorPreset {
  name: string
  detector_name: string
  pixel_size: number  // in mm
}

const detectorPresets: DetectorPreset[] = [
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
]

const selectedPreset = ref<string>('')

// Watch preset selection and auto-fill form / 监听预设选择并自动填充表单
watch(selectedPreset, (presetName) => {
  if (!presetName) return
  const preset = detectorPresets.find(p => p.name === presetName)
  if (preset) {
    createForm.detector_name = preset.detector_name
    // Preset pixel_size is in mm; convert to current pixel size unit
    createForm.pixel_size = pixelSizeUnit.value === 'um' ? preset.pixel_size * 1000 : preset.pixel_size
  }
})

// === Helpers / 辅助函数 ===

function formatValue(value: any, unit: string): string {
  if (value === null || value === undefined) {
    return '—'
  }
  if (typeof value === 'number') {
    if (unit === 'mm') {
      return `${(value * 1000).toFixed(4)} ${unit}`
    }
    if (unit === 'Å') {
      return `${(value * 1e10).toFixed(6)} ${unit}`
    }
    if (unit === 'µm') {
      return `${(value * 1e6).toFixed(3)} ${unit}`
    }
    if (unit === 'deg') {
      return `${(value * 180 / Math.PI).toFixed(4)} ${unit}`
    }
    return `${value} ${unit}`
  }
  return `${value} ${unit}`
}

/** Format beam center from SI meters to user-selected display unit / 将光束中心从 SI 米转换为用户选择的显示单位 */
function formatBeamCenter(valueMeters: number): string {
  if (!Number.isFinite(valueMeters)) return '—'
  const ps = poniData.value?.pixel_size
  if (beamCenterUnit.value === 'px') {
    if (ps && ps > 0) return `${(valueMeters / ps).toFixed(2)} px`
    return '—'
  }
  if (beamCenterUnit.value === 'm') {
    return `${valueMeters.toFixed(6)} m`
  }
  return `${(valueMeters * 1e6).toFixed(3)} µm`
}

// === Export / 导出 ===

async function doExport(): Promise<void> {
  if (!poniData.value) return
  try {
    // Deep-clone to strip Vue reactive proxy metadata before IPC.
    // Vue's reactive()/ref() wrappers add internal symbol keys (e.g. __v_isReactive,
    // __v_raw) that Electron's structured-clone cannot handle, causing
    // "An object could not be cloned" errors on ipcRenderer.invoke.
    const plainPoniData = JSON.parse(JSON.stringify(poniData.value)) as PoniData

    // Determine the output file path via save dialog
    let outputPath: string | undefined
    const fmt = exportFormat.value
    if (fmt === 'poni' || fmt === 'json') {
      const ext = fmt === 'poni' ? 'poni' : 'json'
      const defaultName = `calibration.${ext}`
      const filters = fmt === 'poni'
        ? [{ name: 'PONI Files', extensions: ['poni'] }]
        : [{ name: 'JSON Files', extensions: ['json'] }]
      const savePath = await transport.selectSavePath({
        defaultPath: defaultName,
        filters,
      })
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

.pi-label {
  font-size: 0.8125rem;
  color: var(--text-secondary);
  font-weight: 500;
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

.pi-select {
  padding: 8px 10px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: 0.875rem;
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

.pi-file-info {
  padding: 10px;
  border-radius: var(--radius-md);
  background: var(--bg-hover);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.pi-file-info-label {
  font-size: 0.75rem;
  color: var(--text-muted);
  font-weight: 500;
}

.pi-file-info-value {
  font-size: 0.8rem;
  color: var(--text-primary);
  font-family: var(--font-mono);
  word-break: break-all;
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
  padding: 12px 24px;
  border: none;
  background: var(--primary);
  color: var(--text-inverse);
  font-size: 0.9375rem;
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

.pi-empty {
  padding: 60px 24px;
  text-align: center;
  color: var(--text-muted);
  font-size: 0.9375rem;
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

.pi-loading {
  padding: 40px 24px;
  text-align: center;
  color: var(--text-secondary);
  font-size: 0.9375rem;
}

.pi-error {
  padding: 20px 24px;
  border-radius: var(--radius-md);
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: var(--error);
  font-size: 0.875rem;
}

.pi-content {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 20px;
  background: var(--bg-surface);
}

.pi-content-title {
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 16px;
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
}

/* Responsive / 响应式 */
@media (max-width: 960px) {
  .pi-layout {
    grid-template-columns: 1fr;
  }
}
</style>
