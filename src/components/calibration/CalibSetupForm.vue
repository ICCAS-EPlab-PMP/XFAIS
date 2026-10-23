<template>
  <div class="calib-setup-form">
    <!-- Mode selector: 标样校正 (calibrant) / 内标定标 (internal standard) /
         直通光定心 (direct-beam centroid, the THIRD mode). The three modes are
         MUTUALLY EXCLUSIVE — the parent resets the whole wizard on a switch, so
         the user must 载入并开始 again.
         模式选择：标样校正 / 内标定标 / 直通光定心（第三种模式）。三种模式互斥
         ——切换时父组件重置整个向导，需重新「载入并开始」。 -->
    <div class="csf-field">
      <label class="csf-label">{{ t('calibration.mode.label') }}</label>
      <div class="csf-unit-toggle csf-mode-toggle" role="group" :aria-label="t('calibration.mode.label')">
        <button
          type="button"
          :class="['csf-unit-btn', { 'csf-unit-btn--active': model.mode === 'calibrant' }]"
          data-ai-id="calibration:mode-calibrant"
          @click="patch({ mode: 'calibrant' })"
        >{{ t('calibration.mode.calibrant') }}</button>
        <button
          type="button"
          :class="['csf-unit-btn', { 'csf-unit-btn--active': model.mode === 'internal' }]"
          data-ai-id="calibration:mode-internal"
          @click="patch({ mode: 'internal' })"
        >{{ t('calibration.mode.internal') }}</button>
        <button
          type="button"
          :class="['csf-unit-btn', { 'csf-unit-btn--active': model.mode === 'com' }]"
          data-ai-id="calibration:mode-com"
          @click="patch({ mode: 'com' })"
        >{{ t('calibration.mode.com') }}</button>
      </div>
      <p v-if="isBeamPhase" class="csf-hint">{{ t('calibration.mode.comBeamHint') }}</p>
    </div>

    <!-- SECOND-IMAGE phase of the direct-beam mode: the standard image is
         loaded here and the user chooses which calibration branch continues —
         标样校正 (calibrant rings + refine) or 内标定标 (one known ring) —
         both with the direct-beam centre FIXED and only the distance optimised.
         直通光模式的第二次上传：在此载入标样图，并选择后续走标样校正（环 + 精修）
         还是内标定标（单个已知环）——两条支路都以直通光中心为固定值、只优化距离。 -->
    <div v-if="isStandardPhase" class="csf-field">
      <label class="csf-label">{{ t('calibration.mode.standardBranch') }}</label>
      <div class="csf-unit-toggle csf-mode-toggle" role="group" :aria-label="t('calibration.mode.standardBranch')">
        <button
          type="button"
          :class="['csf-unit-btn', { 'csf-unit-btn--active': standardMode === 'calibrant' }]"
          data-ai-id="calibration:standard-calibrant"
          @click="$emit('update:standardMode', 'calibrant')"
        >{{ t('calibration.mode.calibrant') }}</button>
        <button
          type="button"
          :class="['csf-unit-btn', { 'csf-unit-btn--active': standardMode === 'internal' }]"
          data-ai-id="calibration:standard-internal"
          @click="$emit('update:standardMode', 'internal')"
        >{{ t('calibration.mode.internal') }}</button>
      </div>
      <p class="csf-hint">{{ t('calibration.mode.standardBranchHint') }}</p>
    </div>

    <!-- Image file / 标定图像 -->
    <div class="csf-field">
      <label class="csf-label">
        {{ isBeamPhase ? t('calibration.setup.beamImage') : (isStandardPhase ? t('calibration.setup.standardImage') : t('calibration.setup.imageFile')) }}
      </label>
      <div class="csf-path-row">
        <!-- Web/server mode: transport.selectFiles opens the browser picker and
             uploads the file, returning the server-side path — the user never
             needs to know a server path. / Web 模式下走浏览器选文件并上传，
             回填服务器路径，用户无需知道服务器上的路径。 -->
        <button
          type="button"
          class="csf-btn csf-btn--secondary"
          @click="chooseImage"
        >
          {{ transport.isDesktop() ? t('calibration.setup.selectImage') : t('calibration.setup.uploadImage') }}
        </button>
        <input
          v-model="model.imagePath"
          type="text"
          class="csf-input csf-input--mono"
          :placeholder="transport.isDesktop() ? '—' : 'calibrant_0001.edf'"
          @blur="emitProbed()"
        />
      </div>
      <p v-if="!transport.isDesktop()" class="csf-hint">{{ t('calibration.setup.webUploadHint') }}</p>
    </div>

    <!-- Calibrant source: ONE selector, mutually exclusive built-in vs local .D —
         same segmented-toggle pattern as the mode switch above. / 标样来源：
         内置标样与本地 .D 文件互斥的分段开关，与上方模式开关同款。
         HIDDEN whenever the active branch needs no calibrant: internal-standard
         mode (ring_standard), the direct-beam image phase, and the com mode's
         internal-standard branch. / 当前支路不需要标样时整块隐藏：内标模式、
         直通光模式的直通光图阶段与其内标支路。 -->
    <div v-if="showCalibrant" class="csf-field" :class="{ 'csf-field--disabled': isInternal }">
      <label class="csf-label">{{ t('calibration.setup.calibrantSource') }}</label>
      <div class="csf-unit-toggle csf-mode-toggle" role="group" :aria-label="t('calibration.setup.calibrantSource')">
        <button
          type="button"
          :class="['csf-unit-btn', { 'csf-unit-btn--active': calibrantSource === 'builtin' }]"
          :disabled="isInternal"
          @click="setCalibrantSource('builtin')"
        >{{ t('calibration.setup.calibrantBuiltin') }}</button>
        <button
          type="button"
          :class="['csf-unit-btn', { 'csf-unit-btn--active': calibrantSource === 'file' }]"
          :disabled="isInternal"
          @click="setCalibrantSource('file')"
        >{{ t('calibration.setup.calibrantLocalFile') }}</button>
      </div>

      <!-- Built-in: exactly ONE control. Registry list loaded → <select>; list
           unavailable → free text + datalist fallback (keeps the empty-list bug
           fix). / 内置标样：仅一个控件。列表已拉到用下拉；拉不到退化为自由文本
           + datalist（保留空列表场景的修复）。 -->
      <template v-if="calibrantSource === 'builtin'">
        <select
          v-if="calibrants.length > 0"
          :value="model.calibrant"
          class="csf-select"
          :disabled="isInternal"
          @change="onBuiltinSelect"
        >
          <option value="">—</option>
          <option v-for="name in calibrants" :key="name" :value="name">{{ name }}</option>
        </select>
        <template v-else>
          <input
            :value="model.calibrant"
            type="text"
            class="csf-input csf-input--mono"
            list="calib-calibrant-names"
            :placeholder="isZh ? '内置标样名，如 LaB6' : 'Built-in name, e.g. LaB6'"
            :disabled="isInternal"
            @input="onCalibrantTextInput"
          />
          <datalist id="calib-calibrant-names">
            <option v-for="name in calibrants" :key="name" :value="name" />
          </datalist>
        </template>
      </template>

      <!-- Local .D: a single browse button — NO path text input. The chosen file
           name is echoed as a hint; a small link routes to the calibrant
           generator. / 本地 .D：仅一个选文件按钮——无路径输入框。已选文件名以
           小字回显；小字链接跳转校正标样生成器。 -->
      <template v-else>
        <button
          type="button"
          class="csf-btn csf-btn--secondary csf-btn--block"
          :disabled="isInternal"
          @click="chooseCalibrantFile"
        >
          {{ transport.isDesktop() ? t('calibration.setup.selectCalibrantFile') : t('calibration.setup.uploadCalibrant') }}
        </button>
        <p v-if="model.calibrantPath.trim()" class="csf-hint">
          {{ t('calibration.setup.selectedFile') }}: {{ calibrantFileName }}
        </p>
        <p class="csf-hint csf-hint--link">
          {{ t('calibration.setup.noCalibrantFileHint') }}
          <a
            role="link"
            tabindex="0"
            @click="goGenerator"
            @keydown.enter.prevent="goGenerator"
          >{{ t('calibration.setup.goGenerator') }} →</a>
        </p>
      </template>
    </div>

    <!-- Detector dropdown (auto-recognized from the image) / 探测器下拉（从图像自动识别） -->
    <div class="csf-field">
      <label class="csf-label">{{ t('calibration.setup.detector') }}</label>
      <select
        :value="model.detector"
        class="csf-select"
        @change="patch({ detector: ($event.target as HTMLSelectElement).value })"
      >
        <!-- Empty option = manual pixel size (field below). Its own label —
             NOT the pixelSize key, which read as a duplicate of the field
             label below (2026-10-22 visual review). / 空选项 = 手动像素尺寸
             （下方输入）。用专用文案，不再复用 pixelSize 键造成视觉重复。 -->
        <option value="">{{ t('calibration.setup.noDetectorManual') }}</option>
        <option v-for="name in detectorOptions" :key="name" :value="name">{{ name }}</option>
      </select>
      <p v-if="probing" class="csf-hint">{{ t('calibration.setup.loading') }}</p>
      <p v-else-if="autoDetected" class="csf-badge">{{ autoDetectLabel }}: {{ autoDetected }}</p>
    </div>

    <!-- Pixel size in µm (only when no detector name) / 像素尺寸 µm（无探测器时显示） -->
    <div v-show="!hasDetector" class="csf-field">
      <!-- Unit "(µm)" already lives in the i18n label — do not append it again
           (2026-10-22 visual review: it rendered as「像素尺寸 (µm) (µm)」). -->
      <label class="csf-label">{{ t('calibration.setup.pixelSize') }}</label>
      <NumberField
        :model-value="model.pixelSizeUm"
        class="csf-input"
        step="any"
        min="1"
        @update:model-value="onNumberInput('pixelSizeUm', $event)"
      />
    </div>

    <!-- Mask (REQ 1: prevent wrong picks) / 掩膜（防止拾取错误）
         Hidden on the direct-beam image phase: no peak picking happens there
         (the CoM centres on the bright spot by itself). / 直通光图阶段隐藏：
         该阶段不做寻峰（质心法自带热点抑制）。 -->
    <div v-if="!isBeamPhase" class="csf-field">
      <label class="csf-label">{{ maskFileLabel }}</label>
      <div class="csf-path-row">
        <button
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
          :placeholder="transport.isDesktop() ? '—' : 'mask.npy'"
        />
      </div>
      <p class="csf-hint">{{ maskHint }}</p>
      <p v-if="maskStale" class="csf-badge csf-badge--stale">{{ maskStaleLabel }}</p>
    </div>

    <!-- Mask intensity bounds (optional) / 掩膜强度上下限（可选） -->
    <div v-if="!isBeamPhase" class="csf-field csf-field--pair">
      <label class="csf-field-pair-item">
        <span class="csf-label">{{ maskMinLabel }}</span>
        <NumberField
          :model-value="model.maskMin"
          class="csf-input"
          step="any"
          :placeholder="emptyPlaceholder"
          @update:model-value="onNullableNumberInput('maskMin', $event)"
        />
      </label>
      <label class="csf-field-pair-item">
        <span class="csf-label">{{ maskMaxLabel }}</span>
        <NumberField
          :model-value="model.maskMax"
          class="csf-input"
          step="any"
          :placeholder="emptyPlaceholder"
          @update:model-value="onNullableNumberInput('maskMax', $event)"
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
      <NumberField
        :model-value="wlNumber"
        class="csf-input"
        step="any"
        min="0"
        @update:model-value="onWavelengthInput"
      />
      <p class="csf-hint">{{ t('calibration.setup.wavelengthHint') }}</p>
    </div>

    <!-- Initial distance guess / 初始距离猜测 — COLLAPSED by default
         (2026-10-20 user request: 预估 SD 默认收起，不要展开). The presets
         and hint live inside the fold; the value still travels with the setup
         payload untouched. Hidden in internal-standard mode: that mode derives
         the distance (SD) from the standard ring in step 2, so the guess is
         not needed (the backend setup contract still requires distGuessMm >
         0 — the form simply keeps whatever it holds).
         初始距离猜测——默认折叠（2026-10-20 用户要求：预估 SD 默认收了）。
         预设按钮与提示在折叠区内；数值仍原样随 setup 载荷下发。内标模式下
         隐藏：该模式的 SD 由第 2 步的标准环算出（后端契约仍要求
         distGuessMm > 0，表单保持现值即可）。 -->
    <details v-if="showSdGuess" class="csf-details csf-details--sd">
      <summary class="csf-details-summary">{{ sdGroupLabel }}</summary>
      <div class="csf-field csf-field--inner">
        <label class="csf-label">{{ t('calibration.setup.distGuess') }} (mm)</label>
        <NumberField
          :model-value="model.distGuessMm"
          class="csf-input"
          step="any"
          min="0"
          @update:model-value="onNumberInput('distGuessMm', $event)"
        />
        <!-- Common distance presets (user request 2026-10-13): one tap fills the
             guess so ring assignment starts from a sane geometry. /
             常用距离预设（2026-10-13 用户要求）：一键填入猜测值，使环号分配从
             合理几何起步。 -->
        <div class="csf-preset-row">
          <button
            type="button"
            class="csf-btn csf-btn--secondary csf-btn--sm"
            :title="distPresetTitle"
            @click="onNumberInput('distGuessMm', 130)"
          >WAXS · 130</button>
          <button
            type="button"
            class="csf-btn csf-btn--secondary csf-btn--sm"
            :title="distPresetTitle"
            @click="onNumberInput('distGuessMm', 2500)"
          >SAXS · 2500</button>
        </div>
        <p class="csf-hint">{{ t('calibration.setup.distHint') }}</p>
      </div>
    </details>

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
import { useRouter } from 'vue-router'
import { useTransport } from '@/lib/transport'
import { useToast } from '@/lib/toast'
import NumberField from '@/components/common/NumberField.vue'

