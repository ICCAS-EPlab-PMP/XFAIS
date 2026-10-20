<template>
  <div class="line-chart-wrap">
    <!-- Line / points mode toggle + optional y-scale toggle / 线图·点图切换 + 可选 y 轴刻度切换 -->
    <div class="lc-mode-bar" role="group" :data-testid="testIds.lineChartMode">
      <button
        type="button"
        :class="['lc-mode-btn', { 'lc-mode-active': lineMode === 'lines' }]"
        :data-testid="testIds.lineChartModeLine"
        :aria-pressed="lineMode === 'lines'"
        :title="t('business.display.chartLine')"
        @click="lineMode = 'lines'"
      >
        <svg class="lc-icon" width="16" height="8" viewBox="0 0 16 8" aria-hidden="true">
          <line x1="1" y1="4" x2="15" y2="4" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
        </svg>
        <span class="lc-label">{{ t('business.display.chartLine') }}</span>
      </button>
      <button
        type="button"
        :class="['lc-mode-btn', { 'lc-mode-active': lineMode === 'markers' }]"
        :data-testid="testIds.lineChartModePoints"
        :aria-pressed="lineMode === 'markers'"
        :title="t('business.display.chartPoints')"
        @click="lineMode = 'markers'"
      >
        <svg class="lc-icon" width="16" height="8" viewBox="0 0 16 8" aria-hidden="true">
          <circle cx="3" cy="4" r="1.7" fill="currentColor" />
          <circle cx="8" cy="4" r="1.7" fill="currentColor" />
          <circle cx="13" cy="4" r="1.7" fill="currentColor" />
        </svg>
        <span class="lc-label">{{ t('business.display.chartPoints') }}</span>
      </button>
      <template v-if="yScaleToggle">
        <span class="lc-divider" aria-hidden="true"></span>
        <button
          type="button"
          :class="['lc-mode-btn', { 'lc-mode-active': yScaleState === 'log' }]"
          :aria-pressed="yScaleState === 'log'"
          :title="t('business.display.yLog')"
          @click="yScaleState = 'log'"
        >
          <svg class="lc-icon" width="16" height="8" viewBox="0 0 16 8" aria-hidden="true">
            <path d="M1,1 C4,1.5 6,5 15,7" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
          </svg>
          <span class="lc-label">{{ t('business.display.yLog') }}</span>
        </button>
        <button
          type="button"
          :class="['lc-mode-btn', { 'lc-mode-active': yScaleState === 'linear' }]"
          :aria-pressed="yScaleState === 'linear'"
          :title="t('business.display.yLinear')"
          @click="yScaleState = 'linear'"
        >
          <svg class="lc-icon" width="16" height="8" viewBox="0 0 16 8" aria-hidden="true">
            <line x1="1" y1="7" x2="15" y2="1" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
          </svg>
          <span class="lc-label">{{ t('business.display.yLinear') }}</span>
        </button>
      </template>
    </div>

    <PlotlyChart
      ref="plotlyRef"
      :data="traces"
      :layout="chartLayout"
      :config="chartConfig"
      :dark-mode="true"
      data-testid="line-chart"
      @plot:click="(e) => emit('plot:click', e)"
      @plot:hover="(e) => emit('plot:hover', e)"
      @plot:relayout="(e) => emit('plot:relayout', e)"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import PlotlyChart from './PlotlyChart.vue'
import type { PlotData, PlotLayout } from 'plotly.js-dist-min'
import { axisTitle } from '@/lib/chart-utils'
import { testIds } from '@/lib/testIds'

const emit = defineEmits<{
  'plot:click': [event: unknown]
  'plot:hover': [event: unknown]
  'plot:relayout': [event: unknown]
  /** Free click in DATA coordinates — fires anywhere on the plot area while
   *  `clickCapture` is on (see the native listener below). /
   *  数据坐标系下的自由点击——clickCapture 开启时图面任意位置都触发。 */
  'capture:click': [point: { x: number; y: number }]
}>()

export interface LineTrace {
  x: number[]
  y: number[]
  name?: string
  color?: string
  /** Plotly line dash style ('solid' | 'dash' | 'dot' | 'dashdot'). */
  /** Plotly 线型（'solid' | 'dash' | 'dot' | 'dashdot'）。 */
  dash?: string
}

/** Free annotation rendered above the traces (PeakFit-style peak labels). */
/** 叠加在曲线上的自由标注（PeakFit 式峰标签）。 */
export interface LineAnnotation {
  x: number
  y: number
  text: string
  color?: string
}

