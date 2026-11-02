<template>
  <div class="mask-canvas" ref="containerRef">
    <div
      class="mc-viewport"
      ref="viewportRef"
      @mousedown="onMouseDown"
      @mousemove="onMouseMove"
      @mouseup="onMouseUp"
      @mouseleave="onMouseUp"
      @dblclick="onDblClick"
    >
      <!-- Layer 1: Image -->
      <img
        v-if="imageSrc"
        :src="imageSrc"
        alt="Image"
        class="mc-image"
        :style="imageStyle"
        draggable="false"
      />

      <!-- Layer 2: Mask overlay — redrawn ONLY when the mask data or display
           style changes (full-frame ImageData pass; doing this per mousemove
           made large-detector drawing laggy). / 掩膜层：仅在掩膜数据或显示
           风格变化时整帧重画（此前每次鼠标移动都全量重画大图导致卡顿）。 -->
      <canvas
        v-if="imageLoaded"
        ref="overlayCanvasRef"
        class="mc-overlay"
        :width="imageWidth"
        :height="imageHeight"
        :style="transformStyle"
      />

      <!-- Layer 3: Sketch preview — the cheap per-mousemove layer (clear +
           stroke only), so dragging feels instant. Also carries the polygon
           rubber-band line to the cursor. / 勾勒预览层：每帧只清空+描线，
           代价极小；多边形“上一顶点→光标”的实时跟随线也画在这里。 -->
      <canvas
        v-if="imageLoaded"
        ref="previewCanvasRef"
        class="mc-overlay"
        :width="imageWidth"
        :height="imageHeight"
        :style="transformStyle"
      />

      <!-- Placeholder -->
      <div v-if="!imageLoaded" class="mc-placeholder">
        <span>{{ placeholder }}</span>
      </div>
    </div>

    <!-- Zoom controls -->
    <div class="mc-controls" v-if="imageLoaded">
      <button class="mc-zoom-btn" @click="zoomIn" title="Zoom in">+</button>
      <span class="mc-zoom-level">{{ Math.round(zoom * 100) }}%</span>
      <button class="mc-zoom-btn" @click="zoomOut" title="Zoom out">−</button>
      <button class="mc-zoom-btn" @click="zoomFit" title="Fit to view">⊡</button>
      <button class="mc-zoom-btn" @click="zoom100" title="100%">1:1</button>
    </div>

    <!-- Polygon instruction bar -->
    <div v-if="activeTool === 'polygon' && drawing" class="mc-polygon-hint">
      {{ t('maskMaker.canvas.polygonHint') }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import type { MaskTool, MaskMode, DrawState } from '@/types/mask'
import type { MaskDisplayStyle } from '@/lib/maskDisplay'

const { t } = useI18n()

const props = withDefaults(defineProps<{
  imageSrc: string | null
  imageWidth: number
  imageHeight: number
  imageLoaded: boolean
  maskData: Uint8Array | null
  maskVersion: number
  activeTool: MaskTool
  maskMode: MaskMode
  placeholder?: string
  /**
   * Mask overlay display style (shared preference, see src/lib/maskDisplay.ts).
   * 'red' = translucent red (default), 'white' = opaque white, 'violet' =
   * 5%-opacity deep violet. / 掩膜叠加显示风格（共享偏好，见
   * src/lib/maskDisplay.ts）：'red' 淡红半透明（默认）、'white' 纯白不透明、
   * 'violet' 5% 透明度深紫。
   */
  maskStyle?: MaskDisplayStyle
}>(), {
  maskStyle: 'red',
})

const emit = defineEmits<{
  'shape-drawn': [params: {
    shape_type: string
    params: Record<string, unknown>
  }]
  'pixel-click': [x: number, y: number]
}>()

// ── Refs ──────────────────────────────────────────────────────────────────────
const containerRef = ref<HTMLDivElement | null>(null)
const viewportRef = ref<HTMLDivElement | null>(null)
const overlayCanvasRef = ref<HTMLCanvasElement | null>(null)
/**
 * Layer-3 sketch canvas (see template): the per-mousemove preview lives here
 * so the heavy mask-overlay layer never repaints during drawing.
 * 勾勒预览层画布（见模板）：高频预览画在这层，绘制期间不再触碰重型掩膜层。
 */
const previewCanvasRef = ref<HTMLCanvasElement | null>(null)

// ── Zoom & Pan state ──────────────────────────────────────────────────────────
const zoom = ref(1)
const panX = ref(0)
const panY = ref(0)
const isPanning = ref(false)
const panStartX = ref(0)
const panStartY = ref(0)
const panOriginX = ref(0)
const panOriginY = ref(0)

const MIN_ZOOM = 0.05
const MAX_ZOOM = 20
const ZOOM_STEP = 1.15

// ── Drawing state ─────────────────────────────────────────────────────────────
const drawing = ref(false)
const drawState = ref<DrawState>({
  active: false,
  startX: 0,
  startY: 0,
  currentX: 0,
  currentY: 0,
  polygonPoints: [],
})

const transformStyle = computed(() => ({
  transform: `translate(${panX.value}px, ${panY.value}px) scale(${zoom.value})`,
  transformOrigin: '0 0',
}))

const imageStyle = computed(() => ({
  transform: `translate(${panX.value}px, ${panY.value}px) scale(${zoom.value})`,
  transformOrigin: '0 0',
}))

// ── Coordinate conversion ─────────────────────────────────────────────────────

/** Convert screen (page) coordinates to pixel coordinates in image space. */
function screenToPixel(clientX: number, clientY: number): { x: number; y: number } | null {
  const viewport = viewportRef.value
  if (!viewport) return null

  const rect = viewport.getBoundingClientRect()
  const screenX = clientX - rect.left
  const screenY = clientY - rect.top

  // Invert CSS transform: subtract pan, divide by zoom
  const px = (screenX - panX.value) / zoom.value
  const py = (screenY - panY.value) / zoom.value

  return {
    x: Math.round(px),
    y: Math.round(py),
  }
}

// ── Zoom ──────────────────────────────────────────────────────────────────────

function zoomIn(): void {
  zoom.value = Math.min(MAX_ZOOM, zoom.value * ZOOM_STEP)
}

function zoomOut(): void {
  zoom.value = Math.max(MIN_ZOOM, zoom.value / ZOOM_STEP)
}

function zoomFit(): void {
  const container = containerRef.value
  if (!container || !props.imageWidth || !props.imageHeight) return

  const cw = container.clientWidth - 40
  const ch = container.clientHeight - 40
  const scaleX = cw / props.imageWidth
  const scaleY = ch / props.imageHeight
  zoom.value = Math.min(scaleX, scaleY, 1)
  panX.value = (cw - props.imageWidth * zoom.value) / 2
  panY.value = (ch - props.imageHeight * zoom.value) / 2
}

function zoom100(): void {
  zoom.value = 1
  panX.value = 0
  panY.value = 0
}

function onWheel(e: WheelEvent): void {
  // Prevent page scroll while zooming; registered as a non-passive listener
  // in onMounted so we can call preventDefault without Chromium warnings.
  // 缩放时阻止页面滚动；监听器在 onMounted 中以 non-passive 方式注册，
  // 因此可以调用 preventDefault 而不触发 Chromium 警告。
  e.preventDefault()
  if (!props.imageLoaded) return

  const rect = viewportRef.value?.getBoundingClientRect()
  if (!rect) return

  const mouseX = e.clientX - rect.left
  const mouseY = e.clientY - rect.top

  // Zoom toward cursor
  const oldZoom = zoom.value
  const delta = e.deltaY > 0 ? 1 / ZOOM_STEP : ZOOM_STEP
  zoom.value = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, zoom.value * delta))

  // Adjust pan so the point under cursor stays fixed
  const scaleChange = zoom.value / oldZoom
  panX.value = mouseX - scaleChange * (mouseX - panX.value)
  panY.value = mouseY - scaleChange * (mouseY - panY.value)
}

