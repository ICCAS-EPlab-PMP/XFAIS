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

      <!-- Layer 3: Sketch preview — drawn in SCREEN space (viewport-sized
           canvas; renderPreview maps image→screen coords), so the dashed
           white outline keeps a constant 2-screen-px width and FULL opacity
           at any zoom. The previous image-space canvas stroked with
           lineWidth = 2/zoom: once zoom passed ~2x the width fell below one
           bitmap pixel and the rasterizer's sub-pixel coverage diluted the
           alpha, so the line faded the more you zoomed in (CSS upscaling
           cannot restore coverage that was never rasterized). Still the
           cheap per-mousemove layer; also carries the polygon rubber-band
           line to the cursor. / 勾勒预览层：改为屏幕空间绘制（视口尺寸
           画布；renderPreview 内做图像→屏幕坐标映射），白色虚线在任何
           缩放下都保持 2 屏幕像素宽、完全不透明。旧实现在图像空间用
           lineWidth = 2/zoom 描线：zoom 超过约 2 倍后线宽低于 1 个位图
           像素，光栅化亚像素覆盖率稀释 alpha——放大越多虚线越淡（CSS
           放大补不回从未栅格出的覆盖）。仍是每帧轻量重画的层；多边形
           “上一顶点→光标”实时跟随线也画在这里。 -->
      <canvas
        v-if="imageLoaded"
        ref="previewCanvasRef"
        class="mc-preview"
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
   * 'white' = opaque white (default), 'red' = translucent red, 'violet' =
   * 5%-opacity deep violet. / 掩膜叠加显示风格（共享偏好，见
   * src/lib/maskDisplay.ts）：'white' 纯白不透明（默认）、'red' 淡红半透明、
   * 'violet' 5% 透明度深紫。
   */
  maskStyle?: MaskDisplayStyle
}>(), {
  maskStyle: 'white',
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

// ── Screen-space preview layer sizing / 屏幕空间预览层的尺寸管理 ────────────
//
// The preview canvas is viewport-sized (NOT image-sized): its bitmap tracks
// the viewport client rect × devicePixelRatio so strokes stay crisp. Without
// DPR handling, strokes would render at 1x and blur on HiDPI displays.
// 预览画布是视口尺寸（而非图像尺寸）：位图跟随视口客户区 × 设备像素比，
// 描线才够锐利。不处理 DPR 的话，HiDPI 屏上描线会按 1x 渲染再被拉糊。
const previewDpr = ref(1)

/** (Re)size the preview bitmap to the current viewport; redraw if drawing. */
/** 把预览位图（重）定为当前视口尺寸；绘制中则顺带重画。 */
function resizePreviewCanvas(): void {
  const canvas = previewCanvasRef.value
  const viewport = viewportRef.value
  if (!canvas || !viewport) return
  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  previewDpr.value = dpr
  canvas.width = Math.max(1, Math.round(viewport.clientWidth * dpr))
  canvas.height = Math.max(1, Math.round(viewport.clientHeight * dpr))
  // Keep an in-progress sketch aligned after a mid-draw resize (e.g. window
  // resize during polygon). / 绘制中窗口变化后，勾勒仍贴合图像。
  if (drawing.value) renderPreview()
}

// Size the bitmap when the canvas mounts (imageLoaded turns true) — the
// canvas element itself carries no width/height bindings anymore.
// 画布挂载（imageLoaded 变 true）时定位图尺寸——画布元素上不再绑定
// width/height 属性。
watch(previewCanvasRef, (canvas) => {
  if (canvas) resizePreviewCanvas()
})

// Viewport resizes (window/layout) resize the bitmap via ResizeObserver.
// 视口尺寸变化（窗口/布局）经 ResizeObserver 同步位图。
let previewResizeObserver: ResizeObserver | null = null

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

/** Map image-space coords to preview-canvas CSS pixels (screen space). */
/** 图像空间坐标 → 预览画布 CSS 像素（屏幕空间）。 */
function imgToScreen(x: number, y: number): [number, number] {
  return [x * zoom.value + panX.value, y * zoom.value + panY.value]
}

function renderPreview(): void {
  // PREVIEW LAYER ONLY (Layer 3): clear + stroke, in SCREEN space. The mask
  // overlay (Layer 2) stays untouched here — it used to be fully rebuilt
  // (full-frame ImageData + putImageData) on EVERY mousemove, which lagged
  // badly on large detector frames. Screen-space drawing (see template
  // comment) is what keeps the outline opaque at any zoom.
  // 只操作预览层：清空+描线，且在屏幕空间进行。掩膜层不随鼠标移动整帧重建
  // （此前每次 mousemove 都全量 putImageData，大图严重卡顿）。屏幕空间绘制
  // （见模板注释）正是虚线在任何缩放下保持不透明的原因。
  const canvas = previewCanvasRef.value
  if (!canvas) return

  const ctx = canvas.getContext('2d')
  if (!ctx) return

  // Reset any dpr transform first so clearRect covers the FULL bitmap.
  // 先复位 dpr 变换，clearRect 才能覆盖整个位图。
  ctx.setTransform(1, 0, 0, 1, 0, 0)
  ctx.clearRect(0, 0, canvas.width, canvas.height)

  // Draw preview shape
  const ds = drawState.value
  if (!ds.active) return

  // Draw in CSS pixels; the dpr transform keeps strokes crisp on HiDPI.
  // 按 CSS 像素绘制；dpr 变换保证 HiDPI 屏上描线锐利。
  ctx.setTransform(previewDpr.value, 0, 0, previewDpr.value, 0, 0)

  ctx.save()
  // Pure white outline: the preview (dashed rectangle/disk/ellipse/polygon)
  // must stay readable on BOTH bright and dark image content — the previous
  // blue was invisible on bluish detector frames. Every shape in this switch
  // shares this one stroke style.
  // 纯白勾勒：绘制预览（矩形/圆/椭圆/多边形虚线）必须在亮暗两种图像内容上
  // 都可读——原先的蓝色在偏蓝的探测器图像上看不清。下方各形状共用这一笔刷。
  ctx.strokeStyle = '#FFFFFF'
  // Light-white region fill (2026-11-06 用户需求): while dragging, the region
  // under construction gets a translucent white fill so the selection extent
  // is obvious at a glance — consistent with the opaque white the committed
  // mask shows in the default display tier. Region shapes only; the pencil
  // line has no area.
  // 淡白色区域填充（2026-11-06 用户需求）：拖拽过程中以半透明白填充预览构建
  // 中的区域，选区范围一眼可见——与默认显示档提交后的纯白掩膜观感一致。
  // 仅对有面积的形状填充；铅笔线无区域。
  ctx.fillStyle = 'rgba(255, 255, 255, 0.25)'
  // Constant screen pixels — the crux of the fade fix. Never divide by zoom:
  // a sub-bitmap-pixel width gets its alpha diluted by rasterizer coverage
  // (0.1px line ≈ 10% opacity) and CSS upscaling cannot restore it.
  // 恒定屏幕像素——褪色修复的关键。绝不再除以 zoom：低于位图像素的线宽
  // 会被光栅化覆盖率稀释 alpha（0.1px 线 ≈ 10% 不透明度），CSS 放大补不回。
  ctx.lineWidth = 2
  ctx.setLineDash([6, 4])

  // Anchor points in screen space; radii/edges derive from them directly.
  // 锚点换算到屏幕空间；半径/边长直接由屏幕坐标导出。
  const [sx, sy] = imgToScreen(ds.startX, ds.startY)
  const [cx, cy] = imgToScreen(ds.currentX, ds.currentY)

  switch (props.activeTool) {
    case 'rectangle': {
      const x = Math.min(sx, cx)
      const y = Math.min(sy, cy)
      const w = Math.abs(cx - sx)
      const h = Math.abs(cy - sy)
      ctx.fillRect(x, y, w, h)
      ctx.strokeRect(x, y, w, h)
      break
    }
    case 'disk': {
      const radius = Math.hypot(cx - sx, cy - sy)
      ctx.beginPath()
      ctx.arc(sx, sy, radius, 0, 2 * Math.PI)
      ctx.fill()
      ctx.stroke()
      break
    }
    case 'ellipse': {
      const rx = Math.abs(cx - sx)
      const ry = Math.abs(cy - sy)
      ctx.beginPath()
      ctx.ellipse(sx, sy, rx, ry, 0, 0, 2 * Math.PI)
      ctx.fill()
      ctx.stroke()
      break
    }
    case 'polygon': {
      if (ds.polygonPoints.length > 0) {
        ctx.beginPath()
        // pts are [row, col] i.e. [y, x] — mapped to screen space.
        // 顶点为 [row, col] 即 [y, x]——换算到屏幕空间。
        let [vx, vy] = imgToScreen(ds.polygonPoints[0][1], ds.polygonPoints[0][0])
        ctx.moveTo(vx, vy)
        for (let i = 1; i < ds.polygonPoints.length; i++) {
          ;[vx, vy] = imgToScreen(ds.polygonPoints[i][1], ds.polygonPoints[i][0])
          ctx.lineTo(vx, vy)
        }
        // Line to current mouse position, then close back to the first vertex
        // so the filled region matches the tentative polygon.
        // 连到当前光标，再闭合回首顶点——填充区域即当前暂定多边形。
        ctx.lineTo(cx, cy)
        ctx.closePath()
        ctx.fill()
        ctx.stroke()
      }
      break
    }
    case 'line': {
      ctx.beginPath()
      ctx.moveTo(sx, sy)
      ctx.lineTo(cx, cy)
      ctx.stroke()
      break
    }
  }

  ctx.restore()
}

// Zoom/pan changes move the image under the screen-space sketch (e.g.
// wheel-zoom while a polygon is in progress): the image→screen mapping
// changed, so re-render to keep the outline glued to the image.
// 缩放/平移改变了图像在屏幕上的位置（如多边形绘制中滚轮缩放）：图像→屏幕
// 映射已变，必须重画使勾勒贴合图像。
watch([zoom, panX, panY], () => {
  if (drawing.value) renderPreview()
})

function clearPreview(): void {
  // Preview layer only — the mask layer beneath keeps its last full render.
  // 仅清预览层——下方掩膜层保持上次整帧渲染结果。
  const canvas = previewCanvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  ctx.setTransform(1, 0, 0, 1, 0, 0)
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
  // opacity: red 0.28→71, white opaque→255, violet 0.05→13. White is again
  // the default tier (2026-11-06), matching the exported-mask convention.
  // 与标定渲染条共用的三档显示风格（见 src/lib/maskDisplay.ts）。alpha 为各档
  // 不透明度的 0–255 量化：红 0.28→71、白不透明→255、紫 0.05→13。默认档
  // 自 2026-11-06 起改回纯白，与导出掩膜的白色惯例一致。
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
  // 以 non-passive 方式注册滚轮监听，使 preventDefault 生效且不触发警告。
  viewportRef.value?.addEventListener('wheel', onWheel, { passive: false })
  // Track viewport resizes for the screen-space preview bitmap (see
  // resizePreviewCanvas). / 跟踪视口尺寸变化，同步屏幕空间预览位图。
  if (typeof ResizeObserver !== 'undefined' && viewportRef.value) {
    previewResizeObserver = new ResizeObserver(() => resizePreviewCanvas())
    previewResizeObserver.observe(viewportRef.value)
  }
  nextTick(() => {
    zoomFit()
  })
})

onBeforeUnmount(() => {
  viewportRef.value?.removeEventListener('wheel', onWheel)
  previewResizeObserver?.disconnect()
  previewResizeObserver = null
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

/* Screen-space preview layer: viewport-sized bitmap (dims set in
   resizePreviewCanvas), stretched by CSS to fill the viewport. Unlike
   .mc-overlay it carries NO zoom/pan transform — renderPreview maps
   image→screen coordinates itself. / 屏幕空间预览层：位图尺寸在
   resizePreviewCanvas 中设定，CSS 拉伸填满视口。与 .mc-overlay 不同，
   它不带任何缩放/平移变换——图像→屏幕坐标映射由 renderPreview 完成。 */
.mc-preview {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
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
