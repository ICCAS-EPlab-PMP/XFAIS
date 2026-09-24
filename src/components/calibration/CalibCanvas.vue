<template>
  <div class="calib-canvas" ref="containerRef">
    <div
      class="cc-viewport"
      ref="viewportRef"
      :class="{ 'cc-viewport--add': isInteractive }"
      @mousedown="onMouseDown"
      @mousemove="onMouseMove"
      @mouseup="onMouseUp"
      @mouseleave="onMouseUp"
      @dblclick="onDblClick"
      @contextmenu="onContextMenu"
    >
      <!-- Layer 1: Image / 图像层
           Explicit CSS size = ORIGINAL image dims: when the parent caps the
           rendered preview PNG (preview_scale < 1 for large frames), the
           smaller texture is stretched back to the full coordinate space so
           the overlay (original pixel coordinates) stays aligned.
           显式 CSS 尺寸 = 原始图像尺寸：父组件对大图限制预览 PNG 分辨率
           （preview_scale < 1）时，小纹理拉伸回全尺寸坐标系，叠加层（原始
           像素坐标）保持对齐。 -->
      <img
        v-if="imageSrc"
        :src="imageSrc"
        alt="Calibrant"
        class="cc-image"
        :style="layerStyle"
        draggable="false"
      />

      <!-- Layer 2: Overlay (rings + peaks), drawn in image pixel space / 叠加层（环 + 峰），图像像素坐标系 -->
      <canvas
        v-if="imageSrc && imageWidth > 0 && imageHeight > 0"
        ref="overlayCanvasRef"
        class="cc-overlay"
        :width="imageWidth"
        :height="imageHeight"
        :style="layerStyle"
      />

      <!-- Placeholder / 占位 -->
      <div v-if="!imageSrc" class="cc-placeholder">
        <span>{{ t('calibration.canvas.noImage') }}</span>
      </div>

      <!-- Pick-mode hint bar / 拾取模式提示条 -->
      <div v-if="isInteractive && imageSrc" class="cc-hint">
        {{ hintLabel }}
      </div>
    </div>

    <!-- Zoom controls / 缩放控制 -->
    <div v-if="imageSrc" class="cc-controls">
      <button class="cc-zoom-btn" title="Zoom in" @click="zoomIn">+</button>
      <span class="cc-zoom-level">{{ Math.round(zoom * 100) }}%</span>
      <button class="cc-zoom-btn" title="Zoom out" @click="zoomOut">−</button>
      <button class="cc-zoom-btn" title="Fit to view" @click="zoomFit">⊡</button>
      <button class="cc-zoom-btn" title="100%" @click="zoom100">1:1</button>
    </div>
  </div>
</template>

<script lang="ts">
/**
 * Shared peak-marker palette — STABLE color per ring index, deliberately
 * distinct from the ring-overlay hues (ringColor below). Exported so the
 * per-ring summary table (CalibPeakPanel) can show matching swatches.
 * 峰标记调色板——每个环号一种稳定颜色，刻意区别于理论环叠加色；导出供
 * 每环汇总表（CalibPeakPanel）显示同色色块。
 */
export function calibPeakRingColor(ring: number): string {
  return `hsl(${(ring * 47 + 205) % 360}, 95%, 62%)`
}
</script>

<script setup lang="ts">
/**
 * CalibCanvas.vue — 标定画布（三层：图像 + 叠加 + 交互）
 * Calibration canvas (three layers: image + overlay + interaction).
 *
 * Mirrors MaskCanvas's zoom/pan transform logic: the <img> and the overlay
 * <canvas> share the same CSS transform (translate + scale from origin 0,0),
 * so pan/zoom need no redraw — only stroke widths are zoom-compensated.
 * 叠加层与图像共用同一 CSS transform（平移 + 缩放），因此缩放平移无需重绘，
 * 仅线宽按缩放补偿。
 */
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'

/** A picked calibration peak. y = row, x = col (image pixel coordinates).
 *  ring is null until the backend assigns one (detect/pick return unassigned).
 *  dthetaDeg/suspect come from update_peaks' per-peak self-check (刷新环号/自检).
 *  标定峰。y=行，x=列；ring 在后端分配前为 null；dthetaDeg/suspect 为自检字段。 */