// ── Mouse events ──────────────────────────────────────────────────────────────

function onMouseDown(e: MouseEvent): void {
  if (!props.imageLoaded) return

  if (props.activeTool === 'pan' || e.button === 1) {
    // Start panning
    isPanning.value = true
    panStartX.value = e.clientX
    panStartY.value = e.clientY
    panOriginX.value = panX.value
    panOriginY.value = panY.value
    return
  }

  const pixel = screenToPixel(e.clientX, e.clientY)
  if (!pixel) return

  if (e.button !== 0) return // Only left-click for drawing

  if (props.activeTool === 'polygon') {
    // For polygon, accumulate vertices
    if (!drawing.value) {
      // First click: start polygon
      drawing.value = true
      drawState.value = {
        active: true,
        startX: pixel.x,
        startY: pixel.y,
        currentX: pixel.x,
        currentY: pixel.y,
        polygonPoints: [[pixel.y, pixel.x]],
      }
    } else {
      // Subsequent clicks: add vertex
      drawState.value.polygonPoints.push([pixel.y, pixel.x])
      drawState.value.currentX = pixel.x
      drawState.value.currentY = pixel.y
    }
    renderPreview()
  } else {
    // Start drawing for other shapes
    drawing.value = true
    drawState.value = {
      active: true,
      startX: pixel.x,
      startY: pixel.y,
      currentX: pixel.x,
      currentY: pixel.y,
      polygonPoints: [],
    }
  }

  // Rectangle: execute immediately in frontend (handled in MaskMakerView via events)
  // Other shapes: track drawing for preview, emit on mouseup
}

