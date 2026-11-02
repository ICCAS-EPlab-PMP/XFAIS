<template>
  <div class="czp-backdrop" @click.self="$emit('cancel')">
    <div class="czp-panel">
      <h3 class="czp-title">{{ t('calibration.ring.zoomTitle') }}</h3>

      <div class="czp-canvas-wrap" :style="wrapStyle">
        <canvas
          ref="canvasRef"
          class="czp-canvas"
          :width="displaySize"
          :height="displaySize"
          data-ai-id="calibration:zoom-canvas"
          @click="onCanvasClick"
        />
        <div v-if="!loaded" class="czp-loading">{{ t('calibration.ring.zoomPlaceholder') }}</div>
      </div>

      <p class="czp-coords">{{ coordLabel }}</p>

      <div class="czp-footer">
        <button
          type="button"
          class="czp-btn"
          data-ai-id="calibration:zoom-cancel"
          @click="$emit('cancel')"
        >
          {{ t('calibration.ring.zoomCancel') }}
        </button>
        <button
          type="button"
          class="czp-btn czp-btn--primary"
          data-ai-id="calibration:zoom-confirm"
          :disabled="picked == null"
          @click="confirm"
        >
          {{ t('calibration.ring.zoomConfirm') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * CalibZoomPicker.vue — FIT2D 式放大二次选点弹窗
 * FIT2D-style zoomed second pick: the first canvas click opens this window on a
 * regionSize × regionSize neighbourhood of that click; the window shows the
 * region magnified (nearest-neighbour, no smoothing) and a second click places
 * the crosshair at sub-pixel precision, so ring points can be placed exactly
 * on the ring instead of at screen resolution.
 * 第一次点击在该处开启 regionSize × regionSize 邻域窗口，窗口以最近邻放大显示
 * （不插值），第二次点击以亚像素精度落下十字准星——环上点可精确落在环上，
 * 而不是受限于屏幕分辨率。
 *
 * Props carry the ORIGINAL frame size (imageWidth/Height) while the `<img>` PNG
 * may be downsampled (preview_scale < 1); naturalWidth/imageWidth converts the
 * displayed texture back to true image pixels.
 * 属性携带原始帧尺寸（imageWidth/Height），而 <img> PNG 可能已降采样
 * （preview_scale < 1）；用 naturalWidth/imageWidth 把纹理换算回真实像素。
 */
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

/** A picked point in ORIGINAL image pixels (row = y, col = x). / 原始图像像素。 */
export interface CalibZoomPick {
  row: number
  col: number
}

const props = withDefaults(defineProps<{
  /** Displayed image (blob or data URL). / 显示图像（blob 或 data URL）。 */
  imageSrc: string | null
  /** ORIGINAL frame width in px (true coordinate space). / 原始帧宽。 */
  imageWidth: number
  /** ORIGINAL frame height in px. / 原始帧高。 */
  imageHeight: number
  /** The click that opened the window, in original image pixels. / 锚点。 */
  anchor: { row: number; col: number }
  /** Neighbourhood side length in original px (clamped at the frame edge). */
  regionSize?: number
  /** Magnified canvas side in CSS px. / 放大画布边长。 */
  displaySize?: number
}>(), {
  regionSize: 100,
  displaySize: 300,
})

const emit = defineEmits<{
  /** Second pick confirmed (plain object — never a Vue proxy). */
  confirm: [pick: CalibZoomPick]
  cancel: []
}>()

const { t } = useI18n()

const canvasRef = ref<HTMLCanvasElement | null>(null)
const loaded = ref(false)
const picked = ref<CalibZoomPick | null>(null)

/** Source rectangle in ORIGINAL image pixels (edge-clamped; may be smaller
 *  than regionSize near the frame border). / 源矩形（边界截断，可能小于区域尺寸）。 */
let srcRect = { x0: 0, y0: 0, w: 1, h: 1 }
let image: HTMLImageElement | null = null

const wrapStyle = computed(() => ({
  width: `${props.displaySize}px`,
  height: `${props.displaySize}px`,
}))

const coordLabel = computed(() => {
  const p = picked.value
  if (!p) return '—'
  return `x (col) = ${p.col.toFixed(2)} px, y (row) = ${p.row.toFixed(2)} px`
})

/** (anchor − region/2 … anchor + region/2) in original px, clamped to the
 *  frame — the actual region may be smaller than regionSize at the edges, so
 *  the EFFECTIVE magnification depends on the anchor: ≈3× (300/100) around the
 *  frame centre, up to ≈6× when the region is clipped to ~50 px at an edge.
 *  The crosshair readout stays in true image pixels either way.
 *  以锚点为中心的源区域（原始像素），按帧边界截断——边缘处实际区域可能小于
 *  100 px，故有效放大倍率随锚点变化：画面中心约 3×（300/100），贴边截到
 *  ~50 px 时可达约 6×。十字准星读数始终是真实图像像素。 */
function computeSrcRect(): void {
  const half = props.regionSize / 2
  const x0f = props.anchor.col - half
  const y0f = props.anchor.row - half
  const x0 = Math.max(0, x0f)
  const y0 = Math.max(0, y0f)
  const x1 = Math.min(props.imageWidth, x0f + props.regionSize)
  const y1 = Math.min(props.imageHeight, y0f + props.regionSize)
  srcRect = {
    x0,
    y0,
    w: Math.max(1e-6, x1 - x0),
    h: Math.max(1e-6, y1 - y0),
  }
}

function draw(): void {
  const canvas = canvasRef.value
  if (!canvas || !image) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  // Nearest neighbour: magnified detector pixels must stay square and sharp.
  // 最近邻：放大的探测器像素保持方块、锐利。
  ctx.imageSmoothingEnabled = false
  ctx.clearRect(0, 0, props.displaySize, props.displaySize)
  // Rendered texture → original pixels scale (preview_scale may be < 1: the
  // parent caps large frames at ≤1600 px). NOTE: when the texture is
  // downsampled, sub-pixel precision is bounded by the TEXTURE resolution —
  // one downsampled pixel spans imageWidth/naturalWidth original pixels (e.g.
  // ≈1.28 px at 2048 with a 1600 px texture), so neighbouring crosshair
  // positions may differ by that step even though the readout keeps decimals.
  // 渲染纹理 → 原始像素比例（preview_scale 可能 < 1：父组件对大图限幅到
  // ≤1600 px）。注意：纹理降采样时，亚像素精度受纹理分辨率限制——一个降采样
  // 像素对应 imageWidth/naturalWidth 个原始像素（2048 图、1600 纹理时约
  // 1.28 px），相邻准星位置可能以该步距跳变，尽管读数仍保留小数。
  const scale = image.naturalWidth > 0 && props.imageWidth > 0
    ? image.naturalWidth / props.imageWidth
    : 1
  ctx.drawImage(
    image,
    srcRect.x0 * scale, srcRect.y0 * scale, srcRect.w * scale, srcRect.h * scale,
    0, 0, props.displaySize, props.displaySize,
  )
  if (picked.value) {
    const px = ((picked.value.col - srcRect.x0) / srcRect.w) * props.displaySize
    const py = ((picked.value.row - srcRect.y0) / srcRect.h) * props.displaySize
    ctx.strokeStyle = '#e879f9'
    ctx.lineWidth = 1
    ctx.beginPath()
    ctx.moveTo(px, 0)
    ctx.lineTo(px, props.displaySize)
    ctx.moveTo(0, py)
    ctx.lineTo(props.displaySize, py)
    ctx.stroke()
    ctx.beginPath()
    ctx.arc(px, py, 5, 0, Math.PI * 2)
    ctx.stroke()
  }
}

/** Canvas click → source pixel coordinates (fractions KEPT — that is the point
 *  of the zoomed pass). / 画布点击 → 源像素坐标（保留小数）。 */
function onCanvasClick(e: MouseEvent): void {
  const canvas = canvasRef.value
  if (!canvas) return
  const rect = canvas.getBoundingClientRect()
  if (!(rect.width > 0) || !(rect.height > 0)) return
  const fx = Math.min(Math.max((e.clientX - rect.left) / rect.width, 0), 1)
  const fy = Math.min(Math.max((e.clientY - rect.top) / rect.height, 0), 1)
  picked.value = {
    col: srcRect.x0 + fx * srcRect.w,
    row: srcRect.y0 + fy * srcRect.h,
  }
  draw()
}

function confirm(): void {
  const p = picked.value
  if (!p) return
  // Fresh plain object — a ref's reactive proxy cannot cross the IPC structured
  // clone (BUG C). / 全新普通对象——响应式代理无法通过 IPC 结构化克隆。
  emit('confirm', { row: p.row, col: p.col })
}

function onKeydown(e: KeyboardEvent): void {
  if (e.key === 'Enter') {
    if (picked.value) {
      e.preventDefault()
      confirm()
    }
  } else if (e.key === 'Escape') {
    e.preventDefault()
    emit('cancel')
  }
}

onMounted(() => {
  window.addEventListener('keydown', onKeydown)
  const img = new Image()
  img.onload = () => {
    image = img
    computeSrcRect()
    // Seed the crosshair AT the anchor: the user sees where the first click
    // landed and can nudge it; confirming without a second click returns the
    // anchor itself. / 十字准星先落在锚点：用户可微调；不再点击直接确定即
    // 返回锚点本身。
    picked.value = {
      row: Math.min(Math.max(props.anchor.row, srcRect.y0), srcRect.y0 + srcRect.h),
      col: Math.min(Math.max(props.anchor.col, srcRect.x0), srcRect.x0 + srcRect.w),
    }
    loaded.value = true
    void Promise.resolve().then(draw)
  }
  if (props.imageSrc) img.src = props.imageSrc
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
})
</script>

<style scoped>
.czp-backdrop {
  position: fixed;
  inset: 0;
  z-index: var(--z-modal, 100);
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(15, 23, 42, 0.5);
  backdrop-filter: blur(4px);
}

.czp-panel {
  padding: 20px;
  border-radius: 20px;
  background: var(--bg-surface, #fff);
  border: 1px solid var(--border);
  box-shadow: 0 24px 48px rgba(15, 23, 42, 0.2);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.czp-title {
  font-size: 1.05rem;
  font-weight: 700;
  margin: 0;
  color: var(--text-primary);
}

.czp-canvas-wrap {
  position: relative;
  border: 1px solid var(--border);
  border-radius: 10px;
  overflow: hidden;
}

.czp-canvas {
  display: block;
  width: 100%;
  height: 100%;
  cursor: crosshair;
  /* Nearest-neighbour scaling in CSS as well (belt and braces with the
     imageSmoothingEnabled=false draw). / CSS 侧同样最近邻放大。 */
  image-rendering: pixelated;
}

.czp-loading {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.8rem;
  color: var(--text-muted);
  background: var(--bg-hover, rgba(248, 250, 252, 0.8));
}

.czp-coords {
  margin: 0;
  font-family: var(--font-mono);
  font-size: 0.78rem;
  color: var(--text-secondary);
  text-align: center;
}

.czp-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.czp-btn {
  padding: 8px 18px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--bg-surface, rgba(255, 255, 255, 0.8));
  color: var(--text-primary);
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  transition: all var(--transition-fast, 0.15s);
}

.czp-btn:hover:not(:disabled) {
  border-color: var(--border-hover);
  box-shadow: var(--shadow-sm);
}

.czp-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.czp-btn--primary {
  border: none;
  background: var(--primary);
  color: var(--text-inverse);
  font-weight: 700;
}

.czp-btn--primary:hover:not(:disabled) {
  opacity: 0.9;
}
</style>
