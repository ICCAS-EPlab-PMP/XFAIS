<template>
  <div
    class="mask-maker-view"
    :class="{ 'mask-maker-view--drop': fileDrop.isDragging.value }"
    @dragenter="fileDrop.onDragEnter"
    @dragover="fileDrop.onDragOver"
    @dragleave="fileDrop.onDragLeave"
    @drop="fileDrop.onDrop"
  >
    <!-- Left: Toolbar -->
    <MaskToolbar
      :image-loaded="imageLoaded"
      :active-tool="activeTool"
      :mask-mode="maskMode"
      :can-undo="store?.canUndo() ?? false"
      :can-redo="store?.canRedo() ?? false"
      @open-image="openImage"
      @load-mask="loadMask"
      @export-mask="showExportDialog = true"
      @select-tool="activeTool = $event"
      @select-mode="maskMode = $event"
      @undo="handleUndo"
      @redo="handleRedo"
      @invert="handleInvert"
      @clear="handleClear"
    />

    <!-- Center: Canvas -->
    <div class="mc-center">
      <MaskCanvas
        ref="canvasRef"
        :image-src="imageSrc"
        :image-width="imageWidth"
        :image-height="imageHeight"
        :image-loaded="imageLoaded"
        :mask-data="store?.getMask() ?? null"
        :mask-version="maskVersion"
        :active-tool="activeTool"
        :mask-mode="maskMode"
        :placeholder="t('maskMaker.empty')"
        @shape-drawn="handleShapeDrawn"
      />
    </div>

    <!-- Right: Properties -->
      <MaskProperties
        :image-info="imageInfo"
        :mask-stats="maskStats"
        :image-loaded="imageLoaded"
        :colormap="colormap"
        :use-log="useLog"
        :clim-mode="climMode"
        :clim-min="climMin"
        :clim-max="climMax"
        @apply-threshold="handleApplyThreshold"
        @update:colormap="onDisplayChange('colormap', $event)"
      @update:use-log="onDisplayChange('useLog', $event)"
      @update:clim-mode="onDisplayChange('climMode', $event)"
      @update:clim-min="onDisplayChange('climMin', $event)"
      @update:clim-max="onDisplayChange('climMax', $event)"
    />

    <!-- Export dialog -->
    <MaskExportDialog
      :visible="showExportDialog"
      @close="showExportDialog = false"
      @export="handleExport"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onBeforeUnmount, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useTransport } from '@/lib/transport'
import { useToast } from '@/lib/toast'
import { matchesExtensions, useDropZone } from '@/lib/fileDrop'
import { MaskStore } from '@/lib/mask/mask-store'
import type {
  MaskTool,
  MaskMode,
  MaskImageInfo,
  MaskStats,
  MaskExportFormat,
  ThresholdMode,
  MaskBackendResponse,
  MaskLoadResponse,
  MaskExportResponse,
} from '@/types/mask'
import MaskCanvas from '@/components/mask/MaskCanvas.vue'
import MaskToolbar from '@/components/mask/MaskToolbar.vue'
import MaskProperties from '@/components/mask/MaskProperties.vue'
import MaskExportDialog from '@/components/mask/MaskExportDialog.vue'

const { t } = useI18n()
const transport = useTransport()
const toast = useToast()

// ── State ─────────────────────────────────────────────────────────────────────

const imageLoaded = ref(false)
const imageSrc = ref<string | null>(null)
const imageWidth = ref(0)
const imageHeight = ref(0)
const imageFilePath = ref('')
const imageFileName = ref('')
const imageFileType = ref('')
const imageStats = ref<{ min: number; max: number; std: number } | undefined>()

const activeTool = ref<MaskTool>('pan')
const maskMode = ref<MaskMode>('mask')
const store = ref<MaskStore | null>(null)
const showExportDialog = ref(false)
const canvasRef = ref<InstanceType<typeof MaskCanvas> | null>(null)

// Bump counter: each store mutation increments this so MaskCanvas can re-render overlay.
// Since store.getMask() returns the same Uint8Array reference, Vue's watch cannot detect
// in-place mutations. We use a monotonically increasing counter as a reactivity signal.
const maskVersion = ref(0)

