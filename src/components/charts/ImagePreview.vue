<template>
  <div class="image-preview" ref="containerRef" :data-testid="testIds.imagePreview">
    <div
      class="ip-viewport"
      ref="viewportRef"
      @wheel.prevent="onWheel"
      @mousedown="onMouseDown"
    >
      <img
        v-if="imageB64"
        :src="resolvedSrc"
        :alt="title"
        class="ip-image"
        :style="imageStyle"
        draggable="false"
        @click="onImageClick"
      />
      <!-- Canvas fallback for raw imageData array / 原始 imageData 数组的画布回退 -->
      <canvas
        v-else-if="imageData"
        ref="imageDataCanvasRef"
        class="ip-image"
        :style="imageStyle"
      />
      <div v-else class="ip-placeholder">
        <span>{{ placeholder }}</span>
      </div>

      <!-- Overlay canvas for beam center, sector boundaries / 叠加画布：光束中心、扇区边界 -->
      <canvas
        v-if="(imageB64 || imageData) && overlays.length"
        ref="overlayCanvasRef"
        class="ip-overlay"
        :width="overlayCanvasWidth"
        :height="overlayCanvasHeight"
        :style="imageStyle"
      />

      <div v-if="(imageB64 || imageData) && showColorbar" class="ip-colorbar">
        <div class="ip-colorbar__panel">
          <span class="ip-colorbar__label ip-colorbar__label--top">{{ colorbarMaxLabel }}</span>
          <div class="ip-colorbar__bar-area">
            <div class="ip-colorbar__gradient" :style="{ background: colorbarGradient }"></div>
            <span class="ip-colorbar__tick ip-colorbar__tick--75"></span>
            <span class="ip-colorbar__tick ip-colorbar__tick--50"></span>
            <span class="ip-colorbar__tick ip-colorbar__tick--25"></span>
          </div>
          <span class="ip-colorbar__label ip-colorbar__label--bottom">{{ colorbarMinLabel }}</span>
        </div>
      </div>
    </div>

    <!-- Zoom controls / 缩放控件 -->
    <div class="ip-controls" v-if="imageB64">
      <button class="ip-zoom-btn" @click="zoomIn" title="Zoom in">+</button>
      <span class="ip-zoom-level">{{ Math.round(zoom * 100) }}%</span>
      <button class="ip-zoom-btn" @click="zoomOut" title="Zoom out">−</button>
      <button class="ip-zoom-btn" @click="zoomFit" title="Fit to view">⊡</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { testIds } from '@/lib/testIds'

// --- Overlay types (exported for other views) / 叠加类型（导出供其他视图使用） ---

export interface BeamCenterOverlay {
  type: 'beamCenter'
  x: number
  y: number
}

export interface SectorBoundaryOverlay {
  type: 'sectorBoundary'
  angles: number[]
  centerX: number
  centerY: number
  radius?: number
}

export type Overlay = BeamCenterOverlay | SectorBoundaryOverlay

// --- Props ---

const props = withDefaults(defineProps<{
  imageB64?: string | null
  imageData?: (number | null)[][]
  overlays?: Overlay[]
  showColorbar?: boolean
  colorbarGradient?: string
  colorbarMinLabel?: string
  colorbarMaxLabel?: string
  renderMin?: number
  renderMax?: number
  useLogScale?: boolean
  title?: string
  placeholder?: string
  maxZoom?: number
}>(), {
  imageB64: null,
  imageData: undefined,
  overlays: () => [],
  showColorbar: false,
  colorbarGradient: 'linear-gradient(180deg, #fde725 0%, #5ec962 35%, #21918c 65%, #3b528b 82%, #440154 100%)',
  colorbarMinLabel: '0',
  colorbarMaxLabel: '1',
  renderMin: undefined,
  renderMax: undefined,
  useLogScale: false,
  title: '',
  placeholder: 'No image loaded',
  maxZoom: 5,
})

// --- Emits ---

const emit = defineEmits<{
  'image:click': [event: { x: number; y: number; pixelX: number; pixelY: number }]
}>()

// --- Refs ---

const containerRef = ref<HTMLDivElement | null>(null)
const viewportRef = ref<HTMLDivElement | null>(null)
const overlayCanvasRef = ref<HTMLCanvasElement | null>(null)
const imageDataCanvasRef = ref<HTMLCanvasElement | null>(null)

// Zoom & pan state / 缩放和平移状态
const zoom = ref(1)
const panX = ref(0)
const panY = ref(0)

// Drag state / 拖拽状态
let isDragging = false
let dragStartX = 0
let dragStartY = 0
let panStartX = 0
let panStartY = 0

// Natural image dimensions (read from loaded img) / 图片原始尺寸
const naturalWidth = ref(0)
const naturalHeight = ref(0)