const props = withDefaults(defineProps<{
  traces: LineTrace[]
  /** Free annotations (e.g. per-peak fit labels). / 自由标注（如逐峰拟合标签）。 */
  annotations?: LineAnnotation[]
  xLabel?: string
  yLabel?: string
  xUnit?: string
  yUnit?: string
  title?: string
  /** Initial y-axis scale; SAXS I(q) curves default to log in callers that want it. */
  /** y 轴初始刻度；SAXS I(q) 类曲线由调用方按需默认 log。 */
  yScale?: 'linear' | 'log'
  /** Render a log/linear toggle next to the line/points bar (initial = yScale). */
  /** 在 线/点 切换条旁渲染 对数/线性 切换（初始值 = yScale）。 */
  yScaleToggle?: boolean
  /** Click-anywhere capture: while on, a NATIVE click listener converts the
   *  raw mouse position to data coordinates via Plotly's internal axis
   *  `p2d()` (approach borrowed from the POLYCRY reference implementation —
   *  `plotly_click` only fires near data points and is unreliable, which is
   *  exactly why region picking "couldn't hit the point"). Required by
   *  chart-picking interactions (region/background select / add peak).
   *  全图点击捕获：开启后在 Plotly 容器上挂原生 click 监听，用 Plotly 内部
   *  轴对象 p2d() 把鼠标像素坐标换算为数据坐标（方法取自 POLYCRY 参考实
   *  现——plotly_click 只在数据点附近触发且不可靠，正是此前选区「点不中」
   *  的根因）。供图上拾取交互（选区/背景选区/加峰）使用。 */
  clickCapture?: boolean
  /** Disable Plotly's drag gestures (pan/zoom box) so custom mouse-drag
   *  interactions (PeakFit-style anchor dragging) own the gesture. Wheel
   *  zoom stays available. / 关闭 Plotly 拖拽手势（平移/框选缩放），让自定
   *  义鼠标拖拽（PeakFit 式锚点拖动）接管手势；滚轮缩放仍可用。 */
  disableDrag?: boolean
}>(), {
  xLabel: 'x',
  yLabel: 'Intensity',
  xUnit: '',
  yUnit: '',
  title: '',
  yScale: 'linear',
  yScaleToggle: false,
  clickCapture: false,
  disableDrag: false,
  annotations: () => [],
})

const { t } = useI18n()

/** Trace render mode: line chart vs. scatter (points) only. / 折线渲染模式：线图 / 点图。 */
type LineMode = 'lines' | 'markers'
const lineMode = ref<LineMode>('lines')

/** Live y-axis scale; starts at the yScale prop and tracks it if the parent changes it. */
/** y 轴当前刻度；初始取 yScale 属性，父组件改变时跟随。 */
const yScaleState = ref<'linear' | 'log'>(props.yScale)
watch(() => props.yScale, (v) => { yScaleState.value = v })

const traces = computed<PlotData[]>(() =>
  props.traces.map((tr): PlotData => {
    const common = {
      x: tr.x,
      y: tr.y,
      name: tr.name ?? '',
      type: 'scatter',
      mode: lineMode.value,
    }
    // Only attach the style container for the active mode — never set the other to
    // `undefined`: Plotly's cleanData throws `'line' in undefined` on an explicit undefined.
    // 只为当前模式挂样式容器；切勿把另一个显式置为 undefined，否则 Plotly cleanData 会报错。
    if (lineMode.value === 'lines') {
      return {
        ...common,
        line: {
          width: 1.5,
          ...(tr.color ? { color: tr.color } : {}),
          ...(tr.dash ? { dash: tr.dash } : {}),
        },
      }
    }
    return { ...common, marker: tr.color ? { color: tr.color, size: 4 } : { size: 4 } }
  })
)

const chartLayout = computed<Partial<PlotLayout>>(() => ({
  title: props.title ? { text: props.title } : undefined,
  margin: { t: 48, autoexpand: true },
  hoverdistance: 20,
  ...(props.disableDrag ? { dragmode: false as unknown as PlotLayout['dragmode'] } : {}),
  // PeakFit-style free labels: centered above the anchor, in the peak's own
  // colour. / PeakFit 式自由标签：锚点正上方、使用该峰自己的颜色。
  annotations: props.annotations.map((a) => ({
    x: a.x,
    y: a.y,
    xref: 'x',
    yref: 'y',
    text: a.text,
    showarrow: false,
    yanchor: 'bottom',
    font: { size: 10, color: a.color ?? '#e2e8f0' },
  })),
  hoverlabel: {
    bgcolor: '#1e293b',
    bordercolor: '#475569',
    font: { color: '#f1f5f9', size: 12 },
    align: 'left',
    namelength: -1,
  },
  xaxis: {
    title: { text: axisTitle(props.xLabel, props.xUnit) },
  },
  yaxis: {
    title: { text: axisTitle(props.yLabel, props.yUnit) },
    type: yScaleState.value,
  },
}))