export interface CalibPeak {
  y: number
  x: number
  ring: number | null
  /** Signed deviation from the assigned theoretical ring (degrees). */
  dthetaDeg?: number | null
  /** True when the peak sits beyond the midpoint toward a neighbouring ring. */
  suspect?: boolean
}

/** A predicted ring polyline. points are [y, x] (row, col) pairs, consistent with CalibPeak. */
export interface CalibRing {
  ring: number
  points: number[][]
}

/** A ring-pick guide point (ring mode): y = row, x = col. */
export interface CalibRingGuidePoint {
  y: number
  x: number
}

/**
 * Fitted preview circle through the ring-guide points (Kåsa least squares,
 * computed by the parent). Drawn as a dashed circle. Includes the center —
 * a radius alone cannot place the circle.
 * 穿过环选引导点的拟合预览圆（父组件最小二乘拟合），含圆心与半径，虚线绘制。
 */
export interface CalibRingFit {
  cy: number
  cx: number
  radiusPx: number
}

/**
 * Coarse session-mask overlay (REQ 1): the setup action downsamples the
 * combined mask (file + intensity bounds + dead pixels) to ≤256×256 tiles;
 * grid[i * cols + j] === 1 marks a masked tile. Drawn as translucent red
 * squares in image pixel space, visible at every wizard step.
 * 会话掩膜粗网格叠加（REQ 1）：setup 把合并掩膜降采样为 ≤256×256 网格，
 * 1 = 该格含被屏蔽像素；按图像像素坐标画半透明红色方块，每一步都可见。
 */
export interface CalibMaskOverlay {
  rows: number
  cols: number
  grid: number[]
}

const { t, locale } = useI18n()

const props = withDefaults(defineProps<{
  imageSrc: string | null
  imageWidth: number
  imageHeight: number
  rings: CalibRing[]
  peaks: CalibPeak[]
  /**
   * REQ 2: canvas clicks ALWAYS collect ring-guide points — this is simply
   * "the peaks step is active". View-only otherwise.
   * 画布点击始终收集环引导点——即“峰拾取步骤激活”；其余步骤仅查看。
   */
  interactive?: boolean
  /** Ring-mode guide points — drawn as distinct markers. */
  ringGuide?: CalibRingGuidePoint[]
  /** Fitted circle through the guide points — dashed preview (null = none). */
  ringFit?: CalibRingFit | null
  /** Session mask coarse grid (null = no mask) — translucent red tiles. */
  maskOverlay?: CalibMaskOverlay | null
  /**
   * Refined beam center in image pixels (x = col = poni2/pixel2,
   * y = row = poni1/pixel1). Drawn as a distinct crosshair once a refine
   * has produced a geometry; moves with every subsequent refine.
   * 精修后的光束中心（图像像素）。精修产出几何后以醒目十字标出，随每次
   * 精修更新。
   */
  beamCenter?: { x: number; y: number } | null
}>(), {
  interactive: false,
  ringGuide: () => [],
  ringFit: null,
  maskOverlay: null,
  beamCenter: null,
})

const emit = defineEmits<{
  'canvas-click': [pixel: { row: number; col: number }]
  'canvas-remove': [pixel: { row: number; col: number }]
  /** Double-click finishes the current ring (guide clicks already landed). */
  'canvas-dblclick': [pixel: { row: number; col: number }]
}>()

/** Clicks collect guide points while interactive; otherwise view-only. */
const isInteractive = computed(() => props.interactive)

// Ring-guide hint has no i18n key yet — inline bilingual (see final report).
// 环选提示暂无 i18n 键 —— 内联双语（见最终报告缺失键清单）。
const hintLabel = computed(() =>
  locale.value.startsWith('zh')
    ? '在当前环上点击 ≥3 个引导点；双击 / 回车 / 完成本环收峰'
    : 'Click ≥3 guide points on the current ring; double-click / Enter / Finish harvests it',
)