// ImageData dimensions derived from the array / 从数组获取的图像尺寸
const imageDataWidth = computed(() => props.imageData?.length ? props.imageData[0]?.length ?? 0 : 0)
const imageDataHeight = computed(() => props.imageData?.length ?? 0)

// --- Computed ---

const imageStyle = computed(() => ({
  transform: `translate(${panX.value}px, ${panY.value}px) scale(${zoom.value})`,
  transformOrigin: 'top left' as const,
}))

const resolvedSrc = computed(() => {
  if (!props.imageB64) return ''
  if (props.imageB64.startsWith('blob:')) return props.imageB64
  if (props.imageB64.startsWith('data:')) return props.imageB64
  return 'data:image/png;base64,' + props.imageB64
})

const overlayCanvasWidth = computed(() => naturalWidth.value || imageDataWidth.value)
const overlayCanvasHeight = computed(() => naturalHeight.value || imageDataHeight.value)
// Whether we have a valid image to display / 是否有有效图像显示
const hasImage = computed(() => !!(props.imageB64 || props.imageData))

// --- Zoom helpers ---

const ZOOM_STEP = 0.25
const ZOOM_MIN = 0.25

function clampZoom(z: number): number {
  return Math.min(Math.max(z, ZOOM_MIN), props.maxZoom)
}

function zoomIn() {
  zoom.value = clampZoom(zoom.value + ZOOM_STEP)
}

function zoomOut() {
  zoom.value = clampZoom(zoom.value - ZOOM_STEP)
}

function zoomFit() {
  const vp = viewportRef.value
  if (!vp || !naturalWidth.value) return
  const scaleX = (vp.clientWidth - 4) / naturalWidth.value
  const scaleY = (vp.clientHeight - 4) / naturalHeight.value
  zoom.value = clampZoom(Math.min(scaleX, scaleY, 1))
  panX.value = Math.max((vp.clientWidth - naturalWidth.value * zoom.value) / 2, 0)
  panY.value = Math.max((vp.clientHeight - naturalHeight.value * zoom.value) / 2, 0)
}

// --- Wheel zoom centered on cursor / 滚轮缩放（以光标为中心） ---

function onWheel(e: WheelEvent) {
  const vp = viewportRef.value
  if (!vp) return

  const rect = vp.getBoundingClientRect()
  // Mouse position relative to viewport
  const mx = e.clientX - rect.left
  const my = e.clientY - rect.top

  const oldZoom = zoom.value
  const delta = e.deltaY > 0 ? -ZOOM_STEP : ZOOM_STEP
  const newZoom = clampZoom(oldZoom + delta)
  if (newZoom === oldZoom) return

  // Adjust pan so zoom centers on cursor position
  const ratio = newZoom / oldZoom
  panX.value = mx - ratio * (mx - panX.value)
  panY.value = my - ratio * (my - panY.value)
  zoom.value = newZoom
}

// --- Mouse drag to pan / 鼠标拖拽平移 ---

function onMouseDown(e: MouseEvent) {
  // Only left button
  if (e.button !== 0) return
  isDragging = true
  dragStartX = e.clientX
  dragStartY = e.clientY
  panStartX = panX.value
  panStartY = panY.value

  const vp = viewportRef.value
  if (vp) vp.style.cursor = 'grabbing'

  window.addEventListener('mousemove', onMouseMove)
  window.addEventListener('mouseup', onMouseUp)
}

function onMouseMove(e: MouseEvent) {
  if (!isDragging) return
  panX.value = panStartX + (e.clientX - dragStartX)
  panY.value = panStartY + (e.clientY - dragStartY)
}

function onMouseUp() {
  isDragging = false
  const vp = viewportRef.value
  if (vp) vp.style.cursor = ''
  window.removeEventListener('mousemove', onMouseMove)
  window.removeEventListener('mouseup', onMouseUp)
}

// --- Image click → pixel coordinates / 图片点击 → 像素坐标 ---

function onImageClick(e: MouseEvent) {
  if (isDragging) return
  const img = e.currentTarget as HTMLImageElement
  const rect = img.getBoundingClientRect()

  // Click position relative to the displayed image element
  const relX = e.clientX - rect.left
  const relY = e.clientY - rect.top

  // Displayed size of the image element
  const displayW = rect.width
  const displayH = rect.height

  // Map to natural pixel coordinates
  const pixelX = Math.round((relX / displayW) * naturalWidth.value)
  const pixelY = Math.round((relY / displayH) * naturalHeight.value)

  emit('image:click', {
    x: e.clientX,
    y: e.clientY,
    pixelX,
    pixelY,
  })
}

// --- Image load: capture natural dimensions / 图片加载：获取原始尺寸 ---

function captureImageSize() {
  if (!viewportRef.value) return
  const img = viewportRef.value.querySelector('.ip-image') as HTMLImageElement | null
  if (!img) return
  naturalWidth.value = img.naturalWidth
  naturalHeight.value = img.naturalHeight
}

