<template>
  <div class="calib-setup-form">
    <!-- Image file / 标定图像 -->
    <div class="csf-field">
      <label class="csf-label">{{ t('calibration.setup.imageFile') }}</label>
      <div class="csf-path-row">
        <button
          v-if="transport.isDesktop()"
          type="button"
          class="csf-btn csf-btn--secondary"
          @click="chooseImage"
        >
          {{ t('calibration.setup.selectImage') }}
        </button>
        <input
          v-model="model.imagePath"
          type="text"
          class="csf-input csf-input--mono"
          :placeholder="transport.isDesktop() ? '—' : 'D:\\data\\calibrant.edf'"
          @blur="emitProbed()"
        />
      </div>
      <p v-if="!transport.isDesktop()" class="csf-hint">{{ webPathHint }}</p>
    </div>

    <!-- Calibrant: registry name or .D file / 校准物：名称或 .D 文件 -->
    <div class="csf-field">
      <label class="csf-label">{{ t('calibration.setup.calibrant') }}</label>
      <select
        :value="model.calibrant"
        class="csf-select"
        :disabled="!!model.calibrantPath"
        @change="patch({ calibrant: ($event.target as HTMLSelectElement).value })"
      >
        <option value="">—</option>
        <option v-for="name in calibrants" :key="name" :value="name">{{ name }}</option>
      </select>
      <!-- Registry list unavailable (fetch error) → hint via the built-in-calibrant
           label; the .D file below remains fully usable.
           内置标样列表不可用（拉取失败）→ 以内置标样标签提示；下方 .D 文件仍可用。 -->
      <p v-if="calibrants.length === 0" class="csf-hint">{{ t('calibration.setup.calibrantName') }}: —</p>

      <label class="csf-label csf-label--sub">{{ t('calibration.setup.calibrantName') }}</label>
      <div class="csf-path-row">
        <button
          v-if="transport.isDesktop()"
          type="button"
          class="csf-btn csf-btn--secondary"
          @click="chooseCalibrantFile"
        >
          .D
        </button>
        <input
          v-model="model.calibrantPath"
          type="text"
          class="csf-input csf-input--mono"
          placeholder="AgBh.D / LaB6.D"
        />
      </div>
      <label class="csf-label csf-label--sub">{{ t('calibration.setup.calibrantFile') }}</label>
    </div>

    <!-- Detector dropdown (auto-recognized from the image) / 探测器下拉（从图像自动识别） -->
    <div class="csf-field">
      <label class="csf-label">{{ t('calibration.setup.detector') }}</label>
      <select
        :value="model.detector"
        class="csf-select"
        @change="patch({ detector: ($event.target as HTMLSelectElement).value })"
      >
        <!-- Empty option = manual pixel size (field below) / 空选项 = 手动像素尺寸（下方输入） -->
        <option value="">{{ t('calibration.setup.pixelSize') }}</option>
        <option v-for="name in detectorOptions" :key="name" :value="name">{{ name }}</option>
      </select>
      <p v-if="probing" class="csf-hint">{{ t('calibration.setup.loading') }}</p>
      <p v-else-if="autoDetected" class="csf-badge">{{ autoDetectLabel }}: {{ autoDetected }}</p>
    </div>

    <!-- Pixel size in µm (only when no detector name) / 像素尺寸 µm（无探测器时显示） -->
    <div v-show="!hasDetector" class="csf-field">
      <label class="csf-label">{{ t('calibration.setup.pixelSize') }} (µm)</label>
      <input
        :value="model.pixelSizeUm"
        type="number"
        class="csf-input"
        step="any"
        min="1"
        @input="onNumberInput('pixelSizeUm', $event)"
      />
    </div>

    <!-- Mask (REQ 1: prevent wrong picks) / 掩膜（防止拾取错误） -->
    <div class="csf-field">
      <label class="csf-label">{{ maskFileLabel }}</label>
      <div class="csf-path-row">
        <button
          v-if="transport.isDesktop()"
          type="button"
          class="csf-btn csf-btn--secondary"
          @click="chooseMaskFile"
        >
          {{ maskSelectLabel }}
        </button>
        <input
          v-model="model.maskPath"
          type="text"
          class="csf-input csf-input--mono"
          :placeholder="transport.isDesktop() ? '—' : '/data/mask.npy'"
        />
      </div>
      <p class="csf-hint">{{ maskHint }}</p>
      <p v-if="maskStale" class="csf-badge csf-badge--stale">{{ maskStaleLabel }}</p>
    </div>

    <!-- Mask intensity bounds (optional) / 掩膜强度上下限（可选） -->
    <div class="csf-field csf-field--pair">
      <label class="csf-field-pair-item">
        <span class="csf-label">{{ maskMinLabel }}</span>
        <input
          :value="model.maskMin == null ? '' : model.maskMin"
          type="number"
          class="csf-input"
          step="any"
          :placeholder="emptyPlaceholder"
          @input="onNullableNumberInput('maskMin', $event)"
        />
      </label>
      <label class="csf-field-pair-item">
        <span class="csf-label">{{ maskMaxLabel }}</span>
        <input
          :value="model.maskMax == null ? '' : model.maskMax"
          type="number"
          class="csf-input"
          step="any"
          :placeholder="emptyPlaceholder"
          @input="onNullableNumberInput('maskMax', $event)"
        />
      </label>
    </div>

    <!-- Wavelength ↔ energy input (switchable) / 波长-能量输入（可切换） -->
    <div class="csf-field">
      <div class="csf-label-row">
        <label class="csf-label">
          {{ wlUnit === 'A' ? t('calibration.setup.wavelength') : t('calibration.setup.energy') }}
        </label>
        <!-- Å / keV segmented toggle; the value converts in place on switch.
             Å/keV 分段切换，切换时数值原位换算（λ·E = 12.3984 keV·Å）。 -->
        <div class="csf-unit-toggle" role="group" :aria-label="t('calibration.setup.unitToggle')">
          <button
            type="button"
            :class="['csf-unit-btn', { 'csf-unit-btn--active': wlUnit === 'A' }]"
            @click="wlUnit = 'A'"
          >Å</button>
          <button
            type="button"
            :class="['csf-unit-btn', { 'csf-unit-btn--active': wlUnit === 'keV' }]"
            @click="wlUnit = 'keV'"
          >keV</button>
        </div>
      </div>
      <input
        :value="wlDisplay"
        type="number"
        class="csf-input"
        step="any"
        min="0"
        @input="onWavelengthInput"
      />
      <p class="csf-hint">{{ t('calibration.setup.wavelengthHint') }}</p>
    </div>

    <!-- Initial distance guess / 初始距离猜测 -->
    <div class="csf-field">
      <label class="csf-label">{{ t('calibration.setup.distGuess') }} (mm)</label>
      <input
        :value="model.distGuessMm"
        type="number"
        class="csf-input"
        step="any"
        min="0"
        @input="onNumberInput('distGuessMm', $event)"
      />
      <p class="csf-hint">{{ t('calibration.setup.distHint') }}</p>
    </div>

    <!-- Seed from an existing .poni / 从 PONI 初始化 -->
    <button
      type="button"
      class="csf-btn csf-btn--ghost"
      :disabled="loading"
      @click="seedFromPoni"
    >
      {{ t('calibration.setup.seedFromPoni') }}
    </button>

    <!-- Load / 加载 -->
    <button
      type="button"
      class="csf-btn csf-btn--primary"
      data-ai-id="calibration:load"
      :disabled="!canSubmit || loading"
      @click="submit"
    >
      {{ loading ? t('calibration.setup.loading') : t('calibration.setup.load') }}
    </button>
  </div>
