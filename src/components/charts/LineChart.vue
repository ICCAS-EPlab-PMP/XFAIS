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
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import PlotlyChart from './PlotlyChart.vue'
import type { PlotData, PlotLayout } from 'plotly.js-dist-min'
import { axisTitle } from '@/lib/chart-utils'
import { testIds } from '@/lib/testIds'

const emit = defineEmits<{
  'plot:click': [event: unknown]
  'plot:hover': [event: unknown]
  'plot:relayout': [event: unknown]
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

const props = withDefaults(defineProps<{
  traces: LineTrace[]
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
}>(), {
  xLabel: 'x',
  yLabel: 'Intensity',
  xUnit: '',
  yUnit: '',
  title: '',
  yScale: 'linear',
  yScaleToggle: false,
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
