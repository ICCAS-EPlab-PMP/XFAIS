/**
 * Peak parameter guard (2026-10-20, 0.3.3 regression fix).
 *
 * REPRODUCED FAILURE this prevents: dragging a half-height anchor ACROSS the
 * peak center drives the width solver to the registry floor a2 = 1e-12. A
 * Gaussian that narrow is zero at every sampled data point, so the fit has no
 * width gradient; the ±50 % soft-constraint box is then re-anchored on 1e-12
 * at every later run and the peak can never be recovered — the fit "runs"
 * (a few iterations, same R²) but leaves the width frozen forever, which the
 * user reported as "手调半峰宽后无法进行后续拟合".
 * 复现的故障：把半高锚拖过峰心会把宽度反解到注册表下限 a2 = 1e-12。这么窄的
 * 高斯在所有采样点上都为零，拟合对宽度没有梯度；而 ±50% 软约束每次又以 1e-12
 * 为锚，导致该峰此后再也无法拟合（拟合“能跑”但宽度被永久冻结）——即用户报告
 * 的“手调半峰宽后无法进行后续拟合”。
 *
 * The same garbage can also arrive from the numeric editor (typing 0/1e-12/
 * 1e300), from an old undo snapshot, or from the peak-adjust popover. This
 * module centralises the data-driven sanity floor used at the drag source and
 * the defensive repair applied to the fit request.
 * 同样的无效值也可能来自数值输入（0/1e-12/1e300）、旧的撤销快照或峰调整浮层。
 * 本模块集中提供拖拽源使用的“数据可分辨宽度”下限，以及拟合请求的防御性修正。
 */
import type { ParamValues, PeakSpec } from '@/lib/pwcore/shared/types'
import { PEAK_FN_MAP, type PeakFnId } from '@/lib/pwcore/shared/registry'
import { measurePeakGeometry } from '../core-bridge/engine'

/** Data-derived scale factors used to judge peak parameters. */
export interface GuardContext {
  /** Finite x span (|xMax - xMin|), > 0. / 有限 x 跨度。 */
  span: number
  /** Mean x step of the sampled data (span / (n - 1), > 0). / 平均 x 步长。 */
  step: number
  /** Largest finite |y| in the data. / 数据 |y| 最大值。 */
  maxAbsY: number
  /** Midpoint of the finite x range. / x 范围中点。 */
  xMid: number
}

/** Build a guard context from the live data; null when unusable. */
export function guardContextFrom(x: ArrayLike<number>, y: ArrayLike<number>): GuardContext | null {
  const n = Math.min(x.length, y.length)
  if (n === 0) return null
  let lo = Number.POSITIVE_INFINITY
  let hi = Number.NEGATIVE_INFINITY
  let maxAbsY = 0
  for (let i = 0; i < n; i += 1) {
    const xv = x[i]
    if (Number.isFinite(xv)) {
      if (xv < lo) lo = xv
      if (xv > hi) hi = xv
    }
    const av = Math.abs(y[i])
    if (Number.isFinite(av) && av > maxAbsY) maxAbsY = av
  }
  if (!Number.isFinite(lo) || !Number.isFinite(hi)) return null
  const span = Math.max(hi - lo, 1e-12)
  const step = n > 1 ? Math.max(span / (n - 1), span * 1e-12) : span
  return { span, step, maxAbsY, xMid: 0.5 * (lo + hi) }
}

/**
 * Smallest width the sampled data can actually resolve. A peak much narrower
 * than one x step is invisible to the fit (zero model at every point, zero
 * Jacobian column) — such a width must never be sent to the engine.
 * 采样数据能分辨的最小宽度：窄于一个 x 步长的峰在拟合中完全不可见
 * （所有点模型值为零、雅可比列全零），这种宽度绝不能送进拟合引擎。
 */
export function minMeaningfulWidth(ctx: GuardContext): number {
  return Math.max(ctx.span * 1e-6, ctx.step)
}