</template>

<script setup lang="ts">
/**
 * CalibSetupForm.vue — 标定向导第 1 步：加载表单
 * Calibration wizard step 1: setup form (image, calibrant, geometry guesses).
 *
 * v-model holds the form model (the parent may patch it after seed_from_poni);
 * emits 'submit' with the setup payload and 'seed' with a picked .poni path.
 */
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useTransport } from '@/lib/transport'

/** Editable setup model — owned by the parent (v-model). */
export interface CalibSetupModel {
  /** Calibrant image path on the backend host. */
  imagePath: string
  /** Calibrant registry name (e.g. 'AgBh'), empty when unset. */
  calibrant: string
  /** Optional custom calibrant .D file path (takes precedence over the name). */
  calibrantPath: string
  /** Optional pyFAI detector name; when set, pixel size is taken from the registry. */
  detector: string
  /** Pixel size in µm (used only when no detector name is given). */
  pixelSizeUm: number
  /** Wavelength in Å. */
  wavelengthA: number
  /** Initial distance guess in mm. */
  distGuessMm: number
  /** Optional mask file path (.edf/.npy/.npz/.tif/.tiff) — REQ 1. */
  maskPath: string
  /** Optional mask intensity lower bound (data < min is masked); null = off. */
  maskMin: number | null
  /** Optional mask intensity upper bound (data > max is masked); null = off. */
  maskMax: number | null
}

