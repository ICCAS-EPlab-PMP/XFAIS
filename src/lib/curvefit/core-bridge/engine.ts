/**
 * core-bridge — the ONLY renderer module that imports @core directly.
 *
 * ASSUMED CORE EXPORTS (see agent summary for the integration checklist):
 *
 *   import {
 *     evalPeak,        (fn: PeakFnId, p: ParamValues, xs: ArrayLike<number>, out?: Float64Array) => Float64Array
 *     evalBaseline,    (fn: BaselineFnId, p: ParamValues, xs: ArrayLike<number>, out?: Float64Array) => Float64Array
 *     runFit,          (req: FitRequest, onIter?: (e: FitIterEvent) => void) => Promise<FitOutcome>
 *     stopFit,         () => void   // 停止并保留 semantics
 *     abortFit,        () => void   // 中止并回滚 semantics
 *     detectPeaks,     (x: Float64Array, y: Float64Array, opts: DetectOptions) => DetectedPeak[]
 *     smoothData,      (y: Float64Array, opts: SmoothOptions) => Float64Array
 *     parseData,       (text: string, fileName?: string) => ParsedData
 *     makeDemoData,    (kind: DemoKind) => DemoData
 *   } from '@core'
 *
 * The flattened parameter-vector ordering below MUST match the fitting core
 * exactly (shared contract note in types.ts): [peak0 a-params…, peak1 …,
 * baseline b-params…] over ENABLED peaks / ENABLED baseline and UNLOCKED
 * parameters only, each group in registry declaration order.
 */
import type {
  BaselineSpec,
  DemoData,
  DemoKind,
  DetectOptions,
  DetectedPeak,
  FitIterEvent,
  FitOutcome,
  FitRequest,
  ParamValues,
  PeakSpec,
  ParsedData,
  SmoothOptions,
} from '@/lib/pwcore/shared/types'
import type { BaselineFnId, PeakFnId } from '@/lib/pwcore/shared/registry'
import { BASELINE_FN_MAP, PEAK_FN_MAP } from '@/lib/pwcore/shared/registry'

// -- assumed core surface ----------------------------------------------------

export {
  evalPeak,
  evalBaseline,
  runFit,
  stopFit,
  abortFit,
  detectPeaks,
  smoothData,
  parseData,
  makeDemoData,
  measurePeakGeometry,
  solveAnchorDrag,
  autoscanBaseline,
  autoBaseline,
  refitBaseline,
  detectBaselinePoints,
  subtractBaseline,
} from '@/lib/pwcore/core'
export type {
  PeakGeometry,
  AnchorKind,
  AnchorDragInput,
  AutoscanOptions,
  BaselineMethod,
  BaselineModelId,
  BaselineFitResult,
} from '@/lib/pwcore/core'

import { evalPeak as coreEvalPeak } from '@/lib/pwcore/core'

// -- scalar helpers -----------------------------------------------------------

/** Evaluate a peak component at a single x. */
export function evalPeakAt(fn: PeakFnId, p: ParamValues, x: number): number {
  const out = coreEvalPeak(fn, p, [x])
  return out[0] ?? Number.NaN
}

/**
 * Registry keys that scale peak *width*. Used by the width anchor: dragging
 * the half-height anchor rescales every width-like parameter by the same
 * factor (a2, plus secondary widths like Voigt a3 / EMG tau when derived
 * from 'autoWidth' init).
 */
export function widthKeysOf(fn: PeakFnId): string[] {
  const meta = PEAK_FN_MAP.get(fn)
  if (!meta) return ['a2']
  return meta.params.filter((pm) => pm.key === 'a2' || pm.init === 'autoWidth').map((pm) => pm.key)
}

/** Representative width scale of a peak (smallest width-like parameter). */
export function widthScaleOf(fn: PeakFnId, p: ParamValues): number {
  const keys = widthKeysOf(fn)
  let w = Number.POSITIVE_INFINITY
  for (const k of keys) {
    const v = p[k]
    if (typeof v === 'number' && Number.isFinite(v) && v > 0 && v < w) w = v
  }
  return Number.isFinite(w) ? w : 1
}

/**
 * Numeric FWHM estimate by half-height crossing search around a1.
 * Uses only evalPeak (no core dependency beyond the contract).
 */