// ── Refs ──────────────────────────────────────────────────────────────────────
const containerRef = ref<HTMLDivElement | null>(null)
const viewportRef = ref<HTMLDivElement | null>(null)
const overlayCanvasRef = ref<HTMLCanvasElement | null>(null)

// ── Zoom & pan state (mirrors MaskCanvas) ─────────────────────────────────────
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

/** Max screen-pixel travel before a press counts as a drag, not a click. */
const CLICK_SLOP_PX = 4

const transformStyle = computed(() => ({
  transform: `translate(${panX.value}px, ${panY.value}px) scale(${zoom.value})`,
  transformOrigin: '0 0',
}))

/** Transform PLUS explicit original-dims sizing (see the template note). */
const layerStyle = computed(() => ({
  ...transformStyle.value,
  width: `${props.imageWidth}px`,
  height: `${props.imageHeight}px`,
}))

// ── Coordinate conversion / 坐标转换 ─────────────────────────────────────────

/** Convert screen coordinates to image pixel coordinates (x = col, y = row). */
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
  // Registered non-passive in onMounted so preventDefault works (see MaskCanvas).
  e.preventDefault()
  if (!props.imageSrc) return

  const rect = viewportRef.value?.getBoundingClientRect()
  if (!rect) return

  const mouseX = e.clientX - rect.left
  const mouseY = e.clientY - rect.top

  // Zoom toward cursor
  const oldZoom = zoom.value
  const delta = e.deltaY > 0 ? 1 / ZOOM_STEP : ZOOM_STEP
  zoom.value = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, zoom.value * delta))

  const scaleChange = zoom.value / oldZoom
  panX.value = mouseX - scaleChange * (mouseX - panX.value)
  panY.value = mouseY - scaleChange * (mouseY - panY.value)
}

// ── Mouse events / 鼠标事件 ───────────────────────────────────────────────────

// Click-vs-drag discrimination / 点击与拖拽区分
const pressed = ref(false)
const pressedButton = ref(-1)
const pressStartX = ref(0)
const pressStartY = ref(0)
const pressMoved = ref(false)

function onMouseDown(e: MouseEvent): void {
  if (!props.imageSrc) return

  pressed.value = true
  pressedButton.value = e.button
  pressStartX.value = e.clientX
  pressStartY.value = e.clientY
  pressMoved.value = false

  // Pan with middle OR left drag: a stationary left press stays a click
  // (emitted on mouseup), so panning never blocks peak picking.
  // 中键或左键拖拽平移：左键按住不动仍是点击（mouseup 时发出），平移不挡拾取。
  if (e.button === 0 || e.button === 1) {
    isPanning.value = true
    panStartX.value = e.clientX
    panStartY.value = e.clientY
    panOriginX.value = panX.value
    panOriginY.value = panY.value
  }
}

function onMouseMove(e: MouseEvent): void {
  if (pressed.value) {
    const dx = e.clientX - pressStartX.value
    const dy = e.clientY - pressStartY.value
    if (Math.hypot(dx, dy) > CLICK_SLOP_PX) {
      pressMoved.value = true
    }
  }

  if (isPanning.value) {
    panX.value = panOriginX.value + (e.clientX - panStartX.value)
    panY.value = panOriginY.value + (e.clientY - panStartY.value)
  }
}

function onMouseUp(e: MouseEvent): void {
  if (isPanning.value && (e.button === 0 || e.button === 1)) {
    isPanning.value = false
  }

  if (e.type === 'mouseleave') {
    pressed.value = false
    return
  }

  if (e.button !== 0 || !pressed.value || pressedButton.value !== 0) return
  pressed.value = false

  // A real click (no drag) on the left button.
  if (pressMoved.value) return

  const pixel = screenToPixel(e.clientX, e.clientY)
  if (!pixel) return

  if (e.altKey) {
    // Alt-click removes the nearest peak / Alt 点击删除最近峰
    emit('canvas-remove', { row: pixel.y, col: pixel.x })
  } else if (isInteractive.value) {
    // REQ 2: clicks ALWAYS collect ring-guide points on the current ring.
    // 点击始终收集当前环的引导点。
    emit('canvas-click', { row: pixel.y, col: pixel.x })
  }
}

