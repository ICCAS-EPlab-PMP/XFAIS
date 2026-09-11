<template>
  <div class="image-preview" ref="containerRef" :data-testid="testIds.imagePreview">
    <div
      class="ip-viewport"
      ref="viewportRef"
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
  /** Crosshair color (CSS). Defaults to red; pass e.g. '#eab308' for yellow. / 十字准线颜色（CSS）。默认红色；如 '#eab308' 为黄色。 */
  color?: string
}

export interface SectorBoundaryOverlay {
  type: 'sectorBoundary'
  angles: number[]
  centerX: number
  centerY: number
  radius?: number
}

export interface SectorMaskOverlay {
  type: 'sectorMask'
  /** pyFAI chi angles (degrees) bounding the SELECTED wedge [start, end]:
   *  the sweep from start to end in increasing chi stays clear; everything
   *  else is shaded gray. / 选中扇区的 pyFAI chi 角（度）[起, 止]：从起到止
   *  递增扫过的区域保持透明，其余区域罩灰色蒙版。 */
  angles: [number, number]
  centerX: number
  centerY: number
  /** Mask fill color (CSS). Defaults to a translucent gray.
   *  蒙版填充色（CSS）。默认半透明灰。 */
  color?: string
}

export interface ImageMaskOverlay {
  type: 'imageMask'
  /** PNG URL (blob: or data:) of a same-resolution overlay, alpha-encoded. / 与底图同分辨率的叠加 PNG（blob: 或 data:），由 alpha 通道控制透明度。 */
  src: string
  width: number
  height: number
}

export interface LineSegmentOverlay {
  type: 'lineSegment'
  /** Start point in data space (col, row) — same space as beamCenter.x/y. / 起点数据坐标（列, 行）—— 与 beamCenter.x/y 同空间。 */
  x0: number
  y0: number
  /** End point in data space (col, row). / 终点数据坐标（列, 行）。 */
  x1: number
  y1: number
  /** Line color (CSS). Defaults to cyan (#22d3ee). / 线颜色（CSS）。默认青色 (#22d3ee)。 */
  color?: string
  /** Visual line width in canvas pixels (display only; the integrated band
   *  width is set on the backend). / 画布像素的视觉线宽（仅显示；积分带宽在后端设置）。 */
  lineWidth?: number
}

export type Overlay = BeamCenterOverlay | SectorBoundaryOverlay | SectorMaskOverlay | ImageMaskOverlay | LineSegmentOverlay | OriginMarkerOverlay

export interface OriginMarkerOverlay {
  type: 'originMarker'
  /** Pixel origin corner position in data space (col, row). Usually (0,0) for
   *  top-left orientation, or (width, height) for bottom-right, etc.
   *  / 像素原点角标的数据坐标（列, 行）。通常为 (0,0)（左上方向），或
   *  (width, height)（右下方向）等。 */
  x: number
  y: number
  /** Corner bracket color (CSS). Defaults to cyan (#22d3ee).
   *  / 角标颜色（CSS）。默认青色 (#22d3ee)。 */
  color?: string
}

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
  /** Full-resolution target for click→pixel mapping (cols, rows).
   *  When set (e.g. the displayed image is a downscaled preview but geometry
   *  is computed at full data resolution), clicks map to this size instead of
   *  the displayed image's natural pixels. / 点击→像素映射的全分辨率目标（列, 行）。
   *  当设置时（如显示的是缩小预览图，但几何按全数据分辨率计算），点击映射到此尺寸，
   *  而非所显示图像的自然像素。 */
  dataWidth?: number
  dataHeight?: number
  /** When true, left-drag draws a line segment instead of panning. The
   *  resulting endpoints are emitted via the `line:drawn` event in data-space
   *  pixel coordinates (col=x, row=y), using the same dataWidth/dataHeight
   *  mapping as image:click. / 为 true 时，左键拖拽绘制线段而非平移。结果端点通过
   *  `line:drawn` 事件以数据空间像素坐标（col=x, row=y）发出，映射方式与 image:click 相同。 */
  lineDrawMode?: boolean
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
  dataWidth: undefined,
  dataHeight: undefined,
  lineDrawMode: false,
})

// --- Emits ---

