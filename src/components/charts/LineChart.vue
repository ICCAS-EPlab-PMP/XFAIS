<template>
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
</template>

<script setup lang="ts">
import { computed } from 'vue'
import PlotlyChart from './PlotlyChart.vue'
import type { PlotData, PlotLayout } from 'plotly.js-dist-min'
import { axisTitle } from '@/lib/chart-utils'

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
}

const props = withDefaults(defineProps<{
  traces: LineTrace[]
  xLabel?: string
  yLabel?: string
  xUnit?: string
  yUnit?: string
  title?: string
}>(), {
  xLabel: 'x',
  yLabel: 'Intensity',
  xUnit: '',
  yUnit: '',
  title: '',
})

const traces = computed<PlotData[]>(() =>
  props.traces.map((t) => ({
    x: t.x,
    y: t.y,
    name: t.name ?? '',
    type: 'scattergl',
    mode: 'lines',
    line: t.color ? { color: t.color, width: 1.5 } : { width: 1.5 },
  }))
)

const chartLayout = computed<Partial<PlotLayout>>(() => ({
  title: props.title ? { text: props.title } : undefined,
  xaxis: {
    title: { text: axisTitle(props.xLabel, props.xUnit) },
  },
  yaxis: {
    title: { text: axisTitle(props.yLabel, props.yUnit) },
  },
}))

const chartConfig = {
  scrollZoom: true,
  displayModeBar: true,
  modeBarButtonsToRemove: ['lasso2d', 'select2d'],
}
</script>