/** Wizard mode: 'calibrant' = classic 标样校正; 'internal' = 内标定标 (one
 *  known ring computes the geometry, no calibrant / no refinement);
 *  'com' = 直通光定心 (two uploads: direct-beam image → box → centre of mass,
 *  then the standard image branches back into calibrant or internal standard
 *  with that centre FIXED and only the distance optimised).
 *  向导模式：calibrant = 标样校正；internal = 内标定标（单个已知环直接算
 *  几何，无标样、无精修）；com = 直通光定心（两次上传：直通光图 → 框选质心，
 *  随后标样图回到标样校正或内标定标，中心固定、只优化距离）。 */
export type CalibMode = 'calibrant' | 'internal' | 'com'

/** Which phase of the com mode this form instance is rendering:
 *  'single'   — the ordinary single-image setup (calibrant/internal modes);
 *  'beam'     — com mode, FIRST image (the direct-beam frame);
 *  'standard' — com mode, SECOND image (the calibrant/standard frame).
 *  com 模式下本表单所处阶段：single = 普通单图；beam = 直通光图（第一张）；
 *  standard = 标样图（第二张）。 */
export type CalibSetupPhase = 'single' | 'beam' | 'standard'

/** Editable setup model — owned by the parent (v-model). */
export interface CalibSetupModel {
  /** Mutual-exclusion mode switch (default 'calibrant'). / 互斥模式开关。 */
  mode: CalibMode
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
  /**
   * Beam-centre seed in image pixels (x = column) — filled from a .poni
   * (seed_from_poni) and forwarded with the setup payload as the backend's
   * first-guess centre (poni1/poni2), ahead of guess_poni()'s ellipse fit.
   * null = unset. / 束流中心种子（图像像素，x = 列）——由 .poni 初始化
   * （seed_from_poni）填入，随 setup 载荷下发为后端首猜中心（poni1/poni2），
   * 优先于 guess_poni() 的椭圆估计。null = 未设置。
   */
  centerXPx: number | null
  /** Beam-centre seed in image pixels (y = row). / 束流中心种子（y = 行）。 */
  centerYPx: number | null
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
  /**
   * Beam-centre seed in px (null = not supplied) — the backend stores it as
   * the session's first-guess centre (poni1/poni2) for integration and
   * refinement. / 束流中心种子（像素，null = 未提供）——后端存为会话首猜
   * 中心（poni1/poni2），供积分与精修使用。
   */
  centerX: number | null
  centerY: number | null
  /**
   * TRUE on the com mode's SECOND setup: the backend then pins poni1/poni2 and
   * the rotations and optimises the DISTANCE ONLY (fixed-centre session).
   * com 模式第二次 setup 时置 true：后端钉住 poni1/poni2 与旋转角，只优化
   * 距离（固定中心会话）。
   */
  fixedCenter?: boolean
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
  /** Com-mode phase this form renders (default 'single'). / com 模式阶段。 */
  phase?: CalibSetupPhase
  /** Standard branch chosen on the com mode's SECOND image (default 'calibrant'). */
  standardMode?: 'calibrant' | 'internal'
}>()