// Display settings (colormap / log / clim) — mirrors the viewer. The backend
// `mask_maker` route reuses viewer_config's load/load_preview action, which
// honors render_settings via _build_render_settings, so no backend change is
// needed: changing these triggers a re-render with the new settings.
// 显示设置（色图/对数/clim）—— 镜像图像查看器。mask_maker 路由复用 viewer_config
// 的 load/load_preview action，后端通过 _build_render_settings 读取这些设置。
const colormap = ref('smooth_WAXS_foxtrot')
const useLog = ref(false)
const climMode = ref<'auto' | 'manual'>('auto')
const climMin = ref(0)
// Default upper bound follows int32 — detector data may exceed uint16.
// 默认上限按 int32 设置 —— 探测器数据可能超过 uint16 范围。
const climMax = ref(2147483647)
const autoContrast = ref<{ autoMin: number; autoMax: number; logMin: number; logMax: number } | null>(null)
const climInitialized = ref(false)

/** Update a display field, then re-render the preview if an image is loaded. */
type DisplayField = 'colormap' | 'useLog' | 'climMode' | 'climMin' | 'climMax'
function onDisplayChange(field: DisplayField, value: number | boolean | string): void {
  switch (field) {
    case 'colormap': colormap.value = String(value); break
    case 'useLog': useLog.value = Boolean(value); break
    case 'climMode': climMode.value = (value === 'manual' ? 'manual' : 'auto'); break
    case 'climMin': climMin.value = Number(value); break
    case 'climMax': climMax.value = Number(value); break
  }
  // Auto-mode syncs min/max from the backend's auto-contrast; in manual mode
  // we send the user's values verbatim.
  if (climMode.value === 'auto' && autoContrast.value) {
    climMin.value = useLog.value ? autoContrast.value.logMin : autoContrast.value.autoMin
    climMax.value = useLog.value ? autoContrast.value.logMax : autoContrast.value.autoMax
  }
  if (imageFilePath.value) {
    void loadImage(imageFilePath.value)
  }
}

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

// Computed
const imageInfo = computed<MaskImageInfo | null>(() => {
  if (!imageLoaded.value) return null
  return {
    filePath: imageFilePath.value,
    fileName: imageFileName.value,
    width: imageWidth.value,
    height: imageHeight.value,
    fileType: imageFileType.value,
    stats: imageStats.value,
  }
})

const maskStats = computed<MaskStats | null>(() => {
  if (!store.value) return null
  return store.value.getStats()
})

// ── Image loading ─────────────────────────────────────────────────────────────

async function openImage(): Promise<void> {
  try {
    const result = await transport.selectFiles({
      multiSelections: false,
      filters: [
        { name: 'Image files', extensions: ['edf', 'tif', 'tiff', 'h5', 'hdf5'] },
        { name: 'All files', extensions: ['*'] },
      ],
    })

    const filePath = Array.isArray(result) ? result[0] : result
    if (!filePath) return

    await openImagePath(filePath)
  } catch (err) {
    toast.push({
      title: t('maskMaker.errors.openFailed'),
      message: (err as Error).message,
      tone: 'error',
    })
  }
}

/** Open a specific image path (shared by toolbar button and drag & drop). */
async function openImagePath(filePath: string): Promise<void> {
  // Reset display caches for a fresh file so the new image's auto-contrast
  // seeds the manual clim values rather than reusing the previous file's.
  // 为新文件重置显示缓存，使新图像的自动对比度作为手动 clim 初值。
  climInitialized.value = false
  autoContrast.value = null

  await loadImage(filePath)
}