function onMouseMove(e: MouseEvent): void {
  if (isPanning.value) {
    panX.value = panOriginX.value + (e.clientX - panStartX.value)
    panY.value = panOriginY.value + (e.clientY - panStartY.value)
    return
  }

  if (!drawing.value) return
  // Polygon vertices are added on CLICK, but the mousemove still matters:
  // it drives the rubber-band line from the last vertex to the cursor (the
  // preview layer redraw is cheap). The old early-return here froze that
  // line at the last click — the "no live connector" regression.
  // 多边形顶点仍在点击时添加，但鼠标移动必须放行：预览层的
  // “上一顶点→光标”跟随线靠它实时更新（预览层重绘代价极小）。
  // 此处旧版的提前 return 正是跟随线冻结丢失的根因。

  const pixel = screenToPixel(e.clientX, e.clientY)
  if (!pixel) return

  drawState.value.currentX = pixel.x
  drawState.value.currentY = pixel.y
  renderPreview()
}

function onMouseUp(e: MouseEvent): void {
  if (isPanning.value) {
    isPanning.value = false
    return
  }

  if (!drawing.value) return

  if (props.activeTool === 'rectangle') {
    // Rectangle: emit immediately from mouse position data
    const ds = drawState.value
    const x1 = Math.min(ds.startX, ds.currentX)
    const y1 = Math.min(ds.startY, ds.currentY)
    const w = Math.abs(ds.currentX - ds.startX)
    const h = Math.abs(ds.currentY - ds.startY)
    if (w > 0 && h > 0) {
      emit('shape-drawn', {
        shape_type: 'rectangle',
        params: { row: y1, col: x1, height: h, width: w },
      })
    }
  } else if (props.activeTool !== 'polygon') {
    // Disk, ellipse, line: emit on mouse up
    const ds = drawState.value
    emitShapeFromDrawState()
  }

  if (props.activeTool !== 'polygon') {
    drawing.value = false
    drawState.value.active = false
    clearPreview()
  }
}

function onDblClick(): void {
  if (props.activeTool === 'polygon' && drawing.value && drawState.value.polygonPoints.length >= 3) {
    // Finish polygon
    emit('shape-drawn', {
      shape_type: 'polygon',
      params: { vertices: drawState.value.polygonPoints.map(([r, c]) => [r, c]) },
    })
    drawing.value = false
    drawState.value.active = false
    drawState.value.polygonPoints = []
    clearPreview()
  }
}

function emitShapeFromDrawState(): void {
  const ds = drawState.value
  const startX = ds.startX
  const startY = ds.startY
  const endX = ds.currentX
  const endY = ds.currentY

  switch (props.activeTool) {
    case 'disk': {
      const radius = Math.sqrt((endX - startX) ** 2 + (endY - startY) ** 2)
      if (radius > 0) {
        emit('shape-drawn', {
          shape_type: 'disk',
          params: { crow: startY, ccol: startX, radius },
        })
      }
      break
    }
    case 'ellipse': {
      const radiusC = Math.abs(endX - startX)
      const radiusR = Math.abs(endY - startY)
      if (radiusR > 0 && radiusC > 0) {
        emit('shape-drawn', {
          shape_type: 'ellipse',
          params: { crow: startY, ccol: startX, radius_r: radiusR, radius_c: radiusC },
        })
      }
      break
    }
    case 'line': {
      if (startX !== endX || startY !== endY) {
        emit('shape-drawn', {
          shape_type: 'line',
          params: { row0: startY, col0: startX, row1: endY, col1: endX, width: 1 },
        })
      }
      break
    }
  }
}

// ── Preview rendering (dashed outlines during drawing) ────────────────────────

