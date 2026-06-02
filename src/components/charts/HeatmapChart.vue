<template>
  <PlotlyChart
    :data="heatmapData"
    :layout="chartLayout"
    :config="chartConfig"
    :dark-mode="true"
    data-testid="heatmap-chart"
    @plot:click="(e) => emit('plot:click', e)"
    @plot:hover="(e) => emit('plot:hover', e)"
    @plot:relayout="(e) => emit('plot:relayout', e)"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import PlotlyChart from './PlotlyChart.vue'
import type { PlotData, PlotLayout } from 'plotly.js-dist-min'
import { COLORMAP_PRESETS, axisTitle } from '@/lib/chart-utils'
import type { ColormapName } from '@/lib/chart-utils'

const emit = defineEmits<{
  'plot:click': [event: unknown]
  'plot:hover': [event: unknown]
  'plot:relayout': [event: unknown]
}>()

const props = withDefaults(defineProps<{
  z: (number | null)[][]
  x?: number[]
  y?: number[]
  colorscale?: ColormapName | string
  zmin?: number
  zmax?: number
  logScale?: boolean
  title?: string
  xLabel?: string
  yLabel?: string
  xUnit?: string
  yUnit?: string
}>(), {
  colorscale: 'viridis',
  logScale: false,
  xLabel: 'x',
  yLabel: 'y',
  x: () => [],
  y: () => [],
  zmin: undefined,
  zmax: undefined,
  title: '',
  xUnit: '',
  yUnit: '',
})

function resolveColorscale(name: string): string | (string | number)[][] {
  if (name in COLORMAP_PRESETS) return COLORMAP_PRESETS[name as ColormapName]
  return name
}

const heatmapData = computed<PlotData[]>(() => [{
  z: props.z,
  x: props.x,
  y: props.y,
  type: 'heatmap',
  colorscale: resolveColorscale(props.colorscale),
  showscale: true,
  zmin: props.zmin,
  zmax: props.zmax,
  zauto: props.zmin === undefined || props.zmax === undefined,
  colorbar: {
    thickness: 16,
    outlinewidth: 0,
    tickfont: { color: '#94a3b8', size: 10 },
  },
}])

const chartLayout = computed<Partial<PlotLayout>>(() => ({
  title: props.title ? { text: props.title } : undefined,
  xaxis: {
    title: { text: axisTitle(props.xLabel, props.xUnit) },
    scaleanchor: 'y',
    scaleratio: 1,
    constrain: 'range',
  },
  yaxis: {
    title: { text: axisTitle(props.yLabel, props.yUnit) },
    scaleanchor: 'x',
    scaleratio: 1,
    constrain: 'range',
  },
}))

const chartConfig = {
  scrollZoom: true,
  displayModeBar: true,
  modeBarButtonsToRemove: ['lasso2d', 'select2d'],
}
</script>