/** Payload emitted with 'submit' — forwarded to the backend 'setup' action. */
export interface CalibSetupPayload {
  filePath: string
  calibrant: string | null
  calibrantFile: string | null
  detector: string | null
  pixelSizeUm: number | null
  wavelengthA: number
  distGuessMm: number
  /** Mask file path (null = no mask file). / 掩膜文件路径（null = 无）。 */
  maskPath: string | null
  /** Mask intensity bounds (null = that bound is off). / 强度上下限（null = 关）。 */
  maskMin: number | null
  maskMax: number | null
}

/**
 * Result of the backend 'probe_image' action, passed down by the parent.
 * detector is null when the image could not be recognized.
 */
export interface CalibProbeInfo {
  /** Image path the probe ran against (guards against stale results). */
  imagePath: string
  /** Recognized pyFAI detector name, or null. */
  detector: string | null
  /** Pixel size in µm reported by the probe (null when unknown). */
  pixelSizeUm: number | null
}

const props = defineProps<{
  modelValue: CalibSetupModel
  /** Calibrant names from the backend 'list_calibrants' action. */
  calibrants: string[]
  /** pyFAI detector names from the backend 'list_detectors' action. */
  detectors: string[]
  /** Latest probe_image result for the current image path (null = none). */
  probe?: CalibProbeInfo | null
  /** True while the parent is running probe_image. */
  probing?: boolean
  loading?: boolean
  /**
   * REQ 1: mask inputs changed since the session was created → the shown
   * mask no longer matches the session; the user must re-load (应用 mask).
   * True 时显示“掩膜已修改”徽标，需重新加载以应用。
   */
  maskStale?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: CalibSetupModel]
  submit: [payload: CalibSetupPayload]
  seed: [poniPath: string]
  /** Fired when the image path changes (dialog pick or input blur). */
  probed: [imagePath: string]
}>()

const { t, locale } = useI18n()
const transport = useTransport()

// Web-mode hint is intentionally literal — the file must exist on the server.
const webPathHint = 'server path, e.g. /data/calibrant_0001.edf'

// Mutating helper: spread + emit, matching GeometryForm's v-model idiom.
// 与 GeometryForm 一致：浅拷贝后整体 emit，保持 v-model 语义。
const model = computed({
  get: () => props.modelValue,
  set: (value: CalibSetupModel) => emit('update:modelValue', value),
})

function patch(fields: Partial<CalibSetupModel>): void {
  emit('update:modelValue', { ...props.modelValue, ...fields })
}

function onNumberInput(field: 'pixelSizeUm' | 'distGuessMm', e: Event): void {
  const raw = (e.target as HTMLInputElement).value
  const num = parseFloat(raw)
  if (Number.isFinite(num)) patch({ [field]: num } as Partial<CalibSetupModel>)
}

// ── Wavelength ↔ energy (REQ 波长和能量可以切换) ────────────────────────────
// λ(Å) · E(keV) = hc/e = 12.398419843320026 keV·Å. The form model keeps the
// canonical wavelengthA; this local unit flag only changes what the input
// shows (display derives from the model, so seed_from_poni patches and the
// toggle stay consistent without a second field).
// 表单模型始终保存波长（Å）；单位开关只改变输入框显示（显示值由模型换算，
// PONI 初始化与切换天然一致）。
const KEV_ANGSTROM = 12.398419843320026

const wlUnit = ref<'A' | 'keV'>('A')

const wlDisplay = computed<string>(() => {
  const wl = props.modelValue.wavelengthA
  if (wlUnit.value === 'A') return String(wl)
  if (!Number.isFinite(wl) || wl <= 0) return ''
  return String(Number((KEV_ANGSTROM / wl).toPrecision(7)))
})

function onWavelengthInput(e: Event): void {
  const raw = (e.target as HTMLInputElement).value
  const num = parseFloat(raw)
  if (!Number.isFinite(num) || num <= 0) return
  patch({ wavelengthA: wlUnit.value === 'A' ? num : KEV_ANGSTROM / num })
}

/** Nullable numeric input (mask bounds): empty string → null (bound off).
 *  可空数字输入（掩膜上下限）：空串 → null（该界限关闭）。 */
function onNullableNumberInput(field: 'maskMin' | 'maskMax', e: Event): void {
  const raw = (e.target as HTMLInputElement).value.trim()
  if (!raw) {
    patch({ [field]: null } as Partial<CalibSetupModel>)
    return
  }
  const num = parseFloat(raw)
  if (Number.isFinite(num)) patch({ [field]: num } as Partial<CalibSetupModel>)
}

const hasDetector = computed(() => props.modelValue.detector.trim().length > 0)