function renderPreview(): void {
  // PREVIEW LAYER ONLY (Layer 3): clear + stroke. The mask overlay (Layer 2)
  // stays untouched here — it used to be fully rebuilt (full-frame ImageData
  // + putImageData) on EVERY mousemove, which lagged badly on large detector
  // frames. / 只操作预览层：清空+描线。掩膜层不再随鼠标移动整帧重建
  // （此前每次 mousemove 都全量 putImageData，大图严重卡顿）。
  const canvas = previewCanvasRef.value
  if (!canvas || !props.maskData) return

  const ctx = canvas.getContext('2d')
  if (!ctx) return

  ctx.clearRect(0, 0, canvas.width, canvas.height)

  // Draw preview shape
  const ds = drawState.value
  if (!ds.active) return

  ctx.save()
  // Pure white outline: the preview (dashed rectangle/disk/ellipse/polygon)
  // must stay readable on BOTH bright and dark image content — the previous
  // blue was invisible on bluish detector frames. Every shape in this switch
  // shares this one stroke style.
  // 纯白勾勒：绘制预览（矩形/圆/椭圆/多边形虚线）必须在亮暗两种图像内容上
  // 都可读——原先的蓝色在偏蓝的探测器图像上看不清。下方各形状共用这一笔刷。
  ctx.strokeStyle = '#FFFFFF'
  ctx.lineWidth = 2 / zoom.value
  ctx.setLineDash([6 / zoom.value, 4 / zoom.value])

  const dx = ds.currentX - ds.startX
  const dy = ds.currentY - ds.startY

  switch (props.activeTool) {
    case 'rectangle': {
      const x = Math.min(ds.startX, ds.currentX)
      const y = Math.min(ds.startY, ds.currentY)
      const w = Math.abs(dx)
      const h = Math.abs(dy)
      ctx.strokeRect(x, y, w, h)
      break
    }
    case 'disk': {
      const radius = Math.sqrt(dx * dx + dy * dy)
      ctx.beginPath()
      ctx.arc(ds.startX, ds.startY, radius, 0, 2 * Math.PI)
      ctx.stroke()
      break
    }
    case 'ellipse': {
      const rx = Math.abs(dx)
      const ry = Math.abs(dy)
      ctx.beginPath()
      ctx.ellipse(ds.startX, ds.startY, rx, ry, 0, 0, 2 * Math.PI)
      ctx.stroke()
      break
    }
    case 'polygon': {
      if (ds.polygonPoints.length > 0) {
        ctx.beginPath()
        // pts are [row, col] i.e. [y, x]
        ctx.moveTo(ds.polygonPoints[0][1], ds.polygonPoints[0][0])
        for (let i = 1; i < ds.polygonPoints.length; i++) {
          ctx.lineTo(ds.polygonPoints[i][1], ds.polygonPoints[i][0])
        }
        // Line to current mouse position
        ctx.lineTo(ds.currentX, ds.currentY)
        ctx.stroke()
      }
      break
    }
    case 'line': {
      ctx.beginPath()
      ctx.moveTo(ds.startX, ds.startY)
      ctx.lineTo(ds.currentX, ds.currentY)
      ctx.stroke()
      break
    }
  }

  ctx.restore()
}

function clearPreview(): void {
  // Preview layer only — the mask layer beneath keeps its last full render.
  // 仅清预览层——下方掩膜层保持上次整帧渲染结果。
  const canvas = previewCanvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  ctx.clearRect(0, 0, canvas.width, canvas.height)
}

// ── Mask overlay rendering ────────────────────────────────────────────────────

function renderMaskOverlay(ctx: CanvasRenderingContext2D, w: number, h: number): void {
  if (!props.maskData || props.maskData.length !== w * h) {
    ctx.clearRect(0, 0, w, h)
    return
  }

  // Create ImageData for mask overlay
  const imageData = ctx.createImageData(w, h)
  const pixels = imageData.data

  // Three-tier display style shared with the calibration render bar (see
  // src/lib/maskDisplay.ts). Alpha is the 0–255 quantization of the tier's
  // opacity: red 0.28→71, white opaque→255, violet 0.05→13. The old constant
  // was white at A=140 — 'red' being the default tier now intentionally
  // unifies the pixel-level mask with the calibration coarse grid.
  // 与标定渲染条共用的三档显示风格（见 src/lib/maskDisplay.ts）。alpha 为各档
  // 不透明度的 0–255 量化：红 0.28→71、白不透明→255、紫 0.05→13。旧实现是
  // A=140 的白色——默认档改红后，像素级掩膜与标定粗网格有意统一。
  let mr: number, mg: number, mb: number, ma: number
  switch (props.maskStyle) {
    case 'white':
      mr = 255; mg = 255; mb = 255; ma = 255
      break
    case 'violet':
      mr = 76; mg = 29; mb = 149; ma = 13
      break
    case 'red':
    default:
      mr = 248; mg = 113; mb = 113; ma = 71
      break
  }

  for (let i = 0; i < props.maskData.length; i++) {
    const idx = i * 4
    if (props.maskData[i] !== 0) {
      // Masked pixel: overlay tinted by the selected display tier
      // 掩膜像素：按所选显示档着色
      pixels[idx] = mr      // R
      pixels[idx + 1] = mg  // G
      pixels[idx + 2] = mb  // B
      pixels[idx + 3] = ma  // A
    } else {
      // Unmasked: fully transparent
      pixels[idx + 3] = 0
    }
  }

  ctx.putImageData(imageData, 0, 0)
}