const emit = defineEmits<{
  'image:click': [event: { x: number; y: number; pixelX: number; pixelY: number }]
  'line:drawn': [event: { pixelX0: number; pixelY0: number; pixelX1: number; pixelY1: number }]
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

// Line-drawing state (only active when lineDrawMode is on).
// 画线状态（仅当 lineDrawMode 开启时激活）。
let isDrawingLine = false
let lineStartPxX = 0
let lineStartPxY = 0
let lineCurPxX = 0
let lineCurPxY = 0

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
  // Prevent page scroll while zooming; registered as a non-passive listener
  // in onMounted so we can call preventDefault without Chromium warnings.
  // 缩放时阻止页面滚动；监听器在 onMounted 中以 non-passive 方式注册，
  // 因此可以调用 preventDefault 而不触发 Chromium 警告。
  e.preventDefault()
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

  // In line-draw mode, a left drag draws a segment instead of panning.
  // 在画线模式下，左键拖拽绘制线段而非平移。
  if (props.lineDrawMode) {
    const img = viewportRef.value?.querySelector('.ip-image') as HTMLImageElement | null
    if (!img) return
    const px = clientToDataPixel(e.clientX, e.clientY, img)
    if (!px) return
    isDrawingLine = true
    lineStartPxX = px.pixelX
    lineStartPxY = px.pixelY
    lineCurPxX = px.pixelX
    lineCurPxY = px.pixelY
    const vp = viewportRef.value
    if (vp) vp.style.cursor = 'crosshair'
    window.addEventListener('mousemove', onLineMouseMove)
    window.addEventListener('mouseup', onLineMouseUp)
    e.preventDefault()
    return
  }

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

// --- Line drawing (lineDrawMode) / 画线（lineDrawMode） ---

function onLineMouseMove(e: MouseEvent) {
  if (!isDrawingLine) return
  const img = viewportRef.value?.querySelector('.ip-image') as HTMLImageElement | null
  if (!img) return
  const px = clientToDataPixel(e.clientX, e.clientY, img)
  if (!px) return
  lineCurPxX = px.pixelX
  lineCurPxY = px.pixelY
  scheduleOverlayRedraw()
}

function onLineMouseUp() {
  if (!isDrawingLine) return
  isDrawingLine = false
  const vp = viewportRef.value
  if (vp) vp.style.cursor = ''
  window.removeEventListener('mousemove', onLineMouseMove)
  window.removeEventListener('mouseup', onLineMouseUp)
  // Only emit if the drag produced a non-degenerate segment; a click without
  // movement (start == current) carries no direction info.
  // 仅在拖拽产生非退化线段时发出；无移动的点击（起点 == 当前点）不携带方向信息。
  if (lineStartPxX !== lineCurPxX || lineStartPxY !== lineCurPxY) {
    emit('line:drawn', {
      pixelX0: lineStartPxX,
      pixelY0: lineStartPxY,
      pixelX1: lineCurPxX,
      pixelY1: lineCurPxY,
    })
  } else {
    // Clear the in-progress preview so a stray click doesn't leave a dot.
    // 清除进行中的预览，避免误点击留下一个点。
    scheduleOverlayRedraw()
  }
}

// --- Image click → pixel coordinates / 图片点击 → 像素坐标 ---

/** Map a screen-space client coordinate to data-space pixel coordinates.
 *  Shared by image:click and line:drawn so they always agree on the mapping
 *  (preview vs full-res via dataWidth/dataHeight). Returns null if the image
 *  hasn't loaded yet.
 *  将屏幕空间客户端坐标映射到数据空间像素坐标。image:click 与 line:drawn
 *  共用此映射（通过 dataWidth/dataHeight 处理预览/全分辨率），确保两者一致。
 *  图像尚未加载时返回 null。
 */
function clientToDataPixel(
  clientX: number,
  clientY: number,
  img: HTMLImageElement,
): { pixelX: number; pixelY: number } | null {
  const rect = img.getBoundingClientRect()
  const displayW = rect.width
  const displayH = rect.height
  if (displayW <= 0 || displayH <= 0) return null
  const relX = clientX - rect.left
  const relY = clientY - rect.top

  // Use the image element's OWN natural dimensions (not the reactive ref,
  // which can be stale across preview/full-res swaps) to map the click.
  // When dataWidth/dataHeight are provided, map to the FULL data resolution
  // (the displayed image may be a downscaled preview, but geometry/q are
  // computed at full resolution) — otherwise clicks land on the wrong pixel.
  // 使用图像元素自身的自然尺寸（而非可能跨预览/全分辨率切换后滞后的响应式 ref）
  // 映射坐标。当提供 dataWidth/dataHeight 时，映射到全数据分辨率（显示的可能是
  // 缩小预览图，但几何/q 按全分辨率计算），否则会落到错误像素。
  const dispNatW = img.naturalWidth || naturalWidth.value
  const dispNatH = img.naturalHeight || naturalHeight.value
  const targetW = props.dataWidth ?? dispNatW
  const targetH = props.dataHeight ?? dispNatH

  return {
    pixelX: Math.round((relX / displayW) * targetW),
    pixelY: Math.round((relY / displayH) * targetH),
  }
}

function onImageClick(e: MouseEvent) {
  if (isDragging) return
  // Suppress the click that follows a line-draw drag (mouseup fires click on
  // the <img>; without this guard a draw would also register as a pixel read).
  // 抑制画线拖拽后紧跟的 click（mouseup 会在 <img> 上触发 click；若不拦截，
  // 画线操作会同时触发一次像素读取）。
  if (props.lineDrawMode) return
  const img = e.currentTarget as HTMLImageElement
  const px = clientToDataPixel(e.clientX, e.clientY, img)
  if (!px) return

  // Diagnostic: log the mapping so misalignment between clicks and geometry
  // can be traced (open DevTools console). / 诊断：记录映射，便于排查点击与
  // 几何坐标不一致的问题（打开开发者工具控制台查看）。
  // eslint-disable-next-line no-console
  console.warn('[image:click]', { ...px, dataWidth: props.dataWidth, dataHeight: props.dataHeight })

  emit('image:click', {
    x: e.clientX,
    y: e.clientY,
    pixelX: px.pixelX,
    pixelY: px.pixelY,
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

// Cache decoded overlay images so async loads only happen once per src.
// When an image finishes loading it schedules a redraw, so the first paint may
// skip a not-yet-loaded mask and fill it in on the next frame.
// 缓存已解码的叠加图像，使每个 src 仅异步加载一次。图像加载完成后会触发重绘，
// 因此首帧可能跳过尚未加载的遮罩，并在下一帧补上。
// Bounded by insertion order: the oldest entry is evicted once the cap is hit,
// which keeps the cache from retaining revoked blob: URLs forever as the
// azimuth mask src changes on every range edit.
// 按插入顺序限制大小：达到上限后驱逐最旧条目，避免方位角遮罩 src 随范围编辑变化时
// 缓存永远保留已被回收的 blob: URL。
const OVERLAY_IMAGE_CACHE_MAX = 8
const overlayImageCache = new Map<string, HTMLImageElement>()

function loadOverlayImage(src: string): HTMLImageElement {
  const cached = overlayImageCache.get(src)
  if (cached) return cached
  const img = new Image()
  img.decoding = 'async'
  // Trigger a redraw once decoded so the mask appears without a state change.
  // 解码完成后触发重绘，使遮罩在无状态变更的情况下出现。
  img.onload = () => scheduleOverlayRedraw()
  img.src = src
  // Bounded LRU-style insertion: move newest to the end, evict oldest first.
  // 有界插入：最新条目置于末尾，优先驱逐最旧条目。
  overlayImageCache.delete(src)
  overlayImageCache.set(src, img)
  while (overlayImageCache.size > OVERLAY_IMAGE_CACHE_MAX) {
    const oldest = overlayImageCache.keys().next().value
    if (oldest === undefined) break
    overlayImageCache.delete(oldest)
  }
  return img
}

function drawOverlays() {
  const canvas = overlayCanvasRef.value
  if (!canvas || !naturalWidth.value) return

  const ctx = canvas.getContext('2d')
  if (!ctx) return

  // Canvas dimensions are set by :width/:height bindings
  ctx.clearRect(0, 0, canvas.width, canvas.height)

  // Vector overlays (beamCenter, sectorBoundary) come in DATA coordinates
  // (full resolution, matching the geometry). The canvas is sized to the
  // DISPLAYED image (possibly a downscaled preview). Scale vector coords from
  // data space → canvas space so the crosshair/sector lines land correctly.
  // 矢量叠加（光束中心、扇区线）使用数据坐标（全分辨率，与几何一致）。画布尺寸为
  // 所显示图像（可能是缩小预览）。将矢量坐标从数据空间缩放到画布空间，使十字/扇区线
  // 落在正确位置。
  const scaleX = props.dataWidth && props.dataWidth > 0 ? canvas.width / props.dataWidth : 1
  const scaleY = props.dataHeight && props.dataHeight > 0 ? canvas.height / props.dataHeight : 1

  for (const overlay of props.overlays) {
    // Raster masks are drawn first so vector overlays (beam center, sector
    // lines) render on top. The overlay canvas is sized to natural image
    // pixels, so drawImage at (0,0,w,h) is a 1:1 pixel-aligned composite.
    // 栅格遮罩先绘制，使矢量叠加（光束中心、扇区线）绘制在其之上。叠加画布尺寸
    // 等于图像自然像素，故 drawImage(0,0,w,h) 为 1:1 像素对齐合成。
    if (overlay.type === 'imageMask') {
      const img = overlayImageCache.get(overlay.src)
      if (img?.complete && img.naturalWidth > 0) {
        // Draw to the canvas's own pixel dimensions (= displayed image's
        // natural pixels), NOT overlay.width/height. The mask PNG and the
        // displayed image share the same source data shape, so scaling the
        // mask to canvas.width/height keeps them 1:1 aligned even when the
        // overlay's width/height props come from metadata that differs from
        // the actually-displayed (e.g. preview) image size.
        // 绘制到画布自身的像素尺寸（= 所显示图像的自然像素），而非 overlay.width/height。
        // 遮罩 PNG 与所显示图像共享同一源数据形状，故按 canvas.width/height 缩放遮罩
        // 可保持 1:1 对齐，即使 overlay 的 width/height 来自与实际显示图像（如预览图）
        // 尺寸不一致的元数据。
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
      } else {
        // Kick off the async decode; onload will redraw once ready.
        // 启动异步解码，onload 会在就绪后重绘。
        loadOverlayImage(overlay.src)
      }
    }
  }

  for (const overlay of props.overlays) {
    // The gray azimuth mask is drawn first among vector overlays so the sector
    // boundary rays and beam-center crosshair stay visible on top of it.
    // 灰色方位角蒙版在矢量叠加中最先绘制，扇区边界线与光束中心十字保持在其之上。
    if (overlay.type === 'sectorMask') {
      const cx = overlay.centerX * scaleX
      const cy = overlay.centerY * scaleY
      // Radius covering the whole canvas from the center (anisotropy-safe).
      // 从中心足以覆盖整个画布的半径（各向异性安全）。
      const rx = Math.max(cx, canvas.width - cx, 1)
      const ry = Math.max(cy, canvas.height - cy, 1)
      const rCover = Math.hypot(rx, ry)

      let startDeg = overlay.angles[0]
      let sweep = overlay.angles[1] - startDeg
      if (sweep <= 0) sweep += 360
      if (sweep >= 360) continue // whole plane selected → nothing to shade / 全选则无需蒙版

      // Fill the whole canvas with translucent gray, then knock out the
      // selected wedge via evenodd (rect + wedge as one compound path).
      // The wedge path MUST start at the CENTER (moveTo center → arc →
      // closePath): starting it at the arc start would produce a circular
      // SEGMENT (chord closure) that leaves a gray triangle over the beam
      // center. Chi angles map directly to canvas arc angles (y-down ⇒
      // positive chi sweeps clockwise on screen, matching the boundary rays).
      // 用 evenodd（矩形 + 楔形复合路径）填充全画布灰色、抠掉选中扇区。
      // 楔形路径必须从中心开始（moveTo 中心 → 弧 → closePath）：若从弧起点
      // 开始，闭合的是弦而非两条半径，会在光束中心残留一块灰色三角。
      // chi 角直接映射画布弧角（y 向下 ⇒ 正 chi 屏幕顺时针，与边界线一致）。
      const startRad = (startDeg * Math.PI) / 180
      const endRad = startRad + (sweep * Math.PI) / 180
      ctx.save()
      ctx.fillStyle = overlay.color ?? 'rgba(128, 128, 128, 0.45)'
      ctx.beginPath()
      ctx.rect(0, 0, canvas.width, canvas.height)
      ctx.moveTo(cx, cy)
      ctx.ellipse(cx, cy, rCover, rCover, 0, startRad, endRad, false)
      ctx.closePath()
      ctx.fill('evenodd')
      ctx.restore()
    }

    if (overlay.type === 'beamCenter') {
      const cx = overlay.x * scaleX
      const cy = overlay.y * scaleY
      const arm = 16
      const coreColor = overlay.color ?? '#ef4444'

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
      // Colored core (red by default, yellow if requested) / 彩色核心（默认红，可指定黄）
      draw(coreColor, 2)
    }

    if (overlay.type === 'originMarker') {
      const ox = overlay.x * scaleX
      const oy = overlay.y * scaleY
      const size = 22
      const color = overlay.color ?? '#22d3ee'
      ctx.save()
      ctx.strokeStyle = '#ffffff'
      ctx.lineWidth = 4
      ctx.lineCap = 'round'
      // Determine which corner the bracket opens toward based on position
      // relative to the image center. / 根据原点相对于图像中心的位置确定角标开口方向。
      const imgW = canvas.width
      const imgH = canvas.height
      const isRight = ox > imgW / 2
      const isBottom = oy > imgH / 2
      // White halo / 白色光晕
      ctx.beginPath()
      if (!isRight && !isBottom) {
        // Top-left corner bracket / 左上角标
        ctx.moveTo(ox, oy + size); ctx.lineTo(ox, oy); ctx.lineTo(ox + size, oy)
      } else if (isRight && !isBottom) {
        // Top-right corner bracket / 右上角标
        ctx.moveTo(ox - size, oy); ctx.lineTo(ox, oy); ctx.lineTo(ox, oy + size)
      } else if (!isRight && isBottom) {
        // Bottom-left corner bracket / 左下角标
        ctx.moveTo(ox, oy - size); ctx.lineTo(ox, oy); ctx.lineTo(ox + size, oy)
      } else {
        // Bottom-right corner bracket / 右下角标
        ctx.moveTo(ox - size, oy); ctx.lineTo(ox, oy); ctx.lineTo(ox, oy - size)
      }
      ctx.stroke()
      // Colored core / 彩色核心
      ctx.strokeStyle = color
      ctx.lineWidth = 2
      ctx.beginPath()
      if (!isRight && !isBottom) {
        ctx.moveTo(ox, oy + size); ctx.lineTo(ox, oy); ctx.lineTo(ox + size, oy)
      } else if (isRight && !isBottom) {
        ctx.moveTo(ox - size, oy); ctx.lineTo(ox, oy); ctx.lineTo(ox, oy + size)
      } else if (!isRight && isBottom) {
        ctx.moveTo(ox, oy - size); ctx.lineTo(ox, oy); ctx.lineTo(ox + size, oy)
      } else {
        ctx.moveTo(ox - size, oy); ctx.lineTo(ox, oy); ctx.lineTo(ox, oy - size)
      }
      ctx.stroke()
      ctx.restore()
    }

    if (overlay.type === 'sectorBoundary') {
      // Angles are pyFAI chi in degrees. pyFAI's chi is measured from the
      // positive column axis (+x → right) with +90° pointing along increasing
      // row (+y → DOWN on the displayed image), so positive angles run
      // clockwise on screen. The endpoint must therefore ADD sin to cy;
      // subtracting it (math-class y-up) mirrors the sector vertically and
      // makes the overlay show the opposite wedge from what is integrated.
      // 角度为 pyFAI 的 chi（度）。pyFAI 的 chi 从列正方向（+x → 右）起算，
      // +90° 指向行增加方向（+y → 图像显示中的下方），即正角度在屏幕上顺时针。
      // 端点计算必须对 cy 加 sin；若按数学习惯减去，扇区会上下镜像，
      // 导致叠加层显示的楔形与实际积分的楔形相反。
      const cx = overlay.centerX * scaleX
      const cy = overlay.centerY * scaleY
      const r = overlay.radius ?? Math.max(naturalWidth.value, naturalHeight.value)

      ctx.strokeStyle = '#1e40af'
      ctx.lineWidth = 2.5
      ctx.setLineDash([6, 4])

      for (const angleDeg of overlay.angles) {
        const rad = (angleDeg * Math.PI) / 180
        ctx.beginPath()
        ctx.moveTo(cx, cy)
        ctx.lineTo(cx + r * Math.cos(rad) * scaleX, cy + r * Math.sin(rad) * scaleY)
        ctx.stroke()
      }

      ctx.setLineDash([])
    }

    if (overlay.type === 'lineSegment') {
      drawSegment(
        ctx,
        overlay.x0 * scaleX, overlay.y0 * scaleY,
        overlay.x1 * scaleX, overlay.y1 * scaleY,
        overlay.color ?? '#22d3ee',
        overlay.lineWidth ?? 2,
        false,
      )
    }
  }

  // In-progress drag preview: a dashed cyan segment from the anchored start
  // to the current cursor position. Drawn at the very end so it sits on top.
  // 进行中的拖拽预览：从锚定起点到当前光标位置的虚线青色线段。最后绘制以置于顶层。
  if (isDrawingLine) {
    drawSegment(
      ctx,
      lineStartPxX * scaleX, lineStartPxY * scaleY,
      lineCurPxX * scaleX, lineCurPxY * scaleY,
      '#22d3ee',
      2,
      true,
    )
    // Endpoint markers so the user sees the exact anchor / current point.
    // 端点标记，便于用户看到确切的锚点 / 当前点。
    drawEndpoint(ctx, lineStartPxX * scaleX, lineStartPxY * scaleY, '#22d3ee')
    drawEndpoint(ctx, lineCurPxX * scaleX, lineCurPxY * scaleY, '#22d3ee')
  }
}

/** Stroke a segment on the overlay canvas, with a white outline for visibility. */
function drawSegment(
  ctx: CanvasRenderingContext2D,
  x0: number, y0: number, x1: number, y1: number,
  color: string, lineWidth: number, dashed: boolean,
) {
  ctx.save()
  ctx.lineCap = 'round'
  if (dashed) ctx.setLineDash([6, 4])
  // White halo / 白色光晕
  ctx.strokeStyle = '#ffffff'
  ctx.lineWidth = lineWidth + 2
  ctx.beginPath()
  ctx.moveTo(x0, y0)
  ctx.lineTo(x1, y1)
  ctx.stroke()
  // Colored core / 彩色核心
  ctx.strokeStyle = color
  ctx.lineWidth = lineWidth
  ctx.beginPath()
  ctx.moveTo(x0, y0)
  ctx.lineTo(x1, y1)
  ctx.stroke()
  ctx.restore()
}

function drawEndpoint(ctx: CanvasRenderingContext2D, x: number, y: number, color: string) {
  ctx.save()
  ctx.fillStyle = '#ffffff'
  ctx.beginPath()
  ctx.arc(x, y, 4, 0, Math.PI * 2)
  ctx.fill()
  ctx.fillStyle = color
  ctx.beginPath()
  ctx.arc(x, y, 2.5, 0, Math.PI * 2)
  ctx.fill()
  ctx.restore()
}

function scheduleOverlayRedraw() {
  cancelAnimationFrame(rafId)
  rafId = requestAnimationFrame(drawOverlays)
}

// Redraw overlays when zoom/pan/overlays change. Also redraw on lineDrawMode
// toggle so the cursor style and any in-progress preview update immediately.
// 缩放/平移/叠加变化时重绘叠加。lineDrawMode 切换时也重绘，使光标样式和进行中
// 的预览立即更新。
watch([zoom, panX, panY, () => props.overlays, () => props.lineDrawMode], scheduleOverlayRedraw)

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
  // Register wheel listener as non-passive so preventDefault works without
  // triggering Chromium "[Violation] Added non-passive event listener" warnings.
  // 以 non-passive 方式注册滚轮监听器，使 preventDefault 生效且不触发警告。
  viewportRef.value?.addEventListener('wheel', onWheel, { passive: false })
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
  viewportRef.value?.removeEventListener('wheel', onWheel)
  window.removeEventListener('mousemove', onMouseMove)
  window.removeEventListener('mouseup', onMouseUp)
  window.removeEventListener('mousemove', onLineMouseMove)
  window.removeEventListener('mouseup', onLineMouseUp)
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