// ── Detector dropdown + probe auto-recognition / 探测器下拉与自动识别 ─────────

/** Registry names plus the probed detector when missing from the list. */
const detectorOptions = computed(() => {
  const list = [...props.detectors]
  const probed = props.probe?.detector
  if (probed && !list.includes(probed)) list.push(probed)
  return list
})

/** Probed detector still matching the current selection → show the badge. */
const autoDetected = computed(() => {
  const p = props.probe
  if (!p || !p.detector) return null
  if (p.imagePath !== props.modelValue.imagePath.trim()) return null
  return props.modelValue.detector === p.detector ? p.detector : null
})

// No existing i18n key — short bilingual inline label (see final report).
// 暂无现成 i18n 键 —— 内联双语短文案（见最终报告缺失键清单）。
const autoDetectLabel = computed(() => (locale.value.startsWith('zh') ? '自动识别' : 'Auto-detected'))

// Mask inputs (REQ 1) — inline bilingual labels, no dedicated i18n keys yet.
// 掩膜输入（REQ 1）——内联双语文案，暂无 i18n 键。
const maskFileLabel = computed(() => (isZh.value ? '掩膜文件（可选）' : 'Mask file (optional)'))
const maskSelectLabel = computed(() => (isZh.value ? '选择掩膜' : 'Select mask'))
const maskHint = computed(() =>
  isZh.value
    ? '支持 .edf / .npy / .tif / .tiff；屏蔽坏点、光阑遮挡与饱和亮斑，防止误拾取'
    : 'Supports .edf / .npy / .tif / .tiff; masks dead pixels, beamstop edges and hot spots',
)
const maskMinLabel = computed(() => (isZh.value ? '强度下限' : 'Intensity min'))
const maskMaxLabel = computed(() => (isZh.value ? '强度上限' : 'Intensity max'))
const maskStaleLabel = computed(() =>
  isZh.value ? '掩膜参数已修改 — 请重新“载入并开始”以应用' : 'Mask inputs changed — reload to apply',
)
const emptyPlaceholder = computed(() => (isZh.value ? '不限' : 'off'))
const isZh = computed(() => locale.value.startsWith('zh'))

/** Apply a probe result: auto-select the detector, else prefill pixel size. */
watch(() => props.probe, (p) => {
  if (!p) return
  // Ignore stale results for a previous path. / 忽略针对旧路径的过期结果。
  if (p.imagePath !== props.modelValue.imagePath.trim()) return
  if (p.detector) {
    patch({ detector: p.detector })
  } else {
    patch({
      detector: '',
      ...(p.pixelSizeUm != null && p.pixelSizeUm > 0 ? { pixelSizeUm: p.pixelSizeUm } : {}),
    })
  }
})

/** Last path already emitted — dedupes blur/pick probe requests. */
let lastProbedPath = ''

/** Ask the parent to probe a (new) image path; empty paths are ignored. */
function emitProbed(path?: string): void {
  const value = (path ?? props.modelValue.imagePath).trim()
  if (!value || value === lastProbedPath) return
  lastProbedPath = value
  emit('probed', value)
}

const canSubmit = computed(() => {
  const m = props.modelValue
  if (!m.imagePath.trim()) return false
  if (!m.calibrantPath.trim() && !m.calibrant) return false
  if (!hasDetector.value && !(m.pixelSizeUm > 0)) return false
  return m.wavelengthA > 0 && m.distGuessMm > 0
})

async function chooseImage(): Promise<void> {
  try {
    const result = await transport.selectFiles({
      multiSelections: false,
      filters: [
        { name: 'Detector Images', extensions: ['edf', 'tif', 'tiff', 'h5', 'hdf5', 'cbf'] },
        { name: 'All files', extensions: ['*'] },
      ],
    })
    const path = Array.isArray(result) ? result[0] : result
    if (path) {
      patch({ imagePath: path })
      // Trigger detector auto-recognition for the freshly picked image.
      // 触发对新选图像的探测器自动识别。
      emitProbed(path)
    }
  } catch {
    // User cancelled the dialog / 用户取消对话框
  }
}

async function chooseCalibrantFile(): Promise<void> {
  try {
    const result = await transport.selectFiles({
      multiSelections: false,
      filters: [
        { name: 'Calibrant .D', extensions: ['d', 'D'] },
        { name: 'All files', extensions: ['*'] },
      ],
    })
    const path = Array.isArray(result) ? result[0] : result
    if (path) patch({ calibrantPath: path })
  } catch {
    // User cancelled the dialog / 用户取消对话框
  }
}