export function estimateFwhm(fn: PeakFnId, p: ParamValues, heightHint?: number): number {
  const h = heightHint !== undefined && Number.isFinite(heightHint) ? heightHint : evalPeakAt(fn, p, p.a1)
  const ah = Math.abs(h) / 2
  const w0 = widthScaleOf(fn, p)
  if (!(ah > 0) || !(w0 > 0)) return w0 * 2.355

  const half = ah

  const cross = (dir: 1 | -1): number => {
    let step = Math.max(w0, 1e-12)
    let xPrev = p.a1
    for (let i = 0; i < 220; i++) {
      const x = xPrev + dir * step
      const f = Math.abs(evalPeakAt(fn, p, x))
      if (f < half) {
        // binary search between xPrev (>= half) and x (< half)
        let lo = xPrev
        let hi = x
        for (let j = 0; j < 48; j++) {
          const mid = (lo + hi) / 2
          if (Math.abs(evalPeakAt(fn, p, mid)) >= half) lo = mid
          else hi = mid
        }
        return Math.abs(hi - p.a1)
      }
      xPrev = x
      step *= 1.35
    }
    return Number.NaN
  }

  const right = cross(1)
  const left = cross(-1)
  const fwhm = (Number.isFinite(right) ? right : w0 * 1.177) + (Number.isFinite(left) ? left : w0 * 1.177)
  return Math.max(fwhm, w0 * 0.05)
}

// -- flattened parameter vector (MUST mirror the core) ------------------------

/** Flatten enabled peaks + enabled baseline over unlocked params (fit request/stream order). */
export function flattenModel(peaks: readonly PeakSpec[], baseline: BaselineSpec): number[] {
  const flat: number[] = []
  for (const pk of peaks) {
    if (!pk.enabled) continue
    const meta = PEAK_FN_MAP.get(pk.fn)
    if (!meta) continue
    for (const pm of meta.params) {
      if (pk.locked[pm.key]) continue
      flat.push(pk.p[pm.key] ?? 0)
    }
  }
  if (baseline.enabled && baseline.fn !== 'none') {
    const meta = BASELINE_FN_MAP.get(baseline.fn)
    if (meta) {
      for (const pm of meta.params) {
        if (baseline.locked[pm.key]) continue
        flat.push(baseline.p[pm.key] ?? 0)
      }
    }
  }
  return flat
}

/**
 * Write a flattened vector back into (copies of) the model.
 * Returns the updated specs; caller decides where to apply them.
 */
export function unflattenInto(
  flat: ArrayLike<number>,
  peaks: readonly PeakSpec[],
  baseline: BaselineSpec,
): { peaks: PeakSpec[]; baseline: BaselineSpec } {
  let k = 0
  const nextPeaks: PeakSpec[] = peaks.map((pk) => {
    const copy: PeakSpec = { ...pk, p: { ...pk.p }, locked: { ...pk.locked } }
    if (!copy.enabled) return copy
    const meta = PEAK_FN_MAP.get(copy.fn)
    if (!meta) return copy
    for (const pm of meta.params) {
      if (copy.locked[pm.key]) continue
      if (k < flat.length) copy.p[pm.key] = flat[k]
      k++
    }
    return copy
  })
  const nextBaseline: BaselineSpec = {
    ...baseline,
    p: { ...baseline.p },
    locked: { ...baseline.locked },
  }
  if (nextBaseline.enabled && nextBaseline.fn !== 'none') {
    const meta = BASELINE_FN_MAP.get(nextBaseline.fn)
    if (meta) {
      for (const pm of meta.params) {
        if (nextBaseline.locked[pm.key]) continue
        if (k < flat.length) nextBaseline.p[pm.key] = flat[k]
        k++
      }
    }
  }
  return { peaks: nextPeaks, baseline: nextBaseline }
}

// re-export shared types for convenience of downstream renderer modules
export type { BaselineFnId, PeakFamily, PeakFnId } from '@/lib/pwcore/shared/registry'
export type {
  BaselineSpec,
  DemoData,
  DemoKind,
  DetectOptions,
  DetectedPeak,
  FitIterEvent,
  FitOutcome,
  FitRequest,
  ParamValues,
  PeakSpec,
  ParsedData,
  SmoothOptions,
} from '@/lib/pwcore/shared/types'