/** Double-click finishes the current ring (its two clicks already added points). */
function onDblClick(e: MouseEvent): void {
  if (!props.imageSrc || !props.interactive) return
  const pixel = screenToPixel(e.clientX, e.clientY)
  if (!pixel) return
  emit('canvas-dblclick', { row: pixel.y, col: pixel.x })
}

function onContextMenu(e: MouseEvent): void {
  // Right-click removes the nearest peak instead of opening the browser menu.
  // 右键删除最近峰，而非弹出浏览器菜单。
  e.preventDefault()
  if (!props.imageSrc) return
  const pixel = screenToPixel(e.clientX, e.clientY)
  if (!pixel) return
  emit('canvas-remove', { row: pixel.y, col: pixel.x })
}

// ── Overlay rendering / 叠加层渲染 ───────────────────────────────────────────

/** Distinct hue per ring index. / 每个环索引分配不同色相。 */
function ringColor(index: number): string {
  return `hsl(${(index * 57 + 15) % 360}, 90%, 62%)`
}

/**
 * Visible region in image pixel coordinates (viewport bounds inverse-transform).
 * Used to cull off-screen geometry while zoomed in (perf).
 * 视口在图像像素坐标系中的可见区域，放大时跳过屏外几何（性能优化）。
 */
function visibleBounds(): { x0: number; y0: number; x1: number; y1: number } {
  const viewport = viewportRef.value
  if (!viewport) {
    return { x0: -Infinity, y0: -Infinity, x1: Infinity, y1: Infinity }
  }
  const w = viewport.clientWidth
  const h = viewport.clientHeight
  return {
    x0: -panX.value / zoom.value,
    y0: -panY.value / zoom.value,
    x1: (w - panX.value) / zoom.value,
    y1: (h - panY.value) / zoom.value,
  }
}