// ── Watch mask data changes to redraw overlay ─────────────────────────────────

watch(
  () => props.maskVersion,
  () => {
    const canvas = overlayCanvasRef.value
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    renderMaskOverlay(ctx, canvas.width, canvas.height)
  }
)

// Redraw when the shared display style changes (switched from either view —
// the preference is a module-level ref, see src/lib/maskDisplay.ts).
// 显示风格变化时重绘（可从任一视图切换——偏好为模块级 ref，见
// src/lib/maskDisplay.ts）。
watch(
  () => props.maskStyle,
  () => {
    const canvas = overlayCanvasRef.value
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    renderMaskOverlay(ctx, canvas.width, canvas.height)
  }
)

// ── Lifecycle ─────────────────────────────────────────────────────────────────

onMounted(() => {
  // Register wheel listener as non-passive so preventDefault works without
  // triggering Chromium "[Violation] Added non-passive event listener" warnings.
  // 以 non-passive 方式注册滚轮监听器，使 preventDefault 生效且不触发警告。
  viewportRef.value?.addEventListener('wheel', onWheel, { passive: false })
  nextTick(() => {
    zoomFit()
  })
})

onBeforeUnmount(() => {
  viewportRef.value?.removeEventListener('wheel', onWheel)
})

// Reset zoom/pan when image changes
watch(
  () => props.imageSrc,
  () => {
    zoom.value = 1
    panX.value = 0
    panY.value = 0
    drawing.value = false
    nextTick(() => {
      zoomFit()
      // The v-if canvases are re-created on image change — repaint the mask
      // layer once (the view bumps maskVersion when it supplies maskData)
      // and start the preview layer clean.
      // 换图时 v-if 画布会重建——掩膜层补画一次，预览层清空起步。
      const canvas = overlayCanvasRef.value
      const ctx = canvas?.getContext('2d')
      if (canvas && ctx) renderMaskOverlay(ctx, canvas.width, canvas.height)
      clearPreview()
    })
  }
)
</script>

<style scoped>
.mask-canvas {
  position: relative;
  width: 100%;
  height: 100%;
  background: #1a1a2e;
  border-radius: 16px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.mc-viewport {
  flex: 1;
  position: relative;
  overflow: hidden;
  cursor: crosshair;
  min-height: 300px;
}

.mc-image {
  position: absolute;
  top: 0;
  left: 0;
  image-rendering: pixelated;
}

.mc-overlay {
  position: absolute;
  top: 0;
  left: 0;
  pointer-events: none;
}

.mc-placeholder {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgba(255, 255, 255, 0.3);
  font-size: 1rem;
}

/* Controls */
.mc-controls {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px;
  background: rgba(0, 0, 0, 0.6);
}

.mc-zoom-btn {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.1);
  color: #fff;
  font-size: 1rem;
  font-weight: 700;
  cursor: pointer;
  transition: background 0.15s ease;
}

.mc-zoom-btn:hover {
  background: rgba(255, 255, 255, 0.2);
}

.mc-zoom-level {
  color: rgba(255, 255, 255, 0.7);
  font-size: 0.8rem;
  font-family: var(--font-mono);
  min-width: 50px;
  text-align: center;
}

.mc-polygon-hint {
  position: absolute;
  bottom: 50px;
  left: 50%;
  transform: translateX(-50%);
  padding: 6px 16px;
  border-radius: 999px;
  background: rgba(59, 130, 246, 0.9);
  color: #fff;
  font-size: 0.8rem;
  font-weight: 600;
  pointer-events: none;
  z-index: 10;
}
</style>