async function loadImage(filePath: string): Promise<void> {
  // When re-rendering the SAME file (display-settings change), preserve the
  // existing mask store instead of recreating it — otherwise adjusting the
  // colormap would silently wipe the user's mask.
  // 重新渲染同一文件（显示设置变化）时保留现有 mask store，否则调节色图会清空掩膜。
  const isRerender = imageLoaded.value && imageFilePath.value === filePath

  const { taskId } = await transport.submitTask('mask_maker', {
    action: 'load_preview',
    filePath,
    frame: 0,
    settings: buildRenderSettings(),
  })

  // Receive PNG image as binary data (desktop binary WebSocket frame).
  // 通过二进制数据通道接收 PNG 图像（桌面端二进制 WebSocket 帧）。
  transport.onTaskBinaryData(taskId, (payload) => {
    if (payload.data) {
      if (imageSrc.value?.startsWith('blob:')) URL.revokeObjectURL(imageSrc.value)
      const blob = new Blob([payload.data], { type: payload.mime || 'image/png' })
      const url = URL.createObjectURL(blob)
      imageSrc.value = url

      const w = payload.width || 0
      const h = payload.height || 0
      imageWidth.value = w
      imageHeight.value = h

      // Only (re)create the mask store on first load — preserve it on rerenders.
      // 仅在首次加载时创建 mask store，重渲染时保留。
      if (!isRerender && w > 0 && h > 0) {
        store.value = new MaskStore(h, w)
      }

      imageLoaded.value = true
    }
  })

  transport.onTaskResult(taskId, (payload) => {
    const data = payload.data as Record<string, unknown>

    // If the image was not set via binary data channel, fall back to base64.
    // Skip __binary_blob__ placeholders that indicate binary delivery.
    // 如果二进制通道未设置图像，回退到 base64；跳过二进制占位符。
    if (!imageSrc.value) {
      const previewB64 = data.previewB64
      const displayB64 = data.displayB64
      if (typeof previewB64 === 'string' && previewB64 !== '__binary_blob__') {
        imageSrc.value = `data:image/png;base64,${previewB64}`
      } else if (typeof displayB64 === 'string' && displayB64 !== '__binary_blob__') {
        imageSrc.value = `data:image/png;base64,${displayB64}`
      }
    }

    // Dimensions from result metadata (supplement binary payload dimensions).
    // 从结果元数据补充尺寸信息。
    const w = (data.width ?? data.origWidth ?? 0) as number
    const h = (data.height ?? data.origHeight ?? 0) as number
    if (w > 0 && imageWidth.value === 0) imageWidth.value = w
    if (h > 0 && imageHeight.value === 0) imageHeight.value = h

    // Extract file info
    const meta = (data.metadata ?? {}) as Record<string, unknown>
    imageFileType.value = (meta.fileType as string) ?? ''
    imageFilePath.value = filePath
    imageFileName.value = filePath.split(/[/\\]/).pop() ?? filePath

    // Stats
    const stats = data.stats as Record<string, number> | undefined
    if (stats) {
      imageStats.value = {
        min: stats.min,
        max: stats.max,
        std: stats.std,
      }
    }

    // Capture auto-contrast so the Display Settings panel can seed manual
    // values and keep auto-mode in sync. Mirrors ViewerView's applyFrameResult.
    // 捕获自动对比度，显示设置面板据此初始化手动值并保持 auto 模式同步。
    const contrast = data.contrast as { autoMin: number; autoMax: number; logMin: number; logMax: number } | undefined
    if (contrast) {
      autoContrast.value = contrast
      if (climMode.value === 'auto') {
        climMin.value = useLog.value ? contrast.logMin : contrast.autoMin
        climMax.value = useLog.value ? contrast.logMax : contrast.autoMax
      } else if (!climInitialized.value) {
        climMin.value = useLog.value ? contrast.logMin : contrast.autoMin
        climMax.value = useLog.value ? contrast.logMax : contrast.autoMax
        climInitialized.value = true
      }
    }

    // Initialize mask store if not yet done by binary handler (first load only).
    // 仅首次加载时初始化 MaskStore。
    if (!isRerender && !store.value && w > 0 && h > 0) {
      store.value = new MaskStore(h, w)
    }

    imageLoaded.value = true
  })

  transport.onTaskError(taskId, (err) => {
    toast.push({
      title: t('maskMaker.errors.loadFailed'),
      message: err.error,
      tone: 'error',
    })
  })
}

// ── Shape drawing ─────────────────────────────────────────────────────────────