function drawOverlay(): void {
  const canvas = overlayCanvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const w = canvas.width
  const h = canvas.height
  ctx.clearRect(0, 0, w, h)

  const { x0, y0, x1, y1 } = visibleBounds()
  // Margin so strokes near the viewport edge are not culled prematurely.
  const margin = 16 / zoom.value

  const lineW = Math.max(1.5 / zoom.value, 0.5)
  const arm = Math.max(5 / zoom.value, 1.5)

  // Session-mask overlay (REQ 1): translucent red tiles over masked regions,
  // drawn FIRST so rings/peaks/guides stay on top. Tiles live in image pixel
  // space (each tile spans imageWidth/cols × imageHeight/rows px) and ride the
  // same CSS transform as the image — visible at every step, zoom-compensated.
  // 会话掩膜叠加（REQ 1）：屏蔽区画半透明红色方块，最先绘制以保证环/峰/引导
  // 点在其上。方块位于图像像素坐标系（每格 imageWidth/cols × imageHeight/rows
  // 像素），与图像共用同一 CSS transform——每一步可见，线宽随缩放补偿。
  const mo = props.maskOverlay
  if (mo && mo.rows > 0 && mo.cols > 0 && mo.grid.length === mo.rows * mo.cols) {
    const tileH = h / mo.rows
    const tileW = w / mo.cols
    ctx.fillStyle = 'rgba(248, 113, 113, 0.28)'
    for (let r = 0; r < mo.rows; r++) {
      const ty = r * tileH
      if (ty > y1 + margin || ty + tileH < y0 - margin) continue
      for (let c = 0; c < mo.cols; c++) {
        if (mo.grid[r * mo.cols + c] !== 1) continue
        const tx = c * tileW
        if (tx > x1 + margin || tx + tileW < x0 - margin) continue
        ctx.fillRect(tx, ty, Math.ceil(tileW), Math.ceil(tileH))
      }
    }
  }

  // Ring polylines: one hue per ring index. points are [y, x] (row, col).
  // 环折线：每个环一种颜色。点为 [y, x]（行, 列）。
  props.rings.forEach((ring, idx) => {
    if (!ring.points || ring.points.length < 2) return
    ctx.strokeStyle = ringColor(idx)
    ctx.lineWidth = lineW
    ctx.beginPath()
    let started = false
    for (const pt of ring.points) {
      const y = pt[0]
      const x = pt[1]
      if (
        !Number.isFinite(x) || !Number.isFinite(y) ||
        x < x0 - margin || x > x1 + margin || y < y0 - margin || y > y1 + margin
      ) {
        // Outside the visible region (or a gap marker): break the polyline.
        // 屏外（或断点标记）：断开折线。
        started = false
        continue
      }
      if (!started) {
        ctx.moveTo(x, y)
        started = true
      } else {
        ctx.lineTo(x, y)
      }
    }
    ctx.stroke()
  })

  // Ring-pick guide: dashed preview circle fitted through the guide points,
  // then the guide points themselves as distinct filled markers.
  // 环选引导：穿过引导点的虚线拟合圆预览 + 引导点实心标记。
  if (props.ringFit) {
    const { cy, cx, radiusPx } = props.ringFit
    if (Number.isFinite(cx) && Number.isFinite(cy) && radiusPx > 0) {
      ctx.save()
      ctx.strokeStyle = '#22d3ee'
      ctx.lineWidth = lineW
      // Dash lengths in image px, compensated by zoom → constant on screen.
      ctx.setLineDash([7 / zoom.value, 5 / zoom.value])
      ctx.beginPath()
      ctx.arc(cx, cy, radiusPx, 0, Math.PI * 2)
      ctx.stroke()
      ctx.restore()
    }
  }
  const guideR = Math.max(4 / zoom.value, 1.2)
  props.ringGuide.forEach(p => {
    if (p.x < x0 - margin || p.x > x1 + margin || p.y < y0 - margin || p.y > y1 + margin) return
    ctx.beginPath()
    ctx.arc(p.x, p.y, guideR, 0, Math.PI * 2)
    ctx.fillStyle = '#22d3ee'
    ctx.fill()
    ctx.lineWidth = lineW
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.85)'
    ctx.stroke()
  })

  // Peak markers: colored BY RING (stable palette per ring index — calibPeakRingColor,
  // deliberately different from the overlay hues) with a light outline; unassigned
  // peaks stay amber. / 峰标记按环号着稳定颜色（与理论环叠加色区分），未分配者
  // 保持琥珀色。
  for (const peak of props.peaks) {
    const { x, y } = peak
    if (x < x0 - margin || x > x1 + margin || y < y0 - margin || y > y1 + margin) continue

    const color = peak.ring != null ? calibPeakRingColor(peak.ring) : '#fbbf24'

    // Outline pass then color pass, so peaks stay visible on any background.
    ctx.lineCap = 'round'
    for (const pass of [0, 1]) {
      ctx.strokeStyle = pass === 0 ? 'rgba(255, 255, 255, 0.85)' : color
      ctx.lineWidth = pass === 0 ? lineW * 2.6 : lineW * 1.4
      ctx.beginPath()
      ctx.moveTo(x - arm, y)
      ctx.lineTo(x + arm, y)
      ctx.moveTo(x, y - arm)
      ctx.lineTo(x, y + arm)
      ctx.stroke()
    }

    // Self-check flag (刷新环号/自检): suspect peaks get a warning halo so the
    // user sees WHICH points deviate from their assigned theoretical ring.
    // 自检标记：可疑峰加警示光环，直观显示偏离所分配理论环的点。
    if (peak.suspect) {
      ctx.beginPath()
      ctx.arc(x, y, arm * 1.9, 0, Math.PI * 2)
      ctx.strokeStyle = '#f87171'
      ctx.lineWidth = lineW * 1.6
      ctx.setLineDash([4 / zoom.value, 3 / zoom.value])
      ctx.stroke()
      ctx.setLineDash([])
    }
  }

  // Refined beam center (精修中心位点): a distinct magenta crosshair +
  // dashed circle at (poni2/pixel2, poni1/pixel1) — drawn LAST so it stays
  // on top of rings/peaks/mask. Updates with every refine (parent's
  // `beamCenter` prop). / 精修后的光束中心：醒目洋红十字 + 虚线圆，最后
  // 绘制保证叠在最上层；随每次精修更新（父组件 beamCenter 属性）。
  const bc = props.beamCenter
  if (bc && Number.isFinite(bc.x) && Number.isFinite(bc.y)) {
    if (bc.x >= x0 - margin && bc.x <= x1 + margin && bc.y >= y0 - margin && bc.y <= y1 + margin) {
      const bcArm = Math.max(14 / zoom.value, 4)
      ctx.lineCap = 'round'
      for (const pass of [0, 1]) {
        ctx.strokeStyle = pass === 0 ? 'rgba(255, 255, 255, 0.9)' : '#e879f9'
        ctx.lineWidth = pass === 0 ? lineW * 3.0 : lineW * 1.8
        ctx.beginPath()
        ctx.moveTo(bc.x - bcArm, bc.y)
        ctx.lineTo(bc.x + bcArm, bc.y)
        ctx.moveTo(bc.x, bc.y - bcArm)
        ctx.lineTo(bc.x, bc.y + bcArm)
        ctx.stroke()
      }
      ctx.beginPath()
      ctx.arc(bc.x, bc.y, bcArm * 0.62, 0, Math.PI * 2)
      ctx.strokeStyle = '#e879f9'
      ctx.lineWidth = lineW * 1.6
      ctx.setLineDash([5 / zoom.value, 4 / zoom.value])
      ctx.stroke()
      ctx.setLineDash([])
    }
  }
}