const emit = defineEmits<{
  'update:modelValue': [value: CalibSetupModel]
  submit: [payload: CalibSetupPayload]
  seed: [poniPath: string]
  /** Fired when the image path changes (dialog pick or input blur). */
  probed: [imagePath: string]
  'update:standardMode': [value: 'calibrant' | 'internal']
}>()

const { t, locale } = useI18n()
const transport = useTransport()
const toast = useToast()
const router = useRouter()

const isDesktop = transport.isDesktop()

// Mutating helper: spread + emit, matching GeometryForm's v-model idiom.
// 与 GeometryForm 一致：浅拷贝后整体 emit，保持 v-model 语义。
const model = computed({
  get: () => props.modelValue,
  set: (value: CalibSetupModel) => emit('update:modelValue', value),
})

function patch(fields: Partial<CalibSetupModel>): void {
  emit('update:modelValue', { ...props.modelValue, ...fields })
}

function onNumberInput(field: 'pixelSizeUm' | 'distGuessMm', value: number | null): void {
  if (value != null && Number.isFinite(value)) patch({ [field]: value } as Partial<CalibSetupModel>)
}

/** Tooltip for the WAXS/SAXS distance presets (user request 2026-10-13). */
/** 距离预设按钮的提示文案（2026-10-13 用户要求）。 */
const distPresetTitle = computed(() =>
  isZh.value
    ? '常用样品-探测器距离预设（mm）：WAXS ≈ 130，SAXS ≈ 2500；点击填入'
    : 'Common sample-detector distance presets (mm): WAXS ≈ 130, SAXS ≈ 2500; click to fill',
)