async function handleShapeDrawn(payload: {
  shape_type: string
  params: Record<string, unknown>
}): Promise<void> {
  if (!store.value) return

  const { shape_type, params } = payload

  // Rectangle: execute directly in frontend
  if (shape_type === 'rectangle') {
    store.value.commit()
    store.value.fillRect(
      params.row as number,
      params.col as number,
      params.height as number,
      params.width as number,
      1,
      maskMode.value === 'mask'
    )
    maskVersion.value++
    return
  }

  // All other shapes: send to backend
  try {
    store.value.commit()

    const { taskId } = await transport.submitTask('mask_maker', {
      action: 'draw_shape',
      mask_data: store.value.getMaskBase64(),
      height: imageHeight.value,
      width: imageWidth.value,
      shape_type,
      params,
      level: 1,
      do_mask: maskMode.value === 'mask',
    })

    transport.onTaskResult(taskId, (result) => {
      const data = result.data as MaskBackendResponse
      if (data.mask_data) {
        const bytes = base64ToUint8Array(data.mask_data)
        store.value!.setMask(bytes)
        maskVersion.value++
      }
    })

    transport.onTaskError(taskId, (err) => {
      toast.push({
        title: t('maskMaker.errors.shapeFailed'),
        message: err.error,
        tone: 'error',
      })
    })
  } catch (err) {
    toast.push({
      title: t('maskMaker.errors.shapeFailed'),
      message: (err as Error).message,
      tone: 'error',
    })
  }
}

// ── Threshold ─────────────────────────────────────────────────────────────────

async function handleApplyThreshold(payload: {
  mode: ThresholdMode
  threshold?: number
  threshold_min?: number
  threshold_max?: number
}): Promise<void> {
  if (!store.value || !imageFilePath.value) return

  try {
    store.value.commit()

    const { taskId } = await transport.submitTask('mask_maker', {
      action: 'apply_threshold',
      mask_data: store.value.getMaskBase64(),
      height: imageHeight.value,
      width: imageWidth.value,
      filePath: imageFilePath.value,
      frame: 0,
      mode: payload.mode,
      threshold: payload.threshold,
      threshold_min: payload.threshold_min,
      threshold_max: payload.threshold_max,
      level: 1,
      do_mask: maskMode.value === 'mask',
    })

    transport.onTaskResult(taskId, (result) => {
      const data = result.data as MaskBackendResponse
      if (data.mask_data) {
        const bytes = base64ToUint8Array(data.mask_data)
        store.value!.setMask(bytes)
        maskVersion.value++
      }
    })

    transport.onTaskError(taskId, (err) => {
      toast.push({
        title: t('maskMaker.errors.thresholdFailed'),
        message: err.error,
        tone: 'error',
      })
    })
  } catch (err) {
    toast.push({
      title: t('maskMaker.errors.thresholdFailed'),
      message: (err as Error).message,
      tone: 'error',
    })
  }
}

// ── Edit operations ───────────────────────────────────────────────────────────

function handleUndo(): void {
  if (store.value?.undo()) {
    maskVersion.value++
  }
}

function handleRedo(): void {
  if (store.value?.redo()) {
    maskVersion.value++
  }
}

function handleInvert(): void {
  store.value?.commit()
  store.value?.invert()
  maskVersion.value++
}

function handleClear(): void {
  store.value?.commit()
  store.value?.clear()
  maskVersion.value++
}

// ── Load mask ─────────────────────────────────────────────────────────────────

async function loadMask(): Promise<void> {
  try {
    const result = await transport.selectFiles({
      multiSelections: false,
      filters: [
        { name: 'Mask files', extensions: ['edf', 'tif', 'tiff', 'npy', 'npz', 'msk'] },
        { name: 'All files', extensions: ['*'] },
      ],
    })

    const filePath = Array.isArray(result) ? result[0] : result
    if (!filePath) return

    await loadMaskPath(filePath)
  } catch (err) {
    toast.push({
      title: t('maskMaker.errors.loadMaskFailed'),
      message: (err as Error).message,
      tone: 'error',
    })
  }
}