/** Parameters that carry peak width (a2 and any autoWidth-initialised key). */
export function widthKeysOf(fn: PeakFnId): string[] {
  const meta = PEAK_FN_MAP.get(fn)
  if (!meta) return ['a2']
  const keys: string[] = []
  for (const pm of meta.params) {
    if (pm.key === 'a0' || pm.key === 'a1') continue
    if (pm.key === 'a2' || pm.init === 'autoWidth') keys.push(pm.key)
  }
  return keys.length > 0 ? keys : ['a2']
}

/** Width keys for one concrete peak spec (respects the current function). */
export function widthKeysOfSpec(spec: PeakSpec): string[] {
  return widthKeysOf(spec.fn)
}

/** Clamp one width value into the data-resolvable range. */
export function clampWidth(value: number, ctx: GuardContext): number {
  const minW = minMeaningfulWidth(ctx)
  const maxW = Math.max(ctx.span * 1e3, minW)
  if (!Number.isFinite(value)) return Math.min(Math.max(ctx.span / 20, minW), maxW)
  return Math.min(Math.max(value, minW), maxW)
}

export interface ParamRepair {
  key: string
  from: number
  to: number
}

function clampNum(v: number, lo: number, hi: number): number {
  return Math.min(Math.max(v, lo), hi)
}

/**
 * Convert a data-measured FWHM into the peak's width parameter by probing the
 * model's own FWHM↔parameter scaling (essentially linear for the built-in
 * peaks). Without this conversion a Gaussian sigma would be seeded with the
 * data FWHM (~2.35× too wide) and the ±50 % soft box would exclude the truth.
 * 把数据实测 FWHM 换算成峰的宽度参数：探测模型自身的 FWHM↔参数比例（内置峰形
 * 基本线性）。若不换算，高斯 sigma 会被种成数据 FWHM（约大 2.35 倍），±50%
 * 软约束盒将把真值排除在外。
 */
export function widthParamForFwhm(
  spec: PeakSpec,
  key: string,
  targetFwhm: number,
  probeWidth: number,
): number | null {
  if (!Number.isFinite(targetFwhm) || !(targetFwhm > 0)) return null
  // Always probe at a bounded, well-conditioned width: measuring geometry on
  // a 1e-12 / 1e308 value returns no half-max crossings and no seed.
  // 始终用有界的良态宽度做探测：在 1e-12 / 1e308 上测几何得不到半高交点。
  const probe = Number.isFinite(probeWidth) && probeWidth > 0 ? probeWidth : 1
  const probeP: ParamValues = { ...spec.p, [key]: probe }
  const g = measurePeakGeometry(spec.fn, probeP)
  if (g.leftHalfX === null || g.rightHalfX === null) return null
  const fwhm = g.rightHalfX - g.leftHalfX
  if (!Number.isFinite(fwhm) || !(fwhm > 0)) return null
  const out = (probe * targetFwhm) / fwhm
  return Number.isFinite(out) && out > 0 ? out : null
}

/**
 * Repair one peak's parameters IN PLACE on the supplied (plain, request-side)
 * spec. Returns the repairs performed; empty when the peak was already sane.
 * `seedWidth` is a data-driven width estimate (local half-height span) used
 * when the stored width is degenerate.
 * 就地修正一个峰的参数（作用于请求侧的普通对象）；返回修正记录。
 * `seedWidth` 为数据驱动的宽度估计（局部半高跨度），在存储宽度退化时使用。
 */
