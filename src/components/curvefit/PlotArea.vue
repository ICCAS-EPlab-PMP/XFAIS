<script setup lang="ts">
import 'uplot/dist/uPlot.min.css'
/**
 * Central charts: main uPlot (data/fit/baseline/peaks) + residual uPlot with
 * shared x, plus the PlotController that owns rendering & interaction.
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import EmptyState from './EmptyState.vue'
import { PlotController } from '@/lib/curvefit/chart/plotController'
import { useSpectrum } from '@/lib/curvefit/stores/spectrum'
import { useFit } from '@/lib/curvefit/stores/fit'
import { usePeaks } from '@/lib/curvefit/stores/peaks'
import { useBaselineWork } from '@/lib/curvefit/stores/baseline-work'
import { useTheme } from '@/lib/curvefit/stores/theme'
import { useUi } from '@/lib/curvefit/stores/ui'
import { importFromPlatform, loadDemoSet } from '@/lib/curvefit/stores/session'

const sp = useSpectrum()
const fit = useFit()
const pk = usePeaks()
const blWork = useBaselineWork()
const theme = useTheme()
const ui = useUi()

const mainEl = ref<HTMLElement | null>(null)
const residEl = ref<HTMLElement | null>(null)
const legendEl = ref<HTMLElement | null>(null)
let ctrl: PlotController | null = null

const initController = (): void => {
  if (ctrl || !mainEl.value || !residEl.value) return
  ctrl = new PlotController(mainEl.value, residEl.value, legendEl.value)
  ctrl.attach()
  ui.chart.value = ctrl
}

onMounted(() => initController())

// The chart hosts only exist once data arrives (v-if branch above), long after
// this component mounted — initialize the controller at that moment too.
watch(
  [mainEl, residEl, legendEl],
  () => initController(),
  { flush: 'post' },
)

onBeforeUnmount(() => {
  ctrl?.destroy()
  ctrl = null
  ui.chart.value = null
})

// --- store → controller wiring ---------------------------------------------

watch(
  [
    () => sp.dataVersion.value,
    () => pk.structureVersion.value,
    () => theme.mode.value,
    () => ui.subtractPreview.value,
    () => ui.showPoints.value,
  ],
  () => ctrl?.rebuild(),
)

// A new y column (import, smoothing, baseline subtraction/undo) invalidates
// the 自动拟合 Baseline point set: it belongs to the previous data table.
// / 新数据表作废旧的点集（索引语义）。
watch(() => sp.dataVersion.value, () => {
  blWork.clear()
})

watch(
  [
    () => pk.curvesVersion.value,
    () => fit.curvesTick.value,
    () => blWork.version.value,
    // Mask flips change the DATA column (excluded points become null gaps),
    // so they must repaint the series, not just the overlay.
    // 掩膜变化会改变数据列（排除点变为 null 断口），必须重推数据而不只是重画叠加层。
    () => sp.maskVersion.value,
  ],
  () => {
    ctrl?.refreshChart(false)
  },
)

watch(
      [
        () => pk.selectedId.value,
        () => ui.step.value,
        () => ui.popover.value,
      ],
      () => ctrl?.drawOverlay(),
    )

const hasData = computed(() => sp.ready.value)

/**
 * Interaction hint for the main chart: the per-step gesture vocabulary.
 * 图区提示：各步骤的手势说明。
 */
const hintText = computed(
  () => '滚轮缩放横轴（y 轴不动）· 右键/双击复位 · 数据/基线：单击切点，右拖排除段，左拖恢复 · 放峰：左键放峰',
)
</script>

<template>
  <section class="plot-area">
    <template v-if="hasData">
      <div class="chart-block main">
        <div class="chart-label">
          <span class="lbl">数据 / 拟合</span>
          <span class="tip">{{ hintText }}</span>
          <div ref="legendEl" class="pf-legend" />
        </div>
        <div ref="mainEl" class="chart-host" />
      </div>
      <div class="chart-block resid">
        <div class="chart-label"><span class="lbl">残差 Residual</span></div>
        <div ref="residEl" class="chart-host" />
      </div>
    </template>
    <EmptyState v-else @import="importFromPlatform" @demo="loadDemoSet('chrom')" />
  </section>
</template>

<style scoped>
.plot-area {
  flex: 1;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px 10px 6px;
}
.chart-block {
  position: relative;
  display: flex;
  flex-direction: column;
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  min-height: 0;
  transition: background-color var(--speed) ease, border-color var(--speed) ease;
}
.chart-block.main {
  flex: 72 1 0;
}
.chart-block.resid {
  flex: 28 1 0;
}
.chart-label {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 12px 0;
  font-size: var(--fs-small);
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--text-2);
  user-select: none;
  min-height: 22px;
}
.chart-label .lbl {
  flex: none;
}
.chart-label .tip {
  font-weight: 400;
  /* body copy on the white plot header: --text-3 (#94a3b8) is only ~2.6:1 */
  color: var(--text-2);
  letter-spacing: 0;
  flex: none;
}
.chart-host {
  flex: 1;
  min-height: 0;
  position: relative;
}

/* uPlot legend re-parented into the header row (never steals plot height) */
.pf-legend {
  margin-left: auto;
  min-width: 0;
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: thin;
}
.pf-legend :deep(.u-legend) {
  display: flex;
  flex-wrap: nowrap;
  align-items: center;
  font-size: var(--fs-small);
  line-height: 16px;
  margin: 0;
  padding: 0;
}
.pf-legend :deep(.u-legend tr) {
  display: inline-flex;
  align-items: center;
}
.pf-legend :deep(.u-legend tr.u-series:first-child) {
  display: none; /* the x "series" row */
}
.pf-legend :deep(.u-legend th) {
  display: inline-flex;
  align-items: center;
  padding: 1px 8px 1px 0;
  font-weight: 400;
  color: var(--text-2);
  white-space: nowrap;
  cursor: pointer;
}
.pf-legend :deep(.u-legend th:hover) {
  color: var(--text-1);
}
.pf-legend :deep(.u-legend .u-marker) {
  width: 12px;
  height: 2px;
  margin-right: 5px;
  border-radius: 1px;
}
.pf-legend :deep(.u-legend td) {
  display: none; /* live values off (legend.live = false) */
}
.pf-legend :deep(.u-legend tr.u-off th) {
  color: var(--text-3);
  text-decoration: line-through;
}
</style>
