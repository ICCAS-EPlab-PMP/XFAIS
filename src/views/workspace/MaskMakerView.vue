<template>
  <div class="mask-maker-view">
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
        :contrast="contrastValue"
        :placeholder="t('maskMaker.empty')"
        @shape-drawn="handleShapeDrawn"
      />
    </div>

    <!-- Right: Properties -->
    <MaskProperties
      :image-info="imageInfo"
      :mask-stats="maskStats"
      :image-loaded="imageLoaded"
      :contrast="contrastValue"
      @apply-threshold="handleApplyThreshold"
      @update:contrast="contrastValue = $event"
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
const contrastValue = ref(1)

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

    await loadImage(filePath)
  } catch (err) {
    toast.push({
      title: t('maskMaker.errors.openFailed'),
      message: (err as Error).message,
      tone: 'error',
    })
  }
}

async function loadImage(filePath: string): Promise<void> {
  const { taskId } = await transport.submitTask('mask_maker', {
    action: 'load_preview',
    filePath,
    frame: 0,
  })

  // Receive PNG image as binary data (desktop binary WebSocket frame).
  // 通过二进制数据通道接收 PNG 图像（桌面端二进制 WebSocket 帧）。
  transport.onTaskBinaryData(taskId, (payload) => {
    if (payload.data) {
      const blob = new Blob([payload.data], { type: payload.mime || 'image/png' })
      const url = URL.createObjectURL(blob)
      imageSrc.value = url

      const w = payload.width || 0
      const h = payload.height || 0
      imageWidth.value = w
      imageHeight.value = h

      if (w > 0 && h > 0) {
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

    // Initialize mask store if not yet done by binary handler
    // 如果二进制处理器尚未初始化 MaskStore，则在此初始化
    if (!store.value && w > 0 && h > 0) {
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
  } catch (err) {
    toast.push({
      title: t('maskMaker.errors.loadMaskFailed'),
      message: (err as Error).message,
      tone: 'error',
    })
  }
}

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
