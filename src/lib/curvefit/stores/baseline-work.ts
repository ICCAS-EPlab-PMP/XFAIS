/**
 * Baseline workbench store — the original 自动拟合 Baseline interaction:
 * detect → fit → human point selection (click to toggle, drag-right to
 * exclude a band, drag-left to restore) → immediate refit every edit.
 */
import { reactive, ref, shallowRef } from 'vue'
import type { BaselineMethod, BaselineModelId, BaselineFitResult } from '@/lib/pwcore/core'
import { DEFAULT_CONSTRAINTS } from '@/lib/pwcore/shared/types'
import { BASELINE_FN_MAP } from '@/lib/pwcore/shared/registry'
import { autoBaseline, refitBaseline, subtractBaseline } from '../core-bridge/engine'
import { platform } from '../platform/platform'
import { useSpectrum } from '../stores/spectrum'
import { setBaselineEnabled, setBaselineParam, usePeaks } from '../stores/peaks'
import { useFit } from '../stores/fit'
import { pushCommand } from '../stores/undo'
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

/** True while 应用为联合基线 is fitting the scan curve. */
const applying = ref(false)

/**
 * Route A → route B bridge: make the scanned curve the baseline the fit REALLY
 * uses. The selected parametric baseline function is fitted to the scan vector
 * (every point, so it tracks the drawn curve), its parameters are committed as
 * the joint baseline, and the scan preview is retired — from then on the drawn
 * baseline and the fitted baseline are the same parameters. No numeric core
 * change: this reuses the fit worker with the scan curve as its data.
 * 路线 A → 路线 B 桥接：让扫描曲线成为拟合真正使用的基线。用当前选定的参数化
 * 基线函数拟合扫描向量（全点，贴合所画曲线），把参数提交为联合基线并退掉扫描
 * 预览——此后图上基线与拟合基线是同一份参数。不改数值内核：复用拟合 Worker，
 * 把扫描曲线当作它的数据。
 */
async function applyAsJointBaseline(): Promise<boolean> {
  const sp = useSpectrum()
  const pk = usePeaks()
  const x = sp.x.value
  const z = fit.value ? fit.value.z : null
  if (!x || !z || z.length !== x.length) {
    pushToast('warn', '没有可用的扫描基线：请先自动检测基线')
    return false
  }
  const meta = BASELINE_FN_MAP.get(pk.baseline.fn)
  if (!meta || meta.params.length === 0) {
    pushToast('warn', '请先在路线 B 选择一个带参数的基线函数（如 BGLIN）')
    return false
  }
  if (applying.value || useFit().status.value === 'running') {
    pushToast('info', '已有拟合正在运行：请稍候再应用为联合基线')
    return false
  }

  applying.value = true
  const before = pk.exportSnapshot()
  const prevScan = { fit: fit.value, used: used.value, active: active.value }
  const retire = (): void => {
    used.value = null
    fit.value = null
    active.value = false
    publish()
  }
  try {
    const outcome = await platform.fit({
      jobId: `basescan-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      x,
      y: z,
      mask: new Uint8Array(x.length).fill(1),
      peaks: [],
      baseline: { fn: pk.baseline.fn, p: { ...pk.baseline.p }, locked: {}, enabled: true },
      options: {
        maxIter: 300,
        convDigits: 6,
        robust: 'ls',
        fitExtent: 1,
        xMin: null,
        xMax: null,
        constraints: DEFAULT_CONSTRAINTS,
      },
      stream: false,
    })
    if (!outcome.ok) {
      pushToast('error', `应用为联合基线失败：${outcome.error}`)
      return false
    }
    for (const pm of meta.params) {
      const v = outcome.baselineP[pm.key]
      if (typeof v === 'number' && Number.isFinite(v)) setBaselineParam(pm.key, v)
    }
    setBaselineEnabled(true)
    const after = pk.exportSnapshot()
    retire()
    pushCommand({
      label: '应用扫描基线为联合基线',
      undo: () => {
        pk.importSnapshot(before)
        fit.value = prevScan.fit
        used.value = prevScan.used
        active.value = prevScan.active
        publish()
      },
      redo: () => {
        pk.importSnapshot(after)
        retire()
      },
    })
    const r2 = outcome.stats.r2
    const r2Text = Number.isFinite(r2) ? r2.toFixed(4) : '—'
    if (r2 >= 0.98) {
      pushToast('success', `已应用为联合基线（${meta.name}，对扫描曲线 R²=${r2Text}）：后续拟合与图上包络都用它`)
    } else {
      pushToast(
        'warn',
        `已应用为联合基线（${meta.name}），但它对扫描曲线贴合较差（R²=${r2Text}）：` +
          '可换基线函数后重试，或改用「扣除为新数据」',
      )
    }
    return true
  } catch (err) {
    pushToast('error', `应用为联合基线异常：${err instanceof Error ? err.message : String(err)}`)
    return false
  } finally {
    applying.value = false
  }
}

export function useBaselineWork() {
  return { opts, used, fit, version, active, applying, detect, refit, togglePoint, excludeBand, includeBand, buildSubtracted, applyAsJointBaseline, clear }
}
