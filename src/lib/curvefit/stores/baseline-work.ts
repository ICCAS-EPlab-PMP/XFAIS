/**
 * Baseline workbench store — the original 自动拟合 Baseline interaction:
 * detect → fit → human point selection (click to toggle, drag-right to
 * exclude a band, drag-left to restore) → immediate refit every edit.
 */
import { reactive, ref, shallowRef } from 'vue'
import type { BaselineMethod, BaselineModelId, BaselineFitResult } from '@/lib/pwcore/core'
import { autoBaseline, refitBaseline, subtractBaseline } from '../core-bridge/engine'
import { useSpectrum } from '../stores/spectrum'
import { usePeaks } from '../stores/peaks'
import { pushToast } from '../stores/toast'

export const BASELINE_METHODS: { id: BaselineMethod; label: string; hint: string }[] = [
  { id: 'deriv2zero', label: '二阶导零', hint: '主算法：四步流水线（检测→拟合→残差再筛→重拟合）' },
  { id: 'progressive', label: '渐进线性', hint: '从两端渐进拟合直到拟合劣化（遇峰即停）' },
  { id: 'endpoints', label: '首尾连线', hint: '最简单：首末活动点连线' },
]

export const BASELINE_MODELS: { id: BaselineModelId; label: string }[] = [
  { id: 'best', label: 'Best（自动选型）' },
  { id: 'nparm', label: '非参数' },
  { id: 'const', label: '常数' },
  { id: 'lin', label: '线性' },
  { id: 'quad', label: '二次' },
  { id: 'cub', label: '三次' },
  { id: 'log', label: '对数' },
  { id: 'exp', label: '指数' },
  { id: 'pow', label: '幂' },
  { id: 'hyp', label: '双曲' },
]

const opts = reactive({
  method: 'deriv2zero' as BaselineMethod,
  model: 'best' as BaselineModelId,
  tol: 2,
  zeroNegative: true,
})

/** 1 = point participates in the baseline fit (bright), 0 = excluded (gray). */
const used = shallowRef<Uint8Array | null>(null)
/** Current baseline curve (drives the chart baseline series via scanBase). */
const fit = shallowRef<BaselineFitResult | null>(null)
/** Bumped on every change so the chart/panel can react cheaply. */
const version = ref(0)
const active = ref(false)

function publish(): void {
  version.value += 1
  usePeaks().setScanBase(fit.value ? fit.value.z : null)
}

/** Run detection + the full four-step pipeline; enters baseline mode. */
function detect(): boolean {
  const sp = useSpectrum()
  const x = sp.x.value
  const y = sp.y.value
  if (!x || !y) {
    pushToast('warn', '没有数据：请先导入数据')
    return false
  }
  const r = autoBaseline(opts.method, opts.model, x, y, sp.mask.value, opts.tol)
  if (!r) {
    pushToast('error', '基线检测失败：试着增大容差或换方法')
    return false
  }
  used.value = r.used
  fit.value = r
  active.value = true
  publish()
  return true
}

/** Refit on the current point set (every human edit calls this). */
function refit(): void {
  const sp = useSpectrum()
  const x = sp.x.value
  const y = sp.y.value
  const u = used.value
  if (!x || !y || !u) return
  const r = refitBaseline(opts.model, x, y, u)
  if (r) {
    fit.value = r
    used.value = r.used
    publish()
  }
}

function togglePoint(i: number): void {
  const u = used.value
  if (!u || i < 0 || i >= u.length) return
  u[i] = u[i] ? 0 : 1
  refit()
}

/** drag-right: exclude a band of points from the baseline set. */
function excludeBand(i0: number, i1: number): void {
  const u = used.value
  if (!u) return
  for (let i = Math.max(0, Math.min(i0, i1)); i <= Math.min(u.length - 1, Math.max(i0, i1)); i++) u[i] = 0
  refit()
}

/** drag-left: restore a band of points into the baseline set. */
function includeBand(i0: number, i1: number): void {
  const u = used.value
  if (!u) return
  for (let i = Math.max(0, Math.min(i0, i1)); i <= Math.min(u.length - 1, Math.max(i0, i1)); i++) u[i] = 1
  refit()
}

/** Apply y − baseline as the new data table (undoable by the caller). */
function buildSubtracted(): Float64Array | null {
  const sp = useSpectrum()
  const y = sp.y.value
  const z = fit.value ? fit.value.z : null
  if (!y || !z || z.length !== y.length) return null
  return subtractBaseline(y, z, opts.zeroNegative)
}

function clear(): void {
  used.value = null
  fit.value = null
  active.value = false
  publish()
}

export function useBaselineWork() {
  return { opts, used, fit, version, active, detect, refit, togglePoint, excludeBand, includeBand, buildSubtracted, clear }
}