export function repairPeakParams(
  spec: PeakSpec,
  ctx: GuardContext,
  seedWidth: number | null,
): ParamRepair[] {
  const meta = PEAK_FN_MAP.get(spec.fn)
  if (!meta) return []
  const repairs: ParamRepair[] = []
  const minW = minMeaningfulWidth(ctx)
  const maxW = Math.max(ctx.span * 1e3, minW)
  const seedW = clampNum(
    Number.isFinite(seedWidth ?? Number.NaN) ? (seedWidth as number) : ctx.span / 20,
    minW,
    Math.max(ctx.span / 4, minW),
  )
  // Amplitude sanity ceiling: a0 far outside any plausible height/area scale
  // (e.g. 1e300 from a numerically degenerate drag) makes the LM step guard
  // reject every trial, so the peak is effectively frozen as well.
  // 幅值合理上限：远超任何合理峰高/面积的 a0（例如数值退化拖拽产生的 1e300）
  // 会让 LM 的步长守卫拒绝所有试探步，峰同样被冻结。
  const ampSeed = Math.max(ctx.maxAbsY * 0.25, 1e-12)
  const ampCap = Math.max(ctx.maxAbsY, 1) * Math.max(ctx.span, 1) * 1e6

  for (const pm of meta.params) {
    const key = pm.key
    const v = spec.p[key]
    const widthLike = key !== 'a0' && key !== 'a1' && (key === 'a2' || pm.init === 'autoWidth')

    if (key === 'a0') {
      if (!Number.isFinite(v) || Math.abs(v) > ampCap) {
        const to = Number.isFinite(v) && v < 0 ? -ampSeed : ampSeed
        spec.p[key] = to
        repairs.push({ key, from: v, to })
      }
    } else if (key === 'a1') {
      if (!Number.isFinite(v)) {
        spec.p[key] = ctx.xMid
        repairs.push({ key, from: v, to: ctx.xMid })
      }
    } else if (widthLike) {
      if (!Number.isFinite(v) || v < minW || v > maxW) {
        let to: number
        if (Number.isFinite(v) && v > maxW) {
          // A width far larger than the data range makes the model constant
          // over the window (zero gradient again) — reseed from the data.
          // 宽度远大于数据范围会让模型在窗口内成为常数（同样零梯度）——按数据重估。
          to =
            (seedWidth !== null
              ? widthParamForFwhm(spec, key, seedWidth, clampNum(ctx.span / 20, minW, maxW))
              : null) ?? Math.max(ctx.span / 20, minW)
        } else {
          // Seed from the data-measured FWHM converted into this parameter's
          // own scale, so the ±50 % soft box brackets the real peak again.
          // 用数据实测 FWHM 换算到该参数自身的量纲，使 ±50% 软约束盒重新包住真峰。
          to =
            (seedWidth !== null
              ? widthParamForFwhm(spec, key, seedWidth, clampNum(ctx.span / 20, minW, maxW))
              : null) ?? seedW
        }
        spec.p[key] = clampNum(to, minW, maxW)
        repairs.push({ key, from: v, to: spec.p[key] })
      }
    } else if (!Number.isFinite(v)) {
      const to = typeof pm.init === 'number' ? pm.init : 0
      spec.p[key] = to
      repairs.push({ key, from: v, to })
    }

    // Registry hard bounds always win (mirrors the engine's sanitize()).
    // 注册表硬边界始终优先（与引擎 sanitize() 一致）。
    let out = spec.p[key]
    if (pm.min !== null && out < pm.min) out = pm.min
    if (pm.max !== null && out > pm.max) out = pm.max
    if (out !== spec.p[key]) {
      repairs.push({ key, from: spec.p[key], to: out })
      spec.p[key] = out
    }
  }
  return repairs
}

/** Human-readable one-line summary for the repair toast. */
export function describeRepairs(repairs: ParamRepair[]): string {
  return repairs
    .map((r) => `${r.key}: ${Number.isFinite(r.from) ? r.from.toPrecision(4) : String(r.from)} → ${r.to.toPrecision(4)}`)
    .join('，')
}

/** Frozen-empty helper so callers can read a ParamValues safely. */
export const EMPTY_PARAMS: Readonly<ParamValues> = Object.freeze({})