/** Summary label of the collapsed estimated-SD fold (2026-10-20 user request:
 *  预估 SD 默认收起). Shows the current guess so the fold is informative
 *  even while collapsed. 折叠区标题（2026-10-20 用户要求：预估 SD 默认收
 *  起）——标题带当前值，收起时也有信息量。 */
const sdGroupLabel = computed(() =>
  isZh.value
    ? `预估 SD（初始距离猜测，当前 ${Number.isFinite(props.modelValue.distGuessMm) ? props.modelValue.distGuessMm : '?'} mm）`
    : `Estimated SD (initial distance guess, now ${Number.isFinite(props.modelValue.distGuessMm) ? props.modelValue.distGuessMm : '?'} mm)`,
)

// ── Wavelength ↔ energy (REQ 波长和能量可以切换) ────────────────────────────
// λ(Å) · E(keV) = hc/e = 12.398419843320026 keV·Å. The form model keeps the
// canonical wavelengthA; this local unit flag only changes what the input
// shows (display derives from the model, so seed_from_poni patches and the
// toggle stay consistent without a second field).
// 表单模型始终保存波长（Å）；单位开关只改变输入框显示（显示值由模型换算，
// PONI 初始化与切换天然一致）。
const KEV_ANGSTROM = 12.398419843320026