// Redraw when data or zoom changes (pan needs no redraw — CSS transform).
// 数据或缩放变化时重绘（平移由 CSS transform 处理，无需重绘）。
watch(
  () => [props.rings, props.peaks, props.ringGuide, props.ringFit, props.maskOverlay, props.beamCenter, props.imageWidth, props.imageHeight, zoom.value] as const,
  () => {
    nextTick(() => drawOverlay())
  },
  { deep: true }
)

// ── Lifecycle ─────────────────────────────────────────────────────────────────

onMounted(() => {
  viewportRef.value?.addEventListener('wheel', onWheel, { passive: false })
  nextTick(() => {
    zoomFit()
    drawOverlay()
  })
})

onBeforeUnmount(() => {
  viewportRef.value?.removeEventListener('wheel', onWheel)
})

// Reset zoom/pan when the image changes / 图像变化时重置缩放
watch(
  () => props.imageSrc,
  () => {
    zoom.value = 1
    panX.value = 0
    panY.value = 0
    nextTick(() => {
      zoomFit()
      drawOverlay()
    })
  }
)
</script>

<style scoped>
.calib-canvas {
  position: relative;
  width: 100%;
  height: 100%;
  background: #1a1a2e;
  border-radius: 16px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.cc-viewport {
  flex: 1;
  position: relative;
  overflow: hidden;
  cursor: grab;
  min-height: 300px;
}

.cc-viewport--add {
  cursor: crosshair;
}

.cc-viewport:active {
  cursor: grabbing;
}

.cc-viewport--add:active {
  cursor: crosshair;
}

.cc-image {
  position: absolute;
  top: 0;
  left: 0;
  image-rendering: pixelated;
}

.cc-overlay {
  position: absolute;
  top: 0;
  left: 0;
  pointer-events: none;
}

.cc-placeholder {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgba(255, 255, 255, 0.3);
  font-size: 1rem;
}

.cc-hint {
  position: absolute;
  bottom: 16px;
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
  white-space: nowrap;
}

/* Controls / 控制条 */
.cc-controls {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px;
  background: rgba(0, 0, 0, 0.6);
}

.cc-zoom-btn {
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

.cc-zoom-btn:hover {
  background: rgba(255, 255, 255, 0.2);
}

.cc-zoom-level {
  color: rgba(255, 255, 255, 0.7);
  font-size: 0.8rem;
  font-family: var(--font-mono);
  min-width: 50px;
  text-align: center;
}
</style>