/** Desktop dialog for the mask file (.edf/.npy/.tif/.tiff) — REQ 1. */
async function chooseMaskFile(): Promise<void> {
  try {
    const result = await transport.selectFiles({
      multiSelections: false,
      filters: [
        { name: 'Mask files', extensions: ['edf', 'npy', 'npz', 'tif', 'tiff'] },
        { name: 'All files', extensions: ['*'] },
      ],
    })
    const path = Array.isArray(result) ? result[0] : result
    if (path) patch({ maskPath: path })
  } catch {
    // User cancelled the dialog / 用户取消对话框
  }
}

async function seedFromPoni(): Promise<void> {
  try {
    const result = await transport.selectFiles({
      multiSelections: false,
      filters: [{ name: 'PONI', extensions: ['poni'] }],
    })
    const path = Array.isArray(result) ? result[0] : result
    if (path) emit('seed', path)
  } catch {
    // User cancelled the dialog / 用户取消对话框
  }
}

function submit(): void {
  if (!canSubmit.value) return
  const m = props.modelValue
  emit('submit', {
    filePath: m.imagePath.trim(),
    calibrant: m.calibrantPath.trim() ? null : (m.calibrant || null),
    calibrantFile: m.calibrantPath.trim() || null,
    detector: m.detector.trim() || null,
    pixelSizeUm: hasDetector.value ? null : m.pixelSizeUm,
    wavelengthA: m.wavelengthA,
    distGuessMm: m.distGuessMm,
    maskPath: m.maskPath.trim() || null,
    maskMin: m.maskMin,
    maskMax: m.maskMax,
  })
}
</script>

<style scoped>
.calib-setup-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.csf-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.csf-label {
  font-size: 0.8125rem;
  color: var(--text-secondary);
  font-weight: 500;
}

.csf-label--sub {
  font-size: 0.7rem;
  color: var(--text-muted);
  font-weight: 400;
  margin-top: 2px;
}

/* Label + unit-toggle on one row / 标签与单位切换同行 */
.csf-label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

/* Å / keV segmented toggle / Å/keV 分段切换 */
.csf-unit-toggle {
  display: inline-flex;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  overflow: hidden;
  flex-shrink: 0;
}

.csf-unit-btn {
  border: none;
  background: var(--bg-surface);
  color: var(--text-muted);
  font-size: 0.72rem;
  font-weight: 600;
  font-family: var(--font-mono);
  padding: 3px 10px;
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast);
}

.csf-unit-btn + .csf-unit-btn {
  border-left: 1px solid var(--border);
}

.csf-unit-btn--active {
  background: var(--primary);
  color: var(--text-inverse);
}

.csf-hint {
  margin: 0;
  font-size: 0.75rem;
  color: var(--text-muted);
  line-height: 1.4;
}

/* Auto-detected detector badge / 自动识别探测器徽标 */
.csf-badge {
  margin: 0;
  align-self: flex-start;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--primary-bg, rgba(59, 130, 246, 0.12));
  color: var(--primary);
  font-size: 0.72rem;
  font-weight: 600;
  font-family: var(--font-mono);
  line-height: 1.5;
}

/* Stale-mask warning badge (REQ 1) / 掩膜已修改警示徽标 */
.csf-badge--stale {
  background: rgba(248, 113, 113, 0.14);
  color: #dc2626;
}

/* Side-by-side mask bound inputs / 并排的掩膜上下限输入 */
.csf-field--pair {
  flex-direction: row;
  gap: 8px;
}

.csf-field-pair-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.csf-input {
  padding: 8px 10px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: 0.875rem;
  transition: border-color var(--transition-fast);
}

.csf-input:focus {
  outline: none;
  border-color: var(--border-focus);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}

.csf-input--mono {
  font-family: var(--font-mono);
  font-size: 0.8rem;
}

.csf-select {
  padding: 8px 10px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: 0.875rem;
}

.csf-path-row {
  display: flex;
  gap: 8px;
  align-items: stretch;
}

.csf-path-row .csf-input {
  flex: 1;
  min-width: 0;
}

.csf-btn {
  padding: 8px 16px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  white-space: nowrap;
}

.csf-btn:hover:not(:disabled) {
  border-color: var(--border-hover);
  box-shadow: var(--shadow-sm);
}

.csf-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.csf-btn--secondary {
  border-color: var(--primary);
  color: var(--primary);
}

.csf-btn--ghost {
  border-style: dashed;
}

.csf-btn--primary {
  border: none;
  background: var(--primary);
  color: var(--text-inverse);
  font-weight: 600;
}

.csf-btn--primary:hover:not(:disabled) {
  opacity: 0.9;
}
</style>