// --- Overlay canvas rendering / 叠加画布渲染 ---

let rafId = 0

function drawOverlays() {
  const canvas = overlayCanvasRef.value
  if (!canvas || !naturalWidth.value) return

  const ctx = canvas.getContext('2d')
  if (!ctx) return

  // Canvas dimensions are set by :width/:height bindings
  ctx.clearRect(0, 0, canvas.width, canvas.height)

  for (const overlay of props.overlays) {
    if (overlay.type === 'beamCenter') {
      const cx = overlay.x
      const cy = overlay.y
      const arm = 16

      // Cross-hair with white outline for visibility / 带白色描边的十字准线
      ctx.lineCap = 'round'
      const draw = (color: string, width: number) => {
        ctx.strokeStyle = color
        ctx.lineWidth = Math.max(1, width)
        ctx.beginPath()
        ctx.moveTo(cx - arm, cy)
        ctx.lineTo(cx + arm, cy)
        ctx.moveTo(cx, cy - arm)
        ctx.lineTo(cx, cy + arm)
        ctx.stroke()
      }
      // White outline / 白色外描边
      draw('#ffffff', 4)
      // Red core / 红色核心
      draw('#ef4444', 2)
    }

    if (overlay.type === 'sectorBoundary') {
      const cx = overlay.centerX
      const cy = overlay.centerY
      const r = overlay.radius ?? Math.max(naturalWidth.value, naturalHeight.value)

      ctx.strokeStyle = '#1e40af'
      ctx.lineWidth = 2.5
      ctx.setLineDash([6, 4])

      for (const angleDeg of overlay.angles) {
        const rad = (angleDeg * Math.PI) / 180
        ctx.beginPath()
        ctx.moveTo(cx, cy)
        ctx.lineTo(cx + r * Math.cos(rad), cy - r * Math.sin(rad))
        ctx.stroke()
      }

      ctx.setLineDash([])
    }
  }
}

function scheduleOverlayRedraw() {
  cancelAnimationFrame(rafId)
  rafId = requestAnimationFrame(drawOverlays)
}

// Redraw overlays when zoom/pan/overlays change
watch([zoom, panX, panY, () => props.overlays], scheduleOverlayRedraw)

// --- ImageData canvas rendering / imageData 画布渲染 ---

function renderImageData() {
  const canvas = imageDataCanvasRef.value
  const data = props.imageData
  if (!canvas || !data || data.length === 0) return

  const rows = data.length
  const cols = data[0]?.length ?? 0
  if (cols === 0 || rows === 0) return

  // Set canvas resolution to match image data / 设置画布分辨率以匹配图像数据
  canvas.width = cols
  canvas.height = rows

  // Fit image to display (like zoomFit for regular images) / 适应显示（与常规图像的 zoomFit 相同）
  naturalWidth.value = cols
  naturalHeight.value = rows

  const ctx = canvas.getContext('2d')
  if (!ctx) return

  // Create ImageData from 2D array / 从 2D 数组创建 ImageData
  const imageDataObj = ctx.createImageData(cols, rows)
  const pixels = imageDataObj.data

  // Find min/max for normalization / 查找 min/max 用于归一化
  let minVal = Infinity
  let maxVal = -Infinity
  for (let r = 0; r < rows; r++) {
    const row = data[r]
    if (!row) continue
    for (let c = 0; c < cols; c++) {
      const val = row[c]
      if (val !== null && val !== undefined) {
        if (val < minVal) minVal = val
        if (val > maxVal) maxVal = val
      }
    }
  }

  let renderMin = Number.isFinite(props.renderMin) ? props.renderMin as number : minVal
  let renderMax = Number.isFinite(props.renderMax) ? props.renderMax as number : maxVal

  if (!Number.isFinite(renderMin)) renderMin = minVal
  if (!Number.isFinite(renderMax)) renderMax = maxVal
  if (renderMax <= renderMin) {
    renderMin = minVal
    renderMax = maxVal
  }

  const range = renderMax - renderMin

  // Fill pixels / 填充像素
  for (let r = 0; r < rows; r++) {
    const row = data[r]
    if (!row) continue
    for (let c = 0; c < cols; c++) {
      const val = row[c]
      const idx = (r * cols + c) * 4

      if (val === null || val === undefined || range === 0) {
        // Transparent for null values / null 值透明
        pixels[idx] = 0
        pixels[idx + 1] = 0
        pixels[idx + 2] = 0
        pixels[idx + 3] = 0
      } else {
        let mapped = val
        let lo = renderMin
        let hi = renderMax

        if (props.useLogScale) {
          const safeVal = Math.max(val, 1e-12)
          const safeLo = Math.max(renderMin, 1e-12)
          const safeHi = Math.max(renderMax, safeLo * 1.000001)
          mapped = Math.log10(safeVal)
          lo = Math.log10(safeLo)
          hi = Math.log10(safeHi)
        }

        const normalized = Math.max(0, Math.min(255, Math.round(((mapped - lo) / Math.max(hi - lo, 1e-12)) * 255)))
        pixels[idx] = normalized
        pixels[idx + 1] = normalized
        pixels[idx + 2] = normalized
        pixels[idx + 3] = 255
      }
    }
  }

  ctx.putImageData(imageDataObj, 0, 0)

  // Fit to viewport after render / 渲染后适应视口
  nextTick(() => zoomFit())
}