/** Load a mask from a specific path (shared by toolbar button and drag & drop). */
async function loadMaskPath(filePath: string): Promise<void> {
  const { taskId } = await transport.submitTask('mask_maker', {
    action: 'load_mask',
    file_path: filePath,
  })

  transport.onTaskResult(taskId, (result) => {
    const data = result.data as MaskLoadResponse
    if (data.mask_data) {
      const bytes = base64ToUint8Array(data.mask_data)

      if (store.value) {
        store.value.loadMask(bytes, [data.shape[0], data.shape[1]])
      } else {
        store.value = new MaskStore(data.shape[0], data.shape[1])
        store.value.loadMask(bytes, [data.shape[0], data.shape[1]])
      }
      maskVersion.value++

      toast.push({
        title: t('maskMaker.messages.maskLoaded'),
        message: `${data.shape[0]} × ${data.shape[1]}`,
        tone: 'success',
      })
    }
  })

  transport.onTaskError(taskId, (err) => {
    toast.push({
      title: t('maskMaker.errors.loadMaskFailed'),
      message: err.error,
      tone: 'error',
    })
  })
}

// Drag & drop anywhere on the mask maker: mask-only formats (.npy/.npz/.msk)
// load as a mask; image formats open as the working image.
const MASK_ONLY_EXTENSIONS = ['npy', 'npz', 'msk']

const fileDrop = useDropZone({
  transport,
  extensions: ['edf', 'tif', 'tiff', 'h5', 'hdf5', ...MASK_ONLY_EXTENSIONS],
  onDrop(resolution) {
    const path = resolution.filePaths[0]
    if (!path) return
    if (matchesExtensions(path, MASK_ONLY_EXTENSIONS)) {
      loadMaskPath(path).catch((err: unknown) => {
        toast.push({
          title: t('maskMaker.errors.loadMaskFailed'),
          message: err instanceof Error ? err.message : String(err),
          tone: 'error',
        })
      })
      return
    }
      openImagePath(path).catch((err: unknown) => {
        toast.push({
          title: t('maskMaker.errors.openFailed'),
          message: err instanceof Error ? err.message : String(err),
          tone: 'error',
        })
      })
  },
})

// ── Export mask ───────────────────────────────────────────────────────────────

async function handleExport(payload: {
  format: MaskExportFormat
  savePath: string
}): Promise<void> {
  if (!store.value) return

  try {
    const { taskId } = await transport.submitTask('mask_maker', {
      action: 'export_mask',
      mask_data: store.value.getMaskBase64(),
      height: imageHeight.value,
      width: imageWidth.value,
      format: payload.format,
      save_path: payload.savePath,
    })

    transport.onTaskResult(taskId, (result) => {
      const data = result.data as MaskExportResponse
      showExportDialog.value = false
      toast.push({
        title: t('maskMaker.messages.exportSuccess'),
        message: data.path,
        tone: 'success',
      })
    })

    transport.onTaskError(taskId, (err) => {
      toast.push({
        title: t('maskMaker.errors.exportFailed'),
        message: err.error,
        tone: 'error',
      })
    })
  } catch (err) {
    toast.push({
      title: t('maskMaker.errors.exportFailed'),
      message: (err as Error).message,
      tone: 'error',
    })
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function base64ToUint8Array(b64: string): Uint8Array {
  const binary = atob(b64)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i)
  }
  return bytes
}
</script>

<style scoped>
.mask-maker-view {
  display: grid;
  grid-template-columns: 180px 1fr 220px;
  gap: 16px;
  height: calc(100vh - 200px);
  min-height: 500px;
}

/* Drop-target highlight / 拖放高亮 */
.mask-maker-view--drop {
  box-shadow: inset 0 0 0 3px var(--primary-light);
  border-radius: var(--radius-md);
}

.mc-center {
  min-width: 0;
  display: flex;
  flex-direction: column;
}

@media (max-width: 1100px) {
  .mask-maker-view {
    grid-template-columns: 1fr;
    grid-template-rows: auto 1fr auto;
    height: auto;
  }
}
</style>
