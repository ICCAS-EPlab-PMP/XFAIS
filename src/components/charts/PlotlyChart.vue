<template>
  <div
    ref="containerRef"
    data-testid="plotly-chart"
    class="plotly-chart-container"
  />
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'
import Plotly from 'plotly.js-dist-min'
import type { PlotData, PlotLayout, PlotConfig } from 'plotly.js-dist-min'
import { mergeDarkLayout } from '@/lib/chart-utils'

const emit = defineEmits<{
  'plot:click': [event: unknown]
  'plot:hover': [event: unknown]
  'plot:relayout': [event: unknown]
}>()

const props = defineProps<{
  data: PlotData[]
  layout?: Partial<PlotLayout>
  config?: Partial<PlotConfig>
  darkMode?: boolean
}>()

const containerRef = ref<HTMLElement | null>(null)
let resizeObserver: ResizeObserver | null = null
let isDestroyed = false

function resolvedLayout(): Partial<PlotLayout> {
  if (props.darkMode === false) return { ...props.layout }
  return mergeDarkLayout(props.layout ?? {})
}

function resolvedConfig(): Partial<PlotConfig> {
  return {
    responsive: true,
    displaylogo: false,
    ...props.config,
  }
}

function renderChart(): void {
  if (!containerRef.value || isDestroyed) return
  Plotly.react(
    containerRef.value,
    props.data,
    resolvedLayout(),
    resolvedConfig()
  ).then(() => {
    bindEvents()
  })
}

function bindEvents(): void {
  const el = containerRef.value
  if (!el) return
  el.removeEventListener('plotly_click', handleClick)
  el.removeEventListener('plotly_hover', handleHover)
  el.removeEventListener('plotly_relayout', handleRelayout)
  el.addEventListener('plotly_click', handleClick as EventListener)
  el.addEventListener('plotly_hover', handleHover as EventListener)
  el.addEventListener('plotly_relayout', handleRelayout as EventListener)
}

function handleClick(e: Event & { points?: unknown[] }): void {
  emit('plot:click', e)
}
function handleHover(e: Event & { points?: unknown[] }): void {
  emit('plot:hover', e)
}
function handleRelayout(e: Event): void {
  emit('plot:relayout', e)
}

function setupResizeObserver(): void {
  if (!containerRef.value) return
  resizeObserver = new ResizeObserver(() => {
    if (!containerRef.value || isDestroyed) return
    Plotly.Plots.resize(containerRef.value)
  })
  resizeObserver.observe(containerRef.value)
}

onMounted(() => {
  renderChart()
  setupResizeObserver()
})

onBeforeUnmount(() => {
  isDestroyed = true
  resizeObserver?.disconnect()
  resizeObserver = null
  const el = containerRef.value
  if (el) {
    el.removeEventListener('plotly_click', handleClick as EventListener)
    el.removeEventListener('plotly_hover', handleHover as EventListener)
    el.removeEventListener('plotly_relayout', handleRelayout as EventListener)
    Plotly.purge(el)
  }
})

watch(
  () => [props.data, props.layout, props.config, props.darkMode] as const,
  () => {
    renderChart()
  },
  { deep: true }
)

defineExpose({
  downloadImage(filename: string = 'chart') {
    if (!containerRef.value) return
    Plotly.downloadImage(containerRef.value, {
      format: 'png',
      width: 1200,
      height: 800,
      scale: 2,
      filename,
    })
  },
  getContainer(): HTMLElement | null {
    return containerRef.value
  },
})
</script>

<style scoped>
.plotly-chart-container {
  width: 100%;
  min-height: 320px;
}
</style>