// Watch for imageData changes / 监听 imageData 变化
watch(() => [props.imageData, props.renderMin, props.renderMax, props.useLogScale], renderImageData, { immediate: true })

// --- Lifecycle ---

onMounted(() => {
  // Wait for image to load, then capture dimensions & fit
  nextTick(() => {
    const img = viewportRef.value?.querySelector('.ip-image') as HTMLImageElement | null
    if (img) {
      if (img.complete) {
        captureImageSize()
        zoomFit()
      } else {
        img.addEventListener('load', () => {
          captureImageSize()
          zoomFit()
        }, { once: true })
      }
    }
  })
})

watch(resolvedSrc, () => {
  nextTick(() => {
    const img = viewportRef.value?.querySelector('.ip-image') as HTMLImageElement | null
    if (!img) return
    if (img.complete) {
      captureImageSize()
      zoomFit()
    } else {
      img.addEventListener('load', () => {
        captureImageSize()
        zoomFit()
      }, { once: true })
    }
  })
})

onBeforeUnmount(() => {
  window.removeEventListener('mousemove', onMouseMove)
  window.removeEventListener('mouseup', onMouseUp)
  cancelAnimationFrame(rafId)
})
</script>

<style scoped>
.image-preview {
  position: relative;
  overflow: hidden;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
}

.ip-viewport {
  position: relative;
  width: 100%;
  height: clamp(320px, 62vh, 720px);
  overflow: hidden;
  cursor: grab;
}

.ip-image {
  display: block;
  max-width: none;
  image-rendering: pixelated;
  /* Disable default img drag */
  user-select: none;
  -webkit-user-drag: none;
}

.ip-overlay {
  position: absolute;
  top: 0;
  left: 0;
  pointer-events: none;
}

.ip-colorbar {
  position: absolute;
  top: 12px;
  right: 8px;
  bottom: 32px;
  width: 72px;
  display: flex;
  align-items: stretch;
  z-index: 4;
  pointer-events: none;
}

.ip-colorbar__panel {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  width: 100%;
  padding: 8px 6px;
  background: rgba(15, 23, 42, 0.72);
  border-radius: 6px;
  backdrop-filter: blur(6px);
}

.ip-colorbar__bar-area {
  flex: 1;
  position: relative;
  width: 100%;
  display: flex;
  justify-content: center;
}

.ip-colorbar__gradient {
  width: 22px;
  height: 100%;
  border-radius: 4px;
  border: 1px solid rgba(148, 163, 184, 0.35);
  box-shadow: 0 4px 14px rgba(15, 23, 42, 0.35);
}

.ip-colorbar__tick {
  position: absolute;
  left: 4px;
  right: 4px;
  height: 1px;
  background: rgba(255, 255, 255, 0.35);
}

.ip-colorbar__tick--75 {
  top: 25%;
}

.ip-colorbar__tick--50 {
  top: 50%;
}

.ip-colorbar__tick--25 {
  top: 75%;
}

.ip-colorbar__label {
  color: rgba(226, 232, 240, 0.95);
  font-size: 0.68rem;
  font-family: var(--font-mono);
  text-align: center;
  white-space: nowrap;
  line-height: 1.2;
  padding: 2px 4px;
  background: rgba(15, 23, 42, 0.5);
  border-radius: 3px;
}

.ip-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  min-height: 200px;
  color: var(--text-muted);
  font-size: 0.875rem;
}

.ip-controls {
  position: absolute;
  bottom: 8px;
  right: 8px;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 6px;
  background: rgba(15, 23, 42, 0.72);
  border-radius: 6px;
  backdrop-filter: blur(6px);
  z-index: 10;
}

.ip-zoom-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: none;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.12);
  color: #e2e8f0;
  font-size: 1rem;
  font-weight: 600;
  line-height: 1;
  cursor: pointer;
  transition: background var(--transition-fast);
}

.ip-zoom-btn:hover {
  background: rgba(255, 255, 255, 0.24);
}

.ip-zoom-level {
  min-width: 42px;
  text-align: center;
  font-size: 0.75rem;
  color: #cbd5e1;
  font-family: var(--font-mono);
  user-select: none;
}
</style>
