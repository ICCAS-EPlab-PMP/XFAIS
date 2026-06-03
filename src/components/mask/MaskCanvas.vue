<template>
  <div class="mask-canvas" ref="containerRef">
    <div
      class="mc-viewport"
      ref="viewportRef"
      @wheel.prevent="onWheel"
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

      <!-- Layer 2: Mask overlay (semi-transparent) -->
      <canvas
        v-if="imageLoaded"
        ref="overlayCanvasRef"
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

const { t } = useI18n()

const props = defineProps<{
  imageSrc: string | null
  imageWidth: number
  imageHeight: number
  imageLoaded: boolean
  maskData: Uint8Array | null
  maskVersion: number
  activeTool: MaskTool
  maskMode: MaskMode
  contrast?: number
  placeholder?: string
}>()

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
  filter: `contrast(${props.contrast ?? 1})`,
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
  if (props.activeTool === 'polygon') return // Polygon vertices added on click

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
  const canvas = overlayCanvasRef.value
  if (!canvas || !props.maskData) return

  const ctx = canvas.getContext('2d')
  if (!ctx) return

  // Redraw mask overlay first
  renderMaskOverlay(ctx, canvas.width, canvas.height)

  // Draw preview shape
  const ds = drawState.value
  if (!ds.active) return

  ctx.save()
  ctx.strokeStyle = '#3B82F6'
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
  const canvas = overlayCanvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  renderMaskOverlay(ctx, canvas.width, canvas.height)
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

  for (let i = 0; i < props.maskData.length; i++) {
    const idx = i * 4
    if (props.maskData[i] !== 0) {
      // Masked pixel: semi-transparent white overlay
      pixels[idx] = 255     // R
      pixels[idx + 1] = 255 // G
      pixels[idx + 2] = 255 // B
      pixels[idx + 3] = 140 // A
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

// ── Lifecycle ─────────────────────────────────────────────────────────────────

onMounted(() => {
  nextTick(() => {
    zoomFit()
  })
})

// Reset zoom/pan when image changes
watch(
  () => props.imageSrc,
  () => {
    zoom.value = 1
    panX.value = 0
    panY.value = 0
    drawing.value = false
    nextTick(() => zoomFit())
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