const wlUnit = ref<'A' | 'keV'>('A')

const wlNumber = computed<number | null>(() => {
  const wl = props.modelValue.wavelengthA
  if (wlUnit.value === 'A') return wl
  if (!Number.isFinite(wl) || wl <= 0) return null
  return Number((KEV_ANGSTROM / wl).toPrecision(7))
})

function onWavelengthInput(value: number | null): void {
  if (value == null || !Number.isFinite(value) || value <= 0) return
  patch({ wavelengthA: wlUnit.value === 'A' ? value : KEV_ANGSTROM / value })
}

/** Nullable numeric input (mask bounds): empty field → null (bound off).
 *  可空数字输入（掩膜上下限）：空输入 → null（该界限关闭）。 */
function onNullableNumberInput(field: 'maskMin' | 'maskMax', value: number | null): void {
  patch({ [field]: value } as Partial<CalibSetupModel>)
}

const hasDetector = computed(() => props.modelValue.detector.trim().length > 0)

// Com-mode phases (default 'single'): 'beam' = the direct-beam image, where no
// calibrant exists yet; 'standard' = the second image whose branch the user
// picks. / com 模式阶段（默认 single）：beam = 直通光图（尚无标样）；standard
// = 第二张标样图（用户选择支路）。
const isBeamPhase = computed(() =>
  props.modelValue.mode === 'com' && (props.phase ?? 'single') === 'beam',
)
const isStandardPhase = computed(() =>
  props.modelValue.mode === 'com' && (props.phase ?? 'single') === 'standard',
)
const standardMode = computed(() => props.standardMode ?? 'calibrant')

