/**
 * UI state: workflow step, hover readout, popover anchor, display prefs.
 */
import { ref } from 'vue'

export type StepId = 'data' | 'baseline' | 'peaks' | 'fit' | 'report' | 'polymer'

export const STEPS: { id: StepId; label: string; hint: string }[] = [
  { id: 'data', label: '数据', hint: '导入 / 查看数据' },
  { id: 'baseline', label: '基线', hint: '选择并预览基线' },
  { id: 'peaks', label: '放峰', hint: '左键点击图区放峰' },
  { id: 'fit', label: '拟合', hint: '运行拟合引擎' },
  { id: 'report', label: '报告', hint: '统计审阅与导出' },
  { id: 'polymer', label: '聚合物', hint: '结晶度 / 取向 / Kβ（按需开启）' },
]

/** Workflow order index; used to gate steps before data exists. */
export function stepIndex(id: StepId): number {
  return STEPS.findIndex((s) => s.id === id)
}

const step = ref<StepId>('data')

const hover = ref<{ x: number; y: number } | null>(null)

/** 峰调整 popover anchor (viewport coords of the peak's main anchor). */
const popover = ref<{ peakId: string; cx: number; cy: number } | null>(null)

/** Show raw data points as markers (auto-on for small datasets). */
const showPoints = ref(true)

/** Baseline page: preview data with the baseline subtracted. */
const subtractPreview = ref(false)

/** Live chart controller handle (PNG export); set by PlotArea on mount. */
export interface ChartHandle {
  exportPng(): Promise<Uint8Array | null>
}
const chart = ref<ChartHandle | null>(null)

export function useUi() {
  return {
    step,
    hover,
    popover,
    showPoints,
    subtractPreview,
    chart,
  }
}