const chartConfig = {
  scrollZoom: true,
  displayModeBar: true,
  modeBarButtonsToRemove: ['lasso2d', 'select2d'],
}

// ── Free-click capture (reference: POLYCRY RawView._addFreeClickListener) ──
// A native click listener on the Plotly container converts the mouse pixel to
// a data value through the axis object's p2d(). Unlike plotly_click it works
// on ANY position (empty space included) and is unaffected by dragmode —
// plotly_click's proximity requirement was the root cause of the 2026-10-13
// "can't hit the point when picking the region" report.
// 在 Plotly 容器上挂原生 click 监听，经轴对象 p2d() 把鼠标像素换算为数据
// 坐标：图面任意位置（含空白处）都生效且不受 dragmode 影响——
// plotly_click 的近点限制正是 2026-10-13「选区点不中」的根因。
const plotlyRef = ref<{ getContainer: () => HTMLElement | null } | null>(null)

interface PlotlyAxisLike {
  _offset?: number
  _length?: number
  p2d?: (pixel: number) => number
}
interface PlotlyFullLayoutLike {
  xaxis?: PlotlyAxisLike
  yaxis?: PlotlyAxisLike
}

function nativeClickHandler(e: MouseEvent): void {
  if (!props.clickCapture) return
  const el = plotlyRef.value?.getContainer()
  if (!el) return
  const layout = (el as unknown as { _fullLayout?: PlotlyFullLayoutLike })._fullLayout
  const xaxis = layout?.xaxis
  const yaxis = layout?.yaxis
  if (!xaxis || typeof xaxis.p2d !== 'function') return
  const rect = el.getBoundingClientRect()
  const xPixel = e.clientX - rect.left - (xaxis._offset ?? 0)
  const yPixel = e.clientY - rect.top - (yaxis?._offset ?? 0)
  if (xPixel < 0 || xPixel > (xaxis._length ?? 0)) return // outside plot area
  const x = xaxis.p2d(xPixel)
  const y = yaxis && typeof yaxis.p2d === 'function' ? yaxis.p2d(yPixel) : Number.NaN
  if (Number.isFinite(x)) emit('capture:click', { x, y })
}

onMounted(() => {
  const el = plotlyRef.value?.getContainer()
  el?.addEventListener('click', nativeClickHandler)
})

onBeforeUnmount(() => {
  const el = plotlyRef.value?.getContainer()
  el?.removeEventListener('click', nativeClickHandler)
})

/** Container passthrough for custom drag interactions (PeakFit anchors). */
/** 容器透出，供自定义拖拽交互（PeakFit 锚点）使用。 */
defineExpose({
  getContainer: (): HTMLElement | null => plotlyRef.value?.getContainer() ?? null,
})
</script>

<style scoped>
.line-chart-wrap {
  position: relative;
  overflow: visible;
}
.line-chart-wrap :deep(.plotly) {
  overflow: visible !important;
}
.line-chart-wrap :deep(.js-plotly-plot .plotly .hoverlayer) {
  overflow: visible !important;
}

/* Floating line/points toggle pinned top-left so it never clashes with Plotly's top-right modebar. */
/* 浮动 线/点 切换条置于左上角，避开 Plotly 右上角工具栏。 */
.lc-mode-bar {
  position: absolute;
  top: 8px;
  left: 8px;
  z-index: 5;
  display: inline-flex;
  gap: 2px;
  padding: 3px;
  border-radius: var(--radius-md, 6px);
  background: rgba(18, 20, 26, 0.78);
  border: 1px solid var(--border, rgba(255, 255, 255, 0.12));
  backdrop-filter: blur(4px);
}

.lc-mode-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 9px;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: var(--text-secondary, rgba(255, 255, 255, 0.72));
  font-size: 0.75rem;
  line-height: 1;
  cursor: pointer;
  transition: background-color var(--transition-fast, 0.12s), color var(--transition-fast, 0.12s);
}

.lc-mode-btn:hover {
  color: var(--text-primary, #fff);
}

.lc-mode-active {
  background: var(--primary, #3b82f6);
  color: #fff;
}

.lc-icon {
  flex: 0 0 auto;
}

.lc-divider {
  align-self: stretch;
  width: 1px;
  margin: 2px 3px;
  background: var(--border, rgba(255, 255, 255, 0.18));
}

.lc-label {
  white-space: nowrap;
}
</style>