/** Internal-standard branch is active (internal mode, or the com mode's
 *  internal branch) → no calibrant, no distance guess. / 内标支路激活（内标
 *  模式或 com 模式的内标支路）→ 无标样、无距离猜测。 */
const isInternal = computed(() =>
  props.modelValue.mode === 'internal'
  || (isStandardPhase.value && standardMode.value === 'internal'),
)

/** Show the calibrant selector only where a calibrant is actually consumed. */
const showCalibrant = computed(() => !isInternal.value && !isBeamPhase.value)

/** Distance guess is a CALIBRANT-mode input (internal uses the ring). */
const showSdGuess = computed(() => showCalibrant.value)

/** Calibrant source segment: 'builtin' (registry name) vs 'file' (.D) —
 *  mutually exclusive like the wizard mode switch; switching clears the
 *  other side so exactly one source can be active. / 标样来源分段：内置
 *  名称 vs 本地 .D，与模式开关同款互斥；切换即清空另一侧，任一时刻只有
 *  一个来源生效。 */
const calibrantSource = ref<'builtin' | 'file'>('builtin')

function setCalibrantSource(s: 'builtin' | 'file'): void {
  if (calibrantSource.value === s) return
  calibrantSource.value = s
  // Mutual exclusion: entering a side clears the other side's value.
  // 互斥：进入一侧即清空另一侧的值。
  patch(s === 'builtin' ? { calibrantPath: '' } : { calibrant: '' })
}

function onBuiltinSelect(e: Event): void {
  patch({ calibrant: (e.target as HTMLSelectElement).value, calibrantPath: '' })
}

/** Chosen .D file name for the hint (path may be long). / 回显用文件名。 */
const calibrantFileName = computed(() =>
  props.modelValue.calibrantPath.trim().split(/[/\\]/).pop() || props.modelValue.calibrantPath.trim(),
)

/** Cross-view link to the calibrant generator (makes a .D from a known
 *  standard). / 跳转校正标样生成器（由已知标样生成 .D 文件）。 */
function goGenerator(): void {
  void router.push('/workspace/cell-calibrant-generator')
}

/** External calibrantPath patches (e.g. the parent seeding state) auto-switch
 *  the segment to the file side; the reverse is unnecessary — clearing the
 *  path should not silently jump back to built-in.
 *  外部 patch 了 calibrantPath（如父组件回填）时自动切到本地文件分支；反向
 *  不需要——清空路径不应悄悄跳回内置标样。 */
watch(() => props.modelValue.calibrantPath, (p) => {
  if (p.trim() && calibrantSource.value !== 'file') calibrantSource.value = 'file'
})

/** Free-text built-in calibrant name: the SAME model field the <select> reads,
 *  so a typed registry name updates the select and a select change refills the
 *  text — one source of truth. Non-registry text is kept verbatim (the backend
 *  reports an unknown calibrant rather than the UI silently clamping it).
 *  内置标样自由文本：写的是 <select> 读的同一模型字段，输入注册名即更新
 *  select、select 变化即回填文本——单一数据源。非注册名的文本原样保留
 *  （由后端报未知标样，而非界面静默改写）。 */
function onCalibrantTextInput(e: Event): void {
  patch({ calibrant: (e.target as HTMLInputElement).value.trim() })
}

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
// Web 模式下按钮走浏览器选文件并上传，文案相应改为"上传"。 / Web: pick + upload.
const maskSelectLabel = computed(() => {
  if (!isDesktop) return isZh.value ? '上传掩膜' : 'Upload mask'
  return isZh.value ? '选择掩膜' : 'Select mask'
})
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
  // Branches without a calibrant (internal standard, and the com mode's
  // direct-beam image / internal branch) skip the calibrant requirement —
  // their geometry comes from one known ring or from the CoM centre.
  // 无标样支路（内标、com 模式的直通光图与内标支路）跳过标样必填——几何来自
  // 单个已知环或质心中心。
  if (showCalibrant.value && calibrantSource.value === 'builtin' && !m.calibrant) return false
  if (showCalibrant.value && calibrantSource.value === 'file' && !m.calibrantPath.trim()) return false
  if (!hasDetector.value && !(m.pixelSizeUm > 0)) return false
  if (!(m.wavelengthA > 0)) return false
  // The initial distance guess is a CALIBRANT-mode input (hidden in internal
  // mode, whose SD comes from ring_standard); the payload still carries the
  // form's current value, so the backend contract is unchanged.
  // 初始距离猜测是标样模式的输入（内标模式隐藏，其 SD 由 ring_standard
  // 算出）；载荷仍携带表单当前值，后端契约不变。
  if (showSdGuess.value && !(m.distGuessMm > 0)) return false
  return true
})

/** Report a failed pick/upload — cancel resolves null and never lands here.
 *  选文件/上传失败时提示；用户取消走 resolve(null)，不会进这里。 */
function reportPickFailure(title: string, error: unknown): void {
  const message = error instanceof Error ? error.message : String(error)
  toast.push({ title, message, tone: 'error' })
}

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
      // An explicit dialog pick is a deliberate (re)load request: bypass the
      // dedupe so re-picking the same path retries a previously failed load.
      // 对话框显式选图是明确的（重新）加载请求：绕过去重，使重复选择同一路径
      // 可以重试此前失败的加载。
      lastProbedPath = ''
      emitProbed(path)
    }
  } catch (error) {
    reportPickFailure(t('calibration.setup.uploadImage'), error)
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
    // Picking a file also clears the built-in name — mutual exclusion.
    // 选定文件同时清空内置名——保证互斥。
    if (path) patch({ calibrantPath: path, calibrant: '' })
  } catch (error) {
    reportPickFailure(t('calibration.setup.uploadCalibrant'), error)
  }
}

/** Mask file pick (.edf/.npy/.tif/.tiff) — REQ 1. Web mode uploads it. */
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
  } catch (error) {
    reportPickFailure(maskSelectLabel.value, error)
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
  } catch (error) {
    reportPickFailure(t('calibration.setup.seedFromPoni'), error)
  }
}

function submit(): void {
  if (!canSubmit.value) return
  const m = props.modelValue
  // Internal mode ALWAYS sends no calibrant (whatever the greyed-out inputs
  // still hold) — the backend opens an internal-standard session off that.
  // Otherwise the payload follows the selected source segment: exactly one of
  // name / .D file is sent. / 内标模式一律不下发标样（无论灰度输入框里残留
  // 什么）——后端据此建立内标会话；其余按来源分段二选一下发。
  // Branch-specific calibrant rule: only where a calibrant is consumed.
  // 分支相干的标样规则：仅在实际使用标样的支路下发。
  const internal = !showCalibrant.value
  emit('submit', {
    filePath: m.imagePath.trim(),
    calibrant: internal || calibrantSource.value === 'file' ? null : (m.calibrant || null),
    calibrantFile: internal || calibrantSource.value === 'builtin' ? null : (m.calibrantPath.trim() || null),
    detector: m.detector.trim() || null,
    pixelSizeUm: hasDetector.value ? null : m.pixelSizeUm,
    wavelengthA: m.wavelengthA,
    distGuessMm: m.distGuessMm,
    // Masks belong to the peak-picking phases (beam phase hides the inputs, so
    // nothing stale can leak into that session).
    // 掩膜属于寻峰阶段（直通光图阶段隐藏输入，不会把残留值带进该会话）。
    maskPath: isBeamPhase.value ? null : (m.maskPath.trim() || null),
    maskMin: isBeamPhase.value ? null : m.maskMin,
    maskMax: isBeamPhase.value ? null : m.maskMax,
    // Beam-centre seed (ring fit / manual / direct-beam CoM) — both null
    // unless set. / 束流中心种子（圆环拟合/手动/直通光质心）——未设置时皆 null。
    centerX: m.centerXPx,
    centerY: m.centerYPx,
    // com mode's SECOND setup → fixed-centre session (distance only).
    // com 模式第二次 setup → 固定中心会话（只优化距离）。
    ...(isStandardPhase.value ? { fixedCenter: true } : {}),
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

/* Full-width two-way mode switch / 通栏双向模式开关 */
.csf-mode-toggle {
  width: 100%;
}

.csf-mode-toggle .csf-unit-btn {
  flex: 1;
  padding: 6px 10px;
  font-family: inherit;
  font-size: 0.78rem;
}

/* Internal-standard mode: the calibrant block is irrelevant — greyed out.
   内标模式：标样区无关——整块灰度禁用。 */
.csf-field--disabled {
  opacity: 0.45;
  filter: grayscale(0.4);
}

.csf-field--disabled .csf-btn,
.csf-field--disabled .csf-input,
.csf-field--disabled .csf-select {
  cursor: not-allowed;
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

/* Full-width .D browse button / 通栏 .D 选文件按钮 */
.csf-btn--block {
  width: 100%;
}

/* Distance preset row (user request 2026-10-13). / 距离预设按钮行。 */
.csf-preset-row {
  display: flex;
  gap: 8px;
}

/* Collapsed-by-default fold for the estimated SD (2026-10-20 user request).
   预估 SD 折叠区（2026-10-20 用户要求，默认收起）。 */
.csf-details {
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 0;
}

.csf-details-summary {
  padding: 7px 10px;
  font-size: 0.82rem;
  font-weight: 500;
  color: var(--text-secondary);
  cursor: pointer;
  user-select: none;
}

.csf-details-summary:hover {
  background: var(--bg-hover);
}

.csf-field--inner {
  padding: 4px 10px 10px;
}

.csf-btn--sm {
  padding: 3px 10px;
  font-size: 0.78rem;
}

/* Inline link inside a hint line / 小字提示行内的行内链接 */
.csf-hint--link a {
  color: var(--primary);
  cursor: pointer;
  text-decoration: underline;
}
</style>
